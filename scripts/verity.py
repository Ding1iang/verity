#!/usr/bin/env python3
"""verity 命令行：生成任务交付骨架。

当前提供 `init` 子命令：按仓库里的三份模板创建任务卡、07 验收账本、
阻塞举证单和空的 evidence/ 目录。它只搭骨架，不写证据、不判断通过，
也不替执行者填写范围、验收项、判据和证据。

只使用 Python 标准库。退出码：0 = 创建成功；1 = 目标目录已存在等业务
拒绝；2 = 参数、模板或文件读写错误。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Optional

# 脚本位于 <仓库根>/scripts/verity.py，模板始终从同一仓库的 templates/ 读取。
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
  3. 带项目适配文件：  python3 scripts/verity.py init "导出 PDF" --mode new-feature --adapter ./adapter.json

--mode 可选：new-feature（新功能）、bug-fix（修缺陷）、acceptance（验收）、release（发布）。
--adapter 是项目侧 JSON 文件，至少包含 project 或 project.name；适配文件不放进本仓库。
若 adapter 的 paths.ledger_template 指向项目账本模板，则生成项目模板；否则用本仓库八列模板。
"""


def read_template(name: str) -> str:
    """读取仓库模板；模板缺失时抛出可读异常，避免生成半套文件。"""
    path = TEMPLATE_DIR / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"读不到模板 {path}：{error}") from error


def replace_once(text: str, old: str, new: str, template_name: str) -> str:
    """只替换模板中确定存在的占位串，防止模板改动后静默生成错文件。"""
    if old not in text:
        raise ValueError(f"模板 {template_name} 缺少占位符：{old}")
    return text.replace(old, new, 1)


def run_git_head() -> tuple[str, bool]:
    """取当前目录的短 HEAD；不是 git 仓库或没有提交时返回“未取到”。"""
    try:
        process = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path.cwd(),
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


def read_adapter(adapter_path: Optional[str]) -> tuple[str, Optional[Path]]:
    """读取项目名与可选的账本模板路径。

    project 兼容顶层字符串和 project.name；paths.ledger_template 是项目侧
    可选的十列账本模板，路径相对 project.root（缺省为 adapter 所在目录）。
    模板不存在时直接报错，避免 init 生成半套或退回错误格式。
    """
    if not adapter_path:
        return "未提供", None
    path = Path(adapter_path).expanduser()
    if not path.is_file():
        raise ValueError(f"adapter 文件不存在：{path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"adapter 不是合法 JSON：{error}") from error
    if not isinstance(data, dict):
        raise ValueError("adapter 顶层必须是 JSON 对象")

    # 任务约定允许顶层 project 直接写字符串；t10 的适配层模板用
    # project.name。两种都接受，避免项目侧为了 init 再维护第二份名字。
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

    # 项目根默认是 adapter 所在目录；适配层模板通常写 "../.." 指到项目根。
    project_root = path.parent
    raw_root = data.get("project", {}).get("root") if isinstance(data.get("project"), dict) else None
    if isinstance(raw_root, str) and raw_root.strip():
        project_root = (path.parent / raw_root.strip()).resolve()

    ledger_template: Optional[Path] = None
    raw_paths = data.get("paths")
    raw_template = raw_paths.get("ledger_template") if isinstance(raw_paths, dict) else None
    if raw_template is not None:
        if not isinstance(raw_template, str) or not raw_template.strip():
            raise ValueError("adapter 的 paths.ledger_template 必须是非空字符串")
        ledger_template = (project_root / raw_template.strip()).resolve()
        if not ledger_template.is_file():
            raise ValueError(f"adapter 指定的账本模板不存在：{ledger_template}")
    return project, ledger_template


def read_project(adapter_path: Optional[str]) -> tuple[str, bool]:
    """兼容旧调用：只返回项目名和是否传了 adapter。"""
    project, _ = read_adapter(adapter_path)
    return project, bool(adapter_path)


def mode_label(mode: str) -> str:
    """把 CLI 模式名转成“英文（中文）”形式。"""
    return f"{mode}（{MODE_LABELS[mode]}）"


def render_task_card(
    task_name: str, head: str, project: str, mode: str, today: str
) -> str:
    """按任务卡模板生成文件，只填任务名、HEAD、项目/模式和创建日期。"""
    text = read_template("task-card.md")
    text = replace_once(
        text,
        "# 任务卡：<任务编号> <标题>",
        f"# 任务卡：{task_name}",
        "task-card.md",
    )
    text = replace_once(
        text,
        "| 版本锚点 | commit / 构建号： |",
        f"| 版本锚点 | commit / 构建号：{head} |",
        "task-card.md",
    )
    text = replace_once(
        text,
        "| 环境 | 系统、运行时、依赖版本、夹具： |",
        f"| 环境 | 项目：{project}；模式：{mode_label(mode)}；系统、运行时、依赖版本、夹具：待填写 |",
        "task-card.md",
    )
    text = replace_once(
        text,
        "| v1 | | 初版 | — |",
        f"| v1 | {today} | 初版 | — |",
        "task-card.md",
    )
    return text


def read_file_template(path: Path, label: str) -> str:
    """读取项目侧模板；与仓库模板一样，缺失时抛可读异常。"""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"读不到{label} {path}：{error}") from error


