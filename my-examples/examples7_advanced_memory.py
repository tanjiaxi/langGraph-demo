"""
LangGraph Advanced Memory 深度示例
- Checkpointer 详解
- 时间旅行（恢复到任意时刻）
- 消息管理策略
- 实际应用场景
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from typing_extensions import TypedDict, Annotated
from typing import List
import operator
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
import os
import sqlite3
from datetime import datetime

# ============================================
# 第一部分：Checkpointer 深度理解
# ============================================

print("="*70)
print("💾 第一部分：Checkpointer 是什么？")
print("="*70)

print("""
Checkpointer 的核心概念：
-----------------------
1. **Checkpoint（检查点）**：某个时刻的完整 State 快照
2. **自动保存**：每个节点执行后自动保存
3. **版本控制**：类似 Git commit，每个 checkpoint 有唯一 ID
4. **时间旅行**：可以回到任意历史 checkpoint

类比理解：
---------
Git:
  commit 1 → commit 2 → commit 3 → commit 4
  可以 checkout 到任意 commit

LangGraph Checkpointer:
  checkpoint 1 → checkpoint 2 → checkpoint 3 → checkpoint 4
  可以恢复到任意 checkpoint

数据库事务:
  BEGIN → UPDATE 1 → UPDATE 2 → COMMIT
  可以 ROLLBACK 到任意时刻

JavaScript 类比:
  const history = [state1, state2, state3, state4];
  const currentState = history[2];  // 回到第 3 个状态

Go 类比:
  type Checkpoint struct {
      ID        string
      State     State
      Timestamp time.Time
  }
  checkpoints := []Checkpoint{...}
""")

# ============================================
# 第二部分：Checkpoint 的结构
# ============================================

print("\n" + "="*70)
print("🔍 第二部分：Checkpoint 的内部结构")
print("="*70)


class SimpleState(TypedDict):
    counter: int
    message: str


def increment_node(state: SimpleState):
    new_counter = state["counter"] + 1
    print(f"  执行节点: counter {state['counter']} → {new_counter}")
    return {"counter": new_counter}


# 创建简单图
simple_graph = StateGraph(SimpleState)
simple_graph.add_node("increment", increment_node)
simple_graph.add_edge(START, "increment")
simple_graph.add_edge("increment", END)

# 使用 MemorySaver
memory = MemorySaver()
simple_app = simple_graph.compile(checkpointer=memory)

print("\n🧪 测试：查看 Checkpoint 结构")

config = {"configurable": {"thread_id": "demo_thread"}}

# 执行多次，创建多个 checkpoint
for i in range(3):
    print(f"\n--- 第 {i+1} 次执行 ---")
    result = simple_app.invoke(
        {"counter": i, "message": f"Round {i+1}"},
        config=config
    )

# 查看所有 checkpoint
print("\n📋 所有 Checkpoint:")
history = list(simple_app.get_state_history(config))

for i, checkpoint in enumerate(history):
    print(f"\nCheckpoint {i}:")
    print(f"  Config ID: {checkpoint.config['configurable']['checkpoint_id'][:8]}...")
    print(f"  State: {checkpoint.values}")
    print(f"  Next: {checkpoint.next}")
    print(f"  Metadata: {checkpoint.metadata}")

print(f"\n✅ 共有 {len(history)} 个 checkpoint")

# ============================================
# 第三部分：时间旅行 - 恢复到任意时刻
# ============================================

print("\n" + "="*70)
print("⏰ 第三部分：时间旅行（Time Travel）")
print("="*70)

print("""
时间旅行的应用场景：
-----------------
1. **撤销操作**：回到上一步
2. **分支探索**：从某个点开始尝试不同路径
3. **调试**：回到出错前的状态
4. **A/B 测试**：从同一起点测试不同策略
5. **用户反悔**：允许用户回退操作

类似概念：
---------
Git:
  git checkout <commit-id>
  git reset --hard HEAD~1

游戏存档:
  Save Point 1 → Save Point 2 → Save Point 3
  可以读取任意存档点

