# 反例预备清单

> 第 1–5 节是给独立复核方（verifier）的预备清单，不是验收结论；第 6 节是 verifier 在 2026-11-06 的独立复核记录。十类反例都由 `python3 scripts/anti_examples.py` 在临时目录生成并逐条断言错误码；固定示例目录里的四个反例用于让读者直接看到坏账本长什么样。

## 1. 一键复跑

在仓库根目录执行：

```bash
python3 scripts/anti_examples.py
```

预期最后一行：

```text
结果：10/10 反例按预期报错
```

脚本只看“检查器是否报出指定错误码”，不把退出码 0/1 当作唯一判据；每个样本都打印 `[PASS] 样本名: 错误码`。退出码 0 表示十类全部命中，1 表示至少一类没有命中指定错误码。

## 2. 十类预备清单

| # | 反例 | 生成器样本 | 固定示例（可选） | 期望错误码 | 期望消息关键词 |
|---|---|---|---|---|---|
| 1 | 假截图：写“见截图”，没有可读图片文件 | `fake-screenshot` | `examples/04-project-v1/bad-fake-screenshot/07-验收回归清单.md` | `E_SCREENSHOT` | 证据类型是截图，但没有可读的截图文件 |
| 2 | 假路径：证据路径不存在 | `fake-path` | — | `E_EVIDENCE_PATH` | 证据文件不存在 |
| 3 | 旧证据：证据日期早于 commit 日期 | `stale-evidence` | `examples/02-bug-fix/bad-old-evidence/07-验收回归清单.md` | `E_STALE` | 不能复用旧证据 |
| 4 | 空 07：账本没有任何验收项 | `empty-ledger` | — | `E_NO_ROWS` | 账本没有任何验收项 |
| 5 | 无证据通过：状态写通过，证据为空/占位符 | `no-evidence` | — | `E_MISSING_EVIDENCE` | 的证据列为空 |
| 6 | 只跑主路径：证据自述只覆盖主路径，却写通过 | `main-path-only` | `examples/01-new-feature/bad-main-path/07-验收回归清单.md` | `E_SCOPE_GAP` | 只覆盖主路径，不能支撑整个验收项通过 |
| 7 | 门禁全绿但没探针：用门禁结果替代探针结论 | `gate-only` | `examples/05-release/bad-gate-only/07-验收回归清单.md` | `E_PROBE_MISSING` | 门禁不能替代探针结论 |
| 8 | 设备没验写通过：自述设备未验证，状态仍写通过 | `device-unverified` | — | `E_DEVICE_UNVERIFIED` | 自述设备未验证，不能写成通过 |
| 9 | 重复状态源：同一目录两份 07 账本 | `duplicate-source` | — | `E_DUP_SOURCE` | 同一目录存在第二份 07 账本 |
| 10 | 旧结论词：出现“基本可用”等旧结论 | `old-words` | — | `E_OLD_WORD` | 出现旧结论词 |

## 3. 固定示例的复跑命令

```bash
python3 scripts/check_evidence.py examples/01-new-feature/bad-main-path/07-验收回归清单.md
python3 scripts/check_evidence.py examples/02-bug-fix/bad-old-evidence/07-验收回归清单.md
python3 scripts/check_evidence.py examples/04-project-v1/bad-fake-screenshot/07-验收回归清单.md
python3 scripts/check_evidence.py examples/05-release/bad-gate-only/07-验收回归清单.md
```

四条命令都应非 0 退出，并分别出现 `E_SCOPE_GAP`、`E_STALE`、`E_SCREENSHOT`、`E_PROBE_MISSING`；如果只看到非 0 退出码而没有对应错误码，仍然算反例失效。

## 4. verifier 要核对什么

- 每个样本是否只违反目标规则，而不是因为别的原因顺带失败；`anti_examples.py` 的断言只要求目标错误码存在，报告里要说明是否还出现其他错误。
- 检查器报出的行号是否指向对应证据行，消息是否能让人知道该改哪一列。
- 固定示例的坏账本是否真的按 README 的命令能复跑，不依赖本机绝对路径或未提交文件。
- 十类是否覆盖“假截图、假路径、旧证据、空 07、无证据通过、只跑主路径、门禁全绿但没探针、设备没验写通过、重复状态源、旧结论词”全部关键词。

## 5. 边界

