"""
LangGraph Event Streaming 综合示例
严格按照官方文档 https://docs.langchain.com/oss/python/langgraph/event-streaming

核心概念：
1. Event Streaming 是 LangGraph v1.2+ 推荐的流式 API
2. 使用 stream_events(version="v3") 或 astream_events(version="v3")
3. 提供类型化的投影（projections）：
   - stream.messages: 流式消息输出
   - stream.values: 状态快照
   - stream.output: 最终输出
   - stream.subgraphs: 子图执行
   - stream.interrupts: 中断信息
   - stream: 原始协议事件
4. 支持并发消费多个投影（asyncio.gather）
5. 支持交错消费（stream.interleave）
6. 支持自定义 StreamTransformer

应用场景：
- 实时显示 LLM 输出（token-by-token）
- 监控子图执行
- 追踪状态变化
- 工具调用监控
- 自定义进度事件
"""

import asyncio
import os
from typing import TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from langgraph.stream import ProtocolEvent, StreamChannel, StreamTransformer
from langgraph.config import get_stream_writer
from langchain_openai import ChatOpenAI

# 初始化 LLM (使用 DeepSeek)
llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
    openai_api_base="https://api.deepseek.com",
    temperature=0.7,
    streaming=True  # 启用流式输出
)

os.environ["DEEPSEEK_API_KEY"] = "sk-1f1f27b8e0524422bab4b8517b1068ca"

# ============================================================================
# 场景 1: 基础流式输出 - 使用 stream.values
# ============================================================================

class BasicState(TypedDict):
    """基础状态"""
    messages: list[dict]
    counter: int


def create_basic_graph():
    """创建基础图 - 演示 stream.values"""
    
    def step1(state: BasicState) -> BasicState:
        """第一步"""
        return {
            "messages": state.get("messages", []) + [{"role": "assistant", "content": "步骤1完成"}],
            "counter": state.get("counter", 0) + 1
        }
    
    def step2(state: BasicState) -> BasicState:
        """第二步"""
        return {
            "messages": state.get("messages", []) + [{"role": "assistant", "content": "步骤2完成"}],
            "counter": state.get("counter", 0) + 1
        }
    
    graph = StateGraph(BasicState)
    graph.add_node("step1", step1)
    graph.add_node("step2", step2)
    graph.add_edge(START, "step1")
    graph.add_edge("step1", "step2")
    graph.add_edge("step2", END)
    
    return graph.compile()


def demo_basic_streaming():
    """演示基础流式输出 - 同步版本"""
    print("\n" + "="*80)
    print("场景 1: 基础流式输出 - stream.values (同步)")
    print("="*80)
    
    graph = create_basic_graph()
    
    input_data = {
        "messages": [{"role": "user", "content": "开始"}],
        "counter": 0
    }
    
    # 使用 stream_events (同步版本)
    stream = graph.stream_events(input_data, version="v3")
    
    print("\n📊 流式状态快照:")
    for snapshot in stream.values:
        print(f"  [状态] counter={snapshot.get('counter')}, messages={len(snapshot.get('messages', []))}")
    
    print("\n✅ 最终输出:")
    final_state = stream.output
    print(f"  计数器: {final_state['counter']}")
    print(f"  消息数: {len(final_state['messages'])}")


# ============================================================================
# 场景 2: 异步并发消费多个投影
# ============================================================================

async def demo_async_multiple_projections():
    """演示异步并发消费多个投影"""
    print("\n" + "="*80)
    print("场景 2: 异步并发消费多个投影 - asyncio.gather")
    print("="*80)
    
    graph = create_basic_graph()
    
    input_data = {
        "messages": [{"role": "user", "content": "开始"}],
        "counter": 0
    }
    
    # 使用 astream_events (异步版本)
    stream = await graph.astream_events(input_data, version="v3")
    
    # 定义并发消费函数
    async def consume_values():
        """消费状态快照"""
        print("\n📊 状态流:")
        async for snapshot in stream.values:
            print(f"  [状态] counter={snapshot.get('counter')}")
    
    async def consume_raw_events():
        """消费原始事件"""
        print("\n🔍 原始事件流:")
        event_count = 0
        async for event in stream:
            if event["method"] == "values":
                event_count += 1
                print(f"  [事件 #{event['seq']}] method={event['method']}")
                if event_count >= 3:  # 只显示前3个
                    break
    
    # 并发消费
    await asyncio.gather(
        consume_values(),
        consume_raw_events()
    )
    
    print("\n✅ 最终输出:")
    final_state = await stream.output()  # 异步版本需要 await
    print(f"  计数器: {final_state['counter']}")


