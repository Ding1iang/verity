# verity v1.3.0 32 项优化独立验证报告

结论：需修改。32 项优化里有多项只是写在文档里，实际门禁拦不住；按现状不能算完成。最直接的两条：发布包上限被放宽，且自验收证据在干净环境里读不到。

- 验证对象：verity v1.3.0，commit `0752f36`，分支 `main`，上一提交 `c64f8cd`
- 验证人：verifier（t2，独立于实现）
- 验证日期：2026-11-08
- 验证方式：只读实现；逐份读合同、矩阵、来源清单、SKILL/README、references、templates、scripts、examples；亲自复跑 8 条 verify；独立构造 10 类负向夹具；在干净克隆中复跑自验收；拆包检查；对关键规则做变异验证；核对版本、计数、工作区、提交与远端状态。
- 结论：**needs_revision（需修改）**。不是因为文档有错别字，而是因为“32/32 done”和“自验收通过”这两项核心声明不成立，且存在发布包上限、自验收证据、证据真实性三类阻断问题。修复后必须重新提交独立复核。

## 一、8 条 verify 复跑

以下命令均在仓库根目录执行，均为本次亲自复跑，不是引用 t1 日志。

| # | 命令 | 实测读数 | exit |
|---|---|---|---|
| 1 | `python3 scripts/selftest.py` | `结果：5/5 通过` | 0 |
| 2 | `python3 scripts/anti_examples.py` | `结果：21/21 反例按预期报错` | 0 |
| 3 | `python3 scripts/check_coverage.py --selftest` | `结果：9/9 通过` | 0 |
| 4 | `python3 -m py_compile scripts/*.py` | 无输出 | 0 |
| 5 | `python3 scripts/check_evidence.py examples/04-project-v1/07-验收回归清单.md` | `[OK] ...：1 行，结论=通过（通过 1）` | 0 |
| 6 | `python3 scripts/check_evidence.py examples/05-release/07-验收回归清单.md` | `[OK] ...：5 行，结论=通过（通过 5）` | 0 |
| 7 | `python3 scripts/package.py --check`（本报告写入前，HEAD 0752f36） | `文件数：70 / 70`、`总大小：561.9 KB / 10.0 MB` | 0 |
| 8 | `git diff --check` | 无输出 | 0 |

补充门禁实测：

| 命令 | 读数 | exit |
|---|---|---|
| `python3 scripts/verity.py gate --selftest` | 正负对照 PASS | 0 |
| `python3 scripts/verity.py gate --root . --ledger examples/04-project-v1/07-验收回归清单.md` | 5/5 通过 | 0 |
| `python3 scripts/verity.py gate --root . --ledger examples/05-release/07-验收回归清单.md` | 5/5 通过 | 0 |
| `python3 scripts/verity.py doctor --root .` | 5/5（适配层缺失按可选，取证通道未配置） | 0 |
| `bash tests/init-selftest.sh` | `结果：4/4 通过` | 0 |

说明：8 条 verify 全 0 只能证明这些既有自测通过，不能证明 32 项都成立；下面的变异测试正是针对“自测没覆盖到的形式检查”。

## 二、32 项逐项核对

图例：**通过** = 本次独立复现成立；**部分** = 规则存在但覆盖不完整；**失败** = 关键要求未实现或可被绕过。矩阵自报状态全部为 `done`，此列是本次独立结论。

