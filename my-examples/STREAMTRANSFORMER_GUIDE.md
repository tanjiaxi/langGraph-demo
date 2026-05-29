# StreamTransformer 完整指南

## 什么是 StreamTransformer?

`StreamTransformer` 是 LangGraph Event Streaming 中的一个强大机制,用于**观察和转换原始协议事件**,创建**自定义的投影 (projections)**。

## 工作流程

```
图执行 → 原始事件 → StreamTransformer → 自定义投影 → 应用代码
```

### 具体例子:

```
节点发送 custom 事件 
    ↓
ProgressTransformer 监听并处理
    ↓
推送到 progress 投影
    ↓
UI 通过 stream.extensions['progress'] 访问
    ↓
显示进度条
```

## 为什么需要 StreamTransformer?

### ❌ 不使用 StreamTransformer (手动处理)

```python
stream = graph.stream_events(input_data, version="v3")

# 需要手动遍历所有原始事件
progress_events = []
for event in stream:
    if event["method"] == "custom":
        data = event["params"]["data"]
        if isinstance(data, dict) and data.get("type") == "progress":
            progress_events.append(data)
            # 处理进度事件...

# 问题:
# 1. 代码重复 - 每次都要写相同的过滤逻辑
# 2. 难以复用 - 无法在多个地方共享
# 3. 类型不安全 - 需要手动检查数据结构
# 4. 混乱 - 业务逻辑和事件处理混在一起
```

### ✅ 使用 StreamTransformer (自动处理)

```python
# 1. 定义转换器 (一次定义,到处复用)
class ProgressTransformer(StreamTransformer):
    required_stream_modes = ("custom",)
    
    def __init__(self, scope=()):
        super().__init__(scope)
        self.progress = StreamChannel[ProgressEvent]("progress")
    
    def init(self):
        return {"progress": self.progress}
    
    def process(self, event):
        if event["method"] == "custom":
            data = event["params"]["data"]
            if data.get("type") == "progress":
                self.progress.push(data)
        return True

# 2. 使用转换器
stream = graph.stream_events(
    input_data,
    version="v3",
    transformers=[ProgressTransformer]  # 注册转换器
)

# 3. 访问自定义投影 (简洁清晰)
for progress in stream.extensions["progress"]:
    print(f"{progress['percent']}% - {progress['message']}")

# 优势:
# 1. 代码简洁 - 业务逻辑清晰
# 2. 可复用 - 转换器可以在多个地方使用
# 3. 类型安全 - 使用 TypedDict 定义类型
# 4. 关注点分离 - 事件处理和业务逻辑分离
```

## StreamTransformer 的核心组件

### 1. `required_stream_modes`

声明需要监听的通道。**非常重要!** 未声明的通道不会被发送。

```python
class MyTransformer(StreamTransformer):
    # 声明需要监听 custom 和 messages 通道
    required_stream_modes = ("custom", "messages")
```

**可用的通道**:
- `"messages"` - 聊天模型消息
- `"tools"` - 工具调用
- `"custom"` - 自定义事件
- `"values"` - 状态快照
- `"updates"` - 状态增量
- `"checkpoints"` - 检查点
- `"tasks"` - 任务事件
- `"debug"` - 调试信息

### 2. `StreamChannel`

投影的容器,用于推送和消费事件。

```python
# 命名通道 - 事件会出现在主事件流中
self.progress = StreamChannel[ProgressEvent]("progress")

# 匿名通道 - 仅作为侧通道,不出现在主事件流
self.stats = StreamChannel[StatsEvent]()
```

**区别**:
- **命名通道**: 推送的值会作为 `custom:progress` 事件出现在主事件流
- **匿名通道**: 推送的值只能通过 `stream.extensions` 访问

### 3. 核心方法

#### `__init__(self, scope)`

初始化转换器,创建投影通道。

```python
def __init__(self, scope: tuple[str, ...] = ()) -> None:
    super().__init__(scope)
    self.progress = StreamChannel[ProgressEvent]("progress")
    self.stats = StreamChannel[StatsEvent]()
```

#### `init(self) -> dict`

注册投影,返回投影字典。

```python
def init(self) -> dict:
    return {
        "progress": self.progress,
        "stats": self.stats
    }
```

#### `process(self, event: ProtocolEvent) -> bool`

处理每个协议事件。返回 `False` 会抑制原始事件。

```python
def process(self, event: ProtocolEvent) -> bool:
    if event["method"] == "custom":
        data = event["params"]["data"]
        if data.get("type") == "progress":
            self.progress.push(data)
    return True  # 返回 True 保留原始事件
```

**ProtocolEvent 结构**:
```python
{
    "seq": 1,                    # 序列号
    "method": "custom",          # 通道名
    "params": {
        "namespace": [],         # 命名空间
        "timestamp": 1234567890, # 时间戳
        "data": {...}            # 数据
    }
}
```

#### `finalize(self)` 和 `fail(self, err)`

流结束时的清理工作。

```python
def finalize(self) -> None:
    # 流成功完成时调用
    self.progress.close()

def fail(self, err: BaseException) -> None:
    # 流失败时调用
    self.progress.fail(err)
```

## 实际应用场景

### 1. 进度追踪

