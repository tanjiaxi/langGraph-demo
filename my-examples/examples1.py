from langgraph.graph import StateGraph
from typing_extensions import TypedDict
from langgraph.graph import START, END

# 定义输入的模式
class InputState(TypedDict):
    question: str


# 定义输出的模式
class OutputState(TypedDict):
    answer: str


# 将 InputState 和 OutputState 这两个 TypedDict 类型合并成一个更全面的字典类型。
class OverallState(InputState, OutputState):
    pass
def agent_node(state: InputState):
    print("我是一个AI Agent。")
    return {"question": state["question"]}
def action_node(state: InputState):
    print("我现在是一个执行者。")
    step = state["question"]
    return {"answer": f"我接收到的问题是：{step}，读取成功了！"}
# 新的推荐写法
builder = StateGraph(OverallState, input_schema=InputState, output_schema=OutputState)

# 添加节点
builder.add_node("agent_node", agent_node)
builder.add_node("action_node", action_node)

# 添加边
builder.add_edge(START, "agent_node")
builder.add_edge("agent_node", "action_node")
builder.add_edge("action_node", END)

# 编译图
graph = builder.compile()

# 运行图
if __name__ == "__main__":
    # 传入输入数据
    result = graph.invoke({"question": "什么是 LangGraph？"})
    print("\n=== 最终结果 ===")
    print(result)