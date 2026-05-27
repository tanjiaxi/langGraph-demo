# 条件边（Conditional Edges）完全指南

## 1. 什么是条件边？

**普通边（Edge）**：固定路径
```python
builder.add_edge("A", "B")  # A 总是连接到 B
```

**条件边（Conditional Edge）**：动态路径
```python
builder.add_conditional_edges(
    "A",              # 从 A 出发
    routing_function, # 根据函数决定去哪
)
# A 可能去 B、C 或 D，取决于 routing_function 的返回值
```

---

## 2. 对比三种语言的概念

### Python (LangGraph)
```python
def route(state):
    if state["type"] == "A":
        return "node_a"
    else:
        return "node_b"

builder.add_conditional_edges("start", route)
```

### JavaScript (类似概念)
```javascript
// 类似 React Router 或状态机
const route = (state) => {
    if (state.type === 'A') {
        return 'node_a';
    } else {
        return 'node_b';
    }
};

// 或者路由表
const routes = {
    'A': 'node_a',
    'B': 'node_b'
};
const nextNode = routes[state.type];
```

### Go (类似概念)
```go
func route(state State) string {
    switch state.Type {
    case "A":
        return "node_a"
    default:
        return "node_b"
    }
}

// 或者使用 map
routes := map[string]string{
    "A": "node_a",
    "B": "node_b",
}
nextNode := routes[state.Type]
```

---

## 3. 条件边的三种用法

### 用法 1：直接返回节点名（最简单）

```python
def route(state):
    return "node_a"  # 直接返回节点名称

builder.add_conditional_edges("start", route)
```

### 用法 2：返回键，使用映射表

```python
def route(state):
    return "type_a"  # 返回一个键

builder.add_conditional_edges(
    "start",
    route,
    {
        "type_a": "node_a",  # 映射：键 -> 节点名
        "type_b": "node_b",
    }
)
```

### 用法 3：使用 Literal 类型提示（推荐）

```python
from typing import Literal

def route(state) -> Literal["node_a", "node_b"]:
    if state["value"] > 10:
        return "node_a"
    else:
        return "node_b"

builder.add_conditional_edges("start", route)
```

---

## 4. 完整示例对比

### 示例 1：简单的 if-else

**Python**
```python
def route(state):
    if state["score"] >= 60:
        return "pass_node"
    else:
        return "fail_node"

builder.add_conditional_edges("check", route)
```

**JavaScript 等价**
```javascript
const route = (state) => {
    return state.score >= 60 ? 'pass_node' : 'fail_node';
};
```

**Go 等价**
```go
func route(state State) string {
    if state.Score >= 60 {
        return "pass_node"
    }
    return "fail_node"
}
```

### 示例 2：多路分支

**Python**
```python
def route(state):
    score = state["score"]
    if score >= 90:
        return "excellent"
    elif score >= 60:
        return "pass"
    else:
        return "fail"

builder.add_conditional_edges("grade", route)
```

**JavaScript 等价**
```javascript
const route = (state) => {
    const score = state.score;
    if (score >= 90) return 'excellent';
    if (score >= 60) return 'pass';
    return 'fail';
};
```

**Go 等价**
```go
func route(state State) string {
    switch {
    case state.Score >= 90:
        return "excellent"
    case state.Score >= 60:
        return "pass"
    default:
        return "fail"
    }
}
```

---

## 5. 图结构对比

### 普通边（固定路径）
```
START → A → B → C → END
```

### 条件边（动态路径）
```
START → classify
          ↓
      [条件判断]
       ↙  ↓  ↘
      A   B   C
       ↘  ↓  ↙
        merge → END
```

---

## 6. 实际应用场景

### 场景 1：问题分类路由
```python
def route_by_type(state):
    question_type = state["type"]
    return f"{question_type}_handler"

# technical → technical_handler
# daily → daily_handler
# math → math_handler
```

### 场景 2：错误处理
```python
def route_by_status(state):
    if state["error"]:
        return "error_handler"
    else:
        return "success_handler"
```

### 场景 3：循环控制
```python
def should_continue(state):
    if state["iteration"] < 5:
        return "process_again"  # 继续循环
    else:
        return END  # 结束
```

---

## 7. 调试技巧

### 添加日志
```python
def route(state):
    next_node = "node_a" if state["x"] > 0 else "node_b"
    print(f"🔀 路由: {state['x']} → {next_node}")
    return next_node
```

### 可视化路由
```python
def route(state):
    routes = {
        "A": "node_a",
        "B": "node_b",
        "C": "node_c",
    }
    key = state["type"]
    next_node = routes.get(key, "default_node")
    print(f"路由映射: {key} → {next_node}")
    return next_node
```

---

## 8. 常见错误

### ❌ 错误 1：返回不存在的节点
```python
def route(state):
    return "non_existent_node"  # 运行时错误！
```

### ❌ 错误 2：忘记返回值
```python
def route(state):
    if state["x"] > 0:
        return "node_a"
    # 如果 x <= 0，没有返回值！
```

### ✅ 正确写法
```python
def route(state):
    if state["x"] > 0:
        return "node_a"
    else:
        return "node_b"  # 确保所有路径都有返回值
```

---

## 9. 性能对比

| 特性 | 普通边 | 条件边 |
|------|--------|--------|
| 性能 | 快（编译时确定） | 稍慢（运行时判断） |
| 灵活性 | 低 | 高 |
| 适用场景 | 固定流程 | 动态流程 |

---

## 10. 总结

**条件边 = 动态路由**

```python
# 类比
if-else 语句  →  条件边
switch-case   →  条件边 + 映射表
路由表        →  条件边 + 字典
```

**核心概念**：
1. 路由函数返回**节点名称**（字符串）
2. 根据状态动态决定下一步
3. 类似 JS 的路由或 Go 的 switch

**适用场景**：
- 问题分类
- 错误处理
- 循环控制
- 多路分支
