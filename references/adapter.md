# 项目适配层契约

> verity 仓库只放通用规则。项目根、门禁命令、设备入口、07 目录、证据目录和脱敏规则都属于项目侧，写进项目自己的适配层。
>
> **适配层放项目里，不放进 verity 仓库。** 换项目时只换适配层，通用规则不动。

## 1. 它解决什么

通用技能不知道每个项目怎么构建、怎么跑静态检查、怎么操作设备、07 放在哪。适配层就是这张“项目事实表”：让 verity 的检查器能按项目自己的路径和命令工作，同时把项目专属信息挡在 verity 仓库之外。

适配层只描述事实，不记录任何一次交付的通过/失败结论。结论只写进 07 账本。

## 2. 放在哪里

推荐位置：

```text
<项目根>/.verity/adapter.json
```

也可以放在项目自己的验收目录，命名为 `verity-适配层.json`（中文文件名直接可被检查器发现）。从 `templates/adapter.json` 复制，按本项目实际情况填写。检查器的自动发现顺序是 `verity-适配层.json` → `.verity/adapter.json` → `verity-adapter.json` → `adapter.json`；命令行 `--adapter` 显式指定时优先，不存在直接报错。适配层属于项目资产，跟着项目走；不要把它复制回 verity 仓库，也不要把里面的路径、命令、设备入口写进 verity 的规则或示例。

适配层里**禁止出现**：生产密码/真实凭据、令牌、Cookie、私钥、设备序列号、内网地址、真实用户数据。开发环境的测试口令不属于生产凭据，可按测试数据管理。需要引用凭据时写“从环境变量读取”之类的入口说明，不写值。

## 3. 字段

| 字段 | 必填 | 写什么 | 约束 |
|---|---|---|---|
| `schema` | 是 | 固定写 `verity-adapter/v1` | 版本升级时另立新值，不原地改语义 |
| `schema_version` | 是 | 适配层结构版本，当前为 `1` | 必须是 1 到当前 verity 支持的整数；过新时先升级 verity，过旧时按本文件迁移 |
| `min_verity_version` | 是 | 最低 verity 版本，如 `1.3.0` | 必须写 `x.y.z`；低于它时 `init`、`doctor` 和检查器直接报错 |
| `evidence_commands` | 否 | 取证命令白名单数组，每项含 `id`（`EV-01` 形式）和 `command` | `check_evidence.py --run` 只执行这里的命令；未登记、非零退出或超时都阻断验收 |
| `project.name` | 是 | 项目名，只用于显示 | 不写内部代号或客户名 |
| `project.root` | 是 | 项目根相对适配层文件所在目录的路径 | 适配层在 `<项目根>/.verity/adapter.json` 时写 `..`；命令行传 `--project-root` 时以命令行为准 |
| `baseline.command` | 是 | 取基线提交的命令，运行后输出单个 commit ID | 没有 git 的项目写自己的版本号命令，并在 `description` 说明 |
| `commands.static` | 是 | 静态检查命令列表 | 每项含 `id`、`description`、`command`、`timeout_seconds` |
| `commands.contract` | 是 | 契约/接口检查命令列表 | 没有就写空数组，不写“无”字符串 |
| `commands.device` | 是 | 真机或模拟器上的检查命令列表 | 只写怎么跑，不写设备地址和序列号 |
| `commands.build` | 是 | 构建、安装、截图等命令列表 | 产物路径用项目内相对路径 |
| `paths.ledger_root` | 是 | 07 账本根目录，相对项目根 | 检查器会递归扫描其中的 `07-*.md`，并与覆盖总表对账 |
| `paths.evidence_root` | 是 | 证据文件根目录，相对项目根 | 07 里的证据路径建议相对项目根或账本目录，保持可移植 |
| `paths.coverage_master` | 否 | 覆盖总表路径，相对项目根 | 仅作记录；命令行参数优先 |
| `paths.ledger_filename` | 否 | 项目账本文件名，默认 `07-验收回归清单.md` | 只影响批次包互链检查；仍须符合 `07-*.md` |
| `paths.task_card_filename` | 否 | 项目任务卡文件名，默认 `task-card.md` | 只影响批次包互链检查 |
| `paths.ledger_template` | 否 | 项目自己的 07 账本模板，相对项目根 | 填了它，`init` 会按项目模板生成；留空则用 verity 仓库的 v1 schema 2 十三列模板。模板文件必须存在；`check_evidence.py --adapter` 会读取模板里的 marker 判断是否为 v1 格式 |
| `paths.task_card_template` | 否 | 项目自己的任务卡模板，相对项目根 | 填了它，`init` 按项目模板生成任务卡；留空用 verity 仓库模板 |
| `paths.blocking_form_template` | 否 | 项目自己的阻塞举证单模板，相对项目根 | 填了它，`init` 按项目模板生成举证单；留空用 verity 仓库模板 |
| `ledger.statuses` | 否 | 账本允许的状态数组 | 必须是 verity 支持值的非空子集；项目验收建议 `通过 / 未交付-失败 / 未交付-阻塞 / 未覆盖` |
| `ledger.conclusions` | 否 | 允许的包结论数组 | 必须是 verity 支持值的非空子集；项目验收建议 `通过 / 未交付（失败） / 未交付（阻塞）` |
| `ledger.evidence_types` | 否 | 证据类型数组 | 必须是 verity 支持值的非空子集 |
| `ledger.confidences` | 否 | 证据置信度数组 | 必须是 `高 / 中 / 低` 的非空子集 |
| `device.entry` | 是 | 设备操作入口：项目内脚本路径、工具名或人工操作说明 | 不写序列号、账号、连接地址；不把设备命令抄进 verity |
| `redaction.rules` | 是 | 脱敏规则数组，每项含 `pattern`（正则）、`replace`、`description` | 证据落盘或提交前按顺序应用 |
| `redaction.forbidden` | 是 | 绝对不能出现的内容类别列表 | 至少包含生产密码/真实凭据、令牌、Cookie、私钥、真实用户数据 |
| `modules` | 是 | 在用模块列表，每项含 `id`、`name`、`in_use` | 检查器要求每个 `in_use: true` 的模块在覆盖总表至少有一行 |