数据库:
  SELECT * FROM table AS OF TIMESTAMP '2024-01-01'
""")

os.environ["DEEPSEEK_API_KEY"] = "sk-1f1f27b8e0524422bab4b8517b1068ca"

llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=os.environ["DEEPSEEK_API_KEY"],
    openai_api_base="https://api.deepseek.com",
    temperature=0.7,
)


class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    turn: int


def chat_node(state: ChatState):
    """聊天节点"""
    response = llm.invoke(state["messages"])
    return {
        "messages": [response],
        "turn": state.get("turn", 0) + 1
    }


# 创建聊天图
chat_graph = StateGraph(ChatState)
chat_graph.add_node("chat", chat_node)
chat_graph.add_edge(START, "chat")
chat_graph.add_edge("chat", END)

# 使用 SQLite 存储（持久化）
db_path = "/Users/t/ServerProjects/classic/langgraph/examples/my-examples/time_travel.db"
conn = sqlite3.connect(db_path, check_same_thread=False)
sqlite_memory = SqliteSaver(conn)
chat_app = chat_graph.compile(checkpointer=sqlite_memory)

print("\n🧪 测试：时间旅行")

config = {"configurable": {"thread_id": "time_travel_demo"}}

# 进行 3 轮对话
conversations = [
    "你好，我叫 Alice",
    "我喜欢编程",
    "我最喜欢 Python"
]

print("\n--- 创建对话历史 ---")
for i, msg in enumerate(conversations, 1):
    print(f"\n第 {i} 轮: {msg}")
    result = chat_app.invoke(
        {"messages": [HumanMessage(content=msg)], "turn": 0},
        config=config
    )
    print(f"AI: {result['messages'][-1].content[:50]}...")

# 获取所有 checkpoint
print("\n--- 查看所有 Checkpoint ---")
history = list(chat_app.get_state_history(config))
print(f"共有 {len(history)} 个 checkpoint")

for i, checkpoint in enumerate(history[:5]):  # 只显示前 5 个
    msg_count = len(checkpoint.values.get("messages", []))
    turn = checkpoint.values.get("turn", 0)
    print(f"  Checkpoint {i}: {msg_count} 条消息, Turn {turn}")

# ⭐ 关键：恢复到第 2 轮对话后的状态
print("\n--- 时间旅行：回到第 2 轮 ---")

# 获取第 2 轮的 checkpoint（倒数第 3 个）
target_checkpoint = history[2]  # 索引 2 是倒数第 3 个
target_config = target_checkpoint.config

print(f"目标 Checkpoint ID: {target_config['configurable']['checkpoint_id'][:8]}...")
print(f"该时刻的消息数: {len(target_checkpoint.values['messages'])}")

# 从这个 checkpoint 继续对话
print("\n从第 2 轮继续，问一个新问题:")
result = chat_app.invoke(
    {"messages": [HumanMessage(content="我刚才说了几句话？")]},
    config=target_config  # 使用历史 checkpoint 的 config
)

print(f"AI: {result['messages'][-1].content}")
print("\n✅ AI 只记得前 2 轮的内容，不记得第 3 轮！")

# ============================================
# 第四部分：消息管理策略
# ============================================

print("\n" + "="*70)
print("💬 第四部分：消息管理策略")
print("="*70)

print("""
问题：State 中所有消息都发给 LLM 吗？
------------------------------------
答案：**取决于你的实现！**

三种常见策略：
------------

1. **全部发送**（默认）
   优点：LLM 有完整上下文
   缺点：token 消耗大，超过上下文窗口会报错
   
   messages: Annotated[List[BaseMessage], operator.add]
   llm.invoke(state["messages"])  # 全部发送

2. **只发送最近 N 条**
   优点：控制 token 消耗
   缺点：可能丢失重要上下文
   
   recent_messages = state["messages"][-10:]  # 最近 10 条
   llm.invoke(recent_messages)

3. **智能摘要**（推荐）
   优点：保留关键信息，控制 token
   缺点：需要额外的摘要逻辑
   
   summary = summarize(state["messages"][:-10])
   recent = state["messages"][-10:]
   llm.invoke([summary] + recent)
