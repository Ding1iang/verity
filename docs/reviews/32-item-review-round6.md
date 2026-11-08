# 第六轮针对性复核报告（t14）

- 复核对象：t13 修复后的最终提交 `c079a91369094718e2ab46e7cf28b7e28c247252`（HEAD）
- 最终实现提交：`025ed84436b18bcfff9823217874f083c992f58a`（`ci: 校验 README pre-push 命令漂移`；此后只有记录性改动）
- 复核人：reviewer（独立复核，不参与实现）
- 工作目录：`/Users/dingliang/JavaProject/verity`
- 干净克隆：`/tmp/verity-r6.clone`（detached `c079a91`，工作区干净）
- 版本：`VERSION` = 1.3.0
- 结论：`pass`（R5-01、R5-02、R5-03 均已验证修复；无 blocker/high。另有一条低优先级矩阵旁证需清理，见 R6-01，不阻断放行）

## 结论摘要

R5-01 已实质修复：自验收 07 的“被测版本”和全部 SA/复核行均为 `025ed84`，证据日志头部也为 `025ed84`；`025ed84` 到最终 HEAD `c079a91` 只改文档、证据、清单和 manifest，没有改 scripts/templates/references/tests/.github/README/SKILL/VERSION。manifest 7 个文件一致，`ev-runs.log` 的 HEAD、时间、退出码和输出哈希均可重算。

R5-02 已修复：README 的 pre-push 示例已包含 `--adapter tests/fixtures/valid-adapter.json --run --team --release`，逐字执行得到 6/6、exit 0；CI 同时做 README 命令漂移检查和同一组 gate。

R5-03 已修复：证据日志已重排为 118 行，原来的第 127 行不存在；第 3 节第 52 行明确写“以下三条均为完整命令；examples 两条都带 adapter 与 --run”，实际第 55/64/72 行命令与摘要一致，不再有“只写 --release 却声称 6/6”的歧义。

全部 9 条 verify、自验收 gate、examples/04/05 门禁、init、doctor、package 均在干净克隆通过。32 项逐项结论见下表，全部通过。

## 复核方法

1. 在 `c079a91` 的独立克隆中执行 9 条 verify、自验收 `check_evidence`/`gate`/`manifest`、init、doctor、package。
2. 直接执行 `README.md:114-116` 的 pre-push 示例，并复跑 CI 中的 README 漂移检查。
3. 构造两个临时仓库验证 R5-01 的边界：
   - 证据提交后追加 `scripts/check_evidence.py` 实现改动，旧证据必须报 `E_STALE_EVIDENCE`；
   - 证据提交后只追加 `docs/reviews/note.md`，刷新 workspace_hash 后必须通过，不能误报旧证据。
4. 检查 `check_evidence.py` 的 `git_changed_paths`/`stale_implementation_changes` 实现，确认它比较 `git diff --name-only commit..HEAD` 的路径，而不是只查祖先。
5. 核对 32 项矩阵、模板、README/CHANGELOG 与实际输出；只新增本报告，不修改实现文件。

## 关键命令读数

| 命令 | 读数 | 退出码 |
|---|---|---|
| `python3 scripts/selftest.py` | 5/5 通过 | 0 |
| `python3 scripts/anti_examples.py` | 49/49 按预期 | 0 |
| `python3 scripts/check_coverage.py --selftest` | 9/9 通过 | 0 |
| `python3 -m py_compile scripts/*.py` | 无错误 | 0 |
| `python3 scripts/check_evidence.py examples/04-project-v1/07-验收回归清单.md` | 1 行，结论=通过 | 0 |
| `python3 scripts/check_evidence.py examples/05-release/07-验收回归清单.md` | 5 行，结论=通过 | 0 |
| `python3 scripts/package.py --check` | 60/60，597.8 KB / 10.0 MB | 0 |
| `python3 scripts/package.py --check --max-files 60` | 60/60 | 0 |
| `git diff --check` | 无输出 | 0 |
| 自验收 `check_evidence.py` | 6 行，结论=通过 | 0 |
| 自验收 `gate --adapter tests/fixtures/valid-adapter.json --run --team --release` | 6/6 | 0 |
| 自验收 `manifest --check` | 7 个文件一致，workspace_hash=b75e57ba… | 0 |
| `gate --ledger examples/04 --adapter ... --run` | 5/5 | 0 |
| `gate --ledger examples/05 --adapter ... --run` | 5/5 | 0 |
| `gate --selftest` | 9 个 PASS | 0 |
| `bash tests/init-selftest.sh` | 6/6 通过 | 0 |
| `doctor --root . --adapter tests/fixtures/valid-adapter.json` | 10/10 通过 | 0 |
| `package.py --selftest` | 60 应过、70 应失败 | 0 |
| `metrics --dir .` | 3 份真实账本、12 行、A 12、F1–F6 全 0 | 0 |
| `scan --root .` | 88 个文件、命中 0 项 | 0 |

