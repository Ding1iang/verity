# 外部来源清单

> 本文件只列本技能包实际引用的外部资料，不列项目内部文档。每条外部结论在正文里用 `[S#]` 标注，编号以本表为准。
>
> 访问日期统一为 2026-11-06（Asia/Shanghai）。页面日期以页面自己标注的发布/更新时间为准；页面没标日期就写“未标注”，不拿访问日期冒充页面日期。

## 1. 使用规则

1. **先有来源，再写结论。** 正文里出现外部标准、平台行为、版本规范或工具行为时，必须能指回本表的一行；指不回去的，要么删掉，要么改写成本文件约定。
2. **官方与社区分开。** 标准组织发布的规范/建议记“官方标准”；标准组织下属项目的解释性文档记“官方指南”；平台/工具项目维护的文档记“官方文档”；社区维护的约定记“社区规范”。社区规范不能写成“标准要求”。
3. **日期要能复核。** 页面标注了发布日期或更新时间就照抄；没有标注就写“未标注”。访问日期只表示“我在这天看过”，不表示内容在这天发布。
4. **链接失效时按标题和发布者检索。** 不凭记忆补内容，不把二手转述当原文。
5. **标准条款写编号。** 例如 WCAG 2.2 的 1.4.3、2.5.8；只写“无障碍规范”无法复核。
6. **外部资料只支撑判据，不代替项目验收。** 项目自己的阈值、夹具、视口和状态矩阵仍要在任务卡和 07 里写清。

## 2. 清单

| ID | 标题 | 发布者 / 属性 | 链接 | 页面日期 | 访问日期 | 用在哪 | 支撑的结论 |
|---|---|---|---|---|---|---|---|
| S1 | Web Content Accessibility Guidelines (WCAG) 2.2 | W3C / 官方标准（W3C Recommendation） | https://www.w3.org/TR/WCAG22/ | 发布 2024-12-12 | 2026-11-06 | 视觉验收的总基线 | WCAG 2.2 是 W3C 建议标准；具体条款以 S2–S7、S12 的解释页为准 |
| S2 | Understanding Success Criterion 1.4.3: Contrast (Minimum) | W3C WAI / 官方指南 | https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html | 更新 2026-09-06 | 2026-11-06 | 视觉验收：文字对比度 | 普通文字至少 4.5:1；大字号至少 3:1 |
| S3 | Understanding Success Criterion 1.4.11: Non-text Contrast | W3C WAI / 官方指南 | https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html | 更新 2026-09-06 | 2026-11-06 | 视觉验收：控件、图标、焦点环 | 非文字 UI 组件和图形对象至少 3:1 |
| S4 | Understanding Success Criterion 2.4.7: Focus Visible | W3C WAI / 官方指南 | https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html | 更新 2026-09-06 | 2026-11-06 | 视觉验收：键盘焦点 | 键盘可操作的元素必须有可见焦点指示 |
| S5 | Understanding Success Criterion 2.5.8: Target Size (Minimum) | W3C WAI / 官方指南 | https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html | 更新 2026-05-11 | 2026-11-06 | 视觉验收：点击目标 | 目标尺寸最低 24×24 CSS px，条款有例外；44×44 是本技能包触控基线，不是 WCAG 强制值 |
| S6 | Understanding Success Criterion 1.4.4: Resize Text | W3C WAI / 官方指南 | https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html | 更新 2026-09-06 | 2026-11-06 | 视觉验收：字体放大 | 文字可放大到 200% 而不丢失内容或功能 |
| S7 | Understanding Success Criterion 1.4.10: Reflow | W3C WAI / 官方指南 | https://www.w3.org/WAI/WCAG22/Understanding/reflow.html | 更新 2026-09-06 | 2026-11-06 | 视觉验收：窄窗口 | 320 CSS px 宽度下内容可回流，不出现二维滚动（条款有例外） |
| S8 | `prefers-reduced-motion` | Mozilla MDN / 官方文档（平台能力，不是标准） | https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion | 修改 2026-06-10 | 2026-11-06 | 视觉验收：减少动效 | 这是 CSS 媒体特性，用于检测用户是否要求减少非必要动效；不是 WCAG 的强制条款 |
| S9 | `:focus-visible` | Mozilla MDN / 官方文档（平台能力，不是标准） | https://developer.mozilla.org/en-US/docs/Web/CSS/:focus-visible | 修改 2026-10-16 | 2026-11-06 | 视觉验收：焦点样式实现 | 这是 CSS 伪类，描述浏览器何时匹配焦点可见；实现手段不等于验收标准 |
| S10 | Semantic Versioning 2.0.0 | semver.org / 社区规范（非标准组织） | https://semver.org/ | 未标注（规范版本 2.0.0） | 2026-11-06 | 发布参考：版本号 | 主版本/次版本/修订版的语义约定；只作为版本号约定使用，不声称是 ISO/IEC 标准 |
| S11 | `git revert` 文档 | Git 项目 / 官方文档 | https://git-scm.com/docs/git-revert | 随 Git 2.54.0，页面未标日期 | 2026-11-06 | 发布参考：回滚点 | `git revert` 通过新建反向提交撤销已有提交；不能用它改写已发布历史 |
| S12 | Understanding Success Criterion 2.4.11: Focus Not Obscured (Minimum) | W3C WAI / 官方指南 | https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html | 更新 2026-06-15 | 2026-11-06 | 视觉验收：焦点遮挡 | 键盘焦点不能被浮层、吸底栏等内容完全遮住 |

