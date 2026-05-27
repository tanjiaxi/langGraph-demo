# 消息管理完全指南

## 核心问题：State 中所有消息都发给 LLM 吗？

**答案：取决于你的实现！**

---

## 1. 默认行为（全部发送）

### Python 代码
```python
class State(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

def chat_node(state: State):
    # ⚠️ 默认：发送所有消息
    response = llm.invoke(state["messages"])
    return {"messages": [response]}
```

### 问题
- ✅ LLM 有完整上下文
- ❌ Token 消耗大
- ❌ 可能超过上下文窗口（如 GPT-4 的 128K）
- ❌ 响应变慢

### 示例
```python
# 第 1 轮
state = {"messages": [HumanMessage("你好")]}
# LLM 收到: ["你好"]

# 第 2 轮
state = {"messages": [
    HumanMessage("你好"),
    AIMessage("你好！"),
    HumanMessage("天气怎么样")
]}
# LLM 收到: ["你好", "你好！", "天气怎么样"]  ← 全部

# 第 100 轮
state = {"messages": [... 200 条消息 ...]}
# LLM 收到: 全部 200 条  ← 可能超限！
```

---

## 2. 策略 1：只发送最近 N 条

### Python 代码
```python
def smart_chat_node(state: State):
    # ✅ 只发送最近 10 条
    recent_messages = state["messages"][-10:]
    response = llm.invoke(recent_messages)
    return {"messages": [response]}
```

### JavaScript 等价
```javascript
function smartChatNode(state) {
    // 只取最后 10 条
    const recentMessages = state.messages.slice(-10);
    const response = await llm.invoke(recentMessages);
    return { messages: [response] };
}
```

### Go 等价
```go
func smartChatNode(state State) State {
    // 只取最后 10 条
    start := len(state.Messages) - 10
    if start < 0 {
        start = 0
    }
    recentMessages := state.Messages[start:]
    
    response := llm.Invoke(recentMessages)
    return State{Messages: append(state.Messages, response)}
}
```

### 优缺点
- ✅ 控制 token 消耗
- ✅ 不会超过上下文窗口
- ❌ 可能丢失重要上下文
- ❌ LLM 不记得早期对话

---

## 3. 策略 2：系统消息 + 最近 N 条

### Python 代码
```python
def chat_with_system(state: State):
    # 系统消息（始终包含）
    system_msg = SystemMessage(content="你是一个有帮助的助手")
    
    # 最近 10 条用户消息
    recent_messages = state["messages"][-10:]
    
    # 组合
    messages_to_send = [system_msg] + recent_messages
    
    response = llm.invoke(messages_to_send)
    return {"messages": [response]}
```

### 示例
```python
# State 中有 50 条消息
state["messages"] = [msg1, msg2, ..., msg50]

# 发送给 LLM:
[
    SystemMessage("你是助手"),  # 系统消息
    msg41, msg42, ..., msg50    # 最近 10 条
]
```

---

## 4. 策略 3：智能摘要（推荐）

### Python 代码
```python
class SmartState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    summary: str  # 历史摘要

def summarize_node(state: SmartState):
    """摘要旧消息"""
    if len(state["messages"]) > 20:
        # 摘要前 10 条
        old_messages = state["messages"][:10]
        summary_prompt = f"总结以下对话：{old_messages}"
        summary = llm.invoke([HumanMessage(content=summary_prompt)])
        
        return {"summary": summary.content}
    return {}

def chat_node(state: SmartState):
    """使用摘要 + 最近消息"""
    messages_to_send = []
    
    # 1. 添加摘要（如果有）
    if state.get("summary"):
        messages_to_send.append(
            SystemMessage(content=f"历史摘要：{state['summary']}")
        )
    
    # 2. 添加最近 10 条
    messages_to_send.extend(state["messages"][-10:])
    
    response = llm.invoke(messages_to_send)
    return {"messages": [response]}
```

### 流程图
```
消息历史: [msg1, msg2, ..., msg50]
           ↓
    [msg1...msg40] → 摘要 → "用户询问了天气、新闻等"
           ↓
    [msg41...msg50] → 保留原始消息
           ↓
发送给 LLM:
    [摘要, msg41, msg42, ..., msg50]
```

### 优缺点
- ✅ 保留关键信息
- ✅ 控制 token 消耗
- ✅ LLM 有完整上下文感知
- ❌ 需要额外的摘要调用
- ❌ 摘要可能丢失细节

---

## 5. 策略 4：滑动窗口 + 关键消息

### Python 代码
```python
def sliding_window_chat(state: State):
    messages = state["messages"]
    
    # 1. 提取关键消息（如用户信息）
    key_messages = [
        msg for msg in messages
        if "我叫" in msg.content or "我是" in msg.content
    ]
    
    # 2. 最近 10 条
    recent_messages = messages[-10:]
    
    # 3. 组合（去重）
    messages_to_send = key_messages + [
        msg for msg in recent_messages
        if msg not in key_messages
    ]
    
    response = llm.invoke(messages_to_send)
    return {"messages": [response]}
```

### 示例
```python
# State 中的消息
messages = [
    HumanMessage("我叫 Alice"),      # 关键消息
    AIMessage("你好 Alice"),
    HumanMessage("我喜欢编程"),
    # ... 40 条消息 ...
    HumanMessage("最近的问题")       # 最近消息
]

# 发送给 LLM:
[
    HumanMessage("我叫 Alice"),      # 保留关键信息
    # ... 最近 10 条 ...
    HumanMessage("最近的问题")
]
```

---

