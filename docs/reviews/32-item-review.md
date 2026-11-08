# verity 32 项优化独立复核报告（round 1）

- 复核对象：commit `0752f36`（`feat: 落地 verity v1.3.0 工作流 32 项优化`），父提交 `c64f8cd`
- 复核人：t3 reviewer（未参与 t1 实现、未参与 t2 验证）
- 复核日期：2026-11-08
- 复核方式：在 `/tmp/verity-review.u4wE9i/clone` 对 `0752f36` 做干净克隆，所有读数取自该克隆或 HEAD 的 git 对象；不安装依赖、不联网、不修改实现文件
- **结论：needs_revision（不接受，退回修复）**

## 0. 结论摘要

32 项中：通过 9 项，部分实现 13 项，失败 10 项。矩阵 `docs/optimization-matrix.md` 把 32 项全部标为 `done`，与独立复核结果不一致。

存在 3 个阻断项：

1. 打包文件上限从 60 放宽到 70，违反清单“不要为此放宽 60 文件上限”的明文约束。
2. 自验收证据日志被 `.gitignore` 忽略、未进入 git；干净克隆检查 19 项错误、`gate` 3/5，但 07 账本写“门禁均通过”。
3. 证据真实性没有兜底：ASCII 文本改后缀即可当截图，全零 `workspace_hash` 可通过，manifest 的 `workspace_hash` 不重算也可通过。

放行条件：修复 R-01、R-02、R-03 三个阻断项，处理 R-04 至 R-10 的 high 项；提交新 commit 后重新做 round 2 独立复核。当前工作区已有并发 repair 修改（`scripts/check_evidence.py`、`scripts/verity.py` 未提交），不属于本报告复核对象，本报告不以其为依据。

## 1. 复核范围与方法

已读：t1/t2 合同与 `docs/reviews/32-item-verification.md`、`docs/optimization-matrix.md`、`docs/2026-11-07-外部工作流对比与优化清单.md`、`SKILL.md`、`README.md`、`CHANGELOG.md`、`references/`、`templates/`、`scripts/`、`examples/01`–`05`、`docs/reviews/2026-11-08-self-acceptance/`。

方法：

- 逐项把清单要求映射到具体文件、函数/模板字段、测试或示例，而不是只看矩阵的 `done`。
- 正向：在干净克隆跑 5 个示例账本、`gate`、`selftest`、`anti_examples`、`check_coverage --selftest`、`init-selftest`、`py_compile`、`git diff --check`。
- 负向：在 `/tmp` 的 examples 副本上做变异，覆盖硬触发、模糊判据、伪截图、伪造哈希、范围外文件、单步旅程、缺完成审计。
- 可复现：在 `git clone --no-hardlinks` 的干净克隆里重跑自验收账本、manifest、gate、package，不复用工作区未提交文件。
- 绕过：检查 `git status`、`.gitignore`、策略读取基准、`工作区` commit 语义、manifest 的 tracked 与哈希校验、评审人/执行者字段。

## 2. 命令读数

以下均在干净克隆（HEAD `0752f36`）执行：

| 命令 | 读数 | 退出码 |
| --- | --- | --- |
| `python3 scripts/check_evidence.py examples/01-.../07-...md` | 3 行，结论=通过（通过 3） | 0 |
| 同上 examples/02 | 4 行，结论=通过（通过 4） | 0 |
| 同上 examples/03 | 4 行，结论=通过（通过 2、阻塞 1、不适用 1） | 0 |
| 同上 examples/04 | 1 行，结论=通过（通过 1） | 0 |
| 同上 examples/05 | 5 行，结论=通过（通过 5） | 0 |
| `verity.py gate --ledger examples/04/...` | 5/5 通过 | 0 |
| `verity.py gate --ledger examples/05/...` | 5/5 通过 | 0 |
| `verity.py gate --selftest` | 正负对照 PASS | 0 |
| `python3 scripts/selftest.py` | 5/5 通过 | 0 |
| `python3 scripts/anti_examples.py` | 21/21 反例按预期报错 | 0 |
| `python3 scripts/check_coverage.py --selftest` | 9/9 通过 | 0 |
| `bash tests/init-selftest.sh` | 4/4 通过 | 0 |
| `python3 -m py_compile scripts/*.py` | 无输出 | 0 |
| `git diff --check` | 无输出 | 0 |
| `verity.py doctor --root .` | 5/5（适配层未找到，可选） | 0 |
| `verity.py scan`（临时明文口令文件） | `[WARN] 命中明文凭据` | 0 |
| `verity.py scan --release`（同一文件） | `[FAIL] 命中明文凭据` | 1 |
| `verity.py metrics --dir .` | `{"ledgers":11,"rows":21,"conclusions":{"通过":7,"空":3,"- 一句话说明：":1},"levels":{"A":19},"a_ratio":0.9048}` | 0 |

