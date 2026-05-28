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
from typing import TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from langgraph.stream import ProtocolEvent, StreamChannel, StreamTransformer
from langgraph.config import get_stream_writer


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
    
    config = {"configurable": {"thread_id": "demo-thread-1"}}
    
    # 第一次运行 - 直到中断点
    print("\n🚀 第一阶段: 运行直到中断点")
    stream = graph.stream_events(input_data, config=config, version="v3")
    
    for snapshot in stream.values:
        print(f"  [状态] stage={snapshot.get('stage')}")
    
    # 检查是否中断
    if stream.interrupted:
        print("\n⏸️  执行已暂停")
        print(f"  中断信息: {stream.interrupts}")
        
        # 模拟人工决策
        print("\n👤 人工决策: approve")
        
        # 使用 Command 恢复执行
        print("\n▶️  第二阶段: 恢复执行")
        resume_stream = graph.stream_events(
            Command(resume={"user_decision": "approve"}),
            config=config,
            version="v3"
        )
        
        for snapshot in resume_stream.values:
            print(f"  [状态] stage={snapshot.get('stage')}")
        
        print("\n✅ 最终输出:")
        final_output = resume_stream.output
        print(f"  阶段: {final_output['stage']}")
        print(f"  决策: {final_output['user_decision']}")
    else:
        print("\n⚠️  未检测到中断")
        print("  说明: interrupt_before 会在节点执行前暂停")
        print("  由于这是演示,我们直接使用 update_state 来模拟人工输入")
        
        # 获取当前状态
        state = graph.get_state(config)
        print(f"  当前状态: {state.values.get('stage')}")
        print(f"  下一个节点: {state.next}")
        
        if state.next:
            # 更新状态以提供决策
            graph.update_state(config, {"user_decision": "approve"})
            print("\n👤 人工决策: approve (通过 update_state)")
            
            # 继续执行
            print("\n▶️  继续执行:")
            resume_stream = graph.stream_events(None, config=config, version="v3")
            
            for snapshot in resume_stream.values:
                print(f"  [状态] stage={snapshot.get('stage')}")
            
            print("\n✅ 最终输出:")
            final_output = resume_stream.output
            print(f"  阶段: {final_output['stage']}")
            print(f"  决策: {final_output['user_decision']}")


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
    
    graph = create_progress_graph()
    
    input_data = {"data": "", "step": 0}
    
    # 注册自定义转换器 - 传递类而不是实例
    stream = graph.stream_events(
        input_data,
        version="v3",
        transformers=[ProgressTransformer]  # 传递类,不是实例
    )
    
    print("\n📊 进度追踪（通过自定义转换器）:")
    progress_count = 0
    
    # 从 stream.extensions 访问自定义投影
    for progress in stream.extensions["progress"]:
        progress_count += 1
        print(f"  [{progress['step']}] {progress['percent']}% - {progress['message']}")
    
    print("\n✅ 最终输出:")
    final_output = stream.output
    print(f"  数据: {final_output['data']}")
    print(f"  步骤: {final_output['step']}")
    print(f"  捕获的进度事件: {progress_count} 个")


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
