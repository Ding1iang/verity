#!/usr/bin/env python3
"""生成并运行 10 类反例，逐条断言检查器报出指定错误码。

这个脚本是给 verifier 用的“反例预备清单”执行器：所有样本在临时目录里
即时生成，不依赖仓库里的示例文件，也不写入用户数据。每个样本都故意只
违反一条规则，检查器必须报出对应错误码；只看退出码不算通过。

用法：
    python3 scripts/anti_examples.py

退出码：0 = 10 类反例全部按预期报错；1 = 至少一类没有报出指定错误码。
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER = REPO_ROOT / "scripts" / "check_evidence.py"
TODAY = "2026-11-06"


def row(
    item_id: str,
    *,
    evidence_type: str = "日志",
    evidence: str = "task-card.md",
    status: str = "通过",
    time: str = TODAY,
    commit: str = "工作区",
    producer: str = "反例生成器",
    confidence: str = "高",
) -> dict[str, str]:
    """返回一行十列账本数据；所有反例共用，差异只放在关键列。"""
    return {
        "id": item_id,
        "user_path": "运行反例命令",
        "expected": "检查器报出指定错误码",
        "evidence_type": evidence_type,
        "evidence": evidence,
        "producer": producer,
        "confidence": confidence,
        "time": time,
        "commit": commit,
        "status": status,
    }


def render_ledger(title: str, rows: Iterable[dict[str, str]], conclusion: str = "通过") -> str:
    """渲染一份完整 v1 账本；即使没有数据行也保留五节。"""
    body = [
        f"# 07 验收回归清单：{title}",
        "",
        "<!-- acceptance-evidence: v1 -->",
        "",
        "## 批次信息",
        "",
        "| 字段 | 内容 |",
        "|---|---|",
        "| 任务卡 | task-card.md v1 |",
        f"| 被测版本 | commit：工作区 |",
        "| 环境 | 反例夹具 |",
        "| 执行者 / 复核者 | 反例生成器 / 独立复核 |",
        f"| 收口时间 | {TODAY} |",
        "",
        "## 包结论",
        "",
        f"- 交付结论：{conclusion}",
        "- 一句话说明：这是反例夹具，只用于验证检查器。",
        "- 证据索引：—",
        "",
        "## 外部证据登记",
        "",
        "无外部件。",
        "",
        "## 单项验收（证据账本）",
        "",
        "| 验收项 ID | 用户路径 | 预期 | 证据类型 | 证据 | 产出者 | 置信度 | 时间 | commit | 状态 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in rows:
        body.append(
            "| {id} | {user_path} | {expected} | {evidence_type} | {evidence} | "
            "{producer} | {confidence} | {time} | {commit} | {status} |".format(**item)
        )
    body.extend(
        [
            "",
            "## 欠账",
            "",
            "无欠账。",
            "",
            "## 阻塞举证",
            "",
            "不适用。",
            "",
        ]
    )
    return "\n".join(body)


def write_case(root: Path, name: str, rows: Iterable[dict[str, str]], conclusion: str = "通过") -> Path:
    """写一个反例目录，返回账本路径。"""
    case_dir = root / name
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "task-card.md").write_text(f"# 任务卡：{name}\n", encoding="utf-8")
    ledger = case_dir / "07-验收回归清单.md"
    ledger.write_text(render_ledger(name, rows, conclusion), encoding="utf-8")
    return ledger


def init_git_fixture(root: Path) -> str:
    """在临时目录造一个真实提交，用于验证旧证据的 commit 日期比较。"""
    (root / "task-card.md").write_text("# 任务卡：旧证据反例\n", encoding="utf-8")
    (root / "evidence.txt").write_text("old evidence\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "anti@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "anti-examples"], check=True)
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = "2026-11-06T12:00:00+0800"
    env["GIT_COMMITTER_DATE"] = "2026-11-06T12:00:00+0800"
    subprocess.run(["git", "-C", str(root), "add", "."], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "fixture: old evidence"],
        check=True,
        env=env,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def run_checker(ledger: Path, root: Path) -> tuple[int, str]:
    """调用检查器，合并 stdout/stderr，便于断言具体错误码。"""
    process = subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            str(ledger),
            "--format",
            "v1",
            "--root",
            str(root),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return process.returncode, process.stdout + process.stderr


def main() -> int:
    total = 0
    passed = 0
    failures: list[str] = []

    with tempfile.TemporaryDirectory(prefix="verity-anti-") as temp:
        root = Path(temp)
        cases: list[tuple[str, Path, str]] = []

        # 1. 假截图：写了“见截图”，但没有真实图片文件。
        cases.append(("fake-screenshot", write_case(root, "fake-screenshot", [row("CASE-01", evidence_type="截图", evidence="见截图")]), "E_SCREENSHOT"))

        # 2. 假路径：证据路径不存在。
        cases.append(("fake-path", write_case(root, "fake-path", [row("CASE-02", evidence="evidence/missing.txt")]), "E_EVIDENCE_PATH"))

        # 3. 旧证据：真实 commit 日期晚于证据行日期。
        old_root = root / "stale-evidence"
        old_root.mkdir()
        commit = init_git_fixture(old_root)
        old_ledger = write_case(
            old_root,
            "case",
            [row("CASE-03", time="2026-10-01", commit=commit, evidence="evidence.txt")],
        )
        cases.append(("stale-evidence", old_ledger, "E_STALE"))

        # 4. 空 07：没有验收项。
        cases.append(("empty-ledger", write_case(root, "empty-ledger", []), "E_NO_ROWS"))

        # 5. 无证据通过：状态通过但证据为占位符。
        cases.append(("no-evidence", write_case(root, "no-evidence", [row("CASE-05", evidence="—")]), "E_MISSING_EVIDENCE"))

        # 6. 只跑主路径，却写通过。
        cases.append(("main-path-only", write_case(root, "main-path-only", [row("CASE-06", evidence="只跑了主路径")]), "E_SCOPE_GAP"))

        # 7. 门禁全绿，但自述没跑探针。
        cases.append(("gate-only", write_case(root, "gate-only", [row("CASE-07", evidence="门禁全绿；没跑探针")]), "E_PROBE_MISSING"))

        # 8. 设备没验，却写通过。
        cases.append(("device-unverified", write_case(root, "device-unverified", [row("CASE-08", evidence="设备未验，直接写通过")]), "E_DEVICE_UNVERIFIED"))

        # 9. 重复状态源：同目录两份 07。
        duplicate = write_case(root, "duplicate-source", [row("CASE-09")])
        (duplicate.parent / "07-副本.md").write_text(duplicate.read_text(encoding="utf-8"), encoding="utf-8")
        cases.append(("duplicate-source", duplicate, "E_DUP_SOURCE"))

        # 10. 旧结论词：规范状态之外写“基本可用”。
        cases.append(("old-words", write_case(root, "old-words", [row("CASE-10", evidence="task-card.md：基本可用")]), "E_OLD_WORD"))

        for name, ledger, expected in cases:
            total += 1
            code, output = run_checker(ledger, old_root if name == "stale-evidence" else root)
            if code != 0 and expected in output:
                passed += 1
                print(f"[PASS] {name}: {expected}")
            else:
                failures.append(name)
                print(f"[FAIL] {name}: 期望 {expected}，退出码 {code}")
                print(output.rstrip())

    print(f"结果：{passed}/{total} 反例按预期报错")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
