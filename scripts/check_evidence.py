#!/usr/bin/env python3
"""verity 07 验收账本检查器。

只使用 Python 标准库，检查五类问题：

1. 账本字段：批次信息、表头列数、行内必填项是否齐全；
2. 状态枚举：通用八列只允许七种状态；项目 v1 十三列按适配层枚举校验；
3. 证据文件：证据列引用的相对路径必须真实存在；
4. 旧结论词：出现“通过（含残余）”“基本可用”等直接判错；
5. 重复状态源：同一目录多份 07 账本、同一账本多个账本段或重复 ID；
6. 版本锚点：v1 的 commit 必须是真实 git 对象，并等于 HEAD 或为其祖先；
7. 证据时效：证据日期或文件 mtime 早于 commit 日期时按旧证据拒绝；
8. 证据自述：v1 的截图必须有可读图片，且不能自述“只跑主路径”“门禁全绿没跑探针”“设备未验”却写通过。

默认按账本内容自动识别格式：带 `acceptance-evidence: v1` marker 或
“单项验收（证据账本）”段的按 v1 schema 2 十三列检查，其余按通用八列检查。
也可以用 `--format legacy|v1` 显式指定；`--adapter` 会读取项目根、
项目账本模板和账本枚举，决定证据路径基准、默认格式与允许取值。
`--compat-debt` 仅为读取历史账本放行“带欠账/带欠账交付”；新账本默认拒绝，`--strict` 仍可用于叠加卡口。

退出码：0 = 通过；1 = 发现问题；2 = 参数或读取错误。
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import struct
import tarfile
import tempfile
import zlib
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

# 七种状态，顺序与 references/acceptance.md 第 2 节一致。
STATUSES = ("待验", "验中", "通过", "未通过", "阻塞", "不适用", "待定")
# 进入收口时必须已经有证据的状态。
EVIDENCED_STATUSES = {"通过", "未通过", "阻塞"}
# 模板里的结论占位符不是真实结论；空账本应只报缺字段，不要额外判结论非法。
PLACEHOLDER_CONCLUSIONS = {"通过 / 未通过 / 阻塞", "通过/未通过/阻塞"}

# v1 schema 2 十三列账本（默认模板格式，项目可再收窄枚举）。带 v1 marker 的账本按
# 十三列检查，避免把正常的扩展列误判成“缺少 ## 账本”或把“带欠账”状态
# 误判成旧结论词；旧八列账本继续用 legacy 分支读取。
V1_MARKER = "<!-- acceptance-evidence: v1 -->"
V1_STATUSES = ("通过", "带欠账", "未交付-失败", "未交付-阻塞", "未覆盖")
V1_EVIDENCE_TYPES = ("截图", "布局树", "像素", "DB", "日志", "性能")
V1_CONFIDENCES = ("高", "中", "低")
V1_CONCLUSIONS = ("通过", "带欠账交付", "未交付（失败）", "未交付（阻塞）")
# 新账本默认只允许四状态、三结论；“带欠账”只为读取历史账本保留，
# 需要显式 --compat-debt 才放行，避免它被当成新的收口出口。
V1_STRICT_STATUSES = tuple(status for status in V1_STATUSES if status != "带欠账")
V1_STRICT_CONCLUSIONS = tuple(conclusion for conclusion in V1_CONCLUSIONS if conclusion != "带欠账交付")
V1_PLACEHOLDER_CONCLUSIONS = {
    "通过 / 带欠账交付 / 未交付（失败 / 阻塞）",
    "通过/带欠账交付/未交付（失败/阻塞）",
    "通过 / 带欠账交付 / 未交付",
    "通过/带欠账交付/未交付",
}


@dataclass(frozen=True)
class LedgerPolicy:
    """v1 账本允许的状态与包结论。

    默认值是四状态、三结论，新账本不能写“带欠账”；读取历史账本时用
    `--compat-debt` 显式放行。项目适配层可以继续收窄，但不能超出
    verity 支持的枚举，防止项目配置把错别字固化成新规范。
    """

    statuses: tuple[str, ...] = V1_STRICT_STATUSES
    conclusions: tuple[str, ...] = V1_STRICT_CONCLUSIONS
    evidence_types: tuple[str, ...] = V1_EVIDENCE_TYPES
    confidences: tuple[str, ...] = V1_CONFIDENCES


def normalize_conclusion(value: str) -> str:
    """把包结论里的半角括号统一成全角，便于和适配层枚举比较。"""
    return value.strip().replace("(", "（").replace(")", "）")
V1_SCHEMA_VERSION = "2"
V1_REQUIRED_COLUMNS = (
    "id",
    "covers",
    "user_path",
    "expected",
    "evidence_type",
    "evidence",
    "level",
    "producer",
    "reviewer",
    "confidence",
    "time",
    "commit",
    "status",
)
V1_COLUMN_ALIASES = {
    "id": ("验收项id", "验收项 id", "id", "编号"),
    "covers": ("覆盖ac", "覆盖 ac", "覆盖验收项", "covers"),
    "user_path": ("用户路径", "用户入口"),
    "expected": ("预期", "验收预期"),
    "evidence_type": ("证据类型",),
    "evidence": ("证据",),
    "level": ("证据等级", "等级"),
    "producer": ("产出者", "产出人"),
    "reviewer": ("复核者", "复核人"),
    "confidence": ("置信度",),
    "time": ("时间", "日期"),
    "commit": ("commit", "提交"),
    "status": ("状态",),
}
V1_DISPLAY_COLUMNS = {
    "id": "验收项 ID",
    "covers": "覆盖 AC",
    "user_path": "用户路径",
    "expected": "预期",
    "evidence_type": "证据类型",
    "evidence": "证据",
    "level": "证据等级",
    "producer": "产出者",
    "reviewer": "复核者",
    "confidence": "置信度",
    "time": "时间",
    "commit": "commit",
    "status": "状态",
}
# v2 账本必须齐全的段；少一段就说明收口结构不完整，不能靠单行字段齐全蒙混。
V1_REQUIRED_SECTIONS = (
    "批次信息",
    "用户旅程",
    "包结论",
    "外部证据登记",
    "单项验收（证据账本）",
    "证据身份",
    "完成审计",
    "独立复核",
    "欠账",
    "阻塞举证",
)
# 发布批次额外要求的两段：单向门/回滚风险，以及 F 类复盘。
V1_RELEASE_SECTIONS = ("发布风险", "复盘")
V1_REVIEW_VERDICTS = ("supports", "does-not-support", "unclear")
V1_LEVELS = ("A", "B+", "B", "C")
V1_STRUCTURED_KEYS = {
    "截图": ("viewport", "pixel_hash"),
    "像素": ("viewport", "pixel_hash"),
    "性能": ("runs", "median"),
    "DB": ("before", "after"),
}
# AC 判据里这些词只表达主观感受，无法判定通过与否；需要改成可观察结果。
VAGUE_CRITERION_WORDS = (
    "正常",
    "流畅",
    "友好",
    "尽量",
    "适当",
    "合理",
    "快速",
    "稳定",
    "基本可用",
    "差不多",
)
CRITERION_EXEMPT_RE = re.compile(r"<!--\s*criterion-exempt:\s*(AC-[A-Za-z0-9-]+)\s+(.+?)\s*-->")
# 可判定判据至少要有“动作”和“可观察结果/阈值”，否则“功能可用”这类
# 句子也能过 lint。词表只做下限判断，不替代人工评审。
CRITERION_ACTION_WORDS = (
    "点击", "打开", "输入", "提交", "运行", "执行", "调用", "请求", "创建", "删除",
    "修改", "保存", "加载", "返回", "显示", "输出", "写入", "生成", "触发", "切换",
    "上传", "下载", "启动", "停止", "查询", "搜索", "选择", "安装", "升级", "回滚",
    "校验", "检查", "复跑", "构建", "发布", "读取", "设置", "断言", "比对",
)
CRITERION_OBSERVABLE_RE = re.compile(
    r"(出现|显示|返回|输出|等于|为\s*\d|变成|变为|增加|减少|成功|失败|报错|错误码|"
    r"退出码|读数|计数|状态|一致|包含|存在|为空|不为空|通过|不通过|阈值|"
    r"\d+\s*(?:秒|毫秒|次|条|个|份|%|px)|[<>=≥≤]\s*\d|是|否|OK|PASS|FAIL)",
    re.IGNORECASE,
)
CRITERION_UNIVERSAL_WORDS = ("全部", "所有", "任意", "每次", "始终", "一律", "从不")
CRITERION_SAMPLE_RE = re.compile(
    r"(样本|范围|共\s*\d+|\d+\s*(?:个|条|次|份|批|例)|覆盖\s*\d+|在.{0,12}(?:范围|样本))"
)


def criterion_problem(criterion: str) -> str:
    """返回判据不可判定的原因；空字符串表示通过 lint。"""
    text = criterion.strip()
    if len(text) < 8:
        return "判据太短，至少写清动作和可观察结果"
    if not any(word in text for word in CRITERION_ACTION_WORDS):
        return "判据缺少可执行动作（如点击、运行、提交、返回）"
    if not CRITERION_OBSERVABLE_RE.search(text):
        return "判据缺少可观察结果、读数或阈值（如退出码 0、计数=1、显示成功）"
    for word in CRITERION_UNIVERSAL_WORDS:
        if word in text and not CRITERION_SAMPLE_RE.search(text):
            return f"全称结论“{word}”没有写样本范围（如共 3 个、抽样 5 条）"
    return ""
V1_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*-[0-9]{2,3}$")
V1_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
V1_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 证据 commit 之后到 HEAD 只允许出现“记录性”改动；只要动过下面这些
# 实现或规则路径，旧证据就不再能证明当前 HEAD 的行为，必须重新取证。
# docs/、CHANGELOG.md、evidence/ 等只影响记录，允许在取证提交之后追加。
IMPLEMENTATION_CHANGE_PREFIXES = (
    "scripts/",
    "templates/",
    "references/",
    "tests/",
    ".github/",
)
IMPLEMENTATION_CHANGE_FILES = {"SKILL.md", "README.md", "VERSION"}

# 截图类证据必须能落到一张真实图片上。只认常见图片后缀，并要求文件非空；
# “见截图”“截图如下”这类自述不算证据，防止用文字冒充截图。
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}

# 自述缺口短语：这些话出现在“通过/带欠账”的证据列里，说明证据边界没有
# 覆盖验收项本身，不能作为通过依据。只做保守的短语命中，不改 legacy 行为。
SCOPE_GAP_PHRASES = ("只跑了主路径", "只跑主路径", "仅跑主路径", "只覆盖主路径", "只验证主路径")
PROBE_MISSING_PHRASES = ("没跑探针", "未跑探针", "没有跑探针", "未执行探针", "没做探针", "没探针", "无探针", "没有探针")
DEVICE_UNVERIFIED_PHRASES = ("设备未验", "设备没验", "设备未验证", "未上设备", "没上设备", "未在设备")

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


def resolve_existing_path(candidate: str, root: Path, ledger_dir: Path) -> Optional[Path]:
    """返回证据文件的实际路径；不存在时返回 None。

    相对路径允许按账本所在目录或项目根解析，账本目录优先，便于批次内
    证据随批次目录一起移动。
    """
    raw = Path(candidate)
    if raw.is_absolute():
        return raw if raw.is_file() else None
    for base in (ledger_dir, root):
        path = base / raw
        if path.is_file():
            return path
    return None


def path_exists(candidate: str, root: Path, ledger_dir: Path) -> bool:
    """证据路径允许按仓库根相对，也允许按账本所在目录相对。"""
    return resolve_existing_path(candidate, root, ledger_dir) is not None


def _png_pixels(data: bytes) -> Optional[dict]:
    """解析 PNG 头并计算解码后像素字节的 SHA-256。

    只接受 8 位、非隔行的灰度/RGB/RGBA/灰度+Alpha；其余格式返回尺寸但
    pixel_hash 为 None，检查器会明确拒绝拿不可验证的哈希判通过。
    """
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    position = 8
    width = height = bit_depth = color_type = interlace = None
    compressed = bytearray()
    while position + 12 <= len(data):
        length = int.from_bytes(data[position:position + 4], "big")
        chunk_type = data[position + 4:position + 8]
        chunk = data[position + 8:position + 8 + length]
        if len(chunk) != length:
            return None
        if chunk_type == b"IHDR" and length >= 13:
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(
                ">IIBBBBB", chunk[:13]
            )
        elif chunk_type == b"IDAT":
            compressed.extend(chunk)
        elif chunk_type == b"IEND":
            break
        position += 12 + length
    if width is None or height is None or not width or not height:
        return None
    info = {"format": "png", "width": width, "height": height, "pixel_hash": None}
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type)
    if bit_depth != 8 or interlace != 0 or channels is None:
        return info
    try:
        raw = zlib.decompress(bytes(compressed))
    except zlib.error:
        return info
    stride = width * channels
    if len(raw) < height * (stride + 1):
        return info
    previous = bytearray(stride)
    pixels = bytearray()
    offset = 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        row = bytearray(raw[offset:offset + stride])
        offset += stride
        for index in range(stride):
            left = row[index - channels] if index >= channels else 0
            above = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 1:
                row[index] = (row[index] + left) & 0xFF
            elif filter_type == 2:
                row[index] = (row[index] + above) & 0xFF
            elif filter_type == 3:
                row[index] = (row[index] + ((left + above) // 2)) & 0xFF
            elif filter_type == 4:
                p = left + above - upper_left
                pa, pb, pc = abs(p - left), abs(p - above), abs(p - upper_left)
                predictor = left if pa <= pb and pa <= pc else (above if pb <= pc else upper_left)
                row[index] = (row[index] + predictor) & 0xFF
            elif filter_type != 0:
                return info
        pixels.extend(row)
        previous = row
    info["pixel_hash"] = hashlib.sha256(bytes(pixels)).hexdigest()
    return info


def _jpeg_size(data: bytes) -> Optional[dict]:
    """解析 JPEG 的 SOF 段，返回宽高；无法解码像素哈希。"""
    if not data.startswith(b"\xff\xd8"):
        return None
    position = 2
    while position + 4 <= len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        marker = data[position + 1]
        position += 2
        if marker in {0xD8, 0xD9}:
            continue
        if position + 2 > len(data):
            return None
        length = int.from_bytes(data[position:position + 2], "big")
        if length < 2 or position + length > len(data):
            return None
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if length < 7:
                return None
            height = int.from_bytes(data[position + 3:position + 5], "big")
            width = int.from_bytes(data[position + 5:position + 7], "big")
            if width and height:
                return {"format": "jpeg", "width": width, "height": height, "pixel_hash": None}
            return None
        position += length
    return None


def read_image_info(path: Path) -> Optional[dict]:
    """读取图片真实尺寸；ASCII 文本改名 .png 会在这里被拒绝。"""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if path.suffix.lower() == ".png":
        return _png_pixels(data)
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        return _jpeg_size(data)
    return None


def has_readable_image(evidence: str, root: Path, ledger_dir: Path) -> bool:
    """判断证据里是否至少有一张能按文件头解析出尺寸的图片。

    截图证据的关键是“图能打开”，不是“文字里写了截图”。只认 PNG/JPEG
    文件头；把 ASCII 文本改名成 shot.png 不会再被当成截图。
    """
    for candidate in extract_paths(evidence):
        resolved = resolve_existing_path(candidate, root, ledger_dir)
        if resolved is None or resolved.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if read_image_info(resolved) is not None:
            return True
    return False


# 记录类目录：文档、验收账本、测试材料都属于“记录”，不是受控实现。
# 账本和证据会在取证后继续补写，把它们算进工作区指纹等于“一写账本就
# 作废自己的证据”，因此一律排除。受控实现变化才让旧证据失效。
RECORD_DIR_PREFIXES = ("docs/", "acceptance/", "dist/")


def _is_record_path(relative: str, excluded: Optional[str]) -> bool:
    """判断路径是否属于记录类（不计入工作区指纹）。"""
    if excluded and (relative == excluded or relative.startswith(excluded + "/")):
        return True
    if relative.startswith(".git/") or any(relative.startswith(prefix) for prefix in RECORD_DIR_PREFIXES):
        return True
    # 账本与清单本身随取证更新；证据文件由证据身份表的 SHA-256 单独约束。
    if Path(relative).name.startswith("07-") or Path(relative).name == "manifest.json":
        return True
    if relative.startswith("evidence/") or "/evidence/" in relative:
        return True
    return False


def _fingerprint_bytes(payload: bytes) -> bytes:
    """文本按 LF 归一后再入指纹。

    git 的内容模型是 LF，工作区里的 CRLF 只是检出设置（core.autocrlf）的
    产物。不归一的话，“同一份提交在两台机器上指纹不同”，干净检出与本地
    工作区会互相判对方作废。
    """
    if b"\0" in payload[:8192]:
        return payload
    return payload.replace(b"\r\n", b"\n")


def workspace_fingerprint(root: Path, exclude_dir: Optional[Path] = None) -> Optional[str]:
    """按 git 跟踪文件内容计算工作区指纹。

    只算已跟踪文件，避免未跟踪的评审记录改变结果；账本所在目录与记录类
    目录（docs/、acceptance/、evidence/、07-*.md、manifest.json）不计入，
    所以补写账本、另一份账本的说明、批次文档都不会让本批证据失效。取证后
    受控实现文件内容变化，指纹就会不同，从而让旧证据失效。
    """
    excluded = None
    if exclude_dir is not None:
        try:
            excluded = exclude_dir.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            excluded = None
    try:
        listed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=False,
        )
        names = [raw.decode("utf-8", "surrogateescape") for raw in listed.stdout.split(b"\0") if raw]
        if listed.returncode != 0:
            names = []
    except OSError:
        names = []
    if not names:
        # 非 git 目录（反例夹具、导出的证据包）按目录内容计算；
        # 账本和清单会随取证更新，不纳入工作区指纹，否则永远对不上。
        names = [
            path.relative_to(root).as_posix()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        ]
    digest = hashlib.sha256()
    for relative in names:
        if _is_record_path(relative, excluded):
            continue
        path = root / relative
        if not path.is_file():
            continue
        digest.update(relative.encode("utf-8", "surrogateescape"))
        digest.update(b"\0")
        try:
            digest.update(_fingerprint_bytes(path.read_bytes()))
        except OSError:
            continue
        digest.update(b"\0")
    return digest.hexdigest()


def self_report_gap_issues(evidence: str, status: str, item_id: str, line: int) -> list[Issue]:
    """返回证据自述里暴露出的覆盖缺口。

    只在 v1 的“通过/带欠账”行调用：失败和阻塞本来就允许写清缺口，
    不能把它们再判成“自述缺口”。短语按去空白后的文本匹配，避免
    “只跑了 主路径”这种排版差异漏检。
    """
    if status not in {"通过", "带欠账"}:
        return []
    compact = re.sub(r"\s+", "", evidence)
    issues: list[Issue] = []
    if any(phrase in compact for phrase in SCOPE_GAP_PHRASES):
        issues.append(
            Issue(
                "E_SCOPE_GAP",
                f"{item_id or '该行'} 的证据自述只覆盖主路径，不能支撑整个验收项通过",
                line,
            )
        )
    if "门禁全绿" in compact and any(phrase in compact for phrase in PROBE_MISSING_PHRASES):
        issues.append(
            Issue(
                "E_PROBE_MISSING",
                f"{item_id or '该行'} 只写了门禁全绿，但自述没跑探针；门禁不能替代探针结论",
                line,
            )
        )
    if any(phrase in compact for phrase in DEVICE_UNVERIFIED_PHRASES):
        issues.append(
            Issue(
                "E_DEVICE_UNVERIFIED",
                f"{item_id or '该行'} 自述设备未验证，不能写成通过",
                line,
            )
        )
    return issues


def git_commit_date(root: Path, commit: str) -> tuple[Optional[date], Optional[str]]:
    """校验 commit 是否是真实提交并返回提交日期。

    返回 (日期, 错误)。不是 git 仓库、对象不存在或不是 commit 时，错误
    非空；日期按本机时区取，与证据文件 mtime 的时区口径一致。
    """
    try:
        verify = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError) as error:
        return None, f"无法执行 git：{error}"
    if verify.returncode != 0:
        return None, "不是真实 git 提交，或项目根不是 git 仓库"
    try:
        show = subprocess.run(
            ["git", "-C", str(root), "show", "-s", "--format=%ct", commit],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError) as error:
        return None, f"无法读取提交时间：{error}"
    if show.returncode != 0 or not show.stdout.strip().isdigit():
        return None, "无法读取提交时间"
    try:
        return datetime.fromtimestamp(int(show.stdout.strip())).date(), None
    except (ValueError, OSError) as error:
        return None, f"提交时间无法解析：{error}"


def git_is_ancestor(root: Path, commit: str) -> tuple[bool, Optional[str]]:
    """判断 commit 是否等于 HEAD 或为 HEAD 的祖先。

    git merge-base --is-ancestor 返回 0 = 是，1 = 不是，其他 = 无法判断。
    """
    try:
        process = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", commit, "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError) as error:
        return False, f"无法执行 git：{error}"
    if process.returncode == 0:
        return True, None
    if process.returncode == 1:
        return False, None
    return False, "无法判断 commit 与 HEAD 的祖先关系（项目根可能不是 git 仓库）"


def git_changed_paths(root: Path, base: str, head: str = "HEAD") -> tuple[list[str], Optional[str]]:
    """列出 base..head 之间改动过的仓库相对路径。

    证据绑定的是“取证时的实现版本”。如果之后又改了检查器、模板、规则或
    示例，旧证据只能说明旧版本，不能继续为最终 HEAD 背书。这里使用
    --name-only 只取路径，不依赖文件是否存在。
    """
    try:
        process = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", f"{base}..{head}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError) as error:
        return [], f"无法执行 git：{error}"
    if process.returncode != 0:
        return [], "无法读取证据提交到 HEAD 的差异"
    return [line.strip() for line in process.stdout.splitlines() if line.strip()], None


def project_prefix(root: Path) -> str:
    """返回项目根相对 git 仓库根的前缀（带结尾斜杠，仓库根即项目根时为空）。

    git diff 给的是**仓库根**相对路径，而实现/规则前缀是**项目根**相对写法。
    项目在仓库子目录（monorepo）时，不剥前缀就永远匹配不到，导致“证据绑定
    提交之后实现又改过”这条检查静默失效。
    """
    code, output = git_output(root, "rev-parse", "--show-prefix")
    return output.strip() if code == 0 else ""


def git_output(root: Path, *args: str) -> tuple[int, str]:
    """执行 git 并返回 (退出码, stdout)；失败时 stdout 为空串。"""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return 1, ""
    return result.returncode, result.stdout


def stale_implementation_changes(paths: Iterable[str], prefix: str = "") -> list[str]:
    """返回 base..HEAD 中属于实现/规则文件的路径。

    prefix 是项目根相对仓库根的前缀；传入后会先剥掉前缀再比对，避免
    monorepo 里 `notes-hap/scripts/...` 匹配不到 `scripts/` 而静默失效。
    """
    changed: list[str] = []
    for path in paths:
        normalized = path.replace("\\", "/")
        if prefix and normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
        if normalized in IMPLEMENTATION_CHANGE_FILES:
            changed.append(normalized)
            continue
        if any(normalized.startswith(prefix) for prefix in IMPLEMENTATION_CHANGE_PREFIXES):
            changed.append(normalized)
    return changed


def git_path_dirty(root: Path, path: Path) -> tuple[bool, Optional[str]]:
    """判断单个文件相对 HEAD 是否有未提交改动；非 git 仓库按“无改动”处理。"""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        return False, str(error)
    if result.returncode != 0:
        return False, result.stderr.strip() or None
    return bool(result.stdout.strip()), None


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
    required = ("任务卡", "被测版本", "环境")
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
    if not values.get("执行者") or not values.get("复核者"):
        if not values.get("执行者/复核者"):
            issues.append(
                Issue("W_BATCH_INFO", "批次信息缺少执行者或复核者", section[1], severity="warning")
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
    """把 v1 schema 2 十三列表头映射到字段键；列名允许少量中文别名。"""
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


def expected_v1_conclusion(
    statuses: list[str],
    policy: Optional[LedgerPolicy] = None,
    journey_passed: bool = True,
) -> str:
    """由账本状态和旅程结论推导包结论。

    旅程没通过时，即使所有验收行都通过，整批也只能是“未交付（失败）”；
    这是 v2 相对 v1 的关键收紧，防止账本单行全绿掩盖用户路径没走通。
    """
    current = policy or LedgerPolicy()
    if not journey_passed:
        return "未交付（失败）"
    if any(status == "未交付-失败" for status in statuses):
        return "未交付（失败）"
    if any(status == "未交付-阻塞" for status in statuses):
        return "未交付（阻塞）"
    if any(status == "未覆盖" for status in statuses):
        return "未交付（失败）"
    if "带欠账" in current.statuses and any(status == "带欠账" for status in statuses):
        return "带欠账交付"
    if statuses and all(status == "通过" for status in statuses):
        return "通过"
    return ""


def find_section_prefix(
    sections: list[tuple[str, int, list[tuple[int, str]]]], prefix: str
) -> Optional[tuple[str, int, list[tuple[int, str]]]]:
    """按标题前缀找段，兼容“1. 卡点”“## 卡点”两种写法。"""
    for section in sections:
        if section[0] == prefix or section[0].startswith(prefix):
            return section
    return None


