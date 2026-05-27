"""
LangGraph Streaming（流式输出）完整示例
适合 JS/Go 开发者

Streaming 是什么？
- 实时获取图执行的中间结果
- 类似 ChatGPT 的打字机效果
- 不用等待全部完成就能看到进度
"""

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict, Annotated
from typing import List
import operator
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.config import get_stream_writer
import os
import time

# ============================================
# 第一部分：理解 Streaming
# ============================================

print("="*70)
print("🌊 第一部分：理解 Streaming")
print("="*70)

print("""
Streaming 的核心概念：
--------------------
1. **实时输出**：不等待全部完成，边执行边输出
2. **多种模式**：可以选择输出什么内容
3. **用户体验**：让用户看到进度，不会觉得卡住

类比理解：
---------
传统方式（invoke）:
  用户提问 → [等待...] → 完整答案
  
流式输出（stream）:
  用户提问 → "正在" → "思考" → "中..." → "答案是" → "..."
  
类似概念：
---------
JavaScript:
  // Server-Sent Events (SSE)
  const eventSource = new EventSource('/stream');
  eventSource.onmessage = (event) => {
      console.log(event.data);
  };

Go:
  // Channel streaming
  ch := make(chan string)
  go func() {
      for msg := range ch {
          fmt.Println(msg)
      }
  }()
""")

# ============================================
# 第二部分：基础 Streaming - values 模式
# ============================================

print("\n" + "="*70)
print("📊 第二部分：values 模式（完整状态）")
print("="*70)


class SimpleState(TypedDict):
    counter: int
    message: str


def step1(state: SimpleState):
    print("  [节点 step1] 执行中...")
    time.sleep(0.5)  # 模拟耗时操作
    return {"counter": state["counter"] + 1, "message": "Step 1 完成"}


def step2(state: SimpleState):
    print("  [节点 step2] 执行中...")
    time.sleep(0.5)
    return {"counter": state["counter"] + 1, "message": "Step 2 完成"}


def step3(state: SimpleState):
    print("  [节点 step3] 执行中...")
    time.sleep(0.5)
    return {"counter": state["counter"] + 1, "message": "Step 3 完成"}


# 构建图
simple_graph = StateGraph(SimpleState)
simple_graph.add_node("step1", step1)
simple_graph.add_node("step2", step2)
simple_graph.add_node("step3", step3)
simple_graph.add_edge(START, "step1")
simple_graph.add_edge("step1", "step2")
simple_graph.add_edge("step2", "step3")
simple_graph.add_edge("step3", END)
simple_app = simple_graph.compile()

print("\n🧪 测试：values 模式（每步后的完整状态）")
print("\n对比：invoke vs stream")

# 方式 1：invoke（传统方式）
print("\n--- 使用 invoke（一次性返回）---")
start_time = time.time()
result = simple_app.invoke({"counter": 0, "message": "开始"})
print(f"✅ 完成！耗时 {time.time() - start_time:.1f}s")
print(f"   结果: {result}")

# 方式 2：stream（流式输出）
print("\n--- 使用 stream（实时输出）---")
start_time = time.time()
for i, chunk in enumerate(simple_app.stream(
    {"counter": 0, "message": "开始"},
    stream_mode="values",
    version="v2"
), 1):
    print(f"📦 Chunk {i}: {chunk['data']}")

print(f"✅ 完成！耗时 {time.time() - start_time:.1f}s")

# ============================================
# 第三部分：updates 模式（节点更新）
# ============================================

print("\n" + "="*70)
print("🔄 第三部分：updates 模式（只看节点更新）")
print("="*70)

print("""
values vs updates:
-----------------
values:  每步后的完整 state
updates: 每个节点返回的更新

类比：
values  = 完整的购物车（每次都看全部商品）
updates = 只看新添加的商品
""")

print("\n🧪 测试：updates 模式")

for chunk in simple_app.stream(
    {"counter": 0, "message": "开始"},
    stream_mode="updates",
    version="v2"
):
    node_name = list(chunk['data'].keys())[0]
    update = chunk['data'][node_name]
    print(f"🔄 节点 '{node_name}' 更新: {update}")

# ============================================
# 第四部分：messages 模式（只看消息）
# ============================================

print("\n" + "="*70)
print("💬 第四部分：messages 模式（LLM 对话）")
print("="*70)

os.environ["DEEPSEEK_API_KEY"] = "sk-1f1f27b8e0524422bab4b8517b1068ca"

llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=os.environ["DEEPSEEK_API_KEY"],
    openai_api_base="https://api.deepseek.com",
    temperature=0.7,
)


class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]


def chat_node(state: ChatState):
    """调用 LLM"""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


# 构建聊天图
chat_graph = StateGraph(ChatState)
chat_graph.add_node("chat", chat_node)
chat_graph.add_edge(START, "chat")
chat_graph.add_edge("chat", END)
chat_app = chat_graph.compile()

print("\n🧪 测试：messages 模式（只输出消息）")

