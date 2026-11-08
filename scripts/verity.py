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
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
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

def _checker_functions():
    """延迟导入 check_evidence.py 的解析函数，避免重复实现 Markdown 表格逻辑。"""
    import importlib.util

    path = REPO_ROOT / "scripts" / "check_evidence.py"
    spec = importlib.util.spec_from_file_location("verity_check_evidence", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载检查器：{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def split_sections(text: str):
    return _checker_functions().split_sections(text)


def find_section(sections, title: str):
    return _checker_functions().find_section(sections, title)


def find_section_prefix(sections, prefix: str):
    return _checker_functions().find_section_prefix(sections, prefix)


def parse_first_table(text: str):
    return _checker_functions().parse_first_table(text)


def normalize_header(text: str) -> str:
    return _checker_functions().normalize_header(text)


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
    journey_card_template: Optional[Path] = None


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
        journey_card_template=resolve_template_path(
            data, "journey_card_template", project_root, "旅程卡模板"
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

    # 版本锚点：模板含分支/标签时展开为四项，否则保留简写。
    if re.search(r"^\|\s*版本锚点\s*\|.*分支/标签", text, re.MULTILINE):
        version_value = f"分支/标签：待填写；commit：{head}；构建号：待填写；产物 SHA-256：待填写"
    else:
        version_value = f"commit / 构建号：{head}"
    text = replace_row(text, "版本锚点", version_value, template_name, required=True)

    # 环境：模板含平台与夹具时展开为可执行字段，否则保留合并写法。
    if re.search(r"^\|\s*环境\s*\|.*平台", text, re.MULTILINE):
        env_value = (
            f"系统：待填写；运行时：待填写；平台：待填写；夹具：待填写；"
            f"项目：{project}；模式：{mode_label(mode)}"
        )
    else:
        env_value = f"项目：{project}；模式：{mode_label(mode)}；系统、运行时、依赖版本、夹具：待填写"
    text = replace_row(text, "环境", env_value, template_name, required=True)
    text = replace_row(text, "任务卡版本", "v2", template_name)
    text = replace_row(text, "执行者", "待指派", template_name)
    text = replace_row(text, "复核者", "待指派（必须与执行者不同）", template_name)

    # 变更记录首行固定是 v2 初版；模板换表头后这里会报错，提醒同步脚本。
    text = replace_first_line(
        text,
        r"^\|\s*v2\s*\|.*\|\s*初版\s*\|\s*—\s*\|$",
        f"| v2 | {today} | 初版 | — |",
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

    # 任务卡行在两种模板里都存在；v2 模板写 schema 2。
    text = replace_row(text, "任务卡", "task-card.md v2", template_name)

    # 被测版本：严格模板用中文冒号并带构建号字段，默认模板用斜杠写法。
    if re.search(r"^\|\s*被测版本\s*\|.*commit：", text, re.MULTILINE):
        version_value = f"commit：{head}；构建号：待填写"
    else:
        version_value = f"commit / 构建号：{head}"
    text = replace_row(text, "被测版本", version_value, template_name, required=True)

    if re.search(r"^\|\s*环境\s*\|.*平台", text, re.MULTILINE):
        env_value = (
            f"项目：{project}；模式：{mode_label(mode)}；"
            "平台：待填写；夹具：待填写"
        )
    else:
        env_value = f"项目：{project}；模式：{mode_label(mode)}"
    text = replace_row(text, "环境", env_value, template_name, required=True)

    if today:
        text = replace_row(text, "生成日期", today, template_name)
    # 收口时间、执行者和复核者是模板示例值，建批时必须清空，不能冒充已收口。
    text = replace_row(text, "收口时间", "待填写", template_name)
    text = replace_row(text, "执行者", "待指派", template_name)
    text = replace_row(text, "复核者", "待指派（必须与执行者不同）", template_name)

    # 模板里的包结论和旅程结论都可能是示例“通过”；全部清空，交给收口人填写。
    text = replace_first_line(text, r"^- 交付结论：.*$", "- 交付结论：", template_name)
    text = replace_first_line(text, r"^- 一句话说明：.*$", "- 一句话说明：", template_name)
    text = replace_first_line(text, r"^- 证据索引：.*$", "- 证据索引：—", template_name)
    text = replace_first_line(text, r"^- 旅程结论：.*$", "- 旅程结论：", template_name)
    text = replace_first_line(text, r"^- 结论：.*$", "- 结论：未覆盖", template_name)

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


def render_journey_card(
    task_name: str,
    head: str,
    project: str,
    mode: str,
    today: str,
    template: Optional[Path] = None,
) -> str:
    """生成第一张旅程卡骨架；结论固定为“未覆盖”，绝不预填通过。"""
    if template is not None:
        text = read_file_template(template, "项目旅程卡模板")
        template_name = template.name
    else:
        text = read_template("journey-card.md")
        template_name = "journey-card.md"
    text = text.replace("<YYYY-MM-DD>", today)
    text = replace_title(
        text, r"^# 用户旅程卡：.*$", f"用户旅程卡：J-01 {task_name}", template_name
    )
    text = replace_row(text, "旅程 ID", "J-01", template_name, required=True)
    text = replace_row(text, "任务卡", "task-card.md v2", template_name)
    text = replace_row(text, "执行者", "待指派", template_name)
    text = replace_row(text, "复核者", "待指派（必须与执行者不同）", template_name)
    text = replace_row(
        text,
        "环境",
        f"项目：{project}；模式：{mode_label(mode)}；平台与夹具：待填写",
        template_name,
    )
    text = replace_first_line(text, r"^- 结论：.*$", "- 结论：未覆盖", template_name, required=True)
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
        journey = render_journey_card(
            task_name,
            head,
            config.project,
            args.mode,
            today,
            template=config.journey_card_template,
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
        (target / "journey-01.md").write_bytes(journey.encode("utf-8"))
        (target / "07-验收回归清单.md").write_bytes(ledger.encode("utf-8"))
        (target / "blocking-form.md").write_bytes(blocking_form.encode("utf-8"))
    except OSError as error:
        print(f"错误：写入任务目录失败：{error}", file=sys.stderr)
        return 2

    print(f"已创建：{target}")
    print("  task-card.md")
    print("  journey-01.md")
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


# ---------------------------------------------------------------------------
# 发布前后用的本地工具：doctor / gate / manifest / report / metrics / upgrade / scan
# ---------------------------------------------------------------------------

SECRET_PATTERNS = (
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS Access Key"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "GitHub token"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "API key"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "私钥"),
    (
        re.compile(r"(?i)(?:password|passwd|secret|token)\s*[:=]\s*['\"][^'\"]{6,}['\"]"),
        "明文凭据",
    ),
)
PII_PATTERNS = (
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "邮箱"),
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "手机号"),
)
DEFAULT_ANTI_BYPASS_POLICY = {
    "enabled": True,
    "protected_paths": [
        ".verity/**",
        "scripts/check_*.py",
        "tests/**",
        "**/test_*.py",
        "**/*_test.py",
    ],
    "banned_added": ["pytest.mark.skip", "@unittest.skip", "--no-verify", ".only("],
    "banned_removed": ["assert ", "expect(", "def test_", "it("],
}


def repo_version() -> str:
    """读取仓库 VERSION；缺失时返回 unknown，doctor 会把它标成失败。"""
    try:
        return (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def git_output(root: Path, *args: str) -> tuple[int, str]:
    """在指定目录跑 git，返回 (exit code, 合并后的输出)。"""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        return 127, str(error)
    return result.returncode, (result.stdout + result.stderr).strip()


def find_adapter_file(root: Path, explicit: Optional[str]) -> Optional[Path]:
    """按适配层发现顺序找配置文件；显式传入时只认该文件。"""
    if explicit:
        candidate = Path(explicit).expanduser()
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        return candidate if candidate.is_file() else None
    for name in ("verity-适配层.json", "verity-adapter.json", "adapter.json"):
        candidate = root / name
        if candidate.is_file():
            return candidate
    candidate = root / ".verity" / "adapter.json"
    return candidate if candidate.is_file() else None


def load_json_object(path: Path) -> dict:
    """读取 JSON 对象；结构不对时抛 ValueError，调用方统一转成参数错误。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"读不到 JSON：{path}（{error}）") from error
    if not isinstance(data, dict):
        raise ValueError(f"JSON 顶层必须是对象：{path}")
    return data


def find_single_ledger(root: Path) -> Optional[Path]:
    """未显式给账本时，只在根目录恰好一份 07 时自动选择，避免误判别的批次。"""
    ledgers = sorted(root.glob("07-*.md"))
    return ledgers[0] if len(ledgers) == 1 else None


def relative_to(root: Path, path: Path) -> str:
    """尽量输出仓库相对路径，供 manifest 和报告复用。"""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def collect_batch_files(batch_dir: Path) -> list[Path]:
    """收集批次目录内除 manifest.json 外的全部文件，按路径排序保证可复现。"""
    files = [
        path
        for path in batch_dir.rglob("*")
        if path.is_file() and path.name != "manifest.json" and ".git" not in path.parts
    ]
    return sorted(files, key=lambda item: item.as_posix())


def sha256_file(path: Path) -> str:
    """流式计算文件 SHA-256，避免大证据一次性读进内存。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_git_tracked(root: Path, path: Path) -> bool:
    """判断文件是否已被 git 跟踪；用于发现“证据只在本机、干净检出拿不到”。"""
    code, _ = git_output(root, "ls-files", "--error-unmatch", relative_to(root, path))
    return code == 0


def build_manifest(root: Path, ledger: Path) -> dict:
    """生成证据包清单：文件、SHA-256、字节数、是否跟踪、来源命令。"""
    batch_dir = ledger.parent
    files = []
    for path in collect_batch_files(batch_dir):
        if path.resolve() == ledger.resolve():
            source = f"python3 scripts/check_evidence.py {relative_to(root, ledger)}"
        elif path.parent.name == "evidence":
            source = "见 07 账本对应证据行的取证方式"
        else:
            source = "批次骨架/记录文件"
        files.append(
            {
                "path": relative_to(root, path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "tracked": is_git_tracked(root, path),
                "source_command": source,
            }
        )
    workspace = hashlib.sha256(
        "\n".join(f"{item['path']}:{item['sha256']}" for item in files).encode("utf-8")
    ).hexdigest()
    return {
        "schema": "verity-manifest/v1",
        "created_at": date.today().isoformat(),
        "workspace_hash": workspace,
        "files": files,
        "source_commands": [f"python3 scripts/check_evidence.py {relative_to(root, ledger)}"],
    }


def write_manifest(root: Path, ledger: Path) -> int:
    """写 manifest.json；只写批次目录，不触碰证据本身。"""
    manifest = build_manifest(root, ledger)
    target = ledger.parent / "manifest.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入：{target}")
    print(f"文件数：{len(manifest['files'])}；workspace_hash：{manifest['workspace_hash']}")
    return 0


def check_manifest(root: Path, ledger: Path, strict: bool) -> int:
    """校验清单与磁盘一致；strict 时未跟踪文件也算失败。"""
    target = ledger.parent / "manifest.json"
    if not target.is_file():
        print(f"[FAIL] 缺少证据包清单：{target}", file=sys.stderr)
        return 1
    try:
        manifest = load_json_object(target)
    except ValueError as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    issues: list[str] = []
    listed: set[str] = set()
    for item in manifest.get("files", []):
        relative = str(item.get("path", ""))
        path = root / relative
        listed.add(relative)
        if not path.is_file():
            issues.append(f"清单里的文件不存在：{relative}")
            continue
        if sha256_file(path) != item.get("sha256"):
            issues.append(f"SHA-256 对不上：{relative}")
        if path.stat().st_size != item.get("bytes"):
            issues.append(f"字节数对不上：{relative}")
        if strict and not item.get("tracked") and not is_git_tracked(root, path):
            issues.append(f"证据未被 git 跟踪，干净检出拿不到：{relative}")
    batch_dir = ledger.parent
    for path in collect_batch_files(batch_dir):
        relative = relative_to(root, path)
        if relative not in listed:
            issues.append(f"批次目录有文件未进清单：{relative}")
    if issues:
        for issue in issues:
            print(f"[FAIL] {issue}", file=sys.stderr)
        return 1
    print(f"[OK] 证据包清单一致：{len(listed)} 个文件，workspace_hash={manifest.get('workspace_hash')}")
    return 0


def clean_checkout_check(root: Path, ledger: Path) -> int:
    """用 git archive 导出 HEAD 到临时目录，再在干净副本里校验清单。"""
    code, _ = git_output(root, "rev-parse", "--verify", "HEAD")
    if code != 0:
        print("[FAIL] 不在 git 仓库或 HEAD 不存在，无法做干净检出复验", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix="verity-clean-") as temporary:
        clean_root = Path(temporary)
        archive = subprocess.run(
            ["git", "-C", str(root), "archive", "HEAD"],
            capture_output=True,
            check=False,
        )
        if archive.returncode != 0:
            print("[FAIL] git archive HEAD 失败", file=sys.stderr)
            return 1
        tar = subprocess.run(
            ["tar", "-x", "-C", str(clean_root)],
            input=archive.stdout,
            capture_output=True,
            check=False,
        )
        if tar.returncode != 0:
            print("[FAIL] 解压干净检出失败", file=sys.stderr)
            return 1
        relative = relative_to(root, ledger)
        clean_ledger = clean_root / relative
        if not clean_ledger.is_file():
            print(f"[FAIL] 干净检出里没有账本：{relative}", file=sys.stderr)
            return 1
        return check_manifest(clean_root, clean_ledger, strict=True)


def parse_scope_lock(task_text: str) -> tuple[list[str], list[str]]:
    """读取任务卡“范围锁”：返回 (做, 不做) 的路径/通配列表。"""
    sections = split_sections(task_text)
    section = find_section_prefix(sections, "范围锁")
    if section is None:
        return [], []
    table = parse_first_table(section[2])
    if table is None:
        return [], []
    _, header, rows = table
    normalized = [normalize_header(cell) for cell in header]
    type_index = next((i for i, item in enumerate(normalized) if item in {"类型", "范围"}), None)
    path_index = next((i for i, item in enumerate(normalized) if item in {"路径", "目录", "文件"}), None)
    if type_index is None or path_index is None:
        return [], []
    do_paths: list[str] = []
    dont_paths: list[str] = []
    for _, row in rows:
        kind = row[type_index].strip() if type_index < len(row) else ""
        path = row[path_index].strip().strip("`") if path_index < len(row) else ""
        if not path or path.startswith("<"):
            continue
        if "不做" in kind:
            dont_paths.append(path)
        elif "做" in kind:
            do_paths.append(path)
    return do_paths, dont_paths


def check_scope(root: Path, ledger: Path) -> list[str]:
    """范围锁校验：不做路径一旦出现在改动里就失败；做路径之外只提示。"""
    task_card = ledger.parent / "task-card.md"
    if not task_card.is_file():
        return ["找不到 task-card.md，无法检查范围锁"]
    do_paths, dont_paths = parse_scope_lock(task_card.read_text(encoding="utf-8"))
    if not do_paths and not dont_paths:
        return ["任务卡缺少“范围锁”表或表为空"]
    code, output = git_output(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if code != 0:
        return ["git status 失败，无法检查范围锁"]
    changed = [entry[3:] for entry in output.split("\0") if len(entry) > 3]
    issues: list[str] = []
    for path in changed:
        if any(fnmatch.fnmatch(path, pattern) for pattern in dont_paths):
            issues.append(f"改动落在“不做”范围：{path}")
    return issues


def read_anti_bypass_policy(root: Path, base: str) -> dict:
    """防绕过策略只从 base 读，避免本次改动顺手放宽规则。"""
    code, output = git_output(root, "show", f"{base}:.verity/policy.json")
    if code != 0:
        return dict(DEFAULT_ANTI_BYPASS_POLICY)
    try:
        policy = json.loads(output)
    except json.JSONDecodeError:
        return dict(DEFAULT_ANTI_BYPASS_POLICY)
    if not isinstance(policy, dict):
        return dict(DEFAULT_ANTI_BYPASS_POLICY)
    merged = dict(DEFAULT_ANTI_BYPASS_POLICY)
    merged.update(policy)
    return merged


def check_anti_bypass(root: Path, base: str) -> list[str]:
    """检查 base...HEAD 是否删断言、加 skip/focus 或绕过提交钩子。"""
    policy = read_anti_bypass_policy(root, base)
    if not policy.get("enabled", True):
        return []
    protected = policy.get("protected_paths", [])
    code, output = git_output(root, "diff", "--unified=0", f"{base}...HEAD", "--", *protected)
    if code != 0:
        return [f"git diff {base}...HEAD 失败：{output}"]
    issues: list[str] = []
    banned_added = policy.get("banned_added", [])
    banned_removed = policy.get("banned_removed", [])
    current_file = ""
    for line in output.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            added = line[1:]
            if any(token in added for token in banned_added):
                issues.append(f"{current_file} 新增绕过标记：{added.strip()}")
        elif line.startswith("-") and not line.startswith("---"):
            removed = line[1:]
            if any(token in removed for token in banned_removed):
                issues.append(f"{current_file} 删除了断言/测试：{removed.strip()}")
    return issues


def scan_secrets(paths: list[Path]) -> list[str]:
    """扫描令牌、私钥、明文凭据和常见个人信息；只读文本文件。"""
    findings: list[str] = []
    for path in paths:
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip", ".pdf"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            for pattern, label in SECRET_PATTERNS + PII_PATTERNS:
                match = pattern.search(line)
                if not match:
                    continue
                # 邮箱规则排除 git 远程地址和文档示例域名，避免把 ssh://git@host
                # 与 @example.invalid 这类占位地址误报成个人数据。
                token = match.group(0)
                if label == "邮箱" and (
                    token.startswith("git@")
                    or token.endswith(".invalid")
                    or token.endswith("example.com")
                ):
                    continue
                findings.append(f"{path}:{line_number} 命中{label}")
    return findings


def cmd_doctor(args: argparse.Namespace) -> int:
    """环境预检：版本、模板、脚本、git、适配层、证据命令和取证通道正负对照。"""
    root = Path(args.root).expanduser().resolve()
    checks: list[tuple[str, bool, str]] = []
    checks.append(("VERSION", repo_version() != "unknown", repo_version()))
    templates = ["07-acceptance.md", "task-card.md", "journey-card.md", "blocking-form.md"]
    missing_templates = [name for name in templates if not (TEMPLATE_DIR / name).is_file()]
    checks.append(("模板", not missing_templates, "齐全" if not missing_templates else "缺 " + "、".join(missing_templates)))
    scripts = ["check_evidence.py", "check_coverage.py", "package.py"]
    missing_scripts = [name for name in scripts if not (REPO_ROOT / "scripts" / name).is_file()]
    checks.append(("脚本", not missing_scripts, "齐全" if not missing_scripts else "缺 " + "、".join(missing_scripts)))
    code, head = git_output(root, "rev-parse", "--short", "HEAD")
    checks.append(("git", code == 0, head if code == 0 else "不是 git 仓库"))
    adapter_path = find_adapter_file(root, args.adapter)
    checks.append(("适配层", True, str(adapter_path) if adapter_path else "未找到（可选，不影响通用规则）"))
    if adapter_path is not None:
        try:
            adapter = load_json_object(adapter_path)
        except ValueError as error:
            checks.append(("适配层 JSON", False, str(error)))
            adapter = {}
        else:
            checks.append(("适配层 JSON", adapter.get("schema") == "verity-adapter/v1", str(adapter.get("schema", "缺少 schema"))))
            commands = adapter.get("commands", {})
            total_commands = sum(len(commands.get(key, [])) for key in ("static", "contract", "device", "build"))
            checks.append(("证据命令", total_commands > 0, f"{total_commands} 条"))
            channels = adapter.get("evidence_channels", [])
            if not channels:
                checks.append(("取证通道正负对照", True, "未配置（跳过）"))
            for index, channel in enumerate(channels, 1):
                positive = str(channel.get("command", "")).strip()
                negative = str(channel.get("negative_command", "")).strip()
                if not positive or not negative:
                    checks.append((f"通道 {index}", False, "缺少 command 或 negative_command"))
                    continue
                positive_code, _ = subprocess.run(
                    positive, shell=True, cwd=root, capture_output=True, check=False
                ).returncode, ""
                negative_code, _ = subprocess.run(
                    negative, shell=True, cwd=root, capture_output=True, check=False
                ).returncode, ""
                checks.append(
                    (
                        f"通道 {index}",
                        positive_code == 0 and negative_code != 0,
                        f"正对照 exit={positive_code}，负对照 exit={negative_code}",
                    )
                )
    failed = 0
    print(f"verity doctor（版本 {repo_version()}）")
    for name, ok, detail in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}：{detail}")
        failed += 0 if ok else 1
    print(f"结果：{len(checks) - failed}/{len(checks)} 项通过")
    return 0 if failed == 0 else 1


def cmd_gate(args: argparse.Namespace) -> int:
    """本地完成线闸门：账本、覆盖、清单、范围、防绕过、发布脱敏一次跑完。"""
    if args.selftest:
        return gate_selftest()
    root = Path(args.root).expanduser().resolve()
    ledger = Path(args.ledger).expanduser().resolve() if args.ledger else find_single_ledger(root)
    if ledger is None or not ledger.is_file():
        print("[FAIL] 找不到唯一 07 账本；请显式传 --ledger", file=sys.stderr)
        return 1
    failures = 0
    steps: list[tuple[str, bool, str]] = []

    command = [sys.executable, str(REPO_ROOT / "scripts" / "check_evidence.py"), str(ledger), "--root", str(root)]
    if args.adapter:
        command.extend(["--adapter", str(Path(args.adapter).expanduser())])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    steps.append(("证据账本", result.returncode == 0, (result.stdout + result.stderr).strip().splitlines()[-1] if (result.stdout + result.stderr).strip() else ""))
    failures += 0 if result.returncode == 0 else 1

    coverage = Path(args.coverage).expanduser().resolve() if args.coverage else None
    if coverage is None and args.adapter:
        try:
            adapter = load_json_object(Path(args.adapter).expanduser())
            configured = adapter.get("paths", {}).get("coverage_master", "")
            if configured:
                coverage = Path(args.adapter).expanduser().parent / configured
        except ValueError:
            coverage = None
    if coverage is not None and coverage.is_file():
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "check_coverage.py"), str(coverage), "--root", str(root)],
            capture_output=True,
            text=True,
            check=False,
        )
        steps.append(("覆盖总表", result.returncode == 0, (result.stdout + result.stderr).strip().splitlines()[-1] if (result.stdout + result.stderr).strip() else ""))
        failures += 0 if result.returncode == 0 else 1
    else:
        steps.append(("覆盖总表", True, "未配置（跳过）"))

    manifest = ledger.parent / "manifest.json"
    if manifest.is_file():
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "manifest", "--root", str(root), "--ledger", str(ledger), "--check", "--strict"],
            capture_output=True,
            text=True,
            check=False,
        )
        steps.append(("证据包清单", result.returncode == 0, (result.stdout + result.stderr).strip().splitlines()[-1] if (result.stdout + result.stderr).strip() else ""))
        failures += 0 if result.returncode == 0 else 1
    else:
        steps.append(("证据包清单", True, "未生成（跳过）"))

    scope_issues = check_scope(root, ledger)
    steps.append(("范围锁", not scope_issues, "；".join(scope_issues) if scope_issues else "改动都在“做”范围"))
    failures += 0 if not scope_issues else 1

    if args.team:
        bypass = check_anti_bypass(root, args.base)
        steps.append(("防绕过", not bypass, "；".join(bypass) if bypass else "未发现删断言/skip/focus/--no-verify"))
        failures += 0 if not bypass else 1
    else:
        steps.append(("防绕过", True, "未启用（仅团队/高风险仓库用 --team）"))

    if args.release:
        findings = scan_secrets([path for path in ledger.parent.rglob("*") if path.is_file()])
        steps.append(("安全脱敏", not findings, "；".join(findings[:5]) if findings else "未命中令牌/凭据/个人信息"))
        failures += 0 if not findings else 1

    print("verity gate")
    for name, ok, detail in steps:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}：{detail}")
    print(f"结果：{'通过' if failures == 0 else '失败'}（{len(steps) - failures}/{len(steps)}）")
    return 0 if failures == 0 else 1


