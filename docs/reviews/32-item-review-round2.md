# verity 32 项优化第二轮独立复核报告

- 复核对象：t5 repair 提交 `ef187d878fb2e474f3a33ed97a61ee7714248d33`
- 对照对象：t1 提交 `0752f36638ee8421764505ca17217c4c637e4f63`、t2 报告 `docs/reviews/32-item-verification.md`
- 复核人：t6 reviewer（未参与 t1 实现、未参与 t5 修复）
- 复核日期：2026-11-08
- 复核环境：干净克隆 `/tmp/verity-r2.jE1wKH/clone`，HEAD `ef187d8`；macOS，Python 3，标准库；未安装依赖、未联网、未改实现
- **结论：needs_revision（不接受，退回修复）**

## 0. 结论摘要

32 项中：通过 20 项，部分实现 11 项，失败 1 项。t2 的三个阻断项已有实质修复：package 恢复 60/60，干净克隆自验收 `gate` 5/5，伪截图/全零 workspace_hash/伪造 manifest 哈希均能被拒绝。

但仍有 2 个阻断项和 5 个 high 项未解决：

1. `examples/04` 的 manifest 已过期，`gate` 实测 4/5，但 CHANGELOG、矩阵和自验收任务卡都写“5/5 通过”。
2. 自验收文档与证据互相矛盾：任务卡写打包上限 70（实际 60）、anti 23/23（实际 37/37），07 完成审计写“5 个文件一致”（实际 6 个）；最终 HEAD ef187d8 也没有重新跑自验收。
3. CI 的 gate 未启用 `--team`，没有 pre-push，防绕过在 CI 默认关闭。
4. 第 7 项证据命令执行缺执行时间和 git SHA，`gate` 没有 `--run`。
5. 第 2 项 grill 仍只要求 3 条，清单要求 5–10 条。
6. adapter 未配置 `paths.ledger_template` 时默认按 legacy 解析，导致 `init` 生成的 v2 账本无法用 `--adapter` 检查。
7. 独立复核只校验“复跑命令”字符串和证据路径存在，不执行命令，无法防止假复跑。

放行条件：修复 R2-01、R2-02 两个阻断项，处理 R2-03 至 R2-07 的 high 项；在新提交上重新生成自验收证据并重跑干净克隆，再提交独立复核。

## 1. 复核范围与方法

已读：t1/t2 合同、`docs/reviews/32-item-verification.md`、`docs/optimization-matrix.md`、清单 `docs/2026-11-07-外部工作流对比与优化清单.md`、`SKILL.md`、`README.md`、`CHANGELOG.md`、`references/`、`templates/`、`scripts/`、`examples/01`–`05`、`docs/reviews/2026-11-08-self-acceptance/`。

方法：

- 逐项把清单要求映射到具体文件、函数/模板字段、测试或示例，不看矩阵的 `done` 字样代替证据。
- 正向：在干净克隆跑 5 个示例账本、`gate`、`selftest`、`anti_examples`、`check_coverage --selftest`、`init-selftest`、`py_compile`、`git diff --check`、`package --check`。
- 负向：在 `/tmp` 的 examples 副本上做单点变异，覆盖硬触发、模糊判据、伪截图、全零哈希、伪 manifest、范围外文件、单步旅程、缺完成审计。
- 可复现：使用 `git clone --no-hardlinks` 的干净克隆，不引用工作区未提交文件；所有读数取自 `ef187d8`。
- 绕过：检查 CI、pre-push、`--team` 默认值、证据命令执行、复核复跑、状态文本和证据路径的可伪造面。

## 2. 命令读数

以下均在干净克隆（HEAD `ef187d8`）执行：

