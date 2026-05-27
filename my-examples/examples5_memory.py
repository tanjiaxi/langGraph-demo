"""
LangGraph Memory（持久化存储）示例
适合 JS/Go 开发者

Memory 是什么？
- 类似数据库：保存对话历史，下次可以恢复
- 类似 localStorage（JS）或文件存储（Go）
- 支持多用户、多会话
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver  # 内存存储（测试用）
from langgraph.checkpoint.sqlite import SqliteSaver  # SQLite 存储（生产用）
from typing_extensions import TypedDict, Annotated
from typing import List
import operator
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
import os
import sqlite3

# ============================================
# 第一部分：什么是 Checkpointer？
# ============================================

print("="*60)
print("💾 第一部分：理解 Checkpointer")
print("="*60)

print("""
Checkpointer 是什么？
--------------------
- 保存每一步的 state（检查点）
- 可以恢复到任意历史状态
- 支持多线程（thread）：每个用户/会话独立存储

类似概念：
---------
JavaScript:
  - localStorage.setItem('chat_history', JSON.stringify(state))
  - sessionStorage

Go:
  - 保存到文件：json.Marshal(state) -> file
  - 保存到数据库：INSERT INTO checkpoints ...

支持的存储后端：
--------------
1. MemorySaver: 内存（重启丢失，测试用）
2. SqliteSaver: SQLite 数据库（持久化）
3. PostgresSaver: PostgreSQL（生产环境）
4. RedisSaver: Redis（高性能）
""")

# ============================================
# 第二部分：基础 Memory 示例
# ============================================

print("\n" + "="*60)
print("🔧 第二部分：基础 Memory 使用")
print("="*60)


class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    user_name: str


os.environ["DEEPSEEK_API_KEY"] = "sk-1f1f27b8e0524422bab4b8517b1068ca"

llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=os.environ["DEEPSEEK_API_KEY"],
    openai_api_base="https://api.deepseek.com",
    temperature=0.7,
)


def chat_node(state: ChatState):
    """聊天节点"""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


# 创建图
graph = StateGraph(ChatState)
graph.add_node("chat", chat_node)
graph.add_edge(START, "chat")
graph.add_edge("chat", END)

# ⭐ 关键：添加 checkpointer
memory = MemorySaver()  # 使用内存存储
app = graph.compile(checkpointer=memory)

print("\n🧪 测试 1：基础对话（带 Memory）")

# 配置：指定 thread_id（会话 ID）
config = {"configurable": {"thread_id": "user_alice_001"}}

# 第一轮对话
print("\n--- 第 1 轮 ---")
result1 = app.invoke(
    {"messages": [HumanMessage(content="你好，我叫 Alice")]},
    config=config
)
print(f"🤖 AI: {result1['messages'][-1].content[:50]}...")

# 第二轮对话（使用相同的 thread_id，会自动加载历史）
print("\n--- 第 2 轮 ---")
result2 = app.invoke(
    {"messages": [HumanMessage(content="我刚才说我叫什么？")]},
    config=config
)
print(f"🤖 AI: {result2['messages'][-1].content[:50]}...")

print(f"\n✅ 对话历史已保存！共 {len(result2['messages'])} 条消息")

# ============================================
# 第三部分：多用户/多会话
# ============================================

print("\n" + "="*60)
print("👥 第三部分：多用户会话管理")
print("="*60)

print("""
thread_id 的作用：
-----------------
- 每个 thread_id 是一个独立的会话
- 类似数据库的主键
- 不同用户使用不同的 thread_id

类似概念：
---------
JavaScript:
  const sessionId = 'user_123';
  localStorage.setItem(`chat_${sessionId}`, data);

Go:
  type Session struct {
      ThreadID string
      Messages []Message
  }
  sessions := map[string]Session{}
""")

# Alice 的会话
print("\n🧪 测试 2：Alice 的会话")
alice_config = {"configurable": {"thread_id": "alice"}}
result = app.invoke(
    {"messages": [HumanMessage(content="我是 Alice，我喜欢编程")]},
    config=alice_config
)
print(f"🤖 回复 Alice: {result['messages'][-1].content[:50]}...")

# Bob 的会话（完全独立）
print("\n🧪 测试 3：Bob 的会话")
bob_config = {"configurable": {"thread_id": "bob"}}
result = app.invoke(
    {"messages": [HumanMessage(content="我是 Bob，我喜欢音乐")]},
    config=bob_config
)
print(f"🤖 回复 Bob: {result['messages'][-1].content[:50]}...")

# 继续 Alice 的会话
print("\n🧪 测试 4：继续 Alice 的会话")
result = app.invoke(
    {"messages": [HumanMessage(content="我刚才说我喜欢什么？")]},
    config=alice_config
)
print(f"🤖 回复 Alice: {result['messages'][-1].content[:50]}...")
print("   ✅ AI 记得 Alice 喜欢编程！")

# ============================================
# 第四部分：SQLite 持久化存储
# ============================================

print("\n" + "="*60)
print("💿 第四部分：SQLite 持久化存储")
print("="*60)

print("""
MemorySaver vs SqliteSaver:
--------------------------
MemorySaver:
  - 存储在内存中
  - 程序重启后丢失
  - 适合测试

SqliteSaver:
  - 存储在 SQLite 数据库文件
  - 持久化，重启后仍然存在
  - 适合生产环境
