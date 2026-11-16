# 更新日志

## [v1.4.2] - 2026-11-16

开源准备：公开安装口径、CI 门禁、社区协作与供应链固定项一次补齐；规则和检查器行为不变。

### 新增

- `CODE_OF_CONDUCT.md`：采用 Contributor Covenant 2.1 中文版，联系方式为 `@Ding1iang`。
- `.github/pull_request_template.md`：PR 必须写清改了什么、为什么改、怎么验证。
- `.github/dependabot.yml`：每周检查 GitHub Actions 依赖更新。

### 变更

- `.github/workflows/ci.yml`：完成线不再 gate 历史自验收账本，改为 gate 示例四、五；第三方 Action 固定到提交哈希（checkout v4.4.0、setup-python v5.6.0、lychee v2.9.0）。
- `README.md`：安装从“私有仓库、向管理员索取”改为公开克隆地址；pre-push 示例改用示例四账本；说明压缩包只用于安装/阅读，完整复验走克隆；开源维护口径同步。
- `SECURITY.md`：支持范围从 v1.0.x 更新到 v1.4.x。
- `CONTRIBUTING.md`：改为社区协作口径，补 PR 流程。
- `docs/design.md`：区分“不进技能包和公开示例”与开发档案；移除“公开前保持私有”的旧表述。
- `scripts/package.py`：社区文件不进入技能包，包内文件数不变。
- 版本号 1.4.1 → 1.4.2。

### 验证

- `python3 scripts/selftest.py`：13/13 通过。
- `python3 scripts/anti_examples.py`：58/58 夹具按预期。
- `bash tests/init-selftest.sh`：6/6 通过。
- `python3 scripts/check_coverage.py --selftest`：11/11 通过。
- 五个示例账本 `check_evidence.py`：全部 exit 0。
- `examples/04-project-v1`、`examples/05-release` 的 `verity.py gate ... --run`：各 5/5 通过。
- `python3 scripts/verity.py gate --selftest`：正负对照全过。
- `python3 scripts/package.py --check`：产品 25 / 30，资料 37 / 45，合计 62 / 80。

## [v1.4.1] - 2026-11-16

修范围锁多路径解析与示例证据包清单过期：一格写多个路径不再误判越界，两个示例门禁恢复 5/5。

### 新增

- `scripts/selftest.py`：新增范围锁多路径回归，一格写多个路径必须拆成独立路径；自测 12 项增至 13 项。
- `scripts/verity.py`、`scripts/check_evidence.py`：新增 `split_scope_paths`，按中文顿号、中英文逗号、分号和换行拆分范围锁单元格。

### 变更

- `templates/task-card.md`：范围锁说明补“一格写多个路径用顿号分隔”，与检查器行为对齐。
- `scripts/verity.py`：`manifest --clean-check` 改为按原仓库的跟踪状态校验导出内容，修复干净检出里所有文件被误判未跟踪的问题。
- `examples/04-project-v1`、`examples/05-release`：按当前工作区回填证据身份并重新生成 `manifest.json`，修复按 README 命令复跑只有 4/5 的旧清单。
- 版本号 1.4.0 → 1.4.1。

### 验证

- `python3 scripts/selftest.py`：13/13 通过。
- `python3 scripts/anti_examples.py`：58/58 夹具按预期。
- `bash tests/init-selftest.sh`：6/6 通过。
- `python3 scripts/check_coverage.py --selftest`：11/11 通过。
- `examples/04-project-v1`、`examples/05-release` 的 `verity.py gate ... --run`：各 5/5 通过。
- `python3 scripts/verity.py gate --selftest`：正负对照全过，含干净检出清单。
- `python3 scripts/package.py --check`：产品 25 / 30，资料 37 / 45，合计 62 / 80。

## [v1.4.0] - 2026-11-16

把 E1 入口与视觉、R1 形态×数据、R2 键鼠路径写进规则与任务卡模板，作为影子规则启用；硬拦截留到连续两批复盘后再加。

### 新增

