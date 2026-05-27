# LangGraph 核心概念总结

适合 JavaScript/Go 开发者

---

## 📦 1. State（状态管理）

### 核心概念
State 是在节点间传递和累积的数据结构。

### 对比三种语言

| 特性 | Python (LangGraph) | JavaScript | Go |
|------|-------------------|------------|-----|
| **定义** | `TypedDict` | `interface` | `struct` |
| **更新** | 返回部分字段，自动合并 | `{...state, ...update}` | 手动修改字段 |
| **累积** | `Annotated[List, operator.add]` | 手动 push | 手动 append |

### 示例对比

**Python**
```python
class State(TypedDict):
    messages: Annotated[List[str], operator.add]
    counter: int

def node(state: State):
    return {"counter": state["counter"] + 1}
```

**JavaScript**
```javascript
interface State {
    messages: string[];
    counter: number;
}

function node(state: State): State {
    return {
        ...state,
        counter: state.counter + 1
    };
}
```

**Go**
```go
type State struct {
    Messages []string
    Counter  int
}

func node(state *State) {
    state.Counter++
}
```

### 关键特性

1. **自动合并**：节点只返回需要更新的字段
2. **类型安全**：使用 TypedDict 定义结构
3. **累积策略**：使用 Annotated 指定如何合并列表/数字

---

## 💾 2. Memory（持久化存储）

### 核心概念
Memory 保存每一步的状态快照，支持恢复和多会话管理。

### 对比三种语言

| 特性 | Python (LangGraph) | JavaScript | Go |
|------|-------------------|------------|-----|
| **存储** | Checkpointer | localStorage / DB | 文件 / DB |
| **会话** | thread_id | sessionId | SessionID |
| **恢复** | 自动 | 手动加载 | 手动加载 |

### 示例对比

**Python**
```python
from langgraph.checkpoint.sqlite import SqliteSaver

memory = SqliteSaver(conn)
app = graph.compile(checkpointer=memory)

result = app.invoke(
    input_data,
    config={"configurable": {"thread_id": "user_123"}}
)
```

**JavaScript**
```javascript
// localStorage
const threadId = 'user_123';
const history = JSON.parse(
    localStorage.getItem(`chat_${threadId}`) || '[]'
);
history.push(newMessage);
localStorage.setItem(`chat_${threadId}`, JSON.stringify(history));

// 或数据库
await db.insert('checkpoints', {
    thread_id: threadId,
    state: JSON.stringify(state)
});
```

**Go**
```go
// 文件存储
func saveCheckpoint(threadID string, state State) error {
    data, _ := json.Marshal(state)
    return os.WriteFile(
        fmt.Sprintf("checkpoints/%s.json", threadID),
        data, 0644,
    )
}

// 数据库
db.Exec(
    "INSERT INTO checkpoints (thread_id, state) VALUES (?, ?)",
    threadID, stateJSON,
)
```

### 存储后端

| 后端 | 用途 | 持久化 | 性能 |
|------|------|--------|------|
| MemorySaver | 测试 | ❌ | ⚡⚡⚡ |
| SqliteSaver | 生产（单机） | ✅ | ⚡⚡ |
| PostgresSaver | 生产（分布式） | ✅ | ⚡⚡ |
| RedisSaver | 高性能 | ✅ | ⚡⚡⚡ |

---

## ⏸️ 3. Human-in-the-Loop（人工介入）

### 核心概念
在指定节点前暂停执行，等待人工审核/修改后继续。

### 对比三种语言

| 特性 | Python (LangGraph) | JavaScript | Go |
|------|-------------------|------------|-----|
| **暂停** | `interrupt_before` | `await` + 状态保存 | `channel` 阻塞 |
| **继续** | `invoke(None, config)` | 调用继续函数 | 发送到 channel |
| **修改** | `update_state()` | 修改保存的状态 | 修改 struct |

### 示例对比

**Python**
```python
app = graph.compile(
    checkpointer=memory,
    interrupt_before=["send_email"]
)

# 第一次：执行到暂停点
result = app.invoke(input, config)

# 人工审核...

# 继续执行
result = app.invoke(None, config)

# 或修改后继续
app.update_state(config, {"content": "modified"})
result = app.invoke(None, config)
```

**JavaScript**
```javascript
async function workflow(input, sessionId) {
    const draft = await step1(input);
    
    // 保存状态，等待审批
    await saveState(sessionId, { draft, step: 'awaiting_approval' });
    return { status: 'paused', draft };
}

// 审批后继续
async function continueWorkflow(sessionId, approved) {
    const state = await loadState(sessionId);
    if (approved) {
        return await step2(state.draft);
    }
}
```

