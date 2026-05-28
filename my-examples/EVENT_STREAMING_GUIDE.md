# LangGraph Event Streaming 完整指南

本指南严格按照官方文档编写: https://docs.langchain.com/oss/python/langgraph/event-streaming

## 概述

Event Streaming 是 LangGraph v1.2+ 推荐的流式 API,提供类型化的投影（projections）来消费图执行过程中的事件。

## 核心概念

### 1. 基本 API

```python
# 同步版本
stream = graph.stream_events(input_data, version="v3")

# 异步版本
stream = await graph.astream_events(input_data, version="v3")
```

### 2. 类型化投影

| 投影 | 用途 | 访问方式 |
|------|------|----------|
| `stream.values` | 状态快照流 | `for snapshot in stream.values` |
| `stream.output` | 最终输出 | 同步: `stream.output` / 异步: `await stream.output()` |
| `stream.messages` | 消息流 | `for message in stream.messages` |
| `stream.subgraphs` | 子图执行 | `for subgraph in stream.subgraphs` |
| `stream.interrupts` | 中断信息 | `stream.interrupts` |
| `stream.interrupted` | 是否中断 | `stream.interrupted` |
| `stream` | 原始协议事件 | `for event in stream` |
| `stream.extensions` | 自定义投影 | `stream.extensions["name"]` |

### 3. 同步 vs 异步

**同步 (stream_events)**:
- `stream.output` 是属性
- 使用 `stream.interleave()` 交错消费多个投影

**异步 (astream_events)**:
- `stream.output()` 是方法,需要 `await`
- 使用 `asyncio.gather()` 并发消费多个投影

## 示例场景

### 场景 1: 基础流式输出

```python
stream = graph.stream_events(input_data, version="v3")

# 消费状态快照
for snapshot in stream.values:
    print(f"Counter: {snapshot['counter']}")

# 获取最终输出
final_state = stream.output
```

### 场景 2: 异步并发消费

```python
stream = await graph.astream_events(input_data, version="v3")

async def consume_values():
    async for snapshot in stream.values:
        print(f"State: {snapshot}")

async def consume_events():
    async for event in stream:
        print(f"Event: {event['method']}")

# 并发消费
await asyncio.gather(consume_values(), consume_events())

# 获取最终输出 (异步需要 await)
final_state = await stream.output()
```

### 场景 3: 交错消费 (同步)

```python
stream = graph.stream_events(input_data, version="v3")

# 按严格到达顺序消费多个投影
for name, item in stream.interleave("values", "messages"):
    if name == "values":
        print(f"State: {item}")
    elif name == "messages":
        print(f"Message: {item}")
```

### 场景 4: 人机协作中断和恢复

```python
from langgraph.types import Command

# 第一次运行 - 直到中断点
stream = graph.stream_events(input_data, config=config, version="v3")

for snapshot in stream.values:
    print(snapshot)

# 检查是否中断
if stream.interrupted:
    print(f"Interrupted: {stream.interrupts}")
    
    # 使用 Command 恢复执行
    resume_stream = graph.stream_events(
        Command(resume={"user_decision": "approve"}),
        config=config,
        version="v3"
    )
    
    final_output = resume_stream.output
```

**注意**: 
- 需要使用 `checkpointer` 和 `config` 中的 `thread_id`
- `interrupt_before` 会在节点执行前暂停
- 可以使用 `graph.update_state()` 来更新状态后继续执行

### 场景 3: 交错消费 (同步)

`stream.interleave()` 是同步代码中按严格到达顺序消费多个投影的最佳方式。

```python
stream = graph.stream_events(input_data, version="v3")

# 交错消费多个投影 - 按严格到达顺序
for name, item in stream.interleave("values", "messages", "subgraphs"):
    if name == "values":
        print(f"[state] keys={list(item)}")
    elif name == "messages":
        print(f"[llm] node={item.node}")
    elif name == "subgraphs":
        print(f"[subgraph] path={item.path}")
```

**核心价值**:
- ✅ 按严格时间顺序交错多个投影
- ✅ 保持事件的因果关系和时序
- ✅ 适用于日志记录、调试、实时监控

**使用场景**:
1. **聊天应用**: 交错消费 `messages` (LLM输出) 和 `values` (状态)
2. **多智能体**: 交错消费 `subgraphs` (子图) 和 `messages`
3. **调试工具**: 交错所有投影以查看完整执行流程
4. **实时监控**: 按时序显示所有类型的事件

**对比**:
- **同步代码**: 使用 `stream.interleave()` - 简单直接
- **异步代码**: 使用 `asyncio.gather()` - 并发消费

### 场景 5: 原始协议事件

```python
stream = graph.stream_events(input_data, version="v3")

# 迭代原始协议事件
for event in stream:
    namespace = event["params"]["namespace"]
    method = event["method"]
    seq = event["seq"]
    data = event["params"]["data"]
    
    print(f"Event #{seq}: [{method}] {namespace}")
```

**协议事件结构**:
```python
class ProtocolEvent(TypedDict):
    seq: int                    # 严格递增的序列号
    method: str                 # 通道名: "messages", "values", "custom", etc.
    params: ProtocolEventParams

class ProtocolEventParams(TypedDict):
    namespace: list[str]        # 命名空间路径
    timestamp: int              # 时间戳 (毫秒)
    data: Any                   # 通道特定的数据
```

