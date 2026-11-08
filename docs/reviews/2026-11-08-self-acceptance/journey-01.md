# 用户旅程卡：J-01 从空目录到门禁通过

> 一条卡只写一条用户路径，3–7 步。模板版本：v2（schema 2，2026-11-08）。

## 基本信息

| 字段 | 内容 |
|---|---|
| 旅程 ID | J-01 |
| 任务卡 | task-card.md v2 |
| 用户目标 | 安装者在空目录初始化一个批次，填最小账本，最后用本地门禁确认可以交付 |
| 入口 | 仓库根目录的 `python3 scripts/verity.py init` |
| 前置状态 | 干净工作区；Python 3.9+；无外部服务 |
| 执行者 | builder |
| 复核者 | 自动门禁复跑 |
| 环境 | macOS；Python 3 标准库；git 工作区 |

## 步骤与不变量

| # | 用户动作 | 可见结果 | 跨区域不变量 | 证据 |
|---|---|---|---|---|
| 1 | 运行 init，打开生成的批次目录 | 看到 task-card、journey-01、07、blocking-form、evidence/ | 07 的旅程结论为未覆盖；journey-01 结论为未覆盖；两处都不预填通过 | evidence/04-verification.log |
| 2 | 填任务卡和 07，运行 check_evidence 与 anti_examples | 合规账本 exit 0；49 个反例全部报目标错误码 | 账本覆盖的 AC 与任务卡逐条对得上；截图/路径/构建号都有身份 | evidence/04-verification.log |
| 3 | 运行 gate 与 package --check | gate 5/5；打包文件数与体积在上限内 | gate 结论、07 包结论、manifest 文件数三处一致 | evidence/04-verification.log |

> 至少 3 条不变量；有列表/详情或多页签时，身份一致和选中/焦点一致必须各有一条。

## 结束状态

- 完成后停在哪：批次目录与 `docs/reviews/2026-11-08-self-acceptance/`
- 数据是否保存：07、旅程卡、证据日志与 manifest 都落盘
- 能否退出、撤销或返回：可删除临时批次；仓库改动可回滚到上一提交

## 异常、空、错误分支

| 分支 | 怎么进入 | 预期 | 实际 | 证据 |
|---|---|---|---|---|
| 空模板直接跑检查器 | 不填 07 直接运行 check_evidence | 报缺少验收项/字段，不判通过 | 非 0，报 E_NO_ROWS 或 E_FIELD | evidence/04-verification.log |
| 反例夹具 | 运行 anti_examples | 每个坏样本命中目标错误码 | 49/49 命中 | evidence/04-verification.log |

## 不按清单的 5 分钟

- 走了哪条真实路径：init → 填一张最小账本 → gate
- 新发现：无
- 是否已转成不变量或缺陷：已转成步骤 1 的“不预填通过”不变量

## 结论

- 结论：通过
- 一句话理由：三步都在本机复跑，读数与证据日志一致
- 证据索引：evidence/04-verification.log
- 复核人：自动门禁复跑