**Go**
```go
type Workflow struct {
    ApprovalCh chan bool
}

func (w *Workflow) Run() {
    draft := w.step1()
    
    // 等待审批
    approved := <-w.ApprovalCh
    
    if approved {
        w.step2(draft)
    }
}

// 另一个 goroutine 处理审批
go func() {
    approval := getUserApproval()
    workflow.ApprovalCh <- approval
}()
```

### 使用场景

1. **敏感操作审批**
   - 删除数据
   - 发送邮件
   - 金融交易

2. **内容审核**
   - AI 生成内容
   - 用户提交内容

3. **多级审批**
   - 经理 → 总监 → CEO

4. **调试和测试**
   - 逐步执行
   - 检查中间状态

---

## 🔄 4. 三个概念的关系

```
┌─────────────────────────────────────────┐
│           Human-in-the-Loop             │
│  (在关键节点暂停，等待人工介入)          │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│              Memory                      │
│  (保存每一步的 State 快照)               │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│              State                       │
│  (在节点间传递和累积的数据)              │
└─────────────────────────────────────────┘
```

### 工作流程

1. **State** 在节点间流动和更新
2. **Memory** 保存每一步的 State
3. **Human-in-the-Loop** 在需要时暂停，等待人工操作

---

## 📊 5. 实际应用场景

### 场景 1：客服系统

```python
# State: 对话历史
class CustomerState(TypedDict):
    messages: Annotated[List[Message], operator.add]
    customer_id: str

# Memory: 多用户会话
config = {"configurable": {"thread_id": f"customer_{id}"}}

# Human-in-the-Loop: 复杂问题转人工
interrupt_before=["escalate_to_human"]
```

### 场景 2：内容审核

```python
# State: 内容和审核状态
class ContentState(TypedDict):
    draft: str
    reviewed: bool
    published: bool

# Memory: 保存草稿
checkpointer=SqliteSaver(conn)

# Human-in-the-Loop: 发布前审核
interrupt_before=["publish"]
```

### 场景 3：自动化工作流

```python
# State: 任务进度
class TaskState(TypedDict):
    steps_completed: List[str]
    current_step: str

# Memory: 断点续传
checkpointer=memory

# Human-in-the-Loop: 关键步骤确认
interrupt_before=["deploy_to_production"]
```

---

## 🎯 6. 最佳实践总结

### State
- ✅ 使用 TypedDict 定义类型
- ✅ 列表/数字累积用 Annotated
- ✅ 节点只返回需要更新的字段
- ❌ 避免嵌套过深的结构

### Memory
- ✅ 开发用 MemorySaver，生产用 SqliteSaver
- ✅ 使用有意义的 thread_id
- ✅ 定期清理旧数据
- ❌ 不要在内存中存储敏感信息

### Human-in-the-Loop
- ✅ 在敏感操作前暂停
- ✅ 提供清晰的审核信息
- ✅ 支持修改和重试
- ❌ 不要无限期等待审批

---

## 📚 7. 学习路径

1. **第一步**：理解 State（examples4_state.py）
   - 基础字典操作
   - 合并机制
   - Annotated 累积

2. **第二步**：理解 Memory（examples5_memory.py）
   - Checkpointer 概念
   - 多会话管理
   - 持久化存储

3. **第三步**：理解 Human-in-the-Loop（examples6_human_loop.py）
   - interrupt_before
   - 修改状态
   - 多级审批

4. **第四步**：综合应用
   - 结合三个概念
   - 构建实际系统

---

## 🔗 8. 相关文件

- `examples4_state.py` - State 深度示例
- `examples5_memory.py` - Memory 持久化示例
- `examples6_human_loop.py` - Human-in-the-Loop 示例
- `examples3_conditional.py` - 条件边示例
- `examples2.py` - 基础 LLM 调用

---

## 💡 9. 快速参考

### 创建带 Memory 的应用
```python
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
app = graph.compile(checkpointer=memory)
```

### 使用 thread_id
```python
config = {"configurable": {"thread_id": "user_123"}}
result = app.invoke(input, config)
```

### 添加 Human-in-the-Loop
```python
app = graph.compile(
    checkpointer=memory,
    interrupt_before=["sensitive_node"]
)
```

### 继续执行
```python
result = app.invoke(None, config)
```

### 修改状态后继续
```python
app.update_state(config, {"field": "new_value"})
result = app.invoke(None, config)
```

---

**祝学习愉快！🚀**
