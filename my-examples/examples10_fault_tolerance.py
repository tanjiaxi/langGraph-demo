"""
LangGraph 容错性（Fault Tolerance）示例
适合 JS/Go 开发者

容错性是什么？
- 自动重试失败的节点
- 设置超时限制
- 错误处理和恢复机制
- 类似 HTTP 客户端的重试策略
"""

from langgraph.graph import StateGraph, START, END
from langgraph.types import RetryPolicy, TimeoutPolicy, Command
from langgraph.errors import NodeError, NodeTimeoutError
from langgraph.runtime import Runtime
from typing_extensions import TypedDict
import asyncio
import time
from datetime import timedelta

print("="*60)
print("🛡️  LangGraph 容错性完整示例")
print("="*60)

print("""
LangGraph 提供三种容错机制：
1. Retries（重试）: 自动重试失败的节点
2. Timeouts（超时）: 限制节点执行时间
3. Error Handling（错误处理）: 重试耗尽后的恢复逻辑

执行顺序：
节点执行 → 异常 → 重试策略 → 重试耗尽 → 错误处理器 → 恢复/路由
""")

# ============================================
# 第一部分：基础重试策略
# ============================================

print("\n" + "="*60)
print("🔄 第一部分：基础重试策略（Retry Policy）")
print("="*60)

class BasicState(TypedDict):
    attempt_count: int
    result: str


# 模拟不稳定的 API 调用
call_count = 0

def unstable_api_call(state: BasicState) -> BasicState:
    """模拟不稳定的 API，前两次失败，第三次成功"""
    global call_count
    call_count += 1
    
    print(f"  📞 API 调用 #{call_count}")
    
    if call_count < 3:
        print(f"  ❌ 失败: 网络超时")
        raise ConnectionError("Network timeout")
    
    print(f"  ✅ 成功!")
    return {"result": "API call succeeded", "attempt_count": call_count}


# 创建带重试策略的图
builder = StateGraph(BasicState)

# 添加节点，配置重试策略
builder.add_node(
    "api_call",
    unstable_api_call,
    retry_policy=RetryPolicy(
        max_attempts=3,        # 最多尝试 3 次
        initial_interval=0.5,  # 首次重试前等待 0.5 秒
        backoff_factor=2.0,    # 每次重试间隔翻倍
        max_interval=10.0,     # 最大间隔 10 秒
        jitter=True           # 添加随机抖动
    )
)

builder.add_edge(START, "api_call")
builder.add_edge("api_call", END)

graph1 = builder.compile()

print("\n🧪 测试 1：自动重试")
print("模拟场景：API 前两次失败，第三次成功")


call_count = 0  # 重置计数器
result = graph1.invoke({"attempt_count": 0, "result": ""})
print(f"\n✅ 最终结果: {result['result']}")
print(f"   总共尝试了 {result['attempt_count']} 次")

print("""
类似概念对比：
--------------
JavaScript (axios):
  axios.get(url, {
    timeout: 5000,
    retry: 3,
    retryDelay: (retryCount) => retryCount * 1000
  })

Go (with retry):
  err := retry.Do(
      func() error {
          return callAPI()
      },
      retry.Attempts(3),
      retry.Delay(500 * time.Millisecond),
  )

Python (requests with retry):
  from requests.adapters import HTTPAdapter
  from requests.packages.urllib3.util.retry import Retry
  
  retry_strategy = Retry(
      total=3,
      backoff_factor=2
  )
""")


# ============================================
# 第二部分：自定义重试逻辑
# ============================================

print("\n" + "="*60)
print("🎯 第二部分：自定义重试逻辑")
print("="*60)

print("""
默认行为：
- 重试大多数异常（网络错误、超时等）
- 不重试：ValueError, TypeError, SyntaxError 等编程错误
- HTTP 库：只重试 5xx 错误，不重试 4xx

自定义场景：
- 只重试特定异常
- 根据异常内容决定是否重试
- 扩展默认行为
""")

from langgraph.types import default_retry_on

class CustomAPIError(Exception):
    """自定义 API 错误"""
    pass

