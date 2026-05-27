# Streaming 快速参考指南

## 核心概念

**Streaming** = 实时获取图执行的中间结果，不用等待全部完成

---

## 基础用法

### invoke vs stream

```python
# ❌ 传统方式：等待全部完成
result = graph.invoke(input_data)
print(result)  # 一次性输出

# ✅ 流式输出：实时看到进度
for chunk in graph.stream(input_data, stream_mode="values", version="v2"):
    print(chunk["data"])  # 逐步输出
```

---

## Stream Modes（流式模式）

### 1. values - 完整状态

**用途**：每步后的完整 state

```python
for chunk in graph.stream(input, stream_mode="values", version="v2"):
    print(chunk["data"])  # 完整的 state
```

**输出示例**：
```
{'counter': 0, 'message': '开始'}
{'counter': 1, 'message': 'Step 1 完成'}
{'counter': 2, 'message': 'Step 2 完成'}
```

### 2. updates - 节点更新

**用途**：只看每个节点返回的更新

```python
for chunk in graph.stream(input, stream_mode="updates", version="v2"):
    node_name = list(chunk['data'].keys())[0]
    update = chunk['data'][node_name]
    print(f"节点 {node_name}: {update}")
```

**输出示例**：
```
节点 step1: {'counter': 1}
节点 step2: {'counter': 2}
```

### 3. messages - 消息流

**用途**：聊天应用，只输出消息

```python
for chunk in graph.stream(input, stream_mode="messages", version="v2"):
    message = chunk['data'][0]
    print(message.content)
```

**输出示例**：
```
User: 你好
AI: 你好！有什么可以帮你的吗？
```

### 4. custom - 自定义事件

**用途**：发送自定义进度、状态

```python
# 在节点中发送自定义事件
from langgraph.config import get_stream_writer

def my_node(state):
    writer = get_stream_writer()
    writer({"status": "正在处理", "progress": 50})
    # ... 处理逻辑
    writer({"status": "完成", "progress": 100})
    return {"result": "done"}

# 接收自定义事件
for chunk in graph.stream(input, stream_mode="custom", version="v2"):
    print(chunk['data'])  # {"status": "...", "progress": ...}
```

---

## 多模式组合

```python
for chunk in graph.stream(
    input,
    stream_mode=["values", "updates", "custom"],
    version="v2"
):
    if chunk["type"] == "values":
        print(f"状态: {chunk['data']}")
    elif chunk["type"] == "updates":
        print(f"更新: {chunk['data']}")
    elif chunk["type"] == "custom":
        print(f"进度: {chunk['data']}")
```

---

## 实际应用场景

### 场景 1：打字机效果（Token Streaming）

```python
def streaming_chat_node(state):
    writer = get_stream_writer()
    
    full_response = ""
    for chunk in llm.stream(state["messages"]):
        if chunk.content:
            full_response += chunk.content
            writer({"token": chunk.content})  # 发送每个 token
    
    return {"messages": [AIMessage(content=full_response)]}

# 接收
for chunk in graph.stream(input, stream_mode="custom", version="v2"):
    if "token" in chunk['data']:
        print(chunk['data']['token'], end="", flush=True)
```

### 场景 2：进度追踪

```python
def long_task_node(state):
    writer = get_stream_writer()
    
    writer({"status": "开始", "progress": 0})
    # 步骤 1
    do_step1()
    writer({"status": "步骤 1 完成", "progress": 33})
    
    # 步骤 2
    do_step2()
    writer({"status": "步骤 2 完成", "progress": 66})
    
    # 步骤 3
    do_step3()
    writer({"status": "全部完成", "progress": 100})
    
    return {"result": "done"}
```

### 场景 3：多步骤工作流

```python
# 规划 → 执行 → 总结
for chunk in workflow_app.stream(
    input,
    stream_mode=["updates", "custom"],
    version="v2"
):
    if chunk["type"] == "updates":
        node = list(chunk['data'].keys())[0]
        print(f"✅ {node} 完成")
    elif chunk["type"] == "custom":
        print(f"📊 {chunk['data']['status']}")
```

---

## 跨语言对比

### Python
```python
for chunk in graph.stream(input, stream_mode="values", version="v2"):
    print(chunk["data"])
```

### JavaScript
```javascript
// Server-Sent Events
const eventSource = new EventSource('/api/stream');
eventSource.onmessage = (event) => {
    const chunk = JSON.parse(event.data);
    console.log(chunk);
};

// Async iterator
for await (const chunk of graph.stream(input)) {
    console.log(chunk);
}
```

### Go
```go
// Channel
ch := graph.Stream(input)
for chunk := range ch {
    fmt.Printf("Chunk: %v\n", chunk)
}

// Callback
graph.Stream(input, func(chunk Chunk) {
    fmt.Printf("Chunk: %v\n", chunk)
})
```

---

## Chunk 结构（v2 格式）