- `references/acceptance.md` §1.3–§1.5：E1 入口清单/边界/命名三项检查；R1 的 C2+C4 固定组合（空态加 C1）；R2 的输入方式与纯键盘/鼠标 AC 要求。
- `templates/task-card.md`：新增“检查规则（按改动面选择）”表，要求逐批写启用/不适用及理由。
- `templates/07-acceptance.md`：预期列说明补充 E1/R1/R2 的读数要求。
- `scripts/check_evidence.py`：任务卡已有“检查规则”段但缺少 E1/R1/R2/R3 行时给 `W_RULE_SELECTION` 软提示，不阻断旧任务卡。

### 变更

- 规则来源：46 条历史缺陷纸面回测（R1 8、R2 9、R3 24、E1 9，并集 46/46）；E1 8/9 有归档旧/新证据；R1/R2/R3 有 2026-11-14 真实试运行数据。
- E1/R1/R2 先以影子规则运行，不因缺失直接判失败；两批复盘达标后才升级为硬拦截。
- 版本号 1.3.5 → 1.4.0；不新增文件，打包文件数不变。

### 验证

- `python3 scripts/selftest.py`：12/12 通过。
- `python3 scripts/anti_examples.py`：58/58 夹具按预期。
- `bash tests/init-selftest.sh`：6/6 通过。
- `python3 scripts/check_coverage.py --selftest`：11/11 通过。
- 五个示例账本 `check_evidence.py` 全部 exit 0。
- `python3 scripts/package.py --check`：产品 25 / 30，资料 37 / 45，合计 62 / 80，约 710 KB；检查通过。

本文件记录 verity 的对外变更。版本号遵循语义化版本（`MAJOR.MINOR.PATCH`），格式参考 Keep a Changelog。

## [v1.3.5] - 2026-11-14

把 R3「不变量判据」写进规则与模板：每条 AC 除“给定……应得到……”外必须再写一个跨区域不变量，防止判据只证明局部变化、旧构建也能过。

### 新增

- `references/acceptance.md` §1.1：判据写法后补三条硬规则——①每条 AC 必须有一个跨区域不变量，四选一：当前页是目标 / 计数与内容一致 / 焦点落点 / 跨区域内容一致；②不变量必须落在本次修复或本次需求承诺解决的范围内，范围外另开 AC；③入口类缺陷或需求必须验“默认态下入口可见且可点”，不许用计数、正文或后续流程替代。
- 同一节给 1 个正例和 2 个反例：正例是“打开满 8 个页签后从日历写日记，当前页签与编辑区标题都是新日记”；反例一是“关闭弹窗后焦点回到按钮”超出修复范围，反例二是“待办中心已经能输入”从后续流程开始、旧构建也能过。
- `templates/task-card.md`：验收项表新增“不变量（四选一，带读数）”列，表下写明“没有不变量的 AC 不得开工”。
- `templates/07-acceptance.md`：预期列的填写说明要求能读出对应不变量与读数，禁止只写“正常/可见”。

### 变更

- `references/acceptance.md` 任务卡字段表：验收项补充“不变量”必填内容。
- 版本号 1.3.4 → 1.3.5；不新增文件，打包文件数不变。

### 验证

- 规则来源：2026-11-13 用 5 条历史缺陷做真回放，旧构建必须失败、新构建必须通过；初版 3/5，修订后 5/5。修订即上述两条反例对应的口径。
- `python3 scripts/selftest.py`：12/12 通过。
- `python3 scripts/anti_examples.py`：58/58 夹具按预期。
- `bash tests/init-selftest.sh`：6/6 通过。
- `python3 scripts/check_coverage.py --selftest`：11/11 通过。
- 自验收门禁 6/6；examples/04、05 门禁各 5/5；五个示例账本 `check_evidence.py` 全部 exit 0。
- `python3 scripts/package.py --check`：产品 25 / 30，资料 37 / 45，合计 62 / 80。

## [v1.3.4] - 2026-11-12

把四条批次经验做成机器可挡的规则：复核会话可核验、准备批成为默认、输入通道先写正对照、通过行的读数必须带量化信息。

### 新增

