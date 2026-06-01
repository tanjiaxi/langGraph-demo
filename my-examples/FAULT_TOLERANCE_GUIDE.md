# LangGraph 容错性指南

## 概述

LangGraph 提供三种核心容错机制：

1. **Retries（重试）**: 自动重试失败的节点
2. **Timeouts（超时）**: 限制节点执行时间
3. **Error Handling（错误处理）**: 重试耗尽后的恢复逻辑

## 执行流程

```
节点执行 → 异常 → 重试策略 → 重试耗尽 → 错误处理器 → 恢复/路由
```

## 一、重试策略（Retry Policy）

### 基础用法

```python
from langgraph.types import RetryPolicy

builder.add_node(
    "api_call",
    api_call,
    retry_policy=RetryPolicy(
        max_attempts=3,        # 最多尝试 3 次
        initial_interval=0.5,  # 首次重试前等待 0.5 秒
        backoff_factor=2.0,    # 每次重试间隔翻倍
        max_interval=10.0,     # 最大间隔 10 秒
        jitter=True           # 添加随机抖动
    )
)
```

### 默认重试行为

- ✅ 重试：网络错误、超时、5xx HTTP 错误
- ❌ 不重试：ValueError, TypeError, SyntaxError 等编程错误

### 自定义重试逻辑

```python
from langgraph.types import default_retry_on

def custom_retry_on(exc: BaseException) -> bool:
    if isinstance(exc, MyCustomError):
        return False  # 不重试
    if isinstance(exc, RateLimitError):
        return True   # 总是重试
    return default_retry_on(exc)  # 使用默认逻辑

builder.add_node(
    "api_call",
    api_call,
    retry_policy=RetryPolicy(retry_on=custom_retry_on)
)
```

### Fallback 模式

```python
from langgraph.runtime import Runtime

def api_with_fallback(state: State, runtime: Runtime) -> State:
    attempt = runtime.execution_info.node_attempt
    
    if attempt == 1:
        # 第一次尝试主 API
        return call_primary_api()
    else:
        # 后续尝试备用 API
        return call_fallback_api()
```

## 二、超时控制（Timeouts）

⚠️ **重要**: 超时只适用于异步节点！

### Run Timeout（硬性超时）

```python
from langgraph.types import TimeoutPolicy

builder.add_node(
    "slow_node",
    slow_async_node,
    timeout=TimeoutPolicy(run_timeout=30)  # 30 秒硬性超时
)
```

### Idle Timeout（空闲超时）

```python
async def long_running_node(state: State, runtime: Runtime) -> State:
    for batch in fetch_batches():
        process(batch)
        runtime.heartbeat()  # 重置空闲计时器
    return {"result": "done"}

builder.add_node(
    "long_node",
    long_running_node,
    timeout=TimeoutPolicy(
        idle_timeout=30,           # 30 秒无进度则超时
        refresh_on="heartbeat"     # 只有心跳才重置
    )
)
```

### 超时 + 重试组合

```python
builder.add_node(
    "api_call",
    api_call,
    timeout=TimeoutPolicy(run_timeout=10),
    retry_policy=RetryPolicy(max_attempts=3)
)
```

## 三、错误处理器（Error Handler）

### 基础用法

```python
from langgraph.errors import NodeError
from langgraph.types import Command

def error_handler(state: State, error: NodeError) -> Command:
    print(f"节点 {error.node} 失败: {error.error}")
    
    return Command(
        update={"status": "recovered"},
        goto="recovery_node"  # 路由到恢复节点
    )

builder.add_node(
    "risky_operation",
    risky_operation,
    retry_policy=RetryPolicy(max_attempts=3),
    error_handler=error_handler
)
```

### Saga 补偿模式

```python
def payment_error_handler(state: State, error: NodeError) -> Command:
    # 执行补偿逻辑
    release_inventory()
    notify_user()
    
    return Command(
        update={"status": "compensated"},
        goto="finalize"
    )

builder.add_node("reserve_inventory", reserve_inventory)
builder.add_node(
    "charge_payment",
    charge_payment,
    retry_policy=RetryPolicy(max_attempts=3),
    error_handler=payment_error_handler
)
builder.add_node("finalize", finalize)
```

## 四、图级默认配置

### 统一配置