# ============================================================================
# 场景 3: 交错消费多个投影 - stream.interleave (同步)
# ============================================================================

class ChatState(TypedDict):
    """聊天应用状态"""
    messages: list[dict]
    user_query: str
    thinking_steps: list[str]
    final_answer: str


def create_chat_graph():
    """创建聊天应用图 - 模拟 LLM 生成消息"""
    
    def analyze_query(state: ChatState) -> ChatState:
        """分析用户查询"""
        return {
            **state,
            "thinking_steps": ["正在分析问题..."],
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": "让我思考一下...", "type": "thinking"}
            ]
        }
    
    def generate_response(state: ChatState) -> ChatState:
        """生成回复"""
        query = state.get("user_query", "")
        return {
            **state,
            "thinking_steps": state.get("thinking_steps", []) + ["正在生成回复..."],
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": f"关于'{query}'的回答", "type": "response"}
            ]
        }
    
    def finalize_answer(state: ChatState) -> ChatState:
        """完成回答"""
        return {
            **state,
            "thinking_steps": state.get("thinking_steps", []) + ["回答完成"],
            "final_answer": "这是最终答案",
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": "回答完成!", "type": "done"}
            ]
        }
    
    graph = StateGraph(ChatState)
    graph.add_node("analyze", analyze_query)
    graph.add_node("generate", generate_response)
    graph.add_node("finalize", finalize_answer)
    
    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", "generate")
    graph.add_edge("generate", "finalize")
    graph.add_edge("finalize", END)
    
    return graph.compile()