## R5-01：证据绑定最终实现提交

### 直接核对

- `docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md:13`：`被测版本` 为 `commit：025ed84436b18bcfff9823217874f083c992f58a`。
- 同文件 `:47-52` 的 SA-01..SA-06 六行、`:76-81` 的独立复核六行，commit/复跑 HEAD 均为 `025ed84436b18bcfff9823217874f083c992f58a`。
- `evidence/04-verification.log:4`：`代码 HEAD：025ed84436b18bcfff9823217874f083c992f58a（最终实现提交；此后仅允许记录性改动）`。
- `evidence/ev-runs.log`：`time=2026-11-08T17:39:39`、`head=025ed84...`、`ev=EV-01`、`command=python3 scripts/selftest.py`、`exit=0`、`output_sha256=100615a8...`、`summary=结果：5/5 通过`。
- `git diff --name-only 025ed84..c079a91` 只包含：
  `docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md`、`evidence/04-verification.log`、`evidence/ev-runs.log`、`manifest.json`、`examples/04-project-v1/07-验收回归清单.md`、`examples/04-project-v1/evidence/ev-runs.log`、`examples/04-project-v1/manifest.json`、`examples/05-release/07-验收回归清单.md`。
  没有 scripts、templates、references、tests、.github、README、SKILL 或 VERSION。
- 自验收 manifest `--check`：7 个文件一致，workspace_hash=`b75e57ba2b1600e7e69f211ff460b0648f4c06bafa857bc66c647718590b0747`。
- `c079a91` 本身只改 07、04-verification.log、manifest 三个文件（docs: 校正 R5 日志体积读数），属于记录性改动。

结论：证据绑定的是最终实现提交 `025ed84`，最终 HEAD `c079a91` 未再改实现；R5-01 满足。

### 负向场景：证据之后改 scripts

在 `/tmp/verity-r6-neg-scripts` 的副本中，从 `c079a91` 追加一行注释到 `scripts/check_evidence.py` 并提交：

```text
[FAIL] .../07-验收回归清单.md:7 [E_STALE_EVIDENCE] 证据绑定 commit 025ed84436b1，但之后到 HEAD 又改过实现/规则文件：scripts/check_evidence.py；必须按最终提交重新取证
[FAIL] .../07-验收回归清单.md:58 [E_WORKSPACE_CHANGED] ...
[FAIL] .../07-验收回归清单.md:59 [E_WORKSPACE_CHANGED] ...
检查失败：3 项错误，0 项警告
exit=1
```

`E_STALE_EVIDENCE` 是第 7 行，不是只查祖先；脚本文件被 `stale_implementation_changes` 的 `scripts/` 前缀命中。

### 正向对照：证据之后只改 docs

在 `/tmp/verity-r6-neg-docs` 的副本中，从 `c079a91` 追加 `docs/reviews/note.md` 并提交：

- 未刷新 workspace_hash 时，检查失败只有 2 项 `E_WORKSPACE_CHANGED`，**没有** `E_STALE_EVIDENCE`；说明 docs 改动不会被误判为旧实现证据。
- 用 `workspace_fingerprint(root, 07 所在目录)` 重算为 `8b9c11926511d2f138c6f29ecbf1da4a3c407ea97feafe634318b14959d78dba`，更新 07 的 workspace_hash 后，`check_evidence.py` 返回 `[OK] ...：6 行，结论=通过（通过 6）`，exit 0。

结论：检查器按 `git diff --name-only commit..HEAD` 的路径集合判断实现文件，不是只查提交祖先；docs-only 场景不会误报旧证据，tracked 文档改动需要按规则刷新 workspace_hash。

## R5-02：README pre-push 命令

`README.md:112-117` 的代码块为：

```sh
#!/bin/sh
python3 scripts/verity.py gate --root . \
  --ledger docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md \
  --adapter tests/fixtures/valid-adapter.json --run --team --release
```

在干净克隆逐字执行该脚本：

```text
[PASS] 证据账本
[PASS] 覆盖总表：未配置（跳过）
[PASS] 证据包清单
[PASS] 范围锁
[PASS] 防绕过
[PASS] 安全脱敏
结果：通过（6/6）
exit=0
```

