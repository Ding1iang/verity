# 第四轮针对性复核报告（t10）

- 复核对象：t9 修复提交 `a5b67a3`（前序 `ade4c86`、`c6c5407`、`f020d7a`、`61702b8`、`2de2153`）
- 复核人：reviewer（独立复核，不参与实现）
- 工作目录：`/Users/dingliang/JavaProject/verity`
- 干净克隆：`/tmp/verity-r4.clone`（detached `a5b67a3`，工作区干净）
- 版本：`VERSION` = 1.3.0
- 结论：`needs_revision`（存在 1 个 blocker；不得放行）

## 结论摘要

t9 已实质修复 R3-02 至 R3-06：`ev-runs.log` 进入 git、manifest 和 07 证据行；examples/04 的 README、矩阵、任务卡和 CHANGELOG 已统一为“adapter + `--run` 才是完整 5/5”；矩阵计数、doctor 适配层和 package 报告排除均实测通过。

但 R3-01 仍未完全修复：检查器禁止了 `echo`、`python -c` 等直白假命令，却允许 `sh -c 'echo "结果：5/5 通过"'`。该命令在干净 worktree 中真实执行、退出 0、输出与表格一致，`check_evidence.py` 仍返回 6 行全部通过，独立复核仍可伪造，因此本轮只能判 `needs_revision`。

## 复核范围与方法

1. 在 `a5b67a3` 的独立克隆里复跑 t9 的 8 条 verify、自验收检查、gate、manifest、doctor、package 和 anti 夹具。
2. 逐条验证 R3-01 至 R3-06，不把“文字改成新口径”当作修复。
3. 对 R3-01 做正反两向夹具：合法 `python3 scripts/selftest.py` 必须通过；伪造输出、`python3 -c` 和 shell 包装假命令分别测试。
4. 核对 examples/04 的 README、矩阵、任务卡、CHANGELOG 与实际命令输出一致。
5. 只写本报告，不修改任何实现文件；工作区原有 round3 报告已跟踪，round4 报告为本轮新增。

## 关键命令读数

| 命令 | 读数 | 退出码 |
|---|---|---|
| `python3 scripts/selftest.py` | 5/5 通过 | 0 |
| `python3 scripts/anti_examples.py` | 42/42 按预期 | 0 |
| `python3 scripts/check_coverage.py --selftest` | 9/9 通过 | 0 |
| `python3 -m py_compile scripts/*.py` | 无错误 | 0 |
| `python3 scripts/check_evidence.py examples/04-project-v1/07-验收回归清单.md` | 1 行，结论=通过 | 0 |
| `python3 scripts/check_evidence.py examples/05-release/07-验收回归清单.md` | 5 行，结论=通过 | 0 |
| `python3 scripts/package.py --check`（干净克隆） | 60/60，594.7 KB / 10.0 MB | 0 |
| `python3 scripts/package.py --check --max-files 60` | 60/60 | 0 |
| `git diff --check` | 无输出 | 0 |
| 自验收 `check_evidence.py` | 6 行，结论=通过 | 0 |
| 自验收 `gate` | 5/5 | 0 |
| 自验收 `gate --team --release` | 6/6 | 0 |
| 自验收 `manifest --check` | 6 个文件一致，workspace_hash=4d8d0402… | 0 |
| `gate --ledger examples/04`（无 adapter、无 --run） | 4/5；证据账本 FAIL：账本引用 EV 证据命令但未传 --run | 1 |
| `gate --ledger examples/04 --adapter tests/fixtures/valid-adapter.json --run` | 5/5 | 0 |
| `gate --ledger examples/05` | 5/5 | 0 |
| `manifest --check examples/04` | 6 个文件一致，workspace_hash=679b9795… | 0 |
| `gate --selftest` | 9 个 PASS | 0 |
| `bash tests/init-selftest.sh` | 6/6 通过 | 0 |
| `doctor --root . --adapter tests/fixtures/valid-adapter.json` | 10/10 通过（0 条 commands，1 条 evidence_commands） | 0 |
| `doctor --root .`（无 adapter） | 6/6 通过 | 0 |
| `package.py --selftest` | 60 应过、70 应失败 | 0 |
| `metrics --dir .` | 3 份真实账本、12 行、A 12、F1–F6 全 0 | 0 |
| `scan --root .` 与 `--release` | 0 命中 | 0 |
| `package.py --check`（工作区含 round3/round4 报告） | 60/60，594.7 KB / 10.0 MB | 0 |