for chunk in chat_app.stream(
    {"messages": [HumanMessage(content="用一句话介绍 Python")]},
    stream_mode="messages",
    version="v2"
):
    message = chunk['data'][0]  # 第一条消息
    role = "User" if isinstance(message, HumanMessage) else "AI"
    print(f"💬 {role}: {message.content}")

# ============================================
# 第五部分：custom 模式（自定义事件）
# ============================================

print("\n" + "="*70)
print("🎯 第五部分：custom 模式（自定义进度）")
print("="*70)

print("""
自定义事件的用途：
---------------
- 发送进度更新（"正在搜索...", "正在分析..."）
- 发送中间结果（搜索到 5 条结果）
- 发送状态信息（已完成 30%）

类似概念：
---------
JavaScript:
  socket.emit('progress', {percent: 30});

Go:
  progressCh <- Progress{Percent: 30}
""")


class ResearchState(TypedDict):
    query: str
    results: List[str]
    summary: str


def search_node(state: ResearchState):
    """搜索节点 - 发送自定义进度"""
    writer = get_stream_writer()
    
    writer({"status": "开始搜索", "progress": 0})
    time.sleep(0.3)
    
    writer({"status": "搜索中...", "progress": 30})
    time.sleep(0.3)
    
    writer({"status": "找到 5 条结果", "progress": 60})
    time.sleep(0.3)
    
    writer({"status": "搜索完成", "progress": 100})
    
    return {"results": ["结果1", "结果2", "结果3", "结果4", "结果5"]}


def analyze_node(state: ResearchState):
    """分析节点"""
    writer = get_stream_writer()
    
    writer({"status": "开始分析", "progress": 0})
    time.sleep(0.3)
    
    writer({"status": "分析中...", "progress": 50})
    time.sleep(0.3)
    
    writer({"status": "分析完成", "progress": 100})
    
    return {"summary": f"分析了 {len(state['results'])} 条结果"}


# 构建研究图
research_graph = StateGraph(ResearchState)
research_graph.add_node("search", search_node)
research_graph.add_node("analyze", analyze_node)
research_graph.add_edge(START, "search")
research_graph.add_edge("search", "analyze")
research_graph.add_edge("analyze", END)
research_app = research_graph.compile()

print("\n🧪 测试：custom 模式（自定义进度）")

for chunk in research_app.stream(
    {"query": "LangGraph", "results": [], "summary": ""},
    stream_mode="custom",
    version="v2"
):
    custom_data = chunk['data']
    status = custom_data.get('status', '')
    progress = custom_data.get('progress', 0)
    print(f"📊 {status} [{progress}%]")

# ============================================
# 第六部分：多模式组合
# ============================================

print("\n" + "="*70)
print("🎭 第六部分：多模式组合")
print("="*70)

print("""
可以同时使用多种模式：
-------------------
stream_mode=["values", "updates", "custom"]

每个 chunk 都有 type 字段标识类型
""")

print("\n🧪 测试：多模式组合")

for chunk in research_app.stream(
    {"query": "AI", "results": [], "summary": ""},
    stream_mode=["updates", "custom"],
    version="v2"
):
    if chunk["type"] == "updates":
        node_name = list(chunk['data'].keys())[0]
        print(f"🔄 节点 '{node_name}' 完成")
    elif chunk["type"] == "custom":
        status = chunk['data'].get('status', '')
        print(f"   📊 {status}")

# ============================================
# 第七部分：实际应用 - 打字机效果
# ============================================

print("\n" + "="*70)
print("⌨️  第七部分：打字机效果（Token Streaming）")
print("="*70)

print("""
LLM Token Streaming:
------------------
逐个 token 输出，类似 ChatGPT 的打字效果

实现方式：
1. 使用 llm.stream() 而不是 llm.invoke()
2. 逐个 token 输出
""")


def streaming_chat_node(state: ChatState):
    """流式输出的聊天节点"""
    writer = get_stream_writer()
    
    # 使用 stream 而不是 invoke
    full_response = ""
    for chunk in llm.stream(state["messages"]):
        if chunk.content:
            full_response += chunk.content
            # 发送每个 token
            writer({"token": chunk.content})
    
    return {"messages": [AIMessage(content=full_response)]}


# 构建流式聊天图
streaming_chat_graph = StateGraph(ChatState)
streaming_chat_graph.add_node("chat", streaming_chat_node)
streaming_chat_graph.add_edge(START, "chat")
streaming_chat_graph.add_edge("chat", END)
streaming_chat_app = streaming_chat_graph.compile()

print("\n🧪 测试：打字机效果")
print("AI: ", end="", flush=True)

for chunk in streaming_chat_app.stream(
    {"messages": [HumanMessage(content="用一句话介绍 LangGraph")]},
    stream_mode="custom",
    version="v2"
):
    if "token" in chunk['data']:
        print(chunk['data']['token'], end="", flush=True)

print("\n")

# ============================================
# 第八部分：实际应用 - 多步骤工作流
# ============================================