```python
builder = StateGraph(State)

# 设置默认配置
builder.set_node_defaults(
    retry_policy=RetryPolicy(max_attempts=3),
    error_handler=default_error_handler
)

# 所有节点都会继承默认配置
builder.add_node("node_a", node_a)
builder.add_node("node_b", node_b)

# 个别节点可以覆盖默认值
builder.add_node(
    "node_c",
    node_c,
    error_handler=custom_error_handler
)
```

### 配置优先级

1. 节点级配置（`add_node` 参数）
2. 图级默认配置（`set_node_defaults`）
3. 系统默认值

## 五、实战场景

### 场景 1: 网络 API 调用

```python
builder.add_node(
    "call_external_api",
    call_api,
    retry_policy=RetryPolicy(
        max_attempts=3,
        initial_interval=1.0,
        backoff_factor=2.0
    ),
    timeout=TimeoutPolicy(run_timeout=30)
)
```

### 场景 2: 微服务调用链

```python
builder.set_node_defaults(
    retry_policy=RetryPolicy(max_attempts=3)
)

builder.add_node("user_service", call_user_service)
builder.add_node("inventory_service", call_inventory_service)
builder.add_node(
    "payment_service",
    call_payment_service,
    error_handler=payment_compensation
)
```

### 场景 3: 长时间处理

```python
async def process_large_file(state: State, runtime: Runtime) -> State:
    for chunk in read_chunks():
        process(chunk)
        runtime.heartbeat()  # 定期发送心跳
    return {"result": "done"}

builder.add_node(
    "processor",
    process_large_file,
    timeout=TimeoutPolicy(
        idle_timeout=60,
        refresh_on="heartbeat"
    )
)
```

## 六、错误类型处理策略

| 错误类型 | 处理者 | 策略 |
|---------|--------|------|
| 临时错误（网络、超时） | 系统 | `retry_policy` |
| LLM 可恢复错误 | LLM | 存入 state，循环重试 |
| 需要用户输入 | 人工 | `interrupt()` |
| 重试后仍失败 | 开发者 | `error_handler` |
| 未预期错误 | 开发者 | 让其冒泡，用于调试 |

## 七、最佳实践

1. **网络调用**: 使用 `retry_policy` + `timeout`
2. **关键操作**: 添加 `error_handler` 做补偿
3. **长时间操作**: 使用 `idle_timeout` + `heartbeat`
4. **多节点图**: 使用 `set_node_defaults` 统一配置
5. **主备模式**: 在节点内检查 `runtime.execution_info.node_attempt`

## 八、常见陷阱

### ❌ 错误：同步节点使用超时

```python
def sync_node(state):  # 同步函数
    time.sleep(10)
    return state

builder.add_node(
    "sync_node",
    sync_node,
    timeout=TimeoutPolicy(run_timeout=5)  # ❌ 会报错
)
```

### ✅ 正确：异步节点使用超时

```python
async def async_node(state):  # 异步函数
    await asyncio.sleep(10)
    return state

builder.add_node(
    "async_node",
    async_node,
    timeout=TimeoutPolicy(run_timeout=5)  # ✅ 正确
)
```

### ❌ 错误：错误处理器是同步的，但继承了超时配置

```python
builder.set_node_defaults(
    timeout=TimeoutPolicy(run_timeout=30)  # ❌ 会应用到错误处理器
)

def sync_error_handler(state, error):  # 同步函数
    return {"status": "handled"}

builder.add_node(
    "node",
    node,
    error_handler=sync_error_handler  # ❌ 会报错
)
```

### ✅ 正确：单独为节点设置超时

```python
builder.set_node_defaults(
    retry_policy=RetryPolicy(max_attempts=3)  # 只设置重试
)

builder.add_node(
    "node",
    async_node,
    timeout=TimeoutPolicy(run_timeout=30),  # 单独设置超时
    error_handler=sync_error_handler
)
```

## 九、跨语言对比

### Python (LangGraph)

```python
builder.add_node(
    "api_call",
    api_call,
    retry_policy=RetryPolicy(max_attempts=3),
    timeout=TimeoutPolicy(run_timeout=30),
    error_handler=compensate
)
```

### JavaScript (类似概念)

```javascript
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
```

### Go (类似概念)

```go
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
```

## 参考资料

- [LangGraph 容错性文档](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)
- [完整示例代码](./examples10_fault_tolerance.py)
