# 08 独立复核报告（T5）

- 复核对象：2026-11-06 全量 8 批、两个 T4 真实任务试点、verity v1.0.0
- 复核人：reviewer（独立于实现，只读复核）
- 复核日期：2026-11-07
- 复核方式：逐份读 07 与证据；重跑 `check_evidence --strict`、`check_coverage`、`check-workflow-consistency`、`check-coverage-matrix`；复算 HAP SHA-256；核对临时 worktree 的 HEAD/status；从私有仓库重新克隆 v1.0.0 并复跑 selftest/package/anti_examples；核对 GitHub API 的仓库、Release 与 CI 状态。

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