print("\n" + "="*70)
print("🔧 第八部分：实际应用 - 多步骤工作流")
print("="*70)


class WorkflowState(TypedDict):
    task: str
    plan: str
    execution: str
    result: str


def planning_node(state: WorkflowState):
    """规划节点"""
    writer = get_stream_writer()
    writer({"step": "planning", "status": "开始规划任务"})
    time.sleep(0.5)
    
    plan = f"任务 '{state['task']}' 的执行计划"
    writer({"step": "planning", "status": "规划完成", "plan": plan})
    
    return {"plan": plan}


def execution_node(state: WorkflowState):
    """执行节点"""
    writer = get_stream_writer()
    writer({"step": "execution", "status": "开始执行任务"})
    time.sleep(0.5)
    
    writer({"step": "execution", "status": "执行中...", "progress": 50})
    time.sleep(0.5)
    
    execution = f"执行了计划: {state['plan']}"
    writer({"step": "execution", "status": "执行完成"})
    
    return {"execution": execution}


def summary_node(state: WorkflowState):
    """总结节点"""
    writer = get_stream_writer()
    writer({"step": "summary", "status": "生成总结"})
    time.sleep(0.5)
    
    result = f"任务完成！执行结果: {state['execution']}"
    writer({"step": "summary", "status": "总结完成"})
    
    return {"result": result}


# 构建工作流图
workflow_graph = StateGraph(WorkflowState)
workflow_graph.add_node("planning", planning_node)
workflow_graph.add_node("execution", execution_node)
workflow_graph.add_node("summary", summary_node)
workflow_graph.add_edge(START, "planning")
workflow_graph.add_edge("planning", "execution")
workflow_graph.add_edge("execution", "summary")
workflow_graph.add_edge("summary", END)
workflow_app = workflow_graph.compile()

print("\n🧪 测试：多步骤工作流")

for chunk in workflow_app.stream(
    {"task": "分析数据", "plan": "", "execution": "", "result": ""},
    stream_mode=["updates", "custom"],
    version="v2"
):
    if chunk["type"] == "updates":
        node_name = list(chunk['data'].keys())[0]
        print(f"\n✅ 节点 '{node_name}' 完成")
    elif chunk["type"] == "custom":
        step = chunk['data'].get('step', '')
        status = chunk['data'].get('status', '')
        print(f"   📊 [{step}] {status}")

# ============================================
# 第九部分：对比 JavaScript/Go
# ============================================

print("\n" + "="*70)
print("🔄 跨语言对比")
print("="*70)

print("""
Python (LangGraph):
-------------------
for chunk in graph.stream(input, stream_mode="values", version="v2"):
    print(chunk["data"])


JavaScript (类似实现):
---------------------
// Server-Sent Events
const eventSource = new EventSource('/api/stream');
eventSource.onmessage = (event) => {
    const chunk = JSON.parse(event.data);
    console.log(chunk);
};

// 或者 async iterator
for await (const chunk of graph.stream(input)) {
    console.log(chunk);
}


Go (类似实现):
-------------
// Channel streaming
ch := graph.Stream(input)
for chunk := range ch {
    fmt.Printf("Chunk: %v\\n", chunk)
}

// 或者 callback
graph.Stream(input, func(chunk Chunk) {
    fmt.Printf("Chunk: %v\\n", chunk)
})
""")

# ============================================
# 第十部分：最佳实践
# ============================================

print("\n" + "="*70)
print("📚 Streaming 最佳实践")
print("="*70)

print("""
1. 选择合适的 stream_mode
   - values: 需要完整状态
   - updates: 只关心节点更新
   - messages: 聊天应用
   - custom: 自定义进度

2. 使用 version="v2"
   ✅ 统一的输出格式
   ✅ 类型安全
   ✅ 更好的调试

3. 发送有意义的进度
   ✅ writer({"status": "正在搜索", "progress": 30})
   ❌ writer({"msg": "ok"})

4. 处理长时间操作
   - 定期发送进度更新
   - 让用户知道系统在工作
   - 避免超时

5. 错误处理
   - 在 stream 中捕获异常
   - 发送错误信息给用户
   - 优雅降级

6. 性能考虑
   - 不要发送过于频繁的更新
   - 批量发送小更新
   - 控制 chunk 大小

7. 用户体验
   ✅ 显示进度条
   ✅ 显示当前步骤
   ✅ 显示预计时间
   ❌ 只显示 "加载中..."
""")

print("\n" + "="*70)
print("✅ Streaming 示例完成！")
print("="*70)

print("""
总结：
-----
1. invoke: 一次性返回，简单但用户体验差
2. stream: 实时输出，用户体验好
3. 多种模式: values, updates, messages, custom
4. 自定义事件: 使用 get_stream_writer()
5. Token streaming: 打字机效果
6. 实际应用: 多步骤工作流、进度追踪

下一步：
-------
- 尝试在你的项目中使用 streaming
- 结合 LangSmith 追踪 streaming 执行
- 实现前端的实时显示
""")