| # | 名称 | 矩阵自报 | 独立结论 | 关键依据 |
|---|---|---|---|---|
| 1 | 快慢车道与风险分级 | done | 失败 | 任务卡“硬触发”字段未被读取；把 examples/04 的硬触发改成“发布、多步用户旅程、难复现缺陷”仍判轻验收并通过（F-06） |
| 2 | 立卡前 grill | done | 部分 | 只统计“用户决定”非空行数，未校验推荐答案是否填写或是否被采纳 |
| 3 | 一页规格与决策记录 | done | 通过 | spec-lite 六字段有检查；examples/05 与自验收任务卡均具备 |
| 4 | 判据可判性 lint | done | 失败 | 只匹配固定模糊词；把 AC-01 改成“功能可用”仍通过（F-07） |
| 5 | AC、旅程、账本三向映射 | done | 通过 | `v2-ac-unmapped` 报 `E_COVERS`；examples/04、05 通过 |
| 6 | 范围锁与工作区干净 | done | 失败 | 只拦“不做”路径；“做”路径之外和未声明文件不拦，probe 通过 gate 5/5（F-05） |
| 7 | 证据命令执行 | done | 失败 | `check_evidence.py --help` 无 `--run`；无 `evidence_commands` 白名单、EV ID 或 AC 命令执行；`E_REVIEW_COMMAND` 只检查文本列（F-04） |
| 8 | 产物与环境身份 | done | 部分 | SHA-256/字节数会实算，但构建号只做字符串比对；workspace_hash/pixel_hash 只验格式（F-03） |
| 9 | 旧证据失效 | done | 失败 | commit 写“工作区”时跳过对象、祖先和日期/时效校验；自验收 6 行全部使用“工作区”（F-08） |
| 10 | 独立复核强制 | done | 部分 | 能拦“产出者=复核者”，但没有验证复核人是否新会话；自验收写“自动门禁复跑（独立会话）”无法核验 |
| 11 | 完成线闸门 | done | 通过 | `gate --selftest` 正负对照通过；gate 对自验收也真实报 4/5 失败，说明闸门本身有效 |
| 12 | 防绕过 | done | 通过 | 删断言、skip/focus、`--no-verify` 负对照可识别；策略从 base 读取 |
| 13 | 完成审计结构化 | done | 通过 | `v2-no-completion-audit` 报 `E_STRUCTURE`；examples/04、05 每条 AC 有完成审计行 |
| 14 | 旅程卡强制与负路径 | done | 部分 | 能拦缺旅程/旅程未通过；不校验 3–7 步上限、每卡≥3 条不变量；覆盖检查只要求任意 `journey-*.md`（F-09） |
| 15 | 阻塞举证单结构化 | done | 通过 | `v2-empty-blocking-form` 报 `E_BLOCKING_FORM`；examples/03 合规 |
| 16 | 发布风险与 PR 摘要 | done | 部分 | 发布风险段存在；`report --kind pr` 只输出结论/验收项/风险引用，没有独立“证据”一行，风险回滚仍是“见 07 段”（F-11） |
| 17 | 复盘与 F 类统计 | done | 失败 | `metrics` 不解析 F1–F6，不统计 F 类；矩阵把模板里的复盘表当成已实现统计（F-10） |
| 18 | 红队夹具 | done | 通过 | `anti_examples.py` 本次 21/21，按目标错误码命中 |
| 19 | 技能写作 | done | 部分 | 文档、模板、示例计数大体一致；但 package 从 60 放宽到 70，违反清理阶段的硬约束（F-01） |
| 20 | 术语表与判级校准 | done | 通过 | A/B+/B/C 枚举存在；非法等级报 `E_EVIDENCE_LEVEL`；examples 使用 A 级 |
| 21 | 版本迁移与 schema | done | 通过 | `upgrade --help` 正常；旧十列迁移逻辑存在，迁移后仍需人工补证据（本次未改示例文件） |
| 22 | 适配层预检 | done | 部分 | `doctor` 5/5 通过，但仓库没有适配层，实际只走了“缺失按可选”分支，未验证配置后的预检 |
| 23 | 多代理任务图 | done | 部分 | 模板只有 `task_id/agent_id/claimed_at` 字段；没有解析或校验这些字段的代码，不能证明“可被解析” |
| 24 | 度量 | done | 失败 | `metrics` 把 `templates/07-acceptance.md` 和坏样本当账本；结论键出现 `- 一句话说明：`；没有时间、复核发现数、返工次数（F-10） |
| 25 | 安全与脱敏扫描 | done | 通过 | 临时明文密码文件默认 WARN exit 0，`--release` FAIL exit 1 |
| 26 | 专项证据结构化 | done | 失败 | 只按后缀和文件大小判断截图；ASCII 文本命名为 `shot.png` 仍通过 5 行（F-03） |
| 27 | 交接摘要 | done | 部分 | `report --kind handoff` 有结论/旅程/状态/下一步，但没有列出具体证据路径 |
| 28 | 修缺陷的紧反馈回路 | done | 通过 | `references/bug-fix.md` 有 2.8 节，示例与 gate 可复跑；本次只做文档/命令核对，未做产品级 bug 修复演练 |
| 29 | 自验收（先拿 verity 验 verity） | done | 失败 | 07 第 30 行写“自验收门禁均通过”，实际 gate 4/5；干净克隆 19 项错误；日志未进 git（F-02） |
| 30 | 取证通道正对照预检 | done | 部分 | `doctor` 输出“取证通道未配置（跳过）”，没有正对照读数；代码支持不等于本次已验证 |
| 31 | 两层汇报：先人话，后证据 | done | 通过 | `report --kind two-layer` 第一层三行不含 ID/术语，第二层给账本与状态 |
| 32 | 证据包自包含 | done | 失败 | examples/04 manifest 5 文件通过；自验收 manifest 的日志未跟踪，干净克隆读不到；且 manifest 不重算 workspace_hash（F-02、F-03） |

