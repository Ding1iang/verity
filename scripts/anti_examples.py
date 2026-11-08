#!/usr/bin/env python3
"""生成并运行 11 类反例，逐条断言检查器报出指定错误码。

这个脚本是给 verifier 用的“反例预备清单”执行器：所有样本在临时目录里
即时生成，不依赖仓库里的示例文件，也不写入用户数据。每个样本都故意只
违反一条规则，检查器必须报出对应错误码；只看退出码不算通过。

用法：
    python3 scripts/anti_examples.py

退出码：0 = 11 类反例全部按预期报错；1 = 至少一类没有报出指定错误码。
"""

from __future__ import annotations

import os
import hashlib
import re
import shutil
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
    """返回一行旧版十列账本数据；所有反例共用，差异只放在关键列。"""
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


V2_BASE = REPO_ROOT / "examples" / "05-release"


def v2_case(root: Path, name: str, mutate=None, extra: dict[str, str] | None = None) -> Path:
    """以合规的 v2 批次为底，只改一处，确保反例失败是因为目标规则而不是缺段。"""
    case_dir = root / name
    case_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("task-card.md", "journey-01.md", "README.md"):
        shutil.copyfile(V2_BASE / filename, case_dir / filename)
    text = (V2_BASE / "07-验收回归清单.md").read_text(encoding="utf-8")
    if mutate is not None:
        text = mutate(text)
    ledger = case_dir / "07-验收回归清单.md"
    ledger.write_text(text, encoding="utf-8")
    for filename, content in (extra or {}).items():
        (case_dir / filename).write_text(content, encoding="utf-8")
    return ledger


def drop_section(text: str, title: str) -> str:
    """删除一个二级段，用来验证“必需段缺失必须失败”。"""
    return re.sub(rf"## {re.escape(title)}\n.*?(?=\n## )", "", text, count=1, flags=re.S)