def demo_interleaved_streaming():
    """演示交错消费 - 对比正反例"""
    print("\n" + "="*80)
    print("场景 3: 交错消费多个投影 - stream.interleave (同步)")
    print("="*80)
    print("🎯 场景: 聊天应用 - 需要同时显示 LLM 输出(messages) 和 状态变化(values)")
    print()
    
    graph = create_chat_graph()
    
    input_data = {
        "messages": [{"role": "user", "content": "什么是 LangGraph?"}],
        "user_query": "什么是 LangGraph",
        "thinking_steps": [],
        "final_answer": ""
    }
    
    # ========================================================================
    # ❌ 反例: 不使用 interleave - 只能顺序消费,无法保持时序
    # ========================================================================
    print("="*80)
    print("❌ 反例: 不使用 interleave - 分别消费投影")
    print("="*80)
    print("问题: 先消费所有 values,再消费所有 messages,丢失了时序关系")
    print()
    
    stream1 = graph.stream_events(input_data, version="v3")
    
    print("� 第一步: 消费所有状态快照 (values)")
    print("-" * 60)
    for snapshot in stream1.values:
        steps = snapshot.get('thinking_steps', [])
        if steps:
            print(f"  [STATE] 思考步骤: {steps[-1]}")
    
    # 注意: 此时 stream1 已经被消费完了,无法再消费 messages!
    # 这就是问题所在 - 我们需要重新创建流
    
    stream1_new = graph.stream_events(input_data, version="v3")
    
    print("\n💬 第二步: 消费所有消息 (messages)")
    print("-" * 60)
    # 注意: 在真实的 LLM 场景中,messages 投影会有内容
    # 但我们的模拟图没有真正的 LLM,所以这里可能为空
    message_count = 0
    for message in stream1_new.messages:
        message_count += 1
        print(f"  [MESSAGE] {message}")
    
    if message_count == 0:
        print("  (本示例没有 LLM,所以 messages 投影为空)")
        print("  (在真实场景中,这里会有 LLM 的 token 流)")
    
    print("\n⚠️  问题:")
    print("  1. 需要创建两个流,浪费资源")
    print("  2. 无法保持事件的时序关系")
    print("  3. 用户体验差 - 先看到所有状态,再看到所有消息")
    print("  4. 无法实现'边思考边输出'的效果")
    
    # ========================================================================
    # ✅ 正例: 使用 interleave - 按时序交错消费
    # ========================================================================
    print("\n" + "="*80)
    print("✅ 正例: 使用 interleave - 按时序交错消费")
    print("="*80)
    print("优势: 按事件到达顺序交错显示,保持时序关系")
    print()
    
    stream2 = graph.stream_events(input_data, version="v3")
    
    print("🔀 交错输出 (按时间顺序):")
    print("-" * 60)
    
    event_num = 0
    # 同时交错消费 values 和 messages (如果有的话)
    for name, item in stream2.interleave("values"):
        event_num += 1
        
        if name == "values":
            # 状态快照
            steps = item.get('thinking_steps', [])
            messages = item.get('messages', [])
            
            # 显示最新的思考步骤
            if steps:
                print(f"  [{event_num}] 📊 [STATE] 思考: {steps[-1]}")
            
            # 显示最新的消息
            if messages:
                last_msg = messages[-1]
                msg_type = last_msg.get('type', 'unknown')
                content = last_msg.get('content', '')
                print(f"  [{event_num}] 💬 [MESSAGE] [{msg_type}] {content}")
    
    print("\n✅ 优势:")
    print("  1. 只需一个流,高效")
    print("  2. 保持事件的严格时序关系")
    print("  3. 用户体验好 - 实时看到思考和输出过程")
    print("  4. 可以实现'边思考边输出'的效果")
    
    # ========================================================================
    # 💡 真实场景对比
    # ========================================================================
    print("\n" + "="*80)
    print("💡 真实聊天应用场景对比")
    print("="*80)
    
    print("\n❌ 不使用 interleave 的用户体验:")
    print("-" * 60)
    print("  用户: 什么是 LangGraph?")
    print("  [等待...]")
    print("  [等待...]")
    print("  [等待...]")
    print("  助手: LangGraph 是一个...")
    print("  (用户看不到思考过程,体验差)")
    
    print("\n✅ 使用 interleave 的用户体验:")
    print("-" * 60)
    print("  用户: 什么是 LangGraph?")
    print("  助手: [正在分析问题...]")
    print("  助手: 让我思考一下...")
    print("  助手: [正在生成回复...]")
    print("  助手: 关于'什么是 LangGraph'的回答")
    print("  助手: [回答完成]")
    print("  助手: 回答完成!")
    print("  (用户实时看到思考和输出,体验好)")
    
    print("\n" + "="*80)
    print("� 官方文档示例 (真实 LLM 场景):")
    print("="*80)
    print("""
    # 在真实的 LLM 聊天应用中:
    stream = graph.stream_events(input, version="v3")
    
    for name, item in stream.interleave("values", "messages"):
        if name == "values":
            # 显示状态变化 (如: 正在调用工具...)
            print(f"[状态] {item.get('status')}")
        
        elif name == "messages":
            # 显示 LLM 输出 (逐 token 流式输出)
            for token in item.text:
                print(token, end="", flush=True)
    
    # 这样用户可以:
    # 1. 实时看到 LLM 的思考过程 (values)
    # 2. 实时看到 LLM 的输出 (messages)
    # 3. 两者按时间顺序交错显示,体验流畅
    """)
    
    print("\n🎯 核心要点:")
    print("  • interleave 的价值在于'时序'和'交错'")
    print("  • 适用于需要同时监控多个投影的场景")
    print("  • 聊天应用、多智能体、实时监控都需要这个功能")
    print("  • 同步代码用 interleave,异步代码用 asyncio.gather")
    
    print("\n✅ 最终输出:")
    final_output = stream2.output
    print(f"  最终答案: {final_output.get('final_answer')}")
    print(f"  思考步骤数: {len(final_output.get('thinking_steps', []))}")
    print(f"  消息数: {len(final_output.get('messages', []))}")


