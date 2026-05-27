# LangGraph 学习示例集

适合 JavaScript/Go 开发者快速上手 Python 和 LangGraph

---

## 📚 文件列表

### 基础示例

| 文件 | 主题 | 难度 | 说明 |
|------|------|------|------|
| `examples1.py` | 基础图结构 | ⭐ | 最简单的节点和边 |
| `examples2.py` | LLM 调用 | ⭐⭐ | 集成 DeepSeek 模型 |
| `examples3_conditional.py` | 条件边 | ⭐⭐⭐ | 动态路由和分支 |

### 核心概念（重点！）

| 文件 | 主题 | 难度 | 说明 |
|------|------|------|------|
| `examples4_state.py` | **State 管理** | ⭐⭐⭐ | 状态传递和累积 |
| `examples5_memory.py` | **Memory 存储** | ⭐⭐⭐⭐ | 持久化和多会话 |
| `examples6_human_loop.py` | **Human-in-the-Loop** | ⭐⭐⭐⭐ | 人工介入和审批 |
| `examples7_advanced_memory.py` | **高级 Memory** | ⭐⭐⭐⭐⭐ | Checkpointer 和时间旅行 |
| `examples8_streaming.py` | **Streaming** | ⭐⭐⭐⭐⭐ | 流式输出和实时反馈 |

### 辅助文件

| 文件 | 说明 |
|------|------|
| `chain_explanation.py` | 管道操作符 `\|` 详解 |
| `chain_comparison.py` | 三种语言的链式调用对比 |
| `README_DEEPSEEK.md` | DeepSeek API 配置指南 |
| `CONDITIONAL_EDGES_GUIDE.md` | 条件边完全指南 |
| `CORE_CONCEPTS_SUMMARY.md` | 核心概念总结 |
| `MEMORY_DEEP_DIVE.md` | Memory 深度解析（回答核心问题） |
| `MESSAGE_MANAGEMENT_GUIDE.md` | 消息管理完全指南 |
| `ADVANCED_TOPICS.md` | 高级主题学习指南 |
| `STREAMING_GUIDE.md` | Streaming 快速参考 |

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -U langgraph langchain-openai langchain-core
```

### 2. 配置 API Key

```bash
export DEEPSEEK_API_KEY="sk-your-key-here"
```

或者在代码中设置：
```python
os.environ["DEEPSEEK_API_KEY"] = "sk-..."
```

### 3. 运行示例

```bash
cd /Users/t/ServerProjects/classic/langgraph/examples/my-examples

# 基础示例
python examples1.py

# LLM 调用
python examples2.py

# 条件边
python examples3_conditional.py

# State 管理（重点）
python examples4_state.py

# Memory 存储（重点）
python examples5_memory.py

# Human-in-the-Loop（重点）
python examples6_human_loop.py
```

---

## 📖 学习路径

### 第一阶段：Python 基础（如果不熟悉 Python）

1. 阅读 `examples1.py` 中的注释
2. 对比 JavaScript/Go 语法
3. 理解缩进、字典、类型注解

**关键差异**：
- 没有花括号，用缩进
- 字典 `{"key": value}` vs JS 对象 `{key: value}`
- 类型注解是可选的

### 第二阶段：LangGraph 基础

1. **examples1.py** - 理解节点和边
   - 节点：执行函数
   - 边：连接节点
   - 图：节点 + 边的组合

2. **examples2.py** - 理解 LLM 调用
   - 管道操作符 `|`
   - Prompt 模板
   - 链式调用

3. **examples3_conditional.py** - 理解条件边
   - 路由函数
   - 动态分支
   - 多路选择

### 第三阶段：核心概念（重点！）

4. **examples4_state.py** - 深入理解 State
   - State 是什么？
   - 合并机制
   - Annotated 累积
   - 对话历史管理

5. **examples5_memory.py** - 深入理解 Memory
   - Checkpointer 概念
   - thread_id 和多会话
   - SQLite 持久化
   - 实际应用场景

6. **examples6_human_loop.py** - 深入理解 Human-in-the-Loop
   - interrupt_before
   - 修改状态
   - 多级审批
   - 实际应用场景

### 第四阶段：综合应用

7. 结合三个核心概念构建实际系统
8. 阅读 LangGraph 官方文档
9. 探索更多高级特性

---

## 🎯 核心概念速查

### State（状态管理）

```python
class State(TypedDict):
    messages: Annotated[List[str], operator.add]  # 累积
    counter: int  # 替换