## 3. 各文件用到的来源

| 文件 | 用到的来源 | 说明 |
|---|---|---|
| `references/visual.md` | S1–S9、S12 | 视觉判据、对比度、焦点、目标尺寸、字体放大、回流、减少动效、焦点遮挡 |
| `references/release.md` | S10、S11 | 版本号语义、回滚提交方式；该文件以概念引用为主 |
| `references/behavior-perf.md` | 无外部来源 | p50/p95、样本数门槛和判定表是本技能包约定，不冒充外部标准 |
| `references/acceptance-run.md` | 无外部来源 | 操作、观察、批量验收和复测规则是本技能包约定，不冒充外部标准 |
| `references/ui-improvement.md` | 无外部来源 | 设计侧四步和落地侧四步是本技能包约定，来自通用流程迁移，不引用外部规范 |
| `references/evidence.md`、`references/acceptance.md` | 无外部来源 | 证据分级、七状态、三态交付是本技能包约定 |
| `docs/reviews/anti-examples.md` | 无外部来源 | 十类反例是检查器的内部回归清单，不冒充外部标准 |
| `examples/05-release/README.md` | S10、S11 | 版本号语义与回滚提交方式的示例；示例读数为演示数据 |

## 4. 不采用的说法

下面这些说法很常见，但要么把社区做法写成了官方规则，要么把项目约定写成了标准。正文遇到时按“正确写法”改。

| 常见说法 | 为什么不采用 | 正确写法 |
|---|---|---|
| “44×44 是 WCAG 强制要求” | WCAG 2.5.8 的最低值是 24×24；44×44 是本技能包触控基线，不是 WCAG 强制值 | “WCAG 最低 24×24 [S5]；本技能包触控基线 44×44” |
| “p95 必须至少 20 个样本，这是标准规定” | 这是本技能包为了避免小样本误判定的约定，没有外部标准依据 | “本技能包约定：少于 20 个样本不判 p95” |
| “SemVer 是 ISO 标准” | SemVer 是社区维护的版本号规范，不是 ISO/IEC 标准 | “SemVer 是社区规范 [S10]，本文只把它当版本号约定” |
| “MDN 写的就是 W3C 标准” | MDN 是 Mozilla 维护的平台文档，解释浏览器行为，不是标准正文 | “MDN 是平台官方文档 [S8][S9]；标准条款以 W3C 原文为准” |
| “深色主题下对比度可以放宽” | WCAG 的对比度要求不按主题放宽；深色主题同样要满足门槛 | “浅色/深色都按 4.5:1（大字号 3:1）检查 [S2]” |
| “截图看起来没问题就是通过” | 截图只是 B 级证据，不能覆盖未截到的状态和交互 | “截图 + 结构读数或交互路径，按 07 的最低证据判定” |

## 5. 维护

- 新增外部结论时，先在本表加一行，再在正文写 `[S#]`；不允许先写正文再补来源。
- 正文删除某条外部结论后，回来看本表是否还有文件使用；没有使用就删除该行，避免清单膨胀。
- 每季度或发布前复核链接和页面日期；链接失效时按标题、发布者检索，找不到就标“未验证”，不凭记忆补。
- 本表不记录项目内部文档、代码路径或项目专属适配信息；这些内容不属于技能包的外部来源。