""")

# 创建 SQLite checkpointer
db_path = "/Users/t/ServerProjects/classic/langgraph/examples/my-examples/chat_memory.db"
print(f"\n📁 数据库路径: {db_path}")

# 创建连接
conn = sqlite3.connect(db_path, check_same_thread=False)
sqlite_memory = SqliteSaver(conn)

# 使用 SQLite 编译图
app_with_db = graph.compile(checkpointer=sqlite_memory)

print("\n🧪 测试 5：SQLite 持久化")

# 保存对话
config = {"configurable": {"thread_id": "persistent_user"}}
result = app_with_db.invoke(
    {"messages": [HumanMessage(content="这条消息会保存到数据库")]},
    config=config
)
print(f"✅ 消息已保存到 SQLite: {db_path}")

# ============================================
# 第五部分：查看历史记录
# ============================================

print("\n" + "="*60)
print("📜 第五部分：查看和管理历史")
print("="*60)


def print_history(app, thread_id: str):
    """打印指定会话的历史"""
    config = {"configurable": {"thread_id": thread_id}}
    
    # 获取状态历史
    history = app.get_state_history(config)
    
    print(f"\n📋 Thread '{thread_id}' 的历史:")
    for i, state in enumerate(history):
        if "messages" in state.values:
            msg_count = len(state.values["messages"])
            print(f"  Checkpoint {i}: {msg_count} 条消息")


# 查看 Alice 的历史
print_history(app, "alice")

# ============================================
# 第六部分：实际应用 - 客服系统
# ============================================

print("\n" + "="*60)
print("🎯 第六部分：实际应用 - 客服系统")
print("="*60)


class CustomerState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    customer_id: str
    issue_resolved: bool
    satisfaction_score: int


def customer_service_node(state: CustomerState):
    """客服节点"""
    system_prompt = f"""你是客服助手。
客户 ID: {state['customer_id']}
问题是否解决: {state.get('issue_resolved', False)}
"""
    
    messages = [HumanMessage(content=system_prompt)] + state["messages"]
    response = llm.invoke(messages)
    
    return {"messages": [response]}


# 构建客服图
cs_graph = StateGraph(CustomerState)
cs_graph.add_node("service", customer_service_node)
cs_graph.add_edge(START, "service")
cs_graph.add_edge("service", END)

# 使用 SQLite 存储
cs_app = cs_graph.compile(checkpointer=sqlite_memory)

print("\n🧪 测试 6：客服系统")

# 客户 1 的第一次咨询
customer1_config = {"configurable": {"thread_id": "customer_001"}}
result = cs_app.invoke(
    {
        "messages": [HumanMessage(content="我的订单还没发货")],
        "customer_id": "CUST001",
        "issue_resolved": False,
        "satisfaction_score": 0
    },
    config=customer1_config
)
print(f"🤖 客服: {result['messages'][-1].content[:80]}...")

# 客户 1 的后续咨询（自动加载历史）
print("\n--- 客户 1 后续咨询 ---")
result = cs_app.invoke(
    {"messages": [HumanMessage(content="订单号是 12345")]},
    config=customer1_config
)
print(f"🤖 客服: {result['messages'][-1].content[:80]}...")
print("   ✅ 客服记得之前的对话内容！")

# ============================================
# 第七部分：对比 JavaScript/Go
# ============================================

print("\n" + "="*60)
print("🔄 跨语言对比")
print("="*60)

print("""
Python (LangGraph):
-------------------
from langgraph.checkpoint.sqlite import SqliteSaver

memory = SqliteSaver(conn)
app = graph.compile(checkpointer=memory)

result = app.invoke(
    input_data,
    config={"configurable": {"thread_id": "user_123"}}
)


JavaScript (类似实现):
---------------------
// 使用 localStorage
const threadId = 'user_123';
const history = JSON.parse(
    localStorage.getItem(`chat_${threadId}`) || '[]'
);

// 添加新消息
history.push(newMessage);
localStorage.setItem(`chat_${threadId}`, JSON.stringify(history));

// 或使用数据库
const db = new SQLite('chat.db');
db.run(
    'INSERT INTO messages (thread_id, content) VALUES (?, ?)',
    [threadId, content]
);


Go (类似实现):
-------------
type Checkpoint struct {
    ThreadID  string
    Messages  []Message
    Timestamp time.Time
}

// 保存到文件
func saveCheckpoint(threadID string, state State) error {
    data, _ := json.Marshal(state)
    return os.WriteFile(
        fmt.Sprintf("checkpoints/%s.json", threadID),
        data,
        0644,
    )
}

// 从文件加载
func loadCheckpoint(threadID string) (State, error) {
    data, err := os.ReadFile(
        fmt.Sprintf("checkpoints/%s.json", threadID)
    )
    var state State
    json.Unmarshal(data, &state)
    return state, err
}

// 或使用数据库
db.Exec(
    "INSERT INTO checkpoints (thread_id, state) VALUES (?, ?)",
    threadID, stateJSON,
)
""")

# ============================================
# 第八部分：最佳实践
# ============================================

print("\n" + "="*60)
print("📚 Memory 最佳实践")
print("="*60)

print("""
1. 选择合适的存储后端
   - 开发/测试: MemorySaver
   - 生产环境: SqliteSaver / PostgresSaver
   - 高性能: RedisSaver

2. 使用有意义的 thread_id
   ✅ f"user_{user_id}_session_{session_id}"
   ✅ f"customer_{customer_id}"
   ❌ "thread1"  # 不清楚是谁

3. 定期清理旧数据
   - 设置过期时间
   - 删除不活跃的会话

4. 处理并发
   - SQLite: 适合单机、低并发
   - PostgreSQL: 适合多机、高并发

5. 备份重要数据
   - 定期备份数据库文件
   - 导出关键会话

6. 监控存储大小
   - 限制每个会话的消息数量
   - 压缩或归档旧消息
""")

print("\n" + "="*60)
print("✅ Memory 示例完成！")
print(f"📁 数据库文件: {db_path}")
print("="*60)

# 关闭数据库连接
conn.close()
