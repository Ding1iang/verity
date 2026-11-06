#!/usr/bin/env python3
"""verity 覆盖总表检查器。

只使用 Python 标准库，检查六类问题：

1. 结构：总表必须含批次、模块、入口、必测状态、07 路径、覆盖状态、不适用理由、负责人；
2. 模块：适配层里每个 in_use 模块在总表至少有一行；
3. 07 路径：写“已覆盖”的 07 必须真实存在，且文件名符合 07-*.md；
4. 唯一认领：同一份 07 不能被两行重复认领；
5. 不适用：必须写理由和负责人；
6. 数量：07 根目录下的 07 文件数必须与总表认领的 07 数一致，且没有未登记的 07。

覆盖状态只有三种：已覆盖 / 缺失 / 不适用。本表不写通过/失败结论；
通过/失败只从对应 07 账本读。

退出码：0 = 通过；1 = 发现问题；2 = 参数或读取错误。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

COVERAGE_STATUSES = ("已覆盖", "缺失", "不适用")
REQUIRED_COLUMNS = ("batch", "module", "entry", "must_status", "ledger", "coverage", "owner")
COLUMN_ALIASES = {
    "batch": ("批次", "批次名"),
    "module": ("模块", "模块名"),
    "module_id": ("模块id", "模块标识", "id"),
    "entry": ("入口", "用户入口", "用户路径"),
    "must_status": ("必测状态", "必测"),
    "ledger": ("07路径", "07路径(相对项目根)", "账本路径", "07"),
    "coverage": ("覆盖状态", "覆盖"),
    "na_reason": ("不适用理由", "不适用原因", "n/a理由", "na理由"),
    "owner": ("负责人", "责任人"),
}
DISPLAY_COLUMNS = {
    "batch": "批次",
    "module": "模块",
    "entry": "入口",
    "must_status": "必测状态",
    "ledger": "07 路径",
    "coverage": "覆盖状态",
    "na_reason": "不适用理由",
    "owner": "负责人",
}
EMPTY_VALUES = {"", "—", "-", "–", "无", "n/a", "na", "待填", "tbd", "todo", "/"}
LEDGER_NAME_RE = re.compile(r"^07[-_].+\.md$", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r"^<[^<>]*>$")


@dataclass
class Issue:
    """一条检查结果。code 用于自测断言，line 为总表行号。"""

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


def normalize_key(text: str) -> str:
    """模块 ID/名称匹配时忽略大小写和首尾空白。"""
    return text.strip().lower()


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
    """把表头文字映射到列键；同一列不会被两个键重复占用。"""
    mapping: dict[str, int] = {}
    used: set[int] = set()
    keys = tuple(COLUMN_ALIASES)
    for key in keys:
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


def is_empty(value: str) -> bool:
    """判断必填单元格是否为空或仍是占位符。"""
    text = value.strip().strip("`").strip()
    if text in EMPTY_VALUES:
        return True
    return bool(PLACEHOLDER_RE.fullmatch(text))


def resolve_path(raw: str, project_root: Path) -> Path:
    """把总表里的路径按项目根解析；绝对路径原样使用。"""
    text = raw.strip().strip("`").strip()
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate.resolve()


def is_ledger_name(path: Path) -> bool:
    """07 账本文件名必须是 07-*.md 或 07_*.md。"""
    return bool(LEDGER_NAME_RE.fullmatch(path.name))


def find_git_root(start: Path) -> Optional[Path]:
    """从 start 向上找第一个含 .git 的目录。"""
    for parent in (start, *start.parents):
        if (parent / ".git").exists():
            return parent
    return None


def discover_adapter(start: Path) -> Optional[Path]:
    """从覆盖总表所在目录向上找常见的适配层位置。"""
    names = (Path(".verity") / "adapter.json", Path("verity-adapter.json"), Path("adapter.json"))
    for parent in (start, *start.parents):
        for name in names:
            candidate = parent / name
            if candidate.is_file():
                return candidate
    return None


def load_adapter(path: Path) -> tuple[Optional[dict], list[Issue]]:
    """读取适配层 JSON；解析失败返回问题而不是抛异常。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        return None, [Issue("E_ADAPTER_READ", f"无法读取适配层：{error}")]
    except json.JSONDecodeError as error:
        return None, [Issue("E_ADAPTER_JSON", f"适配层不是合法 JSON：{error}")]
    if not isinstance(data, dict):
        return None, [Issue("E_ADAPTER_JSON", "适配层顶层必须是 JSON 对象")]
    issues: list[Issue] = []
    if data.get("schema") != "verity-adapter/v1":
        issues.append(
            Issue(
                "W_ADAPTER_SCHEMA",
                "适配层 schema 不是 verity-adapter/v1，可能来自旧版本",
                severity="warning",
            )
        )
    return data, issues