### 场景 6: 自定义 StreamTransformer

```python
from langgraph.stream import ProtocolEvent, StreamChannel, StreamTransformer
from langgraph.config import get_stream_writer

# 1. 定义转换器
class ProgressTransformer(StreamTransformer):
    required_stream_modes = ("custom",)  # 声明需要的流模式
    
    def __init__(self, scope: tuple[str, ...] = ()) -> None:
        super().__init__(scope)
        # 创建命名通道
        self.progress = StreamChannel[dict]("progress")
    
    def init(self) -> dict:
        return {"progress": self.progress}
    
    def process(self, event: ProtocolEvent) -> bool:
        if event["method"] == "custom":
            data = event["params"]["data"]
            if data.get("type") == "progress":
                self.progress.push(data)
        return True

# 2. 在节点中发送自定义事件
def my_node(state):
    writer = get_stream_writer()
    writer({"type": "progress", "percent": 50, "message": "进行中"})
    return state

# 3. 注册转换器并消费
stream = graph.stream_events(
    input_data,
    version="v3",
    transformers=[ProgressTransformer]  # 传递类,不是实例
)

# 从 extensions 访问自定义投影
for progress in stream.extensions["progress"]:
    print(f"{progress['percent']}% - {progress['message']}")
```

**关键点**:
- `required_stream_modes`: 声明需要的流模式
- `StreamChannel`: 创建投影通道
- `get_stream_writer()`: 在节点中发送自定义事件
- `transformers` 参数: 传递类或工厂函数,不是实例
- `stream.extensions`: 访问自定义投影

## 通道类型

| 通道 | 用途 |
|------|------|
| `values` | 完整的图状态快照 |
| `updates` | 每个节点的状态增量 |
| `messages` | 聊天模型消息输出 |
| `tools` | 工具调用事件 |
| `lifecycle` | 运行、子图、子代理状态 |
| `checkpoints` | 检查点信息 |
| `input` | 人机交互输入请求和响应 |
| `tasks` | Pregel 任务创建和结果 |
| `custom` | 用户自定义事件 |
| `custom:<name>` | 应用定义的转换器输出 |

## 最佳实践

### 1. 选择合适的 API

- **新应用**: 使用 Event Streaming (`stream_events(version="v3")`)
- **需要底层访问**: 使用 Streaming (`stream(stream_mode=...)`)

### 2. 同步 vs 异步

- **同步**: 简单场景,单线程消费
- **异步**: 需要并发消费多个投影,或与其他异步代码集成

### 3. 自定义转换器

- **命名通道** (`StreamChannel("name")`): 事件会出现在主事件流中
- **匿名通道** (`StreamChannel()`): 仅作为侧通道投影

### 4. 错误处理

```python
stream = graph.stream_events(input_data, version="v3")

try:
    for snapshot in stream.values:
        process(snapshot)
    final_output = stream.output
except Exception as e:
    print(f"Error: {e}")
```

## 常见问题

### Q1: `stream.output` 报错 "not subscriptable"

**原因**: 异步版本中 `stream.output()` 是方法,需要 `await`

**解决**:
```python
# 同步
final_state = stream.output

# 异步
final_state = await stream.output()
```

### Q2: 自定义事件没有被捕获

**原因**: 
1. 没有声明 `required_stream_modes = ("custom",)`
2. 没有注册转换器

**解决**:
```python
class MyTransformer(StreamTransformer):
    required_stream_modes = ("custom",)  # 必须声明
    # ...

stream = graph.stream_events(
    input_data,
    version="v3",
    transformers=[MyTransformer]  # 必须注册
)
```

### Q3: 中断没有触发

**原因**: `interrupt_before` 会在节点执行前暂停,需要正确的配置

**解决**:
```python
# 1. 编译时配置
graph = builder.compile(
    checkpointer=InMemorySaver(),
    interrupt_before=["node_name"]
)

# 2. 使用 config 和 thread_id
config = {"configurable": {"thread_id": "unique-id"}}

# 3. 检查状态
state = graph.get_state(config)
if state.next:
    # 有待执行的节点
    graph.update_state(config, {"key": "value"})
```

### Q4: transformers 参数报错

**错误**: `transformers must be scope-aware callables`

**原因**: 传递了实例而不是类

**解决**:
```python
# ❌ 错误
transformers=[MyTransformer()]

# ✅ 正确
transformers=[MyTransformer]

# ✅ 或使用工厂函数
transformers=[lambda scope: MyTransformer(scope, custom_arg="value")]
```

## 应用场景

1. **实时 UI 更新**: 聊天界面、进度条
2. **多智能体协作监控**: 观察子图执行
3. **工具调用追踪**: 监控工具执行
4. **自定义进度事件**: 通过 StreamTransformer
5. **人机协作工作流**: 中断和恢复
6. **调试和可观测性**: 原始协议事件

## 参考资源

- [官方文档](https://docs.langchain.com/oss/python/langgraph/event-streaming)
- [示例代码](./examples9_event_streaming.py)
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph)
