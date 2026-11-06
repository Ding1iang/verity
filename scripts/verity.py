#!/usr/bin/env python3
"""verity 命令行：生成任务交付骨架。

当前提供 `init` 子命令：按模板创建任务卡、07 验收账本、阻塞举证单和空的
evidence/ 目录。它只搭骨架，不写证据、不判断通过，也不替执行者填写范围、
验收项、判据和证据。

模板来源：
- 仓库自带 `templates/` 是默认骨架；
- 项目适配层可通过 `paths.task_card_template`、`paths.ledger_template`、
  `paths.blocking_form_template` 指定项目模板，路径相对项目根。

只使用 Python 标准库。退出码：0 = 创建成功；1 = 目标目录已存在等业务
拒绝；2 = 参数、模板或文件读写错误。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional


# 脚本位于 <仓库根>/scripts/verity.py，默认模板始终从同一仓库的 templates/ 读取。
REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "templates"

# 四种流程模式。CLI 用英文短名，写进文件时同时保留中文名，便于人读。
MODE_LABELS = {
    "new-feature": "新功能",
    "bug-fix": "修缺陷",
    "acceptance": "验收",
    "release": "发布",
}

INIT_EPILOG = """三种用法：
  1. 直接建在当前目录：python3 scripts/verity.py init "登录限流" --mode bug-fix
  2. 指定父目录：      python3 scripts/verity.py init "验收批次" --mode acceptance --dir ./tasks
  3. 带项目适配层：    python3 scripts/verity.py init "导出 PDF" --mode new-feature --adapter ../docs/验收/verity-适配层.json

