# 更新日志

本文件记录 verity 的对外变更。版本号遵循语义化版本（`MAJOR.MINOR.PATCH`），格式参考 Keep a Changelog。

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
- `scripts/anti_examples.py`：从 11 例扩到 40 例，新增 v2 结构、旅程、判据、范围锁、证据命令和证据归属反例。
- `scripts/package.py`：排除分析记录和独立评审报告，默认文件上限恢复为 60；新增 `--selftest` 验证 60 通过、70 失败。
- `examples/04-project-v1`、`examples/05-release`：补齐旅程、完成审计、证据身份和独立复核。
- 新增 `docs/optimization-matrix.md`（32/32 状态 done）、`docs/reviews/2026-11-08-self-acceptance/` 自验收证据包。

### 验证

- `python3 scripts/selftest.py`：5/5 通过。
- `python3 scripts/anti_examples.py`：49/49 夹具按预期报错。
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
