#!/usr/bin/env python3
"""verity 技能包打包检查与 zip 生成。

规则：产品载荷（入口说明、规则、模板、脚本）与工程资产（文档、示例、
测试与协作文件）分开计数；产品超限直接报错，资料超软上限只提醒，总数或
总体积超限仍然报错，避免仓库无界膨胀。

优先用 `git ls-files` 取“已跟踪 + 未忽略”的文件，保证 .gitignore 里
的私有材料、凭据和构建产物不会被打进包；在没有 git 的目录里退回文件系统
遍历，并套用同一组排除规则。

只使用 Python 标准库。退出码：0 = 已生成（或 --check 通过）；1 = 超限或
打包失败；2 = 参数错误。
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

# 产品载荷是 AI 客户端真正加载的内容；其余算工程资产。
PAYLOAD_FILES = {"SKILL.md"}
PAYLOAD_PREFIXES = ("references/", "templates/", "scripts/")

DEFAULT_MAX_PAYLOAD_FILES = 30
DEFAULT_MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_AUX_FILES = 45
DEFAULT_MAX_AUX_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_FILES = 80
DEFAULT_MAX_BYTES = 10 * 1024 * 1024

# 无 git 时的目录排除表；与 .gitignore 的意图保持一致。
EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "dist",
    "build",
    "tmp",
    "private",
    ".local",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
}
EXCLUDED_NAMES = {".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".zip"}
EXCLUDED_PATTERNS = ("*.local.*", "*.secret", "*.pem", "*.key")
# 分析记录不是技能交付物：它引用外部仓库、体量大且会随调研变化，不进技能包。
EXCLUDED_RELATIVE_PATTERNS = (
    "docs/2026-*外部工作流对比与优化清单.md",
    "docs/2026-11-16-验收流程优化-目标与执行计划.md",
    "docs/2026-11-16-验收流程优化/*",
    "docs/reviews/32-item-review*.md",
    "docs/reviews/32-item-verification*.md",
    "tests/fixtures/*",
    "docs/reviews/2026-11-06-independent-review.md",
    "docs/reviews/clean-clone.md",
    "docs/reviews/anti-examples.md",
    ".github/ISSUE_TEMPLATE/*",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    ".github/pull_request_template.md",
    ".github/dependabot.yml",
    "examples/01-new-feature/bad-main-path/*",
    "examples/02-bug-fix/bad-old-evidence/*",
    "examples/04-project-v1/bad-fake-screenshot/*",
    "examples/05-release/bad-gate-only/*",
    "examples/04-project-v1/manifest.json",
    "examples/05-release/evidence/ev-runs.log",
    "examples/01-new-feature/README.md",
)


def human_size(size: int) -> str:
    """把字节数转成便于阅读的单位。"""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def git_file_list(root: Path) -> Optional[list[Path]]:
    """用 git 列出交付文件；不是 git 仓库或 git 不可用时返回 None。"""
    if not (root / ".git").exists():
        return None
    try:
        process = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            capture_output=True,
            check=False,
        )
    except (OSError, ValueError):
        return None
    if process.returncode != 0:
        return None

    files: list[Path] = []
    for raw in process.stdout.split(b"\x00"):
        if not raw:
            continue
        relative = Path(os.fsdecode(raw))
        absolute = root / relative
        if absolute.is_file():
            files.append(absolute)
    return files


def walk_file_list(root: Path) -> list[Path]:
    """无 git 时的文件系统遍历；跳过缓存、依赖、私有目录和构建产物。"""
    files: list[Path] = []
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name for name in dirnames if name not in EXCLUDED_DIRS
        )
        for name in sorted(filenames):
            if name in EXCLUDED_NAMES:
                continue
            if Path(name).suffix.lower() in EXCLUDED_SUFFIXES:
                continue
            if any(Path(name).match(pattern) for pattern in EXCLUDED_PATTERNS):
                continue
            files.append(Path(current) / name)
    return files


def collect_files(root: Path, output: Path) -> tuple[list[Path], str]:
    """返回 (待打包文件, 来源说明)。输出 zip 自身永远排除。"""
    git_files = git_file_list(root)
    if git_files is not None:
        files, source = git_files, "git ls-files"
    else:
        files, source = walk_file_list(root), "文件系统遍历"

    output_resolved = output.resolve()
    unique: dict[str, Path] = {}
    for path in files:
        resolved = path.resolve()
        if resolved == output_resolved:
            continue
        try:
            relative = resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            relative = resolved.name
        if any(
            fnmatch.fnmatch(relative, pattern)
            for pattern in EXCLUDED_RELATIVE_PATTERNS
        ):
            continue
        unique[resolved.as_posix()] = path
    return [unique[key] for key in sorted(unique)], source


def split_by_payload(files: list[Path], root: Path) -> tuple[list[Path], list[Path]]:
    """按仓库相对路径把待打包文件分成（产品载荷, 工程资产）。"""
    root_resolved = root.resolve()
    payload: list[Path] = []
    aux: list[Path] = []
    for path in files:
        try:
            relative = path.resolve().relative_to(root_resolved).as_posix()
        except ValueError:
            relative = str(path).replace("\\", "/")
        if relative in PAYLOAD_FILES or relative.startswith(PAYLOAD_PREFIXES):
            payload.append(path)
        else:
            aux.append(path)
    return payload, aux


def check_limits(
    payload: list[Path],
    aux: list[Path],
    *,
    max_payload_files: int,
    max_payload_bytes: int,
    max_aux_files: int,
    max_aux_bytes: int,
    max_files: int,
    max_bytes: int,
) -> tuple[list[str], list[str], dict[str, int]]:
    """按两套配额检查，返回 (问题, 警告, 统计)。

    产品载荷超限是硬失败；工程资产超过软上限只给警告，留出清理空间；
    总数或总体积超限仍然硬失败。
    """
    payload_bytes = sum(path.stat().st_size for path in payload)
    aux_bytes = sum(path.stat().st_size for path in aux)
    total = payload_bytes + aux_bytes
    problems: list[str] = []
    warnings: list[str] = []
    if len(payload) > max_payload_files:
        problems.append(f"产品文件数 {len(payload)} 超过上限 {max_payload_files}")
    if payload_bytes > max_payload_bytes:
        problems.append(
            f"产品体积 {human_size(payload_bytes)} 超过上限 {human_size(max_payload_bytes)}"
        )
    if len(aux) > max_aux_files:
        warnings.append(f"资料文件数 {len(aux)} 超过软上限 {max_aux_files}；建议清理历史记录")
    if aux_bytes > max_aux_bytes:
        warnings.append(
            f"资料体积 {human_size(aux_bytes)} 超过软上限 {human_size(max_aux_bytes)}；建议清理历史记录"
        )
    if len(payload) + len(aux) > max_files:
        problems.append(f"文件总数 {len(payload) + len(aux)} 超过上限 {max_files}")
    if total > max_bytes:
        problems.append(f"总体积 {human_size(total)} 超过上限 {human_size(max_bytes)}")
    return problems, warnings, {
        "payload_files": len(payload),
        "payload_bytes": payload_bytes,
        "aux_files": len(aux),
        "aux_bytes": aux_bytes,
        "total_bytes": total,
    }


def make_zip(files: list[Path], root: Path, output: Path, prefix: str) -> None:
    """生成 zip；prefix 非空时所有条目放在同一个根目录下。"""
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            arcname = f"{prefix}/{relative}" if prefix else relative
            archive.write(path, arcname)



def _build_case(root: Path, name: str, payload_count: int, aux_count: int) -> Path:
    """造一个只含产品载荷与工程资产两类文件的临时仓库。"""
    case = root / name
    for index in range(payload_count):
        target = case / "scripts" / f"p-{index:02d}.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x", encoding="utf-8")
    for index in range(aux_count):
        target = case / "docs" / f"a-{index:02d}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x", encoding="utf-8")
    return case


def package_selftest() -> int:
    """按当前配额参数化验证四种边界；调整配额不需要改自测。"""
    limits = {
        "max_payload_files": DEFAULT_MAX_PAYLOAD_FILES,
        "max_payload_bytes": DEFAULT_MAX_PAYLOAD_BYTES,
        "max_aux_files": DEFAULT_MAX_AUX_FILES,
        "max_aux_bytes": DEFAULT_MAX_AUX_BYTES,
        "max_files": DEFAULT_MAX_FILES,
        "max_bytes": DEFAULT_MAX_BYTES,
    }
    cases = (
        ("payload-at-limit", DEFAULT_MAX_PAYLOAD_FILES, DEFAULT_MAX_AUX_FILES, False, False, "产品正好到上限：应通过"),
        ("payload-over", DEFAULT_MAX_PAYLOAD_FILES + 1, 1, True, False, "产品超一个：应失败"),
        ("aux-over", 1, DEFAULT_MAX_AUX_FILES + 1, False, True, "资料超软上限：应通过并提醒"),
        ("total-over", DEFAULT_MAX_PAYLOAD_FILES, DEFAULT_MAX_FILES - DEFAULT_MAX_PAYLOAD_FILES + 1, True, True, "总数超限：应失败"),
    )
    with tempfile.TemporaryDirectory(prefix="verity-package-") as temporary:
        root = Path(temporary)
        for name, payload_count, aux_count, expect_fail, expect_warning, label in cases:
            case = _build_case(root, name, payload_count, aux_count)
            files, _ = collect_files(case, case / "dist" / "verity.zip")
            payload, aux = split_by_payload(files, case)
            problems, warnings, _ = check_limits(payload, aux, **limits)
            ok = bool(problems) == expect_fail and bool(warnings) == expect_warning
            print(
                f"[{'PASS' if ok else 'FAIL'}] {name}：{label}"
                f"（产品 {len(payload)}，资料 {len(aux)}，问题 {len(problems)}，提醒 {len(warnings)}）"
            )
            if not ok:
                return 1
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="统计 verity 技能包文件数/体积并生成 zip")
    parser.add_argument("--root", default=".", help="要打包的仓库根目录，默认当前目录")
    parser.add_argument("--output", help="zip 输出路径，默认 <root>/dist/verity.zip")
    parser.add_argument("--prefix", default="verity", help="zip 内的根目录名；传空字符串表示不套目录")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES, help="文件总数硬上限，默认 80")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help="总体积硬上限（字节），默认 10 MB",
    )
    parser.add_argument(
        "--max-payload-files",
        type=int,
        default=DEFAULT_MAX_PAYLOAD_FILES,
        help="产品载荷文件数上限，默认 30",
    )
    parser.add_argument(
        "--max-payload-bytes",
        type=int,
        default=DEFAULT_MAX_PAYLOAD_BYTES,
        help="产品载荷体积上限（字节），默认 2 MB",
    )
    parser.add_argument(
        "--max-aux-files",
        type=int,
        default=DEFAULT_MAX_AUX_FILES,
        help="工程资产文件数软上限，默认 45",
    )
    parser.add_argument(
        "--max-aux-bytes",
        type=int,
        default=DEFAULT_MAX_AUX_BYTES,
        help="工程资产体积软上限（字节），默认 8 MB",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="只统计和检查，不生成 zip")
    mode.add_argument("--zip", action="store_true", help="生成 zip（不传参数时的默认行为）")
    mode.add_argument("--selftest", action="store_true", help="运行两套配额的边界反例")
    args = parser.parse_args(argv)

    if args.selftest:
        return package_selftest()
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"用法错误：根目录不存在：{root}", file=sys.stderr)
        return 2
    for name in (
        "max_files",
        "max_bytes",
        "max_payload_files",
        "max_payload_bytes",
        "max_aux_files",
        "max_aux_bytes",
    ):
        if getattr(args, name) < 1:
            print(f"用法错误：{name} 必须是正整数", file=sys.stderr)
            return 2

    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else (root / "dist" / "verity.zip")
    )
    files, source = collect_files(root, output)
    payload, aux = split_by_payload(files, root)
    problems, warnings, stats = check_limits(
        payload,
        aux,
        max_payload_files=args.max_payload_files,
        max_payload_bytes=args.max_payload_bytes,
        max_aux_files=args.max_aux_files,
        max_aux_bytes=args.max_aux_bytes,
        max_files=args.max_files,
        max_bytes=args.max_bytes,
    )

    print("verity 打包检查")
    print(f"  根目录：{root}")
    print(f"  文件来源：{source}")
    print(
        f"  文件数：产品 {stats['payload_files']} / {args.max_payload_files}，"
        f"资料 {stats['aux_files']} / {args.max_aux_files}，"
        f"合计 {len(files)} / {args.max_files}"
    )
    print(
        f"  总大小：产品 {human_size(stats['payload_bytes'])} / {human_size(args.max_payload_bytes)}，"
        f"资料 {human_size(stats['aux_bytes'])} / {human_size(args.max_aux_bytes)}，"
        f"合计 {human_size(stats['total_bytes'])} / {human_size(args.max_bytes)}"
    )
    for warning in warnings:
        print(f"  提醒：{warning}")

    if problems:
        for problem in problems:
            print(f"打包失败：{problem}")
        print("未生成 zip。请删除临时产物或拆分交付物后重试。")
        return 1

    if args.check:
        print("检查通过（--check 模式，未生成 zip）")
        return 0

    try:
        make_zip(files, root, output, args.prefix.strip("/"))
    except OSError as error:
        print(f"打包失败：写入 {output} 时出错：{error}", file=sys.stderr)
        return 1

    print(f"已生成：{output}")
    if args.prefix.strip("/"):
        print(f"解压根目录：{args.prefix.strip('/')}/")
    print(f"zip 体积：{human_size(output.stat().st_size)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
