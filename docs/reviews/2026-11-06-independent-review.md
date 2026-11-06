# 08 独立复核报告（T5）

- 复核对象：2026-11-06 全量 8 批、两个 T4 真实任务试点、verity v1.0.0
- 复核人：reviewer（独立于实现，只读复核）
- 复核日期：2026-11-07
- 复核方式：逐份读 07 与证据；重跑 `check_evidence --strict`、`check_coverage`、`check-workflow-consistency`、`check-coverage-matrix`；复算 HAP SHA-256；核对临时 worktree 的 HEAD/status；从私有仓库重新克隆 v1.0.0 并复跑 selftest/package/anti_examples；核对 GitHub API 的仓库、Release 与 CI 状态。

> T5d 复审更新（2026-11-07）：见第九节；最新交付结论为 **通过**；T5c“未交付（失败）”、T5b“未交付（阻塞）”与 T5“未交付（失败）”均保留为历史判定。

## 结论

**未交付（失败）。**

8 批账本全部存在，字段、证据路径和结论语义一致；覆盖总表没有把“已覆盖”误写成“通过”；T4 两份 07 均为 4/4 通过；verity v1.0.0 已发布到私有仓库，tag、Release、CI 与干净克隆均可核。

但导入导出/PDF 与响应式/无障碍/性能两批仍有未闭合的失败项，不能写成“通过”。因此团队目标的“8 批全量验收”尚差 2 批，“v1.0 真实可用”不成立，整体只能判 **未交付（失败）**。这不是复核材料造假，而是交付范围本身未完成。

## 一、8 批逐批复核

| 批次 | 07 结论 | 独立复核 | 关键依据 |
|---|---|---|---|
| 加密回收站 | 通过 7/7 | 通过 | 3aad84de；加密后 DB 无明文，错密码提示正确，回收站恢复仍加密，彻底删除无残留；证据类型与路径匹配 |
| 启动与数据 | 通过 5/5 | 通过 | 706a1d6f；HAP 7e32cc8b…（9,492,557B，仓库内实算一致）；测试从 23:33:49 开始，晚于 commit 23:25:37；T0 已改 3aad84de |
| 搜索收藏标签 | 通过 5/5 | 通过 | 3aad84de；搜索、收藏、标签入口与 DB 读数一致 |
| 日历待办 | 通过 6/6 | 通过 | 3aad84de；待办新建/勾选/删除、日期与 DB 一致 |
| 树导航 | 通过 7/7 | 通过 | 3aad84de；移动/删除/恢复、展开/多选均有补充 DB 读数；性能三次 176/251/247ms，中位 247ms ≤500ms |
| 编辑与自动保存 | 通过 6/6 | 通过 | 基线 3aad84de 5 项 + AC-02 修复 f7cd4f76；<800ms 强杀仍丢最后输入但已显示“● 未保存”，等待 2 秒保存，属已记录的残余行为 |
| 导入导出/PDF | 未交付（失败）4/6 | **不通过** | AC-03 PDF 同段加粗/行内代码/链接被拆行；AC-05 13B 损坏 md 未报错并导入垃圾页 `3d4ab352…` |
| 响应式/无障碍/性能 | 未交付（失败）3/7 | **不通过** | AC-01/02 原生 320/380 窗口被 WM 钳到 480vp；AC-04 Ctrl+F/Z/S 无效；AC-05 40/40 个按钮无可读名称 |

8 批 `check_evidence.py --strict` 全部 exit 0；`check_coverage.py` 读数为 8 行、已覆盖 8/缺失 0/不适用 0、账本 8/8、通过 6/失败 2/阻塞 0；`check-workflow-consistency` 全绿；`check-coverage-matrix.py` 7/7 通过。

## 二、覆盖语义与互链

- `00-覆盖总表.md` 为 10 列，8 行全部“已覆盖”；表头和说明反复写明“已覆盖只表示账本存在，不判通过”“不能把已覆盖当成已验”。说明段的 6 通过/2 失败/0 阻塞与各批 07 一致。
- 总表指向 `docs/测试/回归/覆盖矩阵-M1-M14.md` 为分层验收唯一真相源，`docs/测试/全功能走查清单.md` 仅作历史件；两处互链存在，语义分工写明。
- 覆盖矩阵是 2026-09-14 R4 的分层台账，不直接表达本批通过状态；不能用它替代 07 的批次结论。
- 未发现空账本、重复 07、旧结论词或“已覆盖=通过”的误写。

## 三、T4 两份试点

