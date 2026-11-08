# 第三轮独立复核报告（t8）

- 复核对象：t7 修复提交 `b60b207`（前序 `65808da` fix、`94d9cc2` test）
- 复核人：reviewer（独立复核，不参与实现）
- 工作目录：`/Users/dingliang/JavaProject/verity`
- 干净克隆：`/tmp/verity-r3.clone`（detached `b60b207`，工作区干净）
- 版本：`VERSION` = 1.3.0
- 结论：`needs_revision`（存在 2 个 blocker、1 个 high；不得放行）

## 结论摘要

t7 已实质修复 t2 的三个原始阻断项，也修复了第二轮的大部分问题：包上限恢复 60/60、自验收日志入 git、伪截图和全零 workspace_hash 被拒、CI 补上 `--team` 和反例夹具、适配层默认格式改为 v1、证据归属与返工字段有结构化校验。

但本轮仍发现两条可复现的绕过/自包含缺陷：独立复核的“复跑命令”只校验文本字段，命令根本没执行也能通过；`--run` 写入的 `ev-runs.log` 被 `.gitignore` 忽略且被 manifest 排除，执行时间、HEAD、输出不随证据包交付。另有 examples/04 默认 gate 与矩阵/说明不一致、文档计数漂移、doctor 对合法适配层的命令计数错误，因此结论必须是 `needs_revision`。

## 复核范围与方法

1. 在 `b60b207` 的独立克隆里跑全部自测、反例、示例和门禁，不采用工作区未提交状态。
2. 逐项核对 32 项的实现文件、模板、测试或夹具；不以矩阵文字代替实测。
3. 亲自执行 3 个 P0 负向夹具和 2 个正向样例，确认失败/通过原因。
4. 检查规则、模板、检查器、示例、CI 和文档计数的一致性，以及 clean-clone 可复现性。
5. 只写本报告，不修改任何实现文件。

## 关键命令读数

| 命令 | 读数 | 退出码 |
|---|---|---|
| `python3 scripts/selftest.py` | 5/5 通过 | 0 |
| `python3 scripts/anti_examples.py` | 41/41 按预期 | 0 |
| `python3 scripts/check_coverage.py --selftest` | 9/9 通过 | 0 |
| `bash tests/init-selftest.sh` | 6/6 通过 | 0 |
| `python3 scripts/package.py --check`（干净克隆，不含本轮报告） | 60/60，583.0 KB / 10.0 MB | 0 |
| `python3 scripts/package.py --check`（工作区含本轮未跟踪报告） | 61/60，597.1 KB / 10.0 MB | 1 |
| `python3 scripts/package.py --selftest` | 60 应过、70 应失败 | 0 |
| 自验收 `check_evidence.py` | 6 行，结论通过 | 0 |
| 自验收 `gate` | 5/5 | 0 |
| 自验收 `gate --team --release` | 6/6 | 0 |
| 自验收 `manifest --check` | 6 个文件一致，workspace_hash=849c46e… | 0 |
| `gate --ledger examples/05` | 5/5 | 0 |
| `gate --ledger examples/04`（无 adapter、无 --run） | 4/5；证据账本 FAIL：账本引用 EV 证据命令但未传 --run | 1 |
| `gate --ledger examples/04 --adapter tests/fixtures/valid-adapter.json --run` | 5/5 | 0 |
| `manifest --check examples/04` | 5 个文件一致，workspace_hash=5135fb2… | 0 |
| `gate --selftest` | 9 个 PASS（stderr 的 workspace_hash FAIL 是伪造清单负例） | 0 |
| `metrics --dir .` | 3 份真实账本、12 行、A 12、F1–F6 全 0 | 0 |
| `doctor --root .` | 5/5（适配层未找到为可选） | 0 |
| `doctor --adapter tests/fixtures/valid-adapter.json` | 8/9；`[FAIL] 证据命令：0 条` | 1 |
| `scan --root .` | 78 个文件，命中 0 项 | 0 |
| `scan --root . --release` | 78 个文件，命中 0 项 | 0 |

P0 负向夹具（均为独立副本、本人执行、单点变异）：

| 夹具 | 读数 | 退出码 |
|---|---|---|
| 04 任务卡硬触发由“无”改为“发布”，车道仍轻验收 | `[E_TASK_LANE] 硬触发命中“发布”，必须走全流程车道`，仅 1 项错误 | 1 |
| 05 证据身份 workspace_hash 改为 64 个 0 | `[E_WORKSPACE_CHANGED] README.md 的 workspace_hash 与当前工作区不一致`，仅 1 项错误 | 1 |
| clone 根目录新增未声明 `scope-probe.txt` 后跑 gate | `[FAIL] 范围锁：改动未在范围锁“做”中声明：scope-probe.txt` | 1 |
| `examples/04/bad-fake-screenshot/07` | `[E_SCREENSHOT] EV-01 的证据类型是截图，但没有可读的截图文件`，仅 1 项错误 | 1 |