## R3-01～R3-06 逐项验证

### R3-01 独立复核命令实际执行：未完全修复

- 合法命令 `python3 scripts/selftest.py` 在干净 worktree 中实际执行，自验收 07 的 6 行独立复核仍全部通过。
- 把复跑命令改回真实命令、但把输出摘要改成 `fabricated output` 后，检查器报 6 条 `E_REVIEW_COMMAND`“复跑输出摘要与实际执行输出不一致”，exit 1。
- 把复跑命令改成 `python3 -c "print('fabricated')"` 后，检查器报 6 条 `E_REVIEW_COMMAND`“复跑命令不能是 echo/true/python -c 这类假命令”，exit 1。
- 把复跑命令改成 `sh -c 'echo "结果：5/5 通过"'`，输出仍写“结果：5/5 通过”，其余字段不变；检查器返回 `[OK] ...：6 行，结论=通过（通过 6）`，exit 0。该命令只是打印一句假输出，没有任何复核事实，属于可直接伪造的壳包装绕过。

### R3-02 `ev-runs.log` 纳入证据包：通过

- `git ls-files examples/04-project-v1/evidence/ev-runs.log` 返回该路径，说明已跟踪。
- 文件内容包含 `2026-11-08T16:40:04`、`HEAD=f020d7a...`、`EV-01 exit=0`、命令和输出摘要。
- `examples/04` 的 manifest 共 6 个文件，包含 `examples/04-project-v1/evidence/ev-runs.log`，SHA-256 为 `fa8a5987...`，`tracked=true`；`manifest --check` exit 0。
- `examples/04` 的 07 证据行明确引用 `evidence/ev-runs.log`，证据身份表给出 SHA-256、字节数和结构化读数 `EV-01 exit=0`。
- 干净克隆中文件可见，未依赖工作区未跟踪文件。

### R3-03 examples/04 默认口径：通过

- `examples/04-project-v1/README.md:35-43` 明确区分：`check_evidence.py` 不依赖适配层；完整 gate 必须加 `--adapter tests/fixtures/valid-adapter.json --run`，并明确写“不带 --adapter 时只输出 4/5，4/5 不是完整门禁”。
- 实测 README 的第一条命令 `check_evidence.py` exit 0；完整 gate 5/5；默认 gate 4/5 与 README 的说明一致，不再把 4/5 写成 5/5。
- 矩阵 row 11、CHANGELOG 验证段、自验收 task-card AC-03 均已改为 adapter + `--run` 的 5/5 口径。

### R3-04 矩阵计数：通过

- 矩阵 row 2 的 examples/05 盘问为 5 行，实例文件确为 5 行。
- 矩阵 row 18 为 42/42，`anti_examples.py` 实测 42/42。
- 矩阵 row 11、CHANGELOG、自验收 task-card 的 examples/05 gate 为 5/5，实测 5/5。
- `doctor --adapter` 的“文档计数：一致”通过，检查 README、CHANGELOG、矩阵的 42/60 计数。

### R3-05 doctor 适配层：通过

- `doctor --root . --adapter tests/fixtures/valid-adapter.json` 输出 10/10，通过项包括“证据命令：0 条 commands，1 条 evidence_commands”，不再误报 8/9。

### R3-06 报告与 packaging：通过

- 工作区包含已跟踪的 `docs/reviews/32-item-review-round3.md`，`package.py --check` 仍为 60/60。
- 新增本报告后再次执行 `package.py --check`，仍为 60/60；`32-item-review*.md` 通配排除生效。

## 32 项逐项结论