自验收账本的干净克隆读数：

| 命令 | 读数 | 退出码 |
| --- | --- | --- |
| `check_evidence.py docs/reviews/2026-11-08-self-acceptance/07-...md` | `检查失败：19 项错误，0 项警告` | 1 |
| `verity.py manifest --check --root . --ledger .../07-...md` | `[FAIL] 清单里的文件不存在：.../evidence/04-verification.log` | 1 |
| `verity.py gate --root . --ledger .../07-...md` | 证据账本 FAIL、证据包清单 FAIL，`结果：失败（3/5）` | 1 |
| `package.py --check` | `文件数：70 / 70`、`总大小：561.9 KB / 10.0 MB`、通过 | 0 |
| `package.py --check --max-files 60` | `文件数：70 / 60`、失败 | 1 |

工作区本机（非干净克隆）跑自验收 `gate`：证据账本 PASS、覆盖总表跳过、证据包清单 FAIL（`evidence/04-verification.log` 未被 git 跟踪）、范围锁 PASS、防绕过 PASS，`结果：失败（4/5）`，退出 1。

## 3. 32 项逐项结论

状态口径：**通过**＝有具体实现且我复跑或读取到对应行为；**部分**＝主路径存在但关键约束未实现；**失败**＝清单要求没有落地，或可用负向夹具绕过。