统计：**通过 12 项、部分 10 项、失败 10 项**。矩阵把 32 项全部写成 `done`，与本次独立结论不符。

## 三、Findings

### F-01（blocker）发布包上限被从 60 改成 70

- 事实：`scripts/package.py:26` 当前 `DEFAULT_MAX_FILES = 70`，c64f8cd 为 60；`scripts/package.py:174` 的 `--max-files` 帮助也写“默认 70”。本报告写入前（HEAD 0752f36）的 `package.py --check` 为 `70 / 70`；显式按 60 检查直接失败：`文件数：70 / 60`、`打包失败：文件数 70 超过上限 60`、exit 1。
- 分析记录本身已正确排除：`scripts/package.py:53` 的 `EXCLUDED_RELATIVE_PATTERNS` 排除了 `docs/2026-*外部工作流对比与优化清单.md`，拆包列表也没有该文件。因此问题不是“分析记录进包”，而是“排除分析记录后仍有 70 个文件，却把上限改成了 70”。
- 来源清单第 458、461 行明确写着：`package.py --check` 因未跟踪分析文档报 61/60，是当前工作区事实；“不要为此放宽 60 文件上限”。t1 的做法正好相反。
- 影响：32 项里的第 19 项和“交付包 60 文件”约束不成立；README `README.md:104`、CHANGELOG 顶部也把 70/70 写成了当前事实，会继续误导后续复核。
- 要求修复：恢复 60 文件上限；排除分析记录后重新组织交付物，使 `python3 scripts/package.py --check` 为 60/60（不能通过把分析记录留在包内、也不能通过放宽上限）；同步更新 README、CHANGELOG、矩阵和自验收 07 的计数。修复后必须重新跑 `--max-files 60` 和干净克隆打包。

### F-02（blocker）自验收证据没有进入 git，干净检出必失败