`.github/workflows/ci.yml:57-69` 有 README 命令漂移检查，`:71-76` 的“本地完成线门禁”执行同一组命令；此外 CI 还跑 examples/04、05 的 adapter+run gate、anti_examples、init-selftest 和 package。R5-02 满足。

## R5-03：日志摘要一致性

- 当前 `04-verification.log` 共 118 行，原任务所指的第 127 行已因 t13 重排不存在。
- 当前第 3 节第 52 行写：“以下三条均为完整命令；examples 两条都带 `--adapter tests/fixtures/valid-adapter.json` 与 `--run`，不是只跑默认门禁。”
- 实际命令：第 55 行 self gate 带 `--adapter ... --run --team --release`；第 64 行 examples/04 带 `--adapter ... --run`；第 72 行 examples/05 带 `--adapter ... --run`。摘要与实际命令一致。
- 日志第 62 行 `结果：通过（6/6）` 对应第 55 行完整命令；日志第 70、75 行对应 examples 的 5/5。R5-03 满足。

## 32 项逐项结论

| # | 项目 | 结论 | 依据 |
|---|---|---|---|
| 1 | 快慢车道与风险分级 | 通过 | 硬触发字段读取与 E_TASK_LANE 负向夹具 |
| 2 | 立卡前 grill | 通过 | 5–10 条检查；examples/05 五行；v2-grill-three 报 E_GRILL |
| 3 | 一页规格与决策记录 | 通过 | spec-lite 六字段；缺字段负例报 E_SPEC_LITE |
| 4 | 判据可判性 lint | 通过 | “功能可用”负例报 E_CRITERION；短判据拦截 |
| 5 | AC、旅程、账本三向映射 | 通过 | examples 01–05 通过；v2-ac-unmapped 报 E_COVERS |
| 6 | 范围锁与工作区干净 | 通过 | 未跟踪/已跟踪越界均被 gate 拦截；scope_exception 正例放行 |
| 7 | 证据命令执行 | 通过 | examples/04 `--run` 5/5；EV-01 记录 exit/time/head/哈希；三条命令夹具 |
| 8 | 产物与环境身份 | 通过 | SHA-256、字节数、构建号、workspace_hash、截图像素均实算 |
| 9 | 旧证据失效 | 通过 | scripts 改动报 E_STALE_EVIDENCE；docs-only 不误报；v2-stale-evidence-scripts 通过 |
| 10 | 独立复核强制 | 通过 | EV-01 绑定 ev-runs；sh/伪哈希/旧 HEAD/旧时间均报 E_REVIEW_COMMAND |
| 11 | 完成线闸门 | 通过 | 自验收 6/6；examples/04、05 各 5/5；README/CI 命令一致 |
| 12 | 防绕过 | 通过 | gate --selftest 覆盖删断言、skip、越界、伪造清单 |
| 13 | 完成审计结构化 | 通过 | examples/04、05 每条 AC 有场景/构建/读数/证据 |
| 14 | 旅程卡强制与负路径 | 通过 | 3–7 步、每卡≥3 不变量、跨区域≥3 卡、高风险异常分支有检查 |
| 15 | 阻塞举证单结构化 | 通过 | examples/03 通过；v2-empty-blocking-form 报 E_BLOCKING_FORM |
| 16 | 发布风险与 PR 摘要 | 通过 | report --kind pr 输出结论/证据/风险回滚 |
| 17 | 复盘与 F 类统计 | 通过 | metrics 输出 F1–F6、复核发现、返工、周期中位数 |
| 18 | 红队夹具 | 通过 | anti_examples 49/49 按预期 |
| 19 | 技能写作与计数一致 | 通过 | 版本 1.3.0、60 文件、49 反例、六模板、五示例计数一致 |
| 20 | 术语表与判级校准 | 通过 | A/B+/B/C 可解析；非法等级报错 |
| 21 | 版本迁移与 schema | 通过 | 八列 legacy 拒绝；十列迁移提示；schema 2 校验 |
| 22 | 适配层预检 | 通过 | 无 adapter 6/6；合法 adapter 10/10 |
| 23 | 多代理任务图 | 通过 | “协作模式”和多代理证据归属校验；examples/05 单代理说明 |
| 24 | 度量 | 通过 | 结构化返工字段；metrics 3 账本/12 行 |
| 25 | 安全与脱敏扫描 | 通过 | 默认 WARN；--release 0 命中；scan 88 文件 0 项 |
| 26 | 专项证据结构化 | 通过 | 截图、性能、DB before/after 结构校验 |
| 27 | 交接摘要 | 通过 | report --kind handoff 含证据路径、状态、下一步 |
| 28 | 修缺陷的紧反馈回路 | 通过 | examples/02 复跑通过；anti_examples 49/49；gate --selftest 9/9；矩阵旁证有低优先级偏差（R6-01） |
| 29 | 自验收 | 通过 | 07/证据日志绑定 025ed84；manifest 7 文件；gate 6/6；干净克隆复跑 |
| 30 | 取证通道正对照预检 | 通过 | 通道正对照 exit 0、负对照非 0；doctor 10/10 |
| 31 | 两层汇报 | 通过 | 第一层三行无 ID/路径/术语；第二层给证据 |
| 32 | 证据包自包含 | 通过 | 自验收 7 文件、examples/04 6 文件（含 ev-runs.log），manifest 通过 |