# ============================================================================
# 场景 4: 人机协作中断和恢复
# ============================================================================

class HumanInLoopState(TypedDict):
    """人机协作状态"""
    messages: list[dict]
    user_decision: str | None
    stage: str


def create_human_in_loop_graph():
    """创建人机协作图"""
    from langgraph.types import interrupt
    
    def analyze(state: HumanInLoopState) -> HumanInLoopState:
        """分析阶段"""
        return {
            **state,
            "stage": "分析完成",
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": "分析完成，需要人工决策"}
            ]
        }
    
    def request_decision(state: HumanInLoopState) -> HumanInLoopState:
        """请求人工决策 - 使用 interrupt"""
        decision = interrupt({"question": "是否批准？", "options": ["approve", "reject"]})
        return {
            **state,
            "user_decision": decision,
            "stage": "等待决策"
        }
    
    def execute(state: HumanInLoopState) -> HumanInLoopState:
        """执行阶段"""
        decision = state.get("user_decision", "reject")
        result = "已批准" if decision == "approve" else "已拒绝"
        return {
            **state,
            "stage": f"执行完成: {result}",
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": result}
            ]
        }
    
    graph = StateGraph(HumanInLoopState)
    graph.add_node("analyze", analyze)
    graph.add_node("request_decision", request_decision)
    graph.add_node("execute", execute)
    
    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", "request_decision")
    graph.add_edge("request_decision", "execute")
    graph.add_edge("execute", END)
    
    # 必须使用 checkpointer 才能支持中断
    return graph.compile(
        checkpointer=InMemorySaver(),
        interrupt_before=["request_decision"]
    )


def demo_human_in_loop():
    """演示人机协作中断和恢复"""
    print("\n" + "="*80)
    print("场景 4: 人机协作中断和恢复")
    print("="*80)
    
    graph = create_human_in_loop_graph()
    
    input_data = {
        "messages": [{"role": "user", "content": "执行任务"}],
        "user_decision": None,
        "stage": "初始化"
    }
    
    config = {"configurable": {"thread_id": "demo-thread-4"}}
    
    # 第一次运行 - 直到中断点
    print("\n🚀 第一阶段: 运行直到中断点")
    print("说明: interrupt_before=['request_decision'] 会在该节点执行前暂停")
    print()
    
    stream = graph.stream_events(input_data, config=config, version="v3")
    
    # 消费状态快照
    for snapshot in stream.values:
        print(f"  [状态] stage={snapshot.get('stage')}")
    
    # 重要: 在消费完流后,检查图的状态而不是 stream.interrupted
    # 因为 stream_events 的 interrupted 属性可能不可靠
    state_snapshot = graph.get_state(config)
    
    print(f"\n📊 检查图状态:")
    print(f"  当前阶段: {state_snapshot.values.get('stage')}")
    print(f"  下一个节点: {state_snapshot.next}")
    print(f"  是否有待执行节点: {bool(state_snapshot.next)}")
    
    # 检查是否有待执行的节点 (表示中断)
    if state_snapshot.next:
        print("\n⏸️  执行已在中断点暂停!")
        print(f"  等待执行的节点: {state_snapshot.next}")
        print(f"  这就是 interrupt_before 的效果")
        
        # 模拟人工决策
        print("\n👤 人工决策: approve")
        print("  方式1: 使用 update_state 更新状态")
        
        # 更新状态以提供决策
        graph.update_state(config, {"user_decision": "approve"})
        
        # 继续执行
        print("\n▶️  第二阶段: 恢复执行")
        resume_stream = graph.stream_events(None, config=config, version="v3")
        
        for snapshot in resume_stream.values:
            print(f"  [状态] stage={snapshot.get('stage')}")
        
        print("\n✅ 最终输出:")
        final_output = resume_stream.output
        print(f"  阶段: {final_output['stage']}")
        print(f"  决策: {final_output['user_decision']}")
        
        # 展示另一种恢复方式
        print("\n" + "="*80)
        print("💡 另一种恢复方式: 使用 Command(resume=...)")
        print("="*80)
        
        # 重新运行演示
        config2 = {"configurable": {"thread_id": "demo-thread-4-alt"}}
        
        # 第一次运行
        stream_alt = graph.stream_events(input_data, config=config2, version="v3")
        for _ in stream_alt.values:
            pass  # 消费到中断点
        
        # 使用 Command 恢复
        print("使用 Command(resume={...}) 恢复执行:")
        resume_stream_alt = graph.stream_events(
            Command(resume={"user_decision": "reject"}),
            config=config2,
            version="v3"
        )
        
        for snapshot in resume_stream_alt.values:
            stage = snapshot.get('stage', '')
            if '执行完成' in stage:
                print(f"  [状态] {stage}")
        
        final_alt = resume_stream_alt.output
        print(f"  决策结果: {final_alt['user_decision']}")
    else:
        print("\n⚠️  未检测到中断点")
        print("  这不应该发生,请检查图配置")
    
    # 解释说明
    print("\n" + "="*80)
    print("📚 关键知识点:")
    print("="*80)
    print("1. interrupt_before=['node'] 在节点执行前暂停")
    print("2. 使用 graph.get_state(config) 检查是否中断")
    print("3. state.next 不为空表示有待执行的节点 (中断)")
    print("4. 恢复方式:")
    print("   • update_state() + stream_events(None, config)")
    print("   • stream_events(Command(resume={...}), config)")
    print("5. 必须使用 checkpointer 和 thread_id")
    print("6. stream.interrupted 在 stream_events 中可能不可靠")
    print("   推荐使用 graph.get_state(config).next 来判断")