| 命令 | 读数 | 退出码 |
| --- | --- | --- |
| `python3 scripts/selftest.py` | 5/5 通过 | 0 |
| `python3 scripts/anti_examples.py` | 37/37 夹具按预期 | 0 |
| `python3 scripts/check_coverage.py --selftest` | 9/9 通过 | 0 |
| `python3 scripts/package.py --check` | 60/60，576.8 KB / 10.0 MB，通过 | 0 |
| `python3 scripts/package.py --selftest` | 60 文件应通过、70 文件应失败，均 PASS | 0 |
| `check_evidence.py examples/01` | 3 行，结论=通过（通过 3） | 0 |
| `check_evidence.py examples/02` | 4 行，结论=通过（通过 4） | 0 |
| `check_evidence.py examples/03` | 4 行，结论=通过（通过 2、阻塞 1、不适用 1） | 0 |
| `check_evidence.py examples/04` | 1 行，结论=通过（通过 1） | 0 |
| `check_evidence.py examples/05` | 5 行，结论=通过（通过 5） | 0 |
| `verity.py gate --ledger self` | 5/5 通过 | 0 |
| `verity.py gate --team --release --ledger self` | 6/6 通过 | 0 |
| `verity.py gate --ledger examples/05` | 5/5 通过 | 0 |
| `verity.py gate --ledger examples/04` | 4/5，证据包清单失败：`字节数对不上：examples/04-project-v1/task-card.md` | 1 |
| `verity.py manifest --check self` | 6 个文件一致，workspace_hash=eb430371… | 0 |
| `verity.py manifest --check examples/04` | 5 项错误：07 SHA/字节、journey-01 tracked、task-card SHA/字节 | 1 |
| `bash tests/init-selftest.sh` | 3/4 通过，adapter fixture 缺 schema_version，task-card 未生成 | 1 |
| `verity.py gate --selftest` | 9 个 PASS，正负对照通过 | 0 |
| `verity.py metrics --dir .` | 3 份真实账本、12 行、A 12、A/B+/B/C=100%/0%/0%/0% | 0 |
| `verity.py scan`（临时明文凭据） | `[WARN]` | 0 |
| `verity.py scan --release`（同一文件） | `[FAIL]` | 1 |
| `verity.py doctor --root .` | 5/5（适配层未找到，可选） | 0 |
| 临时完整 adapter + `doctor` | 9/9，通道正对照 exit=0、负对照 exit=1 | 0 |

`gate --selftest` 的 stderr 会打印 `[FAIL] workspace_hash 与清单内的文件哈希重算结果不一致`，这是“伪造 manifest”负例的预期输出；标准输出 9 个 PASS，退出码 0。

## 3. 32 项逐项结论

状态口径：**通过**＝有具体实现且我复跑或读取到对应行为；**部分**＝主路径存在但清单的关键约束未完全落地；**失败**＝清单要求没有落地，或可用负向夹具绕过。