| # | 项目 | 结论 | 依据 |
|---|---|---|---|
| 1 | 快慢车道与风险分级 | 通过 | 硬触发负向夹具命中 E_TASK_LANE；全流程示例通过 |
| 2 | 立卡前 grill | 通过 | 检查器要求 5–10 条，examples/05 为 5 行 |
| 3 | 一页规格与决策记录 | 通过 | examples/05 六字段齐全；反例可报 E_SPEC_LITE |
| 4 | 判据可判性 lint | 通过 | 模糊判据负向夹具命中 E_CRITERION |
| 5 | AC、旅程、账本三向映射 | 通过 | examples/04、05 通过；anti 未映射夹具失败 |
| 6 | 范围锁与工作区干净 | 通过 | 未跟踪文件使 gate 报范围锁失败 |
| 7 | 证据命令执行 | 通过 | examples/04 `--run` 5/5；ev-runs.log 已跟踪并进入 manifest/07 |
| 8 | 产物与环境身份 | 通过 | SHA-256、字节数、workspace_hash、截图像素均实算 |
| 9 | 旧证据失效 | 通过 | 全零 workspace_hash 报 E_WORKSPACE_CHANGED；旧构建夹具失败 |
| 10 | 独立复核强制 | 失败 | `sh -c` 打印假输出仍通过（R4-01） |
| 11 | 完成线闸门 | 通过 | 自验收 gate 6/6；examples/04 adapter+run 5/5；默认 4/5 已明确标注 |
| 12 | 防绕过 | 通过 | gate --selftest 覆盖删断言、skip、越界、伪造清单 |
| 13 | 完成审计结构化 | 通过 | examples/04、05 每条 AC 有场景/构建/读数/证据 |
| 14 | 旅程卡强制与负路径 | 通过 | 3–7 步、每卡≥3 不变量、跨区域和异常分支有检查 |
| 15 | 阻塞举证单结构化 | 通过 | examples/03 通过；空举证反例失败 |
| 16 | 发布风险与 PR 摘要 | 通过 | `report --kind pr` 输出结论/证据/风险回滚 |
| 17 | 复盘与 F 类统计 | 通过 | metrics 输出 F1–F6、复核发现、返工、周期中位数 |
| 18 | 红队夹具 | 通过 | anti_examples 42/42 |
| 19 | 技能写作与计数一致 | 通过 | 版本 1.3.0、60/42/6 计数一致，doctor 文档计数通过 |
| 20 | 术语表与判级校准 | 通过 | A/B+/B/C 可解析，非法等级有错误码 |
| 21 | 版本迁移与 schema | 通过 | 八列 legacy 被拒绝，十列迁移有提示 |
| 22 | 适配层预检 | 通过 | 无适配层 6/6；合法 adapter 10/10 |
| 23 | 多代理任务图 | 通过 | 证据归属段与 task_id/agent_id/claimed_at 已强制 |
| 24 | 度量 | 通过 | 结构化返工字段和 metrics 自测通过 |
| 25 | 安全与脱敏扫描 | 通过 | 默认 WARN，--release 无命中；扫描 84 文件 0 项 |
| 26 | 专项证据结构化 | 通过 | 截图、性能、DB before/after 有结构校验 |
| 27 | 交接摘要 | 通过 | handoff 含证据路径、状态和下一步 |
| 28 | 修缺陷的紧反馈回路 | 通过 | bad-fake-screenshot 只报 E_SCREENSHOT |
| 29 | 自验收 | 通过 | 自验收 check/gate/manifest 通过，计数为 60/42/6 |
| 30 | 取证通道正对照预检 | 通过 | 通道正对照 exit 0、负对照非 0 |
| 31 | 两层汇报 | 通过 | 第一层三行不含 ID/路径/术语，第二层给证据 |
| 32 | 证据包自包含 | 通过 | 自验收 6 文件、examples/04 6 文件（含 ev-runs.log），报告不计数 |

统计：通过 31 项，部分 0 项，失败 1 项。

## 发现项

