from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
# from langgraph.checkpoint import MemorySaver

# 1. 定义状态
class SupportState(TypedDict):
    query: str
    category: str
    sentiment: str
    response: str
    need_escalation: bool

# 2. 定义节点函数
def classify_query(state: SupportState) -> dict:
    """对查询进行分类"""
    query = state["query"].lower()
    
    if "退款" in query or "退货" in query:
        category = "refund"
    elif "密码" in query or "登录" in query:
        category = "account"
    elif "投诉" in query:
        category = "complaint"
    else:
        category = "general"
    
    return {"category": category}

def analyze_sentiment(state: SupportState) -> dict:
    """分析情感倾向"""
    negative_words = ["生气", "失望", "不满", "投诉"]
    query = state["query"]
    
    sentiment = "negative" if any(word in query for word in negative_words) else "positive"
    return {"sentiment": sentiment}

def handle_refund(state: SupportState) -> dict:
    """处理退款请求"""
    return {"response": "已为您创建退款工单，预计3-5个工作日处理完成"}

def handle_account(state: SupportState) -> dict:
    """处理账户问题"""
    return {"response": "请按照以下步骤重置密码：1. 点击'忘记密码' 2. 验证邮箱 3. 设置新密码"}

def handle_complaint(state: SupportState) -> dict:
    """处理投诉"""
    return {"response": "已记录您的投诉，客服主管将在24小时内联系您"}

def handle_general(state: SupportState) -> dict:
    """处理一般问题"""
    return {"response": "感谢您的咨询，请详细描述您的问题"}

def check_escalation(state: SupportState) -> dict:
    """检查是否需要升级处理"""
    need_escalation = state["sentiment"] == "negative" and state["category"] == "complaint"
    return {"need_escalation": need_escalation}

# 3. 条件路由函数
def route_by_category(state: SupportState) -> Literal["handle_refund", "handle_account", "handle_complaint", "handle_general"]:
    """根据分类路由到不同的处理节点"""
    routing_map = {
        "refund": "handle_refund",
        "account": "handle_account",
        "complaint": "handle_complaint",
        "general": "handle_general"
    }
    return routing_map.get(state["category"], "handle_general")

def route_by_escalation(state: SupportState) -> Literal["human_agent", "generate_response"]:
    """根据是否需要升级路由"""
    if state["need_escalation"]:
        return "human_agent"
    return "generate_response"

# 4. 构建图
def build_support_graph():
    # 创建图构建器
    builder = StateGraph(SupportState)
    
    # 添加节点
    builder.add_node("classify", classify_query)
    builder.add_node("sentiment", analyze_sentiment)
    builder.add_node("handle_refund", handle_refund)
    builder.add_node("handle_account", handle_account)
    builder.add_node("handle_complaint", handle_complaint)
    builder.add_node("handle_general", handle_general)
    builder.add_node("check_escalation", check_escalation)
    
    # 添加条件边
    builder.add_conditional_edges(
        "classify",
        route_by_category,
        {
            "handle_refund": "handle_refund",
            "handle_account": "handle_account",
            "handle_complaint": "handle_complaint",
            "handle_general": "handle_general"
        }
    )
    
    # 添加条件边进行升级检查
    builder.add_conditional_edges(
        "check_escalation",
        route_by_escalation,
        {
            "human_agent": END,
            "generate_response": END
        }
    )
    
    # 添加普通边
    builder.add_edge("sentiment", "check_escalation")
    builder.add_edge("handle_refund", "sentiment")
    builder.add_edge("handle_account", "sentiment")
    builder.add_edge("handle_complaint", "sentiment")
    builder.add_edge("handle_general", "sentiment")
    
    # 设置入口点
    builder.set_entry_point("classify")
    
    # 编译图
    return builder.compile()

# 5. 使用图
def main():
    # 创建图实例
    support_graph = build_support_graph()
    
    # 测试用例
    test_queries = [
        "我想申请退款，对产品不满意",
        "忘记登录密码了怎么办",
        "非常生气，我要投诉你们的服务态度",
        "请问你们的工作时间是什么时候"
    ]
    
    for query in test_queries:
        print(f"\n处理查询: {query}")
        result = support_graph.invoke({"query": query})
        print(f"响应: {result['response']}")
        print(f"需要升级: {result.get('need_escalation', False)}")

if __name__ == "__main__":
    main()