- `scripts/check_reviewer.py`：核对账本复核人是否有同名会话目录、目录创建时间、复核独立性，以及 `evidence/verifier-run.json` 的 verifier 与退出码；没有会话目录（如 CI）时打印跳过并退出 0。带 `--selftest`，用临时目录造假会话，不依赖本机真实会话。
- `scripts/verity.py gate --verify-reviewer`：开启后调用复核会话核验，失败即 gate 失败；默认关闭，保持原有门禁不变。
- `scripts/check_evidence.py` 新增 `E_READING_MISSING`：状态“通过”的行，读数为空或只有“正常/通过/无异常/ok”这类无信息词时判红；允许数字、px/vp/ms/%、`exit=`、`sha256`、`color=` 或 DB 字段。
- `tests/fixtures/bad-reading-only-normal/`：读数只写“正常”的反例账本，由 `anti_examples.py` 断言命中 `E_READING_MISSING`。
- `scripts/selftest.py`：新增 2 条复核会话正负例（真目录通过、伪造 id 失败），合计 12/12。

### 变更

- `scripts/check_evidence.py`：干净工作树解包兼容 Python 3.9（`filter="data"` 只在 3.12+ 可用），修复 3.9 下 `gate --run` 直接 TypeError 的旧问题。
- `references/acceptance.md` §8.1：一次收到 ≥3 条用户反馈时，第一批必须是只复验、只建档、不改代码的准备批。
- `references/acceptance.md` §8.4：放行五条第 3 条写明复核会话核验由 `check_reviewer.py` 执行。
- `references/acceptance.md` §8.7：任务书骨架增加“输入通道正对照”“复核”两行必填，并重排编号。
- `references/acceptance.md` §5.1：补充 `E_READING_MISSING` 错误码。
- `SKILL.md`：多批次编排补“准备批优先”和“复核会话核验用 `check_reviewer.py`”；版本号升到 1.3.4。
- 版本号 1.3.3 → 1.3.4。

### 验证

- Python 3.9.6 / 3.12.14 / 3.13.1 各跑一遍：selftest 12/12、anti 58/58、init 6/6、coverage 11/11、check_reviewer 3/3、doctor 10/10、三个 gate 全过、package 通过。
- `python3 scripts/check_reviewer.py --selftest`：3/3 通过。
- `python3 scripts/selftest.py`：12/12 通过。
- `python3 scripts/anti_examples.py`：58/58 夹具按预期。
- `bash tests/init-selftest.sh`：6/6 通过。
- `python3 scripts/check_coverage.py --selftest`：11/11 通过。
- 五个示例账本 `check_evidence.py` 全部 exit 0（04 / 05 的 workspace_hash 按新工作区重算）。
- `python3 scripts/verity.py doctor --root . --adapter tests/fixtures/valid-adapter.json`：10/10 项通过。
- `python3 scripts/verity.py gate`（自验收账本，`--run --team --release`）：6/6 通过；examples/04、05：5/5 通过。
- `python3 scripts/package.py --check`：产品 25 / 30，资料 37 / 45，合计 62 / 80，699.6 KB。

## [v1.3.3] - 2026-11-12

把“多批次编排”收进验收规则：一个工程拆成准备批 / 修复批 / 回归批串行跑时，调度方按统一判据放行，不再靠口头约定。

### 新增

- `references/acceptance.md` §8「多批次编排（调度方）」：批次类型（准备批 / 修复批 / 回归批）、角色与串行约束、每批五步、放行五条、三类缺口、三条红线、任务书八段与最小骨架、收尾规则。
- `SKILL.md` 增加「多批次编排」入口段，指向 §8，并写明“同一工作区不许并行两批”。

### 变更

- 版本号 1.3.2 → 1.3.3。
- 不新增文件；打包实测产品 24 / 30、资料 36 / 45、合计 60 / 80。

### 验证