```python
{
    "type": "values" | "updates" | "messages" | "custom",
    "ns": (),           # namespace（子图用）
    "data": ...         # 实际数据
}
```

### 类型安全

```python
from langgraph.types import StreamPart

for chunk in graph.stream(input, stream_mode="values", version="v2"):
    # chunk 的类型是 StreamPart
    if chunk["type"] == "values":
        # chunk["data"] 自动推断为 State 类型
        state = chunk["data"]
```

---

## 最佳实践

### ✅ 推荐

1. **使用 version="v2"**
   ```python
   graph.stream(input, stream_mode="values", version="v2")
   ```

2. **发送有意义的进度**
   ```python
   writer({"status": "正在搜索", "progress": 30, "found": 5})
   ```

3. **处理长时间操作**
   ```python
   def long_task(state):
       writer = get_stream_writer()
       for i in range(10):
           do_work()
           writer({"progress": (i+1) * 10})
   ```

4. **错误处理**
   ```python
   try:
       for chunk in graph.stream(input):
           print(chunk)
   except Exception as e:
       print(f"错误: {e}")
   ```

### ❌ 避免

1. **过于频繁的更新**
   ```python
   # ❌ 不好
   for i in range(10000):
       writer({"progress": i})  # 太频繁
   
   # ✅ 好
   for i in range(10000):
       if i % 100 == 0:
           writer({"progress": i})
   ```

2. **无意义的消息**
   ```python
   # ❌ 不好
   writer({"msg": "ok"})
   
   # ✅ 好
   writer({"status": "搜索完成", "found": 10, "time": 2.5})
   ```

3. **忘记 flush（打字机效果）**
   ```python
   # ❌ 不好
   print(token, end="")
   
   # ✅ 好
   print(token, end="", flush=True)
   ```

---

## 性能考虑

### 1. Chunk 大小

```python
# ❌ 太小：网络开销大
for char in text:
    writer({"char": char})

# ✅ 合适：批量发送
buffer = []
for char in text:
    buffer.append(char)
    if len(buffer) >= 10:
        writer({"text": "".join(buffer)})
        buffer = []
```

### 2. 更新频率

```python
# ✅ 控制更新频率
import time

last_update = 0
for item in items:
    process(item)
    now = time.time()
    if now - last_update > 0.5:  # 每 0.5 秒更新一次
        writer({"progress": ...})
        last_update = now
```

---

## 调试技巧

### 1. 打印所有 chunk

```python
for chunk in graph.stream(input, stream_mode="debug", version="v2"):
    print(f"Type: {chunk['type']}")
    print(f"Data: {chunk['data']}")
    print("---")
```

### 2. 记录到文件

```python
with open("stream.log", "w") as f:
    for chunk in graph.stream(input):
        f.write(f"{chunk}\n")
        f.flush()
```

### 3. 使用 LangSmith

```python
import os
os.environ["LANGSMITH_TRACING"] = "true"

# 自动追踪所有 streaming 事件
for chunk in graph.stream(input):
    print(chunk)
```

---

## 常见问题

### Q1: invoke 和 stream 有什么区别？

**A**: 
- `invoke`: 等待全部完成，一次性返回
- `stream`: 实时输出，边执行边返回

### Q2: 什么时候用哪种 stream_mode？

**A**:
- `values`: 需要完整状态
- `updates`: 只关心节点更新
- `messages`: 聊天应用
- `custom`: 自定义进度

### Q3: 如何实现打字机效果？

**A**: 使用 `llm.stream()` + `get_stream_writer()`

### Q4: 可以同时使用多种模式吗？

**A**: 可以！`stream_mode=["values", "updates", "custom"]`

### Q5: version="v2" 有什么好处？

**A**: 
- 统一的输出格式
- 类型安全
- 更好的调试

---

## 完整示例

```python
from langgraph.graph import StateGraph, START, END
from langgraph.config import get_stream_writer
from typing_extensions import TypedDict

class State(TypedDict):
    input: str
    output: str

def process_node(state: State):
    writer = get_stream_writer()
    
    # 发送进度
    writer({"status": "开始处理", "progress": 0})
    
    # 处理逻辑
    result = process(state["input"])
    
    writer({"status": "处理完成", "progress": 100})
    
    return {"output": result}

# 构建图
graph = StateGraph(State)
graph.add_node("process", process_node)
graph.add_edge(START, "process")
graph.add_edge("process", END)
app = graph.compile()

# 流式执行
for chunk in app.stream(
    {"input": "test"},
    stream_mode=["updates", "custom"],
    version="v2"
):
    if chunk["type"] == "updates":
        print(f"✅ 节点完成: {chunk['data']}")
    elif chunk["type"] == "custom":
        print(f"📊 进度: {chunk['data']}")
```

---

## 相关文件

- `examples8_streaming.py` - 完整的 Streaming 示例
- [官方文档](https://docs.langchain.com/oss/python/langgraph/streaming)