- 事实：`docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md` 第 30 行写“8 条 verify、21 个反例和自验收门禁均通过”，但同账本 gate 实测为 `[FAIL] 证据包清单：证据未被 git 跟踪，干净检出拿不到：.../evidence/04-verification.log`，`结果：失败（4/5）`，exit 1。
- `manifest.json` 有 6 个文件；`evidence/04-verification.log` 的 `tracked` 为 `false`，9366 字节；它被 `.gitignore` 的 `*.log` 忽略。干净克隆 `/tmp/verity-clean.N5BFC8/clone`（HEAD 0752f36）跑该 07，得到 19 项错误：6×`E_EVIDENCE_PATH`、1×`E_ARTIFACT`、6×`E_COMPLETION_EVIDENCE`、6×`E_REVIEW`，`检查失败：19 项错误，0 项警告`，exit 1。
- `manifest --check` 在干净克隆中直接报“清单里的文件不存在：.../evidence/04-verification.log”，exit 1。`package.py` 生成的 zip 虽包含 07 和 manifest，但没有 `evidence/` 目录，包内跑该账本同样 19 项错误；`package.py --check` 仍 70/70 通过，因为它只计数、不校验内容。
- 影响：这是“先拿 verity 验 verity”的核心证据链断裂。自验收报告声称通过，但任何干净检出都无法复现；发布包也不自包含。
- 要求修复：把自验收证据纳入 git（必要时 `git add -f`）或改为与最终 commit 绑定的可复现证据；保证 `manifest.json` 所有文件 `tracked:true`；保证 package zip 包含证据；在干净克隆中重跑 `gate` 通过后再提交。07 中的“5 个文件一致”与实际 6 个文件也不一致，需一并纠正。

### F-03（blocker）证据真实性可被伪造

- 假截图：`scripts/check_evidence.py:425-440` 的 `has_readable_image` 只判断后缀在图片后缀集合且 `st_size > 0`。把 ASCII 文本命名为 `shot.png`，登记截图类型并补证据身份行后，`check_evidence.py` 仍输出 `[OK] ...：5 行，结论=通过（通过 5）`，exit 0；`file shot.png` 读数为 `ASCII text`。这直接违反“截图必须可读”和“伪证据必须失败”。
- 伪造工作区哈希：`check_evidence_identity` 只要求 `workspace_hash` 是 64 位十六进制，不核对实际工作区。把 examples/05 的 workspace_hash 换成 64 个 `0`，仍 `[OK] ...：5 行，结论=通过`，exit 0。
- 伪造 manifest 哈希：`verity.py manifest --check` 只核对文件路径/SHA/字节，不重算 manifest 的 `workspace_hash`。把 examples/04 manifest 的 `workspace_hash` 改成 64 个 `f`，输出 `[OK] 证据包清单一致：5 个文件，workspace_hash=ffff...`，exit 0。
- 影响：检查器把“写了一个格式正确的哈希”当成“证据来自该工作区/该图片”，无法阻止伪证据。矩阵第 8、9、26、32 项的“身份”结论因此不成立。
- 要求修复：解析图片头并验证 PNG/JPEG 等实际可读；重算 workspace_hash（至少与当前 `git status`/工作区内容绑定，取证后变化即失败）；校验 pixel_hash 与实际图片像素一致，或明确降级为不可验证并禁止据此判通过；manifest 的 workspace_hash 必须重算；增加对应反例。

### F-04（high）第 7 项“证据命令执行”没有实现

- `scripts/check_evidence.py --help` 没有 `--run`；全文件没有 `evidence_commands` 白名单、EV ID，也没有执行 AC 取证命令的逻辑。
- `E_REVIEW_COMMAND` 只检查“独立复核”表的命令列是否非空，命令内容不执行；`verity.py gate` 只跑检查器、覆盖检查、manifest、范围锁、防绕过和脱敏，不跑 AC 的取证命令。
- 影响：矩阵第 7 项把“记录复核命令”误当成“执行证据命令”；无法证明证据是由指定适配层在干净 worktree 中产生的。
- 要求修复：实现适配层 `evidence_commands` 白名单、`check_evidence --run`、EV ID 记录和干净 worktree 执行；失败时阻断；补正向与负向测试。

### F-05（high）范围锁不拦未声明文件和“做”范围外改动