- `python3 scripts/selftest.py`：10/10 通过。
- `bash tests/init-selftest.sh`：6/6 通过。
- `python3 scripts/check_coverage.py --selftest`：11/11 通过。
- `python3 scripts/anti_examples.py`：57/57 夹具按预期。
- 五个示例账本 `check_evidence.py` 全部 exit 0（04 / 05 的 workspace_hash 按新工作区重算）。
- `python3 scripts/package.py --check`：产品 24 / 30，资料 36 / 45，合计 60 / 80，660.5 KB。
- `python3 scripts/verity.py doctor --root .`：6/6；带适配层 10/10。

## [v1.3.2] - 2026-11-11

新增“账本内部矛盾”校验：包结论写通过时，欠账、阻塞、复核、旧产物和完成审计必须彼此一致，不能再靠逐行状态相加得出假通过。

### 新增

- `scripts/check_evidence.py`：新增 `E_DEBT_IN_PASS`（通过 + 欠账非空）、`E_BLOCKING_IN_PASS`（通过 + 阻塞单仍 open 或状态不唯一）、`E_REVIEW_MISMATCH`（重复 AC、复核人等于产出者、EV 与 AC 不对应）、`E_ARTIFACT_STALE`（证据 HAP/commit 不是最终值）、`E_AUDIT_CONTRADICTION`（完成审计写通过却带失败描述）、`E_COMPLETION_MISSING`（任务卡 AC 未同时出现在验收行和完成审计）。
- `blocking-form.md` 现在有唯一当前状态 `open` / `closed`；历史结论只能放在“历史记录”小节，当前状态与历史混写会被判红。
- 适配层 `evidence_commands` 支持 `ac_ids`；`--run` 写入的 `ev-runs.log` 记录新增 `ac_id`、`ac_ids`、`hap_sha`，复核检查按 AC 和最终 HAP 绑定，防止拿 EV-03 搜索证据给 Ctrl+F 签字。
- `scripts/anti_examples.py`：新增 5 个反例（通过+欠账、通过+阻塞 open、重复 AC 复核、通过+旧 HAP、通过+完成审计矛盾），夹具总数 57。
- `scripts/selftest.py`：新增 5 个 v1/v2 自测，原有 5 个 legacy 样本保留，合计 10/10。
- `references/acceptance.md`：补充上述六个错误码和“通过时欠账/阻塞必须为空”的硬规则。

### 修复

- 统一版本号：`VERSION` 与 `SKILL.md` 同为 1.3.2，`doctor` 不再显示旧号。
- 同步文档预期读数：`README.md`、`CONTRIBUTING.md`、`docs/optimization-matrix.md` 改为当前实测值（自测 10/10、初始化自测 6/6、覆盖自测 11/11、反例 55/55、doctor 带适配层 10/10、不带 6/6）。
- `tests/fixtures/valid-adapter.json`：`EV-01` 补 `ac_ids`，让自验收和 v1 示例账本在带适配层的门禁里完成独立复核绑定。
- `scripts/verity.py doctor`：文档计数断言里的反例数量从写死的 50 改到实际的 55，避免正确的文档被自己判成漂移。
- `.github/workflows/ci.yml`：修复说明书逐字比对脚本的续行符转义，单反斜杠会被 Python 三引号折叠成空格，导致该断言恒失败。
- `scripts/verity.py identity`：新增 `--write` / `--check`，按当前文件重算并回填证据身份表的 SHA-256、字节数与 workspace_hash，减少手工抄写。
- `scripts/package.py`：打包预算拆成“产品载荷 / 工程资产”两套配额（当前产品 24 / 30、资料 36 / 45、合计 60 / 80），产品超限才失败，资料超软上限只提醒；自测按配额参数化，调整上限不必改自测。
- `scripts/check_evidence.py`：适配层 `evidence_commands` 支持 `covers` 声明依赖路径，实现变更按依赖范围判定失效，未声明仍按全仓。
- `scripts/check_evidence.py`：证据文件 mtime 早于提交日期时改记为提醒（`E_STALE_MTIME`），内容哈希才是主判据，`--strict` 才阻断；新增两条时间判据反例。
- `scripts/anti_examples.py`：伪造复核与日期归一不再按字面写死旧读数，改为按表格列结构和时间格式匹配，避免账号刷新后负向夹具静默变成正向通过。
- 刷新三份 v1 验收档案：重新取证并绑定最终提交，补齐阻塞单唯一当前状态，修绿初始化自检与整套自动检查。