class RateLimitError(Exception):
    """速率限制错误"""
    pass


def custom_retry_logic(exc: BaseException) -> bool:
    """自定义重试逻辑"""
    # 不重试自定义错误
    if isinstance(exc, CustomAPIError):
        print(f"  ⚠️  CustomAPIError 不重试")
        return False
    
    # 总是重试速率限制错误
    if isinstance(exc, RateLimitError):
        print(f"  🔄 RateLimitError 需要重试")
        return True
    
    # 其他情况使用默认逻辑
    return default_retry_on(exc)


# 测试自定义重试
test_error_count = 0

def api_with_rate_limit(state: BasicState) -> BasicState:
    """模拟速率限制"""
    global test_error_count
    test_error_count += 1
    
    print(f"  📞 调用 #{test_error_count}")
    
    if test_error_count < 3:
        print(f"  ⏱️  速率限制，需要重试")
        raise RateLimitError("Rate limit exceeded, retry after 1s")
    
    print(f"  ✅ 成功!")
    return {"result": "Success after rate limit", "attempt_count": test_error_count}


builder2 = StateGraph(BasicState)
builder2.add_node(
    "rate_limited_api",
    api_with_rate_limit,
    retry_policy=RetryPolicy(
        max_attempts=5,
        initial_interval=0.3,
        retry_on=custom_retry_logic  # 使用自定义逻辑
    )
)
builder2.add_edge(START, "rate_limited_api")
builder2.add_edge("rate_limited_api", END)

graph2 = builder2.compile()

print("\n🧪 测试 2：自定义重试逻辑（速率限制）")
test_error_count = 0
result = graph2.invoke({"attempt_count": 0, "result": ""})
print(f"\n✅ 结果: {result['result']}")
print(f"   重试了 {result['attempt_count'] - 1} 次")


# ============================================
# 第三部分：检查重试状态（Fallback 模式）
# ============================================

print("\n" + "="*60)
print("🔀 第三部分：检查重试状态 - Fallback 模式")
print("="*60)

print("""
使用场景：
- 主 API 失败后切换到备用 API
- 根据重试次数调整策略
- 记录重试信息用于监控
""")

class FallbackState(TypedDict):
    result: str
    api_used: str


def api_with_fallback(state: FallbackState, runtime: Runtime) -> FallbackState:
    """主 API 失败后使用备用 API"""
    attempt = runtime.execution_info.node_attempt
    
    print(f"  📞 尝试 #{attempt}")
    
    if attempt == 1:
        # 第一次尝试主 API
        print(f"  🎯 使用主 API")
        print(f"  ❌ 主 API 失败")
        raise ConnectionError("Primary API failed")
    
    elif attempt == 2:
        # 第二次尝试备用 API
        print(f"  🔄 切换到备用 API")
        return {
            "result": "Success from fallback API",
            "api_used": "fallback"
        }
    
    return {"result": "Unexpected", "api_used": "unknown"}


builder3 = StateGraph(FallbackState)
builder3.add_node(
    "smart_api",
    api_with_fallback,
    retry_policy=RetryPolicy(max_attempts=3)
)
builder3.add_edge(START, "smart_api")
builder3.add_edge("smart_api", END)

graph3 = builder3.compile()

print("\n🧪 测试 3：Fallback 模式")
result = graph3.invoke({"result": "", "api_used": ""})
print(f"\n✅ 结果: {result['result']}")
print(f"   使用的 API: {result['api_used']}")


print("""
runtime.execution_info 提供的信息：
----------------------------------
- node_attempt: 当前尝试次数（从 1 开始）
- node_first_attempt_time: 首次尝试的时间戳
- thread_id: 线程 ID
- run_id: 运行 ID
- checkpoint_id: 检查点 ID
- task_id: 任务 ID
""")

# ============================================
# 第四部分：超时控制（Timeouts）
# ============================================

print("\n" + "="*60)
print("⏱️  第四部分：超时控制")
print("="*60)

print("""
超时类型：
1. run_timeout: 硬性时间限制（墙钟时间）
2. idle_timeout: 空闲超时（无进度时触发）

注意：超时只适用于异步节点！
""")

