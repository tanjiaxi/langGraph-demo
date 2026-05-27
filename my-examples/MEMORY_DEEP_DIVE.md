# Memory 深度解析

回答你的三个核心问题

---

## 问题 1：Checkpointer 怎么使用？

### 基础用法

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

# 方式 1：内存存储（测试用）
memory = MemorySaver()
app = graph.compile(checkpointer=memory)

# 方式 2：SQLite 存储（生产用）
import sqlite3
conn = sqlite3.connect("chat.db", check_same_thread=False)
memory = SqliteSaver(conn)
app = graph.compile(checkpointer=memory)

# 使用时指定 thread_id
config = {"configurable": {"thread_id": "user_123"}}
result = app.invoke(input_data, config)
```

### Checkpointer 做了什么？

```
执行流程：
--------
1. 用户调用 app.invoke(input, config)
2. 图开始执行节点
3. 每个节点执行后，Checkpointer 自动保存 State
4. 保存格式：{thread_id: [checkpoint1, checkpoint2, ...]}
5. 下次调用时，自动加载最新 checkpoint
```

### 类比理解

**Git**
```bash
git add .
git commit -m "checkpoint 1"  # 自动保存
git commit -m "checkpoint 2"  # 自动保存
git log  # 查看所有 commit
git checkout <commit-id>  # 恢复到某个 commit
```

**LangGraph**
```python
app.invoke(input1, config)  # 自动保存 checkpoint 1
app.invoke(input2, config)  # 自动保存 checkpoint 2
app.get_state_history(config)  # 查看所有 checkpoint
app.invoke(input3, checkpoint_config)  # 从某个 checkpoint 继续
```

---

## 问题 2：怎么恢复到任意时刻点？

### 步骤 1：获取所有 Checkpoint

```python
config = {"configurable": {"thread_id": "user_123"}}

# 获取历史
history = list(app.get_state_history(config))

# 查看所有 checkpoint
for i, checkpoint in enumerate(history):
    print(f"Checkpoint {i}:")
    print(f"  State: {checkpoint.values}")
    print(f"  Config ID: {checkpoint.config['configurable']['checkpoint_id']}")
```

### 步骤 2：选择目标 Checkpoint

```python
# 方式 1：按索引选择
target_checkpoint = history[2]  # 第 3 个 checkpoint（倒数第 3 个）

# 方式 2：按条件选择
for checkpoint in history:
    if checkpoint.values.get("turn") == 5:
        target_checkpoint = checkpoint
        break

# 方式 3：回到上一步
previous_checkpoint = history[1]  # 倒数第 2 个
```

### 步骤 3：从该 Checkpoint 继续

```python
# 使用目标 checkpoint 的 config
target_config = target_checkpoint.config

# 从该点继续执行
result = app.invoke(new_input, config=target_config)
```

### 完整示例

```python
# 创建 3 轮对话
config = {"configurable": {"thread_id": "demo"}}

app.invoke({"messages": [HumanMessage("第 1 轮")]}, config)
app.invoke({"messages": [HumanMessage("第 2 轮")]}, config)
app.invoke({"messages": [HumanMessage("第 3 轮")]}, config)

# 获取历史
history = list(app.get_state_history(config))
print(f"共有 {len(history)} 个 checkpoint")

# 回到第 2 轮
second_round = history[2]  # 倒数第 3 个
print(f"回到: {second_round.values}")

# 从第 2 轮重新开始
result = app.invoke(
    {"messages": [HumanMessage("重新提问")]},
    config=second_round.config
)
```

### 时间线图解

```
时间线：
-------
Checkpoint 0: {"turn": 1, "messages": [msg1, msg2]}
    ↓
Checkpoint 1: {"turn": 2, "messages": [msg1, msg2, msg3, msg4]}
    ↓
Checkpoint 2: {"turn": 3, "messages": [msg1, msg2, msg3, msg4, msg5, msg6]}
    ↓
当前状态

时间旅行：
---------
从 Checkpoint 1 继续 → 创建新分支
    ↓
Checkpoint 1': {"turn": 2, "messages": [msg1, msg2, msg3, msg4, new_msg]}
```

---

## 问题 3：应用场景是什么？

### 场景 1：用户撤销操作

**问题**：用户说错话，想撤回

**解决方案**：
```python
# 用户发送消息
result = app.invoke({"messages": [HumanMessage("错误的消息")]}, config)

# 用户想撤销
history = list(app.get_state_history(config))
previous_state = history[1]  # 回到上一步

# 重新发送
result = app.invoke(
    {"messages": [HumanMessage("正确的消息")]},
    config=previous_state.config
)
```

### 场景 2：A/B 测试

**问题**：测试不同的对话策略

**解决方案**：
```python
# 创建初始对话
config = {"configurable": {"thread_id": "ab_test"}}
result = app.invoke(initial_input, config)

# 获取初始 checkpoint
history = list(app.get_state_history(config))
initial_checkpoint = history[0]

# 策略 A
result_a = app.invoke(strategy_a_input, initial_checkpoint.config)

# 策略 B（从同一起点）
result_b = app.invoke(strategy_b_input, initial_checkpoint.config)

# 比较结果
print(f"策略 A 结果: {result_a}")
print(f"策略 B 结果: {result_b}")
```

### 场景 3：断点续传

**问题**：长时间任务中断，需要恢复

**解决方案**：
```python
# 任务执行中（自动保存）
app = graph.compile(checkpointer=SqliteSaver(conn))
result = app.invoke(task_input, config)