""")


class ManagedChatState(TypedDict):
    """带消息管理的聊天状态"""
    messages: Annotated[List[BaseMessage], operator.add]
    summary: str  # 历史摘要
    turn: int


def smart_chat_node(state: ManagedChatState):
    """智能消息管理的聊天节点"""
    messages = state["messages"]
    
    # 策略：如果消息超过 10 条，只发送最近 10 条
    if len(messages) > 10:
        print(f"  ⚠️  消息过多（{len(messages)} 条），只发送最近 10 条")
        messages_to_send = messages[-10:]
    else:
        print(f"  ✅ 发送全部 {len(messages)} 条消息")
        messages_to_send = messages
    
    # 调用 LLM
    response = llm.invoke(messages_to_send)
    
    return {
        "messages": [response],
        "turn": state.get("turn", 0) + 1
    }


print("\n🧪 测试：消息管理策略")

# 创建新图
managed_graph = StateGraph(ManagedChatState)
managed_graph.add_node("chat", smart_chat_node)
managed_graph.add_edge(START, "chat")
managed_graph.add_edge("chat", END)
managed_app = managed_graph.compile(checkpointer=sqlite_memory)

config = {"configurable": {"thread_id": "managed_chat"}}

# 模拟多轮对话
print("\n--- 模拟 12 轮对话 ---")
for i in range(12):
    result = managed_app.invoke(
        {"messages": [HumanMessage(content=f"这是第 {i+1} 条消息")], "turn": 0, "summary": ""},
        config=config
    )

print(f"\n✅ 完成 12 轮对话")
print(f"   State 中有 {len(result['messages'])} 条消息")
print(f"   但只有最近 10 条会发送给 LLM")

# ============================================
# 第五部分：实际应用场景
# ============================================

print("\n" + "="*70)
print("🎯 第五部分：实际应用场景")
print("="*70)

print("""
场景 1：客服系统的会话恢复
------------------------
问题：客服断线后，如何恢复对话？

解决方案：
1. 每次对话自动保存 checkpoint
2. 客服重新连接时，加载最新 checkpoint
3. 继续之前的对话

代码示例：
config = {"configurable": {"thread_id": f"customer_{customer_id}"}}

# 客服断线前
result = app.invoke(input, config)

# 客服重新连接
state = app.get_state(config)  # 获取最新状态
# 继续对话
result = app.invoke(new_input, config)


场景 2：多路径探索（A/B 测试）
---------------------------
问题：从同一起点测试不同的对话策略

解决方案：
1. 保存初始 checkpoint
2. 从该 checkpoint 分别尝试策略 A 和策略 B
3. 比较结果

代码示例：
# 创建初始状态
result = app.invoke(initial_input, config)
history = list(app.get_state_history(config))
initial_checkpoint = history[0]

# 策略 A
result_a = app.invoke(strategy_a_input, initial_checkpoint.config)

# 策略 B（从同一起点）
result_b = app.invoke(strategy_b_input, initial_checkpoint.config)


场景 3：用户撤销操作
------------------
问题：用户想撤销上一步操作

解决方案：
1. 获取倒数第 2 个 checkpoint
2. 从该 checkpoint 继续

代码示例：
history = list(app.get_state_history(config))
previous_checkpoint = history[1]  # 倒数第 2 个

# 从上一步继续
result = app.invoke(new_input, previous_checkpoint.config)


场景 4：调试和错误恢复
--------------------
问题：某个节点出错，想回到出错前的状态

解决方案：
1. 找到出错前的 checkpoint
2. 修复代码
3. 从该 checkpoint 重新执行

代码示例：
history = list(app.get_state_history(config))

# 找到出错前的 checkpoint
for checkpoint in history:
    if checkpoint.values.get("error") is None:
        # 从这里重新开始
        result = app.invoke(None, checkpoint.config)
        break


场景 5：长时间任务的断点续传
--------------------------
问题：任务执行到一半，程序崩溃了

