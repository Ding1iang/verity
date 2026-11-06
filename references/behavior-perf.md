# 行为与性能参考

> 本文件可独立使用，不要求先读 `SKILL.md`。它回答两件事：行为改动怎样证明真的变了，性能改动怎样证明真的够快。
>
> 行为结论最终写进 `07-验收回归清单.md`；本文件不定义第二套状态。

## 0. 适用边界

用于状态变化、事件、异步、重试、幂等、错误恢复和性能。纯视觉的“看见什么”走视觉验收；行为验收看“做了什么变化”，性能验收看“多快、多稳”。

行为通过不能弥补视觉失败，性能通过也不能弥补功能失败。三件事分开记录，最后在 07 里各占一行。

## 1. 行为 = 状态差异

行为结论必须写成一句话：

```text
给定 <前置状态 + 输入>，执行 <操作>，应得到 <后置状态>；除此之外不应有其他变化。
```

只写“点击后正常”“已经修好”不算行为结论，因为没有可对照的前后状态。

### 1.1 快照要记什么

| 层 | 记什么 | 例子 | 不记会怎样 |
|---|---|---|---|
| 数据 | 记录、队列、文件、计数、版本号 | `pending: ["A","B"]`、`version: 7` | 只看到界面变了，不知道数据是否重复写 |
| 界面 | 可见文字、选中/禁用、焦点、空/错/加载态 | `button.disabled: true` | 界面假装成功，实际没落库 |
| 外部副作用 | 请求次数、写入次数、事件、缓存失效 | `write_count: 1` | 重试造成重复写入却看不出来 |
| 日志与错误 | 错误码、重试次数、最后错误 | `last_error: "timeout"` | 失败被吞掉，用户只看到旧页面 |

快照必须来自同一个版本、同一套夹具、同一个环境。旧版本的前置快照加新版本的后置快照，不是一组可比数据。

### 1.2 快照的规范化

- 键排序；数组保持业务顺序；不要用无序集合替代有语义的顺序。
- 明确列出被忽略的易变字段，例如时间戳、请求 ID、随机种子。忽略字段要写原因；不能因为“对不上”就删字段。
- 业务 ID、计数、版本号、状态枚举不能忽略。
- 快照落成 JSON 或同等的可 diff 文本；不要只截一张图当状态。
- 一次操作只对照一组前后快照；不要把三个操作混成一次 diff。

### 1.3 状态差异怎么判

| 观察 | 判定 |
|---|---|
| 实际 diff 与预期 diff 完全一致 | 通过 |
| 预期变化出现，但多出未解释的变化 | 不通过：多写、漏清理或副作用失控 |
| 预期变化少了 | 不通过：功能没做到 |
| 预期变化没出现，且没有任何错误 | 不通过：被静默吞掉 |
| 实际 diff 无法复现 | 不通过或标未验证；先查环境和夹具，不能记“偶尔正常” |
| diff 对上了，但外部副作用多了一次 | 不通过：状态对不代表行为对 |

示例：

```text
// before
{"pending": ["A", "B"], "attempts": {"A": 0, "B": 0}, "done": [], "failed": [], "last_error": null}
// after：处理 A 一次
{"pending": ["B"], "attempts": {"B": 0}, "done": ["A"], "failed": [], "last_error": null}
// diff：pending 少了 A，done 多了 A，attempts 里 A 被移除；没有其他变化
```

`attempts` 里 A 被移除是预期变化，不是“多出来的 diff”；写预期时必须把它写进去。凡是没写进预期的变化，一律按未解释处理。

## 2. 故障注入

只走成功路径，证明不了错误处理。每个行为改动至少选一个与它最相关的故障注入；涉及重试、并发、写入的，至少选两个。

| 故障 | 注入点 | 预期观察 | 不合格表现 |
|---|---|---|---|
| 校验失败 | 提交非法输入、超长文本、空必填项 | 停在错误态；输入保留；没有写入 | 清空输入、跳回首页、仍然落库 |
| 写入失败 | 存储层抛错、磁盘满、事务回滚 | 错误可见；没有半条记录；可重试 | 界面显示成功，数据只写了一半 |
| 超时 | 延迟响应、断网、服务不返回 | 加载态结束；给出重试；不重复提交 | 永远转圈，或重试后出现两条 |
| 重复提交 | 同一操作连点两次、同一请求重放 | 幂等：只产生一条记录或一次副作用 | 两条记录、两次扣减、两次通知 |
| 并发冲突 | 两个操作同时改同一条记录 | 后写有冲突提示或合并策略；不静默覆盖 | 后写直接覆盖，前写无提示消失 |
| 取消 / 中断 | 加载中取消、页面离开、进程被杀 | 没有孤儿任务；状态回到可继续的位置 | 后台继续写、留下半成品 |
| 部分失败 | 批量操作中一条失败 | 要么整批回滚，要么逐条标明成功/失败 | 界面说全成功，实际只成功一部分 |

