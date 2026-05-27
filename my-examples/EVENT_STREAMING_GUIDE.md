# LangGraph Event Streaming 深度指南

## 📚 目录

1. [核心概念](#核心概念)
2. [架构原理](#架构原理)
3. [API 对比](#api-对比)
4. [投影类型](#投影类型)
5. [应用场景](#应用场景)
6. [最佳实践](#最佳实践)
7. [常见问题](#常见问题)

---

## 核心概念

### 什么是 Event Streaming？

**Event Streaming** 是 LangGraph v1.2+ 引入的推荐流式 API，它提供了**类型化的投影（Typed Projections）**来消费图执行事件。

### 为什么需要 Event Streaming？

**传统 stream_mode API 的问题：**
```python
# 旧方式：需要手动解析 stream_mode 元组
for chunk in graph.stream(input, stream_mode="values"):
    # 需要判断 chunk 的类型和结构
    if isinstance(chunk, tuple):
        node, data = chunk
        # 处理数据...
```

**Event Streaming 的优势：**
```python
# 新方式：类型化投影，清晰明确
stream = graph.stream_events(input, version="v3")

# 直接访问消息流
for message in stream.messages:
    print(message.text)

# 直接访问状态流
for snapshot in stream.values:
    print(snapshot)
```

### 核心优势

1. **类型安全**：每个投影都有明确的类型
2. **并发消费**：可以同时消费多个投影
3. **独立迭代**：读取 `stream.messages` 不会消耗 `stream.values` 的事件
4. **可扩展**：支持自定义流转换器

---

## 架构原理

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     LangGraph Pregel Engine                  │
│  (执行图节点，生成原始执行事件)                              │
└────────────────────┬────────────────────────────────────────┘
                     │ Raw Pregel Events
                     │ (updates, values, messages, custom, ...)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                      Event Router                            │
│  (规范化事件，路由到转换器管道)                              │
└────────────────────┬────────────────────────────────────────┘
                     │ Protocol Events
                     │ (ProtocolEvent 包装)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Stream Transformers                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Values     │  │   Messages   │  │   Custom     │      │
│  │ Transformer  │  │ Transformer  │  │ Transformer  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────┬────────────────────────────────────────┘
                     │ Projected Events
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Event Stream Object                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  stream.messages   → 消息投影                        │   │
│  │  stream.values     → 状态快照投影                    │   │
│  │  stream.subgraphs  → 子图投影                        │   │
│  │  stream.output     → 最终输出                        │   │
│  │  stream.extensions → 自定义投影                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                     │
                     ▼
              Application Code
              (你的业务逻辑)
```

### 事件流转过程

1. **Pregel Engine** 执行图节点，生成原始事件
2. **Event Router** 规范化事件为 `ProtocolEvent` 格式
3. **Stream Transformers** 处理事件，生成投影
4. **Event Stream** 暴露类型化投影给应用代码

### ProtocolEvent 结构

```python
class ProtocolEvent(TypedDict):
    seq: int                    # 严格递增的序列号（用于排序）
    method: str                 # 通道名称: "messages", "values", "custom", ...
    params: ProtocolEventParams

class ProtocolEventParams(TypedDict):
    namespace: list[str]        # 从根图到当前作用域的路径
    timestamp: int              # 墙钟时间（毫秒）
    data: Any                   # 通道特定的负载
```

**示例事件：**
```python
{
    "seq": 42,
    "method": "values",
    "params": {
        "namespace": ["researcher:6f4d"],
        "timestamp": 1704067200000,
        "data": {"messages": [...], "counter": 5}
    }
}
```

---

## API 对比

### stream_mode API (旧方式)

```python
# 需要指定 stream_mode
for chunk in graph.stream(input, stream_mode="values"):
    print(chunk)  # 元组或字典，需要手动解析

# 多个 stream_mode 需要多次调用
for chunk in graph.stream(input, stream_mode="messages"):
    print(chunk)
```

**缺点：**
- 需要手动解析不同 stream_mode 的输出格式
- 无法同时消费多个 stream_mode
- 类型不安全

### stream_events API (新方式)

```python
# 一次调用，多个投影
stream = graph.stream_events(input, version="v3")

# 类型化访问
for message in stream.messages:
    print(message.text)

for snapshot in stream.values:
    print(snapshot)

# 并发消费
async def consume_all():
    await asyncio.gather(
        consume_messages(stream),
        consume_values(stream)
    )
```

**优点：**
- 类型安全
- 并发消费
- 清晰的 API

---

## 投影类型

### 1. stream.messages - 消息流

**用途：** 流式输出 LLM 生成的消息

```python
stream = graph.stream_events(input, version="v3")

for message in stream.messages:
    # Token 级别的流式输出
    for token in message.text:
        print(token, end="", flush=True)
    
    # 访问推理过程
    for reasoning in message.reasoning:
        print(f"[思考] {reasoning}")
    
    # 访问工具调用
    for tool_call in message.tool_calls:
        print(f"[工具] {tool_call.name}({tool_call.args})")
    
    # 访问使用统计
    if message.output.usage_metadata:
        print(f"Token 使用: {message.output.usage_metadata}")
```

**关键属性：**
- `message.text` - 可迭代的文本流
- `message.reasoning` - 推理过程流
- `message.tool_calls` - 工具调用流
- `message.node` - 生成消息的节点名称
- `message.output` - 完整的消息对象

### 2. stream.values - 状态快照流

**用途：** 监控每个步骤后的完整状态

```python
stream = graph.stream_events(input, version="v3")

for snapshot in stream.values:
    print(f"当前状态: {snapshot}")
    print(f"消息数: {len(snapshot.get('messages', []))}")
    print(f"计数器: {snapshot.get('counter')}")
```

**特点：**
- 每个节点执行后生成一个快照
- 包含完整的图状态
- 适合监控状态变化

### 3. stream.subgraphs - 子图流

**用途：** 监控嵌套图的执行

```python
stream = graph.stream_events(input, version="v3")

for subgraph in stream.subgraphs:
    print(f"子图: {subgraph.graph_name}")
    print(f"路径: {subgraph.path}")
    
    # 访问子图的消息
    for message in subgraph.messages:
        print(f"  [子图消息] {message.text}")
```

**关键属性：**
- `subgraph.graph_name` - 子图名称
- `subgraph.path` - 从根图到子图的路径
- `subgraph.messages` - 子图的消息流
- `subgraph.values` - 子图的状态流

### 4. stream.output - 最终输出

**用途：** 等待并获取最终结果

```python
stream = graph.stream_events(input, version="v3")

# 消费流
for message in stream.messages:
    print(message.text)

# 获取最终输出
final_state = stream.output
print(f"最终结果: {final_state}")
```

**特点：**
- 阻塞直到图执行完成
- 返回最终状态
- 类似于 `graph.invoke()` 的返回值

### 5. stream.interrupts - 中断信息

**用途：** 检查人机协作中断

```python
stream = graph.stream_events(input, version="v3")

# 消费流
for message in stream.messages:
    print(message.text)

# 检查是否中断
if stream.interrupted:
    print("执行已暂停")
    print(f"中断信息: {stream.interrupts}")
    
    # 恢复执行
    resume_stream = graph.stream_events(
        Command(resume={"approval": "approve"}),
        config=config,
        version="v3"
    )
```

### 6. stream.extensions - 自定义投影

**用途：** 访问自定义流转换器的投影

```python
# 注册自定义转换器
graph = graph.compile(stream_transformers=[ProgressTransformer()])

stream = graph.stream_events(input, version="v3")

# 访问自定义投影
for progress in stream.extensions.progress:
    print(f"进度: {progress['percent']}%")
```

---

## 应用场景

### 场景 1: 实时聊天界面

```python
async def chat_ui_handler(user_message: str):
    """实时更新聊天界面"""
    stream = await agent.astream_events(
        {"messages": [{"role": "user", "content": user_message}]},
        version="v3"
    )
    
    # Token 级别的流式输出
    async for message in stream.messages:
        async for token in message.text:
            # 实时更新 UI
            await websocket.send({"type": "token", "data": token})
    
    # 发送完成信号
    await websocket.send({"type": "complete"})
```

### 场景 2: 进度条和状态监控

```python
async def monitor_progress(task_id: str):
    """监控任务进度"""
    stream = await graph.astream_events(input_data, version="v3")
    
    async def update_progress():
        async for snapshot in stream.values:
            progress = calculate_progress(snapshot)
            await update_ui_progress_bar(task_id, progress)
    
    async def log_messages():
        async for message in stream.messages:
            await log_to_database(task_id, message.text)
    
    # 并发监控
    await asyncio.gather(update_progress(), log_messages())
```

### 场景 3: 多智能体协作监控

```python
async def monitor_multi_agent_system():
    """监控多智能体系统"""
    stream = await graph.astream_events(input_data, version="v3")
    
    # 监控子图（子智能体）
    async for subgraph in stream.subgraphs:
        print(f"智能体 {subgraph.graph_name} 开始工作")
        
        # 监控子智能体的消息
        async for message in subgraph.messages:
            print(f"  [{subgraph.graph_name}] {message.text}")
```

### 场景 4: 工具调用追踪

```python
async def trace_tool_calls():
    """追踪工具调用"""
    stream = await agent.astream_events(input_data, version="v3")
    
    async for message in stream.messages:
        # 追踪工具调用
        for tool_call in message.tool_calls:
            print(f"调用工具: {tool_call.name}")
            print(f"参数: {tool_call.args}")
            
            # 记录到追踪系统
            await tracing_system.log_tool_call(
                tool_name=tool_call.name,
                args=tool_call.args,
                timestamp=datetime.now()
            )
```

### 场景 5: 人机协作工作流

```python
async def human_in_loop_workflow():
    """人机协作工作流"""
    config = {"configurable": {"thread_id": "session-123"}}
    
    # 第一阶段：运行直到中断
    stream = await graph.astream_events(input_data, config=config, version="v3")
    
    async for message in stream.messages:
        await display_to_user(message.text)
    
    # 检查中断
    if stream.interrupted:
        # 请求人工输入
        user_decision = await request_user_input(stream.interrupts)
        
        # 恢复执行
        resume_stream = await graph.astream_events(
            Command(resume=user_decision),
            config=config,
            version="v3"
        )
        
        async for message in resume_stream.messages:
            await display_to_user(message.text)
```

### 场景 6: 自定义进度事件

```python
class ProgressTransformer(StreamTransformer):
    """自定义进度转换器"""
    required_stream_modes = ("values", "custom")
    
    def __init__(self, scope: tuple[str, ...] = ()) -> None:
        super().__init__(scope)
        self.progress = StreamChannel[dict]("progress")
    
    def init(self) -> dict:
        return {"progress": self.progress}
    
    def process(self, event: ProtocolEvent) -> bool:
        if event["method"] == "values":
            # 计算进度
            progress_data = {
                "percent": calculate_percent(event),
                "message": extract_message(event)
            }
            self.progress.push(progress_data)
        return True

# 使用
graph = graph.compile(stream_transformers=[ProgressTransformer()])
stream = graph.stream_events(input_data, version="v3")

for progress in stream.extensions.progress:
    print(f"进度: {progress['percent']}% - {progress['message']}")
```

---

## 最佳实践

### 1. 选择合适的投影

| 需求 | 使用投影 |
|------|---------|
| 实时显示 LLM 输出 | `stream.messages` |
| 监控状态变化 | `stream.values` |
| 追踪子图执行 | `stream.subgraphs` |
| 等待最终结果 | `stream.output` |
| 人机协作 | `stream.interrupts` + `stream.interrupted` |
| 自定义事件 | `stream.extensions` |

### 2. 并发消费模式

**异步代码（推荐）：**
```python
stream = await graph.astream_events(input, version="v3")

async def consume_messages():
    async for message in stream.messages:
        await process_message(message)

async def consume_values():
    async for snapshot in stream.values:
        await process_snapshot(snapshot)

# 并发消费
await asyncio.gather(consume_messages(), consume_values())
```

**同步代码：**
```python
stream = graph.stream_events(input, version="v3")

# 使用 interleave 按到达顺序消费
for name, item in stream.interleave("messages", "values"):
    if name == "messages":
        process_message(item)
    elif name == "values":
        process_snapshot(item)
```

### 3. 错误处理

```python
try:
    stream = await graph.astream_events(input, version="v3")
    
    async for message in stream.messages:
        print(message.text)
    
    final_output = stream.output
except Exception as e:
    print(f"执行失败: {e}")
    # 处理错误
```

### 4. 性能优化

**只消费需要的投影：**
```python
# ❌ 不好：创建了不使用的投影
stream = graph.stream_events(input, version="v3")
for message in stream.messages:
    print(message.text)
# stream.values, stream.subgraphs 等投影被创建但未使用

# ✅ 好：只消费需要的投影
stream = graph.stream_events(input, version="v3")
for message in stream.messages:
    print(message.text)
# 其他投影不会被迭代，不会产生额外开销
```

**使用自定义转换器过滤事件：**
```python
class FilteredTransformer(StreamTransformer):
    """只处理特定节点的事件"""
    required_stream_modes = ("values",)
    
    def process(self, event: ProtocolEvent) -> bool:
        namespace = event["params"]["namespace"]
        node_name = namespace[-1].split(":")[0] if namespace else ""
        
        # 只处理特定节点
        if node_name not in ["important_node1", "important_node2"]:
            return False  # 抑制事件
        
        return True
```

### 5. 调试技巧

**查看原始事件：**
```python
stream = graph.stream_events(input, version="v3")

# 迭代原始协议事件
for event in stream:
    print(f"事件 #{event['seq']}: {event['method']}")
    print(f"  命名空间: {event['params']['namespace']}")
    print(f"  数据: {event['params']['data']}")
```

**使用 LangSmith 追踪：**
```python
import os
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_API_KEY"] = "your-api-key"

# 所有事件会自动发送到 LangSmith
stream = graph.stream_events(input, version="v3")
```

---

## 常见问题

### Q1: stream_events 和 stream 有什么区别？

**A:** 
- `stream()` 是旧的 stream_mode API，返回元组或字典，需要手动解析
- `stream_events()` 是新的 Event Streaming API，返回类型化投影，更易用

**推荐使用 `stream_events(version="v3")`**

### Q2: 为什么需要 version="v3"？

**A:** 
- `v3` 是最新的事件流协议版本
- 提供了更好的类型安全和性能
- 未来版本可能会有 breaking changes，显式指定版本确保兼容性

### Q3: 如何在同步代码中使用？

**A:**
```python
# 同步版本
stream = graph.stream_events(input, version="v3")

# 异步版本
stream = await graph.astream_events(input, version="v3")
```

### Q4: 消费一个投影会影响其他投影吗？

**A:** 不会。每个投影是独立的，消费 `stream.messages` 不会影响 `stream.values`。

### Q5: 如何实现超时控制？

**A:**
```python
import asyncio

async def with_timeout():
    stream = await graph.astream_events(input, version="v3")
    
    try:
        async with asyncio.timeout(30):  # 30秒超时
            async for message in stream.messages:
                print(message.text)
    except asyncio.TimeoutError:
        print("执行超时")
```

### Q6: 自定义转换器的 required_stream_modes 是什么？

**A:** 
- 声明转换器需要哪些 Pregel stream modes
- 运行时会合并所有转换器的 required_stream_modes
- 只有声明的 modes 才会被 Pregel 引擎发出

```python
class MyTransformer(StreamTransformer):
    # 声明需要 custom 和 values 模式
    required_stream_modes = ("custom", "values")
    
    def process(self, event: ProtocolEvent) -> bool:
        # 只会收到 custom 和 values 事件
        if event["method"] == "custom":
            # 处理自定义事件
            pass
        return True
```

### Q7: 如何处理大量事件？

**A:**
```python
# 使用自定义转换器过滤
class SamplingTransformer(StreamTransformer):
    """采样转换器 - 只保留 10% 的事件"""
    def __init__(self):
        super().__init__()
        self.counter = 0
    
    def process(self, event: ProtocolEvent) -> bool:
        self.counter += 1
        # 只保留每10个事件中的1个
        return self.counter % 10 == 0

graph = graph.compile(stream_transformers=[SamplingTransformer()])
```

### Q8: 如何在 FastAPI 中使用？

**A:**
```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.post("/chat/stream")
async def chat_stream(message: str):
    async def event_generator():
        stream = await agent.astream_events(
            {"messages": [{"role": "user", "content": message}]},
            version="v3"
        )
        
        async for msg in stream.messages:
            async for token in msg.text:
                yield f"data: {token}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

---

## 总结

### 核心要点

1. **Event Streaming 是推荐的流式 API** - 使用 `stream_events(version="v3")`
2. **类型化投影** - messages, values, subgraphs, output, extensions
3. **并发消费** - 使用 `asyncio.gather()` 或 `stream.interleave()`
4. **可扩展** - 通过 `StreamTransformer` 添加自定义投影
5. **人机协作** - 使用 `stream.interrupted` 和 `Command(resume=...)`

### 架构理解

```
Pregel Engine → Event Router → Stream Transformers → Typed Projections → Application
```

### 何时使用

| 场景 | 使用 |
|------|------|
| 实时 UI 更新 | `stream.messages` |
| 状态监控 | `stream.values` |
| 子图追踪 | `stream.subgraphs` |
| 人机协作 | `stream.interrupts` |
| 自定义事件 | `StreamTransformer` + `stream.extensions` |
| 调试 | 迭代原始 `stream` 对象 |

### 下一步

1. 运行 `event_streaming_comprehensive.py` 查看所有示例
2. 阅读官方文档：https://docs.langchain.com/oss/python/langgraph/event-streaming
3. 在你的项目中实践 Event Streaming
4. 尝试创建自定义 StreamTransformer

---

**参考资源：**
- [LangGraph Event Streaming 文档](https://docs.langchain.com/oss/python/langgraph/event-streaming)
- [LangGraph Streaming 文档](https://docs.langchain.com/oss/python/langgraph/streaming)
- [LangChain Event Streaming 文档](https://docs.langchain.com/oss/python/langchain/event-streaming)