def gate_selftest() -> int:
    """防绕过的正负对照：临时 git 仓库里先做一次干净提交，再做删断言提交。"""
    with tempfile.TemporaryDirectory(prefix="verity-gate-") as temporary:
        root = Path(temporary)
        subprocess.run(["git", "init", "-q"], cwd=root, check=False)
        subprocess.run(["git", "config", "user.email", "gate@example.invalid"], cwd=root, check=False)
        subprocess.run(["git", "config", "user.name", "gate"], cwd=root, check=False)
        (root / ".verity").mkdir()
        (root / ".verity" / "policy.json").write_text(
            json.dumps(DEFAULT_ANTI_BYPASS_POLICY, ensure_ascii=False), encoding="utf-8"
        )
        tests = root / "tests"
        tests.mkdir()
        (tests / "test_case.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=root, check=False)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=False)
        subprocess.run(["git", "tag", "base"], cwd=root, check=False)
        (tests / "test_case.py").write_text("def test_ok():\n    return True\n", encoding="utf-8")
        (tests / "test_skip.py").write_text("import pytest\n\npytest.mark.skip\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=root, check=False)
        subprocess.run(["git", "commit", "-qm", "bypass"], cwd=root, check=False)
        issues = check_anti_bypass(root, "base")
        negative_ok = any("删除了断言" in issue for issue in issues) and any("绕过标记" in issue for issue in issues)
        subprocess.run(["git", "reset", "--hard", "-q", "base"], cwd=root, check=False)
        clean_issues = check_anti_bypass(root, "base")
        positive_ok = not clean_issues
        print(f"[{'PASS' if negative_ok else 'FAIL'}] 负对照：删断言/加 skip 被识别")
        print(f"[{'PASS' if positive_ok else 'FAIL'}] 正对照：干净提交不误报")
        return 0 if negative_ok and positive_ok else 1


def ledger_summary(ledger: Path) -> dict:
    """从 07 账本抓包结论、旅程结论和状态计数，供 report/metrics 使用。"""
    text = ledger.read_text(encoding="utf-8")
    sections = split_sections(text)
    package = find_section(sections, "包结论")
    conclusion = ""
    one_line = ""
    if package is not None:
        package_text = "\n".join(line for _, line in package[2])
        match = re.search(r"^- 交付结论：\s*(.*)$", package_text, re.MULTILINE)
        conclusion = match.group(1).strip() if match else ""
        match = re.search(r"^- 一句话说明：\s*(.*)$", package_text, re.MULTILINE)
        one_line = match.group(1).strip() if match else ""
    journey = find_section(sections, "用户旅程")
    journey_conclusion = ""
    if journey is not None:
        journey_text = "\n".join(line for _, line in journey[2])
        match = re.search(r"^- 结论：\s*(通过|未通过|阻塞|未覆盖)", journey_text, re.MULTILINE)
        journey_conclusion = match.group(1) if match else ""
    table = find_section(sections, "单项验收（证据账本）")
    counts: dict[str, int] = {}
    levels: dict[str, int] = {}
    if table is not None:
        parsed = parse_first_table(table[2])
        if parsed is not None:
            _, header, rows = parsed
            normalized = [normalize_header(cell) for cell in header]
            status_index = next((i for i, item in enumerate(normalized) if item in {"状态", "status"}), None)
            level_index = next((i for i, item in enumerate(normalized) if item in {"证据等级", "等级", "level"}), None)
            for _, row in rows:
                if status_index is not None and status_index < len(row):
                    status = row[status_index].strip() or "空"
                    counts[status] = counts.get(status, 0) + 1
                if level_index is not None and level_index < len(row):
                    level = row[level_index].strip() or "空"
                    levels[level] = levels.get(level, 0) + 1
    return {
        "conclusion": conclusion,
        "one_line": one_line,
        "journey": journey_conclusion,
        "counts": counts,
        "levels": levels,
        "rows": sum(counts.values()),
    }


def cmd_report(args: argparse.Namespace) -> int:
    """两层汇报 / PR 摘要 / 交接摘要；第一层只用三行以内的人话。"""
    ledger = Path(args.ledger).expanduser().resolve()
    if not ledger.is_file():
        print(f"[FAIL] 账本不存在：{ledger}", file=sys.stderr)
        return 1
    summary = ledger_summary(ledger)
    if args.kind == "two-layer":
        conclusion = summary["conclusion"] or "未写结论"
        journey = summary["journey"] or "未写旅程结论"
        print(f"这批的交付结论是“{conclusion}”，旅程卡结论是“{journey}”。")
        print(f"账本共 {summary['rows']} 条验收项，证据等级分布：{summary['levels'] or '空'}。")
        print(f"一句话说明：{summary['one_line'] or '未填写'}")
        print()
        print(f"账本：{ledger}")
        print(f"状态计数：{summary['counts']}")
        print("下一步：结论不是“通过”时，先补证据或写阻塞举证单，不能改口径。")
        return 0
    if args.kind == "pr":
        print("## 交付摘要")
        print()
        print(f"- 结论：{summary['conclusion'] or '未写'}")
        print(f"- 旅程：{summary['journey'] or '未写'}")
        print(f"- 验收项：{summary['rows']} 条；状态：{summary['counts']}")
        print()
        print("## 风险与回滚")
        print()
        print("- 风险：见 07「发布风险」段；未填时按高风险处理。")
        print("- 回滚：见 07「发布风险」段的回滚点与验证读数。")
        return 0
    print("# 交接摘要")
    print()
    print(f"- 当前结论：{summary['conclusion'] or '未写'}")
    print(f"- 用户旅程：{summary['journey'] or '未写'}")
    print(f"- 账本：{ledger}")
    print(f"- 状态计数：{summary['counts']}")
    print("- 未完成项：看「欠账」「阻塞举证」两段；为空才可交接。")
    print("- 下一步：按 07「完成审计」缺哪条补哪条。")
    return 0


def cmd_metrics(args: argparse.Namespace) -> int:
    """统计批次数、行数、结论和证据等级，输出 JSON 与一行摘要。"""
    root = Path(args.dir).expanduser().resolve()
    ledgers = sorted(root.rglob("07-*.md"))
    total_rows = 0
    conclusions: dict[str, int] = {}
    levels: dict[str, int] = {}
    for ledger in ledgers:
        summary = ledger_summary(ledger)
        total_rows += summary["rows"]
        conclusion = summary["conclusion"] or "空"
        conclusions[conclusion] = conclusions.get(conclusion, 0) + 1
        for level, count in summary["levels"].items():
            levels[level] = levels.get(level, 0) + count
    payload = {
        "ledgers": len(ledgers),
        "rows": total_rows,
        "conclusions": conclusions,
        "levels": levels,
        "a_ratio": round(levels.get("A", 0) / total_rows, 4) if total_rows else 0,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"摘要：{payload['ledgers']} 份账本，{total_rows} 行，A 级占比 {payload['a_ratio']:.0%}")
    return 0


def cmd_upgrade(args: argparse.Namespace) -> int:
    """把旧十列账本迁到 schema 2 十三列，并补缺失段；迁移后仍需人工补证据。"""
    ledger = Path(args.ledger).expanduser().resolve()
    if not ledger.is_file():
        print(f"[FAIL] 账本不存在：{ledger}", file=sys.stderr)
        return 1
    text = ledger.read_text(encoding="utf-8")
    if "覆盖 AC" in text and "## 证据身份" in text and "## 独立复核" in text:
        print("已经是 schema 2，无需迁移。")
        return 0
    lines = text.splitlines()
    out: list[str] = []
    old_header = "| 验收项 ID | 用户路径 | 预期 | 证据类型 | 证据 | 产出者 | 置信度 | 时间 | commit | 状态 |"
    new_header = "| 验收项 ID | 覆盖 AC | 用户路径 | 预期 | 证据类型 | 证据 | 证据等级 | 产出者 | 复核者 | 置信度 | 时间 | commit | 状态 |"
    new_separator = "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    for line in lines:
        if line.strip() == old_header:
            out.extend([new_header, new_separator])
            continue
        if line.startswith("| ") and line.endswith(" |") and "---" not in line:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) == 10 and cells[0] not in {"验收项 ID"}:
                cells = cells[:1] + ["—"] + cells[1:5] + ["B", cells[5], "待指派"] + cells[6:]
                out.append("| " + " | ".join(cells) + " |")
                continue
        out.append(line)
    migrated = "\n".join(out)
    missing = ""
    for title, body in (
        ("用户旅程", "## 用户旅程\n\n- 旅程卡：`journey-01.md`\n- 覆盖路径：<待补>\n- 结论：未覆盖\n- 未解决的不变量：<待补>\n"),
        ("证据身份", "## 证据身份\n\n| 证据 | SHA-256 | 字节数 | 构建号 | 环境 | 取证时间 | workspace_hash | 结构化读数 |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n"),
        ("完成审计", "## 完成审计\n\n| 完成定义 | 对应 AC | 实际场景 / 命令 | 最终构建 | 读数 | 证据 |\n| --- | --- | --- | --- | --- | --- |\n"),
        ("独立复核", "## 独立复核\n\n| AC-ID | 复核结论 | 复跑命令 | 复跑证据 | 复核人 | 时间 |\n| --- | --- | --- | --- | --- | --- |\n"),
    ):
        if f"## {title}" not in migrated:
            missing += "\n" + body
    if missing:
        migrated = migrated.replace("\n## 欠账", missing + "\n## 欠账", 1)
    migrated = migrated.replace("> 模板版本：v1", "> 模板版本：v2（schema 2）")
    backup = ledger.with_suffix(ledger.suffix + ".bak")
    backup.write_text(text, encoding="utf-8")
    ledger.write_text(migrated, encoding="utf-8")
    print(f"已迁移：{ledger}")
    print(f"备份：{backup}")
    print("提示：covers、证据身份、完成审计和复核需要人工补全；迁移不等于通过。")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    """安全/脱敏扫描：默认只告警；发布模式（--release）命中即失败。"""
    root = Path(args.root).expanduser().resolve()
    targets = [Path(item).expanduser().resolve() for item in args.paths] if args.paths else [root]
    files: list[Path] = []
    for target in targets:
        if target.is_file():
            files.append(target)
        elif target.is_dir():
            files.extend(
                path for path in target.rglob("*")
                if path.is_file() and ".git" not in path.parts and "dist" not in path.parts
            )
    findings = scan_secrets(files)
    print(f"verity scan：{len(files)} 个文件，命中 {len(findings)} 项")
    for finding in findings[:50]:
        print(f"  [{'FAIL' if args.release else 'WARN'}] {finding}")
    if args.release and findings:
        return 1
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

    doctor_parser = subparsers.add_parser("doctor", help="环境预检与取证通道正负对照")
    doctor_parser.add_argument("--root", default=".", help="项目根目录，默认当前目录")
    doctor_parser.add_argument("--adapter", help="适配层 JSON；不传时按发现顺序查找")
    doctor_parser.set_defaults(handler=cmd_doctor)

    gate_parser = subparsers.add_parser("gate", help="本地完成线闸门（账本/覆盖/清单/范围/防绕过/脱敏）")
    gate_parser.add_argument("--root", default=".", help="项目根目录，默认当前目录")
    gate_parser.add_argument("--ledger", help="07 账本路径；默认根目录唯一 07")
    gate_parser.add_argument("--adapter", help="适配层 JSON")
    gate_parser.add_argument("--coverage", help="覆盖总表路径")
    gate_parser.add_argument("--team", action="store_true", help="启用防绕过（仅团队/高风险仓库）")
    gate_parser.add_argument("--base", default="HEAD~1", help="防绕过策略与 diff 的基线，默认 HEAD~1")
    gate_parser.add_argument("--release", action="store_true", help="发布模式：额外跑安全/脱敏扫描")
    gate_parser.add_argument("--selftest", action="store_true", help="跑防绕过正负对照后退出")
    gate_parser.set_defaults(handler=cmd_gate)

    manifest_parser = subparsers.add_parser("manifest", help="生成或校验证据包 manifest.json")
    manifest_parser.add_argument("--root", default=".", help="项目根目录")
    manifest_parser.add_argument("--ledger", required=True, help="07 账本路径")
    mode = manifest_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="写 manifest.json")
    mode.add_argument("--check", action="store_true", help="校验 manifest.json")
    mode.add_argument("--clean-check", action="store_true", help="在 git archive 干净检出里校验")
    manifest_parser.add_argument("--strict", action="store_true", help="未跟踪文件也判失败")
    manifest_parser.set_defaults(handler=cmd_manifest)

    report_parser = subparsers.add_parser("report", help="生成两层汇报/PR 摘要/交接摘要")
    report_parser.add_argument("--ledger", required=True, help="07 账本路径")
    report_parser.add_argument("--kind", choices=("two-layer", "pr", "handoff"), default="two-layer")
    report_parser.set_defaults(handler=cmd_report)

    metrics_parser = subparsers.add_parser("metrics", help="统计账本行数、结论和证据等级")
    metrics_parser.add_argument("--dir", default=".", help="扫描目录，默认当前目录")
    metrics_parser.set_defaults(handler=cmd_metrics)

    upgrade_parser = subparsers.add_parser("upgrade", help="把旧十列账本迁到 schema 2 十三列")
    upgrade_parser.add_argument("ledger", metavar="账本", help="要迁移的 07 账本")
    upgrade_parser.set_defaults(handler=cmd_upgrade)

    scan_parser = subparsers.add_parser("scan", help="扫描令牌、私钥、明文凭据和个人信息")
    scan_parser.add_argument("--root", default=".", help="扫描根目录")
    scan_parser.add_argument("--paths", nargs="*", help="只扫描指定文件/目录")
    scan_parser.add_argument("--release", action="store_true", help="发布模式：命中即失败")
    scan_parser.set_defaults(handler=cmd_scan)
    return parser


def cmd_manifest(args: argparse.Namespace) -> int:
    """manifest 子命令分发：写、校验或干净检出复验。"""
    root = Path(args.root).expanduser().resolve()
    ledger = Path(args.ledger).expanduser().resolve()
    if args.write:
        return write_manifest(root, ledger)
    if args.clean_check:
        return clean_checkout_check(root, ledger)
    return check_manifest(root, ledger, args.strict)


def main(argv: Optional[list[str]] = None) -> int:
    """CLI 入口；参数错误交给 argparse 以退出码 2 报出。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