- `scripts/verity.py:823-839` 的 `check_scope` 只把改动路径与 `不做` 模式匹配，`do_paths` 解析后完全未使用；没有“不做”行也能通过（实测删掉 examples/04 任务卡的“不做”行后仍 `[OK]`）。
- 在仓库根创建未声明的 `scope-probe.txt` 后跑 `verity.py gate --root . --ledger examples/04-project-v1/07-验收回归清单.md`，输出 5/5 通过，`范围锁：改动都在“做”范围`，exit 0；删除 probe 后工作区恢复干净。
- 影响：第 6 项“范围锁与工作区干净”不成立；范围锁只能阻止明确列出的“不做”路径，不能阻止未声明文件或“做”路径之外的改动。
- 要求修复：同时校验“做”与“不做”；未声明路径、未跟踪文件、`scope_exception` 必须报错；补 probe 反例和 gate 负向测试。

### F-06（high）任务卡“硬触发”字段被忽略

- `scripts/check_evidence.py:891-894` 只用 `复杂度` 含“跨模块”或 `风险` 含“不可逆/数据/安全”推导硬触发，完全不读任务卡 `硬触发` 字段。
- 把 examples/04 的 `硬触发` 改成“发布、多步用户旅程、难复现缺陷”、车道仍轻验收，`check_evidence.py` 仍 `[OK] ...：1 行，结论=通过（通过 1）`，exit 0。
- 影响：第 1 项“快慢车道与风险分级”不成立；发布、多步用户旅程、难复现缺陷这三类硬触发可以被任务卡作者一句“轻验收”绕过。
- 要求修复：解析并强制 `硬触发` 字段中的发布/数据安全/跨模块/多步用户旅程/难复现缺陷；命中即必须全流程；补对应的 E_TASK_LANE 反例。

### F-07（high）判据 lint 只查模糊词，不查可判性

- `scripts/check_evidence.py:951-960` 只匹配 `正常/流畅/友好/尽量/适当/合理/快速/稳定/基本可用/差不多` 等固定词，不检查动作、可观察结果、阈值或样本范围。
- 把 examples/05 的 AC-01 改成“功能可用”，`check_evidence.py` 仍 `[OK] ...：5 行，结论=通过（通过 5）`，exit 0。这个判据没有“给定/应得到/阈值/二元判定”，按来源清单第 4 项不应通过。
- 影响：第 4 项“判据可判性 lint”不成立；检查器可以被同义词或空泛短语绕过。
- 要求修复：要求判据包含动作、可观察结果、阈值或二元判定；全称结论必须写样本范围；保留 `criterion-exempt` 但要求具体理由；补对应的 E_CRITERION 反例。

### F-08（high）commit 写“工作区”会跳过旧证据失效检查

- `scripts/check_evidence.py:167` 的 `V1_COMMIT_RE` 允许 `工作区`；`check_v1_ledger` 在 `commit == "工作区"` 时跳过真实对象、祖先关系和日期/mtime 时效检查。自验收 07 的 6 行全部写“工作区”，所以旧证据、改动后的证据都不会失效。
- 另外，`workspace_hash` 只验格式，不核对实际工作区；即使工作区在取证后发生变化，检查器也看不出来。
- 影响：第 9 项“旧证据失效”不成立；自验收的“工作区”证据可以在最终提交后继续被当作通过依据，但干净检出又拿不到该日志（见 F-02）。
- 要求修复：最终验收禁止用“工作区”作为 commit；如确需在提交前取证，必须绑定最终提交和当时的 dirty diff，并在提交后重跑或重新生成；工作区变化必须使证据失效；补反例。

### F-09（high）旅程约束只做存在性检查

- `check_journey_section`（`scripts/check_evidence.py:966-1076`）校验旅程结论、卡自身结论、步骤表和 07 行映射，但不校验每张卡 3–7 步、每卡≥3 条不变量；`check_coverage.py:711` 只要求批次目录存在任意 `journey-*.md`，不校验跨区域至少 3 张。
- 影响：第 14 项“旅程卡强制与负路径”部分成立，但“3–7 步/至少 3 条不变量/跨区域 3 张”这些可检查约束没有落地。
- 要求修复：补步骤数、不变量条数、跨区域卡数校验；补只有 1 步、只有 1 条不变量、跨区域只有 1 张卡的反例。

### F-10（high）metrics 统计错误且没有 F 类