| # | 状态 | 复核依据（关键读数/缺口） |
| --- | --- | --- |
| 1 | 通过 | `check_task_card` 读取任务卡“硬触发”列；把 examples/04 改成“发布、数据安全、跨模块、多步用户旅程、难复现缺陷”且车道仍轻验收，仅报 `E_TASK_LANE`，exit 1。 |
| 2 | 部分 | 模板 `templates/task-card.md:40` 只要求“至少 3 条”，检查器 `check_evidence.py:1143` 只判 `useful < 3`；清单要求 5–10 条带推荐答案并写入用户决定。 |
| 3 | 通过 | spec-lite 六字段齐全，缺字段报 `E_SPEC_LITE`。 |
| 4 | 通过 | 判据 lint 有动作/可观察结果/阈值/样本范围/模糊词/豁免检查；把 AC-01 改成“功能可用”仅报 `E_CRITERION`，exit 1。 |
| 5 | 通过 | AC 覆盖、旅程步骤映射、每条 AC 至少一行账本；`E_COVERS`/`E_JOURNEY_STEP` 夹具命中，examples 04/05 正例通过。 |
| 6 | 通过 | `check_scope` 使用 do_paths + dont_paths + scope_exception；干净克隆根目录 `touch scope-probe.txt` 后 gate 报 `[FAIL] 范围锁：改动未在范围锁“做”中声明`，exit 1；删除后恢复。 |
| 7 | 部分 | `check_evidence --run` 能按白名单在 `git archive HEAD` 干净树执行，捕获退出码/stdout/stderr，失败报 `E_EVIDENCE_COMMAND`；但不记录执行时间、git SHA，且 `gate` 没有 `--run` 参数。 |
| 8 | 通过 | 证据身份实算 SHA-256/字节数，校验构建号、环境、日期；ASCII 文本改名为 `shot.png` 报两条 `E_SCREENSHOT`；全零 `workspace_hash` 报 `E_WORKSPACE_CHANGED`。 |
| 9 | 通过 | workspace_hash 与当前工作区指纹比对，工作区变化使旧证据失效；`E_STALE`/`E_STALE_TASKCARD` 反例命中。 |
| 10 | 部分 | 产出者≠复核者、逐 AC supports、至少一条 A 级复跑有校验；但“高风险必须新会话/独立代理”无法验证，复跑命令也不实际执行。 |
| 11 | 部分 | `gate` 存在且自验收 5/5、`--team --release` 6/6；CI 只跑 self `gate --release`，不跑 examples/04、05 的 gate，也没有 pre-push。 |
| 12 | 通过 | `gate --selftest` 覆盖删断言、skip/focus、`--no-verify`、策略基线；防绕过功能本身可用，但 CI 未启用 `--team`（见 R2-03）。 |
| 13 | 通过 | 完成审计每条 AC 至少一行，要求场景/命令/最终构建/读数/真实证据路径；缺段报 `E_STRUCTURE`，examples/04 删段夹具 exit 1。 |
| 14 | 通过 | 旅程卡要求 3–7 步、每卡≥3 条不变量、跨区域≥3 张卡、高风险异常分支、每步映射 07；单步/八步/单不变量/区域不足夹具均命中。 |
| 15 | 通过 | 阻塞举证单四维、每维“试了什么+读数”、能力类正对照、解锁条件齐全；空举证夹具报 `E_BLOCKING_FORM`。 |
| 16 | 通过 | `report --kind pr` 输出结论/旅程/验收项、证据、风险/回滚/验证三行；`templates/07` 有发布风险段。 |
| 17 | 通过 | `templates/07` 复盘表含 F1–F6、次数、根因、规则/模板改动；`metrics` 能解析 F 计数。 |
| 18 | 部分 | `anti_examples.py` 37/37 按预期报错，坏样本和正例都存在；但 CI 不运行 `anti_examples.py`，只跑四个示例的 `check_evidence`。 |
| 19 | 部分 | SKILL/README/CHANGELOG 的版本、13 列、6 模板、四条硬规则、37 反例基本一致；自验收任务卡仍写“70 / 10 MB”“anti 23/23”，计数真相源不一致。 |
| 20 | 通过 | `references/evidence.md` 有术语表、A/B+/B/C 口径、每级正反例；非法等级报 `E_EVIDENCE_LEVEL`。 |
| 21 | 通过 | 任务卡/07 有 schema_version；`upgrade` 对八列 legacy 明确拒绝并给出迁移说明；adapter 有 schema_version 版本检查。 |
| 22 | 部分 | `doctor --root .` 5/5；完整 adapter 9/9，通道正负对照可用；但无 adapter 时 5/5 不覆盖 Python 版本、路径权限和命令实际执行，`init-selftest` fixture 也仍失败。 |
| 23 | 部分 | 模板有 task_id/agent_id/claimed_at；检查器只在“证据归属”段存在时校验，整段缺失直接返回（`check_evidence.py:1741-1743`）；examples/04、05 都没有该段，矩阵第 23 行所称“examples/05 写本批单代理”不成立。 |
| 24 | 部分 | `metrics` 输出账本数、行数、等级比例、F 类、复核发现、周期中位数；`rework` 只是全文 `text.count("返工")`，会把“本批无返工”也计为返工，不是结构化次数。 |
| 25 | 通过 | `scan` 默认 `[WARN]` exit 0，`--release` 对命中项 `[FAIL]` exit 1。 |
| 26 | 通过 | 截图要求 viewport/pixel_hash 且实际解析 PNG/JPEG；性能要求 runs/median，DB 要求 before/after；伪截图夹具报红。 |
| 27 | 通过 | `report --kind handoff` 含当前结论、用户旅程、账本、证据路径、状态计数、未完成项和下一步。 |
| 28 | 通过 | 紧反馈回路有 `examples/02` 复跑和 `gate --selftest` 正负对照；坏样本可秒级变红；但 `bad-fake-screenshot` 夹具隔离性不足（见 R2-11）。 |
| 29 | 失败 | 干净克隆自验收 `gate` 5/5 本身通过，但自验收文档/证据不一致：任务卡写 70/23、07 写 5 个文件、证据日志按 e620d54 取证，最终 HEAD ef187d8 未重跑；`init-selftest` 实际 3/4 失败，07 完成审计却写“通过”。 |
| 30 | 部分 | 有 adapter 且配置 `evidence_channels` 时，doctor 9/9、正对照 exit 0、负对照 exit 1；仓库默认无 adapter，`doctor --root .` 直接跳过通道检查，不能证明开工资质。 |
| 31 | 通过 | `report --kind two-layer` 第一层三行，只讲结论/条数/下一步；第二层才列账本、旅程、状态、证据。 |
| 32 | 部分 | 自验收 manifest 6 个文件、workspace_hash 校验通过；`examples/04` 的 manifest 5 项错误、gate 4/5，说明至少一个随包示例的证据包不自包含。 |

