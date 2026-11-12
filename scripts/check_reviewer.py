#!/usr/bin/env python3
"""复核会话核验：把“复核人是谁”从口头声明变成可核对的会话目录。

账本里的“独立复核”表只写了复核人名字，单看账本无法判断这个名字背后
是不是一个真实会话。本脚本把复核人和本机会话目录、复核执行记录对起来：

1. 复核人 id 在 `--sessions-root` 下存在同名会话目录；
2. 该目录的创建时间不早于批次开始时间（取任务卡的批次日期或账本“收口时间”，
   两者都没有时只提示并跳过这一条）；
3. 复核人不等于任何验收行的产出者，也不等于账本登记的批次会话；
4. `evidence/verifier-run.json` 里的 verifier 与账本复核人一致，且
   `ev09_exit`（优先）或 `exit` 为 0。

CI 或干净机器上没有 `~/.dsh/sessions` 时，会话核验不适用：脚本打印跳过并
以 0 退出，由调用方（`verity.py gate --verify-reviewer`）决定是否启用。

只使用 Python 标准库。退出码：0 = 全部核验通过或没有会话目录可核；
1 = 任一核验不成立；2 = 参数或读取错误。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_SESSIONS_ROOT = Path.home() / ".dsh" / "sessions"
DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
LEDGER_NAME = "07-验收回归清单.md"
VERIFIER_RUN = "verifier-run.json"


def normalize_header(text: str) -> str:
    """表头归一：去空白、去反引号、转小写，便于匹配中英文别名。"""
    return re.sub(r"[\s`*]", "", text.strip()).lower()


def split_table_row(line: str) -> list[str]:
    """按 Markdown 管道拆分一行；首尾空单元格丢弃。"""
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return cells


def parse_sections(text: str) -> list[tuple[str, list[str]]]:
    """把账本按二级标题切段，返回 [(标题, 行列表)]。"""
    sections: list[tuple[str, list[str]]] = []
    title = ""
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if title or lines:
                sections.append((title, lines))
            title = line[3:].strip()
            lines = []
        else:
            lines.append(line)
    if title or lines:
        sections.append((title, lines))
    return sections


def find_section(sections: list[tuple[str, list[str]]], title: str) -> Optional[list[str]]:
    """按标题精确或前缀匹配取段；找不到返回 None。"""
    for name, lines in sections:
        if name == title:
            return lines
    for name, lines in sections:
        if name.startswith(title):
            return lines
    return None


def parse_first_table(lines: list[str]) -> Optional[tuple[list[str], list[tuple[int, list[str]]]]]:
    """取段内第一张 Markdown 表格，返回 (表头, [(行号, 单元格)])。"""
    header: Optional[list[str]] = None
    rows: list[tuple[int, list[str]]] = []
    for index, line in enumerate(lines, 1):
        if not line.strip().startswith("|"):
            if header is not None:
                break
            continue
        cells = split_table_row(line)
        if header is None:
            header = cells
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells if cell):
            continue
        if cells:
            rows.append((index, cells))
    if header is None:
        return None
    return header, rows


def column_index(header: list[str], aliases: Iterable[str]) -> Optional[int]:
    """按别名找列下标；列名先归一化再比较。"""
    wanted = {normalize_header(alias) for alias in aliases}
    for index, name in enumerate(header):
        if normalize_header(name) in wanted:
            return index
    return None


def cell(row: list[str], index: Optional[int]) -> str:
    """安全取单元格；越界或没有该列时返回空串。"""
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def parse_batch_values(lines: Optional[list[str]]) -> dict[str, str]:
    """读取批次信息的两列表，返回 {字段: 内容}。"""
    if not lines:
        return {}
    table = parse_first_table(lines)
    if table is None:
        return {}
    _, rows = table
    values: dict[str, str] = {}
    for _, row in rows:
        if len(row) >= 2 and row[0]:
            values[normalize_header(row[0])] = row[1].strip()
    return values


def collect_reviewers(lines: Optional[list[str]]) -> list[str]:
    """从“独立复核”表收集去重后的复核人。"""
    if not lines:
        return []
    table = parse_first_table(lines)
    if table is None:
        return []
    header, rows = table
    index = column_index(header, ("复核人", "复核者", "reviewer"))
    if index is None:
        return []
    reviewers: list[str] = []
    for _, row in rows:
        value = cell(row, index)
        if value and value not in reviewers:
            reviewers.append(value)
    return reviewers


def collect_producers(lines: Optional[list[str]]) -> set[str]:
    """从“单项验收”表收集全部产出者，用于判断复核人是否自签。"""
    if not lines:
        return set()
    table = parse_first_table(lines)
    if table is None:
        return set()
    header, rows = table
    index = column_index(header, ("产出者", "执行者", "producer"))
    if index is None:
        return set()
    return {cell(row, index) for _, row in rows if cell(row, index)}


def parse_start_date(ledger_dir: Path, batch_values: dict[str, str]) -> Optional[date]:
    """取批次开始时间：任务卡的批次日期优先，其次账本收口时间/生成日期。

    任务卡里的“批次”字段形如 `2026-11-08-批次名`，日期就是批次开始日；
    账本“收口时间”是批次结束时写的日期。两者都只取日期部分，避免把
    “同一天内先建会话、后收口”的正常流程误判成早于批次。
    """
    card = ledger_dir / "task-card.md"
    if card.is_file():
        try:
            card_text = card.read_text(encoding="utf-8")
        except OSError:
            card_text = ""
        card_table = parse_batch_values(split_section_lines(card_text, "基本信息"))
        for key in ("批次", "生成日期", "收口时间"):
            match = DATE_RE.search(card_table.get(normalize_header(key), ""))
            if match:
                return date.fromisoformat(match.group(0))
    for key in ("收口时间", "生成日期"):
        match = DATE_RE.search(batch_values.get(normalize_header(key), ""))
        if match:
            return date.fromisoformat(match.group(0))
    return None


def split_section_lines(text: str, title: str) -> Optional[list[str]]:
    """从整份文档里取某个二级段的正文行。"""
    return find_section(parse_sections(text), title)


def session_created_at(path: Path) -> datetime:
    """取会话目录的创建时间。

    macOS 有 st_birthtime；Linux 没有时退回 ctime（创建/元数据变更时间）。
    目录刚建出来时两者都接近创建时刻，足以挡住“拿旧会话冒充本批复核”。
    """
    stat = path.stat()
    timestamp = getattr(stat, "st_birthtime", None)
    if timestamp is None:
        timestamp = stat.st_ctime
    return datetime.fromtimestamp(timestamp)


def candidate_project_dirs(sessions_root: Path, project_key: str, ledger_dir: Path) -> list[Path]:
    """列出候选项目会话目录。

    显式给了 `--project-key` 时只认目录名包含该键的项目目录；没给时用
    git 仓库根目录名（如 `verity`）自动匹配，匹配不到再用账本上级目录名。
    """
    if not sessions_root.is_dir():
        return []
    project_dirs = [
        path
        for path in sorted(sessions_root.iterdir())
        if path.is_dir() and not path.name.startswith(".")
    ]
    key = project_key.strip().lower()
    if not key:
        key = infer_project_name(ledger_dir).lower()
    if not key:
        return []
    return [path for path in project_dirs if key in path.name.lower()]


def infer_project_name(ledger_dir: Path) -> str:
    """推断项目名：优先 git 仓库根目录名，取不到时用账本所在目录名。"""
    try:
        result = subprocess.run(
            ["git", "-C", str(ledger_dir), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        result = None
    if result is not None and result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).name
    return ledger_dir.name


def find_session_dir(project_dirs: list[Path], reviewer: str) -> Optional[Path]:
    """在候选项目目录里找复核人的会话目录。

    兼容两种命名：目录名就是会话 id，或带 `session-` 前缀。复核人写成
    `session-<id>` 也能匹配。
    """
    target = reviewer.strip()
    bare = target[len("session-"):] if target.startswith("session-") else target
    for project in project_dirs:
        for child in project.iterdir():
            if not child.is_dir():
                continue
            name = child.name
            child_bare = name[len("session-"):] if name.startswith("session-") else name
            if name == target or child_bare == bare:
                return child
    return None


def load_verifier_run(ledger_dir: Path) -> tuple[Optional[dict], str]:
    """读取 evidence/verifier-run.json；缺失或格式不对时返回 (None, 原因)。"""
    path = ledger_dir / "evidence" / VERIFIER_RUN
    if not path.is_file():
        return None, f"缺少 {path.relative_to(ledger_dir).as_posix()}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return None, f"{path.name} 读取失败：{error}"
    if not isinstance(data, dict):
        return None, f"{path.name} 顶层必须是对象"
    return data, ""


def verify(
    ledger: Path,
    sessions_root: Path,
    project_key: str = "",
) -> tuple[bool, list[tuple[str, str, str]]]:
    """执行四项核验，返回 (是否全过, [(状态, 检查项, 说明)])。

    没有会话根目录时返回全过并给一条 skip 说明；调用方据此在 CI 里放行。
    """
    results: list[tuple[str, str, str]] = []
    try:
        text = ledger.read_text(encoding="utf-8")
    except OSError as error:
        return False, [("FAIL", "读取账本", str(error))]

    sections = parse_sections(text)
    batch_values = parse_batch_values(find_section(sections, "批次信息"))
    reviewers = collect_reviewers(find_section(sections, "独立复核"))
    producers = collect_producers(find_section(sections, "单项验收（证据账本）"))
    batch_producer = batch_values.get(normalize_header("执行者"), "")
    batch_session = (
        batch_values.get(normalize_header("批次会话"), "")
        or batch_values.get(normalize_header("批次会话 id"), "")
        or batch_values.get(normalize_header("批次会话id"), "")
    )

    project_dirs = candidate_project_dirs(sessions_root, project_key, ledger.parent)
    if not sessions_root.is_dir() or not project_dirs:
        detail = f"没有会话目录（{sessions_root}），如 CI 环境；复核会话核验跳过"
        return True, [("SKIP", "会话目录", detail)]

    if not reviewers:
        results.append(("FAIL", "复核人", "账本“独立复核”表没有复核人，无法核验"))
        return False, results

    passed = True
    start_date = parse_start_date(ledger.parent, batch_values)

    # 1) 每个复核人都要有同名会话目录；2) 目录创建时间不早于批次开始。
    for reviewer in reviewers:
        session_dir = find_session_dir(project_dirs, reviewer)
        if session_dir is None:
            results.append(("FAIL", "复核会话", f"复核人“{reviewer}”没有同名会话目录"))
            passed = False
            continue
        results.append(("PASS", "复核会话", f"复核人“{reviewer}”对应会话目录 {session_dir.name}"))
        if start_date is None:
            results.append(("SKIP", "会话时间", "未找到批次开始时间（任务卡批次/账本收口时间），跳过时间核对"))
            continue
        created = session_created_at(session_dir)
        if created.date() < start_date:
            results.append(
                (
                    "FAIL",
                    "会话时间",
                    f"会话目录创建于 {created:%Y-%m-%d %H:%M}，早于批次开始 {start_date}；疑似拿旧会话冒充",
                )
            )
            passed = False
        else:
            results.append(
                ("PASS", "会话时间", f"会话目录创建于 {created:%Y-%m-%d %H:%M}，不早于批次开始 {start_date}")
            )

    # 3) 复核人不能是产出者或批次会话（自己给自己签字）。
    for reviewer in reviewers:
        conflicts = []
        if reviewer in producers:
            conflicts.append("验收行产出者")
        if batch_producer and reviewer == batch_producer:
            conflicts.append("批次执行者")
        if batch_session and reviewer == batch_session:
            conflicts.append("批次会话")
        if conflicts:
            results.append(("FAIL", "复核独立性", f"复核人“{reviewer}”同时是{'、'.join(conflicts)}"))
            passed = False
        else:
            results.append(("PASS", "复核独立性", f"复核人“{reviewer}”不是产出者或批次会话"))

    # 4) verifier-run.json 的 verifier 与退出码。
    data, error = load_verifier_run(ledger.parent)
    if data is None:
        results.append(("FAIL", "复核执行记录", error))
        return False, results
    verifier = data.get("verifier", "")
    if isinstance(verifier, list):
        verifier_values = [str(item) for item in verifier]
    else:
        verifier_values = [str(verifier)] if verifier else []
    missing = [reviewer for reviewer in reviewers if reviewer not in verifier_values]
    if missing:
        results.append(
            ("FAIL", "复核执行记录", f"verifier-run.json 的 verifier 与账本复核人不一致：{'、'.join(missing)}")
        )
        passed = False
    else:
        results.append(("PASS", "复核执行记录", f"verifier 与账本复核人一致：{'、'.join(verifier_values)}"))

    exit_value = data.get("ev09_exit", data.get("exit", None))
    exit_text = str(exit_value).strip() if exit_value is not None else ""
    if exit_text not in {"0", "0.0"}:
        results.append(
            ("FAIL", "复核退出码", f"verifier-run.json 的 ev09_exit/exit 缺失或非 0：{exit_text or '缺失'}")
        )
        passed = False
    else:
        results.append(("PASS", "复核退出码", f"ev09_exit/exit={exit_text}"))
    return passed, results


def build_selftest_case(
    base: Path,
    name: str,
    reviewer: str,
    create_session: bool = True,
    verifier: Optional[str] = None,
    exit_code: int = 0,
    sessions_root: Optional[Path] = None,
) -> Path:
    """造一个临时复核夹具，返回账本路径。

    只写临时目录，不读本机真实会话；供 `--selftest` 和 `selftest.py`
    共用，保证两条自测入口造出来的场景完全一致。
    """
    case_dir = base / name
    ledger_dir = case_dir / "batch"
    (ledger_dir / "evidence").mkdir(parents=True, exist_ok=True)
    root = sessions_root if sessions_root is not None else case_dir / "sessions"
    project_dir = root / "--tmp-verity--"
    project_dir.mkdir(parents=True, exist_ok=True)
    if create_session:
        session_dir = project_dir / f"session-{reviewer}"
        session_dir.mkdir()
        (session_dir / "session.lock").write_text("", encoding="utf-8")
    ledger = ledger_dir / LEDGER_NAME
    ledger.write_text(
        "# 07 验收回归清单：复核核验自测\n\n"
        "<!-- acceptance-evidence: v1 -->\n\n"
        "## 批次信息\n\n"
        "| 字段 | 内容 |\n|---|---|\n"
        f"| 执行者 | builder |\n"
        f"| 复核者 | {reviewer} |\n"
        f"| 收口时间 | {date.today().isoformat()} |\n\n"
        "## 单项验收（证据账本）\n\n"
        "| 验收项 ID | 覆盖 AC | 用户路径 | 预期 | 证据类型 | 证据 | 证据等级 | 产出者 | 复核者 | 置信度 | 时间 | commit | 状态 |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        f"| T-01 | AC-01 | J-01 / 步骤 1 | 复核脚本退出 0 | 日志 | README.md（exit=0） | A | builder | {reviewer} | 高 | {date.today().isoformat()} | 工作区 | 通过 |\n\n"
        "## 独立复核\n\n"
        "| AC-ID | 复核结论 | 复跑命令 | 复跑证据 | 复跑退出码 | 复跑输出 | 复跑时间 | 复跑 HEAD | 复核人 | 时间 |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
        f"| AC-01 | supports | EV-01 | README.md | 0 | 结果：1/1 通过 | {date.today().isoformat()}T10:00:00 | 工作区 | {reviewer} | {date.today().isoformat()} |\n",
        encoding="utf-8",
    )
    (ledger_dir / "evidence" / VERIFIER_RUN).write_text(
        json.dumps(
            {
                "verifier": verifier if verifier is not None else reviewer,
                "session_id": reviewer,
                "time": datetime.now().isoformat(timespec="seconds"),
                "ev09_exit": exit_code,
                "exit": exit_code,
                "head": "工作区",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return ledger


def selftest() -> int:
    """临时目录造假会话，跑正负两条路径；不依赖本机真实会话。"""
    with tempfile.TemporaryDirectory(prefix="verity-reviewer-") as temporary:
        base = Path(temporary)
        sessions_root = base / "sessions"
        real_ledger = build_selftest_case(
            base, "real", "verifier-real", sessions_root=sessions_root
        )
        forged_ledger = build_selftest_case(
            base,
            "forged",
            "verifier-forged",
            create_session=False,
            sessions_root=sessions_root,
        )

        real_ok, real_results = verify(real_ledger, sessions_root, "verity")
        forged_ok, forged_results = verify(forged_ledger, sessions_root, "verity")

        total = 2
        passed = 0
        if real_ok and all(status != "FAIL" for status, _, _ in real_results):
            passed += 1
            print("[PASS] 真实会话目录：四项核验通过")
        else:
            print("[FAIL] 真实会话目录：应通过")
            for status, name, detail in real_results:
                print(f"       [{status}] {name}：{detail}")
        if not forged_ok and any("没有同名会话目录" in detail for _, _, detail in forged_results):
            passed += 1
            print("[PASS] 伪造复核人 id：没有同名会话目录，核验失败")
        else:
            print("[FAIL] 伪造复核人 id：应失败")
            for status, name, detail in forged_results:
                print(f"       [{status}] {name}：{detail}")

        # CI 场景：没有会话根目录时必须跳过并放行。
        missing_root = base / "no-sessions"
        skip_ok, skip_results = verify(real_ledger, missing_root, "verity")
        total += 1
        if skip_ok and skip_results and skip_results[0][0] == "SKIP":
            passed += 1
            print("[PASS] 无会话目录：打印跳过并按 CI 放行")
        else:
            print("[FAIL] 无会话目录：应跳过并放行")
            for status, name, detail in skip_results:
                print(f"       [{status}] {name}：{detail}")

        print(f"结果：{passed}/{total} 通过")
        return 0 if passed == total else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="核验 07 账本的复核人是否对应真实会话")
    parser.add_argument("--ledger", help="07 验收回归清单路径")
    parser.add_argument(
        "--sessions-root",
        default=str(DEFAULT_SESSIONS_ROOT),
        help=f"会话根目录，默认 {DEFAULT_SESSIONS_ROOT}",
    )
    parser.add_argument(
        "--project-key",
        default="",
        help="项目会话目录前缀（目录名包含该键即匹配）；省略时按项目名自动匹配",
    )
    parser.add_argument("--selftest", action="store_true", help="用临时目录造假会话跑正负自测")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.ledger:
        print("用法错误：需要 --ledger（或 --selftest）", file=sys.stderr)
        return 2
    ledger = Path(args.ledger).expanduser()
    if not ledger.is_file():
        print(f"用法错误：账本不存在：{ledger}", file=sys.stderr)
        return 2

    passed, results = verify(ledger, Path(args.sessions_root).expanduser(), args.project_key)
    print("verity 复核会话核验")
    print(f"账本：{ledger}")
    for status, name, detail in results:
        print(f"  [{status}] {name}：{detail}")
    fail_count = sum(1 for status, _, _ in results if status == "FAIL")
    if results and results[0][0] == "SKIP":
        print("结果：跳过（没有会话目录，按 CI 处理）")
        return 0
    print(f"结果：{'通过' if passed else '失败'}（{len(results) - fail_count}/{len(results)} 项通过）")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