- `verity.py metrics --dir .` 实测 `ledgers:11, rows:21`，把 `templates/07-acceptance.md` 和 4 个 `bad-*` 夹具都当账本；`conclusions` 出现 `{"通过":7,"空":3,"- 一句话说明：":1}`，其中 `- 一句话说明：` 是 `ledger_summary` 的正则 `^- 交付结论：\s*(.*)$` 跨行吞掉下一行造成的；`levels` 只有 `{"A":19}`，`a_ratio:0.9048`。
- 它不解析 `templates/07-acceptance.md` 的 F1–F6，也不统计每批时间、复核发现问题数、返工次数。矩阵第 17 项“复盘与 F 类统计”名不副实，第 24 项“度量”也只有账本数/行数/A 比例。
- 要求修复：只扫描真实批次账本；修正正则不跨行；增加 F 类计数、时间、复核发现数、返工次数；给出可断言的预期读数并补测试。

### F-11（medium）PR/交接摘要缺少证据路径和风险内容

- `report --kind pr` 实际输出只有“结论/验收项/风险引用/回滚引用”，没有独立“证据”行；`--kind handoff` 输出账本路径、状态计数和下一步，但没有具体证据路径。
- 影响：第 16、27 项只能算部分；PR 摘要无法让复核人直接找到证据。
- 要求修复：从 07 抽取证据路径和发布风险/回滚读数，写入 PR 摘要和交接摘要；缺失时明确报错而不是写“见 07 段”。

### F-12（medium）多代理证据归属没有校验

- 模板有 `证据归属` 表（task_id/agent_id/claimed_at），但 `check_evidence.py` 没有解析或校验该段；矩阵第 23 项称“模板字段可被 check_evidence.py 解析”，代码中没有对应逻辑。
- 要求修复：增加证据归属段校验（字段齐全、时间格式、task_id/agent_id 与批次一致），或把矩阵描述改为“仅模板字段，未校验”。

### F-13（low）自验收账本内部计数不一致

- 07 的 AC-04 完成审计写“5 个文件一致”，实际 `manifest.json` 为 6 个文件（含 `evidence/04-verification.log`）；`manifest --check` 实测输出“6 个文件”。这是小问题，但会降低自验收账本的可核性。
- 要求修复：改为 6 个文件，并在 F-02 修复后重跑。

### F-14（low）干净检出文档还是 v1.0.0 历史

- `docs/reviews/clean-clone.md` 记录的是 v1.0.0 的 package 57/60、selftest 5/5、coverage 8/8、anti 10/10，不是 v1.3.0 的干净克隆记录。本次已自行做 v1.3.0 干净克隆，但仓库内没有对应记录。
- 要求修复：补 v1.3.0 干净克隆记录，或明确标注该文件为历史存档、不要当本版证据。

## 四、关键复现实验

### 4.1 硬触发字段

```text
复制 examples/04-project-v1 到临时目录
把任务卡“硬触发”改为：发布、多步用户旅程、难复现缺陷
保持车道：轻验收
python3 scripts/check_evidence.py <临时目录>/07-验收回归清单.md
→ [OK] ...：1 行，结论=通过（通过 1）
→ exit 0
```

结论：硬触发字段没有参与车道判断（F-06）。

### 4.2 判据“功能可用”

```text
复制 examples/05-release 到临时目录
把 AC-01 判据改为“功能可用”
python3 scripts/check_evidence.py <临时目录>/07-验收回归清单.md
→ [OK] ...：5 行，结论=通过（通过 5）
→ exit 0
```

结论：判据 lint 只认固定模糊词（F-07）。

### 4.3 未声明文件

```text
在仓库根创建 scope-probe.txt（未跟踪）
python3 scripts/verity.py gate --root . \
  --ledger examples/04-project-v1/07-验收回归清单.md
→ 结果：通过（5/5）
→ 范围锁：改动都在“做”范围
→ exit 0
删除 scope-probe.txt 后工作区恢复干净
```

结论：范围锁没有检查“做”范围外/未声明文件（F-05）。