| # | 状态 | 复核依据（关键读数/缺口） |
| --- | --- | --- |
| 1 | 失败 | `check_evidence.py:891` 只从复杂度/风险推导，完全不读任务卡“硬触发”列。把 examples/04 的硬触发改成“发布、多步用户旅程、难复现缺陷”、车道仍轻验收，检查器仍通过（exit 0）。 |
| 2 | 部分 | 模板只有 3 行盘问占位；清单要求 5–10 问且带推荐答案。检查器只查≥3 条，未校验问题质量、推荐答案和“用户决定入卡”。 |
| 3 | 通过 | `templates/task-card.md` 的 spec-lite 六字段齐全，检查器有 `E_SPEC_LITE` 缺字段拦截。 |
| 4 | 失败 | `check_evidence.py:153` 只匹配固定模糊词；把 examples/05 AC-01 判据改成“功能可用”仍通过（exit 0）。没有“动作+可观察结果+阈值/二元判定”、全称结论样本范围、豁免留痕的校验。 |
| 5 | 通过 | 账本“覆盖 AC”列、完成审计、旅程步骤映射有 `E_COVERS`/`E_JOURNEY_STEP` 类检查；examples/04、05 正例通过，坏样本能报错。 |
| 6 | 失败 | `verity.py:823` 的 `check_scope` 只遍历 `dont_paths`，`do_paths` 只用于判空。干净克隆根目录 `touch scope-probe.txt` 后 gate 仍 `5/5` 通过，未声明文件不拦。 |
| 7 | 失败 | HEAD 的 `check_evidence.py:2291` 参数只有 `--format/--json/--compat-debt/--strict`，没有 `--run`；`verity.py` 无 `evidence_commands`/EV ID。清单要求的白名单执行、干净 worktree、退出码/stdout/stderr/时间/SHA 捕获均未实现。 |
| 8 | 部分 | SHA-256 和字节数会实算；但 `workspace_hash` 只校验 64 位格式（`:1360`），截图只判后缀和非空（`:425`）。伪截图和全零哈希均通过。 |
| 9 | 失败 | `check_v1_ledger` 在 `commit == "工作区"` 时跳过 git 对象、祖先、提交日期和 mtime 时效检查（`:1685`）；所有示例都用“工作区”，旧证据可以继续当新证据。 |
| 10 | 部分 | 能检查产出者/复核者字符串不同、逐 AC 有 supports；但“高风险必须新会话/独立代理”无法验证，复核命令只校验字段非空，不实际执行。 |
| 11 | 部分 | `gate` 命令和 `gate --selftest` 存在且 5/5；但 CI 只跑 selftest、examples、package、secret-scan，不调用 `verity.py gate`；仓库无 pre-push 钩子。 |
| 12 | 通过 | `gate --selftest` 的删断言/跳过/`--no-verify` 类坏样本按预期报红；防绕过策略从 base commit 的 `.verity/policy.json` 读取，当前 HEAD 没有放宽 diff。 |
| 13 | 通过 | 完成审计段缺失会报 `E_STRUCTURE`；表格缺列、空字段、AC 未映射、最终构建不一致都有对应错误码；examples/04 删段夹具 exit 1。 |
| 14 | 部分 | `check_journey_section` 只检查旅程结论、卡结论、步骤表和 07 行映射（`:966`）；删到只剩 1 步仍通过，未校验 3–7 步、每卡≥3 不变量、每批至少一张、高风险负路径。 |
| 15 | 通过 | `templates/blocking-form.md` 四维必填、每维“试了什么+读数”、能力类正对照、解锁条件齐全；检查器有 `E_BLOCKING_*` 拦截。 |
| 16 | 部分 | `cmd_report --kind pr` 只有结论/旅程/验收项/风险引用/回滚引用，没有“证据”行和证据路径；不满足“发布风险一页+PR 三行（结论/证据/风险回滚）”。 |
| 17 | 失败 | `cmd_metrics` 只统计账本数、行数、结论、等级和 A 比例；没有 F 类计数、根因、时间、复核发现数、返工次数。 |
| 18 | 通过 | `anti_examples.py` 21/21 按预期报错，覆盖删断言、跳过、伪造状态等坏样本；正例 examples/01–05 均通过。 |
| 19 | 部分 | SKILL 写“四条硬规则”，模板 6 个、示例 5 个、反例 21 个，计数彼此一致；但 `package.py` 上限被改成 70，README/CHANGELOG 同步写 70，违反清单 60 的边界，属于 sprawl 的直接证据。 |
| 20 | 部分 | `references/evidence.md` 有 A/B/C 分级、F1–F6 说明和每级正反例；但没有独立“一页术语表”，且检查器允许 `B+` 而文档只定义 A/B/C/B+B。 |
| 21 | 部分 | `upgrade` 能把旧十列账本补成十三列并补四段；但模板/任务卡没有机器可读的 `schema_version`，adapter 只做 `schema == "verity-adapter/v1"` 的精确匹配，没有版本迁移/兼容检查。 |
| 22 | 通过 | `doctor --root .` 5/5：版本、模板、脚本、git、适配层缺失提示均正常；临时 adapter 配 `evidence_channels` 后 8/8，正对照 exit 0、负对照 exit 1。 |
| 23 | 部分 | 模板有 `task_id/agent_id/claimed_at` 证据归属表（`templates/07-acceptance.md:98`）；HEAD 检查器完全没有 `E_EVIDENCE_OWNER` 或归属解析，矩阵所称“字段可被 check_evidence.py 解析”不成立。 |
| 24 | 失败 | 同 17；`metrics` 把模板和坏样本都算作账本，结论键出现 `- 一句话说明：`，A 级占比 90.48%，不能作为批次度量。 |
| 25 | 通过 | `scan` 默认 `[WARN]` 且 exit 0，`--release` `[FAIL]` 且 exit 1；临时明文口令文件实测符合“warning/发布 fail”。 |
| 26 | 失败 | 同 8；伪截图只判 `png` 后缀和 `st_size>0`，没有读取图片魔数、尺寸或 `pixel_hash`，截图证据可伪造。 |
| 27 | 部分 | `cmd_report --kind handoff` 只有结论/旅程/账本/状态/未完成项/下一步，没有“证据路径”字段；不满足交接摘要要求。 |
| 28 | 通过 | `selftest.py` 的坏样本先红后绿：缺完成审计的副本报 1 项错误、exit 1；正常样例 exit 0，命令为秒级本地标准库执行。 |
| 29 | 失败 | 干净克隆自验收检查 19 项错误、gate 3/5；07 账本第 30 行却写“8 条 verify、21 个反例和自验收门禁均通过”。自验收没有真正做到“检查器跑自己账本”。 |
| 30 | 部分 | `doctor` 的通道正负对照只在显式 adapter 且有 `evidence_channels` 时执行（`verity.py:939`）；仓库没有 adapter 示例，`doctor --root .` 直接跳过该行，不能证明开工资质。 |
| 31 | 部分 | `report --kind two-layer` 第一层实际输出 6 行，并出现“旅程卡”“证据等级分布 {'A': 5}”等技术词；未满足“≤3 行、无 ID/术语/路径”。 |
| 32 | 失败 | `check_manifest` 只核对路径/SHA/字节，`workspace_hash` 只打印不重算；把 examples/04 manifest 的 workspace_hash 改成 64 个 f 仍 `[OK]`。自验收清单还把被 ignore 的日志写成 `tracked=false`，干净检出拿不到。 |