# ============================================================================
# 场景 5: 原始协议事件流
# ============================================================================

def demo_raw_protocol_events():
    """演示原始协议事件流"""
    print("\n" + "="*80)
    print("场景 5: 原始协议事件流 - 底层事件访问")
    print("="*80)
    
    graph = create_basic_graph()
    
    input_data = {
        "messages": [{"role": "user", "content": "开始"}],
        "counter": 0
    }
    
    stream = graph.stream_events(input_data, version="v3")
    
    print("\n🔍 原始协议事件:")
    event_count = 0
    for event in stream:
        event_count += 1
        namespace = event["params"]["namespace"]
        method = event["method"]
        seq = event["seq"]
        
        # 格式化命名空间
        ns_str = " -> ".join(namespace) if namespace else "root"
        
        print(f"  事件 #{seq}: [{method}] namespace={ns_str}")
        
        # 只显示前10个事件
        if event_count >= 10:
            print("  ... (更多事件)")
            break
    
    print(f"\n✅ 总事件数: {event_count}+")


# ============================================================================
# 场景 6: 自定义 StreamTransformer - 进度追踪
# ============================================================================

class ProgressEvent(TypedDict):
    """进度事件"""
    step: str
    percent: int
    message: str


class ProgressTransformer(StreamTransformer):
    """进度追踪转换器"""
    
    # 声明需要的流模式
    required_stream_modes = ("custom",)
    
    def __init__(self, scope: tuple[str, ...] = ()) -> None:
        super().__init__(scope)
        # 创建命名通道 - 会出现在主事件流中
        self.progress = StreamChannel[ProgressEvent]("progress")
    
    def init(self) -> dict:
        """初始化投影"""
        return {"progress": self.progress}
    
    def process(self, event: ProtocolEvent) -> bool:
        """处理每个协议事件"""
        if event["method"] != "custom":
            return True
        
        data = event["params"]["data"]
        if isinstance(data, dict) and data.get("type") == "progress":
            # 推送到进度通道
            self.progress.push({
                "step": data["step"],
                "percent": data["percent"],
                "message": data["message"]
            })
        
        return True