class TimeoutState(TypedDict):
    result: str
    duration: float


async def slow_async_node(state: TimeoutState) -> TimeoutState:
    """模拟慢速异步操作"""
    print(f"  ⏳ 开始慢速操作...")
    start = time.time()
    
    try:
        await asyncio.sleep(3)  # 睡眠 3 秒
        duration = time.time() - start
        print(f"  ✅ 完成，耗时 {duration:.2f}s")
        return {"result": "Completed", "duration": duration}
    except asyncio.CancelledError:
        duration = time.time() - start
        print(f"  ⏰ 超时取消，已运行 {duration:.2f}s")
        raise


# 测试 run_timeout
builder4 = StateGraph(TimeoutState)
builder4.add_node(
    "slow_node",
    slow_async_node,
    timeout=TimeoutPolicy(run_timeout=2)  # 2 秒超时
)
builder4.add_edge(START, "slow_node")
builder4.add_edge("slow_node", END)

graph4 = builder4.compile()

print("\n🧪 测试 4：run_timeout（硬性超时）")
print("节点需要 3 秒，但超时设置为 2 秒")

import asyncio

async def run_test_4():
    try:
        result = await graph4.ainvoke({"result": "", "duration": 0})
        print(f"结果: {result}")
    except NodeTimeoutError as e:
        print(f"\n❌ 捕获超时异常:")
        print(f"   节点: {e.node}")
        print(f"   已运行: {e.elapsed:.2f}s")
        print(f"   超时类型: {e.kind}")
        print(f"   run_timeout: {e.run_timeout}s")

asyncio.run(run_test_4())

print("""
类似概念：
---------
JavaScript (Promise):
  Promise.race([
    fetchData(),
    new Promise((_, reject) => 
      setTimeout(() => reject('timeout'), 2000)
    )
  ])

Go (context):
  ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
  defer cancel()
  
  err := doWork(ctx)
  if err == context.DeadlineExceeded {
      // 超时处理
  }
""")


# ============================================
# 第五部分：空闲超时（Idle Timeout）
# ============================================

print("\n" + "="*60)
print("💤 第五部分：空闲超时（Idle Timeout）")
print("="*60)

print("""
idle_timeout 特点：
- 只在节点无进度时触发
- 有进度信号时会重置计时器
- 适合检测卡死的操作

进度信号包括：
- 状态写入
- 流式输出
- 子任务调度
- runtime.heartbeat() 调用
- LangChain 回调事件
""")


async def node_with_progress(state: TimeoutState, runtime: Runtime) -> TimeoutState:
    """带进度信号的节点"""
    print(f"  🏃 开始处理...")
    
    for i in range(5):
        await asyncio.sleep(0.8)  # 每次 0.8 秒
        # runtime.heartbeat()  # 发送心跳，重置空闲计时器
        print(f"  💓 心跳 #{i+1}")
    
    print(f"  ✅ 完成!")
    return {"result": "Completed with heartbeats", "duration": 4.0}


builder5 = StateGraph(TimeoutState)
builder5.add_node(
    "progress_node",
    node_with_progress,
    timeout=TimeoutPolicy(
        idle_timeout=2,  # 2 秒无进度则超时
        refresh_on="heartbeat"  # 只有心跳才重置计时器
    )
)
builder5.add_edge(START, "progress_node")
builder5.add_edge("progress_node", END)

graph5 = builder5.compile()

print("\n🧪 测试 5：idle_timeout（空闲超时）")
print("总耗时 4 秒，但每 0.8 秒发送心跳")
print("idle_timeout=2 秒，因为有心跳所以不会超时")

async def run_test_5():
    try:
        result = await graph5.ainvoke({"result": "", "duration": 0})
        print(f"结果: {result}")
        print(f"\n✅ 结果: {result['result']}")
    except NodeTimeoutError as e:
        print(f"\n❌ 捕获超时异常:")
        print(f"   节点: {e.node}")
        print(f"   已运行: {e.elapsed:.2f}s")
        print(f"   超时类型: {e.kind}")
        print(f"   run_timeout: {e.run_timeout}s")