## 4. 发现项

### R-01（blocker）打包上限从 60 放宽到 70

- 问题：`scripts/package.py` 的规则、默认值和帮助文本从父提交的 60 改成 70；README 与 CHANGELOG 同步写 70。清单 `docs/2026-11-07-外部工作流对比与优化清单.md:461` 明确写“分析记录不应作为技能包内容发版；正式收口时把它移出包或明确排除，不要为此放宽 60 文件上限”。
- 证据：`git show c64f8cd:scripts/package.py` 为 `DEFAULT_MAX_FILES = 60`、帮助“默认 60”；HEAD `scripts/package.py:4/26/174` 均为 70。干净克隆 `package.py --check` 为 70/70 通过；`--max-files 60` 为 70/60 失败。当前工作区 `package.py --check` 为 71/70 失败（多出未跟踪的 t2 报告）。
- 修复要求：恢复 60 文件上限及规则/帮助/README/CHANGELOG；把 `docs/2026-11-07-外部工作流对比与优化清单.md` 和 `docs/reviews/32-item-verification.md` 移出打包范围或在打包脚本中显式排除；在干净克隆跑 `package.py --check` 必须 60/60 通过、10 MB 以内，并补一个“70 个文件应失败”的反例。
- 文件/行：`scripts/package.py:4`、`:26`、`:174`；`README.md:104`；`CHANGELOG.md`（v1.3.0 节）；`docs/2026-11-07-外部工作流对比与优化清单.md:461`。

### R-02（blocker）自验收证据不在 git，干净克隆无法复现

- 问题：自验收证据 `docs/reviews/2026-11-08-self-acceptance/evidence/04-verification.log` 被 `.gitignore:27` 的 `*.log` 忽略，未进入 git；manifest 把它写成 `tracked=false`，干净克隆 `manifest --check` 直接报文件不存在。自验收 07 第 30 行却写“8 条 verify、21 个反例和自验收门禁均通过”，与实测不符。
- 证据：干净克隆 `check_evidence.py` 报 `检查失败：19 项错误，0 项警告`（含 6×`E_EVIDENCE_PATH`、1×`E_ARTIFACT`、6×`E_COMPLETION_EVIDENCE`、6×`E_REVIEW`）；`gate` 报证据账本 FAIL、证据包清单 FAIL，`结果：失败（3/5）`；工作区 `gate` 4/5，证据包清单 FAIL。manifest 实际 6 个文件，07 第 62 行 AC-04 却写“5 个文件一致”。
- 修复要求：把日志 force-add（`git add -f`）或移到不被忽略的路径并重新生成 manifest；修正 07 的文件数、门禁读数和“通过”表述；在干净克隆重跑 `check_evidence.py` 必须 0 错误、`gate` 5/5；补“删除证据后必须变红”的反例。
- 文件/行：`docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md:30`、`:62`；`docs/reviews/2026-11-08-self-acceptance/manifest.json`；`.gitignore:27`。

### R-03（blocker）证据真实性与 workspace 绑定可伪造

