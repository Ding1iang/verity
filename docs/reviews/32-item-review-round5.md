# 第五轮针对性复核报告（t12）

- 复核对象：t11 修复提交 `d3beb30c20a21d022b9e006c9801f6292a3182af`（`fix: 独立复核绑定 EV 执行记录`）
- 复核人：reviewer（独立复核，不参与实现）
- 工作目录：`/Users/dingliang/JavaProject/verity`
- 干净克隆：`/tmp/verity-r5.ZHDb81/clone`（detached `d3beb30`，工作区干净）
- 版本：`VERSION` = 1.3.0
- 结论：`needs_revision`（存在 1 个 blocker、1 个 high；不得放行）

## 结论摘要

R4-01 的命令执行漏洞已实质修复：复核命令只能填写 EV ID，检查器从 `evidence/ev-runs.log` 读取记录并重算输出 SHA-256；`sh -c`、`bash -c`、`python -c`、`echo` 和旧 HEAD/早于取证时间/伪造哈希的夹具均报红，合法 EV-01/真实命令通过。

但自验收证据仍有最终提交绑定问题：`07-验收回归清单.md` 的“被测版本”和全部复核行仍写 `a5b67a3`，证据日志头部也写 `a5b67a3`；而本轮最终提交 `d3beb30` 修改了 `scripts/check_evidence.py`、`scripts/anti_examples.py` 等实现文件。`check_evidence.py` 只要求 commit 是 HEAD 的祖先，没有要求它就是最终被测提交，所以这份证据在最终提交上仍能通过，不能证明最终提交重新验收过。另有 README 的 pre-push 示例漏传 adapter 和 `--run`，按文档复制会直接失败。

## 复核范围与方法

1. 在 `d3beb30` 的独立克隆中复跑 t11 的 verify、自验收检查、gate、manifest、doctor、init 和 package。
2. 用 `sh -c 'echo "结果：5/5 通过"'` 复现第四轮 R4-01；再测合法 `EV-01` 和 `python3 scripts/selftest.py`。
3. 检查 EV 绑定实现：EV ID、`exit`、`head`、`time`、`output_sha256` 是否逐项校验，而非只加 `sh -c` 黑名单。
4. 生成伪命令、伪哈希、旧 HEAD、早于取证时间四个负向夹具；用自验收 07 和 examples/04、05 做正向样例。
5. 检查 32 项矩阵、README/任务卡/CHANGELOG 的实际命令口径，以及最终提交的证据身份。
6. 只新增本报告，不修改实现文件，不改旧报告结论。

## 关键命令读数

| 命令 | 读数 | 退出码 |
|---|---|---|
| `python3 scripts/selftest.py` | 5/5 通过 | 0 |
| `python3 scripts/anti_examples.py` | 47/47 按预期 | 0 |
| `python3 scripts/check_coverage.py --selftest` | 9/9 通过 | 0 |
| `python3 -m py_compile scripts/*.py` | 无错误 | 0 |
| `python3 scripts/check_evidence.py examples/04-project-v1/07-验收回归清单.md` | 1 行，结论=通过 | 0 |
| `python3 scripts/check_evidence.py examples/05-release/07-验收回归清单.md` | 5 行，结论=通过 | 0 |
| `python3 scripts/package.py --check`（干净克隆） | 60/60，590.6 KB / 10.0 MB | 0 |
| `python3 scripts/package.py --check --max-files 60` | 60/60 | 0 |
| `git diff --check` | 无输出 | 0 |
| 自验收 `check_evidence.py` | 6 行，结论=通过 | 0 |
| 自验收 `gate`（无 adapter、无 --run） | 4/5；证据账本 FAIL：EV 命令未执行 | 1 |
| 自验收 `gate --adapter tests/fixtures/valid-adapter.json --run --team --release` | 6/6 | 0 |
| 自验收 `manifest --check` | 7 个文件一致，workspace_hash=f64b7cae… | 0 |
| `gate --ledger examples/04 --adapter tests/fixtures/valid-adapter.json --run` | 5/5 | 0 |
| `gate --ledger examples/05 --adapter tests/fixtures/valid-adapter.json --run` | 5/5 | 0 |
| `gate --selftest` | 9 个 PASS | 0 |
| `bash tests/init-selftest.sh` | 6/6 通过 | 0 |
| `doctor --root . --adapter tests/fixtures/valid-adapter.json` | 10/10 通过（0 commands，1 evidence_commands） | 0 |
| `package.py --selftest` | 60 应过、70 应失败 | 0 |
| `metrics --dir .` | 3 份真实账本、12 行、A 12、F1–F6 全 0 | 0 |

## R4-01 验证：EV 绑定和负向夹具

### 合法 EV-run

