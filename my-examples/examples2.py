from langgraph.graph import StateGraph
from typing_extensions import TypedDict, Optional
from langgraph.graph import START, END

# 定义输入的模式
class InputState(TypedDict):
    question: str
    llm_answer: Optional[str]  # 表示 answer 可以是 str 类型，也可以是 None

# 定义输出的模式
class OutputState(TypedDict):
    answer: str

# 将 InputState 和 OutputState 这两个 TypedDict 类型合并成一个更全面的字典类型。
class OverallState(InputState, OutputState):
    pass

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import getpass
import os

# DeepSeek API 配置
if not os.environ.get("DEEPSEEK_API_KEY"):
    os.environ["DEEPSEEK_API_KEY"] = getpass.getpass("Enter your DeepSeek API key: ")

# 初始化 DeepSeek 模型（兼容 OpenAI API）
llm = ChatOpenAI(
    model="deepseek-chat",  # DeepSeek 模型名称
    openai_api_key="sk-1f1f27b8e0524422bab4b8517b1068ca",
    openai_api_base="https://api.deepseek.com",  # DeepSeek API 地址
    temperature=0.7,
)

# 创建提示模板
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个有帮助的AI助手。"),
    ("human", "{question}")
])

# 定义 LLM 节点函数
def llm_node(state: InputState):
    print("正在调用 DeepSeek 模型...")
    # 创建链
    chain = prompt | llm
    # 调用模型
    response = chain.invoke({"question": state["question"]})
    return {"llm_answer": response.content}
def language_node(state: InputState):
    print("Calling English node...")
    messages = [
        ("system","无论你接收到什么语言的文本，请翻译成日文",),
        ("human", state["llm_answer"])
    ]
    response = llm.invoke(messages)
    return {"answer": response.content}
# 明确指定它的输入和输出数据的结构或模式
builder = StateGraph(OverallState, input_schema=InputState, output_schema=OutputState)

# 添加节点
builder.add_node("llm_node", llm_node)
builder.add_node("language_node", language_node)

# 添加边
builder.add_edge(START, "llm_node")
builder.add_edge("llm_node","language_node")
builder.add_edge("language_node", END)

# 编译图
graph = builder.compile()

# 运行图
if __name__ == "__main__":
    result = graph.invoke({"question": "什么是langgraph 呢。"})
    print("\n=== DeepSeek 回答 ===")
    print(result["answer"])    