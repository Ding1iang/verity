# verity

给 AI 编码代理用的交付验收技能包。它不教怎么写代码，只回答一个问题：**当代理说“做完了”，凭什么？**

verity 用任务卡先定靶，用证据分级判断结论能不能成立。v1 默认模板（schema 2）用十三列账本和三种包结论：通过、未交付（失败）、未交付（阻塞）；检查器默认拒绝“带欠账/带欠账交付”，读取历史账本时用 `--compat-debt` 显式放行；`--strict` 仍可叠加卡口。旧八列账本保留通过、未通过、阻塞三态。核心只有一句：**结论只能比证据小。**

从 1.3.0 起，32 项工作流优化全部落到规则、模板、检查器和门禁：任务卡先判快慢车道并锁范围，账本强制旅程、完成审计和独立复核，证据绑定产物身份与 SHA-256，`verity.py gate` 成为本地完成线，`anti_examples.py` 用 42 个反例证明门禁会报红。

从 1.2.0 起，修缺陷不再以“最小修复”为目标，而是按根因做完整修复并过完成门禁：最终构建跑完整矩阵、交付物自包含、可补项不能留成欠账。

从 1.1.0 起，批次验收还要过一层“用户旅程”：先写 3–7 步的连续使用路径，每一步同时看可见变化和跨区域不变量；没有旅程卡，批次最多记“未覆盖”，不能判通过。规则见 `references/journey-acceptance.md`，模板见 `templates/journey-card.md`。

## 安装

要求：

- Python 3.9 或更新版本（脚本只用标准库，不需要 `pip install`）。
- `git` 可选，只在克隆仓库或打包检查时用到。
- 不需要联网，不需要其他项目或本机配置。

三种用法，任选一种：

1. **压缩包**：在仓库根目录执行 `python3 scripts/package.py --zip` 生成 `dist/verity.zip`（压缩包不提交到仓库，需要时重新生成），解压后进入 `verity/` 目录。
2. **私有仓库**：`git clone <仓库地址> verity`，进入 `verity/`。仓库地址向仓库管理员索取，本文件不写死。
3. **作为 AI 客户端技能**：把整个目录放进客户端约定的技能目录（例如 `~/.claude/skills/verity/`），入口是根目录的 `SKILL.md`。客户端不支持技能目录时，让代理先读 `SKILL.md` 即可。

安装是否成功，按下一节第 1 步验证。

## 十分钟快速开始

以下命令都在仓库根目录执行。命令里的 `python3` 在 Windows 上换成 `py -3`。每个代码块后面是应该看到的结果。

### 第 1 步（约 2 分钟）：运行自检

```bash
python3 --version
python3 scripts/selftest.py
```

预期最后一行：

```text
结果：5/5 通过
```

这一步会用好样本和四个坏样本验证检查器：缺证据、假路径、旧结论词、重复状态源都必须被拦住。

### 第 2 步（约 3 分钟）：跑五个示例

```bash
python3 scripts/check_evidence.py examples/01-new-feature/07-验收回归清单.md
python3 scripts/check_evidence.py examples/02-bug-fix/07-验收回归清单.md
python3 scripts/check_evidence.py examples/03-blocking/07-验收回归清单.md
python3 scripts/check_evidence.py examples/04-project-v1/07-验收回归清单.md
python3 scripts/check_evidence.py examples/05-release/07-验收回归清单.md
```

预期五行摘要：

```text
[OK] <仓库根>/examples/01-new-feature/07-验收回归清单.md：3 行，结论=通过（通过 3）
[OK] <仓库根>/examples/02-bug-fix/07-验收回归清单.md：4 行，结论=通过（通过 4）
[OK] <仓库根>/examples/03-blocking/07-验收回归清单.md：4 行，结论=阻塞（通过 2 / 阻塞 1 / 不适用 1）
[OK] <仓库根>/examples/04-project-v1/07-验收回归清单.md：1 行，结论=通过（通过 1）
[OK] <仓库根>/examples/05-release/07-验收回归清单.md：5 行，结论=通过（通过 5）
```

五条命令的退出码都是 0。这里的 0 只表示账本格式合规、状态自洽，**不表示交付通过**；第三个示例的结论明确是阻塞。第四个示例是项目 v1 schema 2 十三列格式，检查器按 marker 自动识别；也可以用 `--format v1 --root examples/04-project-v1` 显式指定。第五个示例展示发布模式的五项检查，不包含真实的构建或发布动作。

### 第 3 步（约 2 分钟）：看懂一份账本