| 试点 | 07 结论 | 独立复核 | 关键依据 |
|---|---|---|---|
| 关于页复制版本号 | 4/4 通过 | 通过 | 基线 3aad84de；功能 706a1d6f；干净 worktree HAP `334e4c2d…`（9,492,560B）；构建日志 17s739；干净证据 00:19；metrics 记录用户介入 0、captain 1、主动阻塞 0 |
| 编辑保存提示修复 | 4/4 通过 | 通过 | 基线 3aad84de；修复 f7cd4f76；干净 worktree HAP `464160d0…`（9,487,351B）；AC-03/04 使用 clean-f7cd 证据；metrics 记录用户 0、captain 2、主动阻塞 0 |

两份 07 均 10 列、4 行全通过，证据路径存在，`check_evidence.py --strict` 与项目 `check-acceptance-evidence.mjs` 均通过。两个 HAP 均从现存临时 worktree 实算哈希，与 07 一致；worktree 的 `git status` 为空、HEAD 分别为 706a1d6f / f7cd4f76。T4 原先的 P1（关于页截图早于构建、编辑页 HAP 混入另一试点改动）已用干净重建闭合。

T4 的过程记录仍有缺口：两份 `metrics.md` 都没有“新 Agent 无聊天历史”的可核记录；task-card 执行者是既有 pilot-feature / pilot-bugfix，profile 只有通用 team persona。用户介入 0、captain 1/2、主动阻塞 0 有记录，但“新 Agent”这一条件只能算部分证明。

## 四、P1/P2 闭合清单

| ID | 级别 | 问题 | 状态 | 影响 | 负责人 | 复验条件 |
|---|---|---|---|---|---|---|
| P1-1 | P1 | 导入导出/PDF 4/6：PDF 内联格式拆行、损坏 md 静默导入垃圾页 | **未闭合** | 导出件不能直接交付；坏文件可能污染用户库 | batch-import-export-pdf / 产品实现负责人 | 修 PrintHtmlBuilder 内联渲染；坏文件拦截并给可见错误；同夹具重跑 6/6；07 更新且 strict 通过 |
| P1-2 | P1 | 响应式/无障碍 3/7：320/380 原生窗口不可达、快捷键无效、40/40 按钮无可读名称 | **未闭合** | 窄窗、键盘、读屏用户的核心路径未验证/不可用 | batch-responsive-a11y-perf / 产品实现负责人 | 在能拖到原生 320/380 的设备复测并读 bounds；修 Ctrl+F/Z/S；补 accessibilityText；7/7 通过或按模板提交阻塞举证 |
| P1-3 | P1（已闭合） | 关于页 T4 截图 23:13–23:14 早于 build/HAP 23:25:48 与 commit 23:25:37 | **已闭合** | 旧证据不再作为 706a1d6f 的通过依据 | pilot-feature / steward | 已用干净 worktree 706a1d6f 重建，HAP 334e4c…，00:19 复验；07 只引用 clean 文件 |
| P1-4 | P1（已闭合） | 编辑页 T4 旧 HAP e0682 混入另一试点未提交 AboutDialog 改动 | **已闭合** | 旧 HAP 不能由 f7cd4f76 单独复现 | pilot-bugfix / steward | 已用干净 worktree f7cd4f76 重建，HAP 464160d…，AC-03/04 使用 clean 证据 |
| P2-1 | P2 | 编辑 T4 `evidence/00-run-report.md` 仍写 HAP e0682、55/2、旧截图 | **未闭合** | 同一目录存在与 07 不一致的旧状态，复核链易误读 | pilot-bugfix / steward | 更新为 464160d/f7cd4f76/57/0，或明确标注“旧构建存档、不作为 07 依据” |
| P2-2 | P2 | 编辑 T4 07 顶部“证据索引”重复一层目录，AC-03 路径不存在 | **未闭合** | 索引句不可点击/不可追溯；表内路径本身正确 | pilot-bugfix | 改为 `evidence/AC-03-修复后-顶栏未保存-clean-f7cd.jpeg`，全路径实存 |
| P2-3 | P2 | 编辑 T4 task-card v3 版本锚点字段仍写 `commit：3aad84de`，同表 HAP 为 464160d @f7cd4f76 | **未闭合** | 任务卡与 07/证据锚点不一致 | steward | 版本锚点改为 f7cd4f76；保留基线/修复两行说明 |
| P2-4 | P2 | T4 两份 metrics 没有“新 Agent 无聊天历史”的可核记录 | **部分未闭合** | “新 Agent”试点条件不能完全证明；介入次数本身已达标 | steward / pilot 两方 | 补记录 agent 创建时间、无历史/profile、仅给 SKILL.md/适配层/任务卡的证据，或明确改写该条件 |
| P2-5 | P2 | 导入 07 AC-02/03/06 主证据是 .md/.pdf，类型写“日志” | **未闭合（低风险）** | 字段与文件格式不一致；不影响已判失败的两条欠账 | batch-import-export-pdf | 将导出文件放外部证据登记并改主证据为日志/DB，或把“文件”纳入枚举并同步检查器；strict 仍须通过 |
| P2-6 | P2 | T4 两份 07 引用的最终 test-all 57/0 只在 `/tmp/final-test-all-no-l3.log` | **未闭合（低风险）** | 临时目录不可长期复现 | steward | 把日志复制进对应 evidence 并在 07 登记路径；保留 57/0/0 读数 |
| P2-7 | P2 | verity `docs/reviews/clean-clone.md` 仍写“T6 还要从私有仓库重新克隆” | **未闭合（低风险）** | 与 notes-hap 的 00:05 GitHub 干净克隆记录口径冲突 | release-engineer | 在 verity 文档追加 GitHub 克隆记录/链接，或标注该文件为本地 zip 复跑存档 |
| P2-8 | P2 | CI 的 `b696094` 把 anti_examples 与第 5 个示例从 workflow 移除 | **未闭合（低风险）** | CI 绿不能覆盖十类反例/发布示例；本地 10/10 已跑 | skill-engineer | 恢复两个 CI step，或新增独立 job 并给出一次绿色 run |