### R4-01 blocker：shell 包装的假复核命令仍可通过

- 文件：`scripts/check_evidence.py:1562-1581`
- 问题：检查器只拒绝 `echo`、`true`、`false`、`printf`、`cat` 和 `python -c`，没有限制 `sh -c`、`bash -c` 等其他任意 shell 包装。把自验收 07 的复跑命令改成 `sh -c 'echo "结果：5/5 通过"'`，输出仍写“结果：5/5 通过”，检查器在干净 worktree 中执行该命令，退出码 0、输出匹配，最终返回 `[OK] ...：6 行，结论=通过（通过 6）`，exit 0。
- 影响：第 10 项“独立复核”仍然可被伪造；矩阵 row 10 标为 done，但实际门禁无法区分“真实复跑”和“打印一句假输出”，属于核心阻断项。
- 修复要求：只允许白名单脚本/命令（例如 `python3 scripts/<已登记脚本>.py` 或 adapter `evidence_commands` 中的 EV 命令），拒绝任意 shell 包装和命令拼接；或把实际执行的命令、退出码、输出、时间、HEAD 由检查器生成并写入受控证据，而不是让复核人填写。新增 anti fixture：`sh -c`、`bash -c`、`python -c`、`echo` 四类假命令必须分别报 `E_REVIEW_COMMAND`。

## 已确认修复的 R3 项

- R3-02：`ev-runs.log` 已跟踪，进入 examples/04 manifest 和 07 证据行，干净克隆可见执行时间、HEAD、退出码和输出。
- R3-03：examples/04 README 明确完整 gate 需要 `--adapter tests/fixtures/valid-adapter.json --run`，默认 4/5 被明确标为“不是完整门禁”；矩阵、任务卡和 CHANGELOG 已同步。
- R3-04：矩阵 row 2/11/18 计数、examples/05 盘问行数、anti 42/42、05 gate 5/5 与实测一致。
- R3-05：doctor 对合法 adapter 输出 10/10，不再误报“证据命令 0 条”。
- R3-06：存在 round3 报告和本轮报告时 package 仍为 60/60；`package.py` 已用 `32-item-review*.md` 通配排除。

## 剩余风险

- 复核命令仍是“命令文本 + 表格输出”的信任边界；即使修复 `sh -c`，任意自有脚本仍可打印伪造输出，除非命令来源和输出由检查器生成/签名。
- `ev-runs.log` 的 HEAD 记录是首次执行时的 `f020d7a`，最终 `a5b67a3` 只改文档；后续若代码变更后重复 `--run`，去重逻辑不会更新旧 HEAD 记录，需避免把旧记录当作当前构建证据。
- `examples/04` 默认 gate 4/5 是设计上的“不完整门禁”，但用户若只复制默认命令仍可能误读；README 已提示，仍需在入门文档中保持显眼。
- 32 项矩阵 row 10 在本轮仍标 `done`，与 R4-01 的失败结论不一致，修复后应同步矩阵状态/证据。

## 证据路径

- 复核报告：`docs/reviews/32-item-review-round4.md`
- 干净克隆：`/tmp/verity-r4.clone`（`a5b67a3`）
- R3-01 伪造夹具：`/tmp/verity-r4-fx/docs/reviews/fakebatch/07-验收回归清单.md`（`sh -c` 包装命令，实测仍通过）
- R3-01 反例：`/tmp/verity-r4-fx/docs/reviews/fx-fake-output/07-验收回归清单.md`（真实命令 + 假输出，E_REVIEW_COMMAND）
- R3-01 反例：`/tmp/verity-r4-fx/docs/reviews/fx-py-c/07-验收回归清单.md`（`python3 -c`，E_REVIEW_COMMAND）
- 自验收证据包：`docs/reviews/2026-11-08-self-acceptance/`
- 示例：`examples/04-project-v1/`、`examples/05-release/`

结论：`needs_revision`。修复 R4-01 的 shell 包装假命令绕过，并补上对应的 anti fixture 后，再提交独立复核。