def adapter_project_root(adapter_path: Path, data: dict) -> Path:
    """适配层 project.root 相对适配层文件所在目录。"""
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    raw_root = str(project.get("root", ".")).strip() or "."
    candidate = Path(raw_root).expanduser()
    if not candidate.is_absolute():
        candidate = adapter_path.parent / candidate
    return candidate.resolve()


def adapter_modules(data: dict) -> tuple[list[dict], list[Issue]]:
    """读取适配层 modules；只接受 id/name/in_use 结构。"""
    issues: list[Issue] = []
    raw_modules = data.get("modules")
    if raw_modules is None:
        return [], [Issue("W_NO_MODULES", "适配层没有 modules，无法检查在用模块是否都有行", severity="warning")]
    if not isinstance(raw_modules, list):
        return [], [Issue("E_ADAPTER_MODULES", "适配层 modules 必须是数组")]

    modules: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_modules, 1):
        if not isinstance(item, dict):
            issues.append(Issue("E_ADAPTER_MODULES", f"modules 第 {index} 项不是对象"))
            continue
        module_id = str(item.get("id", "")).strip()
        name = str(item.get("name", "")).strip()
        if not module_id and not name:
            issues.append(Issue("E_ADAPTER_MODULES", f"modules 第 {index} 项缺少 id 和 name"))
            continue
        in_use = item.get("in_use", True)
        if not isinstance(in_use, bool):
            issues.append(Issue("E_ADAPTER_MODULES", f"modules 第 {index} 项 in_use 必须是 true/false"))
            continue
        key = module_id or name
        if key in seen:
            issues.append(Issue("E_ADAPTER_MODULES", f"modules 里模块 {key} 重复"))
            continue
        seen.add(key)
        modules.append({"id": module_id or name, "name": name or module_id, "in_use": in_use})
    return modules, issues


def resolve_ledger_root(
    adapter_data: Optional[dict], project_root: Path, cli_value: Optional[str]
) -> Optional[Path]:
    """确定 07 根目录：命令行 > 适配层 > 不检查。"""
    if cli_value:
        candidate = Path(cli_value).expanduser()
        if not candidate.is_absolute():
            candidate = project_root / candidate
        return candidate.resolve()
    if adapter_data:
        paths = adapter_data.get("paths") if isinstance(adapter_data.get("paths"), dict) else {}
        raw_root = str(paths.get("ledger_root", "")).strip()
        if raw_root and not is_empty(raw_root):
            candidate = Path(raw_root).expanduser()
            if not candidate.is_absolute():
                candidate = project_root / candidate
            return candidate.resolve()
    return None