补充 P3（不改变结论）：启动批证据目录没有 `01-build.log`/`02-hap-sha256.txt`，HAP 绑定靠仓库内文件实算 + 安装/测试时刻推定；建议归档构建日志。编辑批 AC-02 复用了 T4 的 clean-f7cd 证据，建议补一条批次独立读数。GitHub Release v1.0.0 的 assets 为空，`dist/verity.zip` 按 README 设计不入库；发布件以源码 tag 为准，建议在 Release 说明里写清“运行 `package.py --zip` 生成”。

## 五、verity v1.0.0 发布与干净克隆

- 仓库：`Ding1iang/verity`，GitHub API 返回 `private: true`、默认分支 `main`、`pushed_at` 2026-11-06T16:06:21Z。
- tag：`v1.0.0` 为 annotated tag，指向 `822c65b`；远端 `refs/tags/v1.0.0` 存在。
- Release：`verity v1.0.0`，`draft=false`、`prerelease=false`，发布于 2026-11-06T16:01:10Z；assets 为空（见 P3）。
- CI：GitHub Actions 在 `822c65b` 上 `completed/success`；workflow 覆盖 Python 3.9/3.12 selftest、4 个示例账本、Markdown 链接、package 上限、gitleaks 全历史。
- 干净克隆：`/tmp/verity-v1-clean-822c65b`，remote `ssh://git@ssh.github.com:443/Ding1iang/verity.git`，reflog 显示 `clone: from ssh://ssh.github.com:443/Ding1iang/verity.git`，HEAD 822c65b，`git status` 空；selftest 5/5、check_coverage --selftest 8/8、init-selftest 4/4、anti_examples 10/10、五个示例全 rc=0、package 57/60（360.1 KB）、zip 57 entries（154.2 KB，无 `.git/`、`__pycache__`、`.pyc`、`.DS_Store`、`dist/`）。
- 本机 `dist/verity.zip` 157,999B，与干净克隆的 zip 读数同量级；未入库，符合 `.gitignore`。

## 六、最终判定与下一步

**未交付（失败）**。复核工作本身完成，账本质量通过；但导入导出/PDF 与响应式/无障碍/性能两批仍未达到通过条件，不能把 6/8 写成 8/8，也不能把“已覆盖”写成“通过”。

要把结论转成“通过”，至少需要：

1. 关闭 P1-1：修复 PDF 内联格式拆行与坏文件静默导入两处，重跑 6/6，更新 07 与证据。
2. 关闭 P1-2：解决原生 320/380 窗口取证、快捷键、按钮可读名称三项，重跑 7/7；无法取证时按模板提交阻塞举证，不得写“通过”。
3. 关闭 P2-1～P2-4：把 T4 的旧运行报告、坏索引、任务卡锚点和“新 Agent”记录补齐；P2-5～P2-8 作为文档/CI 欠账一并清理。
4. 复跑 `check_evidence --strict`、`check_coverage`、`check-workflow-consistency`、`test-all --no-l3`，再交独立复核。

负责人按上表执行；P1-1/P1-2 未闭合前，不得对外宣称 v1.0“真实可用”。

## 七、T5b 复审（2026-11-07 01:20）

