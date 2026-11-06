# 反例预备清单

> 这是给独立复核方（verifier）的预备清单，不是验收结论。十类反例都由 `python3 scripts/anti_examples.py` 在临时目录生成并逐条断言错误码；固定示例目录里的四个反例用于让读者直接看到坏账本长什么样。

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
