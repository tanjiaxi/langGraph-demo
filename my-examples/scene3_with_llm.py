"""
场景 3: 真实 LLM 演示 - 交错消费 messages 和 values
展示 stream.interleave() 的真正价值
"""

import os
from typing import TypedDict
from langgraph.graph import StateGraph, START, END, MessagesState
from langchain_openai import ChatOpenAI

# 初始化 LLM
llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
    openai_api_base="https://api.deepseek.com",
    temperature=0.7,
    streaming=True  # 启用流式输出
)


class ChatState(MessagesState):
    """聊天应用状态"""
    thinking_steps: list[str]
    final_answer: str


def create_chat_graph_with_llm():
    """创建真实的聊天应用图"""
    
    def analyze_query(state: ChatState) -> ChatState:
        """分析用户查询"""
        return {
            "thinking_steps": ["正在分析问题..."],
        }
    
    def call_llm(state: ChatState) -> ChatState:
        """调用 LLM 生成回复"""
        messages = state["messages"]
        
        # 调用 LLM (会生成流式输出)
        response = llm.invoke(messages)
        
        return {
            "messages": [response],
            "thinking_steps": state.get("thinking_steps", []) + ["LLM 回复完成"],
            "final_answer": response.content
        }
    
    def finalize_answer(state: ChatState) -> ChatState:
        """完成回答"""
        return {
            "thinking_steps": state.get("thinking_steps", []) + ["回答完成"],
        }
    
    graph = StateGraph(ChatState)
    graph.add_node("analyze", analyze_query)
    graph.add_node("call_llm", call_llm)
    graph.add_node("finalize", finalize_answer)
    
    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", "call_llm")
    graph.add_edge("call_llm", "finalize")
    graph.add_edge("finalize", END)
    
    return graph.compile()


def demo_with_real_llm():
    """使用真实 LLM 演示 interleave"""
    print("\n" + "="*80)
    print("🎯 真实 LLM 演示: 交错消费 messages 和 values")
    print("="*80)
    
    graph = create_chat_graph_with_llm()
    
    input_data = {
        "messages": [{"role": "user", "content": "用10句话解释什么是 LangGraph"}],
        "thinking_steps": [],
        "final_answer": ""
    }
    
    # ========================================================================
    # ❌ 反例: 不使用 interleave
    # ========================================================================
    print("\n❌ 反例: 不使用 interleave - 分别消费投影")
    print("="*60)
    
    stream1 = graph.stream_events(input_data, version="v3")
    
    print("📊 第一步: 消费所有状态快照 (values)")
    for snapshot in stream1.values:
        steps = snapshot.get('thinking_steps', [])
        if steps:
            print(f"  [STATE] {steps[-1]}")
    
    # 需要重新创建流
    stream1_new = graph.stream_events(input_data, version="v3")
    
    print("\n💬 第二步: 消费所有消息 (messages)")
    # for message in stream1_new.messages:
    #     text = str(message.text)
    #     print(f"  [MESSAGE] {text}...")
    for message in stream1_new.messages:
        for text in message.text:
            print(text, end="", flush=True)
    print("\n⚠️  问题: 需要两个流,无法保持时序")
    
    # ========================================================================
    # ✅ 正例: 使用 interleave
    # ========================================================================
    print("\n" + "="*80)
    print("✅ 正例: 使用 interleave - 按时序交错消费")
    print("="*60)
    
    stream2 = graph.stream_events(input_data, version="v3")
    
    print("🔀 交错输出 (按时间顺序):\n")
    
    event_num = 0
    # 同时交错消费 values 和 messages
    for name, item in stream2.interleave("values", "messages"):
        event_num += 1
        
        if name == "values":
            # 状态快照
            steps = item.get('thinking_steps', [])
            if steps:
                print(f"  [{event_num}] 📊 [STATE] {steps[-1]}")
        
        elif name == "messages":
            # LLM 消息输出 - 逐 token 流式输出
            print(f"  [{event_num}] 💬 [MESSAGE] ", end="", flush=True)
            for token in item.text:
                print(token, end="", flush=True)
            print()  # 换行
    
    print("\n✅ 优势: 保持时序,实时看到思考和输出过程")
    
    print("\n✅ 最终输出:")
    final_output = stream2.output
    print(f"  答案: {final_output.get('final_answer', '')[:100]}...")
    print(f"  思考步骤: {len(final_output.get('thinking_steps', []))}")


if __name__ == "__main__":
    # 检查 API Key
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("⚠️  请设置 DEEPSEEK_API_KEY 环境变量")
        print("   export DEEPSEEK_API_KEY='your-api-key'")
    else:
        demo_with_real_llm()