def node(state: State):
    return {"counter": state["counter"] + 1}  # 只返回需要更新的字段
```

**关键点**：
- 节点返回的字典会**合并**到 state
- 使用 `Annotated` 指定累积策略
- 类似 Redux 的 reducer

### Memory（持久化存储）

```python
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
app = graph.compile(checkpointer=memory)

result = app.invoke(
    input_data,
    config={"configurable": {"thread_id": "user_123"}}
)
```

**关键点**：
- 保存每一步的状态快照
- 支持多用户/多会话（thread_id）
- 可以恢复到任意历史状态

### Human-in-the-Loop（人工介入）

```python
app = graph.compile(
    checkpointer=memory,
    interrupt_before=["send_email"]  # 在此节点前暂停
)

# 第一次：执行到暂停点
result = app.invoke(input, config)

# 人工审核...

# 继续执行
result = app.invoke(None, config)
```

**关键点**：
- 在敏感操作前暂停
- 等待人工审核/修改
- 支持修改状态后继续

---

## 🔄 跨语言对比

### State 更新

| Python | JavaScript | Go |
|--------|------------|-----|
| `return {"age": 30}` | `{...state, age: 30}` | `state.Age = 30` |

### Memory 存储

| Python | JavaScript | Go |
|--------|------------|-----|
| `checkpointer=SqliteSaver(conn)` | `localStorage.setItem()` | `json.Marshal() -> file` |

### Human-in-the-Loop

| Python | JavaScript | Go |
|--------|------------|-----|
| `interrupt_before=["node"]` | `await` + 状态保存 | `<-channel` 阻塞 |

---

## 💡 常见问题

### Q1: 为什么用 Python 而不是 JS/Go？

**A**: AI 生态在 Python 最成熟：
- LangChain、LangGraph 都是 Python 优先
- 大部分 AI 库（PyTorch、TensorFlow）都是 Python
- Python 只是接口层，底层是 C++/CUDA

### Q2: `|` 管道操作符是什么？

**A**: 类似 Unix 管道或 JS 的函数组合：
```python
chain = prompt | llm  # 等价于 llm(prompt(input))
```

### Q3: State 和 Memory 有什么区别？

**A**:
- **State**: 当前执行的数据（内存中）
- **Memory**: 保存的历史快照（持久化）

### Q4: thread_id 是什么？

**A**: 会话 ID，类似：
- JS: `sessionId`
- Go: `SessionID`
- 用于区分不同用户/会话

### Q5: 如何调试 LangGraph？

**A**:
1. 在节点中添加 `print()` 语句
2. 使用 `get_state_history()` 查看历史
3. 使用 Human-in-the-Loop 逐步执行

---

## 📊 实际应用场景

### 1. 客服系统
- **State**: 对话历史
- **Memory**: 多用户会话
- **Human-in-the-Loop**: 复杂问题转人工

### 2. 内容审核
- **State**: 内容和审核状态
- **Memory**: 保存草稿
- **Human-in-the-Loop**: 发布前审核

### 3. 自动化工作流
- **State**: 任务进度
- **Memory**: 断点续传
- **Human-in-the-Loop**: 关键步骤确认

---

## 🔗 相关资源

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [DeepSeek API 文档](https://platform.deepseek.com/docs)
- [LangChain 文档](https://python.langchain.com/)

---

## 📝 代码风格说明

所有示例都包含：
1. **详细注释**：解释每一步在做什么
2. **跨语言对比**：对比 Python/JS/Go 的写法
3. **实际应用**：展示真实场景的用法
4. **最佳实践**：总结经验和技巧

---

## 🎓 学习建议

1. **按顺序学习**：从 examples1 到 examples6
2. **动手实践**：修改代码，观察结果
3. **对比语法**：理解 Python 和 JS/Go 的差异
4. **理解概念**：不要死记硬背，理解原理
5. **构建项目**：用学到的知识做一个小项目

---

## 🤝 贡献

如果发现问题或有改进建议，欢迎：
1. 修改代码
2. 添加注释
3. 补充示例

---

**祝学习愉快！🚀**

如有问题，请查看：
- `CORE_CONCEPTS_SUMMARY.md` - 核心概念总结
- `CONDITIONAL_EDGES_GUIDE.md` - 条件边指南
- `README_DEEPSEEK.md` - DeepSeek 配置