## 4. 发现项

### R2-01（blocker）examples/04 的 manifest 已过期，完成线 gate 实测 4/5

- 问题：`examples/04-project-v1/manifest.json` 记录的 07 字节数 2990（实际 3075）、task-card 字节数 1491（实际 1514），journey-01 写成 `tracked=false` 但实际已被 git 跟踪；`manifest --check` 报 5 项错误，`gate` 唯一失败为证据包清单。CHANGELOG、矩阵和自验收任务卡却写“examples/04 gate 5/5”。
- 证据：`python3 scripts/verity.py manifest --root . --ledger examples/04-project-v1/07-验收回归清单.md --check` 输出 5 个 `[FAIL]`，exit 1；`gate` 输出 `[FAIL] 证据包清单：字节数对不上：examples/04-project-v1/task-card.md`，`结果：失败（4/5）`。
- 修复要求：重新生成并提交 `examples/04-project-v1/manifest.json`；更新 `CHANGELOG.md:29`、`docs/optimization-matrix.md:18`、自验收 `task-card.md:88` 的 5/5 表述；CI 增加 examples/04 的 `gate`（不是只跑 `check_evidence`），并保留 60 文件上限。
- 文件/行：`examples/04-project-v1/manifest.json:7-40`；`CHANGELOG.md:29`；`docs/optimization-matrix.md:18`；`docs/reviews/2026-11-08-self-acceptance/task-card.md:88`。

### R2-02（blocker）自验收文档、证据和最终提交不一致