- 反例都是可重建的演示数据，不含私有项目、凭据、真实用户数据或设备信息。
- 反例只验证检查器“能拦住已知坏形态”，不证明检查器能证明证据内容真实；真实性仍由独立复核负责。
- 新增反例时先更新本清单和 `scripts/anti_examples.py`，再让 verifier 复跑；不要把只在某台机器上成立的路径写进样本。

## 6. 独立复核记录（verifier，2026-11-06）

复核对象：`git rev-parse HEAD` = `42d4754`；`scripts/check_evidence.py` sha256 `59f31e18e5bf44524dc1b77f7185ef32853d0bcd9bda01f85f13ab64e9b55f5f`；`scripts/anti_examples.py` sha256 `cd1b528fb9ebef80c5d1a7ef26c659383253785ed119597f88f15c74835e4740`。复核期间未修改检查器、程序实现和 ruiku-note 产品代码。

### 6.1 一键复跑（skill-engineer 生成器）

在 verity 仓库根目录执行 `python3 scripts/anti_examples.py`：exit code 0，输出十行 `[PASS] <样本>: <错误码>`，末行 `结果：10/10 反例按预期报错`。该脚本的断言是“退出码非 0 且输出含目标错误码”，不校验行号；行号与消息关键词由 6.2 的独立复建额外核对。

### 6.2 独立复建十个 fixture

不复用 `anti_examples.py` 的 fixture 构造函数，在系统临时目录（`TMP=$(mktemp -d)`）另建十份同形态 v1 账本；每份只改目标列，其他列填合法值。逐份执行：

```bash
python3 scripts/check_evidence.py "$TMP/<样本>/07-验收回归清单.md" --format v1 --root "$TMP" --json
```

判定“拦住”必须同时满足四条：① exit code 非 0；② JSON `errors` 含目标错误码；③ 目标错误的消息含预期关键词；④ `line` 指向对应证据行（空账本指向“单项验收（证据账本）”标题行；重复状态源是文件级错误，`line` 为空但消息点名第二份文件）。只有退出码非 0、错误码对不上的，按“漏过”记。

| # | 反例 | fixture（临时目录内） | 命令 | exit | 关键错误（code / message / line） | 其他错误 | 判定 |
|---|---|---|---|---|---|---|---|
| 1 | 假截图 | `fake-screenshot/`：证据类型“截图”，证据写“见截图”，目录内无可读图片 | `check_evidence.py $TMP/fake-screenshot/07-验收回归清单.md --format v1 --root $TMP --json` | 1 | `E_SCREENSHOT` / `CASE-01 的证据类型是截图，但没有可读的截图文件` / L29 | 无 | 拦住 |
| 2 | 假路径 | `fake-path/`：证据写 `evidence/missing.txt`，文件不存在 | `check_evidence.py $TMP/fake-path/07-验收回归清单.md --format v1 --root $TMP --json` | 1 | `E_EVIDENCE_PATH` / `证据文件不存在：evidence/missing.txt（已查临时根与 fixture 目录）` / L29 | 无 | 拦住 |
| 3 | 旧证据 | `stale-evidence/`：git 提交日期 2026-11-06，证据行日期写 2026-10-01 | `check_evidence.py $TMP/stale-evidence/07-验收回归清单.md --format v1 --root $TMP/stale-evidence --json` | 1 | `E_STALE` / `证据日期 2026-10-01 早于 commit 日期 2026-11-06，不能复用旧证据` / L29 | 无 | 拦住 |
| 4 | 空 07 | `empty-ledger/`：五节齐全，证据表只有表头、没有数据行 | `check_evidence.py $TMP/empty-ledger/07-验收回归清单.md --format v1 --root $TMP --json` | 1 | `E_NO_ROWS` / `账本没有任何验收项` / L25（“单项验收（证据账本）”标题行） | 无 | 拦住 |
| 5 | 无证据通过 | `no-evidence/`：状态“通过”，证据列写占位符“—” | `check_evidence.py $TMP/no-evidence/07-验收回归清单.md --format v1 --root $TMP --json` | 1 | `E_MISSING_EVIDENCE` / `CASE-05（通过）的证据列为空` / L29 | 同一空单元格另报 `E_FIELD`“证据为空”（L29，同根因重复提示） | 拦住 |
| 6 | 只跑主路径 | `main-path-only/`：证据自述“只跑了主路径”，状态仍写“通过” | `check_evidence.py $TMP/main-path-only/07-验收回归清单.md --format v1 --root $TMP --json` | 1 | `E_SCOPE_GAP` / `CASE-06 的证据自述只覆盖主路径，不能支撑整个验收项通过` / L29 | 无 | 拦住 |
| 7 | 门禁全绿但没探针 | `gate-only/`：证据写“门禁全绿；没跑探针”，状态“通过” | `check_evidence.py $TMP/gate-only/07-验收回归清单.md --format v1 --root $TMP --json` | 1 | `E_PROBE_MISSING` / `CASE-07 只写了门禁全绿，但自述没跑探针；门禁不能替代探针结论` / L29 | 无 | 拦住 |
| 8 | 设备没验写通过 | `device-unverified/`：证据自述“设备未验，直接写通过” | `check_evidence.py $TMP/device-unverified/07-验收回归清单.md --format v1 --root $TMP --json` | 1 | `E_DEVICE_UNVERIFIED` / `CASE-08 自述设备未验证，不能写成通过` / L29 | 无 | 拦住 |
| 9 | 重复状态源 | `duplicate-source/`：同目录放 `07-验收回归清单.md` 与 `07-副本.md` | `check_evidence.py $TMP/duplicate-source/07-验收回归清单.md --format v1 --root $TMP --json` | 1 | `E_DUP_SOURCE` / `同一目录存在第二份 07 账本：07-副本.md；07 是唯一状态源` / 文件级（line=null） | 无 | 拦住 |
| 10 | 旧结论词 | `old-words/`：证据写 `task-card.md：基本可用`，状态“通过” | `check_evidence.py $TMP/old-words/07-验收回归清单.md --format v1 --root $TMP --json` | 1 | `E_OLD_WORD` / `出现旧结论词“基本可用”，只能写规范状态/结论` / L29 | 无 | 拦住 |

