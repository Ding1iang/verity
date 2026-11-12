# 任务卡：verity v1.3.4 自验收

## 基本信息

| 字段 | 内容 |
|---|---|
| 任务编号 | verity-self-acceptance-1.3.4 |
| 任务卡版本 | v2 |
| schema_version | 2 |
| 平台 | 本机 macOS；Python 3 标准库；git 工作区 |
| 产物 SHA-256 | 以 `manifest.json` 记录为准 |
| 执行者 | builder |
| 复核者 | 自动门禁复跑（独立会话） |

## 车道与风险

| 维度 | 取值 | 说明 |
|---|---|---|
| 复杂度 | 跨模块 | 检查器、模板、文档、示例、打包脚本同时改动 |
| 风险 | 高 | 规则变化会让旧账本失效，并影响 commit/发布门禁 |
| 车道 | 全流程 | 跨模块且改检查器，不能走轻验收 |
| 硬触发 | 跨模块、发布 | 触发全流程 |
| 理由 | 先拿 verity 验 verity | 32 项优化必须由同一套门禁自证 |

## 立卡前盘问

| # | 问题 | 推荐答案 | 用户决定 |
|---|---|---|---|
| 1 | 32 项是否允许只做一部分？ | 不允许，矩阵 32/32 全 done | 全量落地 |
| 2 | 旧十列账本是否必须继续可读？ | 保留 legacy 八列；v1 迁移到 schema 2 | 保留兼容并加 upgrade |
| 3 | 门禁是否依赖外部服务？ | 不依赖，只做本地可执行入口 | 本地 gate |
| 4 | 自验收证据由谁复核？ | 独立复核者逐条复跑并记录退出码 | 独立复核，不留自证 |
| 5 | 发现问题时是否允许带欠账？ | 不允许，失败项必须修完再交付 | 不欠账交付 |

## 规格摘要（spec-lite）

| 字段 | 内容 |
|---|---|
| 问题 | 32 项优化分散在检查器、模板、文档和示例，缺少统一门禁与自证 |
| 用户 | 使用 verity 的 AI 编码代理与独立复核者 |
| 目标 | 把 32 项优化落到规则、模板、检查器、门禁、夹具、文档和自验收，形成 v1.3.0 |
| 范围外 | 不实现清单“不抄”的整套技能包、强制 issue tracker、每任务 worktree、七节 spec、ZK/FHE、JSON-only 门禁、独立 goal-setter、rebar、Java/Spring 绑定、teach/prototype 清单 |
| 关键决定 | v1 schema 2 十三列；十段必需结构；证据身份 SHA-256；独立复核逐 AC；gate 本地入口；分析文档不进发布包 |
| 验收方向 | 以第 5 节验证命令、58 个反例、examples/04 与 05、init 自测和矩阵 32 行为准 |

## 目标

把 verity 的 32 项工作流优化全部落地，并用 verity 自己的检查器和门禁完成一次自验收。

## 范围

### 做

- `scripts/`：检查器、覆盖检查、复核会话核验、反例、打包、verity 工具链。
- `templates/`：任务卡、07 账本、旅程卡、举证单、适配层、覆盖总表。
- `references/`、`SKILL.md`、`README.md`、`CHANGELOG.md`、`VERSION`。
- `examples/04-project-v1/`、`examples/05-release/`、`docs/optimization-matrix.md`、`docs/reviews/`。
- `tests/`（含读数反例夹具）与 `.github/` 的既有自测入口。

### 不做

- `../outside-project/`、`dist/`、`.git/`、任何外部项目目录。

## 范围锁

| 类型 | 路径 |
|---|---|
| 做 | scripts/ |
| 做 | templates/ |
| 做 | references/ |
| 做 | examples/ |
| 做 | docs/ |
| 做 | tests/ |
| 做 | .github/ |
| 做 | README.md |
| 做 | SKILL.md |
| 做 | CHANGELOG.md |
| 做 | VERSION |
| 做 | CONTRIBUTING.md |
| 不做 | ../outside-project/ |
| 不做 | dist/ |
| 不做 | .git/ |

## 要验的状态（5–8 个）