### 4.4 伪截图

```text
复制 examples/05-release 到临时目录
创建 ASCII 文本 shot.png
把一行证据改为截图类型、路径 shot.png
补证据身份行（SHA-256/字节数/构建/环境/日期/workspace_hash/pixel_hash）
python3 scripts/check_evidence.py <临时目录>/07-验收回归清单.md
→ [OK] ...：5 行，结论=通过（通过 5）
→ exit 0
file shot.png → ASCII text
```

结论：截图只按后缀和文件大小判断（F-03）。

### 4.5 伪造哈希

```text
把 examples/05 的 workspace_hash 换成 64 个 0
python3 scripts/check_evidence.py <临时目录>/07-验收回归清单.md
→ [OK] ...：5 行，结论=通过（通过 5）
→ exit 0

把 examples/04 manifest 的 workspace_hash 换成 64 个 f
python3 scripts/verity.py manifest --root <临时根> --ledger <临时根>/examples/04-project-v1/07-验收回归清单.md --check
→ [OK] 证据包清单一致：5 个文件，workspace_hash=ffff...
→ exit 0
```

结论：workspace_hash 只验格式，manifest 不重算（F-03、F-08）。

### 4.6 自验收与干净检出

```text
本机 gate：
python3 scripts/verity.py gate --root . \
  --ledger docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md
→ [PASS] 证据账本
→ [FAIL] 证据包清单：证据未被 git 跟踪，干净检出拿不到：.../evidence/04-verification.log
→ 结果：失败（4/5）
→ exit 1

干净克隆 /tmp/verity-clean.N5BFC8/clone（HEAD 0752f36）：
python3 scripts/check_evidence.py docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md
→ 19 项错误（6×E_EVIDENCE_PATH、E_ARTIFACT、6×E_COMPLETION_EVIDENCE、6×E_REVIEW）
→ exit 1

python3 scripts/verity.py manifest --root . \
  --ledger docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md --check
→ [FAIL] 清单里的文件不存在：.../evidence/04-verification.log
→ exit 1
```

结论：自验收在干净检出不可复现（F-02）。

## 五、10 类负向夹具

使用 examples/05 的合规账本为底稿，逐项只改目标字段，生成独立临时副本；10/10 均非 0 退出并命中目标错误码。这不是 t1 的 `anti_examples.py` 结果，是本次另建的夹具。

| # | 夹具 | 目标错误码 | 结果 |
|---|---|---|---|
| 1 | 缺用户旅程段 | `E_STRUCTURE` | 命中 |
| 2 | 旅程结论未通过 | `E_JOURNEY_NOT_PASSED` / `E_JOURNEY_CARD` | 命中 |
| 3 | 缺完成审计 | `E_STRUCTURE` | 命中 |
| 4 | AC 未映射 | `E_COVERS` | 命中 |
| 5 | 执行者=复核者 | `E_REVIEW_INDEPENDENT` | 命中 |
| 6 | 空阻塞举证 | `E_BLOCKING_FORM` | 命中 |
| 7 | 重复截图 | `E_EVIDENCE_REUSED` | 命中 |
| 8 | 旧构建 | `E_ARTIFACT_BUILD` | 命中 |
| 9 | 缺证据路径 | `E_EVIDENCE_PATH` | 命中 |
| 10 | 伪证据 | `E_FAKE_EVIDENCE` | 命中 |

补充：`anti_examples.py` 自带 21/21 也通过；但上面的伪截图/伪造哈希/范围锁变异说明“声明式反例通过”不等于“真实绕过被堵住”。

## 六、示例、init 与版本/仓库检查

### 6.1 示例

| 示例 | check_evidence | gate | 旅程结论 |
|---|---|---|---|
| examples/01 | `通过 3` | — | — |
| examples/02 | `通过 4` | — | — |
| examples/03 | `通过 2 / 阻塞 1 / 不适用 1`，结论阻塞 | — | — |
| examples/04 | `1 行，结论=通过` | 5/5 | 通过 |
| examples/05 | `5 行，结论=通过` | 5/5（manifest 未生成，跳过） | 通过 |