```python
class ProgressTransformer(StreamTransformer):
    required_stream_modes = ("custom",)
    
    def __init__(self, scope=()):
        super().__init__(scope)
        self.progress = StreamChannel("progress")
    
    def process(self, event):
        if event["method"] == "custom":
            data = event["params"]["data"]
            if data.get("type") == "progress":
                self.progress.push({
                    "percent": data["percent"],
                    "message": data["message"]
                })
        return True

# 使用
for progress in stream.extensions["progress"]:
    update_progress_bar(progress["percent"])
```

### 2. Token 统计

```python
class TokenStatsTransformer(StreamTransformer):
    required_stream_modes = ("messages",)
    
    def __init__(self, scope=()):
        super().__init__(scope)
        self.total_tokens = 0
        self.stats = StreamChannel()
    
    def init(self):
        return {"token_stats": self.stats}
    
    def process(self, event):
        if event["method"] == "messages":
            data = event["params"]["data"]
            if isinstance(data, dict):
                usage = data.get("usage", {})
                self.total_tokens += usage.get("total_tokens", 0)
        return True
    
    def finalize(self):
        self.stats.push({"total_tokens": self.total_tokens})
        self.stats.close()

# 使用
for stats in stream.extensions["token_stats"]:
    print(f"Total tokens: {stats['total_tokens']}")
```

### 3. 工具调用监控

```python
class ToolMonitorTransformer(StreamTransformer):
    required_stream_modes = ("tools",)
    
    def __init__(self, scope=()):
        super().__init__(scope)
        self.tool_calls = StreamChannel("tool_calls")
        self.call_count = {}
    
    def init(self):
        return {"tool_calls": self.tool_calls}
    
    def process(self, event):
        if event["method"] == "tools":
            data = event["params"]["data"]
            if data.get("event") == "tool-started":
                tool_name = data["tool_name"]
                self.call_count[tool_name] = self.call_count.get(tool_name, 0) + 1
                self.tool_calls.push({
                    "tool": tool_name,
                    "count": self.call_count[tool_name]
                })
        return True

# 使用
for call in stream.extensions["tool_calls"]:
    print(f"Tool {call['tool']} called {call['count']} times")
```

### 4. 错误收集

```python
class ErrorCollectorTransformer(StreamTransformer):
    required_stream_modes = ("messages", "tools", "custom")
    
    def __init__(self, scope=()):
        super().__init__(scope)
        self.errors = StreamChannel()
    
    def init(self):
        return {"errors": self.errors}
    
    def process(self, event):
        data = event["params"]["data"]
        
        # 检查各种错误
        if isinstance(data, dict):
            if data.get("event") == "message-error":
                self.errors.push({"type": "llm_error", "error": data.get("error")})
            elif data.get("event") == "tool-error":
                self.errors.push({"type": "tool_error", "error": data.get("error")})
        
        return True

# 使用
for error in stream.extensions["errors"]:
    log_error(error)
```

## 注册转换器

### 方式1: 调用时注册 (推荐用于实验)

```python
stream = graph.stream_events(
    input_data,
    version="v3",
    transformers=[ProgressTransformer, TokenStatsTransformer]
)
```

### 方式2: 编译时注册 (推荐用于生产)

```python
graph = builder.compile(
    transformers=[ProgressTransformer, TokenStatsTransformer]
)

# 之后每次调用都会使用这些转换器
stream = graph.stream_events(input_data, version="v3")
```

## 常见问题

### Q1: 为什么传递类而不是实例?

```python
# ❌ 错误
transformers=[ProgressTransformer()]

# ✅ 正确
transformers=[ProgressTransformer]
```

**原因**: LangGraph 需要为每个流创建独立的实例,以避免状态共享问题。

### Q2: 如何传递参数给转换器?

使用工厂函数:

```python
transformers=[lambda scope: ProgressTransformer(scope, custom_arg="value")]
```

### Q3: 自定义事件没有被捕获?

检查:
1. 是否声明了 `required_stream_modes = ("custom",)`
2. 是否注册了转换器
3. 节点是否使用 `get_stream_writer()` 发送事件

### Q4: 如何访问自定义投影?

```python
# 通过 stream.extensions 访问
for item in stream.extensions["projection_name"]:
    process(item)
```

## 最佳实践

1. **使用 TypedDict 定义事件类型**
   ```python
   class ProgressEvent(TypedDict):
       step: str
       percent: int
       message: str
   
   self.progress = StreamChannel[ProgressEvent]("progress")
   ```

2. **命名通道 vs 匿名通道**
   - 需要在主事件流中看到 → 命名通道
   - 仅作为侧通道 → 匿名通道

3. **声明所有需要的通道**
   ```python
   required_stream_modes = ("custom", "messages", "tools")
   ```

4. **返回 True 保留原始事件**
   ```python
   def process(self, event):
       # 处理事件...
       return True  # 保留原始事件
   ```

5. **在 finalize 中清理资源**
   ```python
   def finalize(self):
       self.channel.close()
   ```

## 参考资源

- [官方文档](https://docs.langchain.com/oss/python/langgraph/event-streaming)
- [示例代码](./examples9_event_streaming.py) - 场景6
- [Event Streaming 指南](./EVENT_STREAMING_GUIDE.md)
