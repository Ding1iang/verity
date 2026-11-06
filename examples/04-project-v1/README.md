# 项目 v1 十列账本示例

这个示例演示项目自己的十列账本如何被通用检查器识别。

```bash
python3 scripts/check_evidence.py examples/04-project-v1/07-验收回归清单.md \
  --format v1 --root examples/04-project-v1
```

也可以让适配层声明 `paths.ledger_template`，再由 `--adapter` 自动识别格式和项目根。旧八列示例仍按 legacy 格式运行，不需要额外参数。