def table_key_values(
    section: tuple[str, int, list[tuple[int, str]]]
) -> tuple[dict[str, str], dict[str, int]]:
    """读取两列表格的键值对，返回值表和键所在行号。"""
    values: dict[str, str] = {}
    lines: dict[str, int] = {}
    table = parse_first_table(section[2])
    if table is None:
        return values, lines
    _, _, rows = table
    for number, row in rows:
        if len(row) >= 2:
            key = normalize_header(row[0])
            values[key] = row[1].strip()
            lines[key] = number
    return values, lines


def parse_batch_values(sections) -> tuple[dict[str, str], dict[str, int], Optional[int]]:
    """读取 v2 批次信息；返回值、行号和段起始行。"""
    section = find_section(sections, "批次信息")
    if section is None:
        return {}, {}, None
    values, lines = table_key_values(section)
    return values, lines, section[1]


def parse_task_card_acs(task_text: str) -> list[tuple[str, str, int]]:
    """从任务卡读取 AC 清单：返回 [(AC-ID, 判据, 行号)]。"""
    sections = split_sections(task_text)
    for name in ("验收项表", "验收项", "验收标准"):
        section = find_section(sections, name)
        if section is None:
            continue
        table = parse_first_table(section[2])
        if table is None:
            continue
        _, header, rows = table
        normalized = [normalize_header(item) for item in header]
        id_index = None
        criterion_index = None
        for index, item in enumerate(normalized):
            if id_index is None and item in {"验收项id", "验收项 id", "id", "编号", "ac-id", "ac id"}:
                id_index = index
            if criterion_index is None and (
                item in {"判据", "验收判据", "验收标准", "预期", "通过判据"}
                or item.startswith("判据（")
                or item.startswith("判据(")
            ):
                criterion_index = index
        if id_index is None:
            continue
        result: list[tuple[str, str, int]] = []
        for number, row in rows:
            ac_id = cell(row, id_index).strip()
            if not ac_id:
                continue
            result.append((ac_id, cell(row, criterion_index).strip(), number))
        return result
    return []