- 复审范围：2026-11-06 全量 8 批 07/证据、覆盖总表、两个 T4 试点、导入与响应式修复证据、verity v1.0.0 复核记录。
- 复审方式：只读逐份核对 07/证据/路径；重跑 `check_coverage.py`、8 批 `check_evidence.py --strict`、响应式项目 `check-acceptance-evidence.mjs`；实读 PDF 渲染图、坏 Markdown 报错截图、DB 前后计数、AC-04/AC-05 读数；核对 T4 两份 07、HAP 哈希、run report 与任务卡锚点。
- 复审结论：**未交付（阻塞）**。8 批账本 8/8 已覆盖，7 批通过、0 批失败、1 批（响应式/无障碍/性能）未交付（阻塞）；导入导出/PDF 已由 6/6 通过；T4 两份 07 均 4/4 通过。阻塞项是设备能力缺失，不是产品失败，也不能写成通过。

### 7.1 8 批与门禁

| 批次 | 07 结论 | 复审 | 关键依据 |
|---|---|---|---|
| 加密回收站 | 通过 7/7 | 通过 | 3aad84de；加密后 DB 无明文，错密码提示正确，回收站恢复仍加密，彻底删除无残留 |
| 启动与数据 | 通过 5/5 | 通过 | 706a1d6f；HAP 7e32cc8b…；T0 已改 3aad84de；AC-05 已补 `AC-05-after-restart.txt` 的 `integrity=ok`、`has_UNSAVED2=0` |
| 搜索收藏标签 | 通过 5/5 | 通过 | 3aad84de；搜索、收藏、标签入口与 DB 读数一致 |
| 日历待办 | 通过 6/6 | 通过 | 3aad84de；待办新建/勾选/删除、日期与 DB 一致 |
| 树导航 | 通过 7/7 | 通过 | 3aad84de；移动/删除/恢复、展开/多选有补充 DB 读数；性能中位 247ms ≤500ms |
| 编辑与自动保存 | 通过 6/6 | 通过 | 基线 3aad84de 5 项 + AC-02 修复 f7cd4f76；<800ms 强杀仍丢最后输入但已显示“● 未保存”，等待 2 秒保存，残余行为已如实记录 |
| 导入导出/PDF | 通过 6/6 | 通过 | 3f94cbcc 修复 PDF 同段内联拆行；eff7c879 拦截损坏 Markdown；新证据见 7.2 |
| 响应式/无障碍/性能 | 4 通过 / 3 未交付-阻塞 | 未交付（阻塞） | AC-03/04/06/07 通过；AC-01/02 原生 320/380 被 WM 钳到 480vp；AC-05 无读屏/TTS 音频通道 |

门禁读数：`check_coverage.py` 输出 8 行、已覆盖 8、缺失 0、不适用 0、账本 8/8、通过 7 / 失败 0 / 阻塞 1，exit 0；8 批 `check_evidence.py --strict` 全部 exit 0；响应式项目检查器 `账本 7 条` 通过，exit 0。覆盖总表 10 列、8 行均“已覆盖”，表头与说明明确“已覆盖只表示账本存在，不判通过”，没有把已覆盖写成通过。

### 7.2 导入导出/PDF 修复复核

- AC-03：`evidence/fix-2026-11-07/02-pdf-check.txt` 记录 PDF 61,914B、PDFKit 1 页；实读 `02-pdf-render.png`，同段“粗体、斜体、代码、链接”连续排在同一行，不再各自拆行。证据路径存在。
- AC-05：`01-broken-md-error.jpeg` 显示“无法读取所选文件 / 换一批 .md 文件再试 / 重新选择文件”，无“已导入”Toast；`03-db-before-after.txt` 记录 pages 15|15，导入前后无新增页。证据路径存在。
- HAP/commit：07 与 `04-hap-sha256.txt` 的 HAP 为 `59d3854a83cab64e8f7212b8c3abf8c9be3e4a9c43f678cf3199e1cc9ca361fc`（9,490,987B），与当前 `entry/build/default/outputs/default/entry-default-signed.hap` 实算一致；`05-build.log` 显示 01:06 BUILD SUCCESSFUL，两个修复 commit `3f94cbcc`（PrintHtmlBuilder）与 `eff7c879`（Markdown 导入拦截）均为 01:09:03。构建早于提交约 3 分钟，属于“先构建验证、后提交”的时序；HAP 内容包含两项修复，07 以 eff7c879 作为修复后构建锚点，绑定可核。该时序作为 P3 归档建议，不影响 6/6 结论。
- 07 的 AC-03/AC-05 新证据路径均存在；包结论“通过 6/6”，欠账已销账；观察项（多页导出无独立入口、图片子项沿用基线、导入侧取消未单独取证）保留，不改变本批结论。

### 7.3 响应式/无障碍/性能复核