--mode 可选：new-feature（新功能）、bug-fix（修缺陷）、acceptance（验收）、release（发布）。
--adapter 是项目侧唯一的适配配置文件；显式传入时优先使用，找不到会直接报错。
适配层可用 paths.task_card_template / paths.ledger_template / paths.blocking_form_template
指定项目模板；未指定时使用本仓库 templates/ 下的默认模板。
"""


@dataclass(frozen=True)
class AdapterConfig:
    """项目适配层中 init 需要的字段。

    project_root 是项目根（不是适配层文件所在目录）；模板路径均已按项目根
    解析成绝对路径。未传 adapter 时 project 为“未提供”，三个模板为 None。
    """

    project: str
    project_root: Path
    ledger_template: Optional[Path] = None
    task_card_template: Optional[Path] = None
    blocking_form_template: Optional[Path] = None


def read_template(name: str) -> str:
    """读取仓库模板；模板缺失时抛出可读异常，避免生成半套文件。"""
    path = TEMPLATE_DIR / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"读不到模板 {path}：{error}") from error


def read_file_template(path: Path, label: str) -> str:
    """读取项目侧模板；与仓库模板一样，缺失时抛可读异常。"""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"读不到{label} {path}：{error}") from error


def replace_title(text: str, pattern: str, title: str, template_name: str) -> str:
    """替换模板首行标题；模板没有标题时直接报错，防止生成没有批次名的账本。"""
    replaced, count = re.subn(pattern, f"# {title}", text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"模板 {template_name} 缺少可识别的标题行：{pattern}")
    return replaced


def replace_row(
    text: str,
    field: str,
    value: str,
    template_name: str,
    *,
    required: bool = False,
) -> str:
    """替换表格中某个字段的整行内容。

    参数：
        field: 第一列字段名，按字面匹配，不走正则。
        value: 新的第二列内容；调用方保证其中不含未转义的表格竖线。
        required: 为 True 时找不到该行即报错，用于约束模板与脚本字段一致。
    """
    pattern = re.compile(r"^\|\s*" + re.escape(field) + r"\s*\|.*\|[ \t]*$", re.MULTILINE)
    replaced, count = pattern.subn(f"| {field} | {value} |", text, count=1)
    if required and count != 1:
        raise ValueError(f"模板 {template_name} 缺少字段行：{field}")
    return replaced


def replace_first_line(
    text: str, pattern: str, replacement: str, template_name: str, *, required: bool = False
) -> str:
    """按正则替换第一处整行；用于包结论等单行字段。"""
    replaced, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if required and count != 1:
        raise ValueError(f"模板 {template_name} 缺少字段行：{pattern}")
    return replaced


def run_git_head(cwd: Path) -> tuple[str, bool]:
    """在指定目录取短 HEAD；不是 git 仓库或没有提交时返回“未取到”。

    传入项目根而不是当前目录，避免从 verity 仓库调用 --adapter 时把
    verity 自己的 HEAD 写进项目任务卡。
    """
    try:
        process = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return "未取到", False
    head = process.stdout.strip()
    if process.returncode == 0 and head:
        return head, True
    return "未取到", False


def resolve_template_path(
    data: dict, key: str, project_root: Path, config_label: str
) -> Optional[Path]:
    """读取 paths.<key> 并解析为绝对路径；空字符串等价于未配置。

    模板文件不存在时立即报错，避免 init 静默退回默认模板、生成格式不一致
    的半套文件。
    """
    raw_paths = data.get("paths")
    raw_value = raw_paths.get(key) if isinstance(raw_paths, dict) else None
    if raw_value is None:
        return None
    if not isinstance(raw_value, str):
        raise ValueError(f"adapter 的 paths.{key} 必须是字符串")
    if not raw_value.strip():
        return None
    path = (project_root / raw_value.strip()).resolve()
    if not path.is_file():
        raise ValueError(f"adapter 指定的{config_label}不存在：{path}")
    return path


def read_adapter(adapter_path: Optional[str], base_dir: Optional[Path] = None) -> AdapterConfig:
    """读取项目适配层。

    参数：
        adapter_path: 显式 --adapter；为空时返回“未提供”配置。
        base_dir: 未传 adapter 时的项目根，默认当前目录。

    兼容顶层 project 字符串和 project.name 两种写法；project.root 相对
    适配层文件所在目录，缺省即该目录。模板路径相对项目根。
    """
    fallback_root = (base_dir or Path.cwd()).resolve()
    if not adapter_path:
        return AdapterConfig(project="未提供", project_root=fallback_root)

    path = Path(adapter_path).expanduser()
    if not path.is_file():
        raise ValueError(f"adapter 文件不存在：{path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"adapter 不是合法 JSON：{error}") from error
    if not isinstance(data, dict):
        raise ValueError("adapter 顶层必须是 JSON 对象")

    raw_project = data.get("project")
    if isinstance(raw_project, str):
        project = raw_project.strip()
    elif isinstance(raw_project, dict) and isinstance(raw_project.get("name"), str):
        project = raw_project["name"].strip()
    else:
        project = ""
    if not project:
        raise ValueError("adapter 缺少非空的 project 或 project.name 字段")
    if any(character in project for character in "\r\n|"):
        raise ValueError("adapter 的项目名不能包含换行或表格竖线")

    project_root = path.parent.resolve()
    raw_root = data.get("project", {}).get("root") if isinstance(data.get("project"), dict) else None
    if isinstance(raw_root, str) and raw_root.strip():
        project_root = (path.parent / raw_root.strip()).resolve()
    if not project_root.is_dir():
        raise ValueError(f"adapter 的项目根不是目录：{project_root}")

    return AdapterConfig(
        project=project,
        project_root=project_root,
        ledger_template=resolve_template_path(data, "ledger_template", project_root, "账本模板"),
        task_card_template=resolve_template_path(data, "task_card_template", project_root, "任务卡模板"),
        blocking_form_template=resolve_template_path(
            data, "blocking_form_template", project_root, "举证单模板"
        ),
    )


def mode_label(mode: str) -> str:
    """把 CLI 模式名转成“英文（中文）”形式。"""
    return f"{mode}（{MODE_LABELS[mode]}）"


def render_task_card(
    task_name: str,
    head: str,
    project: str,
    mode: str,
    today: str,
    template: Optional[Path] = None,
    batch_name: Optional[str] = None,
) -> str:
    """按任务卡模板生成文件，只填已知信息。

    T1 严格模板与仓库默认模板字段不同，这里按“字段行存在就填、关键字段
    必须存在”的方式处理：标题、版本锚点、环境、变更记录缺一即报错，
    避免模板悄悄改字段后生成不完整的任务卡。
    """
    if template is not None:
        text = read_file_template(template, "项目任务卡模板")
        template_name = template.name
    else:
        text = read_template("task-card.md")
        template_name = "task-card.md"
    text = text.replace("<YYYY-MM-DD>", today)

    title_name = batch_name if batch_name and mode == "acceptance" else task_name
    text = replace_title(text, r"^# 任务卡：.*$", f"任务卡：{title_name}", template_name)

    if batch_name:
        text = replace_row(text, "任务编号", batch_name, template_name)
        text = replace_row(text, "批次", batch_name, template_name)

    # 版本锚点：严格模板含分支/标签与 HAP 哈希，默认模板只写 commit/构建号。
    if re.search(r"^\|\s*版本锚点\s*\|.*分支/标签", text, re.MULTILINE):
        version_value = f"分支/标签：待填写；commit：{head}；构建号：待填写；HAP SHA-256：待填写"
    else:
        version_value = f"commit / 构建号：{head}"
    text = replace_row(text, "版本锚点", version_value, template_name, required=True)

    # 环境：严格模板要求设备 lane 与夹具，默认模板允许合并成一行。
    if re.search(r"^\|\s*环境\s*\|.*设备 lane", text, re.MULTILINE):
        env_value = (
            f"系统：待填写；运行时：待填写；设备 lane：待填写；夹具：待填写；"
            f"项目：{project}；模式：{mode_label(mode)}"
        )
    else:
        env_value = f"项目：{project}；模式：{mode_label(mode)}；系统、运行时、依赖版本、夹具：待填写"
    text = replace_row(text, "环境", env_value, template_name, required=True)

    # 变更记录首行固定是 v1 初版；模板换表头后这里会报错，提醒同步脚本。
    text = replace_first_line(
        text,
        r"^\|\s*v1\s*\|.*\|\s*初版\s*\|\s*—\s*\|$",
        f"| v1 | {today} | 初版 | — |",
        template_name,
        required=True,
    )
    return text


def render_ledger(
    task_name: str,
    head: str,
    project: str,
    mode: str,
    ledger_template: Optional[Path] = None,
    today: Optional[str] = None,
    batch_name: Optional[str] = None,
) -> str:
    """按 07 模板生成空账本。

    空账本只保留已知的批次信息，必须清掉模板里的示例结论和示例通过行；
    否则 init 会把“通过”预写进新批次，这是不可接受的假证据。
    """
    if ledger_template is not None:
        text = read_file_template(ledger_template, "项目账本模板")
        template_name = ledger_template.name
    else:
        text = read_template("07-acceptance.md")
        template_name = "07-acceptance.md"
    text = text.replace("<YYYY-MM-DD>", today or date.today().isoformat())

    title_name = batch_name or task_name
    text = replace_title(text, r"^# 07 验收回归清单[：·].*$", f"07 验收回归清单：{title_name}", template_name)

    # 任务卡行在两种模板里都存在；严格模板已经写好 task-card.md v1。
    text = replace_row(text, "任务卡", "task-card.md v1", template_name)

    # 被测版本：严格模板用中文冒号并带构建号字段，默认模板用斜杠写法。
    if re.search(r"^\|\s*被测版本\s*\|.*commit：", text, re.MULTILINE):
        version_value = f"commit：{head}；构建号：待填写"
    else:
        version_value = f"commit / 构建号：{head}"
    text = replace_row(text, "被测版本", version_value, template_name, required=True)

    if re.search(r"^\|\s*环境\s*\|.*设备 lane", text, re.MULTILINE):
        env_value = (
            f"项目：{project}；模式：{mode_label(mode)}；"
            "设备 lane：待填写；夹具：待填写"
        )
    else:
        env_value = f"项目：{project}；模式：{mode_label(mode)}"
    text = replace_row(text, "环境", env_value, template_name, required=True)

    if today:
        text = replace_row(text, "生成日期", today, template_name)
    # 收口时间、执行者/复核者是模板示例值，建批时必须清空，不能冒充已收口。
    text = replace_row(text, "收口时间", "待填写", template_name)
    text = replace_row(text, "执行者 / 复核者", "待指派 / 待指派", template_name)

    # 严格模板的包结论默认是示例“通过”；清成空值，交给收口人填写。
    text = replace_first_line(text, r"^- 交付结论：.*$", "- 交付结论：", template_name)
    text = replace_first_line(text, r"^- 一句话说明：.*$", "- 一句话说明：", template_name)
    text = replace_first_line(text, r"^- 证据索引：.*$", "- 证据索引：—", template_name)

    # 示例行只用于证明模板可解析；建批后必须删掉，不能留下预写的通过。
    # 只删行本身和行尾换行，保留表格后的空行，避免 Markdown 标题贴住表格。
    text = re.sub(
        r"^\|\s*TC-00-01\s*\|.*\|[ \t]*\r?\n?",
        "",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    # 模板里“下方示例行”的说明对新账本已不成立，换成建批提示。
    text = re.sub(
        r"^> 下方 `TC-00-01`.*$",
        "> 建批后由执行者填写真实证据，禁止预写通过。",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    return text


def validate_task_name(task_name: str) -> str:
    """任务名会拼进目录名，拒绝空名和路径分隔符，避免写到父目录之外。"""
    name = task_name.strip()
    if not name:
        raise ValueError("任务名不能为空")
    if name in {".", ".."} or "/" in name or "\\" in name or "\x00" in name:
        raise ValueError("任务名不能包含路径分隔符，也不能是 . 或 ..")
    return name


def init_task(args: argparse.Namespace) -> int:
    """执行 init：先检查目标目录，再完整渲染，避免重复目录被覆盖或留下半套文件。"""
    try:
        task_name = validate_task_name(args.task_name)
    except ValueError as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2

    today = date.today().isoformat()
    parent = Path(args.dir).expanduser()
    if not parent.is_absolute():
        parent = Path.cwd() / parent
    try:
        parent = parent.resolve()
    except OSError as error:
        print(f"错误：无法解析父目录 {parent}：{error}", file=sys.stderr)
        return 2
    target = parent / f"{today}-{task_name}"
    # 先拒绝重复目录：即使 adapter 或模板同时有问题，也不能覆盖已有任务。
    if target.exists():
        print(f"错误：目录已存在，拒绝覆盖：{target}", file=sys.stderr)
        return 1

    try:
        config = read_adapter(args.adapter)
        head, head_ok = run_git_head(config.project_root)
        batch_name = target.name if args.mode == "acceptance" else None
        task_card = render_task_card(
            task_name,
            head,
            config.project,
            args.mode,
            today,
            template=config.task_card_template,
            batch_name=batch_name,
        )
        ledger = render_ledger(
            task_name,
            head,
            config.project,
            args.mode,
            config.ledger_template,
            today,
            batch_name=batch_name,
        )
        # 举证单没有可自动填写的已知值，原样复制；等真正阻塞时再填。
        if config.blocking_form_template is not None:
            blocking_form = read_file_template(config.blocking_form_template, "项目举证单模板")
        else:
            blocking_form = read_template("blocking-form.md")
    except ValueError as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2

    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print(f"错误：无法创建父目录 {parent}：{error}", file=sys.stderr)
        return 2
    if not parent.is_dir():
        print(f"错误：父目录不是目录：{parent}", file=sys.stderr)
        return 2

    try:
        target.mkdir()
        (target / "evidence").mkdir()
        # 用 bytes 写出，确保换行和编码不被平台默认值改写。
        (target / "task-card.md").write_bytes(task_card.encode("utf-8"))
        (target / "07-验收回归清单.md").write_bytes(ledger.encode("utf-8"))
        (target / "blocking-form.md").write_bytes(blocking_form.encode("utf-8"))
    except OSError as error:
        print(f"错误：写入任务目录失败：{error}", file=sys.stderr)
        return 2

    print(f"已创建：{target}")
    print("  task-card.md")
    print("  07-验收回归清单.md")
    print("  blocking-form.md")
    print("  evidence/")
    print(f"日期：{today}")
    print(f"HEAD：{head}")
    print(f"模式：{mode_label(args.mode)}")
    print(f"项目：{config.project}" + ("" if config.project != "未提供" else "（未传 --adapter）"))
    if config.ledger_template is not None:
        print(f"账本模板：{config.ledger_template}")
    if config.task_card_template is not None:
        print(f"任务卡模板：{config.task_card_template}")
    if not head_ok:
        print("提示：未取到 git HEAD，版本锚点已写“未取到”；请补版本锚点后再开工。")
    checker = REPO_ROOT / "scripts" / "check_evidence.py"
    check_command = f"python3 {checker} {target / '07-验收回归清单.md'}"
    if args.adapter:
        check_command += f" --adapter {Path(args.adapter).expanduser().resolve()}"
    print(f"检查：{check_command}")
    print("提示：范围、验收项、判据和证据保持空白；空账本检查会报缺字段，这是预期行为。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI；--help 里同时给出三种用法和四种模式。"""
    parser = argparse.ArgumentParser(
        prog="verity.py",
        description="verity 技能包命令行：生成任务交付骨架，不代替验收。",
        epilog=INIT_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="子命令")

    init_parser = subparsers.add_parser(
        "init",
        help="创建任务卡、07 账本、举证单和 evidence/ 目录",
        description="按模板创建一份任务交付骨架。只填已知信息，不写证据、不判通过。",
        epilog=INIT_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    init_parser.add_argument("task_name", metavar="任务名", help="任务名，会拼进“日期-任务名”目录")
    init_parser.add_argument(
        "--mode",
        required=True,
        choices=tuple(MODE_LABELS),
        metavar="模式",
        help="new-feature / bug-fix / acceptance / release",
    )
    init_parser.add_argument(
        "--dir",
        default=".",
        metavar="父目录",
        help="任务目录的父目录，默认当前目录；不存在时会创建",
    )
    init_parser.add_argument(
        "--adapter",
        metavar="verity-适配层.json",
        help="项目唯一的适配配置文件；显式传入时优先，文件不存在直接报错",
    )
    init_parser.set_defaults(handler=init_task)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI 入口；参数错误交给 argparse 以退出码 2 报出。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