def parse_ac_ids(value: str) -> list[str]:
    """从“AC-01、AC-02”之类单元格里提取 AC ID。"""
    return re.findall(r"AC-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", value)


def read_scope_lock(task_text: str) -> tuple[list[str], list[str]]:
    """读取任务卡范围锁，返回 (做, 不做) 路径列表。"""
    sections = split_sections(task_text)
    section = find_section(sections, "范围锁")
    if section is None:
        return [], []
    table = parse_first_table(section[2])
    if table is None:
        return [], []
    _, header, rows = table
    normalized = [normalize_header(item) for item in header]
    type_index = next((i for i, item in enumerate(normalized) if item in {"类型", "做不做"}), None)
    path_index = next((i for i, item in enumerate(normalized) if item in {"路径", "范围", "文件"}), None)
    if type_index is None or path_index is None:
        return [], []
    allow: list[str] = []
    deny: list[str] = []
    for _, row in rows:
        kind = cell(row, type_index).strip()
        value = cell(row, path_index).strip()
        if not value or value.startswith("<"):
            continue
        if kind in {"做", "允许", "范围"}:
            allow.append(value)
        elif kind in {"不做", "禁止", "范围外"}:
            deny.append(value)
    return allow, deny


def check_task_card(
    ledger_dir: Path,
    batch_values: dict[str, str],
    issues: list[Issue],
) -> tuple[Optional[Path], list[tuple[str, str, int]], str, str, str]:
    """校验任务卡结构并返回 AC 清单、车道和风险。"""
    card_name = batch_values.get("任务卡", "").strip()
    card_path: Optional[Path] = None
    if card_name and not v1_text_empty(card_name):
        candidate = Path(card_name)
        if not candidate.is_absolute():
            candidate = ledger_dir / candidate
        if candidate.exists():
            card_path = candidate
    if card_path is None:
        fallback = ledger_dir / "task-card.md"
        if fallback.exists():
            card_path = fallback
    if card_path is None:
        issues.append(Issue("E_TASKCARD", "找不到任务卡；v2 账本必须能和任务卡 AC 双向映射", None))
        return None, [], "", "", ""

    text = card_path.read_text(encoding="utf-8")
    sections = split_sections(text)
    basic = find_section(sections, "基本信息")
    card_schema = ""
    if basic is not None:
        basic_values, _ = table_key_values(basic)
        card_schema = basic_values.get("schema_version", "").strip()
    if card_schema != "2":
        issues.append(
            Issue(
                "E_SCHEMA",
                f"任务卡 schema_version 必须是 2（当前 {card_schema or '缺失'}）；"
                "旧任务卡先运行 python3 scripts/verity.py upgrade <07>",
                basic[1] if basic is not None else None,
            )
        )
    acs = parse_task_card_acs(text)
    if not acs:
        issues.append(Issue("E_TASKCARD", "任务卡没有可解析的“验收项表”或 AC 清单", None))

    lane = ""
    risk = ""
    complexity = ""
    hard_trigger = ""
    lane_section = find_section(sections, "车道与风险")
    if lane_section is None:
        issues.append(Issue("E_TASK_LANE", "任务卡缺少“## 车道与风险”段", None))
    else:
        values, _ = table_key_values(lane_section)
        lane = values.get("车道", "").strip()
        risk = values.get("风险", "").strip()
        complexity = values.get("复杂度", "").strip()
        hard_trigger = values.get("硬触发", "").strip()
        if lane not in {"轻验收", "全流程"}:
            issues.append(Issue("E_TASK_LANE", "车道只能是“轻验收”或“全流程”", lane_section[1]))
        if not hard_trigger:
            issues.append(
                Issue("E_TASK_LANE", "车道与风险表缺少“硬触发”字段（没有就填“无”）", lane_section[1])
            )
        trigger_words = (
            "发布", "数据", "安全", "跨模块", "多步用户旅程", "难复现", "不可逆", "迁移"
        )
        hit_triggers = [word for word in trigger_words if word in hard_trigger]
        if hit_triggers and lane != "全流程":
            issues.append(
                Issue(
                    "E_TASK_LANE",
                    "硬触发命中“" + "、".join(hit_triggers) + "”，必须走全流程车道",
                    lane_section[1],
                )
            )

    if lane == "全流程":
        grill = find_section(sections, "立卡前盘问")
        if grill is None:
            issues.append(Issue("E_GRILL", "全流程任务缺少“## 立卡前盘问”段", None))
        else:
            table = parse_first_table(grill[2])
            useful = 0
            if table is not None:
                _, _, rows = table
                for number, row in rows:
                    decision = cell(row, len(row) - 1).strip()
                    if decision and not decision.startswith("<") and decision not in {"—", "-"}:
                        useful += 1
            if not 5 <= useful <= 10:
                issues.append(
                    Issue(
                        "E_GRILL",
                        "立卡前盘问必须记录 5–10 条问题，且每条都有推荐答案和用户决定",
                        grill[1],
                    )
                )

        spec = find_section_prefix(sections, "规格摘要")
        if spec is None:
            issues.append(Issue("E_SPEC_LITE", "全流程任务缺少“## 规格摘要”段", None))
        else:
            values, _ = table_key_values(spec)
            required_spec = ("问题", "用户", "目标", "范围外", "关键决定", "验收方向")
            missing_spec = [name for name in required_spec if not values.get(name, "").strip()]
            if missing_spec:
                issues.append(
                    Issue(
                        "E_SPEC_LITE",
                        "规格摘要缺字段：" + "、".join(missing_spec),
                        spec[1],
                    )
                )

    scope = find_section(sections, "范围锁")
    if scope is None:
        issues.append(Issue("E_SCOPE_LOCK", "任务卡缺少“## 范围锁”段", None))
    else:
        allow, _ = read_scope_lock(text)
        if not allow:
            issues.append(Issue("E_SCOPE_LOCK", "范围锁没有填写任何“做”路径", scope[1]))

    exemptions = {match.group(1): match.group(2).strip() for match in CRITERION_EXEMPT_RE.finditer(text)}
    for ac_id, criterion, number in acs:
        if not criterion:
            issues.append(Issue("E_CRITERION", f"{ac_id} 没有可判定判据", number))
            continue
        if ac_id in exemptions:
            reason = exemptions[ac_id]
            if len(reason) < 8 or reason in {"无", "无需", "不适用", "见上"}:
                issues.append(
                    Issue("E_CRITERION", f"{ac_id} 的 criterion-exempt 理由过于笼统，需写清为何不可自动判定", number)
                )
            continue
        hit = next((word for word in VAGUE_CRITERION_WORDS if word in criterion), "")
        if not hit and re.search(r"(?:^|[，。；、\s])等(?:[，。；、\s]|$)", criterion):
            hit = "等"
        if hit:
            issues.append(
                Issue(
                    "E_CRITERION",
                    f"{ac_id} 的判据含模糊词“{hit}”，请改成可观察结果或加 criterion-exempt 说明",
                    number,
                )
            )
            continue
        problem = criterion_problem(criterion)
        if problem:
            issues.append(Issue("E_CRITERION", f"{ac_id} 的判据不可判定：{problem}", number))

    return card_path, acs, lane, risk, hard_trigger


def check_journey_section(
    ledger_dir: Path,
    sections,
    rows: list[dict],
    risk: str,
    hard_trigger: str,
    issues: list[Issue],
) -> bool:
    """校验旅程卡、旅程结论和 07 行到旅程步骤的映射。"""
    section = find_section(sections, "用户旅程")
    if section is None:
        return False
    text = "\n".join(line for _, line in section[2])
    card_match = re.search(r"旅程卡[:：]\s*(.+)", text)
    conclusion_match = re.search(r"结论[:：]\s*(.+)", text)
    conclusion = conclusion_match.group(1).strip() if conclusion_match else ""
    cards = []
    if card_match:
        cards = [
            item.strip().strip("`")
            for item in re.split(r"[,，、;；]", card_match.group(1))
            if item.strip()
        ]
    if not cards:
        issues.append(Issue("E_JOURNEY_MISSING", "用户旅程段没有填写旅程卡路径", section[1]))
        return False
    if v1_text_empty(conclusion) or conclusion not in {"通过", "未通过", "阻塞", "未覆盖"}:
        issues.append(Issue("E_JOURNEY", "用户旅程结论必须是 通过/未通过/阻塞/未覆盖", section[1]))
        return False
    if conclusion != "通过":
        issues.append(
            Issue("E_JOURNEY_NOT_PASSED", f"旅程结论为“{conclusion}”，整批不得判通过", section[1])
        )

    passed = conclusion == "通过"
    # 跨区域批次至少要有三张旅程卡，覆盖不同区域；一张卡不能代表多区域。
    if "跨区域" in (risk + hard_trigger) and len(cards) < 3:
        issues.append(
            Issue(
                "E_JOURNEY_REGION",
                f"跨区域批次至少需要 3 张旅程卡，当前只有 {len(cards)} 张",
                section[1],
            )
        )
        passed = False
    for name in cards:
        card_path = ledger_dir / name
        if not card_path.exists():
            issues.append(Issue("E_JOURNEY_MISSING", f"旅程卡不存在：{name}", section[1]))
            passed = False
            continue
        card_text = card_path.read_text(encoding="utf-8")
        card_sections = split_sections(card_text)
        card_conclusion_section = find_section(card_sections, "结论")
        card_conclusion = ""
        if card_conclusion_section is not None:
            match = re.search(
                r"结论[:：]\s*(通过|未通过|阻塞|未覆盖)",
                "\n".join(line for _, line in card_conclusion_section[2]),
            )
            card_conclusion = match.group(1) if match else ""
        if card_conclusion != "通过":
            issues.append(
                Issue("E_JOURNEY_CARD", f"旅程卡 {name} 自身结论不是“通过”", section[1])
            )
            passed = False

        card_id = "J-01"
        base = find_section(card_sections, "基本信息")
        if base is not None:
            values, _ = table_key_values(base)
            card_id = values.get("旅程id", card_id) or card_id
        step_section = find_section(card_sections, "步骤与不变量")
        steps: list[int] = []
        if step_section is not None:
            table = parse_first_table(step_section[2])
            if table is not None:
                _, header, step_rows = table
                normalized = [normalize_header(item) for item in header]
                index = next(
                    (i for i, item in enumerate(normalized) if item in {"步骤", "序号", "步骤号", "#", "编号"}),
                    None,
                )
                if index is not None:
                    for _, row in step_rows:
                        value = cell(row, index).strip()
                        if value.isdigit():
                            steps.append(int(value))
        if not steps:
            issues.append(Issue("E_JOURNEY_STEP", f"旅程卡 {name} 没有可解析的步骤表", section[1]))
            passed = False
        elif not 3 <= len(steps) <= 7:
            issues.append(
                Issue(
                    "E_JOURNEY_STEP",
                    f"旅程卡 {name} 有 {len(steps)} 步，应为 3–7 步",
                    section[1],
                )
            )
            passed = False
        # 每张卡至少写三条跨区域不变量；不变量是“换区域仍成立”的约束，
        # 不是重复步骤描述。
        invariants: set[str] = set()
        if step_section is not None:
            table = parse_first_table(step_section[2])
            if table is not None:
                _, header, invariant_rows = table
                normalized = [normalize_header(item) for item in header]
                invariant_index = next(
                    (i for i, item in enumerate(normalized) if "不变量" in item),
                    None,
                )
                if invariant_index is not None:
                    for _, row in invariant_rows:
                        value = cell(row, invariant_index).strip()
                        if value and not value.startswith("<") and value not in {"—", "-"}:
                            invariants.add(value)
        if len(invariants) < 3:
            issues.append(
                Issue(
                    "E_JOURNEY_INVARIANT",
                    f"旅程卡 {name} 只有 {len(invariants)} 条不变量，每卡至少 3 条",
                    section[1],
                )
            )
            passed = False
        for step in steps:
            pattern = re.compile(rf"{re.escape(card_id)}\s*/\s*步骤\s*{step}(?!\d)")
            if not any(pattern.search(row["user_path"]) for row in rows):
                issues.append(
                    Issue(
                        "E_JOURNEY_STEP",
                        f"旅程步骤 {card_id} 步骤 {step} 没有对应的 07 验收行",
                        section[1],
                    )
                )
                passed = False

        if any(word in risk for word in ("不可逆", "数据", "安全")):
            negative = find_section(card_sections, "异常、空、错误分支")
            if negative is None:
                issues.append(
                    Issue("E_JOURNEY_NEGATIVE", f"高风险旅程卡 {name} 缺少异常/空/错误分支", section[1])
                )
                passed = False
            else:
                table = parse_first_table(negative[2])
                filled = False
                if table is not None:
                    _, _, negative_rows = table
                    for _, row in negative_rows:
                        if all(item.strip() and not item.strip().startswith("<") for item in row):
                            filled = True
                            break
                if not filled:
                    issues.append(
                        Issue("E_JOURNEY_NEGATIVE", f"旅程卡 {name} 的异常分支没有填写", section[1])
                    )
                    passed = False
    return passed