asyncio.run(run_test_5())


# ============================================
# 第六部分：超时 + 重试组合
# ============================================

print("\n" + "="*60)
print("🔄⏱️  第六部分：超时 + 重试组合")
print("="*60)

print("""
组合使用场景：
- 每次尝试都有超时限制
- 超时后自动重试
- 超时计时器在每次重试时重置
""")

retry_with_timeout_count = 0

async def flaky_with_timeout(state: TimeoutState) -> TimeoutState:
    """有时会超时的节点"""
    global retry_with_timeout_count
    retry_with_timeout_count += 1
    
    print(f"  📞 尝试 #{retry_with_timeout_count}")
    
    if retry_with_timeout_count == 1:
        print(f"  ⏳ 第一次尝试会超时...")
        await asyncio.sleep(3)  # 超过 2 秒超时限制
    else:
        print(f"  ⚡ 第二次尝试很快")
        await asyncio.sleep(0.5)
    
    return {"result": "Success", "duration": 0.5}


builder6 = StateGraph(TimeoutState)
builder6.add_node(
    "flaky_node",
    flaky_with_timeout,
    timeout=TimeoutPolicy(run_timeout=2),  # 2 秒超时
    retry_policy=RetryPolicy(max_attempts=3)  # 最多 3 次
)
builder6.add_edge(START, "flaky_node")
builder6.add_edge("flaky_node", END)

graph6 = builder6.compile()

print("\n🧪 测试 6：超时 + 重试")
print("第一次尝试会超时，第二次成功")

async def run_test_6():
    global retry_with_timeout_count
    retry_with_timeout_count = 0
    result = await graph6.ainvoke({"result": "", "duration": 0})
    print(f"\n✅ 结果: {result['result']}")
    print(f"   总共尝试了 {retry_with_timeout_count} 次")

asyncio.run(run_test_6())


# ============================================
# 第七部分：错误处理器（Error Handler）
# ============================================

print("\n" + "="*60)
print("🚨 第七部分：错误处理器（Error Handler）")
print("="*60)

print("""
错误处理器特点：
- 在所有重试耗尽后执行
- 可以更新状态
- 可以路由到其他节点（补偿模式）
- 适合 Saga 模式的补偿逻辑
""")

class PaymentState(TypedDict):
    status: str
    amount: float
    error_message: str


def reserve_inventory(state: PaymentState) -> PaymentState:
    """预留库存"""
    print(f"  📦 预留库存")
    return {"status": "inventory_reserved"}


payment_attempt = 0

def charge_payment(state: PaymentState) -> PaymentState:
    """支付（会失败）"""
    global payment_attempt
    payment_attempt += 1
    
    print(f"  💳 尝试支付 #{payment_attempt}")
    
    # 模拟支付失败
    raise RuntimeError("Payment gateway timeout")


def payment_error_handler(state: PaymentState, error: NodeError) -> Command:
    """支付失败的错误处理器"""
    print(f"\n  🚨 错误处理器被调用")
    print(f"     失败节点: {error.node}")
    print(f"     错误信息: {error.error}")
    print(f"  🔄 执行补偿逻辑: 释放库存")
    
    return Command(
        update={
            "status": "payment_failed_compensated",
            "error_message": str(error.error)
        },
        goto="finalize"  # 路由到最终节点
    )


def finalize(state: PaymentState) -> PaymentState:
    """最终处理"""
    print(f"  ✅ 最终状态: {state['status']}")
    return state


# 构建支付流程图
builder7 = StateGraph(PaymentState)

builder7.add_node("reserve_inventory", reserve_inventory)
builder7.add_node(
    "charge_payment",
    charge_payment,
    retry_policy=RetryPolicy(
        max_attempts=3,
        retry_on=ConnectionError  # 只重试连接错误
    ),
    error_handler=payment_error_handler  # 重试耗尽后的处理
)
builder7.add_node("finalize", finalize)

builder7.add_edge(START, "reserve_inventory")
builder7.add_edge("reserve_inventory", "charge_payment")
# 注意：不需要添加 charge_payment -> finalize 的边
# 因为 error_handler 会通过 Command 路由