命令对象统一写成：

```json
{
  "id": "static-lint",
  "description": "静态检查：类型检查与 lint",
  "command": "<在项目根执行的完整命令>",
  "timeout_seconds": 300
}
```

## 4. 和覆盖总表的关系

- 适配层的 `modules` 是“应该被覆盖的模块清单”；覆盖总表是“实际有没有 07 的记录”。
- 覆盖总表一行一个在用模块或用户路径，只写 `已覆盖` / `缺失` / `不适用`，不写通过/失败。
- 通过/失败只从该行指向的 07 账本读。覆盖总表不能替代 07，也不能用来证明交付通过。
- 检查器会把 `paths.ledger_root` 下的 07 文件与总表认领的 07 对账；数量对不上、同一份 07 被两行认领、已覆盖却找不到文件，都会报错。

## 5. 怎么校验适配层

```bash
python3 <verity 仓库>/scripts/check_coverage.py <覆盖总表> \
  --adapter <项目根>/.verity/adapter.json \
  --project-root <项目根>
```

项目使用 `paths.ledger_template` 生成 v1 schema 2 十三列账本时，检查单份 07 要带上同一个适配层，让检查器按项目格式和项目根解析证据：

```bash
python3 <verity 仓库>/scripts/check_evidence.py <07 路径> \
  --adapter <项目根>/.verity/adapter.json
```

检查器默认只允许四状态、三结论，不接受 `带欠账` 状态与 `带欠账交付` 结论；读取历史账本时加 `--compat-debt` 显式放行。`--strict` 可叠加卡口，出现欠账会报 `E_STRICT_DEBT`。不带适配层也可以显式写 `--format v1 --root <项目根>`；旧八列账本用 `--format legacy`。

退出码：`0` 通过；`1` 有问题；`2` 参数或读取错误。

检查器只读取适配层，**不会执行** `commands` 里的命令。命令由项目自己的流程或代理在取证时执行；检查器只核对路径、模块和覆盖关系。

## 6. 换项目时改哪里

只改七处：`project`、`baseline`、`commands`、`paths`、`ledger`（可选）、`device`、`redaction`，再按新项目的模块清单更新 `modules`。规则正文、模板和脚本都不改。

如果新项目没有设备，`device.entry` 写“无设备操作”并把 `commands.device` 设为空数组；不要删字段，保持结构一致。