### 验证

- `python3 -m py_compile scripts/*.py`：通过。
- `python3 scripts/selftest.py`：10/10 通过。
- `python3 scripts/anti_examples.py`：57/57 夹具按预期。
- `python3 scripts/package.py --check`：60/60 文件，未放宽上限。

## [v1.3.1] - 2026-11-10

修正两处会让“证据自己作废自己”的规则缺陷：跨模块批次被拆成多本 07，以及工作区指纹把文档和账本也算进受控范围。

### 修复

- `scripts/check_evidence.py`：`workspace_fingerprint` 只算受控实现文件（代码、脚本、模板、配置），`docs/`、`acceptance/`、`evidence/`、`07-*.md`、`manifest.json` 等记录类路径不计入；文本按 LF 归一后再入指纹，消除 CRLF 检出与干净检出的互相作废。
- `scripts/check_coverage.py`：同一份 07 允许被同一批次的多行认领（一个批次跨多个模块，一本账管多模块）；只有跨批次共用才报 `E_LEDGER_DUP`。结论计数与“账本 N/N”按 07 文件数去重，同一份账本不会把通过数放大。
- `scripts/check_coverage.py`：自测增到 11 例，新增“同批次多模块共用一份 07”正向样本与“同一份 07 被两个批次认领”负向样本。
- `scripts/anti_examples.py`：夹具日期随运行日期平移，修复跑日期一变就整批假红的问题。
- `scripts/verity.py`（`check_scope`）、`scripts/check_evidence.py`（`stale_implementation_changes`）：项目在 git 仓库子目录里（monorepo）时，先把 `git status`/`git diff` 的仓库根相对路径剥掉项目前缀再比对。修复两类静默失效：范围锁把所有改动判成“未声明”、以及“证据绑定提交之后实现又改过”从来不报红。
- `references/acceptance.md`、`references/adapter.md`、`references/evidence.md`、`templates/coverage-master.md`：明确“一个批次一本账、跨模块写进同一本”“同批次多模块可共用 07”“workspace_hash 只覆盖受控实现”的口径。

## [v1.3.0] - 2026-11-08

v1.3.0 落地 32 项工作流优化：任务卡前置盘问与快慢车道、AC/旅程/账本三向映射、结构化完成审计、产物身份、旧证据失效、独立复核、本地完成线闸门、防绕过、证据包清单、阻塞举证四维、红队夹具、doctor/gate/manifest/report/metrics/upgrade/scan 工具链。

### 变更

- `SKILL.md`、`README.md`、`references/acceptance.md`、`references/adapter.md`：升到 1.3.0，统一 v1 schema 2 十三列、十段必需结构、四条硬规则、六份模板、五个示例和 49 类反例的计数。
- `templates/task-card.md`：新增车道与风险、立卡前盘问、规格摘要（spec-lite）、范围锁和可判判据。
- `templates/07-acceptance.md`：十三列账本、用户旅程、证据身份、完成审计、独立复核、复盘、发布风险、证据归属。
- `templates/journey-card.md`、`templates/blocking-form.md`：升 v2，补通用布局说明与四维举证字段。
- `scripts/check_evidence.py`：v1 schema 2 全量校验；旅程未通过不判通过、AC 覆盖、同人复核、空举证、重复截图、旧构建、缺路径和伪证据都会阻断。
- `scripts/check_coverage.py`：批次目录必须含 `journey-*.md`，自测增到 9 例。
- `scripts/verity.py`：新增 doctor、gate、manifest、report、metrics、upgrade、scan；init 生成 `journey-01.md` 且不预填通过。
- `scripts/anti_examples.py`：从 11 例扩到 49 例，新增 v2 结构、旅程、判据、范围锁、证据命令和证据归属反例。
- `scripts/package.py`：排除分析记录和独立评审报告，默认文件上限恢复为 60；新增 `--selftest` 验证 60 通过、70 失败。
- `examples/04-project-v1`、`examples/05-release`：补齐旅程、完成审计、证据身份和独立复核。
- 新增 `docs/optimization-matrix.md`（32/32 状态 done）、`docs/reviews/2026-11-08-self-acceptance/` 自验收证据包。