打开 `examples/03-blocking/07-验收回归清单.md`，重点看三处：

1. **账本**：一行一个验收项，八列信息齐全；阻塞项的证据指向举证单。
2. **收口**：旧八列结论必须是三态之一（v1 默认模板用三包结论），计数要和账本行数对得上。
3. **举证单**：`blocking-form.md` 里四个维度、正对照和解锁条件都填满，缺一项就只能记未通过。

### 第 4 步（约 2 分钟）：开始自己的任务

```bash
python3 scripts/verity.py init "示例任务" --mode acceptance --dir tmp
```

这条命令会生成 `tmp/<日期>-示例任务/`，里面有任务卡、`journey-01.md`、空账本、举证单和 `evidence/`；旅程结论默认是“未覆盖”，不会预填通过。按 `examples/` 里的样子填写任务卡和账本，然后执行：

```bash
python3 scripts/check_evidence.py "tmp/<日期>-示例任务/07-验收回归清单.md"
```

模板原样运行时检查器会报错，因为验收项、判据、最低证据、证据、状态和复核人还没填。这是预期行为，不是安装失败；逐行填完再跑，直到出现 `[OK]`。

### 第 5 步（约 1 分钟）：打包检查

```bash
python3 scripts/package.py --check
```

预期包含：

```text
检查通过（--check 模式，未生成 zip）
```

当前仓库实测为 60 / 60 文件；上限是 60 文件、10 MB。

`--check` 只统计和校验，不生成压缩包。文件数或体积超过上限时会直接失败，不生成 zip。

### 可选：把完成线装成 pre-push

在仓库根的 `.git/hooks/pre-push` 写入下面内容，并执行 `chmod +x .git/hooks/pre-push`；推送前会自动跑账本、覆盖、清单、范围锁和脱敏检查，任一失败就阻止推送：

```sh
#!/bin/sh
python3 scripts/verity.py gate --root . \
  --ledger docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md --release
```

这不是服务端强制，只是本地提醒；真正的强制线在 CI 的“本地完成线门禁”步骤。

## 四种模式

四种模式不是四套流程，而是同一套验收骨架的四个入口，最后都落到同一份 `07-验收回归清单.md`。一次交付只选一个主模式。

| 模式 | 当前要回答的问题 | 第一步 | 收口条件 | 详见 |
|---|---|---|---|---|
| 新功能 | 要不要做、做成什么样 | 把需求逐条改写成验收项，立任务卡 | 全部验收项有达标证据 | `references/new-feature.md` |
| 修缺陷 | 为什么不符合预期 | 先复现并留下失败证据，再定位根因 | 原缺陷复现项与回归项都通过 | `references/bug-fix.md` |
| 验收 | 现在能不能算完成 | 只取证判级，不改代码 | v1 三包结论（旧八列三态）写入 07 账本 | `references/acceptance.md` |
| 发布 | 这一批能不能对外 | 汇总已有账本，补版本、更新日志、回滚点 | 发布检查全过，账本归档 | `references/release.md` |

选择方法：看当前必须回答哪个问题，只选一个入口。新功能和修缺陷在收尾时切到验收视角，发布前切到发布视角，但账本始终是同一份。

纯视觉优化（“觉得丑”类）不是第五种模式：不改业务行为、不加能力时，设计侧和落地侧走 `references/ui-improvement.md`，验收仍按 `references/visual.md`。

## 接到项目上

verity 仓库只放通用规则；项目根、门禁命令、设备入口、07 目录、证据目录和脱敏规则都放项目自己的适配层。

1. 复制 `templates/adapter.json` 到 `<项目根>/.verity/adapter.json`，按 `references/adapter.md` 填写。适配层只描述项目事实，不写凭据，也不复制进 verity 仓库。项目把适配层放在别处时，命令里用 `--adapter <显式路径>` 覆盖默认值；显式路径优先。检查器也会自动发现项目验收目录下的 `verity-适配层.json`，不要维护第二份配置。
2. 复制 `templates/coverage-master.md` 到项目的验收目录，一行一个在用模块或用户路径。总表只记 07 是否存在、是否不适用，不写通过/失败；通过/失败仍只从 07 读。
3. 检查覆盖关系：

```bash
python3 scripts/check_coverage.py <覆盖总表> \
  --adapter <项目根>/.verity/adapter.json \
  --project-root <项目根>
```

检查器只读适配层，不执行里面的命令；它查的是结构、路径和数量，不判断证据真假。

## 五个示例

