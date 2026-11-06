# 干净目录复跑记录

> 本文件先记录本机临时目录的复跑，再记录 2026-11-07 从私有 GitHub 仓库的干净克隆复跑。两者是独立证据，不能互相替代。

## 范围与环境

- 被测版本：`VERSION` = `1.0.0`。
- 源工作区：`/Users/dingliang/JavaProject/verity`。
- 复跑日期：2026-11-06。
- 运行环境：macOS，Python 3.13（脚本只用标准库，不联网）。
- 复跑方式：用 `python3 scripts/package.py --zip` 生成 `dist/verity.zip`，解压到 `mktemp -d` 创建的空临时目录，再在该目录的 `verity/` 下执行 README 命令。
- 每次复跑使用 `mktemp -d` 生成的独立空目录，避免沿用源工作区的缓存或未提交文件。

## 复跑步骤

```bash
python3 scripts/package.py --zip
TMP_DIR="$(mktemp -d)"
unzip -q dist/verity.zip -d "$TMP_DIR"
cd "$TMP_DIR/verity"

python3 scripts/selftest.py
python3 scripts/package.py --check
python3 scripts/check_evidence.py examples/01-new-feature/07-验收回归清单.md
python3 scripts/check_evidence.py examples/02-bug-fix/07-验收回归清单.md
python3 scripts/check_evidence.py examples/03-blocking/07-验收回归清单.md
python3 scripts/check_evidence.py examples/04-project-v1/07-验收回归清单.md
python3 scripts/check_evidence.py examples/05-release/07-验收回归清单.md
python3 scripts/anti_examples.py
```

## 实测结果

| 检查 | 结果 |
|---|---|
| 自测 | `结果：5/5 通过` |
| 打包检查 | `文件数：57 / 60`，`检查通过` |
| 01 新功能示例 | `3 行，结论=通过（通过 3）` |
| 02 修缺陷示例 | `4 行，结论=通过（通过 4）` |
| 03 阻塞示例 | `4 行，结论=阻塞（通过 2 / 阻塞 1 / 不适用 1）` |
| 04 验收示例 | `1 行，结论=通过（通过 1）` |
| 05 发布示例 | `5 行，结论=通过（通过 5）` |
| 十类反例 | `结果：10/10 反例按预期报错` |

## zip 内容检查

- 解压后的目录可以直接执行 README 中的命令，不依赖源工作区的绝对路径。
- zip 中不含 `.git/`、`__pycache__/`、`*.pyc`、`dist/`、临时文件或密钥文件。
- 最终 zip 共 57 个条目；压缩包本身不提交仓库，本记录只保留复跑结果和命令。

## 结论与后续

本机临时目录复跑通过，作为 v1.0.0 打包前的最低证据。GitHub 私有仓库的独立干净克隆复跑见下一节；两者共同证明发布件不依赖本机工作区。

## GitHub 私有仓库干净克隆（2026-11-07）

- 克隆命令：`git clone --depth 1 --branch v1.0.0 ssh://git@ssh.github.com:443/Ding1iang/verity.git /tmp/verity-v1-clean-822c65b`
- 克隆结果：HEAD `822c65b`，`git status` 空；remote 为 `ssh://git@ssh.github.com:443/Ding1iang/verity.git`。
- 复跑结果：`selftest.py` 5/5；`check_coverage.py --selftest` 8/8；`tests/init-selftest.sh` 4/4；`anti_examples.py` 10/10；五个示例账本 3/4/2通过+1阻塞+1不适用/1/5；`package.py --check` 57/60、360.1KB；`package.py --zip` 57 entries、154.2KB，无 `.git/`、`__pycache__`、`.pyc`、`.DS_Store`、`dist/`。
- 首次 HTTPS 克隆两次失败（`Error in the HTTP2 framing layer`、`Empty reply from server`），改用 SSH over 443 成功；失败命令与错误保留在此，作为通道限制记录。
- 结论：私有仓库干净克隆可复跑，不依赖本机工作区；该结论与 `notes-hap/docs/测试/2026-11-06-全量/verity-干净克隆记录.md` 一致。
