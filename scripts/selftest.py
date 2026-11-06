#!/usr/bin/env python3
"""verity 检查器自测。

在临时目录里造一个合规账本作为好样本，再分别造“缺证据 / 假路径 /
旧结论词 / 重复状态源”四类坏样本，逐个调用 check_evidence.py。

四类坏样本覆盖任务要求的四类拦截；其中前三类各是一个独立坏样本，
第四类用同目录第二份 07 账本触发。任何一类没被拦住，退出码为 1。

只使用 Python 标准库。退出码：0 = 全部符合预期；1 = 有样本不符合预期；
2 = 检查器缺失或无法执行。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

CHECKER = Path(__file__).resolve().parent / "check_evidence.py"

BATCH_INFO = """## 批次信息

| 字段 | 内容 |
|---|---|
| 任务卡 | task-card.md v1 |
| 被测版本 | commit abc1234 |
| 环境 | Python 3.13 / macOS |
| 执行者 / 复核者 | 执行者甲 / 复核者乙 |
| 收口时间 | 2026-11-06 14:30 |
"""

HEADER = """## 账本

| ID | 验收项 | 判据 | 最低证据 | 证据等级 | 证据（文件或命令读数） | 状态 | 复核 |
|---|---|---|---|---|---|---|---|
"""


def make_ledger(
    rows: list[list[str]],
    conclusion: str = "通过",
    counts: str = "通过 2 / 未通过 0 / 阻塞 0 / 不适用 1",
) -> str:
    """拼出一份完整账本；rows 每项固定八列。"""
    body = "\n".join("| " + " | ".join(row) + " |" for row in rows)
    return (
        "# 07 验收回归清单：自测样本\n\n"
        + BATCH_INFO
        + "\n"
        + HEADER
        + body
        + "\n\n## 收口\n\n"
        + f"- 结论：{conclusion}\n"
        + f"- 计数：{counts}\n"
        + "- 举证单：无\n"
    )


def good_rows() -> list[list[str]]:
    """合规样本的三行账本：两条通过、一条不适用。"""
    return [
        [
            "AC-1",
            "自测脚本可运行",
            "给定 python3 scripts/selftest.py，应输出全部通过并退出 0",
            "A",
            "A",
            "`evidence/ac1.log`",
            "通过",
            "复核人甲",
        ],
        [
            "AC-2",
            "两路证据互证",
            "给定两条不同通道的观察，应得到同一结论",
            "B+B",
            "B+B",
            "`evidence/ac2-ui.txt`；`evidence/ac2-db.txt`",
            "通过",
            "复核人甲",
        ],
        [
            "AC-3",
            "发布检查",
            "发布检查对本次脚本任务不成立，理由已写明",
            "—",
            "—",
            "理由：本次不涉及发布，任务卡范围已排除",
            "不适用",
            "任务卡作者",
        ],
    ]


@dataclass
class Case:
    """一个自测样本。expected_codes 为空表示应通过。"""

    slug: str
    label: str
    rows: list[list[str]]
    conclusion: str = "通过"
    expected_codes: tuple[str, ...] = ()
    copy_ledger: bool = False

    @property
    def should_pass(self) -> bool:
        return not self.expected_codes


def build_case(root: Path, case: Case) -> Path:
    """把样本写到独立目录，并补齐证据文件。"""
    case_dir = root / case.slug
    case_dir.mkdir(parents=True)
    (case_dir / "evidence").mkdir()
    (case_dir / "evidence" / "ac1.log").write_text("selftest: 5/5 passed, exit 0\n", encoding="utf-8")
    (case_dir / "evidence" / "ac2-ui.txt").write_text("界面读数：通过\n", encoding="utf-8")
    (case_dir / "evidence" / "ac2-db.txt").write_text("库读数：通过\n", encoding="utf-8")
    (case_dir / "07-验收回归清单.md").write_text(
        make_ledger(case.rows, case.conclusion), encoding="utf-8"
    )
    if case.copy_ledger:
        shutil.copyfile(
            case_dir / "07-验收回归清单.md",
            case_dir / "07-验收回归清单-副本.md",
        )
    return case_dir


def run_checker(case_dir: Path) -> subprocess.CompletedProcess[str]:
    """在样本目录中运行检查器；相对路径与真实用法一致。"""
    return subprocess.run(
        [sys.executable, str(CHECKER), "07-验收回归清单.md"],
        cwd=case_dir,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    if not CHECKER.is_file():
        print(f"自测失败：找不到检查器 {CHECKER}", file=sys.stderr)
        return 2

    missing_evidence = good_rows()
    missing_evidence[1][5] = ""

    fake_path = good_rows()
    fake_path[1][5] = "`evidence/not-there.log`"

    old_words = good_rows()
    old_words[0][7] = "基本可用"

    cases = [
        Case("good", "好样本", good_rows()),
        Case(
            "bad-missing-evidence",
            "坏样本·缺证据",
            missing_evidence,
            expected_codes=("E_MISSING_EVIDENCE",),
        ),
        Case(
            "bad-fake-path",
            "坏样本·假路径",
            fake_path,
            expected_codes=("E_EVIDENCE_PATH",),
        ),
        Case(
            "bad-old-words",
            "坏样本·旧结论词",
            old_words,
            expected_codes=("E_OLD_WORD",),
        ),
        Case(
            "bad-duplicate-source",
            "坏样本·重复状态源",
            good_rows(),
            expected_codes=("E_DUP_SOURCE",),
            copy_ledger=True,
        ),
    ]

    print("verity 自测")
    print(f"检查器：{CHECKER}")
    passed = 0
    failures: list[str] = []

    with tempfile.TemporaryDirectory(prefix="verity-selftest-") as temp:
        root = Path(temp)
        for case in cases:
            case_dir = build_case(root, case)
            process = run_checker(case_dir)
            output = process.stdout + process.stderr

            if case.should_pass:
                ok = process.returncode == 0 and "结论=通过" in process.stdout
                detail = f"退出 {process.returncode}，未给出通过摘要"
            else:
                hit = all(code in output for code in case.expected_codes)
                ok = process.returncode != 0 and hit
                detail = (
                    f"退出 {process.returncode}，"
                    f"{'命中 ' if hit else '未命中 '}{'/'.join(case.expected_codes)}"
                )

            if ok:
                passed += 1
                print(f"[PASS] {case.label}：{detail if not case.should_pass else '退出 0，结论=通过'}")
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


if __name__ == "__main__":
    sys.exit(main())
