"""测试 stream.output 的正确用法"""
import asyncio
from typing import TypedDict
from langgraph.graph import StateGraph, START, END


class State(TypedDict):
    value: int


def node1(state: State) -> State:
    return {"value": state["value"] + 1}


async def test_stream_output():
    graph = StateGraph(State)
    graph.add_node("node1", node1)
    graph.add_edge(START, "node1")
    graph.add_edge("node1", END)
    compiled = graph.compile()
    
    # 测试 astream_events
    stream = await compiled.astream_events({"value": 0}, version="v3")
    
    # 先消费流
    async for value in stream.values:
        print(f"值: {value}")
    
    # 然后访问 output
    print(f"\nstream.output 类型: {type(stream.output)}")
    print(f"stream.output: {stream.output}")
    
    # 尝试不同的访问方式
    try:
        result = stream.output
        print(f"直接访问成功: {result}")
    except Exception as e:
        print(f"直接访问失败: {e}")
    
    try:
        result = await stream.output
        print(f"await 访问成功: {result}")
    except Exception as e:
        print(f"await 访问失败: {e}")


if __name__ == "__main__":
    asyncio.run(test_stream_output())