graph7 = builder7.compile()

print("\n🧪 测试 7：错误处理器（Saga 补偿模式）")
print("流程：预留库存 → 支付失败 → 补偿（释放库存）")

payment_attempt = 0
result = graph7.invoke({
    "status": "initial",
    "amount": 100.0,
    "error_message": ""
})

print(f"\n📊 最终结果:")
print(f"   状态: {result['status']}")
print(f"   错误信息: {result['error_message']}")

print("""
Saga 模式对比：
--------------
传统方式（手动补偿）:
  try:
      reserve_inventory()
      charge_payment()
  except PaymentError:
      release_inventory()  # 手动补偿
      raise

LangGraph 方式（声明式）:
  .add_node(
      "charge_payment",
      charge_payment,
      retry_policy=RetryPolicy(...),
      error_handler=compensate_handler  # 自动补偿
  )
""")


# ============================================
# 第八部分：图级默认配置
# ============================================

print("\n" + "="*60)
print("⚙️  第八部分：图级默认配置（Graph Defaults）")
print("="*60)

print("""
使用 set_node_defaults() 的好处：
- 避免重复配置
- 统一的容错策略
- 个别节点可以覆盖默认值
""")

class MultiNodeState(TypedDict):
    results: list[str]


def default_error_handler(state: MultiNodeState, error: NodeError) -> MultiNodeState:
    """默认错误处理器"""
    print(f"  🚨 默认处理器: {error.node} 失败")
    return {"results": [f"handled_{error.node}"]}


node_a_count = 0
def node_a(state: MultiNodeState) -> MultiNodeState:
    """节点 A（会失败）"""
    global node_a_count
    node_a_count += 1
    print(f"  🅰️  节点 A 尝试 #{node_a_count}")
    
    if node_a_count < 2:
        raise ConnectionError("Node A failed")
    
    return {"results": ["node_a_success"]}


def node_b(state: MultiNodeState) -> MultiNodeState:
    """节点 B（正常）"""
    print(f"  🅱️  节点 B 执行")
    return {"results": ["node_b_success"]}


def custom_error_handler_for_c(state: MultiNodeState, error: NodeError) -> MultiNodeState:
    """节点 C 的自定义错误处理器"""
    print(f"  🎯 自定义处理器: {error.node} 失败")
    return {"results": [f"custom_handled_{error.node}"]}


def node_c(state: MultiNodeState) -> MultiNodeState:
    """节点 C（会失败，使用自定义处理器）"""
    print(f"  ©️  节点 C 执行")
    raise ValueError("Node C always fails")


# 使用图级默认配置
builder8 = StateGraph(MultiNodeState)

# 设置默认配置（应用到所有节点）
builder8.set_node_defaults(
    retry_policy=RetryPolicy(max_attempts=2),
    error_handler=default_error_handler
)

# 添加节点
builder8.add_node("node_a", node_a)  # 使用默认配置
builder8.add_node("node_b", node_b)  # 使用默认配置
builder8.add_node(
    "node_c",
    node_c,
    error_handler=custom_error_handler_for_c  # 覆盖默认处理器
)

builder8.add_edge(START, "node_a")
builder8.add_edge("node_a", "node_c")
builder8.add_edge("node_c", "node_b")
builder8.add_edge("node_", END)

graph8 = builder8.compile()

print("\n🧪 测试 8：图级默认配置")
print("节点 A: 使用默认重试和错误处理")
print("节点 B: 正常执行")
print("节点 C: 使用自定义错误处理器")

node_a_count = 0
result = graph8.invoke({"results": []})

print(f"\n📊 结果: {result['results']}")

print("""
配置优先级：
----------
1. 节点级配置（add_node 参数）
2. 图级默认配置（set_node_defaults）
3. 系统默认值

示例：
builder.set_node_defaults(
    retry_policy=RetryPolicy(max_attempts=3),
    error_handler=default_handler,
    timeout=TimeoutPolicy(run_timeout=30)
)

builder.add_node("special", special_node, 
    error_handler=custom_handler  # 覆盖默认
)
""")


