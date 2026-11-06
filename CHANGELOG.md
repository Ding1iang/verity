# 更新日志

本文件记录 verity 的对外变更。版本号遵循语义化版本（`MAJOR.MINOR.PATCH`），格式参考 Keep a Changelog。

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
