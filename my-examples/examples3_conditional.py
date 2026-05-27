"""
LangGraph 条件边示例
根据问题类型，路由到不同的处理节点
"""

from langgraph.graph import StateGraph
from typing_extensions import TypedDict, Literal
from langgraph.graph import START, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import os

# ============================================
# 1. 定义状态类型
# ============================================

class State(TypedDict):
    question: str           # 用户问题
    question_type: str      # 问题类型（技术/日常/数学）
    llm_answer: str         # LLM 回答
    final_answer: str       # 最终答案

# ============================================
# 2. 配置 DeepSeek 模型
# ============================================

os.environ["DEEPSEEK_API_KEY"] = "sk-1f1f27b8e0524422bab4b8517b1068ca"

llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=os.environ["DEEPSEEK_API_KEY"],
    openai_api_base="https://api.deepseek.com",
    temperature=0.7,
)

# ============================================
# 3. 定义节点函数
# ============================================

def classify_question(state: State) -> State:
    """
    分类节点：判断问题类型
    """
    print(f"\n📋 [分类节点] 正在分析问题: {state['question']}")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个问题分类器。请将问题分类为以下三种之一：
        - technical: 技术问题（编程、AI、科技等）
        - daily: 日常问题（生活、娱乐、常识等）
        - math: 数学问题（计算、公式等）
        
        只回复一个单词：technical、daily 或 math"""),
        ("human", "{question}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"question": state["question"]})
    question_type = response.content.strip().lower()
    
    print(f"✅ 问题类型: {question_type}")
    
    return {"question_type": question_type}


def technical_node(state: State) -> State:
    """
    技术问题处理节点
    """
    print(f"\n💻 [技术节点] 处理技术问题...")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个技术专家。请用专业、详细的方式回答技术问题，包含代码示例。"),
        ("human", "{question}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"question": state["question"]})
    
    return {"llm_answer": response.content}


def daily_node(state: State) -> State:
    """
    日常问题处理节点
    """
    print(f"\n💬 [日常节点] 处理日常问题...")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个友好的助手。请用轻松、口语化的方式回答日常问题。"),
        ("human", "{question}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"question": state["question"]})
    
    return {"llm_answer": response.content}


def math_node(state: State) -> State:
    """
    数学问题处理节点
    """
    print(f"\n🔢 [数学节点] 处理数学问题...")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个数学老师。请详细解释计算步骤，给出最终答案。"),
        ("human", "{question}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"question": state["question"]})
    
    return {"llm_answer": response.content}


def format_answer(state: State) -> State:
    """
    格式化节点：添加问题类型标签
    """
    print(f"\n✨ [格式化节点] 生成最终答案...")
    
    type_emoji = {
        "technical": "💻",
        "daily": "💬",
        "math": "🔢"
    }
    
    emoji = type_emoji.get(state["question_type"], "❓")
    final = f"{emoji} [{state['question_type'].upper()}]\n\n{state['llm_answer']}"
    
    return {"final_answer": final}


# ============================================
# 4. 定义路由函数（条件边的核心）
# ============================================

def route_question(state: State) -> Literal["technical_node", "daily_node", "math_node"]:
    """
    路由函数：根据问题类型决定下一个节点
    
    这个函数的返回值必须是节点名称（字符串）
    """
    question_type = state["question_type"]
    
    # 路由逻辑
    if question_type == "technical":
        print(f"🔀 [路由] 问题类型是 technical，路由到 technical_node")
        return "technical_node"
    elif question_type == "math":
        print(f"🔀 [路由] 问题类型是 math，路由到 math_node")
        return "math_node"
    else:
        print(f"🔀 [路由] 问题类型是 daily，路由到 daily_node")
        return "daily_node"


# ============================================
# 5. 构建图（重点：add_conditional_edges）
# ============================================

builder = StateGraph(State)

# 添加所有节点
builder.add_node("classify", classify_question)
builder.add_node("technical_node", technical_node)
builder.add_node("daily_node", daily_node)
builder.add_node("math_node", math_node)
builder.add_node("format", format_answer)

# 添加边
builder.add_edge(START, "classify")

# ⭐ 关键：添加条件边
# add_conditional_edges(
#     source_node,        # 从哪个节点出发
#     routing_function,   # 路由函数（决定去哪）
#     path_map            # 可选：路由映射（如果路由函数返回的不是节点名）
# )
builder.add_conditional_edges(
    "classify",          # 从 classify 节点出发
    route_question,      # 使用 route_question 函数决定路由
    # 因为 route_question 直接返回节点名，所以不需要 path_map
)

# 所有处理节点都连接到格式化节点
builder.add_edge("technical_node", "format")
builder.add_edge("daily_node", "format")
builder.add_edge("math_node", "format")

# 格式化后结束
builder.add_edge("format", END)

# 编译图
graph = builder.compile()

# ============================================
# 6. 可视化图结构（可选）
# ============================================

def print_graph_structure():
    """打印图的结构"""
    print("\n" + "="*50)
    print("📊 图结构:")
    print("="*50)
    print("""
    START
      ↓
    classify (分类问题)
      ↓
    [条件边] ← 根据 question_type 路由
      ├─→ technical_node (技术问题)
      ├─→ daily_node (日常问题)
      └─→ math_node (数学问题)
      ↓
    format (格式化答案)
      ↓
    END
    """)
    print("="*50 + "\n")


# ============================================
# 7. 测试不同类型的问题
# ============================================

if __name__ == "__main__":
    print_graph_structure()
    
    # 测试问题列表
    test_questions = [
        "什么是 LangGraph？如何使用条件边？",  # 技术问题
        "今天天气真好，推荐一些户外活动吧",      # 日常问题
        "计算 123 * 456 等于多少？",           # 数学问题
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'='*60}")
        print(f"🧪 测试 {i}: {question}")
        print(f"{'='*60}")
        
        result = graph.invoke({"question": question})
        
        print(f"\n📤 最终输出:")
        print(result["final_answer"])
        print(f"\n{'='*60}\n")


# ============================================
# 8. 对比 JavaScript/Go 的条件边概念
# ============================================

"""
JavaScript 等价概念:
------------------
const routeQuestion = (state) => {
    if (state.questionType === 'technical') {
        return 'technical_node';
    } else if (state.questionType === 'math') {
        return 'math_node';
    } else {
        return 'daily_node';
    }
};

// 类似 switch-case 或路由表
const routes = {
    'technical': technicalNode,
    'daily': dailyNode,
    'math': mathNode
};

const nextNode = routes[routeQuestion(state)];


Go 等价概念:
-----------
func routeQuestion(state State) string {
    switch state.QuestionType {
    case "technical":
        return "technical_node"
    case "math":
        return "math_node"
    default:
        return "daily_node"
    }
}

// 或者使用 map
routes := map[string]func(State) State{
    "technical": technicalNode,
    "daily":     dailyNode,
    "math":      mathNode,
}

nextNodeName := routeQuestion(state)
nextNode := routes[nextNodeName]
"""
