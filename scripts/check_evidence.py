#!/usr/bin/env python3
"""verity 07 验收账本检查器。

只使用 Python 标准库，检查五类问题：

1. 账本字段：批次信息、表头八列、行内必填项是否齐全；
2. 状态枚举：只允许 references/acceptance.md 定义的七种状态；
3. 证据文件：证据列引用的相对路径必须真实存在；
4. 旧结论词：出现“通过（含残余）”“带欠账”“基本可用”等直接判错；
5. 重复状态源：同一目录多份 07 账本、同一账本多个“账本”段或重复 ID。

退出码：0 = 通过；1 = 发现问题；2 = 参数或读取错误。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

# 七种状态，顺序与 references/acceptance.md 第 2 节一致。
STATUSES = ("待验", "验中", "通过", "未通过", "阻塞", "不适用", "待定")
# 进入收口时必须已经有证据的状态。
EVIDENCED_STATUSES = {"通过", "未通过", "阻塞"}
# 尚未产生结论、允许证据列为空的状态。
PENDING_STATUSES = {"待验", "验中", "待定"}
# 账本允许的证据等级记法。
LEVELS = {"A", "B", "C", "B+B", "—"}

# 账本表头八列。别名用于兼容模板里的全角括号与常见简写。
COLUMN_ALIASES = {
    "id": ("id", "编号", "验收项id"),
    "item": ("验收项", "项目"),
    "criterion": ("判据", "验收判据"),
    "min_level": ("最低证据", "最低等级"),
    "level": ("证据等级", "等级"),
    "evidence": ("证据（文件或命令读数）", "证据(文件或命令读数)", "证据"),
    "status": ("状态",),
    "reviewer": ("复核", "复核人"),
}
REQUIRED_COLUMNS = tuple(COLUMN_ALIASES)

# 被禁止的旧结论词：命中即判错，不做“警告”处理。
OLD_WORD_PATTERNS = (
    (re.compile(r"通过\s*[（(]\s*含残余"), "通过（含残余）"),
    (re.compile(r"带欠账"), "带欠账"),
    (re.compile(r"基本可用"), "基本可用"),
    (re.compile(r"基本完成"), "基本完成"),
    (re.compile(r"差不多"), "差不多了"),
    (re.compile(r"应该没问题"), "应该没问题"),
    (re.compile(r"通过\s*[（(]\s*低置信"), "通过（低置信）"),
    (re.compile(r"除少数场景外都通过"), "除少数场景外都通过"),
    (re.compile(r"部分待验"), "部分待验"),
)

# 证据列里可识别的文件后缀。只匹配“像文件”的 token，命令和读数不受影响。
FILE_EXTENSIONS = (
    "md|markdown|txt|log|json|ya?ml|toml|csv|tsv|xml|html|png|jpe?g|gif|"
    "webp|svg|pdf|zip|tar|gz|py|sh|js|ts|java|ets|kt|go|rs"
)
PATH_RE = re.compile(
    r"(?<![\w./-])"
    r"((?:\.{0,2}/)?(?:[\w\u4e00-\u9fff@+.-]+/)*"
    r"[\w\u4e00-\u9fff@+.-]+\.(?:" + FILE_EXTENSIONS + r"))"
    r"(?![\w])",
    re.IGNORECASE,
)


@dataclass
class Issue:
    """一条检查结果。code 用于自测断言，line 为账本行号。"""

    code: str
    message: str
    line: Optional[int] = None
    severity: str = "error"

    def render(self, path: Path) -> str:
        location = str(path)
        if self.line is not None:
            location += f":{self.line}"
        label = "FAIL" if self.severity == "error" else "WARN"
        return f"[{label}] {location} [{self.code}] {self.message}"


def normalize_header(text: str) -> str:
    """去掉空白并把全角括号折成半角，避免表头因排版差异被误判。"""
    return (
        text.replace("（", "(")
        .replace("）", ")")
        .replace(" ", "")
        .replace("\u3000", "")
        .strip()
        .lower()
    )


def split_table_row(line: str) -> list[str]:
    """拆分 Markdown 表格行；支持单元格里用 \\| 转义的竖线。"""
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    text = text.replace(r"\|", "\x00")
    return [cell.strip().replace("\x00", "|") for cell in text.split("|")]


def is_separator_row(cells: Iterable[str]) -> bool:
    """判断表头下的分隔行，例如 |---|:---:|。"""
    items = [cell.strip() for cell in cells if cell.strip()]
    return bool(items) and all(re.fullmatch(r":?-{2,}:?", item) for item in items)


def split_sections(text: str) -> list[tuple[str, int, list[tuple[int, str]]]]:
    """按二级标题切段，返回 (标题, 标题行号, [(行号, 行内容)])。"""
    sections: list[tuple[str, int, list[tuple[int, str]]]] = []
    title: Optional[str] = None
    start = 0
    buffer: list[tuple[int, str]] = []

    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            if title is not None:
                sections.append((title, start, buffer))
            title = match.group(1).strip()
            start = number
            buffer = []
        elif title is not None:
            buffer.append((number, line))

    if title is not None:
        sections.append((title, start, buffer))
    return sections


def find_section(
    sections: list[tuple[str, int, list[tuple[int, str]]]], name: str
) -> Optional[tuple[str, int, list[tuple[int, str]]]]:
    for section in sections:
        if section[0] == name:
            return section
    return None


def parse_first_table(
    lines: list[tuple[int, str]],
) -> Optional[tuple[int, list[str], list[tuple[int, list[str]]]]]:
    """取段内第一张表，返回 (表头行号, 表头, 数据行)。"""
    header: Optional[tuple[int, list[str]]] = None
    rows: list[tuple[int, list[str]]] = []

    for number, line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            if header is not None:
                break
            continue
        cells = split_table_row(stripped)
        if header is None:
            header = (number, cells)
            continue
        if is_separator_row(cells):
            continue
        rows.append((number, cells))

    if header is None:
        return None
    return header[0], header[1], rows


def resolve_columns(header: list[str]) -> dict[str, int]:
    """把表头文字映射到八列键；同一列不会被两个键重复占用。"""
    mapping: dict[str, int] = {}
    used: set[int] = set()
    for key in REQUIRED_COLUMNS:
        aliases = {normalize_header(alias) for alias in COLUMN_ALIASES[key]}
        for index, raw in enumerate(header):
            if index in used:
                continue
            if normalize_header(raw) in aliases:
                mapping[key] = index
                used.add(index)
                break
    return mapping


def cell(row: list[str], index: Optional[int]) -> str:
    """按列下标取值；缺列时按空字符串处理，让字段检查统一报错。"""
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def evidence_is_empty(text: str) -> bool:
    """判断证据列是否只是占位符。"""
    compact = re.sub(r"\s+", "", text.strip().strip("`"))
    if compact in {
        "",
        "—",
        "-",
        "–",
        "无",
        "n/a",
        "na",
        "见上文",
        "同上",
        "待补",
        "待取证",
    }:
        return True
    return bool(re.fullmatch(r"[-—–]+", compact))


def level_rank(level: str) -> int:
    """证据等级强弱：A > B+B > B > C > 无。"""
    level = level.strip().upper().replace(" ", "")
    return {"A": 4, "B+B": 3, "B": 2, "C": 1}.get(level, 0)


def minimum_required_levels(text: str) -> set[str]:
    """从“最低证据”列解析出可接受的等级集合。"""
    compact = text.upper().replace(" ", "")
    required: set[str] = set()
    if "A" in compact:
        required.add("A")
    if "B+B" in compact:
        required.add("B+B")
    elif "B" in compact:
        required.add("B")
    return required


def extract_paths(text: str) -> list[str]:
    """从证据单元格提取候选文件路径，保留出现顺序并去重。"""
    paths: list[str] = []
    for match in PATH_RE.finditer(text):
        candidate = match.group(1).rstrip(".,;:，。；：、）)]}")
        if not candidate or candidate in paths:
            continue
        if any(char in candidate for char in "<>*?$"):
            continue
        paths.append(candidate)
    return paths


def path_exists(candidate: str, root: Path, ledger_dir: Path) -> bool:
    """证据路径允许按仓库根相对，也允许按账本所在目录相对。"""
    raw = Path(candidate)
    if raw.is_absolute():
        return raw.is_file()
    for base in (ledger_dir, root):
        if (base / raw).is_file():
            return True
    return False


def scan_old_words(text: str) -> list[Issue]:
    """扫描旧结论词；跳过代码块和欠账表，避免把欠账描述本身误判成结论。"""
    issues: list[Issue] = []
    in_fence = False
    in_debt_section = False

    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if re.match(r"^##\s+", line):
            in_debt_section = bool(re.match(r"^##\s+欠账表", line))
        if in_fence or in_debt_section:
            continue
        for pattern, label in OLD_WORD_PATTERNS:
            if pattern.search(line):
                issues.append(
                    Issue("E_OLD_WORD", f"出现旧结论词“{label}”，只能写通过/未通过/阻塞", number)
                )
    return issues


def parse_batch_info(
    sections: list[tuple[str, int, list[tuple[int, str]]]],
) -> list[Issue]:
    """批次信息是账本元数据；缺失或留空只提示，不阻断单行账本校验。"""
    issues: list[Issue] = []
    section = find_section(sections, "批次信息")
    if section is None:
        return [Issue("W_BATCH_INFO", "缺少“批次信息”段，建议补齐任务卡、版本与环境", severity="warning")]

    table = parse_first_table(section[2])
    if table is None:
        return [Issue("W_BATCH_INFO", "“批次信息”段没有表格", section[1], severity="warning")]

    _, header, rows = table
    required = ("任务卡", "被测版本", "环境", "执行者 / 复核者")
    values: dict[str, str] = {}
    for _, row in rows:
        if len(row) >= 2:
            values[normalize_header(row[0])] = row[1].strip()

    for name in required:
        value = values.get(normalize_header(name), "")
        if not value or (value.startswith("<") and value.endswith(">")):
            issues.append(
                Issue("W_BATCH_INFO", f"批次信息“{name}”未填写", section[1], severity="warning")
            )
    return issues


def check_duplicate_sources(path: Path, text: str, sections) -> list[Issue]:
    """检查重复状态源：多份 07 文件、多个账本段/收口段、多个不同结论。"""
    issues: list[Issue] = []

    ledger_headings = [
        number for number, line in enumerate(text.splitlines(), 1) if re.match(r"^##\s+账本\s*$", line)
    ]
    if len(ledger_headings) > 1:
        issues.append(
            Issue("E_DUP_SOURCE", f"发现 {len(ledger_headings)} 个“账本”段，状态只能有一个来源", ledger_headings[1])
        )

    closing_sections = [section for section in sections if section[0] == "收口"]
    if len(closing_sections) > 1:
        issues.append(
            Issue("E_DUP_SOURCE", f"发现 {len(closing_sections)} 个“收口”段", closing_sections[1][1])
        )

    conclusions = set(re.findall(r"结论[:：]\s*(通过|未通过|阻塞)", text))
    if len(conclusions) > 1:
        issues.append(
            Issue("E_DUP_SOURCE", f"账本出现多个不同结论：{'、'.join(sorted(conclusions))}")
        )

    if path.name.startswith("07-"):
        peers = [
            peer
            for peer in path.parent.glob("07-*.md")
            if peer.is_file() and peer.resolve() != path.resolve()
        ]
        if peers:
            names = "、".join(sorted(peer.name for peer in peers))
            issues.append(
                Issue("E_DUP_SOURCE", f"同一目录存在第二份 07 账本：{names}；07 是唯一状态源",)
            )
    return issues


def check_ledger(path: Path, root: Path) -> tuple[list[Issue], dict[str, int], str]:
    """执行全部检查，返回 (问题列表, 状态计数, 收口结论)。"""
    issues: list[Issue] = []
    status_counts: Counter[str] = Counter()
    declared_conclusion = ""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        return [Issue("E_READ", f"无法读取账本：{error}")], {}, ""

    sections = split_sections(text)
    if not sections:
        issues.append(Issue("E_STRUCTURE", "没有二级标题，无法定位账本"))
        return issues, {}, ""

    issues.extend(parse_batch_info(sections))
    issues.extend(scan_old_words(text))
    issues.extend(check_duplicate_sources(path, text, sections))

    ledger_section = find_section(sections, "账本")
    if ledger_section is None:
        issues.append(Issue("E_STRUCTURE", "缺少“## 账本”段"))
        return issues, {}, ""

    table = parse_first_table(ledger_section[2])
    if table is None:
        issues.append(Issue("E_STRUCTURE", "“账本”段没有 Markdown 表格", ledger_section[1]))
        return issues, {}, ""

    header_line, header, rows = table
    columns = resolve_columns(header)
    missing = [name for name in REQUIRED_COLUMNS if name not in columns]
    if missing:
        display = {
            "id": "ID",
            "item": "验收项",
            "criterion": "判据",
            "min_level": "最低证据",
            "level": "证据等级",
            "evidence": "证据（文件或命令读数）",
            "status": "状态",
            "reviewer": "复核",
        }
        issues.append(
            Issue(
                "E_COLUMNS",
                "账本表头缺少列：" + "、".join(display[name] for name in missing),
                header_line,
            )
        )

    if not rows:
        issues.append(Issue("E_NO_ROWS", "账本没有任何验收项", ledger_section[1]))

    seen_ids: dict[str, int] = {}
    ledger_dir = path.parent
    for number, row in rows:
        if len(row) != len(header):
            issues.append(
                Issue(
                    "E_COLUMNS",
                    f"该行有 {len(row)} 列，表头有 {len(header)} 列；一行必须完整对应八列",
                    number,
                )
            )
            continue

        item_id = cell(row, columns.get("id"))
        item = cell(row, columns.get("item"))
        criterion = cell(row, columns.get("criterion"))
        min_level = cell(row, columns.get("min_level"))
        level = cell(row, columns.get("level")).upper().replace(" ", "")
        evidence = cell(row, columns.get("evidence"))
        status = cell(row, columns.get("status"))
        reviewer = cell(row, columns.get("reviewer"))

        if not item_id:
            issues.append(Issue("E_FIELD", "ID 为空", number))
        elif item_id in seen_ids:
            issues.append(
                Issue("E_DUP_ID", f"ID {item_id} 与第 {seen_ids[item_id]} 行重复", number)
            )
        else:
            seen_ids[item_id] = number

        for field_name, value in (
            ("验收项", item),
            ("判据", criterion),
            ("最低证据", min_level),
        ):
            if not value:
                issues.append(Issue("E_FIELD", f"{field_name}为空", number))

        if not status:
            issues.append(Issue("E_FIELD", "状态为空", number))
        elif status not in STATUSES:
            issues.append(
                Issue(
                    "E_STATUS",
                    f"状态“{status}”不在七种枚举内（{'/'.join(STATUSES)}）",
                    number,
                )
            )
        else:
            status_counts[status] += 1

        if level and level not in LEVELS:
            issues.append(
                Issue("E_EVIDENCE_LEVEL", f"证据等级“{level}”不合法（A/B/C/B+B/—）", number)
            )

        if status in EVIDENCED_STATUSES:
            if not reviewer:
                issues.append(Issue("E_FIELD", f"{status}项缺少复核人", number))
            if evidence_is_empty(evidence):
                issues.append(
                    Issue("E_MISSING_EVIDENCE", f"{item_id or '该行'}（{status}）的证据列为空", number)
                )
            else:
                for candidate in extract_paths(evidence):
                    if not path_exists(candidate, root, ledger_dir):
                        issues.append(
                            Issue(
                                "E_EVIDENCE_PATH",
                                f"证据文件不存在：{candidate}（已查 {root} 与 {ledger_dir}）",
                                number,
                            )
                        )

        if status == "通过":
            if level in {"", "C", "—"}:
                issues.append(
                    Issue("E_EVIDENCE_LEVEL", f"{item_id or '该行'}判通过但证据等级为“{level or '空'}”", number)
                )
            elif min_level.strip() in {"", "—", "-", "–"}:
                issues.append(
                    Issue("E_FIELD", f"{item_id or '该行'}判通过但最低证据未填写有效等级", number)
                )
            else:
                required = minimum_required_levels(min_level)
                if not required:
                    issues.append(
                        Issue("W_MIN_LEVEL", f"{item_id or '该行'}最低证据无法解析：{min_level}", number, severity="warning")
                    )
                # “A / B+B”表示两种达标方式任选其一，因此取最弱的可接受等级
                # 作为门槛：A 或 B+B 都能过，单条 B 不行。
                elif level_rank(level) < min(level_rank(item) for item in required):
                    issues.append(
                        Issue(
                            "E_EVIDENCE_LEVEL",
                            f"{item_id or '该行'}最低证据要求 {min_level}，实际只有 {level}",
                            number,
                        )
                    )

    # 收口结论必须与账本状态一致，避免账本说一套、结论说另一套。
    closing = find_section(sections, "收口")
    if closing is None:
        issues.append(Issue("E_CONCLUSION", "缺少“## 收口”段"))
    else:
        closing_text = "\n".join(line for _, line in closing[2])
        match = re.search(r"结论[:：]\s*(.+)", closing_text)
        if not match:
            issues.append(Issue("E_CONCLUSION", "收口缺少“结论：”行", closing[1]))
        else:
            declared_conclusion = match.group(1).strip()
            if declared_conclusion not in {"通过", "未通过", "阻塞"}:
                issues.append(
                    Issue(
                        "E_CONCLUSION",
                        f"结论“{declared_conclusion}”只能是：通过 / 未通过 / 阻塞",
                        closing[1],
                    )
                )

        count_match = re.search(
            r"计数[:：]\s*通过\s*(\d+)\s*/\s*未通过\s*(\d+)\s*/\s*阻塞\s*(\d+)\s*/\s*不适用\s*(\d+)",
            closing_text,
        )
        if count_match:
            declared_counts = {
                "通过": int(count_match.group(1)),
                "未通过": int(count_match.group(2)),
                "阻塞": int(count_match.group(3)),
                "不适用": int(count_match.group(4)),
            }
            actual_counts = {
                "通过": status_counts.get("通过", 0),
                "未通过": status_counts.get("未通过", 0),
                "阻塞": status_counts.get("阻塞", 0),
                "不适用": status_counts.get("不适用", 0),
            }
            if declared_counts != actual_counts:
                issues.append(
                    Issue(
                        "E_COUNT",
                        f"收口计数 {declared_counts} 与账本实际 {actual_counts} 不一致",
                        closing[1],
                    )
                )
        else:
            issues.append(
                Issue("W_COUNT", "收口缺少“计数：通过 x / 未通过 y / 阻塞 z / 不适用 w”", closing[1], severity="warning")
            )

        if declared_conclusion in {"通过", "未通过", "阻塞"} and not missing:
            invalid_status = any(
                cell(row, columns.get("status")) not in STATUSES for _, row in rows
            )
            if not invalid_status:
                if status_counts.get("未通过", 0):
                    expected = "未通过"
                elif status_counts.get("阻塞", 0):
                    expected = "阻塞"
                elif any(status_counts.get(item, 0) for item in PENDING_STATUSES):
                    expected = "未通过"
                else:
                    expected = "通过"
                if expected != declared_conclusion:
                    issues.append(
                        Issue(
                            "E_CONCLUSION",
                            f"账本状态推出结论应为“{expected}”，实际写“{declared_conclusion}”",
                            closing[1],
                        )
                    )

    return issues, dict(status_counts), declared_conclusion


def render_summary(path: Path, counts: dict[str, int], conclusion: str) -> str:
    """输出一行人类可读的通过摘要。"""
    parts = [f"{status} {counts[status]}" for status in STATUSES if counts.get(status)]
    detail = " / ".join(parts) if parts else "无验收项"
    return f"[OK] {path}：{sum(counts.values())} 行，结论={conclusion or '未写'}（{detail}）"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="检查 verity 07 验收账本的字段、状态、证据文件与单一状态源"
    )
    parser.add_argument("ledger", nargs="?", help="07 账本路径；省略时在当前目录查找唯一的 07-*.md")
    parser.add_argument("--root", help="仓库根目录，证据相对路径按它解析；默认自动向上查找 .git")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果，便于 CI 消费")
    args = parser.parse_args(argv)

    if args.ledger:
        path = Path(args.ledger).expanduser()
    else:
        candidates = sorted(peer for peer in Path.cwd().glob("07-*.md") if peer.is_file())
        if len(candidates) != 1:
            print(
                "用法错误：请指定账本路径；当前目录找到 "
                f"{len(candidates)} 份 07-*.md（必须恰好一份）",
                file=sys.stderr,
            )
            return 2
        path = candidates[0]

    if not path.is_file():
        print(f"用法错误：账本不存在或不是文件：{path}", file=sys.stderr)
        return 2

    resolved = path.resolve()
    if args.root:
        root = Path(args.root).expanduser().resolve()
    else:
        root = resolved.parent
        for parent in (resolved.parent, *resolved.parent.parents):
            if (parent / ".git").exists():
                root = parent
                break

    issues, counts, conclusion = check_ledger(resolved, root)
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity != "error"]

    if args.json:
        payload = {
            "ledger": str(resolved),
            "ok": not errors,
            "conclusion": conclusion,
            "counts": counts,
            "errors": [
                {"code": issue.code, "message": issue.message, "line": issue.line}
                for issue in errors
            ],
            "warnings": [
                {"code": issue.code, "message": issue.message, "line": issue.line}
                for issue in warnings
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for issue in issues:
            print(issue.render(resolved))
        if errors:
            print(f"检查失败：{len(errors)} 项错误，{len(warnings)} 项警告")
        else:
            print(render_summary(resolved, counts, conclusion))
            if warnings:
                print(f"检查通过，另有 {len(warnings)} 项警告")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
