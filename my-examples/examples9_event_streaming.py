"""
LangGraph Event Streaming 综合示例
展示最新的 stream_events API (v3) 和各种应用场景

核心概念：
1. Event Streaming 是 LangGraph v1.2+ 推荐的流式 API
2. 提供类型化的投影（projections）：messages, values, subgraphs, output()
3. 支持并发消费多个投影
4. 支持人机协作中断和恢复
5. 支持自定义事件（通过 get_stream_writer）

应用场景：
- 实时显示 LLM 输出（token-by-token）
- 监控子图执行
- 追踪状态变化
- 工具调用监控
- 自定义进度事件
"""

import asyncio
from typing import TypedDict, Annotated, Literal
import operator
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt


# ============================================================================
# 场景 1: 基础事件流 - Token 级别的 LLM 输出流
# ============================================================================

class BasicState(TypedDict):
    """基础状态"""
    messages: list[dict]
    result: str


def create_basic_streaming_graph():
    """创建基础流式图 - 模拟 LLM 输出"""
    
    def llm_node(state: BasicState) -> BasicState:
        """模拟 LLM 生成响应"""
        # 在实际应用中，这里会调用真实的 LLM
        # 这里我们模拟逐字符生成
        response = "LangGraph 是一个强大的工作流编排框架，支持复杂的多智能体协作。"
        
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "result": response
        }
    
    graph = StateGraph(BasicState)
    graph.add_node("llm", llm_node)
    graph.add_edge(START, "llm")
    graph.add_edge("llm", END)
    
    return graph.compile()


async def demo_basic_streaming():
    """演示基础流式输出"""
    print("\n" + "="*80)
    print("场景 1: 基础事件流 - Token 级别的 LLM 输出")
    print("="*80)
    
    graph = create_basic_streaming_graph()
    
    input_data = {
        "messages": [{"role": "user", "content": "介绍一下 LangGraph"}],
        "result": ""
    }
    
    # 使用 astream 获取最终状态
    print("\n📝 流式输出消息:")
    final_state = None
    async for state in graph.astream(input_data):
        final_state = state
        # 获取节点名称和状态
        for node_name, node_state in state.items():
            if "result" in node_state:
                result = node_state["result"]
                # 模拟逐字符输出
                for char in result:
                    print(char, end="", flush=True)
    
    print("\n\n✅ 最终状态:")
    if final_state:
        node_name = list(final_state.keys())[0]
        print(f"结果: {final_state[node_name].get('result', 'N/A')}")



# ============================================================================
# 场景 2: 多投影并发消费 - 同时监控消息、状态和子图
# ============================================================================

class MultiProjectionState(TypedDict):
    """多投影状态"""
    messages: list[dict]
    step_count: int
    processing_status: str


def create_multi_projection_graph():
    """创建多投影图"""
    
    def step1(state: MultiProjectionState) -> MultiProjectionState:
        return {
            **state,
            "step_count": state.get("step_count", 0) + 1,
            "processing_status": "Step 1 完成"
        }
    
    def step2(state: MultiProjectionState) -> MultiProjectionState:
        return {
            **state,
            "step_count": state.get("step_count", 0) + 1,
            "processing_status": "Step 2 完成"
        }
    
    def step3(state: MultiProjectionState) -> MultiProjectionState:
        return {
            **state,
            "step_count": state.get("step_count", 0) + 1,
            "processing_status": "Step 3 完成",
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": "所有步骤已完成"}
            ]
        }
    
    graph = StateGraph(MultiProjectionState)
    graph.add_node("step1", step1)
    graph.add_node("step2", step2)
    graph.add_node("step3", step3)
    
    graph.add_edge(START, "step1")
    graph.add_edge("step1", "step2")
    graph.add_edge("step2", "step3")
    graph.add_edge("step3", END)
    
    return graph.compile()