def render_ledger(
    task_name: str,
    head: str,
    project: str,
    mode: str,
    ledger_template: Optional[Path] = None,
    today: Optional[str] = None,
) -> str:
    """按 07 模板生成空账本；项目 v1 模板与仓库八列模板都只填已知信息。"""
    if ledger_template is not None:
        text = read_file_template(ledger_template, "项目账本模板")
        text = replace_once(
            text,
            "# 07 验收回归清单 · <批次目录>",
            f"# 07 验收回归清单：{task_name}",
            ledger_template.name,
        )
        if today:
            text = replace_once(
                text,
                "| 生成日期 | <date> |",
                f"| 生成日期 | {today} |",
                ledger_template.name,
            )
        text = replace_once(
            text,
            "| 被测版本 | commit / 构建号：<commit> |",
            f"| 被测版本 | commit / 构建号：{head} |",
            ledger_template.name,
        )
        text = replace_once(
            text,
            "| 环境 | 项目：<项目>；模式：<模式> |",
            f"| 环境 | 项目：{project}；模式：{mode_label(mode)} |",
            ledger_template.name,
        )
        return text

    text = read_template("07-acceptance.md")
    text = replace_once(
        text,
        "# 07 验收回归清单：<批次或版本>",
        f"# 07 验收回归清单：{task_name}",
        "07-acceptance.md",
    )
    text = replace_once(
        text,
        "| 任务卡 | <路径> v<n> |",
        "| 任务卡 | task-card.md v1 |",
        "07-acceptance.md",
    )
    text = replace_once(
        text,
        "| 被测版本 | commit / 构建号： |",
        f"| 被测版本 | commit / 构建号：{head} |",
        "07-acceptance.md",
    )
    text = replace_once(
        text,
        "| 环境 | |",
        f"| 环境 | 项目：{project}；模式：{mode_label(mode)} |",
        "07-acceptance.md",
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
        project, ledger_template = read_adapter(args.adapter)
        head, head_ok = run_git_head()
        task_card = render_task_card(task_name, head, project, args.mode, today)
        ledger = render_ledger(task_name, head, project, args.mode, ledger_template, today)
        # 举证单没有可自动填写的已知值，原样复制；等真正阻塞时再填。
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
    print(f"项目：{project}" + ("" if project != "未提供" else "（未传 --adapter）"))
    if ledger_template is not None:
        print(f"账本模板：{ledger_template}")
    if not head_ok:
        print("提示：未取到 git HEAD，版本锚点已写“未取到”；请补版本锚点后再开工。")
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
        description="按仓库模板创建一份任务交付骨架。只填已知信息，不写证据、不判通过。",
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
        metavar="adapter.json",
        help="项目适配文件；读取 project 或 project.name 字段，文件不复制进本仓库",
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