- 自验收 07 的 `独立复核` 段已从任意命令改成 `EV-01`；`evidence/ev-runs.log` 含 `time`、`head`、`ev`、`command`、`exit`、`output`、`output_sha256`、`summary`。
- 干净克隆中 `check_evidence.py` 返回 6 行全部通过，exit 0。
- `gate --adapter tests/fixtures/valid-adapter.json --run --team --release` 返回 6/6，exit 0。

### 负向夹具

以下夹具均从干净克隆复制，保持原 commit，检查器从夹具自己的 `evidence/ev-runs.log` 读取记录：

| 夹具 | 变异 | 实际结果 | 退出码 |
|---|---|---|---|
| `fx-sh` | 独立复核命令改为 `sh -c 'echo "结果：5/5 通过"'` | 13 项错误，含 `E_REVIEW_COMMAND`“复跑命令必须填 EV ID” | 1 |
| `fx-hash` | `ev-runs.log` 的 `output_sha256` 改为 64 个 0 | 6 项 `E_REVIEW_COMMAND`“输出哈希与记录内容不一致” | 1 |
| `fx-oldhead` | `ev-runs.log` 的 `head` 改为祖先 `ade4c86` | `E_REVIEW_COMMAND`“不是本批被测 commit”“复跑 HEAD 不一致” | 1 |
| `fx-early` | `ev-runs.log` 的 `time` 改为 2026-11-07 | `E_REVIEW_COMMAND`“早于批次生成日期”“复跑时间不一致” | 1 |

结论：R4-01 的“任意 shell 命令打印假输出”路径已封闭，且不是只加 `sh -c` 黑名单；检查器确实读取 EV 记录并校验哈希、HEAD 和时间。

## R3-02～R3-06 回归

- R3-02 通过：`git ls-files` 可见自验收和 examples/04 的 `evidence/ev-runs.log`；自验收 manifest 7 个文件、examples/04 manifest 6 个文件均一致；07 证据行引用 `ev-runs.log`。
- R3-03 通过：examples/04 README 区分“check_evidence 不依赖适配层”和“完整 gate 需要 adapter + --run”；默认 4/5 被明确标为“不是完整门禁”。
- R3-04 通过：矩阵 row 2 为 5 行盘问、row 18 为 47/47、row 11/CHANGELOG/task-card 的 examples/05 为 5/5，实测一致。
- R3-05 通过：`doctor --root . --adapter tests/fixtures/valid-adapter.json` 为 10/10，正确报告 0 条 commands、1 条 evidence_commands。
- R3-06 通过：干净克隆含 round3/round4 报告时 package 仍为 60/60；`32-item-review*.md` 通配排除。

## 最终提交证据绑定检查

### R5-01 blocker：自验收证据仍绑定 a5b67a3，未绑定最终 d3beb30

- `docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md:13`：`被测版本` 写 `commit：a5b67a3743bf261a7f917adc92af2de70ffdacb5`。
- 同一文件 `:47-52` 的 6 条 SA 行、`:76-81` 的 6 条复核行也全部写 `a5b67a3`。
- `docs/reviews/2026-11-08-self-acceptance/evidence/04-verification.log:3`：`代码 HEAD：a5b67a3743bf261a7f917adc92af2de70ffdacb5`。
- 最终提交 `d3beb30` 的实际 diff 包含 `scripts/check_evidence.py +329/-...`、`scripts/anti_examples.py +137/-...`、`scripts/package.py +2/-...` 等实现文件；`git diff --stat a5b67a3..d3beb30` 为 26 文件、+628/-238，不是纯文档提交。
- `scripts/check_evidence.py:2342-2349` 只校验 commit 是 HEAD 或 HEAD 的祖先；`:2445-2477` 只按 commit 日期/文件 mtime 判断旧证据，不检查 commit 与最终 HEAD 之间是否改过实现文件。因此自验收 07 在 `d3beb30` 上仍然通过，但证据实际来自 `a5b67a3`。
- 影响：最终提交的检查器、反例、打包逻辑没有对应的完整自验收证据；第 9 项“旧证据失效”和第 29 项“自验收”不能按最终提交成立。这是本轮不能给 pass 的主要原因。

### R5-02 high：README 的 pre-push 示例复制后直接失败

- `README.md:114-115` 的示例为：
  `python3 scripts/verity.py gate --root . --ledger docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md --release`
- 实测该命令在干净克隆中返回 4/5，`[FAIL] 证据账本：账本引用了 EV 证据命令，但 gate 未传 --run，命令未执行`，exit 1。
- 同一命令加 `--team --release` 仍为 5/6；只有加 `--adapter tests/fixtures/valid-adapter.json --run --team --release` 才是 6/6。
- 影响：用户按 README 的“可选 pre-push”复制 hook，推送前会被自己刚写的 gate 拦住；文档与最终实现不一致。修复应把示例改成 adapter + `--run`，并在 CI/测试中校验 README 命令。