正对照：同结构合法账本（`positive-control/`，证据 `evidence.txt` 真实存在、状态“通过”、结论“通过”）执行同一命令，exit 0、`errors` 为空。十份反例均报错、正对照放行，说明不是“检查器只会失败”的退出码假象。

### 6.3 固定示例复跑

| 固定示例 | 命令 | exit | 关键错误 |
|---|---|---|---|
| `examples/01-new-feature/bad-main-path/07-验收回归清单.md` | `python3 scripts/check_evidence.py <该路径> --json` | 1 | `E_SCOPE_GAP` / L29 |
| `examples/02-bug-fix/bad-old-evidence/07-验收回归清单.md` | `python3 scripts/check_evidence.py <该路径> --json` | 1 | `E_STALE` / L29 |
| `examples/04-project-v1/bad-fake-screenshot/07-验收回归清单.md` | `python3 scripts/check_evidence.py <该路径> --json` | 1 | `E_SCREENSHOT` / L29 |
| `examples/05-release/bad-gate-only/07-验收回归清单.md` | `python3 scripts/check_evidence.py <该路径> --json` | 1 | `E_PROBE_MISSING` / L29 |

### 6.4 判定与边界

- 判定：十类 **10/10 拦住，假通过 0**；正对照 1/1 放行。没有出现“exit 非 0 但目标错误码不符”的样本，也没有漏过。
- 检查器不是只看退出码：每份都核对了错误码、消息关键词和行号；第 5 类的附加 `E_FIELD` 与 `E_MISSING_EVIDENCE` 指向同一空单元格，属同一根因的重复提示，不构成另一条规则被顺带违反。
- 补充自测：`python3 scripts/selftest.py` 5/5、`python3 scripts/check_coverage.py --selftest` 8/8，均 exit 0。十类反例都是证据账本坏形态，判定入口是 `check_evidence.py`；`check_coverage.py` 负责覆盖总表与 07 挂接，不判账本内容。
- fixture 不污染发布包：全部在系统临时目录生成，复核后已删除；本任务只修改 `docs/reviews/anti-examples.md` 一个已跟踪文件，未新增包内文件；`python3 scripts/package.py --check` exit 0（复核时 56/60，复核结束时 57/60，增量来自其他任务的并发新增文件，反例未进入包）。
- 边界：未改检查器、未改 verity 实现、未改 ruiku-note 产品代码；反例只证明已知坏形态会被拦，不证明证据内容真实。