- 问题：`has_readable_image` 只判断后缀在 `IMAGE_SUFFIXES` 且 `st_size>0`（`scripts/check_evidence.py:425-441`）；证据身份只对 `workspace_hash` 做 64 位格式校验（`:1360`）；`check_manifest` 只核对路径/SHA-256/字节数，`workspace_hash` 只打印不重算（`scripts/verity.py:722-757`）。
- 证据：把 52 字节 ASCII 文本命名为 `shot.png`、在 REL-01 写“截图”并补 `viewport/pixel_hash/workspace_hash`，检查器仍 5/5 通过；把 examples/05 的 `workspace_hash` 换成 64 个 0，仍 5/5 通过；把 examples/04 manifest 的 `workspace_hash` 改成 64 个 f，`manifest --check` 仍 `[OK]`。另外 examples/04 manifest 把已跟踪的 `journey-01.md` 写成 `tracked=false`，说明该字段本身不可靠。
- 修复要求：图片校验至少读取魔数/可解码性并核对 `pixel_hash`；`workspace_hash` 必须由当前工作区状态重算并与记录比对，工作区变化即判旧证据失效；manifest 生成与检查都重算 `workspace_hash`；补“伪图片、全零哈希、伪造 manifest 哈希”三个反例，均必须报红。
- 文件/行：`scripts/check_evidence.py:425-441`、`:1284-1360`；`scripts/verity.py:722-757`。

### R-04（high）第 7 项证据命令执行链未实现

- 问题：清单要求 `evidence_commands` 白名单、`check_evidence --run` 在干净 worktree 执行、捕获退出码/stdout/stderr/时间/git SHA，账本引用 EV ID。HEAD 的 `check_evidence.py` 没有 `--run` 参数，`verity.py` 没有 `evidence_commands` 读取或 EV ID 生成。
- 证据：`git show HEAD:scripts/check_evidence.py` 的 `main()` 参数只有 `ledger/--root/--adapter/--format/--json/--compat-debt/--strict`；`grep -n "evidence_commands\|--run\|EV-" scripts/verity.py` 无结果。矩阵第 7 行却标 `done`。
- 修复要求：adapter 增加命令白名单；`check_evidence --run`/`gate --run` 在干净 worktree 执行命令并写 EV ID、退出码、stdout/stderr、时间、HEAD SHA；账本证据行引用 EV ID；补执行成功、执行失败、命令不在白名单三个夹具。
- 文件/行：`scripts/check_evidence.py:2291-2315`；`scripts/verity.py:1123-1190`；`docs/optimization-matrix.md` 第 7 项。

### R-05（high）范围锁只拦“不做”路径

- 问题：`check_scope` 只把 changed 与 `dont_paths` 匹配；`do_paths` 只用于判空，未参与“做路径之外必须报错/提示”的逻辑（`scripts/verity.py:823-842`）。docstring 写“做路径之外只提示”，但代码没有实现。
- 证据：干净克隆根目录 `touch scope-probe.txt` 后，examples/04 gate 仍 `[PASS] 范围锁：改动都在“做”范围`，`结果：通过（5/5）`，exit 0。
- 修复要求：对 changed+untracked 逐项匹配 `do_paths`；范围外文件必须失败，除非任务卡/账本有 `scope_exception` 且写明理由、批准人和到期；补“新增未声明文件、修改未声明文件、声明 exception 后放行”三个夹具。
- 文件/行：`scripts/verity.py:809-842`。

### R-06（high）任务卡“硬触发”字段没有被读取

- 问题：`check_task_card` 的 `hard_trigger` 只由 complexity 含“跨模块”或 risk 含“不可逆/数据/安全”推导（`scripts/check_evidence.py:891-895`），完全不读任务卡的“硬触发”列。清单要求发布、多步用户路径、无法复现缺陷等硬触发必须走全流程，不能靠代理自判。
- 证据：examples/04 的硬触发从“无”改成“发布、多步用户旅程、难复现缺陷”、车道仍“轻验收”，`check_evidence.py` 仍 1 行通过、exit 0。模板 `templates/task-card.md:27` 和 `SKILL.md:46` 都写这些硬触发，但检查器不认。
- 修复要求：解析“硬触发”单元格；任何非“无”的命中词都要求车道=全流程；定义允许值（跨模块/不可逆/数据/安全/发布/多步用户旅程/无法稳定复现）；补“硬触发+轻验收必须失败”“硬触发+全流程通过”两个夹具。
- 文件/行：`scripts/check_evidence.py:850-900`；`templates/task-card.md:27`；`SKILL.md:46`。