# ============================================
# 第九部分：实际应用 - 微服务调用
# ============================================

print("\n" + "="*60)
print("🌐 第九部分：实际应用 - 微服务调用链")
print("="*60)

print("""
场景：电商订单处理
1. 用户服务：验证用户
2. 库存服务：检查库存
3. 支付服务：处理支付
4. 物流服务：创建物流单

每个服务都可能失败，需要容错和补偿
""")

class OrderState(TypedDict):
    order_id: str
    user_id: str
    status: str
    steps_completed: list[str]
    error_log: list[str]


# 模拟各个微服务
user_service_calls = 0

async def call_user_service(state: OrderState, runtime: Runtime) -> OrderState:
    """调用用户服务"""
    global user_service_calls
    user_service_calls += 1
    
    print(f"  👤 调用用户服务 (尝试 #{user_service_calls})")
    
    if user_service_calls == 1:
        print(f"     ❌ 网络超时")
        raise ConnectionError("User service timeout")
    
    print(f"     ✅ 用户验证成功")
    return {"steps_completed": ["user_verified"]}


async def call_inventory_service(state: OrderState) -> OrderState:
    """调用库存服务"""
    print(f"  📦 调用库存服务")
    await asyncio.sleep(0.5)
    print(f"     ✅ 库存充足")
    return {"steps_completed": ["inventory_checked"]}


payment_service_calls = 0

async def call_payment_service(state: OrderState) -> OrderState:
    """调用支付服务（会失败）"""
    global payment_service_calls
    payment_service_calls += 1
    
    print(f"  💳 调用支付服务 (尝试 #{payment_service_calls})")
    
    # 模拟支付服务不稳定
    raise RuntimeError("Payment service unavailable")


def payment_compensation(state: OrderState, error: NodeError) -> Command:
    """支付失败补偿"""
    print(f"\n  🔄 支付失败，执行补偿:")
    print(f"     - 释放库存")
    print(f"     - 通知用户")
    
    return Command(
        update={
            "status": "payment_failed",
            "error_log": [f"Payment failed: {error.error}"]
        },
        goto="notify_user"
    )


async def notify_user(state: OrderState) -> OrderState:
    """通知用户"""
    print(f"  📧 通知用户订单失败")
    return {"status": "user_notified"}


# 构建微服务调用链
builder9 = StateGraph(OrderState)

# 设置默认容错策略
builder9.set_node_defaults(
    retry_policy=RetryPolicy(
        max_attempts=3,
        initial_interval=0.3,
        backoff_factor=2.0
    ),
    timeout=TimeoutPolicy(run_timeout=5)
)

# 添加服务节点
builder9.add_node("user_service", call_user_service)
builder9.add_node("inventory_service", call_inventory_service)
builder9.add_node(
    "payment_service",
    call_payment_service,
    error_handler=payment_compensation  # 支付失败时补偿
)
builder9.add_node("notify_user", notify_user)

# 构建流程
builder9.add_edge(START, "user_service")
builder9.add_edge("user_service", "inventory_service")
builder9.add_edge("inventory_service", "payment_service")
# payment_service 失败时会通过 error_handler 路由到 notify_user

graph9 = builder9.compile()

print("\n🧪 测试 9：微服务调用链")
print("模拟：用户服务重试成功，支付服务失败并补偿")

async def run_test_9():
    global user_service_calls, payment_service_calls
    user_service_calls = 0
    payment_service_calls = 0
    
    result = await graph9.ainvoke({
        "order_id": "ORD-12345",
        "user_id": "USER-001",
        "status": "pending",
        "steps_completed": [],
        "error_log": []
    })
    
    print(f"\n📊 订单处理结果:")
    print(f"   订单 ID: {result['order_id']}")
    print(f"   最终状态: {result['status']}")
    print(f"   完成步骤: {result['steps_completed']}")
    print(f"   错误日志: {result['error_log']}")

asyncio.run(run_test_9())


# ============================================
# 第十部分：容错策略总结
# ============================================

print("\n" + "="*60)
print("📚 容错策略总结")
print("="*60)

