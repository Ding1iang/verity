# verity v1.3.5 自验收

> 历史存档：本目录记录 v1.3.5 时点的自验收，绑定旧提交，不代表当前版本。当前版本的示例复验见 `examples/04-project-v1` 和 `examples/05-release`。

这份记录用 verity 自己的 v1 schema 2 账本验收 v1.3.5 的 R3 不变量判据规则，证明“规则、模板、检查器、门禁”不是只写在说明里。

## 文件

- `task-card.md`：全流程任务卡，含车道与风险、立卡前盘问、spec-lite、范围锁和 AC-01–10。
- `journey-01.md`：从 init 到 gate 的 3 步用户旅程，结论通过。
- `07-验收回归清单.md`：十三列账本、证据身份、完成审计、独立复核和复盘。
- `evidence/04-verification.log`：本机真实命令日志，包含任务书第 3 节 10 条验证命令、58 个反例、check_reviewer 正负例、gate 正负对照、doctor 和打包读数。
- `manifest.json`：证据包清单，记录文件、SHA-256、字节数、是否被 git 跟踪和来源命令。
- `blocking-form.md`：本批无阻塞，保留结构供复核。

## 复跑

```bash
python3 scripts/check_evidence.py docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md
python3 scripts/verity.py manifest --root . \
  --ledger docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md --check
```

两条命令都应 exit 0。检查器通过只表示账本格式、证据路径和计数自洽；证据内容是否充分仍由独立复核人判断。

## 两层汇报快照

`python3 scripts/verity.py report --ledger docs/reviews/2026-11-08-self-acceptance/07-验收回归清单.md --kind two-layer` 的前三行固定为：

```text
这批可以交付，交付结论是“通过”。
共 10 条验收项，10 条是关键项。
下一步：按账本收口并归档证据。
```

空行之后才是账本路径、旅程结论、状态计数和证据路径；第一层不出现 ID、字段名、文件路径或术语。

## 边界

- 证据是 2026-11-14 在本机工作区生成，构建号 `verity-1.3.5`。
- 账本 commit 列绑定实现提交 596e269；自验收证据随后单独提交，最终提交号由任务汇报记录。