### R-07（high）判据 lint 只匹配固定模糊词

- 问题：`VAGUE_CRITERION_WORDS` 只列正常/流畅/友好/尽量/适当/合理/快速/稳定/基本可用/差不多（`scripts/check_evidence.py:153-165`）；判据检查只做 `word in criterion`（`:951`）。没有“动作+可观察结果+阈值/二元判定”、全称结论样本范围、豁免留痕的规则。
- 证据：把 examples/05 AC-01 的判据改成“功能可用”，检查器仍 5/5 通过、exit 0；“功能可用”不在固定词表里。
- 修复要求：判据改为结构化字段或强制模板（动作、可观察结果、阈值/二元判定、样本范围、豁免理由）；保留模糊词表作为补充；补“功能可用/用户体验好/基本正确”等变体反例，均须报红。
- 文件/行：`scripts/check_evidence.py:153-165`、`:940-960`。

### R-08（high）commit 写“工作区”可绕过旧证据检查

- 问题：`V1_COMMIT_RE` 允许“工作区”（`scripts/check_evidence.py:167`）；`check_v1_ledger` 在 commit 不是“工作区”时才做 git 对象、祖先、提交日期和 mtime 时效检查（`:1685`）。因此所有示例和自验收都可以写“工作区”，旧证据不会被判过期。
- 证据：examples/04、05 和自验收 07 的所有行都写“工作区”；把旧证据复制进新批次并保持“工作区”即可通过；代码路径确认跳过对象/祖先/日期/mtime。
- 修复要求：`工作区` 必须绑定 `workspace_hash`/diff 摘要和取证时间；取证后工作区变化即失效；非“工作区”必须校验对象存在、是 HEAD 祖先、日期在批次窗口内。补“旧 commit 当新证据”“工作区变化后旧证据失效”两个夹具。
- 文件/行：`scripts/check_evidence.py:167`、`:1481-1700`。

### R-09（high）旅程卡只查存在性，不查步数/不变量

- 问题：`check_journey_section` 只检查旅程结论、卡结论、步骤表和 07 行映射（`scripts/check_evidence.py:966-1050`）；没有 3–7 步、每卡≥3 不变量、每批至少一张、高风险负路径的校验。
- 证据：删除 examples/04 `journey-01.md` 的步骤 2/3，只剩 1 步，`check_evidence.py` 仍 1 行通过、exit 0。
- 修复要求：解析步骤表并限制 3–7 步；解析“不变量”并限制≥3；高风险批次要求负路径；每批至少一张旅程卡；补“1 步/8 步/2 条不变量/高风险缺负路径”四个反例。
- 文件/行：`scripts/check_evidence.py:966-1060`；`templates/journey-card.md`。

### R-10（high）metrics 统计口径错误且缺关键维度

- 问题：`cmd_metrics` 用 `root.rglob("07-*.md")` 扫所有 07（`scripts/verity.py:1164-1190`），把模板、反例、示例都算成账本；结论键出现 `- 一句话说明：`；只有 A 级占比，没有每批时间、A/B/C 比例、复核发现数、返工次数、F 类计数/根因。
- 证据：干净克隆 `metrics --dir .` 输出 `{"ledgers":11,"rows":21,"conclusions":{"通过":7,"空":3,"- 一句话说明：":1},"levels":{"A":19},"a_ratio":0.9048}`，摘要“11 份账本，21 行，A 级占比 90%”。11 份包含 `templates/07-acceptance.md`、反例和示例，不是真实批次。
- 修复要求：只统计带 batch marker/位于真实批次目录的 07；解析批次信息中的时间、角色、复核发现和返工；增加 F1–F6 计数与根因汇总；输出 A/B+/B/C 比例；补“模板/反例不入账”“F 类计数正确”两个夹具。
- 文件/行：`scripts/verity.py:1164-1190`。

### R-11（medium）PR/交接摘要缺证据路径