- 问题：自验收任务卡写“打包 70 / 10 MB”“anti 23/23”，实际 package 60/60、anti 37/37；07 完成审计 AC-04 写“5 个文件一致”，实际 manifest 6 个文件；07 的完成审计 AC-02 写 `init-selftest` “通过”，实测 3/4 失败。证据日志声明取证基于 e620d54，最终 HEAD ef187d8 只改了 docs/manifest/log，没有在新提交上重跑自验收。
- 证据：`package.py --check` 60/60；`anti_examples.py` 37/37；`manifest --check self` 6 个文件；`bash tests/init-selftest.sh` 3/4、exit 1；`git show --stat ef187d8` 为 5 个 docs/manifest/log 文件。
- 修复要求：修正任务卡第 89、104 行和 07 第 61、63 行；在最终提交上重跑全部自验收命令并重新生成 `evidence/04-verification.log` 与 manifest；以最终 HEAD 为 commit 列；在报告里只写实测读数，不得把 3/4 写成通过。
- 文件/行：`docs/reviews/2026-11-08-self-acceptance/task-card.md:89`、`:104`；`docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md:61`、`:63`；`docs/reviews/2026-11-08-self-acceptance/evidence/04-verification.log`。

### R2-03（high）CI 默认关闭防绕过，且没有 pre-push

- 问题：CI 的 gate 只跑 `--release`，没有 `--team`；`verity.py gate` 的防绕过是显式 `--team` 才启用。删除断言、加 `skip`/`focus`、`--no-verify` 这类改动在 CI 默认不会报红；仓库也没有 pre-push 钩子。
- 证据：`.github/workflows/ci.yml:46-51` 的 gate 参数只有 `--root`、`--ledger`、`--release`；`scripts/verity.py:1618-1625` 的 `--team` 是可选开关；`gate --selftest` 的负对照证明只有启用防绕过时才识别。
- 修复要求：CI 的 gate 加 `--team`；增加 `anti_examples.py` 步骤；提供并文档化 pre-push 钩子（或 CI 对 PR diff 强制执行同一检查）；补一个“删断言/加 skip 的 PR 必须失败”的端到端夹具。
- 文件/行：`.github/workflows/ci.yml:38-51`；`scripts/verity.py:1618-1625`。

### R2-04（high）第 7 项证据命令缺执行时间/git SHA，gate 不自动执行

- 问题：`run_evidence_commands` 能执行白名单命令并捕获退出码/stdout/stderr，但不记录执行时间、git SHA，也不把执行结果写入账本；`gate` 没有 `--run` 参数，因此完成线只做静态检查，不能保证证据命令真的跑过。
- 证据：`scripts/check_evidence.py:2793-2825` 只有 `subprocess.run`、输出 tail 和 `[OK]`/`E_EVIDENCE_COMMAND`，没有时间/SHA 字段；`scripts/verity.py:1618-1625` 的 gate 参数无 `--run`。成功/失败/白名单三个 anti 夹具能过，但只覆盖执行器本身。
- 修复要求：在 EV 记录中写入执行时间、HEAD SHA、退出码、stdout/stderr 摘要；`gate --run` 或 `gate --team` 自动执行并阻断失败；账本证据行引用 EV ID；补“gate 不跑命令时必须失败”的夹具。
- 文件/行：`scripts/check_evidence.py:2793-2825`；`scripts/verity.py:1618-1625`；`docs/optimization-matrix.md:14`。

### R2-05（high）第 2 项 grill 只要求 3 条，清单要求 5–10 条

- 问题：模板写“至少记录 3 条”，检查器只判 `useful < 3`；`examples/05` 实际也只有 3 行。清单要求立卡前 5–10 问、带推荐答案、用户决定入卡，当前实现没有满足数量下限。
- 证据：`templates/task-card.md:40`；`scripts/check_evidence.py:1136-1145`；`examples/05-release/task-card.md` 的“立卡前盘问”3 行。
- 修复要求：模板改成 5–10 行结构；检查器要求 5–10 条且每条有问题、推荐答案、用户决定；examples/05 补到至少 5 条；加“只有 3 条必须失败”的反例。
- 文件/行：`templates/task-card.md:40`；`scripts/check_evidence.py:1136-1145`；`docs/optimization-matrix.md:9`。

### R2-06（high）adapter 无 ledger_template 时默认 legacy，与文档和 init 不一致