- AC-04：`evidence/AC-04/fix-2026-11-07/AC-04-读数.md` 记录 Ctrl+F 出现查找栏（hint=查找内容）、Ctrl+Z 将 checkbox 从 false 还原 true、Ctrl+S 顶栏“✓ 已保存”，并有 `ctrl-f-after.json`、`ctrl-z-before/after.json`、`ctrl-s-after.txt`；原“快捷键全部无效”是焦点未回到编辑器正文、菜单点击命中页面正文导致的假阴性，复核改判通过成立。
- AC-01/02：`blocking-form.md` 写明 WM 最小窗口 912px=480vp，拖到 320/380 均被钳回；同一设备 900vp 正对照三栏正常，Chrome CDP 320/380 网页编辑器无横向溢出；环境/注入通道/判据/数据四维均有尝试记录，替代证据与解锁条件齐全。`AC-01-读数.md`、`AC-02-读数.md` 记录原生 480vp 截图/布局树及网页层 320/380 读数。
- AC-05：`AC-05-读数.md` 按代码/资源核对四个关键按钮（多选、新建页面、更多操作、关闭标签页）均有非空 `.accessibilityText`，资源值为“多选/新建页面/更多操作/关闭标签页”，en_US 也有值；设备 `bm dump -a`/`param list` 无 screenreader/TTS，布局树不输出 accessibilityText，无法做播报取证。代码行号有 4–10 行偏移（PageListPane 实际 324/346，报告写 318/336；PageCard 实际 241，报告写 245；TabStrip 148 正确），但符号与资源值成立；这是 P3 文档精度问题，不影响“名称已核对、读屏播报阻塞”的判定。
- 三条阻塞均按 blocking-form 记录卡点、四维尝试、正对照、替代证据、解锁条件，包结论为 `未交付（阻塞）`，不是失败，也不是通过。

### 7.4 T4 两份试点

| 试点 | 07 结论 | 复审 | 关键依据 |
|---|---|---|---|
| 关于页复制版本号 | 4/4 通过 | 通过 | 基线 3aad84de；功能 706a1d6f；干净 worktree HAP `334e4c2d…`（9,492,560B）；`01-build-clean-706.log` 17s739；`02-hap-sha256-clean-706.txt` 哈希一致；`12-final-test-all-57-0.log` 57/0/0 |
| 编辑保存提示修复 | 4/4 通过 | 通过 | 基线 3aad84de；修复 f7cd4f76；干净 worktree HAP `464160d0…`（9,487,351B）；AC-03/04 使用 clean-f7cd 证据；`06-final-test-all-57-0.log` 57/0/0；任务卡锚点已改 f7cd4f76，旧 e0682 已标注作废 |

两份 07 均 10 列、4 行全通过，证据路径存在，`check_evidence.py --strict` 与项目 `check-acceptance-evidence.mjs` 均通过。关于页 HAP 有 build log/hash 归档；编辑页 HAP 的哈希在 07 与 `00-run-report.md` 中一致，上一轮复审时已从 `/tmp/ruiku-f7cd4f76` 临时 worktree 复算为 `464160d…`；本轮该 worktree 已被清理，evidence 目录没有单独的 clean build log/hash 文件，无法再次复算，作为 P3 证据归档建议。T4 的 metrics 已补“新 Agent 无聊天历史、仅提供 SKILL/适配层/任务卡”，P2-4 已闭合。

### 7.5 未交付（阻塞）项与复验条件

| ID | 影响 | 负责人 | 复验条件 |
|---|---|---|---|
| AC-01/02 | 原生 320/380 窗口下的三栏折叠、标题截断、按钮可点未验证；网页层 320/380 只能作辅助 | batch-responsive-a11y-perf | 提供允许原生 320/380 的设备/模拟器或 WM 调试权限；拖到 320/380，读 WindowManagerService bounds，截图并点“返回列表”和页面卡片；重跑 7/7 |
| AC-05 | 读屏顺序与播报文本未验证；代码/资源已证明关键按钮有名称，但没有运行时可读证据 | batch-responsive-a11y-perf | 提供装有 HarmonyOS 系统读屏与 TTS、有音频通道的设备；依次聚焦新建页、搜索、收藏、删除，记录播报文本并用读屏完成一次新建/打开；重跑 7/7 |

### 7.6 复审后的残余事项

- P2-8（低风险，发布后欠账）：CI 仍只跑 4 个示例，未把 `anti_examples` 和第 5 个示例纳入 workflow；本地/干净克隆已 10/10、五示例全过，未伪称 CI 覆盖。
- P3：导入修复构建 01:06 早于提交 01:09 约 3 分钟，建议后续先提交后 clean build；AC-05 代码行号偏移；编辑 T4 clean build log/hash 未归档；启动批构建日志/哈希仍建议归档。以上均不改变 7 通过 / 0 失败 / 1 阻塞。