async def demo_multi_projection_streaming():
    """演示多投影并发消费"""
    print("\n" + "="*80)
    print("场景 2: 多投影并发消费 - 同时监控消息、状态和子图")
    print("="*80)
    
    graph = create_multi_projection_graph()
    
    input_data = {
        "messages": [{"role": "user", "content": "开始处理"}],
        "step_count": 0,
        "processing_status": "初始化"
    }
    
    # 使用 astream 来获取状态更新
    print("\n📊 状态流:")
    final_state = None
    
    async for state in graph.astream(input_data):
        final_state = state
        node_name = list(state.keys())[0]
        node_state = state[node_name]
        print(f"  [状态] {node_name}: step_count={node_state.get('step_count')}, status={node_state.get('processing_status')}")
    
    print("\n✅ 最终输出:")
    if final_state:
        node_name = list(final_state.keys())[0]
        node_state = final_state[node_name]
        print(f"  步骤数: {node_state.get('step_count', 'N/A')}")
        print(f"  最终状态: {node_state.get('processing_status', 'N/A')}")


# ============================================================================
# 场景 3: 人机协作中断和恢复
# ============================================================================

class HumanInLoopState(TypedDict):
    """人机协作状态"""
    messages: list[dict]
    user_approval: str | None
    processing_stage: str


def create_human_in_loop_graph():
    """创建人机协作图"""
    
    def analyze_request(state: HumanInLoopState) -> HumanInLoopState:
        """分析请求"""
        return {
            **state,
            "processing_stage": "分析完成",
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": "我已分析您的请求，需要执行敏感操作。"}
            ]
        }
    
    def request_approval(state: HumanInLoopState) -> HumanInLoopState:
        """请求人工批准"""
        # 使用 interrupt 暂停执行
        approval = interrupt({
            "question": "是否批准执行此操作？",
            "options": ["approve", "reject", "modify"]
        })
        
        return {
            **state,
            "user_approval": approval,
            "processing_stage": "等待批准"
        }
    
    def execute_action(state: HumanInLoopState) -> HumanInLoopState:
        """执行操作"""
        approval = state.get("user_approval", "reject")
        
        if approval == "approve":
            result = "操作已成功执行"
        elif approval == "reject":
            result = "操作已被拒绝"
        else:
            result = "操作已修改并执行"
        
        return {
            **state,
            "processing_stage": "执行完成",
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": result}
            ]
        }
    
    graph = StateGraph(HumanInLoopState)
    graph.add_node("analyze", analyze_request)
    graph.add_node("request_approval", request_approval)
    graph.add_node("execute", execute_action)
    
    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", "request_approval")
    graph.add_edge("request_approval", "execute")
    graph.add_edge("execute", END)
    
    # 必须使用 checkpointer 才能支持中断和恢复
    return graph.compile(
        checkpointer=InMemorySaver(),
        interrupt_before=["request_approval"]
    )


async def demo_human_in_loop_streaming():
    """演示人机协作中断和恢复"""
    print("\n" + "="*80)
    print("场景 3: 人机协作中断和恢复")
    print("="*80)
    
    graph = create_human_in_loop_graph()
    
    input_data = {
        "messages": [{"role": "user", "content": "执行敏感操作"}],
        "user_approval": None,
        "processing_stage": "初始化"
    }
    
    # 第一次运行 - 直到中断点
    config = {"configurable": {"thread_id": "demo-thread-1"}}
    
    print("\n🚀 第一阶段: 运行直到中断点")
    
    # 使用 invoke 而不是 astream,因为中断会停止流
    try:
        result = await graph.ainvoke(input_data, config=config)
        print(f"  [完成] {result.get('processing_stage', 'N/A')}")
    except Exception as e:
        # 中断会导致执行停止,这是预期的
        pass
    
    # 检查是否中断
    state_snapshot = graph.get_state(config)
    if state_snapshot.next:
        print("\n⏸️  执行已暂停，等待人工输入")
        print(f"  下一个节点: {state_snapshot.next}")
        print(f"  当前状态: {state_snapshot.values.get('processing_stage', 'N/A')}")
        
        # 模拟人工决策
        print("\n👤 人工决策: approve")
        
        # 使用 update_state 提供批准
        graph.update_state(config, {"user_approval": "approve"})
        
        # 继续执行
        print("\n▶️  第二阶段: 恢复执行")
        result = await graph.ainvoke(None, config=config)
        
        print("\n✅ 最终输出:")
        print(f"  处理阶段: {result.get('processing_stage', 'N/A')}")
        print(f"  批准状态: {result.get('user_approval', 'N/A')}")
    else:
        print("\n⚠️  未检测到中断点")