### R5-03 low：自验收证据日志摘要省略了 adapter/--run

- `docs/reviews/2026-11-08-self-acceptance/evidence/04-verification.log:127` 写“自验收 gate `--release` 与 `--team --release`：6/6”。
- 同日志 `:58` 和 `:67` 的实际命令包含 `--adapter ... --run`；摘要如果被单独阅读，会再次误导用户使用不完整命令。
- 这是 R5-02 的同一根因，修复 README 时同步修正日志摘要。

## 32 项逐项结论

| # | 项目 | 结论 | 依据 |
|---|---|---|---|
| 1 | 快慢车道与风险分级 | 通过 | 硬触发负向夹具命中 E_TASK_LANE |
| 2 | 立卡前 grill | 通过 | 检查器要求 5–10 条，examples/05 为 5 行 |
| 3 | 一页规格与决策记录 | 通过 | examples/05 六字段齐全；反例可报 E_SPEC_LITE |
| 4 | 判据可判性 lint | 通过 | 模糊判据反例命中 E_CRITERION |
| 5 | AC、旅程、账本三向映射 | 通过 | examples/04、05 通过；anti 未映射夹具失败 |
| 6 | 范围锁与工作区干净 | 通过 | 未跟踪文件使 gate 报范围锁失败 |
| 7 | 证据命令执行 | 通过 | examples/04 `--run` 5/5；ev-runs.log 已跟踪并进入 manifest/07 |
| 8 | 产物与环境身份 | 通过 | SHA-256、字节数、workspace_hash、截图像素均实算 |
| 9 | 旧证据失效 | 失败 | 自验收仍以 a5b67a3 证据通过最终 d3beb30（R5-01） |
| 10 | 独立复核强制 | 通过 | EV-01 真实记录校验通过；sh/伪哈希/旧 HEAD/旧时间均报 E_REVIEW_COMMAND |
| 11 | 完成线闸门 | 通过 | 自验收 adapter+run 6/6；examples/04 adapter+run 5/5；默认命令已文档化 |
| 12 | 防绕过 | 通过 | gate --selftest 覆盖删断言、skip、越界、伪造清单 |
| 13 | 完成审计结构化 | 通过 | examples/04、05 每条 AC 有场景/构建/读数/证据 |
| 14 | 旅程卡强制与负路径 | 通过 | 3–7 步、每卡≥3 不变量、跨区域和异常分支有检查 |
| 15 | 阻塞举证单结构化 | 通过 | examples/03 通过；空举证反例失败 |
| 16 | 发布风险与 PR 摘要 | 通过 | report --kind pr 输出结论/证据/风险回滚 |
| 17 | 复盘与 F 类统计 | 通过 | metrics 输出 F1–F6、复核发现、返工、周期中位数 |
| 18 | 红队夹具 | 通过 | anti_examples 47/47 |
| 19 | 技能写作与计数一致 | 通过 | 版本 1.3.0、60/47/6 计数一致，doctor 文档计数通过 |
| 20 | 术语表与判级校准 | 通过 | A/B+/B/C 可解析，非法等级有错误码 |
| 21 | 版本迁移与 schema | 通过 | 八列 legacy 被拒绝，十列迁移有提示 |
| 22 | 适配层预检 | 通过 | 无适配层 6/6；合法 adapter 10/10 |
| 23 | 多代理任务图 | 通过 | 证据归属段与 task_id/agent_id/claimed_at 已强制 |
| 24 | 度量 | 通过 | 结构化返工字段和 metrics 自测通过 |
| 25 | 安全与脱敏扫描 | 通过 | 默认 WARN，--release 无命中；扫描 84 文件 0 项 |
| 26 | 专项证据结构化 | 通过 | 截图、性能、DB before/after 有结构校验 |
| 27 | 交接摘要 | 通过 | handoff 含证据路径、状态和下一步 |
| 28 | 修缺陷的紧反馈回路 | 通过 | bad-fake-screenshot 只报 E_SCREENSHOT |
| 29 | 自验收 | 部分 | check/gate/manifest 通过，但自验收证据绑定 a5b67a3，未绑定最终 d3beb30（R5-01） |
| 30 | 取证通道正对照预检 | 通过 | 通道正对照 exit 0、负对照非 0 |
| 31 | 两层汇报 | 通过 | 第一层三行不含 ID/路径/术语，第二层给证据 |
| 32 | 证据包自包含 | 通过 | 自验收 7 文件、examples/04 6 文件（含 ev-runs.log），manifest 通过 |