### 验证

- `python3 scripts/selftest.py`：5/5 通过。
- `python3 scripts/anti_examples.py`：50/50 夹具按预期报错。
- `python3 scripts/check_coverage.py --selftest`：9/9 通过。
- `python3 scripts/verity.py gate --selftest`：正负对照通过。
- `python3 scripts/verity.py gate --root . --ledger examples/04-project-v1/07-验收回归清单.md --adapter tests/fixtures/valid-adapter.json --run`：5/5 通过；05 为 5/5（未生成 manifest 时清单步骤跳过）。
- `python3 scripts/package.py --check`：60/60 文件（上限 60）。

## [v1.2.0] - 2026-11-07

v1.2.0 把修缺陷从“最小修复”改为“根因修复（完整覆盖）”，并把完成审计前移到收口门禁：能现在补的验证、证据和修复，不允许留成欠账。

### 变更

- `SKILL.md` 升到 1.2.0；硬规则新增“完整修复，不留可补的缺口”，五步流程的落账步骤加入完成审计；带欠账改为仅历史账本兼容。
- `references/bug-fix.md`：步骤 4 从“最小修复”改为“根因修复”，2.4 改为“根因修复（完整覆盖）”，硬边界收窄为四类；新增 2.7 完成门禁；04 记录从“最小性”改为“改动与完整性”。
- `references/acceptance.md`、`templates/07-acceptance.md`：新增完成审计表与收口规则，完成定义逐条对应最终构建、实际读数和证据。
- `README.md`、`docs/design.md`、`references/adapter.md`、`CONTRIBUTING.md`、`templates/adapter.json`：同步“带欠账仅为读取历史账本兼容，新账本默认禁止”。
- `scripts/check_evidence.py`：默认只允许四状态、三结论，新增 `--compat-debt` 仅用于读取历史账本；新增第 11 个反例验证带欠账默认报错。

### 验证

- `python3 scripts/selftest.py`：5/5 通过。
- `python3 scripts/anti_examples.py`：11/11 反例按预期报错。
- `python3 scripts/check_coverage.py --selftest`：8/8 通过。
- 默认拒绝带欠账（E_STATUS / E_CONCLUSION），加 `--compat-debt` 可读取历史账本并退出 0。
- `python3 scripts/package.py --check`：60/60 文件。
- 五个示例账本全部通过 `check_evidence.py`；01/02/04/05 的结论分别为通过 3/4/1/5 行，03 为阻塞（通过 2 / 阻塞 1 / 不适用 1）。

## [v1.1.0] - 2026-11-07

v1.1.0 补上“用户旅程”验收层：批次不只看单点检查有没有打勾，还要看用户从入口到目标的连续路径、跨区域状态是否一致、整窗证据是否成立。

### 新增

- `references/journey-acceptance.md`：用户旅程卡、跨区域不变量、整窗证据、每批 5 分钟不按清单使用、批次通过条件。
- `templates/journey-card.md`：J-ID、步骤、可见变化、跨区域不变量、证据和结论。

### 变更

- `SKILL.md` 升到 1.1.0；五步流程加入旅程卡和整窗/不变量检查，输出增加“旅程”一行。
- `references/acceptance.md`：批次通过增加“至少一份旅程卡通过、无未解决不变量”；07 用户路径列必须引用 J-ID/步骤。
- `references/acceptance-run.md`：观察先看整窗，每步做跨区域自检，批量验收先写 1–3 张旅程卡并留 5 分钟真实使用。
- `references/visual.md`：新增跨区域选中态，要求整窗截图/像素采样，不能只靠布局树判选中。
- `templates/07-acceptance.md`、`templates/task-card.md`：加入旅程段、旅程字段和收口条件。

### 验证

- `python3 scripts/selftest.py`：5/5 通过。
- `python3 scripts/anti_examples.py`：10/10 反例通过。
- `python3 scripts/package.py --check`：60/60 文件。