# ============================================================================
# 场景 4: 自定义流转换器 - 进度追踪
# ============================================================================

# ============================================================================
# 场景 4: 自定义事件流 - 进度追踪
# ============================================================================

class CustomTransformerState(TypedDict):
    """自定义事件状态"""
    data: str
    step: int


def create_custom_transformer_graph():
    """创建使用自定义事件的图"""
    from langgraph.config import get_stream_writer
    
    def step_a(state: CustomTransformerState) -> CustomTransformerState:
        # 发送自定义事件
        writer = get_stream_writer()
        writer({"type": "progress", "step": "A", "percent": 33, "message": "步骤 A 完成"})
        
        return {"data": "A", "step": 1}
    
    def step_b(state: CustomTransformerState) -> CustomTransformerState:
        writer = get_stream_writer()
        writer({"type": "progress", "step": "B", "percent": 66, "message": "步骤 B 完成"})
        
        return {"data": state["data"] + "B", "step": 2}
    
    def step_c(state: CustomTransformerState) -> CustomTransformerState:
        writer = get_stream_writer()
        writer({"type": "progress", "step": "C", "percent": 100, "message": "步骤 C 完成"})
        
        return {"data": state["data"] + "C", "step": 3}
    
    graph = StateGraph(CustomTransformerState)
    graph.add_node("step_a", step_a)
    graph.add_node("step_b", step_b)
    graph.add_node("step_c", step_c)
    
    graph.add_edge(START, "step_a")
    graph.add_edge("step_a", "step_b")
    graph.add_edge("step_b", "step_c")
    graph.add_edge("step_c", END)
    
    # 简化版本：不使用自定义转换器，直接使用 custom 事件
    return graph.compile()


async def demo_custom_transformer():
    """演示自定义事件流"""
    print("\n" + "="*80)
    print("场景 4: 自定义事件流 - 进度追踪")
    print("="*80)
    
    graph = create_custom_transformer_graph()
    
    input_data = {"data": "", "step": 0}
    
    # 使用 astream 配合 stream_mode="custom" 来捕获自定义事件
    progress_events = []
    final_output = None
    
    print("\n📊 进度追踪（通过自定义事件）:")
    
    # 使用 astream 并指定 stream_mode 包含 custom
    async for chunk in graph.astream(input_data, stream_mode=["custom", "values"]):
        # chunk 可能是自定义事件或状态值
        if isinstance(chunk, tuple) and len(chunk) == 2:
            mode, data = chunk
            if mode == "custom":
                # 自定义事件
                if isinstance(data, dict) and data.get("type") == "progress":
                    progress_events.append(data)
                    print(f"  [{data['step']}] {data['percent']}% - {data['message']}")
            elif mode == "values":
                # 最终状态
                final_output = data
        elif isinstance(chunk, dict):
            # 单一模式下的数据
            if chunk.get("type") == "progress":
                progress_events.append(chunk)
                print(f"  [{chunk['step']}] {chunk['percent']}% - {chunk['message']}")
            else:
                final_output = chunk
    
    print("\n✅ 最终输出:")
    if final_output:
        print(f"  数据: {final_output.get('data', 'N/A')}")
        print(f"  步骤: {final_output.get('step', 'N/A')}")
    else:
        print("  未捕获到最终输出")
    print(f"  捕获的进度事件: {len(progress_events)} 个")


# ============================================================================
# 场景 5: 交错消费多个投影 - 严格按到达顺序
# ============================================================================

class InterleavedState(TypedDict):
    """交错状态"""
    messages: list[dict]
    counter: int