故障注入的安全边界：

- 只在测试、夹具或临时数据上注入；不碰真实用户数据，不改生产配置。
- 注入前记录注入点、方法、预期和清理方式；注入后恢复现场。
- 能用事务、临时目录、测试替身解决的，不改产品代码来“制造故障”。
- 注入本身也要有证据：注入日志、错误码、前后快照；不能只说“我试过断网”。

## 3. 连续三次

“连续三次”是稳定性检查，不是性能采样。

- 同一版本、同一环境、同一夹具、同一命令，背靠背跑三次；中间不改代码、不改配置、不清缓存。
- 三次结果必须完全一致：状态、输出、错误码、关键读数都一致。
- 记录三次的时间、版本/提交号和运行环境；只写“跑了三次”不算证据。
- 随机、时间、并发相关的行为，先固定种子或时钟；固定不了就增加重复次数并记录分布，不能拿三次碰巧一致当稳定。

| 结果 | 判定 |
|---|---|
| 3/3 完全一致 | 通过（只证明这三次稳定，不证明永远稳定） |
| 2/3 一致 | 不通过：按不稳定处理，先定位差异 |
| 0–1/3 一致 | 不通过：功能或夹具本身有问题 |
| 三次都失败但错误一致 | 仍是不通过；一致地失败不是稳定通过 |

## 4. 性能 p50 / p95

性能结论必须带样本数，否则不可判。

### 4.1 定义与采样

- p50：第 50 百分位，本文用最近秩法取第 `ceil(0.50 × n)` 个样本，代表典型体验。
- p95：第 95 百分位，代表大多数用户会遇到的慢尾；本文用最近秩法，取第 `ceil(0.95 × n)` 个样本。
- 至少 20 个样本才判 p95；少于 20 个只能写“样本不足，不判 p95”。30 个更稳，但不强求。
- 先预热，再逐次计时；每次计时用同一个工作负载、同一个夹具、同一个环境。
- 记录原始样本或原始样本文件；不能只留一个算好的 p95。
- 明确计时边界：从哪个事件开始，到哪个事件结束。界面操作要说明“到可见结果出现”还是“到请求返回”；两者不能混。

### 4.2 判定表

| 指标 | 判据 | 说明 |
|---|---|---|
| p95 | 小于等于阈值 | 主判据；超过即不通过 |
| p50 | 记录并与基线比较 | 代表典型体验；p50 好不能抵消 p95 超标 |
| max | 记录并提示风险 | 不单独判通过；异常大值时说明原因 |
| n | 至少 20 | 少于 20 不判 p95 |
| 原始样本 | 必须保留 | 没有原始样本的 p95 不可复核 |

不要用平均值代替 p95，不要只报最快一次，不要跨机器或跨版本直接比绝对值。要比就跟同一环境、同一夹具的基线比。

### 4.3 报告格式

```text
指标: 设置页保存到成功提示可见
环境: <系统/运行时/构建号>
夹具: <数据规模、网络条件、是否冷启动>
样本: n=30，原始样本 evidence/perf-samples.txt
读数: min=0.41ms p50=0.64ms p95=1.22ms max=1.28ms
阈值: p95 <= 50ms
结论: 通过
```

示例读数来自本机一次实际运行，只用于演示格式；换环境必须重测，不能照抄。

## 5. 独立例子：重试队列

下面这个脚本只用 Python 标准库，直接运行即可。它同时演示状态差异、故障注入、连续三次和 p50/p95。