正向样例：examples/05 gate 5/5；examples/04 使用 `tests/fixtures/valid-adapter.json --run` 后 gate 5/5；examples 01–05 的 `check_evidence.py` 分别为 3/4/4/1/5 行，全部 exit 0。

## 32 项逐项结论

| # | 项目 | 结论 | 依据 |
|---|---|---|---|
| 1 | 快慢车道与风险分级 | 通过 | 硬触发负向夹具命中 E_TASK_LANE；全流程示例通过 |
| 2 | 立卡前 grill | 通过 | 检查器要求 5–10 条，examples/05 已补到 5 行 |
| 3 | 一页规格与决策记录 | 通过 | examples/05 六字段齐全；反例可报 E_SPEC_LITE |
| 4 | 判据可判性 lint | 通过 | 模糊判据负向夹具命中 E_CRITERION |
| 5 | AC、旅程、账本三向映射 | 通过 | examples/04、05 通过；anti 的未映射夹具失败 |
| 6 | 范围锁与工作区干净 | 通过 | 未跟踪文件使 gate 报范围锁失败 |
| 7 | 证据命令执行 | 部分 | 能执行白名单并记录，但 `ev-runs.log` 被忽略、未进 manifest（R3-02） |
| 8 | 产物与环境身份 | 通过 | SHA-256、字节数、workspace_hash、截图像素均实算 |
| 9 | 旧证据失效 | 通过 | 全零 workspace_hash 报 E_WORKSPACE_CHANGED；旧构建有夹具 |
| 10 | 独立复核强制 | 失败 | 伪造复跑命令和输出仍通过（R3-01） |
| 11 | 完成线闸门 | 部分 | 自验收和 05 通过；examples/04 默认 gate 4/5（R3-03） |
| 12 | 防绕过 | 通过 | `gate --selftest` 覆盖删断言、skip、越界、伪造清单；CI 已带 `--team` |
| 13 | 完成审计结构化 | 通过 | examples/04、05 每条 AC 有场景/构建/读数/证据 |
| 14 | 旅程卡强制与负路径 | 通过 | 3–7 步、每卡≥3 不变量、跨区域和异常分支有检查 |
| 15 | 阻塞举证单结构化 | 通过 | examples/03 通过；空举证反例失败 |
| 16 | 发布风险与 PR 摘要 | 通过 | `report --kind pr` 输出结论/证据/风险回滚 |
| 17 | 复盘与 F 类统计 | 通过 | metrics 输出 F1–F6、复核发现、返工、周期中位数 |
| 18 | 红队夹具 | 通过 | anti_examples 41/41 |
| 19 | 技能写作与计数一致 | 部分 | 版本/60/41 大体一致，但矩阵仍有 3 行/4/4 旧计数（R3-04） |
| 20 | 术语表与判级校准 | 通过 | 证据等级 A/B+/B/C 可解析，非法等级有错误码 |
| 21 | 版本迁移与 schema | 通过 | 八列 legacy 被明确拒绝，十列迁移有提示 |
| 22 | 适配层预检 | 部分 | 无适配层 5/5；合法 `valid-adapter.json` 被 doctor 判 8/9（R3-05） |
| 23 | 多代理任务图 | 通过 | 证据归属段和 task_id/agent_id/claimed_at 已强制 |
| 24 | 度量 | 通过 | 结构化返工字段已使用，metrics 自测通过 |
| 25 | 安全与脱敏扫描 | 通过 | 默认 WARN、--release 阻断；本轮 0 命中 |
| 26 | 专项证据结构化 | 通过 | 截图、性能、DB before/after 均有结构校验 |
| 27 | 交接摘要 | 通过 | handoff 含证据路径、状态和下一步 |
| 28 | 修缺陷的紧反馈回路 | 通过 | bad-fake-screenshot 现在只报 E_SCREENSHOT |
| 29 | 自验收 | 部分 | 自验收 check/gate 通过，但 task-card 仍写 04 5/5、05 4/4 |
| 30 | 取证通道正对照预检 | 通过 | 配置通道时正对照 exit 0、负对照非 0 |
| 31 | 两层汇报 | 通过 | 第一层三行不含 ID/路径/术语，第二层给证据 |
| 32 | 证据包自包含 | 部分 | 自验收 manifest 6 文件通过；examples/04 的 ev-runs.log 未纳入（R3-02），本轮报告计入 package（R3-06） |