def check_coverage(
    coverage_path: Path,
    project_root: Path,
    adapter_data: Optional[dict],
    ledger_root: Optional[Path],
) -> tuple[list[Issue], dict[str, int], int]:
    """执行全部检查，返回 (问题列表, 覆盖状态计数, 07 文件数)。"""
    issues: list[Issue] = []
    status_counts: Counter[str] = Counter()

    try:
        text = coverage_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return [Issue("E_READ", f"无法读取覆盖总表：{error}")], {}, 0

    sections = split_sections(text)
    section = find_section(sections, "总表") or find_section(sections, "覆盖总表")
    if section is None:
        return [Issue("E_STRUCTURE", "缺少“## 总表”段")], {}, 0

    table = parse_first_table(section[2])
    if table is None:
        return [Issue("E_STRUCTURE", "“总表”段没有 Markdown 表格", section[1])], {}, 0

    header_line, header, rows = table
    columns = resolve_columns(header)
    missing_columns = [key for key in REQUIRED_COLUMNS if key not in columns]
    if missing_columns:
        issues.append(
            Issue(
                "E_COLUMNS",
                "总表表头缺少列：" + "、".join(DISPLAY_COLUMNS[key] for key in missing_columns),
                header_line,
            )
        )
    if not rows:
        issues.append(Issue("E_NO_ROWS", "总表没有任何数据行", section[1]))

    # 适配层模块清单：id/name 都能匹配，优先用模块 ID 列。
    modules: list[dict] = []
    module_issues: list[Issue] = []
    if adapter_data is not None:
        modules, module_issues = adapter_modules(adapter_data)
        issues.extend(module_issues)
    else:
        issues.append(Issue("W_NO_ADAPTER", "未找到适配层，跳过“每个在用模块必须有行”检查", severity="warning"))

    declared_ids = {normalize_key(module["id"]): module for module in modules}
    declared_names = {normalize_key(module["name"]): module for module in modules if module["name"]}
    matched_modules: set[str] = set()

    claimed: dict[Path, int] = {}

    for number, row in rows:
        if len(row) != len(header):
            issues.append(
                Issue(
                    "E_COLUMNS",
                    f"该行有 {len(row)} 列，表头有 {len(header)} 列；一行必须完整对应表头",
                    number,
                )
            )
            continue

        batch = cell(row, columns.get("batch"))
        module_name = cell(row, columns.get("module"))
        module_id = cell(row, columns.get("module_id"))
        entry = cell(row, columns.get("entry"))
        must_status = cell(row, columns.get("must_status"))
        ledger_raw = cell(row, columns.get("ledger"))
        coverage_status = cell(row, columns.get("coverage"))
        na_reason = cell(row, columns.get("na_reason"))
        owner = cell(row, columns.get("owner"))

        for field_name, value in (
            ("批次", batch),
            ("入口", entry),
            ("必测状态", must_status),
        ):
            if is_empty(value):
                issues.append(Issue("E_FIELD", f"{field_name}为空", number))
        if is_empty(module_name) and is_empty(module_id):
            issues.append(Issue("E_FIELD", "模块和模块 ID 不能同时为空", number))
        if is_empty(owner):
            issues.append(
                Issue(
                    "E_NA_OWNER" if coverage_status == "不适用" else "E_FIELD",
                    "负责人为空",
                    number,
                )
            )

        # 模块匹配：模块 ID 优先，其次模块名。
        matched_module: Optional[dict] = None
        if module_id:
            matched_module = declared_ids.get(normalize_key(module_id))
        if matched_module is None and module_name:
            matched_module = declared_names.get(normalize_key(module_name))
        if matched_module is None and module_name:
            matched_module = declared_ids.get(normalize_key(module_name))
        if matched_module is not None:
            matched_modules.add(matched_module["id"])
        elif adapter_data is not None:
            issues.append(
                Issue(
                    "W_MODULE_UNKNOWN",
                    f"模块“{module_id or module_name}”不在适配层 modules 里，可能是笔误或清单过期",
                    number,
                    severity="warning",
                )
            )

        if not coverage_status:
            issues.append(Issue("E_FIELD", "覆盖状态为空", number))
        elif coverage_status not in COVERAGE_STATUSES:
            issues.append(
                Issue(
                    "E_COVERAGE_STATUS",
                    f"覆盖状态“{coverage_status}”不合法（只能写 已覆盖 / 缺失 / 不适用）",
                    number,
                )
            )
        else:
            status_counts[coverage_status] += 1

        if coverage_status == "已覆盖":
            if is_empty(ledger_raw):
                issues.append(Issue("E_LEDGER_MISSING", "已覆盖行必须写 07 路径", number))
            else:
                ledger_path = resolve_path(ledger_raw, project_root)
                if not ledger_path.is_file():
                    issues.append(
                        Issue(
                            "E_LEDGER_MISSING",
                            f"已覆盖行指向的 07 不存在：{ledger_raw}（解析为 {ledger_path}）",
                            number,
                        )
                    )
                else:
                    if not is_ledger_name(ledger_path):
                        issues.append(
                            Issue(
                                "E_LEDGER_NAME",
                                f"07 文件名不符合 07-*.md：{ledger_path.name}",
                                number,
                            )
                        )
                    if ledger_root is not None:
                        try:
                            ledger_path.relative_to(ledger_root)
                        except ValueError:
                            issues.append(
                                Issue(
                                    "E_LEDGER_OUTSIDE",
                                    f"07 不在配置的 07 根目录下：{ledger_raw}",
                                    number,
                                )
                            )
                    if ledger_path in claimed:
                        issues.append(
                            Issue(
                                "E_LEDGER_DUP",
                                f"07 被重复认领：{ledger_raw}（第 {claimed[ledger_path]} 行已认领）",
                                number,
                            )
                        )
                    else:
                        claimed[ledger_path] = number

        elif coverage_status == "缺失":
            if is_empty(ledger_raw):
                issues.append(Issue("E_LEDGER_MISSING", "缺失行也要写计划中的 07 路径", number))
            else:
                ledger_path = resolve_path(ledger_raw, project_root)
                if ledger_path.exists():
                    issues.append(
                        Issue(
                            "E_STATUS_CONFLICT",
                            f"07 已存在但覆盖状态仍写“缺失”：{ledger_raw}；应改为“已覆盖”",
                            number,
                        )
                    )

        elif coverage_status == "不适用":
            if is_empty(na_reason):
                issues.append(Issue("E_NA_REASON", "不适用行必须写理由", number))
            # 负责人在上面的通用字段检查里已经按 E_NA_OWNER 报过，不重复报。

    # 在用模块必须至少有一行。
    for module in modules:
        if module["in_use"] and module["id"] not in matched_modules:
            issues.append(
                Issue(
                    "E_MODULE_MISSING",
                    f"在用模块“{module['id']} / {module['name']}”在总表没有行",
                )
            )

    # 07 根目录与总表对账：数量必须一致，且不能有未登记 07。
    found_ledgers: list[Path] = []
    if ledger_root is not None:
        if ledger_root.exists() and ledger_root.is_dir():
            found_ledgers = sorted(
                {
                    path.resolve()
                    for path in ledger_root.rglob("07*")
                    if path.is_file() and is_ledger_name(path)
                },
                key=lambda item: item.as_posix(),
            )
        else:
            if claimed:
                issues.append(
                    Issue("E_LEDGER_ROOT", f"07 根目录不存在：{ledger_root}")
                )
            else:
                issues.append(
                    Issue(
                        "W_NO_LEDGER_DIR",
                        f"07 根目录不存在，暂按 0 份 07 处理：{ledger_root}",
                        severity="warning",
                    )
                )

        found_set = set(found_ledgers)
        claimed_set = set(claimed)
        if len(found_set) != len(claimed_set):
            issues.append(
                Issue(
                    "E_LEDGER_COUNT",
                    f"07 根目录有 {len(found_set)} 份 07，总表认领 {len(claimed_set)} 份；数量对不上",
                )
            )
        for ledger_path in found_ledgers:
            if ledger_path not in claimed_set:
                issues.append(
                    Issue(
                        "E_LEDGER_UNCLAIMED",
                        f"07 未在总表登记：{ledger_path}",
                    )
                )

    return issues, dict(status_counts), len(found_ledgers)


