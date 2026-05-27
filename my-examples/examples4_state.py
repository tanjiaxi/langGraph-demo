"""
LangGraph State 深度理解示例
适合 JS/Go 开发者

State 是什么？
- 类似 Redux 的 store（JS）
- 类似 Go 的 struct，但会在节点间传递和累积
"""

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict, Annotated
from typing import List
import operator

# ============================================
# 第一部分：基础 State（简单字典）
# ============================================

print("="*60)
print("📦 第一部分：基础 State")
print("="*60)

class BasicState(TypedDict):
    """
    基础状态：就像普通的字典
    
    JavaScript 等价:
    interface BasicState {
        counter: number;
        message: string;
    }
    
    Go 等价:
    type BasicState struct {
        Counter int
        Message string
    }
    """
    counter: int
    message: str


def increment_node(state: BasicState) -> BasicState:
    """每次调用 counter +1"""
    print(f"  当前 counter: {state['counter']}")
    return {"counter": state["counter"] + 1}


def append_message(state: BasicState) -> BasicState:
    """追加消息"""
    new_msg = f"Step {state['counter']}"
    print(f"  追加消息: {new_msg}")
    return {"message": state["message"] + " -> " + new_msg}


# 构建图
basic_graph = StateGraph(BasicState)
basic_graph.add_node("increment", increment_node)
basic_graph.add_node("append", append_message)
basic_graph.add_edge(START, "increment")
basic_graph.add_edge("increment", "append")
basic_graph.add_edge("append", END)
basic_app = basic_graph.compile()

# 测试
print("\n🧪 测试基础 State:")
result = basic_app.invoke({"counter": 0, "message": "Start"})
print(f"✅ 最终结果: {result}")
print(f"   counter: {result['counter']}")
print(f"   message: {result['message']}")

# ============================================
# 第二部分：State 的合并机制（重点！）
# ============================================

print("\n" + "="*60)
print("🔄 第二部分：State 合并机制")
print("="*60)

print("""
关键概念：节点返回的字典会 **合并** 到 state 中，而不是替换！

类似 JavaScript:
  state = { ...state, ...nodeReturn }

类似 Go:
  // 手动合并字段
  state.Field1 = nodeReturn.Field1
  state.Field2 = nodeReturn.Field2
""")


class MergeState(TypedDict):
    name: str
    age: int
    city: str


def update_age(state: MergeState):
    """只更新 age"""
    print(f"  更新前: {state}")
    return {"age": 30}  # 只返回 age


def update_city(state: MergeState):
    """只更新 city"""
    print(f"  更新前: {state}")
    return {"city": "Beijing"}  # 只返回 city


merge_graph = StateGraph(MergeState)
merge_graph.add_node("update_age", update_age)
merge_graph.add_node("update_city", update_city)
merge_graph.add_edge(START, "update_age")
merge_graph.add_edge("update_age", "update_city")
merge_graph.add_edge("update_city", END)
merge_app = merge_graph.compile()

print("\n🧪 测试合并机制:")
result = merge_app.invoke({"name": "Alice", "age": 25, "city": "Shanghai"})
print(f"✅ 最终结果: {result}")
print("   注意：name 保持不变，age 和 city 被更新")

# ============================================
# 第三部分：Annotated State（高级特性）
# ============================================

print("\n" + "="*60)
print("🎯 第三部分：Annotated State（列表累积）")
print("="*60)

print("""
问题：如果多个节点都返回 messages，如何处理？
- 默认：后面的覆盖前面的（替换）
- Annotated：可以指定累积策略（追加、求和等）

类似 Redux reducer 的概念！
""")


class AnnotatedState(TypedDict):
    """
    使用 Annotated 指定合并策略
    
    operator.add 表示：新值 + 旧值（列表追加）
    """
    messages: Annotated[List[str], operator.add]  # 列表会累积
    total: Annotated[int, operator.add]           # 数字会求和
    name: str                                      # 普通字段会替换


def node_a(state: AnnotatedState):
    print("  Node A 添加消息")
    return {
        "messages": ["Message from A"],
        "total": 10,
        "name": "Node A"
    }


def node_b(state: AnnotatedState):
    print("  Node B 添加消息")
    return {
        "messages": ["Message from B"],
        "total": 20,
        "name": "Node B"
    }


def node_c(state: AnnotatedState):
    print("  Node C 添加消息")
    return {
        "messages": ["Message from C"],
        "total": 30,
        "name": "Node C"
    }