def check_completion_audit(
    sections,
    acs: list[tuple[str, str, int]],
    batch_build: str,
    root: Path,
    ledger_dir: Path,
    issues: list[Issue],
) -> None:
    """检查完成审计表：每条 AC 都要有场景、构建、读数和证据。"""
    section = find_section(sections, "完成审计")
    if section is None:
        return
    table = parse_first_table(section[2])
    if table is None:
        issues.append(Issue("E_COMPLETION_AUDIT", "完成审计段没有表格", section[1]))
        return
    _, header, rows = table
    normalized = [normalize_header(item) for item in header]
    indexes = {}
    for key, aliases in {
        "definition": ("完成定义", "验收项", "完成项"),
        "ac": ("对应ac", "对应 ac", "ac", "验收项id"),
        "scenario": ("实际场景/命令", "实际场景命令", "场景/命令", "实际场景"),
        "build": ("最终构建", "构建", "构建号"),
        "reading": ("读数", "结果", "实际读数"),
        "evidence": ("证据", "证据路径"),
    }.items():
        indexes[key] = next((i for i, item in enumerate(normalized) if item in aliases), None)
    missing = [key for key, index in indexes.items() if index is None]
    if missing:
        issues.append(
            Issue("E_COMPLETION_AUDIT", "完成审计表头缺列：" + "、".join(missing), section[1])
        )
        return
    covered: set[str] = set()
    for number, row in rows:
        values = {key: cell(row, index).strip() for key, index in indexes.items()}
        if all(not value for value in values.values()):
            continue
        empty = [key for key, value in values.items() if not value or value.startswith("<")]
        if empty:
            issues.append(
                Issue("E_COMPLETION_AUDIT", "完成审计行有空字段：" + "、".join(empty), number)
            )
        ids = parse_ac_ids(values["ac"])
        if not ids:
            issues.append(Issue("E_COMPLETION_AC", "完成审计行没有对应 AC", number))
        covered.update(ids)
        if batch_build and values["build"] not in {batch_build, "同批次", "本批次"}:
            issues.append(
                Issue(
                    "E_COMPLETION_AUDIT",
                    f"完成审计的最终构建“{values['build']}”与批次构建“{batch_build}”不一致",
                    number,
                )
            )
        paths = extract_paths(values["evidence"])
        if not paths:
            issues.append(Issue("E_COMPLETION_EVIDENCE", "完成审计行没有真实证据路径", number))
        else:
            for candidate in paths:
                if resolve_existing_path(candidate, root, ledger_dir) is None:
                    issues.append(
                        Issue("E_COMPLETION_EVIDENCE", f"完成审计证据不存在：{candidate}", number)
                    )
    expected = {ac_id for ac_id, _, _ in acs}
    uncovered = sorted(expected - covered)
    if uncovered:
        issues.append(
            Issue("E_COMPLETION_AC", "完成审计缺少这些 AC 的记录：" + "、".join(uncovered), section[1])
        )


def _normalize_review_text(value: str) -> str:
    """把复核输出/记录压成单行，避免换行与多余空白造成假差异。"""
    return " ".join(value.split())


def _load_ev_records(path: Path) -> tuple[list[dict], list[str]]:
    """读取 ev-runs.log（JSON Lines），返回记录和格式错误。

    记录必须由 --run 实际执行后写入，不能手工编造。检查器只读记录，
    不再执行复核行里的任意命令，shell 包装因此失去作用。
    """
    if not path.is_file():
        return [], []
    records: list[dict] = []
    errors: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"ev-runs.log 第 {number} 行不是合法 JSON")
            continue
        if not isinstance(record, dict):
            errors.append(f"ev-runs.log 第 {number} 行不是对象")
            continue
        records.append(record)
    return records, errors


def _review_log_path(values: dict[str, str], root: Path, ledger_dir: Path) -> Path:
    """从复核证据列找 ev-runs.log；找不到时退回本批次 evidence/。"""
    for candidate in extract_paths(values.get("evidence", "")):
        resolved = resolve_existing_path(candidate, root, ledger_dir)
        if resolved is not None and resolved.name == "ev-runs.log":
            return resolved
    return ledger_dir / "evidence" / "ev-runs.log"


def check_independent_review(
    sections,
    acs: list[tuple[str, str, int]],
    rows: list[dict],
    batch_values: dict[str, str],
    root: Path,
    ledger_dir: Path,
    issues: list[Issue],
) -> None:
    """检查独立复核：逐 AC 表态，复核命令必须绑定 EV 执行记录。

    复核行的“复跑命令”只接受 EV ID。检查器从该行证据路径对应的
    ev-runs.log 读取实际执行记录，重算输出哈希，并核对 exit、HEAD、
    执行时间和输出摘要。任意命令字符串（包括 sh -c、echo、python -c）
    都无法提供匹配记录，因此不会因为“输出看起来对”而通过。
    """
    section = find_section(sections, "独立复核")
    if section is None:
        return
    table = parse_first_table(section[2])
    if table is None:
        issues.append(Issue("E_REVIEW", "独立复核段没有表格", section[1]))
        return
    _, header, review_rows = table
    normalized = [normalize_header(item) for item in header]
    indexes = {}
    for key, aliases in {
        "ac": ("ac-id", "ac id", "验收项id", "验收项 id"),
        "verdict": ("复核结论", "结论"),
        "command": ("复跑命令", "命令"),
        "evidence": ("复跑证据", "证据"),
        "reviewer": ("复核人", "复核者"),
        "time": ("时间", "日期"),
        "exitcode": ("复跑退出码", "退出码", "exit code"),
        "output": ("复跑输出", "输出摘要", "stdout/stderr 摘要"),
        "runtime": ("复跑时间", "执行时间"),
        "head": ("复跑 head", "复跑head", "head", "复跑提交"),
    }.items():
        indexes[key] = next((i for i, item in enumerate(normalized) if item in aliases), None)
    missing = [key for key, index in indexes.items() if index is None]
    if missing:
        issues.append(Issue("E_REVIEW", "独立复核表头缺列：" + "、".join(missing), section[1]))
        return

    batch_producer = batch_values.get("执行者", "").strip()
    batch_reviewer = batch_values.get("复核者", "").strip()
    if batch_producer and batch_reviewer and batch_producer == batch_reviewer:
        issues.append(
            Issue("E_REVIEW_INDEPENDENT", "批次执行者与复核者不能是同一个人", section[1])
        )

    build_text = batch_values.get("被测版本", "")
    commit_match = re.search(r"commit[:：]\s*([0-9a-fA-F]{7,40})", build_text)
    batch_commit = commit_match.group(1).lower() if commit_match else ""
    if not batch_commit:
        issues.append(
            Issue("E_REVIEW_COMMAND", "批次信息缺少被测 commit，无法绑定 EV 执行记录", section[1])
        )
    batch_date = batch_values.get("生成日期", "").strip()
    actual_head = _git_head(root)
    now = datetime.now()
    log_cache: dict[Path, tuple[list[dict], list[str]]] = {}
    covered: dict[str, list[dict]] = {}
    for number, row in review_rows:
        values = {key: cell(row, index).strip() for key, index in indexes.items()}
        if all(not value for value in values.values()):
            continue
        ids = parse_ac_ids(values["ac"])
        if not ids:
            issues.append(Issue("E_REVIEW_AC", "复核行没有 AC ID", number))
        if values["verdict"] not in V1_REVIEW_VERDICTS:
            issues.append(
                Issue(
                    "E_REVIEW_AC",
                    "复核结论只能是 supports / does-not-support / unclear",
                    number,
                )
            )
        if not values["reviewer"]:
            issues.append(Issue("E_REVIEW_INDEPENDENT", "复核人不能为空", number))
        elif batch_reviewer and values["reviewer"] != batch_reviewer:
            issues.append(
                Issue(
                    "E_REVIEW_INDEPENDENT",
                    f"复核人“{values['reviewer']}”与批次复核者“{batch_reviewer}”不一致",
                    number,
                )
            )
        if values["time"] and not V1_DATE_RE.fullmatch(values["time"]):
            issues.append(Issue("E_REVIEW", f"复核时间“{values['time']}”不是 YYYY-MM-DD", number))
        if values["exitcode"] != "0":
            issues.append(Issue("E_REVIEW_COMMAND", "复跑退出码必须是 0；没有真跑过不能写通过", number))
        output = values["output"].strip()
        if not output or output.startswith("<") or output in {"见", "同上", "见截图", "无输出"}:
            issues.append(Issue("E_REVIEW_COMMAND", "复跑输出摘要不能为空或写“见/同上”", number))
        if values["runtime"] and not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?", values["runtime"]
        ):
            issues.append(Issue("E_REVIEW_COMMAND", "复跑时间应为 YYYY-MM-DD 或 ISO 时间", number))

        command = values["command"].strip().strip("`")
        if not re.fullmatch(r"EV-\d{2,3}", command):
            issues.append(
                Issue(
                    "E_REVIEW_COMMAND",
                    "复跑命令必须填 EV ID（如 EV-01），不能填任意 shell 命令",
                    number,
                )
            )
            continue
        log_path = _review_log_path(values, root, ledger_dir)
        if log_path not in log_cache:
            log_cache[log_path] = _load_ev_records(log_path)
        records, log_errors = log_cache[log_path]
        for error in log_errors:
            issues.append(Issue("E_REVIEW_COMMAND", error, number))
        record = next(
            (item for item in reversed(records) if str(item.get("ev", "")).strip() == command),
            None,
        )
        if record is None:
            issues.append(
                Issue(
                    "E_REVIEW_COMMAND",
                    f"复核命令 {command} 没有对应的执行记录；必须先通过 --run 实际执行",
                    number,
                )
            )
            continue
        required_fields = ("time", "head", "ev", "command", "exit", "output", "output_sha256", "summary")
        missing_fields = [field for field in required_fields if not str(record.get(field, "")).strip()]
        if missing_fields:
            issues.append(
                Issue(
                    "E_REVIEW_COMMAND",
                    f"{command} 的执行记录缺字段：" + "、".join(missing_fields),
                    number,
                )
            )
            continue
        record_output = str(record["output"])
        claimed_hash = str(record["output_sha256"]).strip().lower()
        actual_hash = hashlib.sha256(record_output.encode("utf-8")).hexdigest()
        if claimed_hash != actual_hash:
            issues.append(
                Issue(
                    "E_REVIEW_COMMAND",
                    f"{command} 的输出哈希与记录内容不一致，记录可能被改写",
                    number,
                )
            )
        record_head = str(record["head"]).strip().lower()
        if not re.fullmatch(r"[0-9a-f]{7,40}", record_head):
            issues.append(Issue("E_REVIEW_COMMAND", f"{command} 的执行记录 HEAD 不是提交哈希", number))
        elif batch_commit and record_head != batch_commit:
            issues.append(
                Issue(
                    "E_REVIEW_COMMAND",
                    f"{command} 的执行记录 HEAD“{record_head[:12]}”不是本批被测 commit“{batch_commit[:12]}”",
                    number,
                )
            )
        else:
            ancestor, error = git_is_ancestor(root, record_head)
            if not ancestor:
                issues.append(
                    Issue(
                        "E_REVIEW_COMMAND",
                        f"{command} 的执行记录 HEAD“{record_head[:12]}”不是当前 HEAD“{actual_head[:12]}”的祖先"
                        + (f"：{error}" if error else ""),
                        number,
                    )
                )
        try:
            record_time = datetime.fromisoformat(str(record["time"]).replace("Z", "+00:00"))
            if record_time.tzinfo is not None:
                record_time = record_time.astimezone().replace(tzinfo=None)
        except ValueError:
            issues.append(Issue("E_REVIEW_COMMAND", f"{command} 的执行记录时间不是 ISO 时间", number))
            record_time = None
        if record_time is not None:
            if batch_date and V1_DATE_RE.fullmatch(batch_date):
                if record_time.date() < datetime.strptime(batch_date, "%Y-%m-%d").date():
                    issues.append(
                        Issue(
                            "E_REVIEW_COMMAND",
                            f"{command} 的执行记录早于批次生成日期，不能作为本次取证",
                            number,
                        )
                    )
            if record_time > now.replace(microsecond=0) + timedelta(minutes=5):
                issues.append(Issue("E_REVIEW_COMMAND", f"{command} 的执行记录时间晚于当前时间", number))
            if values["runtime"] and str(record["time"]).strip() != values["runtime"].strip():
                issues.append(
                    Issue(
                        "E_REVIEW_COMMAND",
                        f"{command} 的复跑时间与执行记录时间不一致",
                        number,
                    )
                )
        claimed_head = values["head"].strip().strip("`")
        if claimed_head.lower() != record_head:
            issues.append(
                Issue(
                    "E_REVIEW_COMMAND",
                    f"{command} 的复跑 HEAD 与执行记录 HEAD 不一致",
                    number,
                )
            )
        claimed_summary = _normalize_review_text(values["output"])
        record_summary = _normalize_review_text(str(record["summary"]))
        if claimed_summary != record_summary:
            issues.append(
                Issue(
                    "E_REVIEW_COMMAND",
                    f"{command} 的复跑输出与执行记录摘要不一致",
                    number,
                )
            )
        paths = extract_paths(values["evidence"])
        if not paths:
            issues.append(Issue("E_REVIEW", "复核行没有复跑证据路径", number))
        else:
            for candidate in paths:
                if resolve_existing_path(candidate, root, ledger_dir) is None:
                    issues.append(Issue("E_REVIEW", f"复跑证据不存在：{candidate}", number))
        for ac_id in ids:
            covered.setdefault(ac_id, []).append(values)

    expected = {ac_id for ac_id, _, _ in acs}
    for ac_id in sorted(expected):
        verdicts = [item["verdict"] for item in covered.get(ac_id, [])]
        if "supports" not in verdicts:
            issues.append(
                Issue("E_REVIEW_AC", f"{ac_id} 没有独立复核的 supports 结论", section[1])
            )
    a_ids = {
        ac_id
        for row in rows
        if row["status"] == "通过" and row["level"] == "A"
        for ac_id in row["covers"]
    }
    command_rows = [
        item
        for ac_id, items in covered.items()
        for item in items
        if item["command"] and not item["command"].startswith("<")
    ]
    if not command_rows:
        issues.append(Issue("E_REVIEW_COMMAND", "独立复核没有复跑任何命令", section[1]))
    elif a_ids and not any(
        set(parse_ac_ids(item["ac"])) & a_ids for item in command_rows
    ):
        issues.append(Issue("E_REVIEW_COMMAND", "至少要对一条 A 级证据复跑命令", section[1]))

    for row in rows:
        if row["reviewer"] and row["producer"] and row["reviewer"] == row["producer"]:
            issues.append(
                Issue(
                    "E_REVIEW_INDEPENDENT",
                    f"{row['id']} 的产出者与复核者是同一人“{row['producer']}”",
                    row["line"],
                )
            )