统计：通过 32 项。

## 发现项

### R6-01（low）矩阵第 28 行的旁证表述与当前输出不一致

- 文件：`docs/optimization-matrix.md:35`
- 问题：该行写“自验收日志复跑 `check_evidence.py examples/02-bug-fix/07-验收回归清单.md`；失败样本 `examples/04/bad-fake-screenshot` 只报一个目标错误”。实测：
  - 自验收日志中没有 `examples/02-bug-fix` 的复跑记录（grep 无结果）；
  - 直接运行 `python3 scripts/check_evidence.py examples/04-project-v1/bad-fake-screenshot/07-验收回归清单.md` 报 8 项错误：`E_STALE_EVIDENCE`、`E_SCREENSHOT`、2 项 `E_ARTIFACT_HASH`、`E_WORKSPACE_CHANGED`、2 项 `E_REVIEW_COMMAND`、`E_REVIEW_AC`，不是只报一个目标错误。
- 影响：不影响第 28 项的功能（紧反馈回路、gate --selftest、anti_examples 均通过），但矩阵旁证会夸大坏样本的隔离性，降低“坏样本只违反目标规则”的可信度。
- 修复要求：把矩阵第 28 行的例子改为 `anti_examples.py` 的 `fake-screenshot`/`v2-review-*` 夹具，或刷新 `bad-fake-screenshot` 的 commit/证据身份使直接检查只保留 `E_SCREENSHOT`；同时删除日志中没有发生的 `examples/02` 复跑表述。该项为 low，不阻断本轮 pass。

## 已确认修复的 R5-01～R5-03

- R5-01：07 被测版本/SA 行/复核 HEAD 和证据日志头部统一为 `025ed84`；manifest 7 文件重生成；`025ed84..c079a91` 无实现文件变更；负向 scripts 改动报 E_STALE_EVIDENCE，docs-only 不误报。
- R5-02：README pre-push 示例逐字执行 6/6、exit 0；CI 有漂移检查和同命令 gate。
- R5-03：日志第 52 行摘要明确三条完整命令，实际命令均带 adapter/--run；原第 127 行因重排不存在，无残留误导。

## 剩余风险

- 证据绑定以 `025ed84` 为实现锚点、`c079a91` 为记录性 HEAD；若未来再改 scripts/templates/references/tests/.github/README/SKILL/VERSION，`E_STALE_EVIDENCE` 会拦截，必须重新取证。
- `ev-runs.log` 是本地 JSONL，检查器可校验哈希/HEAD/时间/退出码，但没有密码学签名；能防误用和普通篡改，不能防有写权限的人重写全部记录。
- 矩阵第 28 行的低优先级旁证偏差建议在下一次文档维护中清理，不影响本轮 32 项功能结论。
- `docs/reviews/32-item-review-round6.md` 是复核产物，不应进入技能包；`package.py` 的 `32-item-review*.md` 排除规则已验证，工作区保留时 package 仍为 60/60。

## 证据路径

- 复核报告：`docs/reviews/32-item-review-round6.md`
- 干净克隆：`/tmp/verity-r6.clone`（`c079a91`）
- 负向 scripts 夹具：`/tmp/verity-r6-neg-scripts`（追加 scripts 改动后 E_STALE_EVIDENCE）
- 正向 docs 夹具：`/tmp/verity-r6-neg-docs`（追加 docs 后只报 E_WORKSPACE_CHANGED；刷新指纹后通过）
- README 命令：`/tmp/readme-prepush.sh`（从 `README.md:112-117` 提取并执行，6/6）
- 自验收证据：`docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md`、`evidence/04-verification.log`、`evidence/ev-runs.log`、`manifest.json`
- 示例：`examples/04-project-v1/`（gate 5/5、manifest 6 文件）、`examples/05-release/`（gate 5/5）

结论：`pass`。R5-01、R5-02、R5-03 均已修复并复跑通过；R6-01 是低优先级矩阵旁证清理项，不构成 blocker/high。