统计：通过 25 项，部分 6 项，失败 1 项。

## 发现项

### R3-01 blocker：独立复核命令可以伪造，检查器不执行

- 文件：`scripts/check_evidence.py:1518-1534`
- 问题：`check_independent_review` 只检查“复跑命令”非空、不是 echo/true、退出码文本为 0、输出摘要非空、时间格式合法；它不执行命令，也不核对输出。复核人写一条不会实际运行的命令和任意输出，仍会被判为通过。
- 复现：把自验收 07 的 AC-05 复核行改为 `python3 -c "print('fabricated')"`，输出改为 `fabricated`，其余字段不变；执行 `python3 scripts/check_evidence.py docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md`，返回 `[OK] ...：6 行，结论=通过（通过 6）`，exit 0。
- 影响：第 10 项“执行者≠复核者、复核人至少复跑一条 A 级命令”可以被文字绕过；这是“假通过”路径，属于本轮不得放行的核心阻断项。
- 修复要求：在干净 worktree 真正执行复核命令，捕获并核对退出码/stdout/stderr/时间/HEAD；或要求复核行引用已执行的 EV-run 记录并校验其哈希。新增 anti fixture：伪造复跑命令必须失败。

### R3-02 blocker：`--run` 的执行记录不随证据包交付

- 文件：`scripts/check_evidence.py:2923`、`scripts/verity.py:688`、`.gitignore:27`
- 问题：`run_evidence_commands` 把执行时间、HEAD、退出码和输出追加到 `evidence/ev-runs.log`；该文件被 `.gitignore` 的 `*.log` 忽略，`collect_batch_files` 又显式排除 `ev-runs.log`，因此它不会进 manifest，也不会被 07 证据行引用。干净检出里看不到任何一次 `--run` 的历史记录。
- 复现：`git check-ignore -v examples/04-project-v1/evidence/ev-runs.log` 指向 `.gitignore:27:*.log`；`git ls-files examples/04-project-v1/evidence/` 为空；执行 `gate --adapter tests/fixtures/valid-adapter.json --run` 后 `manifest --check examples/04` 仍只报告 5 个文件，manifest 中没有 `ev-runs.log`。
- 影响：第 7 项要求的“捕获退出码/stdout/stderr/时间/git SHA”只存在于本地临时文件；第 32 项要求的证据包自包含不成立。这与 t2 的 F-02“被 ignore 的日志未入 git”是同一类问题。
- 修复要求：把运行记录写入受控、可跟踪的证据文件并纳入 manifest 和 07 证据行；或 force-add 该日志并移除忽略规则。新增 clean-clone 检查：证据包必须包含运行记录。

### R3-03 high：examples/04 的默认 gate 为 4/5，文档却写 5/5

- 文件：`examples/04-project-v1/README.md:35`、`docs/optimization-matrix.md:18`、`docs/reviews/2026-11-08-self-acceptance/task-card.md:90,104`
- 问题：examples/04 的 07 引用 EV-01，`gate` 在没有 adapter 和 `--run` 时必然在证据账本步骤失败；但 README 说“本示例不依赖适配层”，矩阵写“gate 跑 examples/04 为 5/5”，自验收任务卡也写 04 5/5。只有 `--adapter tests/fixtures/valid-adapter.json --run` 才得到 5/5。
- 复现：`gate --root . --ledger examples/04...` → 4/5，exit 1；加 `--adapter tests/fixtures/valid-adapter.json --run` → 5/5，exit 0。
- 影响：用户按矩阵或任务卡执行完成线会直接失败；示例的“正向样例”与默认命令口径不一致。
- 修复要求：统一文档和示例命令，明确 examples/04 需要 adapter + `--run`；或为示例提供默认可发现的适配层，使默认 gate 5/5。CI 已使用 adapter+run，应同步矩阵、README、任务卡和 CHANGELOG。

### R3-04 medium：矩阵/文档计数漂移

- 文件：`docs/optimization-matrix.md:9,18`、`CHANGELOG.md:29`、`docs/reviews/2026-11-08-self-acceptance/task-card.md:90`
- 问题：矩阵 row 2 仍写 examples/05 盘问“3 行”，实际已是 5 行；矩阵 row 11、CHANGELOG、自验收任务卡仍写 examples/05 gate “4/4”，实际是 5/5；矩阵 row 7 声称自验收日志记录 `--run` 读数，但日志第 63 行记录的是“未传 --run”的失败，不是成功执行记录。
- 影响：32 项矩阵的“测试/证据”列不再是当前可复跑事实，复核人无法按矩阵直接复现。
- 修复要求：按当前输出重写这些计数，并把矩阵证据列改为可直接执行的命令；增加文档计数测试或 CI 校验。