# 程序崩溃...

# 重启后恢复
app = graph.compile(checkpointer=SqliteSaver(conn))
state = app.get_state(config)  # 加载最新状态

if state.next:  # 如果有未完成的节点
    result = app.invoke(None, config)  # 继续执行
```

### 场景 4：调试和错误恢复

**问题**：某个节点出错，想回到出错前

**解决方案**：
```python
history = list(app.get_state_history(config))

# 找到出错前的 checkpoint
for checkpoint in history:
    if not checkpoint.values.get("error"):
        print(f"找到正常状态: {checkpoint.values}")
        
        # 修复代码后，从这里重新执行
        result = app.invoke(None, checkpoint.config)
        break
```

### 场景 5：客服会话恢复

**问题**：客服断线，需要恢复对话

**解决方案**：
```python
# 客服在线时
config = {"configurable": {"thread_id": f"customer_{customer_id}"}}
result = app.invoke(customer_message, config)

# 客服断线...

# 客服重新连接
state = app.get_state(config)  # 自动加载最新状态
print(f"恢复对话，当前消息数: {len(state.values['messages'])}")

# 继续对话
result = app.invoke(new_message, config)
```

### 场景 6：多路径探索

**问题**：从某个点尝试不同的决策

**解决方案**：
```python
# 执行到决策点
result = app.invoke(input_to_decision_point, config)

# 保存决策点
history = list(app.get_state_history(config))
decision_point = history[0]

# 路径 1：选择 A
result_1 = app.invoke({"choice": "A"}, decision_point.config)

# 路径 2：选择 B（从同一决策点）
result_2 = app.invoke({"choice": "B"}, decision_point.config)

# 路径 3：选择 C
result_3 = app.invoke({"choice": "C"}, decision_point.config)
```

---

## 问题 4：State 所有消息都发给 LLM 吗？

### 答案：不一定！取决于你的实现

### 默认行为（全部发送）

```python
def chat_node(state: State):
    # ⚠️ 发送所有消息
    response = llm.invoke(state["messages"])
    return {"messages": [response]}
```

**问题**：
- 消息越来越多
- Token 消耗大
- 可能超过上下文窗口

### 推荐做法（只发送最近 N 条）

```python
def smart_chat_node(state: State):
    # ✅ 只发送最近 10 条
    recent_messages = state["messages"][-10:]
    response = llm.invoke(recent_messages)
    return {"messages": [response]}
```

### 高级做法（摘要 + 最近）

```python
def advanced_chat_node(state: State):
    messages_to_send = []
    
    # 1. 如果有历史摘要，添加
    if state.get("summary"):
        messages_to_send.append(
            SystemMessage(content=f"历史摘要：{state['summary']}")
        )
    
    # 2. 添加最近 10 条
    messages_to_send.extend(state["messages"][-10:])
    
    # 3. 发送
    response = llm.invoke(messages_to_send)
    return {"messages": [response]}
```

### 对比表

| 方式 | State 中的消息 | 发送给 LLM 的消息 | Token 消耗 |
|------|--------------|-----------------|-----------|
| 全部发送 | 100 条 | 100 条 | 高 |
| 最近 N 条 | 100 条 | 10 条 | 低 |
| 摘要 + 最近 | 100 条 | 1 条摘要 + 10 条 | 中 |

### 关键点

1. **State 中的消息会累积**
   ```python
   messages: Annotated[List[BaseMessage], operator.add]
   # 每次都会追加，不会替换
   ```

2. **但你可以控制发送给 LLM 的消息**
   ```python
   # State 有 100 条
   len(state["messages"])  # 100
   
   # 只发送 10 条
   llm.invoke(state["messages"][-10:])
   ```

3. **Checkpointer 保存的是完整 State**
   ```python
   # Checkpoint 保存所有 100 条消息
   checkpoint.values["messages"]  # 100 条
   
   # 但发送给 LLM 时可以选择
   ```

---

## 总结

### Checkpointer 的三个核心功能

1. **自动保存**：每个节点执行后自动保存 State
2. **版本控制**：每个 checkpoint 有唯一 ID
3. **时间旅行**：可以恢复到任意 checkpoint

### 使用流程

```python
# 1. 创建 Checkpointer
memory = SqliteSaver(conn)

# 2. 编译图
app = graph.compile(checkpointer=memory)

# 3. 执行（自动保存）
result = app.invoke(input, config)

# 4. 查看历史
history = list(app.get_state_history(config))

# 5. 时间旅行
target = history[2]
result = app.invoke(new_input, target.config)
```

### 消息管理

```python
# State 中累积所有消息
state["messages"]  # [msg1, msg2, ..., msg100]

# 但只发送最近 N 条给 LLM
llm.invoke(state["messages"][-10:])  # 只发送 10 条
```

### 最佳实践

1. ✅ 生产环境使用 SqliteSaver
2. ✅ 使用有意义的 thread_id
3. ✅ 定期清理旧 checkpoint
4. ✅ 监控消息数量
5. ✅ 只发送必要的消息给 LLM

---

## 相关文件

- `examples7_advanced_memory.py` - Checkpointer 和时间旅行示例
- `MESSAGE_MANAGEMENT_GUIDE.md` - 消息管理完全指南
- `examples5_memory.py` - 基础 Memory 示例