## [v1.0.0] - 2026-11-06

v1.0.0 把 verity 从可用骨架收口为可发布版本：默认 v1 十列四状态，检查器覆盖 commit 锚点、证据复用和证据自述缺口，覆盖总表能统计包结论，并补齐四个模式的示例与十类反例。

### 变更

- 默认 07 模板切到 v1 十列四状态；旧八列账本仍可用 `--format legacy` 读取。
- `check_evidence.py` 增加 commit 真实性/祖先校验、证据 mtime 复用拦截、`--strict` 拒绝欠账；`未覆盖` 收口按 `未交付（失败）` 判定。
- `check_coverage.py` 增加 07 包结论统计、批次目录与任务卡/07 互链检查；摘要输出“账本 N/N、结论通过/失败/阻塞”。
- 适配层支持直接发现 `verity-适配层.json`，新增任务卡/举证单模板路径与 `ledger` 枚举收窄；默认模板说明从八列改为 v1。
- 新增发布模式示例 `examples/05-release`；新功能、修缺陷、验收、发布四个模式各带一个反例 fixture。
- 新增 `scripts/anti_examples.py`，在临时目录生成十类反例并逐条断言错误码；新增 `docs/reviews/anti-examples.md` 预备清单。
- `check_evidence.py` 增加截图可读性（`E_SCREENSHOT`）和证据自述缺口（`E_SCOPE_GAP` / `E_PROBE_MISSING` / `E_DEVICE_UNVERIFIED`）检查；README、贡献指南与本地验证覆盖五个示例与 57/60 文件读数；CI 保持四示例，并运行自测、打包、链接与密钥扫描。
- 新增 `docs/reviews/clean-clone.md`，记录本机临时目录解压后的复跑结果。

### 验证

- `python3 scripts/selftest.py`：5/5 通过。
- 五个示例账本：01 通过 3、02 通过 4、03 阻塞（通过 2 / 阻塞 1 / 不适用 1）、04 通过 1、05 通过 5。
- `python3 scripts/anti_examples.py`：10/10 反例按预期报错。
- `python3 scripts/check_coverage.py --selftest`：8/8 通过。
- `bash tests/init-selftest.sh`：4/4 通过。
- `python3 scripts/package.py --check`：57 / 60 文件，总大小小于 10 MB。
- `python3 scripts/package.py --zip` 后解压到空临时目录，按 README 复跑 selftest、package 检查与五个示例，全部通过；zip 不含 `.git`、`__pycache__`、`.pyc`、临时文件或密钥。

### 已知限制

- `check_evidence.py` 只验形式，不验证据内容的真实性；真实性由复核人负责。
- `check_coverage.py` 只核对结构与路径，不执行适配层里的命令，也不判断证据真假。
- `package.py` 只统计文件数与体积，不判断内容是否敏感；敏感信息由 secret scan 与人工检查负责。
- 示例中的版本号、读数和项目名都是演示数据，不能当作真实项目证据复用。

## [v0.2.0] - 2026-11-06

v0.2.0 让 verity 能接入真实项目：新增任务初始化、项目适配层、覆盖总表检查和项目 v1 账本支持；通用八列账本继续可用。

### 新增

- `scripts/verity.py init`：按任务名、模式和可选适配层生成任务卡、07 账本、阻塞举证单和 `evidence/` 目录；目录已存在时拒绝覆盖。
- 项目适配层：`templates/adapter.json` 与 `references/adapter.md`，集中记录项目根、门禁命令、设备入口、07/证据目录和脱敏规则；默认读取项目根 `.verity/adapter.json`，可用 `--adapter` 显式覆盖。
- 覆盖总表：`templates/coverage-master.md` 与 `scripts/check_coverage.py`，按在用模块检查 07 是否存在、是否不适用，并检查重复认领和数量对账。
- 项目 v1 十列账本：`check_evidence.py` 支持项目自己的十列五档格式，按 marker 自动识别，也可用 `--format v1` 或 `--adapter` 指定；通用八列仍为默认格式。
- 验收执行参考 `references/acceptance-run.md`：补记锚点、备数据、选通道、单条执行、批量验收、失败归因、复测和证据复用。
- 视觉优化参考 `references/ui-improvement.md`：只改呈现、不改行为时的设计侧与落地侧流程。
- 项目示例 `examples/04-project-v1` 与 `tests/init-selftest.sh`。

