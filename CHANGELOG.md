# 更新日志

本文件记录 verity 的对外变更。版本号遵循语义化版本（`MAJOR.MINOR.PATCH`），格式参考 Keep a Changelog。

## [v0.1.0] - 2026-11-06

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