def create_interleaved_graph():
    """创建交错消费图"""
    
    def node1(state: InterleavedState) -> InterleavedState:
        return {
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": "节点1输出"}
            ],
            "counter": state.get("counter", 0) + 1
        }
    
    def node2(state: InterleavedState) -> InterleavedState:
        return {
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": "节点2输出"}
            ],
            "counter": state.get("counter", 0) + 1
        }
    
    graph = StateGraph(InterleavedState)
    graph.add_node("node1", node1)
    graph.add_node("node2", node2)
    
    graph.add_edge(START, "node1")
    graph.add_edge("node1", "node2")
    graph.add_edge("node2", END)
    
    return graph.compile()


def demo_interleaved_streaming():
    """演示交错消费多个投影（同步版本）"""
    print("\n" + "="*80)
    print("场景 5: 交错消费多个投影 - 严格按到达顺序")
    print("="*80)
    
    graph = create_interleaved_graph()
    
    input_data = {
        "messages": [{"role": "user", "content": "开始"}],
        "counter": 0
    }
    
    # 同步版本使用 stream_events
    stream = graph.stream_events(input_data, version="v3")
    
    print("\n🔀 交错输出 (按到达顺序):")
    # 使用 interleave 按严格顺序消费多个投影
    for name, item in stream.interleave("values", "messages"):
        if name == "values":
            print(f"  [状态] counter={item.get('counter')}")
        elif name == "messages":
            content = item.output.content if hasattr(item.output, 'content') else str(item.output)
            print(f"  [消息] node={item.node}, content={content}")
    
    print("\n✅ 最终输出:")
    final_output = stream.output  # 同步版本是属性，不是方法
    print(f"  计数器: {final_output['counter']}")
    print(f"  消息数: {len(final_output['messages'])}")


# ============================================================================
# 场景 6: 原始协议事件流 - 底层事件访问
# ============================================================================

def demo_raw_protocol_events():
    """演示原始协议事件流"""
    print("\n" + "="*80)
    print("场景 6: 原始协议事件流 - 底层事件访问")
    print("="*80)
    
    graph = create_interleaved_graph()
    
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
        
        # 只显示前10个事件，避免输出过多
        if event_count >= 10:
            print("  ... (更多事件)")
            break
    
    print(f"\n✅ 总事件数: {event_count}+")


# ============================================================================
# 主函数
# ============================================================================

async def main():
    """运行所有演示"""
    print("\n" + "="*80)
    print("LangGraph Event Streaming 综合示例")
    print("展示最新的 stream_events API (v3)")
    print("="*80)
    
    # 场景 1: 基础流式输出
    await demo_basic_streaming()
    
    # 场景 2: 多投影并发消费
    await demo_multi_projection_streaming()
    
    # 场景 3: 人机协作中断和恢复
    await demo_human_in_loop_streaming()
    
    # 场景 4: 自定义事件流
    await demo_custom_transformer()
    
    # 场景 5: 交错消费（同步）
    demo_interleaved_streaming()
    
    # 场景 6: 原始协议事件
    demo_raw_protocol_events()
    
    print("\n" + "="*80)
    print("✅ 所有演示完成！")
    print("="*80)
    
    print("\n📚 关键要点:")
    print("1. stream_events(version='v3') 是推荐的流式 API")
    print("2. 提供类型化投影: messages, values, subgraphs, output()")
    print("3. 支持并发消费多个投影 (asyncio.gather)")
    print("4. 支持交错消费 (stream.interleave)")
    print("5. 支持人机协作中断和恢复 (interrupt + Command)")
    print("6. 支持自定义事件 (get_stream_writer)")
    print("7. 可访问原始协议事件 (iterate stream directly)")
    print("8. stream.output() 和 stream.interrupts() 是异步方法，需要 await")
    
    print("\n🎯 应用场景:")
    print("- 实时 UI 更新（聊天界面、进度条）")
    print("- 多智能体协作监控")
    print("- 工具调用追踪")
    print("- 自定义进度和状态事件（通过 get_stream_writer）")
    print("- 人机协作工作流")
    print("- 调试和可观测性")


if __name__ == "__main__":
    asyncio.run(main())