def run_v2_cases(root: Path) -> list[tuple[str, Path, str]]:
    """十个 v2 负向夹具：每条只违反一项新规则。"""
    cases: list[tuple[str, Path, str]] = []

    cases.append(("v2-no-journey", v2_case(root, "v2-no-journey", lambda text: drop_section(text, "用户旅程")), "E_STRUCTURE"))

    def journey_not_passed(text: str) -> str:
        text = text.replace("- 结论：通过\n- 未解决的不变量：无", "- 结论：未通过\n- 未解决的不变量：无", 1)
        return text.replace("- 旅程结论：通过", "- 旅程结论：未通过", 1)

    journey_ledger = v2_case(root, "v2-journey-not-passed", journey_not_passed)
    (journey_ledger.parent / "journey-01.md").write_text(
        (journey_ledger.parent / "journey-01.md").read_text(encoding="utf-8").replace("- 结论：通过", "- 结论：未通过", 1),
        encoding="utf-8",
    )
    cases.append(("v2-journey-not-passed", journey_ledger, "E_JOURNEY_NOT_PASSED"))

    cases.append(("v2-no-completion-audit", v2_case(root, "v2-no-completion-audit", lambda text: drop_section(text, "完成审计")), "E_STRUCTURE"))

    cases.append(("v2-ac-unmapped", v2_case(root, "v2-ac-unmapped", lambda text: text.replace("| REL-01 | AC-01 |", "| REL-01 | AC-99 |", 1)), "E_COVERS"))

    def same_reviewer(text: str) -> str:
        return text.replace("示例复核者（独立）", "示例执行者")

    cases.append(("v2-producer-equals-reviewer", v2_case(root, "v2-producer-equals-reviewer", same_reviewer), "E_REVIEW_INDEPENDENT"))

    empty_form = """# 阻塞举证单：反例 / REL-05

## 1. 卡点

| 字段 | 内容 |
|---|---|
| 卡点 |  |
| 现象 |  |

## 2. 能力探测

| 探测项 | 命令或步骤 | 实际读数 | 结论 |
|---|---|---|---|
|  |  |  |  |

## 3. 正对照

| 对照位置 | 操作 | 结果 | 说明 |
|---|---|---|---|
|  |  |  |  |

## 4. 四维尝试

| 维度 | 试过什么 | 实际结果 | 是否排除 |
|---|---|---|---|
| 环境 |  |  | 否 |

## 5. 替代证据

| 替代通道 | 能证明什么 | 不能证明什么 | 证据 |
|---|---|---|---|
|  |  |  |  |

## 6. 为什么不是失败

## 7. 解锁条件

- 需要谁提供什么：
"""

    def blocked(text: str) -> str:
        text = text.replace("| REL-05 | AC-05 | J-01 / 步骤 5 | 主路径和错误路径各一次，结果已记录 | 日志 | README.md | A | 示例执行者 | 示例复核者（独立） | 高 | 2026-11-08 | 工作区 | 通过 |", "| REL-05 | AC-05 | J-01 / 步骤 5 | 主路径和错误路径各一次，结果已记录 | 日志 | README.md | A | 示例执行者 | 示例复核者（独立） | 高 | 2026-11-08 | 工作区 | 未交付-阻塞 |", 1)
        return text.replace("- 交付结论：通过", "- 交付结论：未交付（阻塞）", 1)

    cases.append(("v2-empty-blocking-form", v2_case(root, "v2-empty-blocking-form", blocked, {"blocking-form.md": empty_form}), "E_BLOCKING_FORM"))

    def duplicate_screenshot(text: str, *, sha: str, size: int) -> str:
        text = text.replace("| REL-04 | AC-04 | J-01 / 步骤 4 | 上一可用版本、恢复步骤和恢复后冒烟检查齐全 | 日志 | README.md |", "| REL-04 | AC-04 | J-01 / 步骤 4 | 上一可用版本、恢复步骤和恢复后冒烟检查齐全 | 截图 | shot.png |", 1)
        text = text.replace("| REL-05 | AC-05 | J-01 / 步骤 5 | 主路径和错误路径各一次，结果已记录 | 日志 | README.md |", "| REL-05 | AC-05 | J-01 / 步骤 5 | 主路径和错误路径各一次，结果已记录 | 截图 | shot.png |", 1)
        identity = f"| shot.png | {sha} | {size} | example-05-build | 示例项目 / 单机 / Python 3.9+ | 2026-11-08 | 83df5b9c8f2ee3816149f37918b108d7991f0f571efd1d9495adf6cbcc5cbae6 | viewport=390x844；pixel_hash={'a' * 64} |\n"
        return text.replace("| README.md | 2df74429", identity + "| README.md | 2df74429", 1)

    shot = root / "v2-duplicate-screenshot" / "shot.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    shot.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    sha = hashlib.sha256(shot.read_bytes()).hexdigest()
    screenshot_ledger = v2_case(root, "v2-duplicate-screenshot", lambda text: duplicate_screenshot(text, sha=sha, size=shot.stat().st_size))
    (screenshot_ledger.parent / "shot.png").write_bytes(shot.read_bytes())
    cases.append(("v2-duplicate-screenshot", screenshot_ledger, "E_EVIDENCE_REUSED"))

    cases.append(("v2-old-build", v2_case(root, "v2-old-build", lambda text: text.replace("| example-05-build | 示例项目", "| example-04-build | 示例项目", 1)), "E_ARTIFACT_BUILD"))
    cases.append(("v2-missing-evidence-path", v2_case(root, "v2-missing-evidence-path", lambda text: text.replace("| REL-03 | AC-03 | J-01 / 步骤 3 | 干净检出构建成功，产物 SHA-256 已记录 | 日志 | README.md |", "| REL-03 | AC-03 | J-01 / 步骤 3 | 干净检出构建成功，产物 SHA-256 已记录 | 日志 | evidence/missing.log |", 1)), "E_EVIDENCE_PATH"))
    cases.append(("v2-fake-evidence", v2_case(root, "v2-fake-evidence", lambda text: text.replace("| REL-03 | AC-03 | J-01 / 步骤 3 | 干净检出构建成功，产物 SHA-256 已记录 | 日志 | README.md |", "| REL-03 | AC-03 | J-01 / 步骤 3 | 干净检出构建成功，产物 SHA-256 已记录 | 日志 | todo.log |", 1), {"todo.log": "TODO\n"}), "E_FAKE_EVIDENCE"))
    return cases


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

        # 11. 新账本默认禁止带欠账：没有 --compat-debt 时，带欠账必须报错。
        cases.append(("debt-not-allowed", write_case(root, "debt-not-allowed", [row("CASE-11", status="带欠账")], conclusion="带欠账交付"), "E_STATUS"))

        all_cases = cases + run_v2_cases(root)
        for name, ledger, expected in all_cases:
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