def render_summary(path: Path, counts: dict[str, int], ledger_count: int) -> str:
    """输出一行人类可读的通过摘要。"""
    total = sum(counts.values())
    detail = " / ".join(
        f"{status} {counts.get(status, 0)}" for status in COVERAGE_STATUSES
    )
    return f"[OK] {path}：{total} 行（{detail}），07 文件 {ledger_count} 份"


def run_check(args: argparse.Namespace) -> int:
    coverage_path = Path(args.coverage).expanduser()
    if not coverage_path.is_file():
        print(f"用法错误：覆盖总表不存在或不是文件：{coverage_path}", file=sys.stderr)
        return 2
    coverage_path = coverage_path.resolve()

    adapter_path: Optional[Path] = None
    if args.adapter:
        adapter_path = Path(args.adapter).expanduser()
        if not adapter_path.is_file():
            print(f"用法错误：适配层不存在或不是文件：{adapter_path}", file=sys.stderr)
            return 2
        adapter_path = adapter_path.resolve()
    else:
        discovered = discover_adapter(coverage_path.parent)
        if discovered is not None:
            adapter_path = discovered.resolve()

    adapter_data: Optional[dict] = None
    issues: list[Issue] = []
    if adapter_path is not None:
        adapter_data, adapter_issues = load_adapter(adapter_path)
        issues.extend(adapter_issues)
        if adapter_data is None:
            for issue in issues:
                print(issue.render(adapter_path))
            return 1

    if args.project_root:
        project_root = Path(args.project_root).expanduser().resolve()
    elif adapter_data is not None and adapter_path is not None:
        project_root = adapter_project_root(adapter_path, adapter_data)
    else:
        project_root = find_git_root(coverage_path.parent) or coverage_path.parent

    if not project_root.is_dir():
        print(f"用法错误：项目根不存在或不是目录：{project_root}", file=sys.stderr)
        return 2

    ledger_root = resolve_ledger_root(adapter_data, project_root, args.ledger_root)
    if ledger_root is None:
        issues.append(
            Issue(
                "W_NO_LEDGER_ROOT",
                "没有配置 07 根目录（适配层 paths.ledger_root 或 --ledger-root），跳过数量对账",
                severity="warning",
            )
        )

    check_issues, counts, ledger_count = check_coverage(
        coverage_path, project_root, adapter_data, ledger_root
    )
    issues.extend(check_issues)
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity != "error"]

    if args.json:
        payload = {
            "coverage": str(coverage_path),
            "ok": not errors,
            "rows": sum(counts.values()),
            "counts": counts,
            "ledger_files": ledger_count,
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
            print(issue.render(coverage_path))
        if errors:
            print(f"检查失败：{len(errors)} 项错误，{len(warnings)} 项警告")
        else:
            print(render_summary(coverage_path, counts, ledger_count))
            if warnings:
                print(f"检查通过，另有 {len(warnings)} 项警告")

    return 1 if errors else 0


# ---------------------------------------------------------------------------
# 自测：一个 8 行好样本 + 五个坏样本（缺模块、假路径、重复 07、不适用无理由、
# 07 数量对不上）。自测只写临时目录，不碰仓库文件。
# ---------------------------------------------------------------------------

BASE_MODULES = [
    {"id": f"m{index:02d}", "name": f"模块{index}", "in_use": True}
    for index in range(1, 9)
]


def base_rows() -> list[list[str]]:
    """8 行样本：m01-m06 已覆盖，m07 缺失，m08 不适用。"""
    rows: list[list[str]] = []
    for index in range(1, 9):
        module_id = f"m{index:02d}"
        module_name = f"模块{index}"
        entry = f"入口{index}"
        if index <= 6:
            rows.append(
                [
                    "B1",
                    module_name,
                    module_id,
                    entry,
                    "必测",
                    f"ledgers/07-{module_id}.md",
                    "已覆盖",
                    "—",
                    "负责人甲",
                ]
            )
        elif index == 7:
            rows.append(
                [
                    "B1",
                    module_name,
                    module_id,
                    entry,
                    "必测",
                    f"ledgers/07-{module_id}.md",
                    "缺失",
                    "—",
                    "负责人甲",
                ]
            )
        else:
            rows.append(
                [
                    "B1",
                    module_name,
                    module_id,
                    entry,
                    "免测",
                    "—",
                    "不适用",
                    "本批明确不测，已由项目负责人批准",
                    "负责人乙",
                ]
            )
    return rows


def render_master(rows: list[list[str]]) -> str:
    """把行拼成一份完整的覆盖总表。"""
    body = "\n".join("| " + " | ".join(row) + " |" for row in rows)
    return (
        "# 覆盖总表：自测项目\n\n"
        "## 总表\n\n"
        "| 批次 | 模块 | 模块 ID | 入口 | 必测状态 | 07 路径 | 覆盖状态 | 不适用理由 | 负责人 |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        + body
        + "\n"
    )


@dataclass
class SelftestCase:
    """一个自测样本；mutate 直接改 8 行样本。"""

    slug: str
    label: str
    mutate: Callable[[list[list[str]], Path], None]
    expected_codes: tuple[str, ...] = ()
    add_orphan: bool = False

    @property
    def should_pass(self) -> bool:
        return not self.expected_codes


def build_selftest_project(root: Path, case: SelftestCase) -> Path:
    """在独立临时目录里造项目、适配层、6 份 07 和覆盖总表。"""
    project = root / case.slug
    (project / ".verity").mkdir(parents=True)
    (project / "ledgers").mkdir()

    adapter = {
        "schema": "verity-adapter/v1",
        "project": {"name": "selftest", "root": ".."},
        "paths": {"ledger_root": "ledgers", "evidence_root": "evidence"},
        "modules": BASE_MODULES,
    }
    (project / ".verity" / "adapter.json").write_text(
        json.dumps(adapter, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for index in range(1, 7):
        (project / "ledgers" / f"07-m{index:02d}.md").write_text(
            f"# 07 验收回归清单：m{index:02d}\n", encoding="utf-8"
        )

    rows = base_rows()
    case.mutate(rows, project)
    if case.add_orphan:
        (project / "ledgers" / "07-orphan.md").write_text(
            "# 07 验收回归清单：未登记\n", encoding="utf-8"
        )
    (project / "coverage-master.md").write_text(render_master(rows), encoding="utf-8")
    return project


def run_selftest() -> int:
    """逐个好/坏样本调用自身；坏样本必须命中预期错误码。"""
    checker = Path(__file__).resolve()
    cases = [
        SelftestCase("good", "好样本", lambda rows, project: None),
        SelftestCase(
            "bad-missing-module",
            "坏样本·缺模块",
            lambda rows, project: rows.pop(6),
            expected_codes=("E_MODULE_MISSING",),
        ),
        SelftestCase(
            "bad-fake-path",
            "坏样本·假路径",
            lambda rows, project: rows[1].__setitem__(5, "ledgers/07-not-there.md"),
            expected_codes=("E_LEDGER_MISSING",),
        ),
        SelftestCase(
            "bad-duplicate-ledger",
            "坏样本·重复 07",
            lambda rows, project: rows[1].__setitem__(5, rows[0][5]),
            expected_codes=("E_LEDGER_DUP",),
        ),
        SelftestCase(
            "bad-na-no-reason",
            "坏样本·不适用无理由",
            lambda rows, project: rows[7].__setitem__(7, ""),
            expected_codes=("E_NA_REASON",),
        ),
        SelftestCase(
            "bad-ledger-count",
            "坏样本·07 数量对不上",
            lambda rows, project: None,
            expected_codes=("E_LEDGER_COUNT",),
            add_orphan=True,
        ),
    ]

    print("verity 覆盖总表自测")
    print(f"检查器：{checker}")
    passed = 0
    failures: list[str] = []

    with tempfile.TemporaryDirectory(prefix="verity-coverage-selftest-") as temp:
        root = Path(temp)
        for case in cases:
            project = build_selftest_project(root, case)
            master = project / "coverage-master.md"
            adapter = project / ".verity" / "adapter.json"
            process = subprocess.run(
                [
                    sys.executable,
                    str(checker),
                    str(master),
                    "--adapter",
                    str(adapter),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            output = process.stdout + process.stderr

            if case.should_pass:
                ok = process.returncode == 0 and "[OK]" in process.stdout
                detail = f"退出 {process.returncode}，{'未给出通过摘要' if not ok else '8 行全部通过'}"
            else:
                hit = all(code in output for code in case.expected_codes)
                ok = process.returncode != 0 and hit
                detail = (
                    f"退出 {process.returncode}，"
                    f"{'命中 ' if hit else '未命中 '}{'/'.join(case.expected_codes)}"
                )

            if ok:
                passed += 1
                print(f"[PASS] {case.label}：{detail}")
            else:
                print(f"[FAIL] {case.label}：{detail}")
                failures.append(case.label)
                for line in output.splitlines():
                    print(f"       {line}")

    print(f"结果：{passed}/{len(cases)} 通过")
    if failures:
        print("未通过的样本：" + "、".join(failures), file=sys.stderr)
        return 1
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="检查 verity 覆盖总表：模块齐全、07 真实、唯一认领、不适用有理由、数量对账"
    )
    parser.add_argument("coverage", nargs="?", help="覆盖总表路径")
    parser.add_argument("--adapter", help="项目适配层 JSON；省略时从总表所在目录向上自动查找")
    parser.add_argument("--project-root", help="项目根目录；省略时取适配层 project.root 或 git 根")
    parser.add_argument("--ledger-root", help="07 根目录；省略时取适配层 paths.ledger_root")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果，便于 CI 消费")
    parser.add_argument("--selftest", action="store_true", help="运行内置好/坏样本自测")
    args = parser.parse_args(argv)

    if args.selftest:
        return run_selftest()
    if not args.coverage:
        parser.print_usage(sys.stderr)
        print("用法错误：请指定覆盖总表路径，或使用 --selftest", file=sys.stderr)
        return 2
    return run_check(args)


if __name__ == "__main__":
    sys.exit(main())
