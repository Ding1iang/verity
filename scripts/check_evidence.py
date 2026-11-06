#!/usr/bin/env python3
"""verity 07 验收账本检查器。

只使用 Python 标准库，检查五类问题：

1. 账本字段：批次信息、表头列数、行内必填项是否齐全；
2. 状态枚举：通用八列只允许七种状态；项目 v1 十列只允许五种状态；
3. 证据文件：证据列引用的相对路径必须真实存在；
4. 旧结论词：出现“通过（含残余）”“基本可用”等直接判错；
5. 重复状态源：同一目录多份 07 账本、同一账本多个账本段或重复 ID。

默认按账本内容自动识别格式：带 `acceptance-evidence: v1` marker 或
“单项验收（证据账本）”段的按项目 v1 十列检查，其余按通用八列检查。
也可以用 `--format legacy|v1` 显式指定；`--adapter` 会读取项目根和
项目账本模板，决定证据路径基准与默认格式。

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
# 模板里的结论占位符不是真实结论；空账本应只报缺字段，不要额外判结论非法。
PLACEHOLDER_CONCLUSIONS = {"通过 / 未通过 / 阻塞", "通过/未通过/阻塞"}

# 项目 v1 十列账本（项目侧契约，如 ruiku-note）。verity 仓库仍以八列为
# 基础格式；带 v1 marker 的账本按项目格式检查，避免把正常的扩展列误判成
# “缺少 ## 账本”或把“带欠账”状态误判成旧结论词。
V1_MARKER = "<!-- acceptance-evidence: v1 -->"
V1_STATUSES = ("通过", "带欠账", "未交付-失败", "未交付-阻塞", "未覆盖")
V1_EVIDENCE_TYPES = ("截图", "布局树", "像素", "DB", "日志", "性能")
V1_CONFIDENCES = ("高", "中", "低")
V1_REQUIRED_COLUMNS = (
    "id",
    "user_path",
    "expected",
    "evidence_type",
    "evidence",
    "producer",
    "confidence",
    "time",
    "commit",
    "status",
)
V1_COLUMN_ALIASES = {
    "id": ("验收项id", "验收项 id", "id", "编号"),
    "user_path": ("用户路径", "用户入口"),
    "expected": ("预期", "验收预期"),
    "evidence_type": ("证据类型",),
    "evidence": ("证据",),
    "producer": ("产出者", "产出人"),
    "confidence": ("置信度",),
    "time": ("时间", "日期"),
    "commit": ("commit", "提交"),
    "status": ("状态",),
}
V1_DISPLAY_COLUMNS = {
    "id": "验收项 ID",
    "user_path": "用户路径",
    "expected": "预期",
    "evidence_type": "证据类型",
    "evidence": "证据",
    "producer": "产出者",
    "confidence": "置信度",
    "time": "时间",
    "commit": "commit",
    "status": "状态",
}
V1_PLACEHOLDER_CONCLUSIONS = {
    "通过 / 带欠账交付 / 未交付（失败 / 阻塞）",
    "通过/带欠账交付/未交付（失败/阻塞）",
    "通过 / 带欠账交付 / 未交付",
    "通过/带欠账交付/未交付",
}
V1_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*-[0-9]{2,3}$")
V1_COMMIT_RE = re.compile(r"^(?:[0-9a-fA-F]{7,40}|工作区)$")
V1_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

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


def scan_old_words(text: str, v1: bool = False) -> list[Issue]:
    """扫描旧结论词；跳过代码块和欠账表，避免把欠账描述本身误判成结论。

    v1 项目账本把“带欠账”作为正式状态和“带欠账交付”作为正式包结论，
    因此该格式下只跳过这一条旧词规则，其余旧词仍照常拦截。
    """
    issues: list[Issue] = []
    in_fence = False
    in_debt_section = False

    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if re.match(r"^##\s+", line):
            in_debt_section = bool(re.match(r"^##\s+欠账(?:表)?\s*$", line))
        if in_fence or in_debt_section:
            continue
        for pattern, label in OLD_WORD_PATTERNS:
            if v1 and label == "带欠账":
                continue
            if pattern.search(line):
                issues.append(
                    Issue(
                        "E_OLD_WORD",
                        f"出现旧结论词“{label}”，只能写规范状态/结论",
                        number,
                    )
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


def check_duplicate_sources(path: Path, text: str, sections, v1: bool = False) -> list[Issue]:
    """检查重复状态源：多份 07 文件、多个账本段/收口段、多个不同结论。"""
    issues: list[Issue] = []

    # v1 的账本段叫“单项验收（证据账本）”，和通用八列的“账本”一样只能
    # 出现一次；两种格式都按同一原则检查。
    ledger_pattern = (
        r"^##\s+(?:账本|单项验收（证据账本）)\s*$"
        if v1
        else r"^##\s+账本\s*$"
    )
    ledger_headings = [
        number for number, line in enumerate(text.splitlines(), 1) if re.match(ledger_pattern, line)
    ]
    if len(ledger_headings) > 1:
        issues.append(
            Issue("E_DUP_SOURCE", f"发现 {len(ledger_headings)} 个账本段，状态只能有一个来源", ledger_headings[1])
        )

    closing_sections = [section for section in sections if section[0] == "收口"]
    if len(closing_sections) > 1:
        issues.append(
            Issue("E_DUP_SOURCE", f"发现 {len(closing_sections)} 个“收口”段", closing_sections[1][1])
        )

    if v1:
        package_sections = [section for section in sections if section[0] == "包结论"]
        if len(package_sections) > 1:
            issues.append(
                Issue("E_DUP_SOURCE", f"发现 {len(package_sections)} 个“包结论”段", package_sections[1][1])
            )
        conclusions = set(
            re.findall(r"交付结论[:：]\s*(\S+)", text)
        )
    else:
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


def v1_text_empty(value: str) -> bool:
    """判断 v1 文本字段是否未填写；只把空白和尖括号占位符当空。

    包结论里的“—”是项目约定的“没有外部证据/索引”，不能当空值。
    """
    text = value.strip()
    return not text or (text.startswith("<") and text.endswith(">"))


def v1_value_empty(value: str) -> bool:
    """判断 v1 账本单元格是否仍未填写；未覆盖行允许用“—”占位。"""
    text = value.strip()
    return v1_text_empty(text) or text in {"—", "-", "–"}


def resolve_v1_columns(header: list[str]) -> dict[str, int]:
    """把 v1 十列表头映射到字段键；列名允许少量中文别名。"""
    mapping: dict[str, int] = {}
    used: set[int] = set()
    for key in V1_REQUIRED_COLUMNS:
        aliases = {normalize_header(alias) for alias in V1_COLUMN_ALIASES[key]}
        for index, raw in enumerate(header):
            if index in used:
                continue
            if normalize_header(raw) in aliases:
                mapping[key] = index
                used.add(index)
                break
    return mapping


def v1_conclusion_value(text: str) -> tuple[str, Optional[int]]:
    """从包结论段取出交付结论；空值或模板占位符返回空字符串。"""
    for number, line in enumerate(text.splitlines(), 1):
        match = re.search(r"交付结论[:：]\s*(.+)", line)
        if not match:
            continue
        value = match.group(1).strip()
        if v1_value_empty(value) or value in V1_PLACEHOLDER_CONCLUSIONS:
            return "", number
        return value, number
    return "", None


def expected_v1_conclusion(statuses: list[str]) -> str:
    """由账本状态推导包结论；未覆盖属于欠账，不能写“通过”。"""
    if any(status == "未交付-失败" for status in statuses):
        return "未交付（失败）"
    if any(status == "未交付-阻塞" for status in statuses):
        return "未交付（阻塞）"
    if any(status in {"带欠账", "未覆盖"} for status in statuses):
        return "带欠账交付"
    if statuses and all(status == "通过" for status in statuses):
        return "通过"
    return ""


def check_v1_ledger(
    path: Path, root: Path, text: str, sections
) -> tuple[list[Issue], dict[str, int], str]:
    """检查项目 v1 十列五节账本。

    该格式的“带欠账”是正式状态，不是旧结论词；字段、枚举和证据路径
    仍按同一套底线检查，避免项目模板绕过通用校验器。
    """
    issues: list[Issue] = []
    status_counts: Counter[str] = Counter()
    conclusion = ""
    conclusion_line: Optional[int] = None

    required_sections = ("包结论", "外部证据登记", "单项验收（证据账本）", "欠账", "阻塞举证")
    for name in required_sections:
        if find_section(sections, name) is None:
            issues.append(Issue("E_STRUCTURE", f"缺少“## {name}”段"))

    package = find_section(sections, "包结论")
    if package is not None:
        package_text = "\n".join(line for _, line in package[2])
        conclusion, conclusion_line = v1_conclusion_value(package_text)
        if not conclusion:
            issues.append(Issue("E_FIELD", "包结论的交付结论为空", conclusion_line or package[1]))
        elif not re.fullmatch(r"通过|带欠账交付|未交付(?:[（(](?:失败|阻塞)[）)])?", conclusion):
            issues.append(
                Issue(
                    "E_CONCLUSION",
                    f"交付结论“{conclusion}”只能是：通过 / 带欠账交付 / 未交付（失败 / 阻塞）",
                    conclusion_line,
                )
            )
        for label in ("一句话说明", "证据索引"):
            match = re.search(label + r"[:：]\s*(.+)", package_text)
            value = match.group(1).strip() if match else ""
            if v1_text_empty(value):
                issues.append(Issue("E_FIELD", f"包结论的“{label}”为空", package[1]))

    ledger_section = find_section(sections, "单项验收（证据账本）")
    if ledger_section is None:
        return issues, dict(status_counts), conclusion

    table = parse_first_table(ledger_section[2])
    if table is None:
        issues.append(Issue("E_STRUCTURE", "“单项验收（证据账本）”段没有 Markdown 表格", ledger_section[1]))
        return issues, dict(status_counts), conclusion

    header_line, header, rows = table
    columns = resolve_v1_columns(header)
    missing = [key for key in V1_REQUIRED_COLUMNS if key not in columns]
    if missing:
        issues.append(
            Issue(
                "E_COLUMNS",
                "v1 账本表头缺少列：" + "、".join(V1_DISPLAY_COLUMNS[key] for key in missing),
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
                    f"该行有 {len(row)} 列，表头有 {len(header)} 列；一行必须完整对应十列",
                    number,
                )
            )
            continue

        values = {key: cell(row, columns.get(key)) for key in V1_REQUIRED_COLUMNS}
        item_id = values["id"]
        status = values["status"]
        if v1_value_empty(item_id):
            issues.append(Issue("E_FIELD", "验收项 ID 为空", number))
        elif V1_ID_RE.match(item_id) is None:
            issues.append(Issue("E_ID", f"验收项 ID“{item_id}”不符合命名规则，如 MOD-01", number))
        elif item_id in seen_ids:
            issues.append(Issue("E_DUP_ID", f"ID {item_id} 与第 {seen_ids[item_id]} 行重复", number))
        else:
            seen_ids[item_id] = number

        for key in V1_REQUIRED_COLUMNS:
            # id 与 status 分别有格式/枚举检查；未覆盖行允许证据类字段填 “—”，
            # 因为该状态的定义就是“还没取证”。
            if key in {"id", "status"}:
                continue
            if status == "未覆盖" and key in {
                "evidence_type",
                "evidence",
                "confidence",
                "time",
                "commit",
            }:
                continue
            if v1_value_empty(values[key]):
                issues.append(Issue("E_FIELD", f"{V1_DISPLAY_COLUMNS[key]}为空", number))

        evidence_type = values["evidence_type"]
        if (
            status != "未覆盖"
            and evidence_type
            and not v1_value_empty(evidence_type)
            and evidence_type not in V1_EVIDENCE_TYPES
        ):
            issues.append(
                Issue(
                    "E_EVIDENCE_TYPE",
                    f"证据类型“{evidence_type}”只能是：{'/'.join(V1_EVIDENCE_TYPES)}",
                    number,
                )
            )

        confidence = values["confidence"]
        if (
            status != "未覆盖"
            and confidence
            and not v1_value_empty(confidence)
            and confidence not in V1_CONFIDENCES
        ):
            issues.append(
                Issue("E_CONFIDENCE", f"置信度“{confidence}”只能是：{'/'.join(V1_CONFIDENCES)}", number)
            )

        time_value = values["time"]
        if (
            status != "未覆盖"
            and time_value
            and not v1_value_empty(time_value)
            and not V1_DATE_RE.fullmatch(time_value)
        ):
            issues.append(Issue("E_TIME", f"时间“{time_value}”不是 YYYY-MM-DD", number))

        commit = values["commit"]
        if (
            status != "未覆盖"
            and commit
            and not v1_value_empty(commit)
            and not V1_COMMIT_RE.fullmatch(commit)
        ):
            issues.append(Issue("E_COMMIT", f"commit“{commit}”不是 7-40 位哈希或“工作区”", number))

        if v1_value_empty(status):
            issues.append(Issue("E_FIELD", "状态为空", number))
        elif status not in V1_STATUSES:
            issues.append(
                Issue(
                    "E_STATUS",
                    f"状态“{status}”不在 v1 五种枚举内（{'/'.join(V1_STATUSES)}）",
                    number,
                )
            )
        else:
            status_counts[status] += 1

        if status in {"通过", "带欠账"}:
            evidence = values["evidence"]
            if v1_value_empty(evidence) or evidence_is_empty(evidence):
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

    # 包结论必须和账本状态一致；空结论已在包结论段报过缺字段。
    if conclusion:
        expected = expected_v1_conclusion(list(status_counts.elements()))
        if expected and conclusion != expected:
            issues.append(
                Issue(
                    "E_CONCLUSION",
                    f"账本状态推出交付结论应为“{expected}”，实际写“{conclusion}”",
                    conclusion_line,
                )
            )

    return issues, dict(status_counts), conclusion


def check_ledger(
    path: Path, root: Path, forced_format: str = "auto"
) -> tuple[list[Issue], dict[str, int], str]:
    """执行全部检查，返回 (问题列表, 状态计数, 收口/包结论)。

    forced_format：auto 按 marker 判断；legacy 强制八列；v1 强制项目十列。
    """
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

    if forced_format == "v1":
        v1 = True
    elif forced_format == "legacy":
        v1 = False
    else:
        v1 = V1_MARKER in text or "单项验收（证据账本）" in text

    issues.extend(parse_batch_info(sections))
    issues.extend(scan_old_words(text, v1=v1))
    issues.extend(check_duplicate_sources(path, text, sections, v1=v1))
    if v1:
        v1_issues, v1_counts, v1_conclusion = check_v1_ledger(path, root, text, sections)
        return issues + v1_issues, v1_counts, v1_conclusion

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
            if declared_conclusion in PLACEHOLDER_CONCLUSIONS:
                # 模板占位符视为“还没写结论”，交给缺字段提示；不要在空账本上
                # 再抛一条 E_CONCLUSION，让使用者先看到可操作的补填信息。
                declared_conclusion = ""
            elif declared_conclusion not in {"通过", "未通过", "阻塞"}:
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
        if count_match and declared_conclusion:
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
        elif declared_conclusion:
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


def adapter_context(adapter_path: Path) -> tuple[Path, str]:
    """读取适配层的项目根和账本格式。

    项目根按 adapter 所在目录解析 project.root；项目模板含 v1 marker 时
    返回 v1，否则沿用通用八列。显式 --format 仍可覆盖这里的判断。
    """
    try:
        data = json.loads(adapter_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"无法读取适配层：{error}") from error
    if not isinstance(data, dict):
        raise ValueError("适配层顶层必须是对象")

    project_root = adapter_path.parent
    project = data.get("project")
    raw_root: object = None
    if isinstance(project, str):
        raw_root = None
    elif isinstance(project, dict):
        raw_root = project.get("root")
    raw_root = data.get("project_root", raw_root)
    if isinstance(raw_root, str) and raw_root.strip():
        project_root = (adapter_path.parent / raw_root.strip()).resolve()

    paths = data.get("paths") if isinstance(data.get("paths"), dict) else {}
    raw_template = paths.get("ledger_template")
    fmt = "legacy"
    if isinstance(raw_template, str) and raw_template.strip() and not (
        raw_template.strip().startswith("<") and raw_template.strip().endswith(">")
    ):
        template = (project_root / raw_template.strip()).resolve()
        if not template.is_file():
            raise ValueError(f"适配层 paths.ledger_template 指向的模板不存在：{template}")
        if V1_MARKER in template.read_text(encoding="utf-8"):
            fmt = "v1"
    return project_root, fmt


def render_summary(path: Path, counts: dict[str, int], conclusion: str) -> str:
    """输出一行人类可读的通过摘要。"""
    ordered = V1_STATUSES + tuple(status for status in STATUSES if status not in V1_STATUSES)
    parts = [f"{status} {counts[status]}" for status in ordered if counts.get(status)]
    detail = " / ".join(parts) if parts else "无验收项"
    return f"[OK] {path}：{sum(counts.values())} 行，结论={conclusion or '未写'}（{detail}）"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="检查 verity 07 验收账本的字段、状态、证据文件与单一状态源"
    )
    parser.add_argument("ledger", nargs="?", help="07 账本路径；省略时在当前目录查找唯一的 07-*.md")
    parser.add_argument("--root", help="仓库根目录，证据相对路径按它解析；默认自动向上查找 .git")
    parser.add_argument("--adapter", help="项目适配层 JSON；用于读取项目根和项目账本模板格式")
    parser.add_argument(
        "--format",
        choices=("auto", "legacy", "v1"),
        default="auto",
        help="账本格式：auto 按 marker 判断（默认），legacy 八列，v1 项目十列",
    )
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
    adapter_root: Optional[Path] = None
    adapter_format = "auto"
    if args.adapter:
        adapter_path = Path(args.adapter).expanduser()
        if not adapter_path.is_file():
            print(f"用法错误：适配层不存在或不是文件：{adapter_path}", file=sys.stderr)
            return 2
        try:
            adapter_root, adapter_format = adapter_context(adapter_path.resolve())
        except ValueError as error:
            print(f"用法错误：{error}", file=sys.stderr)
            return 2

    if args.root:
        root = Path(args.root).expanduser().resolve()
    elif adapter_root is not None:
        # 项目适配层声明了 project.root 时，证据路径必须按项目根解析，
        # 不能按 verity 仓库或 07 所在目录猜测。
        root = adapter_root
    else:
        root = resolved.parent
        for parent in (resolved.parent, *resolved.parent.parents):
            if (parent / ".git").exists():
                root = parent
                break

    forced_format = args.format if args.format != "auto" else adapter_format
    issues, counts, conclusion = check_ledger(resolved, root, forced_format)
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
        field_errors = [issue for issue in errors if issue.code == "E_FIELD"]
        # 空账本往往一次缺多个字段；只聚合一条可操作提示，避免刷屏。
        # 只有“全部错误都是缺字段”时才聚合，混合错误仍逐条给行号。
        aggregate_only = bool(field_errors) and len(field_errors) == len(errors)
        if aggregate_only:
            fields = []
            for issue in field_errors:
                if issue.message not in fields:
                    fields.append(issue.message)
            print(
                f"[FAIL] {resolved} [E_FIELD] "
                + "、".join(fields)
                + f"（共 {len(field_errors)} 处），请补齐后再检查。"
            )
        else:
            for issue in issues:
                print(issue.render(resolved))
            if field_errors:
                print(f"缺字段：{len(field_errors)} 处必填内容为空，请补齐后再检查。")
        if errors:
            print(f"检查失败：{len(errors)} 项错误，{len(warnings)} 项警告")
        else:
            print(render_summary(resolved, counts, conclusion))
            if warnings:
                print(f"检查通过，另有 {len(warnings)} 项警告")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