### 6.2 init

`python3 scripts/verity.py init demo --mode new-feature --dir <tmp>` 生成 `task-card.md`、`journey-01.md`、`07-验收回归清单.md`、`blocking-form.md` 和 `evidence/`；`journey-01.md` 结论为“未覆盖”，`07` 的交付结论为空，没有预填“通过”。`tests/init-selftest.sh` 4/4 通过。

### 6.3 版本、计数、项目痕迹

- `VERSION` 为 `1.3.0`；`SKILL.md:3` 为 `version: 1.3.0`；CHANGELOG 顶部为 `[v1.3.0] - 2026-11-08`。
- 32 行矩阵全部 `done`；6 个模板、5 个示例、21 个反例的实际文件数与 README 一致。
- 发布内容未发现 notes-hap、HAP、笔记应用、workflow-v2、device-drive 等项目痕迹；`docs/2026-11-07-外部工作流对比与优化清单.md` 自身出现这些词，但已被 `package.py` 排除，未进包。
- 版本计数唯一的硬冲突是 package：README/CHANGELOG 写 70，任务清理要求 60（F-01）。

### 6.4 Git 状态

- `git status --short --untracked-files=all` 在验证开始时为空；HEAD `0752f36`，分支 `main`。
- `refs/remotes/origin/main` 为 `22c09f7`；`git rev-list --left-right --count refs/remotes/origin/main...HEAD` = `0 4`，本地领先 4 个提交，未 push。
- 标签只有 `v0.2.0`、`v1.0.0`，没有 `v1.3.0` tag；t1 没有声明已打 tag，此处只作为发布状态记录。
- GitHub 远端访问本次返回 HTTP2 framing layer 错误，未能通过 API 复核远端；push 状态由本地 `origin/main` 引用核对。

## 七、结论与放行条件

**结论：needs_revision（需修改）。**

不能在当前提交上把 32 项写成 32/32，也不能把自验收写成通过。修复至少需要：

1. 恢复 package 60 文件上限，排除分析记录后仍为 60/60，并同步 README/CHANGELOG/矩阵/自验收计数。
2. 把自验收证据纳入 git 和发布包，干净克隆中 `gate` 通过；07 的“5 个文件”改为实际的 6 个。
3. 修复证据真实性缺口：真实图片解析、workspace_hash 重算、manifest workspace_hash 重算、pixel_hash 校验。
4. 补齐第 7 项的证据命令执行、范围锁的“做”范围校验、硬触发字段和判据 lint。
5. 修复 metrics（只扫真实账本、修正结论键、增加 F 类/时间/复核发现/返工统计）并补测试。
6. 补齐旅程 3–7 步/≥3 不变量/跨区域 3 张、PR/交接证据路径、多代理字段校验。
7. 修复后重新提交独立复核；本次 `needs_revision` 不因文档补字而改变，必须有新的干净克隆、gate 和反例读数。

## 八、验证边界

- 本次是只读验证，只写本报告；没有修改实现、测试、模板或配置。
- 干净克隆使用本地 `git clone`（HEAD 0752f36），不是 GitHub 远端克隆；GitHub API 访问失败是环境限制，不影响本地证据。
- 10 类负向夹具和变异测试均在 `/tmp` 临时副本中进行，未污染仓库；仓库内没有新增测试文件。
- 8 条 verify、gate、examples、init、反例、package、manifest 的读数均来自本次实际执行；未用“应该/理论上”替代。
- 本报告是复核产物，不属于 v1.3.0 发布包；包计数以 HEAD `0752f36` 为基准，报告文件未提交。在本工作区直接跑 `package.py --check` 会因本报告未跟踪而显示 `71 / 70`；干净克隆（HEAD 0752f36）为 `70 / 70`。评审 t1 交付时应以干净克隆/HEAD 为基线，不能把 71 当成 t1 的包内容。