### R3-05 medium：doctor 对合法适配层误报“证据命令 0 条”

- 文件：`scripts/verity.py:1029`、`tests/fixtures/valid-adapter.json`
- 问题：`cmd_doctor` 只统计 `adapter.get("commands")` 下的 static/contract/device/build，不读取 `evidence_commands`；而 `tests/fixtures/valid-adapter.json` 正是用 `evidence_commands` 配置 EV-01，且能被 `gate --run` 正常使用。执行 `doctor --adapter tests/fixtures/valid-adapter.json` 得到 8/9，`[FAIL] 证据命令：0 条`。
- 影响：合法的适配层会被预检判失败；doctor 与 gate/check_evidence 的适配层 schema 不一致。
- 修复要求：doctor 同时统计/校验 `commands` 与 `evidence_commands`，或统一适配层字段；新增“合法 adapter 的 doctor 应通过”测试。

### R3-06 medium：本轮复核报告被 package 计入，交付时 61/60

- 文件：`scripts/package.py:54-64`
- 问题：排除列表只精确列出 `docs/reviews/32-item-review.md`、`32-item-verification.md`、`32-item-review-round2.md`，没有覆盖本轮 `32-item-review-round3.md`。工作区只有这份未跟踪报告时，`package.py --check` 报 `文件数：61 / 60`、exit 1；干净克隆（不含报告）才是 60/60。
- 影响：复核报告是合同要求的交付物，但一提交就会让打包门禁失败；第 32 项“证据包自包含”与“技能包 60 文件上限”互相冲突。
- 修复要求：用 `docs/reviews/32-item-review*.md` 通配排除所有复核报告，或把复核报告移出技能包目录；增加 package 自测覆盖“存在复核报告仍为 60/60”。

## 已确认修复的原始阻断项

- t2 F-01：`package.py` 已恢复 60/60，`--selftest` 验证 60 应过、70 应失败。
- t2 F-02：自验收 `04-verification.log` 已入 git，manifest 6 个文件通过，干净克隆 gate 5/5。
- t2 F-03：ASCII 伪截图报 E_SCREENSHOT；全零 workspace_hash 报 E_WORKSPACE_CHANGED；伪造 manifest.workspace_hash 被 gate selftest 识别。
- R2-01/R2-02：examples/04 manifest 已重生成，自验收计数已改为 60/41/6，init 6/6；但 R3-03/R3-04 仍有文档计数漂移。
- R2-03：CI 已加 `--team`、anti_examples、init-selftest、examples/04 adapter+run、examples/05 gate、package selftest。
- R2-05/R2-06/R2-08/R2-09/R2-10/R2-11/R2-12：grill 下限 5、适配层默认 v1、init 6/6、证据归属强制、返工字段结构化、伪截图隔离、绝对路径清理均已验证。

## 剩余风险

- 复核命令仍是“文本自证”，不是可执行证据；本轮 R3-01 未修复前，任何“独立复核通过”都可能被伪造。
- `ev-runs.log` 被忽略且不进 manifest，证据包无法证明命令何时、在哪个 HEAD 上执行。
- 本轮复核报告本身会被 package 计入（61/60），交付前必须排除或移出。
- examples/04 的默认 gate 与文档不一致，用户按矩阵复跑会得到 4/5。
- 矩阵和 CHANGELOG 的旧计数会继续误导下一轮复核。
- doctor 对合法 adapter 误报，可能让接入方在预检阶段放弃正确配置。

## 证据路径

- 复核报告：`docs/reviews/32-item-review-round3.md`
- 干净克隆：`/tmp/verity-r3.clone`（`b60b207`）
- 伪复核夹具：`/tmp/verity-r3-fx`（自验收 07 的 AC-05 复跑命令被替换后仍通过）
- 负向夹具：`/tmp/verity-r3-neg`（硬触发）、`/tmp/verity-r3-neg2`（全零 workspace_hash）
- 自验收证据包：`docs/reviews/2026-11-08-self-acceptance/`
- 示例：`examples/04-project-v1/`、`examples/05-release/`

结论：`needs_revision`。修复 R3-01、R3-02 两个 blocker，并处理 R3-03 至 R3-06 后再提交独立复核。