def read_structured_readings(value: str) -> dict[str, str]:
    """解析“viewport=1280x800;pixel_hash=...”这类结构化读数。"""
    result: dict[str, str] = {}
    for item in re.split(r"[;；]", value):
        if not item.strip():
            continue
        if "=" not in item:
            continue
        key, raw = item.split("=", 1)
        result[key.strip()] = raw.strip()
    return result


def check_evidence_identity(
    sections,
    rows: list[dict],
    batch_build: str,
    root: Path,
    ledger_dir: Path,
    issues: list[Issue],
) -> None:
    """核对证据身份表：SHA-256、字节数、构建、环境和结构化读数。"""
    section = find_section(sections, "证据身份")
    if section is None:
        return
    table = parse_first_table(section[2])
    if table is None:
        issues.append(Issue("E_ARTIFACT", "证据身份段没有表格", section[1]))
        return
    _, header, identity_rows = table
    normalized = [normalize_header(item) for item in header]
    indexes = {}
    for key, aliases in {
        "evidence": ("证据", "证据路径"),
        "sha256": ("sha-256", "sha256"),
        "bytes": ("字节数", "大小"),
        "build": ("构建号", "构建"),
        "environment": ("环境",),
        "time": ("取证时间", "时间"),
        "workspace": ("workspace_hash", "workspace hash", "工作区哈希"),
        "structured": ("结构化读数", "读数"),
    }.items():
        indexes[key] = next((i for i, item in enumerate(normalized) if item in aliases), None)
    missing = [key for key, index in indexes.items() if index is None]
    if missing:
        issues.append(Issue("E_ARTIFACT", "证据身份表头缺列：" + "、".join(missing), section[1]))
        return

    current_workspace = workspace_fingerprint(root, ledger_dir)
    registered: dict[Path, dict[str, str]] = {}
    for number, row in identity_rows:
        values = {key: cell(row, index).strip() for key, index in indexes.items()}
        if all(not value for value in values.values()):
            continue
        for candidate in extract_paths(values["evidence"]):
            resolved = resolve_existing_path(candidate, root, ledger_dir)
            if resolved is None:
                issues.append(Issue("E_ARTIFACT", f"证据身份登记了不存在的文件：{candidate}", number))
                continue
            registered[resolved] = values
            if not re.fullmatch(r"[0-9a-fA-F]{64}", values["sha256"]):
                issues.append(Issue("E_ARTIFACT_HASH", f"{candidate} 的 SHA-256 格式不对", number))
            else:
                actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
                if values["sha256"].lower() != actual:
                    issues.append(
                        Issue("E_ARTIFACT_HASH", f"{candidate} 的 SHA-256 与文件实际值不一致", number)
                    )
            if not values["bytes"].isdigit():
                issues.append(Issue("E_ARTIFACT_HASH", f"{candidate} 的字节数不是整数", number))
            elif int(values["bytes"]) != resolved.stat().st_size:
                issues.append(
                    Issue("E_ARTIFACT_HASH", f"{candidate} 的字节数与文件实际大小不一致", number)
                )
            if not values["build"] or (
                batch_build and values["build"] not in {batch_build, "同批次", "本批次"}
            ):
                issues.append(
                    Issue(
                        "E_ARTIFACT_BUILD",
                        f"{candidate} 的构建号“{values['build']}”与批次“{batch_build}”不一致",
                        number,
                    )
                )
            if not values["environment"]:
                issues.append(Issue("E_ARTIFACT_ENV", f"{candidate} 没有登记环境", number))
            if not V1_DATE_RE.fullmatch(values["time"]):
                issues.append(Issue("E_ARTIFACT", f"{candidate} 的取证时间不是 YYYY-MM-DD", number))
            if not re.fullmatch(r"[0-9a-fA-F]{64}", values["workspace"]):
                issues.append(
                    Issue("E_ARTIFACT_ENV", f"{candidate} 的 workspace_hash 不是 64 位哈希", number)
                )
            elif current_workspace is None:
                issues.append(
                    Issue("E_ARTIFACT_ENV", "无法计算当前工作区指纹，不能验证 workspace_hash", number)
                )
            elif values["workspace"].lower() != current_workspace:
                issues.append(
                    Issue(
                        "E_WORKSPACE_CHANGED",
                        f"{candidate} 的 workspace_hash 与当前工作区不一致：取证后文件已变化",
                        number,
                    )
                )

    for row in rows:
        if row["status"] == "未覆盖":
            continue
        for path in row["paths"]:
            if path not in registered:
                issues.append(
                    Issue(
                        "E_ARTIFACT_MISSING",
                        f"{row['id']} 的证据 {path.name} 没有在“证据身份”表登记",
                        row["line"],
                    )
                )
                continue
            values = registered[path]
            structured = read_structured_readings(values["structured"])
            required_keys = V1_STRUCTURED_KEYS.get(row["type"], ())
            missing_keys = [key for key in required_keys if not structured.get(key)]
            if missing_keys:
                issues.append(
                    Issue(
                        "E_ARTIFACT_STRUCTURE",
                        f"{row['id']} 的{row['type']}证据缺少结构化读数：{'、'.join(missing_keys)}",
                        row["line"],
                    )
                )
            if row["type"] in {"截图", "像素"}:
                expected_pixel = structured.get("pixel_hash", "")
                if expected_pixel and not re.fullmatch(r"[0-9a-fA-F]{64}", expected_pixel):
                    issues.append(
                        Issue("E_ARTIFACT_STRUCTURE", f"{row['id']} 的 pixel_hash 不是 64 位哈希", row["line"])
                    )
                for path in row["paths"]:
                    if path.suffix.lower() not in IMAGE_SUFFIXES:
                        continue
                    info = read_image_info(path)
                    if info is None:
                        issues.append(
                            Issue("E_SCREENSHOT", f"{row['id']} 的截图无法按 PNG/JPEG 头解析：{path.name}", row["line"])
                        )
                        continue
                    if structured.get("viewport"):
                        if not re.fullmatch(r"\d+x\d+", structured["viewport"]):
                            issues.append(
                                Issue("E_ARTIFACT_STRUCTURE", f"{row['id']} 的 viewport 应为 宽x高", row["line"])
                            )
                        elif structured["viewport"] != f"{info['width']}x{info['height']}":
                            issues.append(
                                Issue(
                                    "E_ARTIFACT_STRUCTURE",
                                    f"{row['id']} 的 viewport {structured['viewport']} 与图片实际 "
                                    f"{info['width']}x{info['height']} 不一致",
                                    row["line"],
                                )
                            )
                    if expected_pixel:
                        if info.get("pixel_hash") is None:
                            issues.append(
                                Issue(
                                    "E_ARTIFACT_STRUCTURE",
                                    f"{row['id']} 的图片格式无法验证 pixel_hash，不能据此判通过",
                                    row["line"],
                                )
                            )
                        elif expected_pixel.lower() != info["pixel_hash"]:
                            issues.append(
                                Issue("E_ARTIFACT_STRUCTURE", f"{row['id']} 的 pixel_hash 与图片实际像素不一致", row["line"])
                            )
            if row["type"] == "性能" and structured.get("runs"):
                if not structured["runs"].isdigit() or int(structured["runs"]) <= 0:
                    issues.append(
                        Issue("E_ARTIFACT_STRUCTURE", f"{row['id']} 的 runs 必须是正整数", row["line"])
                    )