- 问题：`cmd_report` 的 PR 输出只有结论/旅程/验收项/风险引用/回滚引用，没有“证据”行；handoff 输出没有证据路径（`scripts/verity.py:1123-1163`）。清单第 16、27 项要求 PR 三行含证据、交接摘要含证据路径。
- 修复要求：PR 输出固定三行“结论/证据（路径+EV ID）/风险与回滚”；handoff 输出“证据路径”字段并校验路径存在；补两个输出快照测试。
- 文件/行：`scripts/verity.py:1123-1163`；`SKILL.md` 输出格式。

### R-12（medium）多代理证据归属只有模板，没有校验

- 问题：`templates/07-acceptance.md:98-102` 定义了 `task_id/agent_id/claimed_at` 表，但 HEAD 的 `check_evidence.py` 没有 `E_EVIDENCE_OWNER`、没有解析“证据归属”段；任何缺失、空值、多人混写都能通过。
- 证据：`git show HEAD:scripts/check_evidence.py | grep -n "证据归属\|E_EVIDENCE_OWNER\|task_id\|claimed_at"` 无结果；矩阵第 23 行却称“模板字段可被 check_evidence.py 解析”。
- 修复要求：多代理批次强制“证据归属”表；校验三列齐全、claimed_at 为日期/ISO、task_id 一致、证据路径存在；单代理批次允许一句说明但要有执行者；补缺失表、空字段、多 task_id 三个反例。
- 文件/行：`templates/07-acceptance.md:98-102`；`scripts/check_evidence.py`（HEAD 无对应实现）。

### R-13（medium）schema_version 与升级链不完整

- 问题：清单第 21 项要求 `schema_version` 进 07/任务卡、upgrade 或迁移说明、adapter 版本检查。模板只有“模板版本：v2（schema 2）”散文；代码没有 `schema_version` 字段；adapter 只做 `schema == "verity-adapter/v1"` 精确匹配（`scripts/verity.py:935`），没有版本兼容检查。`upgrade` 只处理旧十列，不处理八列 legacy；对八列副本跑 upgrade 后仍按 legacy 通过，未生成“覆盖 AC”列。
- 修复要求：07/任务卡增加机器可读 `schema_version`；`upgrade` 明确支持 8→13 或对不支持的版本给出失败提示；adapter 增加版本范围检查；补旧十列、旧八列、未来版本三个夹具。
- 文件/行：`scripts/verity.py:1190-1220`、`:935`；`templates/07-acceptance.md:5`；`templates/task-card.md:2`。

### R-14（medium）gate 未接入 CI/pre-push

- 问题：清单第 11 项要求 `verity gate` 作为完成线并在 pre-push/CI 阻断。`.github/workflows/ci.yml` 只跑 selftest、5 个示例账本、package 和 secret-scan，没有调用 `verity.py gate`；仓库没有 pre-push 钩子或安装说明。
- 修复要求：CI 增加 `verity.py gate`（至少对自验收账本和一个示例）；提供 `git config core.hooksPath`/pre-push 安装脚本或明确 CI 替代方案；补“gate 失败则 CI 红”的演示。
- 文件/行：`.github/workflows/ci.yml:18-70`；`scripts/verity.py:970`（gate 命令）。

### R-15（low）两层汇报第一层越过三行且含术语

- 问题：`report --kind two-layer` 第一层输出 3 段正文，加上账本/状态/下一步共 6 行；出现“旅程卡”“证据等级分布 {'A': 5}”等词。清单第 31 项要求第一层≤3 行、无 ID/术语/路径。
- 修复要求：第一层只输出 3 行纯人话（结论+原因+下一步），不打印 dict、ID、文件名；技术细节全部放到空行后的第二层；补输出快照测试。
- 文件/行：`scripts/verity.py:1123-1140`。

### R-16（low）术语表与判级校准不完整

- 问题：`references/evidence.md` 有 A/B/C 分级和 F1–F6 说明，但没有清单要求的“一页术语表”；检查器允许 `B+`（`check_evidence.py:145`），文档只定义 A/B/C/B+B，判级口径不一致。
- 修复要求：在 `references/evidence.md` 增加一页术语表（或独立 `glossary.md`），统一 A/B+/B/C/B+B 的记法与门槛；补每个等级的正例/反例和 F1–F6 短例。
- 文件/行：`references/evidence.md:18-53`；`scripts/check_evidence.py:145`。