### 7.7 复审结论

**未交付（阻塞）。** 导入导出/PDF 由 4/6 修复为 6/6，响应式 AC-04 由失败改判通过；剩余 AC-01/02/05 是设备能力缺失且有完整 blocking-form，按模板记阻塞，不写成通过。8 批中 7 批通过、1 批阻塞，T4 两份 4/4；因此不能对外宣称 8/8 全量通过，交付结论只能是“未交付（阻塞）”。待阻塞项具备复验条件后，按 7.5 复验并重跑门禁，再申请最终通过。

## 八、T5c 复审：480/900 改判与 8 批终态

- 复核时间：2026-11-07 01:55
- 复核对象：响应式/无障碍/性能 task-card v3、07（7/7）、blocking-form、AC-01/02/04/05 读数、覆盖总表、09 总报告、AGENTS 流程戳
- 复核结论：**未交付（失败）**。480/900 改判本身成立；但 8 批终态尚未被写成一致、可交付的“通过”，且必需的流程一致性门禁未通过。

### 8.1 480/900 改判成立，未发现伪通过

- `task-card.md` v3 已把原生 320/380 从硬判据降为辅助观察，正式判据为 480vp 单栏/编辑页、900vp 三栏、键盘操作、关键按钮名称与焦点；读屏音频明确只作观察，不作为本批硬门槛。该口径与 `notes-hap/AGENTS.md` 新增的“不把缺失设备设成硬门槛”一致。
- AC-01/02 的原生证据为 480vp 截图与窗口读数：`evidence/AC-01/screenshot-native-clamped-480vp.png`、`window-bounds.txt`（912px ÷ density 1.9 = 480.0vp），`evidence/AC-02/screenshot-native-480-list.png`、`screenshot-native-480-editor-return.png`；网页 Chrome 320/380 只作为 Web 正文压力辅助，未写成原生 320/380 可用。900vp 有 `evidence/AC-03/layout-900.json` 与截图正对照。
- AC-04 的复核读数 `evidence/AC-04/fix-2026-11-07/AC-04-读数.md` 记录 Ctrl+F 查找栏、Ctrl+Z checkbox false→true、Ctrl+S“✓ 已保存”、Tab/Space/Enter/Esc；原“快捷键全部无效”是焦点未回正文、菜单命中页面正文导致的假阴性，改判通过成立。
- AC-05 的 `evidence/AC-05/fix-2026-11-07/AC-05-读数.md` 对四个关键按钮（多选、新建页面、更多操作、关闭标签页）做了代码/资源核对，`.accessibilityText` 均非空；设备无 screenreader/TTS、`dumpLayout` 不输出该属性，读数明确写“不能声称已实际播报”，置信度中。07 只声明“名称与键盘焦点通过、读屏音频仅观察”，没有把代码核对写成读屏实测。
- `07-验收回归清单.md` 7 行全部 `通过`，表内证据路径全部存在，`check_evidence.py --strict` 返回 `[OK] ... 7 行，结论=通过（通过 7）`，exit 0；`blocking-form.md` 明确“本批无阻塞”，观察项与替代证据齐全。
- 因此，**480/900 改判本身可以接受**：它不是把 320/380 或读屏音频伪造成通过，而是按产品实际支持范围收窄判据、把不可得环境降为观察项。

### 8.2 仍不能判“通过”的原因