- 问题：`references/adapter.md:45` 明确写“留空则用 verity 仓库的 v1 schema 2 十三列模板”；但 `adapter_context` 在无 `paths.ledger_template` 时把 `fmt` 初始化为 `legacy`，不会根据模板 marker 自动识别。实测完整 adapter + `init` 生成 v2 账本后，`check_evidence --adapter` 报 `[E_STRUCTURE] 缺少“## 账本”段`。
- 证据：`scripts/check_evidence.py:2661-2672`；临时 adapter 的 `init` 生成 task-card/journey/07 成功，但随后 `check_evidence --adapter` exit 1；报错为缺少“## 账本”段。
- 修复要求：无 template 时默认 v1（或读取 init 使用的模板 marker 自动判定）；补“无 ledger_template 的 adapter + init + check_evidence”回归测试，要求 exit 0；文档与代码保持一致。
- 文件/行：`references/adapter.md:45`；`scripts/check_evidence.py:2661-2672`。

### R2-07（high）独立复核只校验文本，不执行复跑命令

- 问题：`check_independent_review` 只检查复核行有非空“复跑命令”、证据路径存在、逐 AC 有 supports；它不执行命令、不核对退出码，也不要求命令输出。复核人可以写一个假命令或指向旧日志，仍能通过格式检查。
- 证据：`scripts/check_evidence.py:1524-1542` 只构造 `command_rows` 并检查非空/A 级交集；examples/04 的复跑证据是 `README.md`，不是命令输出。
- 修复要求：至少记录复跑命令的退出码/stdout 摘要/执行时间，或让 `gate --team` 执行复核命令；补“假复跑命令/指向旧日志”反例。
- 文件/行：`scripts/check_evidence.py:1524-1542`；`templates/07-acceptance.md` 独立复核段。

### R2-08（medium）init-selftest 的 adapter fixture 过旧，测试 3/4 失败

- 问题：`tests/init-selftest.sh:159` 只写 `{"schema":"verity-adapter/v1","project":{"name":"演示项目"}}`，缺 `schema_version`、`min_verity_version` 等必填字段；当前 strict `read_adapter` 直接拒绝，`init` 退出 2，task-card 未生成，测试报“模式未带入”“adapter 字段带入”失败。
- 证据：`bash tests/init-selftest.sh` → 3/4，exit 1；错误为 `adapter.schema_version 必须是 1..1 的整数`；CI 没有运行该脚本。
- 修复要求：fixture 补全合法 adapter 字段；加入 CI；测试应覆盖“合法 adapter 成功 + 缺字段失败”两条路径。
- 文件/行：`tests/init-selftest.sh:155-184`。

### R2-09（medium）证据归属段缺失时直接放行，examples 也没有归属段

- 问题：`check_evidence_ownership` 在找不到“## 证据归属”段时 `return`，不判断批次是否多代理；一个多代理批次只要完全不写该段就能绕过。`examples/04`、`examples/05` 都没有该段，矩阵第 23 行却称 examples/05 写了“本批单代理”。
- 证据：`scripts/check_evidence.py:1741-1743`；`grep -n "证据归属" examples/04... examples/05...` 无结果；`docs/optimization-matrix.md:30`。
- 修复要求：从任务卡/批次信息读取协作模式，多代理批次强制要求归属表；单代理批次也要写明确说明；examples 补段；修正矩阵。
- 文件/行：`scripts/check_evidence.py:1733-1743`；`docs/optimization-matrix.md:30`。

### R2-10（medium）metrics 的返工次数是全文词频，不是结构化计数

- 问题：`ledger_summary` 用 `text.count("返工")` 统计返工次数；账本里写“本批无返工”也会计为 1，写多次同义说明会重复计数，不能作为批次度量。
- 证据：`scripts/verity.py:1341`；当前 3 份账本读数 `rework=0`，但没有反例证明“无返工”不会被误计。
- 修复要求：在复盘/批次信息中增加结构化返工字段（次数、原因、任务 ID），解析该字段；补“无返工文本必须为 0”的反例。
- 文件/行：`scripts/verity.py:1341`。