```python
#!/usr/bin/env python3
"""行为与性能验收的最小例子。"""

import json
import math
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class Job:
    job_id: str
    fail_once: bool = False
    attempts: int = 0


class RetryQueue:
    def __init__(self) -> None:
        self.pending: list[Job] = []
        self.done: list[str] = []
        self.failed: list[str] = []
        self.last_error: Optional[str] = None

    def add(self, job_id: str, fail_once: bool = False) -> None:
        self.pending.append(Job(job_id, fail_once))

    def process(self) -> str:
        if not self.pending:
            return "empty"
        job = self.pending[0]
        job.attempts += 1
        if job.fail_once and job.attempts == 1:
            if job.job_id not in self.failed:
                self.failed.append(job.job_id)
            self.last_error = "timeout"
            return "retry"
        self.pending.pop(0)
        if job.job_id in self.failed:
            self.failed.remove(job.job_id)
        if job.job_id not in self.done:
            self.done.append(job.job_id)
        self.last_error = None
        return "ok"

    def snapshot(self) -> dict:
        return {
            "pending": [job.job_id for job in self.pending],
            "attempts": {job.job_id: job.attempts for job in self.pending},
            "done": list(self.done),
            "failed": list(self.failed),
            "last_error": self.last_error,
        }


def changed(before: dict, after: dict) -> dict:
    return {
        key: {"before": before[key], "after": after[key]}
        for key in before
        if before[key] != after[key]
    }


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def run_scenario() -> dict:
    queue = RetryQueue()
    queue.add("A")
    queue.add("B", fail_once=True)
    assert queue.process() == "ok"
    assert queue.process() == "retry"
    assert queue.process() == "ok"
    return queue.snapshot()


def work() -> int:
    total = 0
    for i in range(20_000):
        total += i * i
    return total


def main() -> int:
    # 状态差异
    queue = RetryQueue()
    queue.add("A")
    queue.add("B")
    before = queue.snapshot()
    queue.process()
    after = queue.snapshot()
    diff = changed(before, after)
    assert diff == {
        "pending": {"before": ["A", "B"], "after": ["B"]},
        "attempts": {"before": {"A": 0, "B": 0}, "after": {"B": 0}},
        "done": {"before": [], "after": ["A"]},
    }, diff
    print("state_diff: PASS", json.dumps(diff, ensure_ascii=False))

    # 故障注入：第一次超时，任务不丢、不重复，第二次成功
    queue = RetryQueue()
    queue.add("B", fail_once=True)
    assert queue.process() == "retry"
    failed = queue.snapshot()
    assert failed["pending"] == ["B"] and failed["failed"] == ["B"]
    assert failed["done"] == [] and failed["last_error"] == "timeout"
    assert queue.process() == "ok"
    recovered = queue.snapshot()
    assert recovered["pending"] == [] and recovered["failed"] == []
    assert recovered["done"] == ["B"] and recovered["last_error"] is None
    print("fault_injection: PASS", json.dumps(recovered, ensure_ascii=False))

    # 连续三次：同一场景，三次快照必须完全一致
    runs = [run_scenario() for _ in range(3)]
    assert runs[0] == runs[1] == runs[2], runs
    print("three_runs: PASS (3/3 identical)")

    # 性能：预热后采集 30 个样本
    work()
    samples = []
    for _ in range(30):
        started = time.perf_counter()
        work()
        samples.append((time.perf_counter() - started) * 1000)
    p50 = percentile(samples, 50)
    p95 = percentile(samples, 95)
    assert p95 < 50.0, p95
    print(
        f"perf: n={len(samples)} p50={p50:.3f}ms "
        f"p95={p95:.3f}ms max={max(samples):.3f}ms threshold=50ms PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

运行与实测输出：

```text
$ python3 behavior_perf_example.py
state_diff: PASS {"pending": {"before": ["A", "B"], "after": ["B"]}, "attempts": {"before": {"A": 0, "B": 0}, "after": {"B": 0}}, "done": {"before": [], "after": ["A"]}}
fault_injection: PASS {"pending": [], "attempts": {}, "done": ["B"], "failed": [], "last_error": null}
three_runs: PASS (3/3 identical)
perf: n=30 p50=0.635ms p95=1.220ms max=1.280ms threshold=50ms PASS
```

怎么把它当成 07 的一行：

```text
| BP-DEMO-01 | 处理失败后重试不丢任务、不重复写入 | 第一次处理返回超时，任务仍在 pending；第二次处理成功，done 只出现一次，failed 清空 | A | A | evidence/behavior-output.txt；evidence/perf-samples.txt | 通过 | 复核者乙 |
```

`state_diff` 的输出里，`attempts` 的 `A` 被移除是预期变化，不是多余 diff。写预期时要把“任务离开 pending，所以 attempts 里也消失”写清楚，否则会被误判为多出来的变化。

## 6. 收口自检

- [ ] 行为结论写成了“前置状态 + 操作 + 后置状态”，不是一句“正常”。
- [ ] 快照包含数据、界面、外部副作用和错误；易变字段的忽略有原因。
- [ ] 一次操作只对照一组前后快照；多余变化有解释或被判失败。
- [ ] 至少注入了一个与改动相关的故障；重试/并发/写入类至少两个。
- [ ] 连续三次同版本、同环境、同夹具；三次结果一致，记录完整。
- [ ] 性能样本不少于 20 个；报告了 n、p50、p95、max、阈值和原始样本。
- [ ] p95 超标就是不通过；p50 好不能抵消。
- [ ] 07 里一个验收项一行，状态只用七种状态。

## 7. 来源

本文件没有引用外部标准。p50/p95 是描述统计，样本数门槛和判定表是本技能包的约定，不冒充行业标准；外部资料清单见 `docs/sources.md`。