| 示例 | 演示什么 | 入口文件 |
|---|---|---|
| 新功能 | 需求拆成三条可判验收项，主路径、空结果、默认行为各有证据 | `examples/01-new-feature/README.md` |
| 修缺陷 | 从复现、根因四问到根因修复、完成门禁和独立复核的完整链路 | `examples/02-bug-fix/README.md` |
| 阻塞 | 四维取证与正对照怎么写，为什么阻塞不是通过 | `examples/03-blocking/README.md` |
| 项目 v1 十三列 | 项目自己的 schema 2 十三列账本如何被通用检查器识别，演示显式格式与适配层接入 | `examples/04-project-v1/README.md` |
| 发布 | 验收通过后，版本、更新日志、干净构建、回滚点与发布后冒烟如何逐项留证 | `examples/05-release/README.md` |

每个示例目录都含输入、填写完成的任务卡、07 账本和预期输出；阻塞示例另有举证单。示例里的项目和读数是演示数据，用来说明格式，真实任务必须换成自己的实测记录。

## 目录结构

```text
verity/
├── SKILL.md                 # 技能入口：何时用、四种模式、五步流程、四条硬规则
├── references/              # 规则正文：证据、验收、验收执行、四种模式、视觉、视觉优化、行为性能、项目适配层
├── templates/               # 六份可复制模板：任务卡、07 账本、阻塞举证单、适配层、覆盖总表、用户旅程卡
├── examples/                # 五个端到端示例
├── scripts/                 # init、doctor、gate、manifest、report、metrics、upgrade、scan、自测、账本/覆盖检查、反例、打包（纯标准库）
├── tests/                   # init 命令自测（bash）
├── docs/                    # 设计说明、外部来源与复核记录
└── README.md
```

## 限制

- **检查器只查形式，不查真假。** `check_evidence.py` 能验证默认 v1 schema 2 十三列或旧八列的字段、状态、证据文件是否存在、截图是否有可读图片、证据自述是否只覆盖主路径/用门禁替代探针/设备未验却写通过、commit 是否真实且为 HEAD 祖先、证据是否早于被测版本、旧结论词和计数是否一致；它无法证明证据内容真实、充分或覆盖了声明范围。真实性由复核人负责。
- **不自动取证，也不自动改账本。** 证据要由执行者按判据实际跑出来；检查器只报错，不替人补证据。
- **门禁是本地入口。** `verity.py gate` 只读账本、覆盖表、清单和范围锁，不需要外部服务；它不能替代 CI 或人工发布决策。
- **不替代人的发布决策。** 发布模式给出检查项和账本要求，最终是否对外由人决定。
- **不绑定语言、框架和平台。** 示例用 Python 命令行只是为了能直接跑；规则本身与语言无关。
- **示例是演示数据。** 示例中的版本号、测试读数和项目名不是真实项目记录，不能当作证据复用。
- **一次交付一份 07。** 后续批次新建账本并引用旧批次，不覆盖历史；同一目录出现第二份 07 会被检查器判错。
- **项目专属材料不进仓库。** 设备适配、真实数据、凭据、内部地址和具体项目结构都留在仓库之外，判断标准是“换个项目、换台机器还能用吗”。详见 `docs/design.md` 第 4 节。
- **仓库在自验收通过前保持私有。** 自验收完成并复核通过后才考虑开源，详见 `docs/design.md` 第 5 节。

## 相关文档

- 技能入口：`SKILL.md`
- 证据分级与假结论：`references/evidence.md`
- 任务卡、v1 schema 2 十三列、四状态与包结论、旧八列三态：`references/acceptance.md`
- 验收执行、批量与复测：`references/acceptance-run.md`
- 视觉验收：`references/visual.md`
- 纯视觉优化：`references/ui-improvement.md`
- 行为与性能：`references/behavior-perf.md`
- 42 类反例与红队夹具：`docs/reviews/anti-examples.md`
- 本机空目录复跑记录：`docs/reviews/clean-clone.md`
- 新功能模式：`references/new-feature.md`
- 修缺陷模式：`references/bug-fix.md`
- 发布模式：`references/release.md`
- 项目适配层契约：`references/adapter.md`
- 设计说明与仓库边界：`docs/design.md`
- 外部来源与核验日期：`docs/sources.md`
- 32 项优化落地矩阵：`docs/optimization-matrix.md`
- 外部工作流对比与优化清单（分析记录，不是规则正文）：`docs/2026-11-07-外部工作流对比与优化清单.md`