### 变更

- `SKILL.md` 增加“说真话，不迎合”、项目接入说明，并引用验收执行参考。
- `README.md` 快速开始改用 `init` 命令，补充第四个示例与项目接入步骤，并更新模板和脚本说明。
- `check_evidence.py` 现在能读取项目账本模板并按格式检查；通用八列账本无需额外参数。
- `acceptance.md` 补充扩展列、项目 v1 账本和仓库外证据登记规则；`bug-fix.md`、`new-feature.md`、`visual.md` 补充开工前摸底、计划审查和视觉优化分流。

### 修复

- `init` 在写入前拒绝已存在的任务目录，避免覆盖已有任务。
- 空账本检查提示补充缺失字段说明，模板原样运行时能指出待填项。

### 验证

- `python3 scripts/selftest.py`：5/5 通过。
- 四个示例账本：01 通过 3、02 通过 4、03 阻塞（通过 2 / 阻塞 1 / 不适用 1）、04 通过 1。
- `bash tests/init-selftest.sh`：4/4 通过。
- `python3 scripts/package.py --check`：47 / 60 文件，总大小小于 10 MB。

### 已知限制

- `check_evidence.py` 仍不校验证据是否来自当前提交（HEAD）；跨提交复用证据必须由流程层按 F2 独立复核。v0.1.0 曾计划在 v0.2 补脚本锚点，本版未实现，顺延到后续版本。
- 项目 v1 十列是项目自己的 schema，不是通用八列的扩展；两种格式不要混写，通用场景继续用八列。
- `check_coverage.py` 只核对结构与路径，不执行适配层里的命令，也不判断证据真假。

## [v0.1.0] - 2026-11-06

> 历史版本说明：v0.1.0 的 tag 与 Release 未保留，历史版本不提供；以下内容仅保留当时的版本记录，不能按 tag 复现。

首个自用版本。目标是把“AI 说做完了，凭什么”落成一套可检查的交付流程。

### 新增

- 技能入口 `SKILL.md`：四种模式、五步流程、三条硬规则。
- 规则正文 `references/`：证据分级 F1–F6、验收任务卡与七种状态、新功能 / 修缺陷 / 验收 / 发布四种模式、视觉与行为性能取证。
- 模板 `templates/`：任务卡、07 验收回归清单、阻塞举证单。
- 脚本 `scripts/`：`check_evidence.py` 账本检查、`selftest.py` 好坏样本自测、`package.py` 文件数与体积检查及 zip 生成。
- 三个端到端示例与根 README 快速开始。
- 开源协作文件：CONTRIBUTING、SECURITY、issue 模板、GitHub Actions 流水线。

### 变更

- 打包上限从 30 文件 / 40 MB 调整为 60 文件 / 10 MB，按自用开源仓库口径统计全部跟踪文件。
- `package.py` 增加显式 `--zip` 参数；压缩包由脚本生成，不提交仓库。

### 验证

- `python3 scripts/selftest.py`：5/5 通过。
- 三个示例账本：3/3 通过（新功能 3、修缺陷 4、阻塞 2/1/1）。
- `python3 scripts/package.py --check`：35 / 60 文件，总大小小于 10 MB。
- gitleaks 全历史扫描无泄露；Markdown 链接与 GitHub Actions 工作流本地校验通过。

### 已知限制

- `check_evidence.py` 不校验证据是否来自当前提交（HEAD），跨提交复用证据需流程层按 F2 独立复核；计划在 v0.2 补脚本锚点，本版不改证据格式。
- 检查器只验形式，不验证据真假；真实性由复核人负责。
- `package.py` 只统计文件数与体积，不判断内容是否敏感；敏感信息由 secret scan 与人工检查负责。

### 安全

- 仓库在自验收与复核通过前保持私有；v0.1.0 采用 MIT 许可证。
