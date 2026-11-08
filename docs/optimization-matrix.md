# 32 项工作流优化落地矩阵

> 清单来源：`docs/2026-11-07-外部工作流对比与优化清单.md`。本矩阵只记录落地事实，不复制清单正文。
> 状态只有 `done`；每行的“测试/证据”列给出可直接复跑的命令、夹具或文件。

| 编号 | 名称 | 状态 | 改动文件 | 测试 / 证据 |
|---|---|---|---|---|
| 1 | 快慢车道与风险分级 | done | `templates/task-card.md`、`scripts/check_evidence.py`（`check_task_card` / `E_TASK_LANE`） | `examples/05-release/task-card.md` 全流程；`check_evidence.py examples/05-release/07-验收回归清单.md` 通过 |
| 2 | 立卡前 grill | done | `templates/task-card.md`、`scripts/check_evidence.py`（`E_GRILL`） | `examples/05-release/task-card.md` 的“立卡前盘问”3 行；自验收 `evidence/04-verification.log` 删行后报 `E_GRILL` |
| 3 | 一页规格与决策记录 | done | `templates/task-card.md`、`scripts/check_evidence.py`（`E_SPEC_LITE`） | `examples/05-release/task-card.md` 的“规格摘要（spec-lite）”；自验收日志删段后报 `E_SPEC_LITE` |
| 4 | 判据可判性 lint | done | `scripts/check_evidence.py`（`E_CRITERION`、`criterion-exempt`） | 自验收日志把 AC 判据改成“界面正常”后报 `E_CRITERION`；`examples/05` 原判据通过 |
| 5 | AC、旅程、账本三向映射 | done | `scripts/check_evidence.py`（`covers`、`E_COVERS`、`E_JOURNEY_STEP`）、`templates/07-acceptance.md` | `python3 scripts/anti_examples.py` 的 `v2-ac-unmapped` 报 `E_COVERS`；`examples/04`、`05` 正常通过 |
| 6 | 范围锁与工作区干净 | done | `templates/task-card.md`、`scripts/verity.py`（`check_scope`）、`scripts/verity.py gate` | `python3 scripts/verity.py gate --selftest`；`gate --root . --ledger examples/04...` 的范围锁 5/5 |
| 7 | 证据命令执行 | done | `scripts/verity.py`（`cmd_gate` 调检查器）、`scripts/check_evidence.py`（复核命令 `E_REVIEW_COMMAND`） | `verity.py gate` 实际执行 `check_evidence.py` / `check_coverage.py`；`docs/reviews/2026-11-08-self-acceptance/evidence/04-verification.log` |
| 8 | 产物与环境身份 | done | `templates/07-acceptance.md`（证据身份段）、`scripts/check_evidence.py`（`E_ARTIFACT_*`） | `examples/04`、`05` 的证据身份表；`anti_examples.py` 的 `v2-old-build` 报 `E_ARTIFACT_BUILD` |
| 9 | 旧证据失效 | done | `scripts/check_evidence.py`（`E_STALE`、`E_STALE_TASKCARD`、`E_ARTIFACT_BUILD`） | `anti_examples.py` 的 `stale-evidence`、`v2-old-build` 均按预期失败 |
| 10 | 独立复核强制 | done | `templates/07-acceptance.md`（独立复核段）、`scripts/check_evidence.py`（`E_REVIEW_INDEPENDENT`、`E_REVIEW_AC`） | `anti_examples.py` 的 `v2-producer-equals-reviewer` 报 `E_REVIEW_INDEPENDENT`；`examples/04`、`05` 逐 AC supports |
| 11 | 完成线闸门 | done | `scripts/verity.py`（`cmd_gate`、`gate_selftest`） | `python3 scripts/verity.py gate --selftest` 正负对照 PASS；`gate` 跑 examples/04、05 均 5/5 |
| 12 | 防绕过 | done | `scripts/verity.py`（`read_anti_bypass_policy`、`check_anti_bypass`）、`.verity/policy.json` 约定 | `gate --selftest` 的负对照：删断言、加 skip/focus、`--no-verify` 被识别；正对照干净提交不误报 |
| 13 | 完成审计结构化 | done | `templates/07-acceptance.md`、`scripts/check_evidence.py`（`E_COMPLETION_AUDIT`、`E_COMPLETION_AC`、`E_COMPLETION_EVIDENCE`） | `anti_examples.py` 的 `v2-no-completion-audit` 报 `E_STRUCTURE`；`examples/04`、`05` 每条 AC 有完成审计行 |
| 14 | 旅程卡强制与负路径 | done | `scripts/check_evidence.py`（`E_JOURNEY_NOT_PASSED`、`E_JOURNEY_STEP`）、`scripts/check_coverage.py`（`E_JOURNEY_CARD_MISSING`）、`scripts/verity.py init` | `anti_examples.py` 的 `v2-no-journey`、`v2-journey-not-passed` 均失败；`check_coverage.py --selftest` 9/9 含 `bad-no-journey` |
| 15 | 阻塞举证单结构化 | done | `templates/blocking-form.md`、`scripts/check_evidence.py`（`check_blocking_form`、`E_BLOCKING_FORM`） | `anti_examples.py` 的 `v2-empty-blocking-form` 报 `E_BLOCKING_FORM`；`examples/03-blocking/blocking-form.md` 通过 |
| 16 | 发布风险与 PR 摘要 | done | `templates/07-acceptance.md`（发布风险段）、`scripts/verity.py report --kind pr` | `examples/05-release/07` 的发布风险表；`python3 scripts/verity.py report --ledger examples/05-release/07-验收回归清单.md --kind pr` |
| 17 | 复盘与 F 类统计 | done | `templates/07-acceptance.md`（复盘表）、`scripts/verity.py metrics` | `examples/05-release/07` 的 F1–F6 表；`python3 scripts/verity.py metrics --dir .` |
| 18 | 红队夹具 | done | `scripts/anti_examples.py`、`docs/reviews/anti-examples.md` | `python3 scripts/anti_examples.py`：21/21 按预期报错 |
| 19 | 技能写作 | done | `SKILL.md`、`README.md`、`references/` | `python3 scripts/package.py --check`；SKILL/README 与模板/示例计数一致 |
| 20 | 术语表与判级校准 | done | `references/evidence.md`、`scripts/check_evidence.py`（A/B+/B/C） | `examples/04`、`05` 证据等级均为 A；`check_evidence.py` 对非法等级报 `E_EVIDENCE_LEVEL` |
| 21 | 版本迁移与 schema | done | `scripts/verity.py upgrade`、`VERSION`、`CHANGELOG.md` | `python3 scripts/verity.py upgrade --help`；自验收日志用旧十列夹具跑 `upgrade` 后 schema 2 |
| 22 | 适配层预检 | done | `scripts/verity.py doctor`、`references/adapter.md` | `python3 scripts/verity.py doctor --root .`：5/5 通过（适配层缺失按可选） |
| 23 | 多代理任务图 | done | `templates/07-acceptance.md`（证据归属：task_id / agent_id / claimed_at） | `examples/05` 单代理批次写“本批单代理”；模板字段可被 `check_evidence.py` 解析 |
| 24 | 度量 | done | `scripts/verity.py metrics` | `python3 scripts/verity.py metrics --dir .` 输出账本数、行数、A 级占比 |
| 25 | 安全与脱敏扫描 | done | `scripts/verity.py scan`（默认 warning，`--release` 阻断） | `python3 scripts/verity.py scan --root .`；`--release` 对命中项返回非 0 |
| 26 | 专项证据结构化 | done | `templates/07-acceptance.md`（结构化读数列）、`scripts/check_evidence.py`（viewport/pixel_hash/runs/median/before/after） | `examples/04`、`05` 证据身份；`anti_examples.py` 的 `v2-duplicate-screenshot` 验证截图身份 |
| 27 | 交接摘要 | done | `scripts/verity.py report --kind handoff` | `python3 scripts/verity.py report --ledger examples/05-release/07-验收回归清单.md --kind handoff` |
| 28 | 修缺陷的紧反馈回路 | done | `references/bug-fix.md`（2.8 紧反馈回路）、`scripts/verity.py gate` | 自验收日志复跑 `check_evidence.py examples/02-bug-fix/07-验收回归清单.md`；失败样本 `examples/04/bad-fake-screenshot` 只报一个目标错误 |
| 29 | 自验收（先拿 verity 验 verity） | done | `docs/reviews/2026-11-08-self-acceptance/` | 该目录的 07、证据身份、完成审计、独立复核与 manifest |
| 30 | 取证通道正对照预检 | done | `scripts/verity.py doctor`（`evidence_channels`） | `python3 scripts/verity.py doctor --root .` 输出取证通道正对照；缺失通道按可选处理 |
| 31 | 两层汇报：先人话，后证据 | done | `scripts/verity.py report --kind two-layer`、`SKILL.md` 输出格式 | `python3 scripts/verity.py report --ledger examples/05-release/07-验收回归清单.md --kind two-layer` |
| 32 | 证据包自包含 | done | `scripts/verity.py manifest`、`examples/04-project-v1/manifest.json`、自验收 manifest | `python3 scripts/verity.py manifest --root . --ledger examples/04-project-v1/07-验收回归清单.md --check`：5 个文件一致 |