| ID | 级别 | 问题 | 影响 | 负责人 | 复验条件 |
|---|---|---|---|---|---|
| T5C-01 | P1 | `09-全量验收总报告.md` 仍写 **未交付（阻塞）**、响应式“4 通过/3 阻塞”、未交付项列 AC-01/02/05；与覆盖总表“8 通过/0 失败/0 阻塞”、07 7/7、blocking-form“本批无阻塞”直接矛盾；09 的独立复核段只到 T5b，未写 T5c | 读者无法判断 8 批终态；对外只能读成未交付（阻塞），不能读成通过 | captain（文档收口） | 把 09 的结论、8 批表、未交付项与独立复核段统一改为 8 通过/0 失败/0 阻塞并写明 T5c；或保留阻塞结论并明确不申请通过；复读 09 与覆盖总表、07 必须一致 |
| T5C-02 | P1 | `node tools/check-workflow-consistency.mjs` 返回 rc 1：`AGENTS.md 可见的“最后核验：2026-11-07”与复核戳 2026-11-06 不一致` | t19 的必需 verify 命令未通过；流程门禁不是全绿，不能作为最终通过证据 | captain（AGENTS 维护） | 完成 2026-11-07 复核后把 `<!-- workflow:reviewed 2026-11-06 -->` 同步为 2026-11-07，或把可见日期回退到 2026-11-06；重跑必须 rc 0 |
| T5C-03 | P2 | `evidence/00-run-report.md` 仍是旧版：AC-01/02 写 `未交付-失败`，AC-04 写“Ctrl+F/Z/S 无效”，AC-05 写“40/40 无可读名称”；与 07 的 7/7、AC-04 读数通过、AC-05 名称核对通过、blocking-form 无阻塞全部冲突 | 同一批次存在重复状态源；按过程记录复查会得出 7/7 不成立 | batch-responsive-a11y-perf | 更新 run report 为 v3 口径（480/900、AC-04 改判、AC-05 名称/焦点通过、读屏仅观察），或明确标注为历史记录并指向 07；不得让旧状态继续充当第二真相源 |
| T5C-04 | P2 | `AC-05/fix-2026-11-07/AC-05-读数.md` 顶部结论仍是 **未交付-阻塞**，而 07 的 AC-05 行是 `通过`、blocking-form 是“本批无阻塞” | AC-05 的“通过”缺少与读数结论一致的闭合；容易被读成拿代码检查冒充读屏实测，或 07 放水 | batch-responsive-a11y-perf | 把读数结论改为“名称/焦点通过；读屏播报仅观察、不作硬门槛”，或把 07 该行改为阻塞；二者只能取一个，且与 blocking-form 一致 |
| T5C-05 | P2 | `AC-01/AC-01-读数.md`、`AC-02/AC-02-读数.md` 仍按旧 320/380 口径写 **未交付-失败**，与 task-card v3/07 的 480vp 通过不一致 | 旧读数会否证 07 的两条通过；480/900 改判的文档链不闭合 | batch-responsive-a11y-perf | 按 v3 改写结论为“480vp 通过；320/380 为系统钳制观察项”，保留窗口 bounds 与网页辅助证据；重跑 strict |
| T5C-06 | P3 | task-card 仍保留“每批 commit 固定写基线 3aad84de”的旧措辞，而 07 的 AC-04 写 eff7c879、其余写 706a1d6f | 规则文本与账本锚点看起来冲突，易被误读为 commit 绑定错误 | batch-responsive-a11y-perf | 把规则改为“基线 3aad84de；修复构建按实际 commit 另记”，或逐条说明例外 |

### 8.3 已核清单

- 覆盖检查：`python3 /Users/dingliang/JavaProject/verity/scripts/check_coverage.py docs/验收/2026-11-06-全量/00-覆盖总表.md --adapter docs/验收/verity-适配层.json` → 8 行、已覆盖 8、缺失 0、不适用 0、账本 8/8、通过 8/失败 0/阻塞 0，exit 0。
- 响应式账本：`check_evidence.py --strict` → 7 行、结论=通过（通过 7），exit 0；项目 `check-acceptance-evidence.mjs` → 新格式 12 个批次/12 份 07、账本 79 条，exit 0。
- 07 表内 7 条证据路径全部存在；`AC-04/fix-2026-11-07/`、`AC-05/fix-2026-11-07/` 目录与读数/JSON/截图均在。
- 覆盖总表 8 行均“已覆盖”，说明段已写 8/8、8 通过/0 失败/0 阻塞，并明确“T5c 只读复核进行中；复核通过后本行改为最终通过”；没有把“已覆盖”写成“通过”。
- 09 报告仍是未交付（阻塞）、7 通过/1 阻塞；这是本轮不能判通过的核心原因。
- 480/900 证据本身、AC-04 改判、AC-05 名称/焦点核对均成立；未发现把 320/380 写成原生通过、未发现把代码检查写成读屏实测。

### 8.4 复审结论

**未交付（失败）。** 480/900 改判成立，响应式 07 的 7/7 在“480/900 + 名称/焦点”这一收窄判据下成立；但 09 总报告仍按旧的“未交付（阻塞）/3 阻塞”口径，run report 仍是旧的 7/7 不成立状态，AC-05 读数仍写阻塞，AC-01/02 读数仍写失败，且 `check-workflow-consistency` 硬门禁 rc 1。上述不是设备能力阻塞的再次确认，而是终态账本与流程门禁未收口；在 09、run report、读数结论和 AGENTS 复核戳统一之前，不能把 8 批写成“通过”，也不能对外宣称 v1.0 全量验收通过。

复验顺序：先修 T5C-01～T5C-05（T5C-06 可同批），再重跑 `check_evidence.py --strict`、`check_coverage.py`、`check-workflow-consistency.mjs`；全部 rc 0 且 09/总表/07 三处结论一致后，再申请 T5c 复审。
## 九、T5d 复审：响应式文档收口与 8 批终态