解决方案：
1. 使用 SqliteSaver 持久化
2. 重启后加载最新 checkpoint
3. 继续执行

代码示例：
# 程序崩溃前
app = graph.compile(checkpointer=SqliteSaver(conn))
result = app.invoke(input, config)  # 自动保存

# 程序重启后
app = graph.compile(checkpointer=SqliteSaver(conn))  # 重新连接
state = app.get_state(config)  # 加载最新状态
result = app.invoke(None, config)  # 继续执行
""")

# ============================================
# 第六部分：实战演示 - 可撤销的对话系统
# ============================================

print("\n" + "="*70)
print("🎮 第六部分：实战演示 - 可撤销的对话系统")
print("="*70)


class UndoableChatState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    turn: int


def undoable_chat_node(state: UndoableChatState):
    response = llm.invoke(state["messages"])
    return {
        "messages": [response],
        "turn": state.get("turn", 0) + 1
    }


undoable_graph = StateGraph(UndoableChatState)
undoable_graph.add_node("chat", undoable_chat_node)
undoable_graph.add_edge(START, "chat")
undoable_graph.add_edge("chat", END)
undoable_app = undoable_graph.compile(checkpointer=sqlite_memory)

print("\n🧪 测试：可撤销的对话系统")

config = {"configurable": {"thread_id": "undoable_chat"}}

# 第一轮
print("\n--- 第 1 轮 ---")
result = undoable_app.invoke(
    {"messages": [HumanMessage(content="推荐一部科幻电影")], "turn": 0},
    config=config
)
print(f"AI: {result['messages'][-1].content[:80]}...")

# 第二轮
print("\n--- 第 2 轮 ---")
result = undoable_app.invoke(
    {"messages": [HumanMessage(content="再推荐一部动作片")]},
    config=config
)
print(f"AI: {result['messages'][-1].content[:80]}...")

# 用户反悔，想撤销第 2 轮
print("\n--- 用户撤销第 2 轮 ---")
history = list(undoable_app.get_state_history(config))
previous_state = history[1]  # 倒数第 2 个 checkpoint

print(f"回到 checkpoint: {previous_state.config['configurable']['checkpoint_id'][:8]}...")
print(f"该时刻的消息数: {len(previous_state.values['messages'])}")

# 从第 1 轮后重新开始
print("\n--- 重新提问 ---")
result = undoable_app.invoke(
    {"messages": [HumanMessage(content="推荐一部喜剧片")]},
    config=previous_state.config
)
print(f"AI: {result['messages'][-1].content[:80]}...")
print("\n✅ 成功撤销并重新提问！")

# ============================================
# 第七部分：最佳实践
# ============================================

print("\n" + "="*70)
print("📚 最佳实践总结")
print("="*70)

print("""
1. 选择合适的 Checkpointer
   - 开发/测试: MemorySaver（快速，但不持久）
   - 生产环境: SqliteSaver（持久化，单机）
   - 高并发: PostgresSaver 或 RedisSaver

2. 消息管理策略
   ✅ 监控消息数量
   ✅ 超过阈值时只发送最近 N 条
   ✅ 或者使用摘要 + 最近消息
   ❌ 不要无限累积消息

3. Checkpoint 清理
   ✅ 定期删除旧的 checkpoint
   ✅ 只保留最近 N 个
   ✅ 或者设置过期时间

4. thread_id 命名规范
   ✅ 使用有意义的 ID: f"user_{user_id}_session_{session_id}"
   ✅ 包含时间戳: f"chat_{user_id}_{timestamp}"
   ❌ 避免随机 ID: "abc123"

5. 错误处理
   ✅ 捕获异常，保存错误状态
   ✅ 提供恢复机制
   ✅ 记录错误日志

6. 性能优化
   ✅ 使用索引（数据库）
   ✅ 批量操作
   ✅ 异步保存（如果可能）
""")

print("\n" + "="*70)
print("✅ Advanced Memory 示例完成！")
print(f"📁 数据库文件: {db_path}")
print("="*70)

# 关闭连接
conn.close()
