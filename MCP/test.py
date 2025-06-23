import asyncio
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict
from typing import Annotated
from langchain_core.messages import HumanMessage, AnyMessage
from langgraph.graph.message import add_messages

class TestState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

async def dummy_node(state: TestState) -> TestState:
    print("Executing dummy_node")
    await asyncio.sleep(0.1) # Simulate async work
    return {"messages": [HumanMessage(content="Hello from dummy node!")]}

async def test_streaming():
    graph = StateGraph(TestState)
    graph.add_node("start_node", dummy_node)
    graph.add_edge("start_node", END)
    graph.set_entry_point("start_node")
    
    compiled_graph = graph.compile()

    print("Starting test stream...")
    try:
        # CHANGE THIS LINE: Use astream() for async graphs
        async for event in compiled_graph.astream({"messages": [HumanMessage(content="Initial message")]}):
            print(f"Received event: {event}")
        print("Test stream finished.")
    except TypeError as e:
        print(f"Error during streaming: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_streaming())