annotated_graph = StateGraph(AnnotatedState)
annotated_graph.add_node("a", node_a)
annotated_graph.add_node("b", node_b)
annotated_graph.add_node("c", node_c)
annotated_graph.add_edge(START, "a")
annotated_graph.add_edge("a", "b")
annotated_graph.add_edge("b", "c")
annotated_graph.add_edge("c", END)
annotated_app = annotated_graph.compile()

print("\n🧪 测试 Annotated State:")
result = annotated_app.invoke({
    "messages": ["Initial"],
    "total": 0,
    "name": "Start"
})
print(f"✅ 最终结果:")
print(f"   messages: {result['messages']}")
print(f"   total: {result['total']} (10 + 20 + 30)")
print(f"   name: {result['name']} (被最后一个节点替换)")

# ============================================
# 第四部分：实际应用 - 对话历史管理
# ============================================

print("\n" + "="*60)
print("💬 第四部分：实际应用 - 对话历史")
print("="*60)

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
import os

os.environ["DEEPSEEK_API_KEY"] = "sk-1f1f27b8e0524422bab4b8517b1068ca"

llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=os.environ["DEEPSEEK_API_KEY"],
    openai_api_base="https://api.deepseek.com",
    temperature=0.7,
)


class ConversationState(TypedDict):
    """
    对话状态：消息历史会累积
    """
    messages: Annotated[List[BaseMessage], operator.add]
    user_name: str
    turn_count: int


def chat_node(state: ConversationState):
    """调用 LLM 生成回复"""
    print(f"\n  💭 Turn {state['turn_count']}: 调用 LLM...")
    
    # 调用 LLM
    response = llm.invoke(state["messages"])
    
    print(f"  🤖 AI: {response.content[:50]}...")
    
    return {
        "messages": [response],  # 追加 AI 消息
        "turn_count": state["turn_count"] + 1
    }


# 构建对话图
chat_graph = StateGraph(ConversationState)
chat_graph.add_node("chat", chat_node)
chat_graph.add_edge(START, "chat")
chat_graph.add_edge("chat", END)
chat_app = chat_graph.compile()

print("\n🧪 测试多轮对话:")

# 第一轮
print("\n--- 第 1 轮 ---")
state = chat_app.invoke({
    "messages": [HumanMessage(content="你好，我叫 Alice")],
    "user_name": "Alice",
    "turn_count": 1
})

# 第二轮（继续上一轮的状态）
print("\n--- 第 2 轮 ---")
state["messages"].append(HumanMessage(content="我刚才说我叫什么？"))
state = chat_app.invoke(state)

print(f"\n✅ 对话历史（共 {len(state['messages'])} 条消息）:")
for i, msg in enumerate(state["messages"], 1):
    role = "👤 User" if isinstance(msg, HumanMessage) else "🤖 AI"
    print(f"  {i}. {role}: {msg.content[:60]}...")

# ============================================
# 第五部分：State 的最佳实践
# ============================================

print("\n" + "="*60)
print("📚 State 最佳实践")
print("="*60)

print("""
1. 使用 TypedDict 定义清晰的类型
   ✅ class State(TypedDict):
          field: str
   ❌ state = {}  # 不推荐

2. 对于需要累积的字段，使用 Annotated
   ✅ messages: Annotated[List, operator.add]
   ❌ messages: List  # 会被替换，不会累积

3. 节点只返回需要更新的字段
   ✅ return {"age": 30}  # 只更新 age
   ❌ return state  # 返回整个 state 是多余的

4. 保持 State 扁平化
   ✅ user_name: str
      user_age: int
   ❌ user: dict  # 嵌套字典不好管理

5. 使用有意义的字段名
   ✅ conversation_history: List[Message]
   ❌ data: List  # 不清楚是什么数据
""")

# ============================================
# 第六部分：对比 JavaScript/Go
# ============================================

print("\n" + "="*60)
print("🔄 跨语言对比")
print("="*60)

print("""
Python (LangGraph):
-------------------
class State(TypedDict):
    messages: Annotated[List[str], operator.add]
    counter: int

def node(state: State):
    return {"counter": state["counter"] + 1}

# State 自动合并
state = {...state, ...node_return}


JavaScript (Redux 风格):
-----------------------
interface State {
    messages: string[];
    counter: number;
}

function reducer(state: State, action): State {
    return {
        ...state,
        counter: state.counter + 1
    };
}


Go (手动管理):
-------------
type State struct {
    Messages []string
    Counter  int
}

func node(state *State) {
    state.Counter++
    // 需要手动修改 state
}


关键区别：
---------
- Python: 返回部分字段，自动合并
- JS: 返回新对象，手动展开
- Go: 直接修改指针，无需返回
""")

print("\n" + "="*60)
print("✅ State 示例完成！")
print("="*60)