def check_evidence_ownership(
    sections,
    batch_values: dict[str, str],
    root: Path,
    ledger_dir: Path,
    issues: list[Issue],
) -> None:
    """校验证据归属：先读协作模式，单代理要写说明，多代理必须登记到人。"""
    mode = batch_values.get("协作模式", "").strip()
    section = find_section_prefix(sections, "证据归属")
    if not mode:
        issues.append(Issue("E_EVIDENCE_OWNER", "批次信息缺少“协作模式”（单代理/多代理）"))
    elif mode not in {"单代理", "多代理"}:
        issues.append(Issue("E_EVIDENCE_OWNER", "协作模式只能是“单代理”或“多代理”"))
    if section is None:
        issues.append(
            Issue(
                "E_EVIDENCE_OWNER",
                "缺少“## 证据归属”段；单代理也要写明本批单代理，多代理必须给归属表",
            )
        )
        return
    text = "\n".join(line for _, line in section[2])
    table = parse_first_table(section[2])
    if table is None:
        if mode == "多代理":
            issues.append(
                Issue("E_EVIDENCE_OWNER", "多代理批次必须用表格登记 task_id/agent_id/claimed_at/证据路径", section[1])
            )
        elif "单代理" not in text:
            issues.append(Issue("E_EVIDENCE_OWNER", "单代理批次必须明确写“本批为单代理”", section[1]))
        return
    _, header, rows = table
    normalized = [normalize_header(item) for item in header]
    indexes = {}
    for key, aliases in {
        "task": ("task_id", "task id", "任务id"),
        "agent": ("agent_id", "agent id", "代理id", "执行者"),
        "claimed": ("claimed_at", "claimed at", "领取时间"),
        "evidence": ("证据路径", "证据", "evidence", "path"),
    }.items():
        indexes[key] = next((i for i, item in enumerate(normalized) if item in aliases), None)
    required = ["task", "agent", "claimed"]
    if mode == "多代理":
        required.append("evidence")
    missing = [key for key in required if indexes[key] is None]
    if missing:
        issues.append(Issue("E_EVIDENCE_OWNER", "证据归属表头缺列：" + "、".join(missing), section[1]))
        return
    seen_tasks: set[str] = set()
    for number, row in rows:
        values = {
            key: (cell(row, index).strip() if index is not None and index < len(row) else "")
            for key, index in indexes.items()
        }
        if all(not value for value in values.values()):
            continue
        empty = [key for key in required if not values[key] or values[key].startswith("<")]
        if empty:
            issues.append(Issue("E_EVIDENCE_OWNER", "证据归属行有空字段：" + "、".join(empty), number))
        if values["claimed"] and not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?", values["claimed"]
        ):
            issues.append(Issue("E_EVIDENCE_OWNER", "claimed_at 应为 YYYY-MM-DD 或 ISO 时间", number))
        if values["task"]:
            if values["task"] in seen_tasks:
                issues.append(Issue("E_EVIDENCE_OWNER", f"task_id 重复：{values['task']}", number))
            seen_tasks.add(values["task"])
        if mode == "多代理" and values["evidence"]:
            paths = extract_paths(values["evidence"])
            if not paths:
                issues.append(Issue("E_EVIDENCE_OWNER", "多代理归属行必须给证据路径", number))
            for candidate in paths:
                if resolve_existing_path(candidate, root, ledger_dir) is None:
                    issues.append(Issue("E_EVIDENCE_OWNER", f"归属证据不存在：{candidate}", number))
    if len(seen_tasks) > 1:
        issues.append(Issue("E_EVIDENCE_OWNER", "同一批次出现了多个 task_id", section[1]))
    if mode == "单代理" and not text.strip():
        issues.append(Issue("E_EVIDENCE_OWNER", "单代理批次也要写明证据归属说明", section[1]))


def check_rework_fields(
    batch_values: dict[str, str], issues: list[Issue], line: Optional[int]
) -> None:
    """校验结构化返工字段，禁止用全文词频猜返工次数。"""
    count_text = batch_values.get("返工次数", "").strip()
    reason = batch_values.get("返工原因", "").strip()
    task_id = batch_values.get("返工任务id", "").strip() or batch_values.get("返工任务 id", "").strip()
    missing = [name for name, value in (("返工次数", count_text), ("返工原因", reason), ("返工任务 ID", task_id)) if not value]
    if missing:
        issues.append(Issue("E_REWORK", "批次信息缺结构化返工字段：" + "、".join(missing), line))
        return
    if not count_text.isdigit():
        issues.append(Issue("E_REWORK", "返工次数必须是非负整数", line))
        return
    count = int(count_text)
    empty_words = {"无", "—", "-", "无返工", "没有"}
    if count == 0:
        if reason not in empty_words:
            issues.append(Issue("E_REWORK", "返工次数为 0 时，返工原因必须写“无”", line))
        if task_id not in empty_words:
            issues.append(Issue("E_REWORK", "返工次数为 0 时，返工任务 ID 必须写“无”", line))
    else:
        if reason in empty_words:
            issues.append(Issue("E_REWORK", "返工次数大于 0 时必须写明返工原因", line))
        if not re.fullmatch(r"t\d+[A-Za-z0-9_-]*", task_id):
            issues.append(Issue("E_REWORK", "返工次数大于 0 时返工任务 ID 必须形如 t5", line))


def check_blocking_form(
    ledger_dir: Path,
    rows: list[dict],
    issues: list[Issue],
) -> None:
    """校验阻塞举证单：四维尝试、正对照和解锁条件。"""
    blocked = [row for row in rows if row["status"] == "未交付-阻塞"]
    if not blocked:
        return
    form = ledger_dir / "blocking-form.md"
    if not form.exists():
        issues.append(Issue("E_BLOCKING_FORM", "有阻塞行但没有 blocking-form.md", blocked[0]["line"]))
        return
    text = form.read_text(encoding="utf-8")
    sections = split_sections(text)
    required_prefixes = ("1.", "2.", "3.", "4.", "5.", "6.", "7.")
    for prefix in required_prefixes:
        if find_section_prefix(sections, prefix) is None:
            issues.append(Issue("E_BLOCKING_FORM", f"阻塞举证单缺少第 {prefix} 节", None))
    point = find_section_prefix(sections, "1.")
    if point is not None:
        values, _ = table_key_values(point)
        if not values.get("卡点") or not values.get("现象"):
            issues.append(Issue("E_BLOCKING_FORM", "阻塞举证单的卡点/现象为空", point[1]))
    positive = find_section_prefix(sections, "3.")
    if positive is not None:
        table = parse_first_table(positive[2])
        ok = False
        if table is not None:
            _, header, positive_rows = table
            normalized = [normalize_header(item) for item in header]
            result_index = next(
                (i for i, item in enumerate(normalized) if item in {"结果", "正对照结果"}), None
            )
            for _, row in positive_rows:
                value = cell(row, result_index).strip() if result_index is not None else ""
                if "通过" in value:
                    ok = True
        if not ok:
            issues.append(Issue("E_BLOCKING_FORM", "阻塞举证单没有正对照通过记录", positive[1]))
    attempts = find_section_prefix(sections, "4.")
    if attempts is not None:
        table = parse_first_table(attempts[2])
        dimensions: dict[str, bool] = {}
        if table is not None:
            _, header, attempt_rows = table
            normalized = [normalize_header(item) for item in header]
            dim_index = next((i for i, item in enumerate(normalized) if "维度" in item), None)
            excluded_index = next(
                (i for i, item in enumerate(normalized) if "排除" in item), None
            )
            for _, row in attempt_rows:
                dim = cell(row, dim_index).strip() if dim_index is not None else ""
                excluded = cell(row, excluded_index).strip() if excluded_index is not None else ""
                if dim:
                    filled = all(item.strip() and not item.strip().startswith("<") for item in row)
                    dimensions[dim] = filled and excluded in {"是", "已排除"}
        for name in ("环境", "注入通道", "判据", "数据"):
            if not dimensions.get(name):
                issues.append(
                    Issue("E_BLOCKING_FORM", f"阻塞举证单四维中的“{name}”没有完整尝试记录", attempts[1])
                )
    unlock = find_section_prefix(sections, "7.")
    if unlock is not None:
        bullets = [
            line.strip()[1:].strip()
            for _, line in unlock[2]
            if line.strip().startswith("-")
        ]
        bullets = [item for item in bullets if item and not item.startswith("<")]
        if len(bullets) < 4:
            issues.append(
                Issue("E_BLOCKING_FORM", "解锁条件至少写清谁提供什么、如何复验、判据、影响", unlock[1])
            )