统计：通过 30 项，部分 1 项，失败 1 项。

## 发现项

### R5-01 blocker：最终提交没有对应的自验收证据

- 文件：`docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md:13`（以及 `:47-52`、`:76-81`）
- 问题：账本和全部复核行写 `a5b67a3`；最终提交 `d3beb30` 改动了 `scripts/check_evidence.py`、`scripts/anti_examples.py`、`scripts/package.py` 等实现文件，但自验收证据没有重跑到 `d3beb30`。检查器只要求 commit 是 HEAD 祖先，因此仍能通过。
- 影响：第 9 项旧证据失效和第 29 项自验收不能按最终提交成立；最终实现的行为没有被同版本的完整证据覆盖。
- 修复要求：把 `07` 的“被测版本”和全部 commit/复核 HEAD 更新为 `d3beb30`（或重新生成到最终提交）；重新生成 `evidence/04-verification.log`、`equipment/ev-runs.log`、`manifest.json` 并更新 SHA/字节/workspace_hash；检查器应拒绝“batch commit 与 HEAD 之间改过 scripts/templates/references 的旧证据”，而不只是校验祖先关系。

### R5-02 high：README pre-push 命令缺少 adapter 和 --run

- 文件：`README.md:114-115`
- 问题：示例命令只有 `--release`，没有 `--adapter tests/fixtures/valid-adapter.json --run`；在最终提交上实测 4/5，exit 1，报“账本引用了 EV 证据命令，但 gate 未传 --run，命令未执行”。
- 影响：用户复制文档中的 pre-push hook 后，推送前会被错误的完成线命令拦住；文档与实现不一致。
- 修复要求：把 README 示例改成 `--adapter tests/fixtures/valid-adapter.json --run`（需要团队/脱敏时再加 `--team --release`）；在 CI 或文档测试中执行该命令，防止再次漂移。

### R5-03 low：自验收日志摘要省略 adapter/--run

- 文件：`docs/reviews/2026-11-08-self-acceptance/evidence/04-verification.log:127`
- 问题：摘要写“gate `--release` 与 `--team --release`：6/6”，但同日志 `:58`、`:67` 的实际命令包含 adapter 和 `--run`；单独阅读摘要会误用不完整命令。
- 修复要求：摘要改成完整命令，或明确写“以下两条均带 adapter 与 --run”。

## 已确认修复的 R4-01

- `check_evidence.py` 的 `check_independent_review` 只接受 `EV-\d{2,3}`；从 `ev-runs.log` 读取执行记录，重算 `output_sha256`，并校验 `exit`、`head`、`time`、`summary`。
- `anti_examples.py` 已增加 `v2-review-bash-c`、`v2-review-echo`、`v2-review-python-c`、`v2-review-forged-hash`、`v2-review-old-head`、`v2-review-early-time` 等夹具，47/47 按预期。
- 自验收 07 的复核行已改为 `EV-01`；自验收 `check_evidence.py` 6 行通过，`gate --adapter ... --run` 6/6。

## 剩余风险

- 自验收证据和 examples 的 `被测版本` 均写 `a5b67a3`；若后续继续以 `d3beb30` 作为最终交付，所有“最终提交”表述都应以 `d3beb30` 重新取证。
- `ev-runs.log` 是本地 JSONL，检查器只能校验哈希、HEAD、时间与记录自洽；没有签名密钥时，仍无法从密码学上证明记录没有被重写。
- README 的 pre-push 是可选本地 hook，不是服务端强制；真正的强制线仍在 CI，但文档错误会直接造成用户失败。
- 32 项矩阵当前 32/32 标 done；本报告第 9、29 项与矩阵不一致，修复 R5-01 后应同步矩阵证据。

## 证据路径

- 复核报告：`docs/reviews/32-item-review-round5.md`
- 干净克隆：`/tmp/verity-r5.ZHDb81/clone`（`d3beb30`）
- 负向夹具：`/tmp/verity-r5-fx/fx-sh/`、`/tmp/verity-r5-fx/fx-hash/`、`/tmp/verity-r5-fx/fx-oldhead/`、`/tmp/verity-r5-fx/fx-early/`
- 正向样例：自验收 `docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md`；`examples/04-project-v1/`；`examples/05-release/`
- 自验收证据：`docs/reviews/2026-11-08-self-acceptance/evidence/04-verification.log`、`evidence/ev-runs.log`、`manifest.json`

结论：`needs_revision`。R4-01 已修复，但最终提交的自验收证据仍绑定旧提交 `a5b67a3`，且 README 的 pre-push 命令缺少 adapter 与 `--run`；修复 R5-01、R5-02 后重新提交独立复核。