## 5. 可复现性与防绕过检查

- **干净检出**：`git clone --no-hardlinks` 后自验收 19 项错误、gate 3/5，证明“工作区通过”不等于“交付可复现”。这是 R-02 的核心。
- **工作区 commit**：所有示例和自验收都写“工作区”，检查器跳过 git 对象/祖先/日期/mtime，旧证据可复用。这是 R-08。
- **manifest**：只核对路径/SHA/字节，不重算 `workspace_hash`；被 ignore 的日志仍可写入清单，干净检出拿不到。这是 R-02/R-03。
- **直接改状态/删断言/skip/--no-verify**：`gate --selftest` 正负对照 PASS，`anti_examples.py` 21/21 报红，说明这类绕过有覆盖；但“改状态”的检查仍依赖证据行本身，无法识别伪造的命令输出。
- **策略从 diff 放宽**：`read_anti_bypass_policy` 从 base 的 `.verity/policy.json` 读，当前 HEAD 未发现放宽；但 R-01 的 60→70 是“规则/默认值”放宽，不是 policy 文件，现有防绕过没有覆盖。
- **执行者≠复核者**：字符串不同能检查；高风险“新会话/独立代理”没有可验证凭据，只有自述。这是第 10 项部分通过的原因。
- **项目痕迹**：未发现任务卡设备名、笔记应用示例、适配层“密码”禁词等旧痕迹；`grep` 检查通过。此项不单独列为 finding，但 R-01 的 70 上限属于“为分析记录放宽规则”的同类问题。

## 6. 与 t2 报告的差异

- 我确认 t2 的 F-01、F-02、F-03 三个 blocker，以及范围锁、硬触发、判据、工作区绕过、旅程、metrics 等 high 项；读数见上。
- t2 的 F-14（`clean-clone.md` 仍是 v1.0.0）不采纳为缺陷：该文件顶部已明确写“历史记录，v1.0.0 时点”，是带标注的历史证据，不是当前版本的复现声明。
- 32 项计数与 t2 略有差异：t2 为通过 12/部分 10/失败 10；我按“关键约束是否真的落地”重判，item 11、20、21、31 降为部分，item 19 从通过降为部分，item 22 维持通过，最终 9/13/10。差异的原因是口径，不是新增事实。

## 7. 剩余风险

- 即使修复 R-01–R-03，检查器仍主要是语法/结构检查；伪造命令输出、伪造截图内容、伪造人工复核仍需要人工抽查和外部证据（如 CI 日志、原始截图、录屏）。
- 示例批次全部用“工作区”锚点，没有真实 commit 的完整复现样例；修复后应至少保留一个 commit 锚点样例。
- 本报告只覆盖 HEAD `0752f36`；当前工作区的 repair 修改未复核，不能把工作区状态当作已修复。
- 本报告文件本身未提交，作为 round 1 复核交付；round 2 应在修复 commit 上重新生成并提交报告。

## 8. 放行条件

1. R-01：恢复 60 文件上限，分析文档移出包或显式排除；干净克隆 `package.py --check` 60/60 通过。
2. R-02：自验收日志进入 git，manifest 重生成，07 读数与文件数修正；干净克隆 `check_evidence.py` 0 错误、`gate` 5/5。
3. R-03：伪截图、全零 `workspace_hash`、伪造 manifest 哈希三个夹具全部报红；`workspace_hash` 由检查器重算。
4. R-04–R-10：至少完成 high 项；无法在本轮完成的，必须在报告中写明“未实现”并从矩阵撤下 `done`，不能继续标完成。
5. 修复后提交新 commit（不要用工作区状态送审），由未参与 repair 的 reviewer 做 round 2 独立复核；round 2 必须重新跑本报告第 2 节的命令并附读数。

## 9. 证据路径

- 本报告：`docs/reviews/32-item-review.md`
- t2 验证报告：`docs/reviews/32-item-verification.md`
- 自验收账本：`docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md`
- 优化矩阵：`docs/optimization-matrix.md`
- 复核命令的干净克隆临时目录：`/tmp/verity-review.u4wE9i/clone`（临时目录，不作为长期证据；命令和读数已写入本报告第 2 节，可在任意干净检出复跑）