def check_v1_ledger(
    path: Path,
    root: Path,
    text: str,
    sections,
    policy: Optional[LedgerPolicy] = None,
    strict: bool = False,
) -> tuple[list[Issue], dict[str, int], str]:
    """检查项目 v1/v2 账本。

    v2 在早期十列基础上增加“覆盖 AC、证据等级、复核者”三列，并要求
    用户旅程、证据身份、完成审计、独立复核、阻塞举证等段齐全。字段、
    枚举、证据路径、commit 真实性和证据时效仍按同一套底线检查，
    避免项目模板绕过通用校验器。
    """
    current_policy = policy or LedgerPolicy()
    issues: list[Issue] = []
    status_counts: Counter[str] = Counter()
    debt_lines: list[int] = []
    conclusion = ""
    conclusion_line: Optional[int] = None

    for name in V1_REQUIRED_SECTIONS:
        if find_section(sections, name) is None:
            issues.append(Issue("E_STRUCTURE", f"缺少“## {name}”段"))

    batch_values, batch_lines, batch_start = parse_batch_values(sections)
    if batch_start is None:
        issues.append(Issue("E_BATCH_INFO", "缺少“## 批次信息”段"))
    else:
        schema_version = batch_values.get("schema_version", "").strip()
        if schema_version != "2":
            issues.append(
                Issue(
                    "E_SCHEMA",
                    f"账本 schema_version 必须是 2（当前 {schema_version or '缺失'}）；旧账本先运行 "
                    "python3 scripts/verity.py upgrade <07>",
                    batch_start,
                )
            )
        for name in (
            "任务卡", "被测版本", "环境", "执行者", "复核者", "收口时间", "生成日期",
            "协作模式", "返工次数", "返工原因", "返工任务 ID",
        ):
            value = batch_values.get(normalize_header(name), "").strip()
            if v1_text_empty(value):
                issues.append(Issue("E_BATCH_INFO", f"批次信息“{name}”未填写", batch_start))
        for name in ("收口时间", "生成日期"):
            value = batch_values.get(normalize_header(name), "").strip()
            if value and not V1_DATE_RE.fullmatch(value):
                issues.append(Issue("E_BATCH_INFO", f"批次信息“{name}”不是 YYYY-MM-DD", batch_start))
        check_rework_fields(batch_values, issues, batch_start)

    build_text = batch_values.get("被测版本", "")
    build_match = re.search(r"构建号[:：]\s*([^；;，,\s]+)", build_text)
    batch_build = build_match.group(1).strip() if build_match else ""
    commit_match = re.search(r"commit[:：]\s*([0-9a-fA-F]{7,40})", build_text)
    batch_commit = commit_match.group(1).lower() if commit_match else ""
    if batch_commit:
        changed, changed_error = git_changed_paths(root, batch_commit)
        if changed_error:
            issues.append(
                Issue(
                    "E_STALE_EVIDENCE",
                    f"无法确认证据提交 {batch_commit[:12]} 到 HEAD 的差异：{changed_error}；"
                    "旧证据不能继续作为最终提交的验收依据",
                    batch_start,
                )
            )
        else:
            stale_paths = stale_implementation_changes(changed, project_prefix(root))
            if stale_paths:
                preview = "、".join(stale_paths[:5])
                more = f" 等 {len(stale_paths)} 个文件" if len(stale_paths) > 5 else ""
                issues.append(
                    Issue(
                        "E_STALE_EVIDENCE",
                        f"证据绑定 commit {batch_commit[:12]}，但之后到 HEAD 又改过实现/规则文件："
                        f"{preview}{more}；必须按最终提交重新取证",
                        batch_start,
                    )
                )
    environment = batch_values.get("环境", "")
    is_release = "release" in environment.lower() or "发布" in environment
    if is_release:
        for name in V1_RELEASE_SECTIONS:
            if find_section(sections, name) is None:
                issues.append(Issue("E_RELEASE_SECTION", f"发布批次缺少“## {name}”段"))

    card_path, acs, _, risk, hard_trigger = check_task_card(path.parent, batch_values, issues)
    journey_passed = False

    package = find_section(sections, "包结论")
    if package is not None:
        package_text = "\n".join(line for _, line in package[2])
        conclusion, conclusion_line = v1_conclusion_value(package_text)
        if not conclusion:
            issues.append(Issue("E_FIELD", "包结论的交付结论为空", conclusion_line or package[1]))
        elif normalize_conclusion(conclusion) not in current_policy.conclusions:
            issues.append(
                Issue(
                    "E_CONCLUSION",
                    f"交付结论“{conclusion}”只能是：{' / '.join(current_policy.conclusions)}",
                    conclusion_line,
                )
            )
        for label in ("一句话说明", "证据索引"):
            match = re.search(label + r"[:：]\s*(.+)", package_text)
            value = match.group(1).strip() if match else ""
            if v1_text_empty(value):
                issues.append(Issue("E_FIELD", f"包结论的“{label}”为空", package[1]))
        journey_match = re.search(r"旅程结论[:：]\s*.*?(通过|未通过|阻塞|未覆盖)", package_text)
        journey_value = journey_match.group(1).strip() if journey_match else ""
        if not journey_value or v1_text_empty(journey_value):
            issues.append(Issue("E_FIELD", "包结论的“旅程结论”为空", package[1]))
        elif journey_value != "通过":
            issues.append(
                Issue("E_JOURNEY_NOT_PASSED", f"包结论写明旅程结论“{journey_value}”，不得判通过", package[1])
            )

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
    row_records: list[dict] = []
    image_uses: dict[Path, int] = {}
    for number, row in rows:
        if len(row) != len(header):
            issues.append(
                Issue(
                    "E_COLUMNS",
                    f"该行有 {len(row)} 列，表头有 {len(header)} 列；一行必须完整对应十三列",
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
            # 但 AC 映射、产出者和复核者仍必须写清楚。
            if key in {"id", "status"}:
                continue
            if status == "未覆盖" and key in {
                "evidence_type",
                "evidence",
                "level",
                "confidence",
                "time",
                "commit",
            }:
                continue
            if v1_value_empty(values[key]):
                issues.append(Issue("E_FIELD", f"{V1_DISPLAY_COLUMNS[key]}为空", number))

        covers = parse_ac_ids(values["covers"])
        if not covers:
            issues.append(
                Issue("E_COVERS", f"{item_id or '该行'} 没有填写覆盖的 AC（如 AC-01）", number)
            )

        evidence_type = values["evidence_type"]
        if (
            status != "未覆盖"
            and evidence_type
            and not v1_value_empty(evidence_type)
            and evidence_type not in current_policy.evidence_types
        ):
            issues.append(
                Issue(
                    "E_EVIDENCE_TYPE",
                    f"证据类型“{evidence_type}”只能是：{'/'.join(current_policy.evidence_types)}",
                    number,
                )
            )

        level = values["level"].strip()
        if status != "未覆盖" and level and level not in V1_LEVELS:
            issues.append(Issue("E_LEVEL", f"证据等级“{level}”只能是 A/B+/B/C", number))

        confidence = values["confidence"]
        if (
            status != "未覆盖"
            and confidence
            and not v1_value_empty(confidence)
            and confidence not in current_policy.confidences
        ):
            issues.append(
                Issue(
                    "E_CONFIDENCE",
                    f"置信度“{confidence}”只能是：{'/'.join(current_policy.confidences)}",
                    number,
                )
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
        commit_date: Optional[date] = None
        if status != "未覆盖" and commit and not v1_value_empty(commit):
            if not V1_COMMIT_RE.fullmatch(commit):
                issues.append(
                    Issue("E_COMMIT", f"commit“{commit}”不是 7-40 位哈希；最终验收必须绑定真实提交", number)
                )
            else:
                commit_date, commit_error = git_commit_date(root, commit)
                if commit_error:
                    issues.append(
                        Issue(
                            "E_COMMIT",
                            f"commit“{commit}”无法校验：{commit_error}",
                            number,
                        )
                    )
                else:
                    ancestor, ancestor_error = git_is_ancestor(root, commit)
                    if ancestor_error:
                        issues.append(Issue("E_COMMIT", f"commit“{commit}”无法校验：{ancestor_error}", number))
                    elif not ancestor:
                        issues.append(
                            Issue(
                                "E_COMMIT",
                                f"commit“{commit}”不是 HEAD 或 HEAD 的祖先，不能用旧提交当本批锚点",
                                number,
                            )
                        )
                    elif batch_commit and not (
                        commit.lower() == batch_commit
                        or batch_commit.startswith(commit.lower())
                    ):
                        issues.append(
                            Issue(
                                "E_COMMIT",
                                f"行 commit“{commit[:12]}”与批次被测 commit“{batch_commit[:12]}”不一致；"
                                "最终验收必须统一绑定同一个提交",
                                number,
                            )
                        )

        if v1_value_empty(status):
            issues.append(Issue("E_FIELD", "状态为空", number))
        elif status not in current_policy.statuses:
            issues.append(
                Issue(
                    "E_STATUS",
                    f"状态“{status}”不在允许枚举内（{'/'.join(current_policy.statuses)}）",
                    number,
                )
            )
        else:
            status_counts[status] += 1
            if status == "带欠账":
                debt_lines.append(number)

        producer = values["producer"].strip()
        reviewer = values["reviewer"].strip()
        if producer and reviewer and producer == reviewer:
            issues.append(
                Issue("E_REVIEW_INDEPENDENT", f"{item_id or '该行'} 的产出者与复核者是同一人", number)
            )

        evidence_paths: list[Path] = []
        # 除“未覆盖”外，每种状态都必须给证据；状态本身允许“未交付”，
        # 但“没证据的失败/阻塞”无法复核，仍按缺证据拒绝。
        if status != "未覆盖":
            evidence = values["evidence"]
            if v1_value_empty(evidence) or evidence_is_empty(evidence):
                issues.append(
                    Issue("E_MISSING_EVIDENCE", f"{item_id or '该行'}（{status}）的证据列为空", number)
                )
            else:
                for candidate in extract_paths(evidence):
                    resolved_path = resolve_existing_path(candidate, root, ledger_dir)
                    if resolved_path is None:
                        issues.append(
                            Issue(
                                "E_EVIDENCE_PATH",
                                f"证据文件不存在：{candidate}（已查 {root} 与 {ledger_dir}）",
                                number,
                            )
                        )
                        continue
                    evidence_paths.append(resolved_path)
                    if resolved_path.suffix.lower() in IMAGE_SUFFIXES:
                        previous = image_uses.get(resolved_path)
                        if previous is not None:
                            issues.append(
                                Issue(
                                    "E_EVIDENCE_REUSED",
                                    f"同一张截图被第 {previous} 行和本行重复使用：{candidate}",
                                    number,
                                )
                            )
                        else:
                            image_uses[resolved_path] = number
                    else:
                        try:
                            head = resolved_path.read_bytes()[:4096].decode("utf-8", "ignore").strip()
                        except OSError:
                            head = ""
                        lowered = head.lower()
                        if (
                            not head
                            or re.fullmatch(r"<.*>", head, re.S)
                            or lowered in {"todo", "tbd", "待补", "待取证", "见截图", "示例"}
                            or head.startswith("TODO")
                        ):
                            issues.append(
                                Issue(
                                    "E_FAKE_EVIDENCE",
                                    f"{item_id or '该行'} 的证据文件只有占位内容：{candidate}",
                                    number,
                                )
                            )

                # 截图不是“写一句见截图”就算数：必须能解析出一张真实、
                # 非空的图片文件；这条对所有状态生效，失败/阻塞也不能用文字冒充。
                if evidence_type == "截图" and not has_readable_image(evidence, root, ledger_dir):
                    issues.append(
                        Issue(
                            "E_SCREENSHOT",
                            f"{item_id or '该行'} 的证据类型是截图，但没有可读的截图文件",
                            number,
                        )
                    )

                # 证据自述里的“只跑主路径”“门禁全绿没跑探针”“设备未验”
                # 本身就是覆盖缺口，不能靠状态栏写“通过”掩盖。
                issues.extend(self_report_gap_issues(evidence, status, item_id, number))

                # 旧证据不能复用：证据日期和文件 mtime 都不能早于 commit 日期。
                # 同一天内不按小时卡，避免“上午产出证据、下午提交基线”的正常流程误报。
                if commit_date is not None:
                    row_date: Optional[date] = None
                    if V1_DATE_RE.fullmatch(time_value):
                        try:
                            row_date = date.fromisoformat(time_value)
                        except ValueError:
                            row_date = None
                    if row_date is not None and row_date < commit_date:
                        issues.append(
                            Issue(
                                "E_STALE",
                                f"证据日期 {row_date} 早于 commit 日期 {commit_date}，不能复用旧证据",
                                number,
                            )
                        )
                    for evidence_path in evidence_paths:
                        try:
                            file_date = datetime.fromtimestamp(evidence_path.stat().st_mtime).date()
                        except OSError as error:
                            issues.append(
                                Issue(
                                    "E_EVIDENCE_PATH",
                                    f"无法读取证据文件时间：{evidence_path}（{error}）",
                                    number,
                                )
                            )
                            continue
                        if file_date < commit_date:
                            issues.append(
                                Issue(
                                    "E_STALE",
                                    f"证据文件 mtime {file_date} 早于 commit 日期 {commit_date}，"
                                    f"不能复用旧证据：{evidence_path}",
                                    number,
                                )
                            )

        row_records.append(
            {
                "id": item_id,
                "covers": covers,
                "status": status,
                "type": evidence_type,
                "level": level,
                "producer": producer,
                "reviewer": reviewer,
                "time": time_value,
                "commit": commit,
                "user_path": values["user_path"],
                "paths": evidence_paths,
                "line": number,
            }
        )

    # 账本行必须覆盖任务卡的全部 AC；只写“AC-01”却漏掉 AC-02 不能算通过。
    expected_acs = {ac_id for ac_id, _, _ in acs}
    covered_acs = {ac_id for row in row_records for ac_id in row["covers"]}
    unknown = sorted(covered_acs - expected_acs)
    if unknown:
        issues.append(
            Issue("E_COVERS", "账本引用了任务卡里不存在的 AC：" + "、".join(unknown), ledger_section[1])
        )
    uncovered_acs = sorted(expected_acs - covered_acs)
    if uncovered_acs:
        issues.append(
            Issue("E_COVERS", "任务卡 AC 没有被账本行覆盖：" + "、".join(uncovered_acs), ledger_section[1])
        )

    # 旅程步骤映射需要完整的行记录，放在行循环之后补一次。
    journey_ok = check_journey_section(path.parent, sections, row_records, risk, hard_trigger, issues)
    if journey_passed != journey_ok:
        journey_passed = journey_ok

    check_evidence_identity(sections, row_records, batch_build, root, ledger_dir, issues)
    check_completion_audit(sections, acs, batch_build, root, ledger_dir, issues)
    check_independent_review(sections, acs, row_records, batch_values, root, ledger_dir, issues)
    check_blocking_form(ledger_dir, row_records, issues)
    check_evidence_ownership(sections, batch_values, root, ledger_dir, issues)

    # 任务卡在取证之后又被改动，说明判据变了，旧证据随之失效。
    if card_path is not None and card_path.exists():
        dirty, _ = git_path_dirty(root, card_path)
        if dirty:
            try:
                card_date = datetime.fromtimestamp(card_path.stat().st_mtime).date()
            except OSError:
                card_date = None
            if card_date is not None:
                for row in row_records:
                    if V1_DATE_RE.fullmatch(row["time"]):
                        try:
                            row_date = date.fromisoformat(row["time"])
                        except ValueError:
                            continue
                        if card_date > row_date:
                            issues.append(
                                Issue(
                                    "E_STALE_TASKCARD",
                                    f"任务卡在证据日期 {row_date} 之后又改过，旧证据失效",
                                    row["line"],
                                )
                            )
                            break

    # 包结论必须和账本状态一致；空结论已在包结论段报过缺字段。
    if conclusion:
        expected = expected_v1_conclusion(
            list(status_counts.elements()), current_policy, journey_passed
        )
        if expected and normalize_conclusion(conclusion) != expected:
            issues.append(
                Issue(
                    "E_CONCLUSION",
                    f"账本状态推出交付结论应为“{expected}”，实际写“{conclusion}”",
                    conclusion_line,
                )
            )

    # strict 用于发版前卡口：带欠账一律不放行，不管它写成了状态还是包结论。
    if strict and (
        status_counts.get("带欠账", 0)
        or normalize_conclusion(conclusion) == "带欠账交付"
    ):
        issues.append(
            Issue(
                "E_STRICT_DEBT",
                "strict 模式拒绝带欠账：请补齐欠账证据或把结论改为未交付",
                debt_lines[0] if debt_lines else conclusion_line,
            )
        )

    return issues, dict(status_counts), conclusion


def check_ledger(
    path: Path,
    root: Path,
    forced_format: str = "auto",
    policy: Optional[LedgerPolicy] = None,
    strict: bool = False,
) -> tuple[list[Issue], dict[str, int], str]:
    """执行全部检查，返回 (问题列表, 状态计数, 收口/包结论)。

    forced_format：auto 按 marker 判断；legacy 强制八列；v1 强制项目十三列。
    policy 决定 v1 允许状态/结论/证据类型/置信度；strict 额外拒绝带欠账。
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
        v1_issues, v1_counts, v1_conclusion = check_v1_ledger(
            path, root, text, sections, policy, strict
        )
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


@dataclass(frozen=True)
class AdapterContext:
    """适配层对账本检查的影响：项目根、默认格式和允许枚举。"""

    project_root: Path
    format: str
    policy: LedgerPolicy


def read_policy(data: dict) -> LedgerPolicy:
    """读取 adapter.ledger 枚举块；未配置时用通用五状态。

    枚举只能从 verity 已支持的值里取子集，不允许项目自造状态名；否则
    “错别字”会被配置固化成规范。空列表视为配置错误。
    """
    raw = data.get("ledger")
    if raw is None:
        return LedgerPolicy()
    if not isinstance(raw, dict):
        raise ValueError("适配层 ledger 必须是对象")

    def pick(key: str, default: tuple[str, ...], normalize: bool = False) -> tuple[str, ...]:
        value = raw.get(key)
        if value is None:
            return default
        if not isinstance(value, list) or not value or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            raise ValueError(f"适配层 ledger.{key} 必须是非空字符串数组")
        items = tuple(
            normalize_conclusion(item) if normalize else item.strip()
            for item in value
        )
        allowed = tuple(
            normalize_conclusion(item) if normalize else item for item in default
        )
        invalid = [item for item in items if item not in allowed]
        if invalid:
            raise ValueError(
                f"适配层 ledger.{key} 含未支持取值：{'、'.join(invalid)}；"
                f"只能是：{'/'.join(allowed)}"
            )
        # 去重但保持配置顺序，避免重复枚举让报错信息变长。
        return tuple(dict.fromkeys(items))

    return LedgerPolicy(
        statuses=pick("statuses", V1_STATUSES),
        conclusions=pick("conclusions", V1_CONCLUSIONS, normalize=True),
        evidence_types=pick("evidence_types", V1_EVIDENCE_TYPES),
        confidences=pick("confidences", V1_CONFIDENCES),
    )


def adapter_context(adapter_path: Path) -> AdapterContext:
    """读取适配层的项目根、账本格式和允许枚举。

    项目根按 adapter 所在目录解析 project.root；项目模板含 v1 marker 时
    默认格式为 v1，否则沿用通用八列。显式 --format 仍可覆盖格式判断，
    但枚举只由适配层决定，避免 CLI 参数绕过项目合同。
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
    # 没配置项目模板时按 v1/v2 处理：init 生成的就是带 marker 的新账本，
    # 只有显式 --format legacy 才回退八列，避免适配层缺省值把新账本当旧账本读。
    fmt = "v1"
    if isinstance(raw_template, str) and raw_template.strip() and not (
        raw_template.strip().startswith("<") and raw_template.strip().endswith(">")
    ):
        template = (project_root / raw_template.strip()).resolve()
        if not template.is_file():
            raise ValueError(f"适配层 paths.ledger_template 指向的模板不存在：{template}")
        if V1_MARKER not in template.read_text(encoding="utf-8"):
            fmt = "legacy"
    return AdapterContext(project_root=project_root, format=fmt, policy=read_policy(data))


def render_summary(path: Path, counts: dict[str, int], conclusion: str) -> str:
    """输出一行人类可读的通过摘要。"""
    ordered = V1_STATUSES + tuple(status for status in STATUSES if status not in V1_STATUSES)
    parts = [f"{status} {counts[status]}" for status in ordered if counts.get(status)]
    detail = " / ".join(parts) if parts else "无验收项"
    return f"[OK] {path}：{sum(counts.values())} 行，结论={conclusion or '未写'}（{detail}）"


def read_evidence_commands(adapter_path: Path) -> dict[str, str]:
    """读取适配层的 evidence_commands 白名单。

    支持对象形式 {"EV-01": {"command": "..."}} 和数组形式
    [{"id": "EV-01", "command": "..."}]；只允许 EV-数字 ID。
    """
    try:
        data = json.loads(adapter_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"无法读取适配层：{error}") from error
    raw = data.get("evidence_commands") if isinstance(data, dict) else None
    if raw is None:
        return {}
    commands: dict[str, str] = {}
    if isinstance(raw, dict):
        items = raw.items()
        for key, value in items:
            command = value.get("command") if isinstance(value, dict) else value
            if not isinstance(command, str) or not command.strip():
                raise ValueError(f"evidence_commands.{key} 缺少 command")
            commands[str(key)] = command.strip()
    elif isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("evidence_commands 数组项必须是对象")
            key = str(item.get("id", "")).strip()
            command = item.get("command")
            if not key or not isinstance(command, str) or not command.strip():
                raise ValueError("evidence_commands 数组项必须有 id 和 command")
            commands[key] = command.strip()
    else:
        raise ValueError("evidence_commands 必须是对象或数组")
    invalid = [key for key in commands if not re.fullmatch(r"EV-\d{2,3}", key)]
    if invalid:
        raise ValueError("evidence_commands 的 ID 必须是 EV-01 形式：" + "、".join(invalid))
    return commands


def _extract_clean_worktree(root: Path):
    """把 HEAD 导出到临时目录，证据命令在干净树上执行。"""
    temporary = tempfile.TemporaryDirectory(prefix="verity-evidence-")
    target = Path(temporary.name)
    archive = subprocess.run(
        ["git", "-C", str(root), "archive", "--format=tar", "HEAD"],
        capture_output=True,
        check=False,
    )
    if archive.returncode == 0:
        with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as bundle:
            bundle.extractall(target, filter="data")
    else:
        # 非 git 项目退化为复制工作区，但仍排除版本库与构建产物。
        shutil.copytree(
            root,
            target,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "dist", "__pycache__", "*.pyc"),
        )
    return temporary, target


def run_evidence_commands(
    path: Path,
    root: Path,
    adapter_path: Optional[Path],
    issues: list[Issue],
    timeout: int = 120,
) -> None:
    """按 EV ID 执行适配层白名单命令，并把可复核的执行记录写入 ev-runs.log。

    记录使用 JSON Lines，保留时间、HEAD、EV ID、命令、退出码、输出摘要
    和输出 SHA-256。已有同 EV、同命令、exit=0 的记录时直接复用，避免每次
    gate 重跑都改写证据包；复核检查只认这些记录，不执行任意命令。
    """
    if adapter_path is None:
        issues.append(Issue("E_EVIDENCE_COMMAND", "启用 --run 时必须提供适配层 evidence_commands"))
        return
    try:
        commands = read_evidence_commands(adapter_path)
    except ValueError as error:
        issues.append(Issue("E_EVIDENCE_COMMAND", str(error)))
        return
    if not commands:
        issues.append(Issue("E_EVIDENCE_COMMAND", "适配层没有配置 evidence_commands 白名单"))
        return
    text = path.read_text(encoding="utf-8")
    sections = split_sections(text)
    section = find_section(sections, "单项验收（证据账本）")
    if section is None:
        return
    table = parse_first_table(section[2])
    if table is None:
        return
    _, header, rows = table
    columns = resolve_v1_columns(header)
    referenced: list[str] = []
    for number, row in rows:
        status = cell(row, columns.get("status")).strip()
        evidence = cell(row, columns.get("evidence"))
        if status == "未覆盖":
            continue
        ids = re.findall(r"EV-\d{2,3}", evidence)
        if not ids:
            issues.append(
                Issue("E_EVIDENCE_COMMAND", "启用 --run 时，每行证据必须标注 EV ID（如 EV-01）", number)
            )
            continue
        referenced.extend(ids)
    missing = sorted(set(referenced) - set(commands))
    if missing:
        issues.append(Issue("E_EVIDENCE_COMMAND", "账本引用了未登记的命令：" + "、".join(missing)))
        return
    if not referenced:
        issues.append(Issue("E_EVIDENCE_COMMAND", "账本没有引用任何 EV ID"))
        return
    evidence_dir = path.parent / "evidence"
    log_path = evidence_dir / "ev-runs.log"
    existing_records, log_errors = _load_ev_records(log_path)
    if log_errors:
        # 旧格式或损坏记录无法被复核校验，要求先清理后再执行。
        issues.append(Issue("E_EVIDENCE_COMMAND", "；".join(log_errors)))
        return
    temporary, worktree = _extract_clean_worktree(root)
    new_records: list[dict] = []
    try:
        for evidence_id in sorted(set(referenced)):
            command = commands[evidence_id]
            reusable = next(
                (
                    item
                    for item in reversed(existing_records)
                    if str(item.get("ev", "")) == evidence_id
                    and str(item.get("command", "")) == command
                    and str(item.get("exit", "")) == "0"
                    and str(item.get("output_sha256", ""))
                ),
                None,
            )
            if reusable is not None:
                print(f"[OK] {evidence_id} 复用已有执行记录：{command}")
                continue
            try:
                process = subprocess.run(
                    command,
                    shell=True,
                    cwd=worktree,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                issues.append(
                    Issue("E_EVIDENCE_COMMAND", f"{evidence_id} 命令执行失败：{error}")
                )
                continue
            lines = (process.stdout + process.stderr).strip().splitlines()
            tail = " | ".join(lines[-3:]) if lines else "无输出"
            summary = lines[-1] if lines else "无输出"
            timestamp = datetime.now().isoformat(timespec="seconds")
            head = _git_head(root)
            record = {
                "time": timestamp,
                "head": head,
                "ev": evidence_id,
                "command": command,
                "exit": process.returncode,
                "output": tail,
                "output_sha256": hashlib.sha256(tail.encode("utf-8")).hexdigest(),
                "summary": summary,
            }
            if process.returncode != 0:
                issues.append(
                    Issue(
                        "E_EVIDENCE_COMMAND",
                        f"{evidence_id} 退出码 {process.returncode}：{command}；输出：{tail}",
                    )
                )
            else:
                print(f"[OK] {evidence_id} 退出码 0：{command}；输出：{tail}")
            new_records.append(record)
    finally:
        temporary.cleanup()
    if new_records:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            for record in new_records:
                stable_parts = (record["ev"], record["command"], record["exit"])
                duplicate = any(
                    (str(item.get("ev", "")), str(item.get("command", "")), str(item.get("exit", "")))
                    == stable_parts
                    for item in existing_records
                )
                if duplicate:
                    continue
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                existing_records.append(record)


def _git_head(root: Path) -> str:
    """取当前 HEAD；不在 git 仓库时返回 unknown。"""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except OSError:
        return "unknown"


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
        help="账本格式：auto 按 marker 判断（默认），legacy 八列，v1 项目十三列",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果，便于 CI 消费")
    parser.add_argument(
        "--compat-debt",
        action="store_true",
        help="仅为读取历史账本，允许“带欠账”状态或“带欠账交付”结论；新账本不要使用",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="严格模式：拒绝任何“带欠账”状态或“带欠账交付”结论（默认已拒绝，保留用于显式卡口）",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="按账本中的 EV ID 执行适配层 evidence_commands 白名单命令（在 HEAD 干净树中运行）",
    )
    parser.add_argument("--timeout", type=int, default=120, help="单条证据命令超时秒数，默认 120")
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
    policy = LedgerPolicy()
    adapter_file: Optional[Path] = None
    if args.adapter:
        adapter_path = Path(args.adapter).expanduser()
        if not adapter_path.is_file():
            print(f"用法错误：适配层不存在或不是文件：{adapter_path}", file=sys.stderr)
            return 2
        try:
            context = adapter_context(adapter_path.resolve())
        except ValueError as error:
            print(f"用法错误：{error}", file=sys.stderr)
            return 2
        adapter_root = context.project_root
        adapter_format = context.format
        policy = context.policy
        adapter_file = adapter_path.resolve()
    elif args.compat_debt:
        # 只有未指定项目适配层时才允许松开；项目适配层自己的枚举优先。
        policy = LedgerPolicy(statuses=V1_STATUSES, conclusions=V1_CONCLUSIONS)

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

    if args.run and adapter_file is None:
        for parent in (resolved.parent, *resolved.parent.parents):
            for name in (".verity/adapter.json", "verity-适配层.json", "verity-adapter.json", "adapter.json"):
                candidate = parent / name
                if candidate.is_file():
                    adapter_file = candidate.resolve()
                    break
            if adapter_file is not None:
                break
        if adapter_file is None:
            print("用法错误：--run 需要适配层（.verity/adapter.json 或 --adapter）", file=sys.stderr)
            return 2

    forced_format = args.format if args.format != "auto" else adapter_format
    issues, counts, conclusion = check_ledger(
        resolved, root, forced_format, policy=policy, strict=args.strict
    )
    if args.run:
        run_evidence_commands(resolved, root, adapter_file, issues, timeout=args.timeout)
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity != "error"]

    if args.json:
        payload = {
            "ledger": str(resolved),
            "ok": not errors,
            "conclusion": conclusion,
            "counts": counts,
            "strict": args.strict,
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