### R2-11（low）bad-fake-screenshot 夹具不是单点错误，矩阵却称只报一个

- 问题：`examples/04/bad-fake-screenshot/07` 实测 4 项错误（`E_SCHEMA`、`E_COMMIT`、`E_SCREENSHOT`、`E_WORKSPACE_CHANGED`），不是只命中截图规则；`docs/optimization-matrix.md:35` 却写“只报一个目标错误”。这削弱了“坏样本只违反目标规则”的隔离性。
- 证据：`python3 scripts/check_evidence.py examples/04/bad-fake-screenshot/07-验收回归清单.md` → 4 项错误，exit 1。
- 修复要求：把夹具修成只违反截图规则（或更新矩阵说明为多错误样本）；保证目标错误码可单独归因。
- 文件/行：`docs/optimization-matrix.md:35`；`examples/04/bad-fake-screenshot/07-验收回归清单.md`。

### R2-12（low）自验收证据日志含本机绝对路径

- 问题：`docs/reviews/2026-11-08-self-acceptance/evidence/04-verification.log` 含 `/Users/dingliang/JavaProject/verity/...` 绝对路径；该日志随包发布，属于项目/本机痕迹，不利于可移植性。
- 证据：日志第 12、67、87、92、97 行等均含绝对路径。
- 修复要求：取证时使用相对路径或脱敏规则；重新生成日志和 manifest，确认包内无绝对路径。
- 文件/行：`docs/reviews/2026-11-08-self-acceptance/evidence/04-verification.log:12`。

## 5. 已确认修复的 t2 阻断项

- t2 F-01：package 上限已恢复 60；`package.py:4/27/207` 均为 60，干净克隆 60/60 通过，`--selftest` 的 70 文件负例失败。
- t2 F-02：自验收证据已入 git；干净克隆 `check_evidence` 6 行通过、`gate` 5/5、manifest 6 文件通过。
- t2 F-03：伪截图、全零 workspace_hash、伪造 manifest 哈希均已被拒绝；`anti_examples.py` 中 `v2-ascii-image`、`v2-workspace-forged` 等夹具命中。

因此本轮不是重复 t2 的结论，而是针对 t5 修复后的残余问题和新增回归。

## 6. 剩余风险

- `check_evidence` 仍信任账本里的状态文本和证据路径；能防格式、路径、哈希和部分伪造，但无法证明“人真的执行了命令”。独立复核的复跑仍是流程约束，不是密码学证明。
- `examples/04` 的 manifest 失败不会被现有 CI 发现，因为 CI 只跑 `check_evidence`，不跑 examples/04 的 `gate`；这是本次 blocker 的直接逃逸路径。
- `examples/05` 的 gate 没有进 CI；发布示例可能再次漂移。
- 本报告是复核产物，不应进入技能包；`package.py` 的排除模式目前只覆盖旧 `32-item-review.md`，合并时需把 round 2 报告排除或移出，否则文件数会从 60 变成 61。
- `docs/reviews/clean-clone.md` 是 v1.0.0 历史记录，不作为本轮缺陷；但不应被误读为当前干净克隆证据。

## 7. 证据路径

- 干净克隆：`/tmp/verity-r2.jE1wKH/clone`（HEAD `ef187d8`）
- 本文：`docs/reviews/32-item-review-round2.md`
- 自验收：`docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md`、`evidence/04-verification.log`、`manifest.json`
- 示例：`examples/04-project-v1/`、`examples/05-release/`
- 负向夹具：在 `/tmp` 的 examples 副本上单点变异，未写入仓库；关键读数见第 2 节和 R2-01/R2-04/R2-05。

本轮只新增本报告，未修改任何实现文件、模板、示例或脚本。