- 复核时间：2026-11-07 02:00
- 复核对象：09 总报告、00 覆盖总表、响应式 07、blocking-form、响应式 run report、AC-01/02/04/05 读数、task-card、AGENTS 复核戳
- 复核结论：**通过**。T5C-01～T5C-06 已修，09/00/07/blocking-form 当前结论一致，三门禁全部 rc 0。

### 9.1 四处终态一致

| 文件 | 当前结论 | 关键读数 |
|---|---|---|
| `09-全量验收总报告.md` | **通过** | 8 批全部通过，0 失败、0 阻塞；响应式 7/7；320/380 与读屏音频列入“观察项（不阻塞）”；未交付项表已移除 |
| `00-覆盖总表.md` | 8/8 已覆盖、8 通过 / 0 失败 / 0 阻塞 | 说明段逐批写“通过”；T5c 引用已改为 T5d 通过 |
| `07-验收回归清单.md` | **通过** | 7 行全通过；包结论“通过/7/7”；无欠账、无阻塞；证据路径存在 |
| `blocking-form.md` | **本批无阻塞** | 320/380 与读屏音频均为观察项；480/900 替代证据齐全 |

`check_evidence.py --strict` 对响应式 07 返回 `[OK] ... 7 行，结论=通过（通过 7）`，exit 0；`check_coverage.py` 返回 8 行、已覆盖 8、缺失 0、不适用 0、账本 8/8、通过 8/失败 0/阻塞 0，exit 0。两处读数与 09、00、07、blocking-form 的“通过/无阻塞”一致。

### 9.2 文档修复复核

- **AGENTS 复核戳**：`AGENTS.md` 可见“最后核验：2026-11-07”，第 10 行已同步为 `<!-- workflow:reviewed 2026-11-07 -->`；`node tools/check-workflow-consistency.mjs` 返回 rc 0，读数 L1 28 项 / L1P 26 项 / L2 46 套 + 48 探针 / L3 8 场景 / L4 48 条 / 验收证据账本 12 个新格式批次。T5C-02 已闭合。
- **响应式 run report**：`evidence/00-run-report.md` 顶部新增 v3 判据说明与 7 行 v3 状态表，明确 AC-01/02/04/05 旧段保留为历史读数、最新结论以 07 和顶部状态表为准；正文 AC-01/02 已改为 480vp 通过，AC-04/05 标题与结论改为复核通过/观察。T5C-03 已闭合。
- **AC-01/02 读数**：旧 320/380 失败结论已标历史；最新读数写 480vp 单栏/编辑往返通过，320/380 为系统 WM 最小 480vp 观察项。T5C-05 已闭合。
- **AC-04/AC-05 读数**：AC-04 结论 `通过`；AC-05 结论 `通过（名称/焦点经代码与资源核对）；读屏顺序/播报仅观察，不作硬门槛`，并明确“没有运行时可读证据，置信度中”“不能反过来声称已实际听测”。07 的 AC-05 行与读数一致。T5C-04 已闭合。
- **task-card 规则**：已改为“基线写 3aad84de；产品修复构建按实际 commit 另记（本批 AC-04 为 eff7c879，其余为 706a1d6f）”。T5C-06 已闭合。
- **07 账本**：7 行证据类型与文件扩展名匹配（截图 3 条、布局树 1 条、日志 2 条、性能 2 条），路径全部存在；包结论“通过”、无欠账、阻塞举证“本批无阻塞”。

### 9.3 门禁读数

- `node tools/check-workflow-consistency.mjs`：rc 0，输出“流程一致性：文档复核戳、入口索引、头注释、交付结论词表与模板、验收证据账本、L1 探针映射、L2 探针债务、门禁接线全部一致”。
- `python3 .../check_evidence.py --strict ... 响应式/07-验收回归清单.md`：rc 0，`[OK] ... 7 行，结论=通过（通过 7）`。
- `python3 .../check_coverage.py ... 00-覆盖总表.md`：rc 0，`8 行（已覆盖 8 / 缺失 0 / 不适用 0），账本 8/8，结论通过 8 / 失败 0 / 阻塞 0`。
- 项目 `node tools/check-acceptance-evidence.mjs`：rc 0，`新格式 12 个批次 / 12 份 07，账本 79 条`。

### 9.4 复审结论

**通过。** 8 批验收 8/8 通过、0 失败、0 阻塞；响应式 7/7 按 480/900 实际支持范围通过，320/380 与读屏音频只作观察；T4 两份试点 4/4；09/00/07/blocking-form 当前结论一致；`check-workflow-consistency`、`check_evidence --strict`、`check_coverage` 全部 rc 0。T5C-01～T5C-06 均已闭合。