def create_progress_graph():
    """创建带进度追踪的图"""
    
    class ProgressState(TypedDict):
        data: str
        step: int
    
    def step_a(state: ProgressState) -> ProgressState:
        # 使用 get_stream_writer 发送自定义事件
        writer = get_stream_writer()
        writer({"type": "progress", "step": "A", "percent": 33, "message": "步骤 A 完成"})
        return {"data": "A", "step": 1}
    
    def step_b(state: ProgressState) -> ProgressState:
        writer = get_stream_writer()
        writer({"type": "progress", "step": "B", "percent": 66, "message": "步骤 B 完成"})
        return {"data": state["data"] + "B", "step": 2}
    
    def step_c(state: ProgressState) -> ProgressState:
        writer = get_stream_writer()
        writer({"type": "progress", "step": "C", "percent": 100, "message": "步骤 C 完成"})
        return {"data": state["data"] + "C", "step": 3}
    
    graph = StateGraph(ProgressState)
    graph.add_node("step_a", step_a)
    graph.add_node("step_b", step_b)
    graph.add_node("step_c", step_c)
    
    graph.add_edge(START, "step_a")
    graph.add_edge("step_a", "step_b")
    graph.add_edge("step_b", "step_c")
    graph.add_edge("step_c", END)
    
    return graph.compile()


def demo_custom_transformer():
    """演示自定义 StreamTransformer"""
    print("\n" + "="*80)
    print("场景 6: 自定义 StreamTransformer - 进度追踪")
    print("="*80)
    
    # ========================================================================
    # 💡 什么是 StreamTransformer?
    # ========================================================================
    print("\n💡 什么是 StreamTransformer?")
    print("="*60)
    print("""
StreamTransformer 是一个强大的机制,用于:
1. 观察和转换原始协议事件
2. 创建自定义的投影 (projections)
3. 将底层事件转换为应用层需要的格式

工作流程:
  图执行 → 原始事件 → StreamTransformer → 自定义投影 → 应用代码
  
  例如:
  节点发送 custom 事件 → ProgressTransformer 处理 → progress 投影 → UI 显示进度条
    """)
    
    # ========================================================================
    # 📖 ProgressTransformer 的作用
    # ========================================================================
    print("\n📖 ProgressTransformer 的作用:")
    print("="*60)
    print("""
1. 监听 'custom' 通道的事件
2. 过滤出 type='progress' 的事件
3. 将这些事件推送到 'progress' 投影
4. 应用代码通过 stream.extensions['progress'] 访问

代码结构:
  class ProgressTransformer(StreamTransformer):
      required_stream_modes = ("custom",)  # 声明需要监听 custom 通道
      
      def __init__(self, scope):
          self.progress = StreamChannel("progress")  # 创建投影通道
      
      def init(self):
          return {"progress": self.progress}  # 注册投影
      
      def process(self, event):
          if event["method"] == "custom":  # 监听 custom 事件
              if event["data"].get("type") == "progress":
                  self.progress.push(event["data"])  # 推送到投影
          return True
    """)
    
    # ========================================================================
    # 🎯 实际演示
    # ========================================================================
    print("\n🎯 实际演示:")
    print("="*60)
    
    graph = create_progress_graph()
    input_data = {"data": "", "step": 0}
    
    print("\n方式1: 不使用 StreamTransformer (手动处理)")
    print("-" * 60)
    
    # 不使用转换器,手动处理原始事件
    stream_raw = graph.stream_events(input_data, version="v3")
    
    progress_events_manual = []
    for event in stream_raw:
        if event["method"] == "custom":
            data = event["params"]["data"]
            if isinstance(data, dict) and data.get("type") == "progress":
                progress_events_manual.append(data)
                print(f"  [手动] {data['step']} - {data['percent']}% - {data['message']}")
    
    print(f"\n  手动捕获: {len(progress_events_manual)} 个进度事件")
    print("  ⚠️  问题: 需要手动过滤和处理,代码重复")
    
    print("\n方式2: 使用 StreamTransformer (自动处理)")
    print("-" * 60)
    
    # 使用转换器,自动处理
    stream = graph.stream_events(
        input_data,
        version="v3",
        transformers=[ProgressTransformer]  # 传递类,不是实例
    )
    
    progress_count = 0
    # 从 stream.extensions 访问自定义投影
    for progress in stream.extensions["progress"]:
        progress_count += 1
        print(f"  [自动] {progress['step']} - {progress['percent']}% - {progress['message']}")
    
    print(f"\n  自动捕获: {progress_count} 个进度事件")
    print("  ✅ 优势: 代码简洁,可复用,类型安全")
    
    # ========================================================================
    # 🎯 实际应用场景
    # ========================================================================
    print("\n" + "="*80)
    print("🎯 StreamTransformer 的实际应用场景:")
    print("="*80)
    print("""
1. 进度追踪:
   • 将 custom 事件转换为进度百分比
   • UI 显示进度条
   
2. Token 统计:
   • 监听 messages 通道
   • 统计 LLM 使用的 token 数量
   • 计算成本
   
3. 工具调用监控:
   • 监听 tools 通道
   • 记录工具调用次数和耗时
   • 生成调用报告
   
4. 错误收集:
   • 监听所有通道
   • 收集错误和警告
   • 生成错误报告
   
5. 自定义日志:
   • 将事件转换为结构化日志
   • 发送到日志系统
    """)
    
    # ========================================================================
    # 💡 关键要点
    # ========================================================================
    print("\n💡 关键要点:")
    print("="*60)
    print("""
1. StreamTransformer 是观察者模式
   • 不修改原始事件
   • 只创建新的投影
   
2. required_stream_modes 很重要
   • 声明需要监听的通道
   • 未声明的通道不会被发送
   
3. StreamChannel 是投影的容器
   • 命名通道: StreamChannel("name") - 出现在主事件流
   • 匿名通道: StreamChannel() - 仅作为侧通道
   
4. 传递类而不是实例
   • transformers=[MyTransformer] ✅
   • transformers=[MyTransformer()] ❌
   • 原因: LangGraph 需要为每个流创建独立的实例
   
5. 访问自定义投影
   • stream.extensions["projection_name"]
   • 返回一个可迭代对象
    """)
    
    print("\n✅ 最终输出:")
    final_output = stream.output
    print(f"  数据: {final_output['data']}")
    print(f"  步骤: {final_output['step']}")
    print(f"  捕获的进度事件: {progress_count} 个")
    
    print("\n📚 扩展阅读:")
    print("  • 查看 EVENT_STREAMING_GUIDE.md 了解更多")
    print("  • 官方文档: https://docs.langchain.com/oss/python/langgraph/event-streaming")