1. 空模板 init 后：生成 journey-01，旅程结论为未覆盖。
2. v2 合规账本：examples/04、05 均 exit 0。
3. 负向夹具：49/49 按目标错误码报错。
4. 覆盖自测：9/9 通过，缺旅程批次被拦。
5. 完成线 gate：examples/04 为 5/5（`--adapter tests/fixtures/valid-adapter.json --run`）、05 为 5/5；反绕过正负对照通过。
6. 打包：文件数与体积在 60 / 10 MB 内。
7. 文档：版本、十三列、六模板、四条硬规则、49 类反例一致。

## 用户旅程

- J-01：安装者从空目录初始化批次，填一张最小账本，跑到 gate 通过。

## 验收项表

| AC-ID | 判据（给定……应得到……） | 旅程 | 最低证据 | 取证方式 |
|---|---|---|---|---|
| AC-01 | 给定 v2 合规账本，check_evidence 应 exit 0；给定缺旅程/旅程未通过/缺完成审计/AC 未映射/同人复核/空举证/重复截图/旧构建/缺路径/伪证据，应非 0 且命中对应错误码 | J-01 / 步骤 2 | A | 运行 anti_examples 与 examples 04/05 |
| AC-02 | 给定空目录运行 init，应生成 journey-01.md，且 07 与旅程卡都不预填“通过” | J-01 / 步骤 1 | A | 运行 init 自测并读生成文件 |
| AC-03 | 给定 examples/04，带 `--adapter tests/fixtures/valid-adapter.json --run` 的 gate 应 5/5 通过；给定 examples/05，gate 应 5/5 通过；给定坏提交，anti-bypass 应报红 | J-01 / 步骤 3 | A | 运行 gate --selftest 与两次 gate |
| AC-04 | 运行 manifest --write 后再 --check，核对输出应报告 7 个文件且 SHA-256 一致 | J-01 / 步骤 2 | A | 运行 manifest --write / --check |
| AC-05 | 运行第 5 节列出的 11 条验证命令，应返回退出码 0；selftest 12/12、anti 58/58、coverage 11/11 与读数一致 | J-01 / 步骤 3 | A | 运行 verify 命令并保存日志 |
| AC-06 | 检查 SKILL/README/references/templates/scripts，版本 1.3.4、schema 2 十三列、六模板、四条硬规则、58 类反例应一致 | J-01 / 步骤 3 | A | grep 计数与 package --check |
| AC-07 | 运行 `check_reviewer.py --selftest`，应返回退出码 0；给定伪造复核人 id 应返回退出码 1；gate 不带 `--verify-reviewer` 时步骤数不变 | J-01 / 步骤 3 | A | 运行 check_reviewer --selftest 与 gate |
| AC-08 | 检查 `references/acceptance.md` §8.1/§8.4/§8.7 与 `SKILL.md`，grep 输出应包含准备批优先、输入通道正对照、复核会话核验 3 处规则 | J-01 / 步骤 1 | A | grep 规则原文 |
| AC-09 | 运行 check_evidence 检查读数只写“ok”的反例账本，应返回退出码 1 且命中 `E_READING_MISSING`；五个示例账本应返回退出码 0 | J-01 / 步骤 2 | A | 运行 anti_examples 与 check_evidence |
| AC-10 | 运行 VERSION 与 manifest --check，应为 1.3.4，且自验收与示例账本的 workspace_hash、SHA-256 与最终提交一致 | J-01 / 步骤 3 | A | 运行 manifest --check 与 gate |

## 覆盖总表对齐

- 本批为技能包自验收，不适用项目覆盖总表；以 `docs/optimization-matrix.md` 32 行为覆盖清单。

## 约束与红线

- 不 push，不做破坏性 git 操作。
- 不删除用户已有改动。
- 不安装新依赖，不联网。

## 交付物

- v1.3.0 规则、模板、脚本、示例与矩阵。
- 本目录 07、证据日志、manifest 与复核记录。

## 变更记录

| 版本 | 日期 | 改了什么 | 作废哪些旧证据 |
|---|---|---|---|
| v2 | 2026-11-08 | 立卡并锁定 32 项范围 | 无 |

## 交付前自检

- [x] 每条 AC 有判据、旅程和最低证据。
- [x] 范围锁覆盖全部改动路径。
- [x] 盘问、spec-lite 和风险已记录。
