#!/usr/bin/env python3
"""verity 技能包打包检查与 zip 生成。

规则：文件数超过 60 或总大小超过 10 MB 时直接报错，不生成 zip。
上限按自用开源仓库的口径设置，覆盖技能内容与 GitHub 协作文件。

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

DEFAULT_MAX_FILES = 60
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
    "docs/reviews/32-item-review.md",
    "docs/reviews/32-item-verification.md",
    "docs/reviews/2026-11-06-independent-review.md",
    ".github/ISSUE_TEMPLATE/*",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "examples/01-new-feature/bad-main-path/*",
    "examples/02-bug-fix/bad-old-evidence/*",
    "examples/04-project-v1/bad-fake-screenshot/*",
    "examples/05-release/bad-gate-only/*",
    "examples/04-project-v1/manifest.json",
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


def check_limits(files: list[Path], max_files: int, max_bytes: int) -> tuple[int, list[str]]:
    """统计文件数与总大小，返回 (总字节数, 超限说明)。"""
    total = sum(path.stat().st_size for path in files)
    problems: list[str] = []
    if len(files) > max_files:
        problems.append(f"文件数 {len(files)} 超过上限 {max_files}")
    if total > max_bytes:
        problems.append(f"总大小 {human_size(total)} 超过上限 {human_size(max_bytes)}")
    return total, problems


def make_zip(files: list[Path], root: Path, output: Path, prefix: str) -> None:
    """生成 zip；prefix 非空时所有条目放在同一个根目录下。"""
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            arcname = f"{prefix}/{relative}" if prefix else relative
            archive.write(path, arcname)



def package_selftest() -> int:
    """验证 60 文件通过、70 文件失败的硬上限，防止为了临时记录放宽规则。"""
    with tempfile.TemporaryDirectory(prefix="verity-package-") as temporary:
        root = Path(temporary)
        for count, should_pass in ((60, True), (70, False)):
            case = root / str(count)
            case.mkdir()
            for index in range(count):
                (case / f"file-{index:02d}.txt").write_text("x", encoding="utf-8")
            files, _ = collect_files(case, case / "dist" / "verity.zip")
            _, problems = check_limits(files, DEFAULT_MAX_FILES, DEFAULT_MAX_BYTES)
            ok = (not problems) if should_pass else bool(problems)
            print(f"[{'PASS' if ok else 'FAIL'}] {count} 文件：{'应通过' if should_pass else '应失败'}（{len(files)} 个）")
            if not ok:
                return 1
    return 0

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="统计 verity 技能包文件数/体积并生成 zip")
    parser.add_argument("--root", default=".", help="要打包的仓库根目录，默认当前目录")
    parser.add_argument("--output", help="zip 输出路径，默认 <root>/dist/verity.zip")
    parser.add_argument("--prefix", default="verity", help="zip 内的根目录名；传空字符串表示不套目录")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES, help="文件数上限，默认 60")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help="总大小上限（字节），默认 10 MB",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="只统计和检查，不生成 zip")
    mode.add_argument("--zip", action="store_true", help="生成 zip（不传参数时的默认行为）")
    mode.add_argument("--selftest", action="store_true", help="运行 60 通过 / 70 失败的上限反例")
    args = parser.parse_args(argv)

    if args.selftest:
        return package_selftest()
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"用法错误：根目录不存在：{root}", file=sys.stderr)
        return 2
    if args.max_files < 1 or args.max_bytes < 1:
        print("用法错误：上限必须是正整数", file=sys.stderr)
        return 2

    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else (root / "dist" / "verity.zip")
    )
    files, source = collect_files(root, output)
    total, problems = check_limits(files, args.max_files, args.max_bytes)

    print("verity 打包检查")
    print(f"  根目录：{root}")
    print(f"  文件来源：{source}")
    print(f"  文件数：{len(files)} / {args.max_files}")
    print(f"  总大小：{human_size(total)} / {human_size(args.max_bytes)}")

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
