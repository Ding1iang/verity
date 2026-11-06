# 贡献指南

verity 是一套自用的交付验收技能包。欢迎提交缺陷报告、规则修正和示例改进。

## 开始之前

1. 先开 issue 说明要解决的问题；不要直接提交大改动。
2. 一个提交只做一件事，不把重构、格式化和无关文档混进同一个提交。
3. 改动必须带可复算的证据：命令、退出码或实际读数，不接受“应该”“理论上”。

## 本地检查

在仓库根目录执行：

```bash
python3 scripts/selftest.py
bash tests/init-selftest.sh
python3 scripts/check_coverage.py --selftest
python3 scripts/check_evidence.py examples/01-new-feature/07-验收回归清单.md
python3 scripts/check_evidence.py examples/02-bug-fix/07-验收回归清单.md
python3 scripts/check_evidence.py examples/03-blocking/07-验收回归清单.md
python3 scripts/check_evidence.py examples/04-project-v1/07-验收回归清单.md
python3 scripts/check_evidence.py examples/05-release/07-验收回归清单.md
python3 scripts/anti_examples.py
python3 scripts/package.py --check
```

预期结果：自测 5/5、初始化自测 4/4、覆盖自测 8/8 通过，五个示例账本退出码为 0，反例 10/10 按预期报错，打包检查显示 `文件数：57 / 60`（上限 60 文件、10 MB）。任何一项报错都不要提交。

## 提交信息

格式：`feat/fix/docs/ci/chore: 中文描述`。正文说明改了什么、为什么改、怎么验证。没有验证记录的改动按未完成处理。

## 规则改动的额外要求

- 改 `SKILL.md`、`references/` 或 `templates/` 时，说明对四种模式的影响；v1 默认模板是四状态三包结论（检查器兼容带欠账，项目合同用 `--strict` 关闭），旧八列是七状态三态。
- 改 `scripts/` 时，补一个能让检查器报红的坏样本；只有好样本通过的改动不合并。
- 改证据格式属于破坏性变更，先开 issue 讨论并升级版本号。

## 仓库边界

不提交具体项目的内部资料、设备适配信息、凭据、内部地址和真实用户数据，判断标准见 `docs/design.md` 第 4 节。提 issue 时也不要贴真实密码、令牌、Cookie 或未脱敏截图。

## 许可

贡献内容按 MIT 许可证授权，见 `LICENSE`。