print("""
┌─────────────────────┬──────────────────────────────────────┐
│      机制           │              使用场景                │
├─────────────────────┼──────────────────────────────────────┤
│ Retry Policy        │ 网络抖动、临时故障、速率限制         │
│ Timeout             │ 防止节点卡死、限制响应时间           │
│ Error Handler       │ 补偿逻辑、降级处理、Saga 模式        │
│ Fallback            │ 主备切换、多数据源                   │
│ Graph Defaults      │ 统一配置、减少重复代码               │
└─────────────────────┴──────────────────────────────────────┘

容错机制执行顺序：
----------------
1. 节点执行
2. 发生异常
3. 检查超时（如果是 NodeTimeoutError）
4. 应用重试策略
5. 重试耗尽
6. 调用错误处理器
7. 更新状态 / 路由到其他节点

最佳实践：
---------
1. 网络调用：使用 retry_policy + timeout
2. 关键操作：添加 error_handler 做补偿
3. 长时间操作：使用 idle_timeout + heartbeat
4. 多节点图：使用 set_node_defaults 统一配置
5. 主备模式：在节点内检查 runtime.execution_info.node_attempt

错误类型处理策略：
----------------
┌──────────────────┬──────────┬────────────────────────┐
│   错误类型       │  处理者  │        策略            │
├──────────────────┼──────────┼────────────────────────┤
│ 临时错误         │  系统    │ retry_policy           │
│ (网络、超时)     │          │                        │
├──────────────────┼──────────┼────────────────────────┤
│ LLM 可恢复错误   │  LLM     │ 存入 state，循环重试   │
│ (工具失败)       │          │                        │
├──────────────────┼──────────┼────────────────────────┤
│ 需要用户输入     │  人工    │ interrupt()            │
├──────────────────┼──────────┼────────────────────────┤
│ 重试后仍失败     │  开发者  │ error_handler          │
├──────────────────┼──────────┼────────────────────────┤
│ 未预期错误       │  开发者  │ 让其冒泡，用于调试     │
└──────────────────┴──────────┴────────────────────────┘
""")

print("""
跨语言对比：
----------
Python (LangGraph):
  builder.add_node(
      "api_call",
      api_call,
      retry_policy=RetryPolicy(max_attempts=3),
      timeout=TimeoutPolicy(run_timeout=30),
      error_handler=compensate
  )

JavaScript (类似概念):
  async function withRetry(fn, options) {
      for (let i = 0; i < options.maxAttempts; i++) {
          try {
              return await Promise.race([
                  fn(),
                  timeout(options.timeout)
              ]);
          } catch (err) {
              if (i === options.maxAttempts - 1) {
                  return options.errorHandler(err);
              }
              await sleep(options.backoff * i);
          }
      }
  }

Go (类似概念):
  func withRetry(fn func() error, opts RetryOptions) error {
      for i := 0; i < opts.MaxAttempts; i++ {
          ctx, cancel := context.WithTimeout(
              context.Background(),
              opts.Timeout,
          )
          defer cancel()
          
          err := fn()
          if err == nil {
              return nil
          }
          
          if i == opts.MaxAttempts-1 {
              return opts.ErrorHandler(err)
          }
          
          time.Sleep(opts.Backoff * time.Duration(i))
      }
      return nil
  }
""")

print("\n" + "="*60)
print("✅ 容错性示例完成!")
print("="*60)
print("\n📚 学到的内容:")
print("   1. 重试策略（RetryPolicy）")
print("   2. 自定义重试逻辑")
print("   3. Fallback 模式")
print("   4. 超时控制（run_timeout, idle_timeout）")
print("   5. 心跳机制（heartbeat）")
print("   6. 超时 + 重试组合")
print("   7. 错误处理器（Error Handler）")
print("   8. Saga 补偿模式")
print("   9. 图级默认配置")
print("   10. 微服务调用链实战")
print("\n💡 关键要点:")
print("   • 容错机制可以组合使用")
print("   • 超时只适用于异步节点")
print("   • 错误处理器在重试耗尽后执行")
print("   • 使用 Command 可以路由到其他节点")
print("   • set_node_defaults 避免重复配置")
print("="*60)