## 6. 策略对比表

| 策略 | Token 消耗 | 上下文完整性 | 实现复杂度 | 适用场景 |
|------|-----------|-------------|-----------|---------|
| **全部发送** | 高 | 完整 | 简单 | 短对话 |
| **最近 N 条** | 低 | 部分 | 简单 | 一般对话 |
| **系统 + 最近** | 低 | 部分 | 简单 | 需要系统提示 |
| **智能摘要** | 中 | 较完整 | 复杂 | 长对话 |
| **滑动窗口 + 关键** | 中 | 较完整 | 中等 | 需要记住关键信息 |

---

## 7. 实际应用示例

### 场景 1：客服系统（推荐：智能摘要）

```python
class CustomerState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    customer_info: str  # 客户信息（始终保留）
    issue_summary: str  # 问题摘要

def customer_service_node(state: CustomerState):
    messages_to_send = [
        SystemMessage(content=f"客户信息：{state['customer_info']}"),
        SystemMessage(content=f"问题摘要：{state['issue_summary']}"),
    ]
    messages_to_send.extend(state["messages"][-5:])  # 最近 5 条
    
    response = llm.invoke(messages_to_send)
    return {"messages": [response]}
```

### 场景 2：教育助手（推荐：关键消息）

```python
def tutor_node(state: State):
    # 保留所有问题和答案，但摘要解释过程
    qa_messages = [
        msg for msg in state["messages"]
        if "问题" in msg.content or "答案" in msg.content
    ]
    recent_messages = state["messages"][-10:]
    
    messages_to_send = qa_messages + recent_messages
    response = llm.invoke(messages_to_send)
    return {"messages": [response]}
```

### 场景 3：代码助手（推荐：最近 N 条）

```python
def code_assistant_node(state: State):
    # 代码对话通常是独立的，只需最近上下文
    recent_messages = state["messages"][-5:]
    response = llm.invoke(recent_messages)
    return {"messages": [response]}
```

---

## 8. Token 计算

### 估算公式
```
1 个英文单词 ≈ 1.3 tokens
1 个中文字符 ≈ 2-3 tokens
```

### 示例
```python
# 一条消息
msg = "你好，今天天气怎么样？"  # 约 24 tokens

# 10 轮对话（20 条消息）
total_tokens = 20 * 24 = 480 tokens

# 100 轮对话（200 条消息）
total_tokens = 200 * 24 = 4800 tokens  # 可能超限！
```

### 模型限制
| 模型 | 上下文窗口 | 建议最大消息数 |
|------|-----------|--------------|
| GPT-3.5 | 16K tokens | ~50 条 |
| GPT-4 | 128K tokens | ~400 条 |
| DeepSeek | 32K tokens | ~100 条 |

---

## 9. 最佳实践

### ✅ 推荐做法

1. **监控消息数量**
```python
if len(state["messages"]) > 50:
    print("⚠️ 消息过多，考虑清理")
```

2. **动态调整策略**
```python
def adaptive_chat(state: State):
    msg_count = len(state["messages"])
    
    if msg_count < 10:
        messages = state["messages"]  # 全部发送
    elif msg_count < 50:
        messages = state["messages"][-20:]  # 最近 20 条
    else:
        # 摘要 + 最近 10 条
        messages = [summarize(state["messages"][:-10])] + state["messages"][-10:]
    
    return llm.invoke(messages)
```

3. **记录 Token 使用**
```python
def chat_with_logging(state: State):
    messages = state["messages"][-10:]
    
    # 估算 token
    token_count = sum(len(msg.content.split()) * 1.3 for msg in messages)
    print(f"📊 预计使用 {token_count:.0f} tokens")
    
    response = llm.invoke(messages)
    return {"messages": [response]}
```

### ❌ 避免的做法

1. **无限累积消息**
```python
# ❌ 不好
def bad_chat(state: State):
    # 永远发送所有消息
    return llm.invoke(state["messages"])
```

2. **丢失关键信息**
```python
# ❌ 不好
def bad_chat(state: State):
    # 只发送最后 1 条，丢失上下文
    return llm.invoke([state["messages"][-1]])
```

3. **不检查消息数量**
```python
# ❌ 不好
def bad_chat(state: State):
    # 没有检查，可能超限
    return llm.invoke(state["messages"])
```

---

## 10. 调试技巧

### 打印发送的消息
```python
def debug_chat(state: State):
    messages = state["messages"][-10:]
    
    print(f"\n📤 发送给 LLM 的消息（共 {len(messages)} 条）:")
    for i, msg in enumerate(messages, 1):
        role = "User" if isinstance(msg, HumanMessage) else "AI"
        print(f"  {i}. {role}: {msg.content[:50]}...")
    
    response = llm.invoke(messages)
    return {"messages": [response]}
```

### 监控 Token 使用
```python
from langchain.callbacks import get_openai_callback

def monitored_chat(state: State):
    with get_openai_callback() as cb:
        response = llm.invoke(state["messages"][-10:])
        print(f"📊 Token 使用: {cb.total_tokens}")
        print(f"💰 成本: ${cb.total_cost:.4f}")
    
    return {"messages": [response]}
```

---

## 总结

**核心原则**：
1. State 中的消息会累积
2. 但你可以控制发送给 LLM 的消息
3. 根据场景选择合适的策略
4. 监控和优化 Token 使用

**推荐策略**：
- 短对话（<10 轮）：全部发送
- 中等对话（10-50 轮）：最近 N 条
- 长对话（>50 轮）：智能摘要 + 最近 N 条