# ============================================================================
# 主函数
# ============================================================================

async def main():
    """运行所有演示"""
    print("\n" + "="*80)
    print("LangGraph Event Streaming 综合示例")
    print("严格按照官方文档: https://docs.langchain.com/oss/python/langgraph/event-streaming")
    print("="*80)
    
    # 场景 1: 基础流式输出 (同步)
    demo_basic_streaming()
    
    # 场景 2: 异步并发消费
    await demo_async_multiple_projections()
    
    # 场景 3: 交错消费 (同步)
    demo_interleaved_streaming()
    
    # 场景 4: 人机协作中断和恢复 (同步)
    demo_human_in_loop()
    
    # 场景 5: 原始协议事件 (同步)
    demo_raw_protocol_events()
    
    # 场景 6: 自定义 StreamTransformer (同步)
    demo_custom_transformer()
    
    print("\n" + "="*80)
    print("✅ 所有演示完成！")
    print("="*80)
    
    print("\n📚 关键要点:")
    print("1. stream_events(version='v3') 是推荐的流式 API")
    print("2. 同步: stream_events(), 异步: astream_events()")
    print("3. stream.values: 状态快照流")
    print("4. stream.output: 最终输出 (同步是属性，异步需要 await)")
    print("5. stream.interleave(): 交错消费多个投影 (同步)")
    print("6. asyncio.gather(): 并发消费多个投影 (异步)")
    print("7. stream.interrupted 和 stream.interrupts: 人机协作")
    print("8. StreamTransformer: 自定义投影，通过 stream.extensions 访问")
    print("9. get_stream_writer(): 在节点中发送自定义事件")
    
    print("\n🎯 应用场景:")
    print("- 实时 UI 更新（聊天界面、进度条）")
    print("- 多智能体协作监控")
    print("- 工具调用追踪")
    print("- 自定义进度和状态事件")
    print("- 人机协作工作流")
    print("- 调试和可观测性")


if __name__ == "__main__":
    asyncio.run(main())
