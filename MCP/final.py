from typing import Annotated, Dict, Any, List, Union
from typing_extensions import TypedDict
from langchain_core.messages import SystemMessage, ToolMessage, HumanMessage, AIMessage, AnyMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
import uuid
import json

# LangChain Imports
from langchain_core.tools import BaseTool # The type you want to end up with

# FastMCP Imports (still needed for the underlying client)
from fastmcp import Client
import asyncio

# IMPORTANT: LangChain MCP Adapters import
from langchain_mcp_adapters.client import MultiServerMCPClient # For connecting to servers and loading tools
from langchain_mcp_adapters.tools import load_mcp_tools # The function to convert MCP tools to LangChain tools

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

class Agent:
    def __init__(self, model, lc_tools: List[BaseTool], system=""): # Now expects List[BaseTool] directly
        self.model = model
        self.system = system
        self.tries = 0
        self.max_tries = 3

        self.lc_tools = lc_tools # Directly use the LangChain-compatible tools
        self.llm = model.bind_tools(self.lc_tools)
        self.tools = {t.name: t for t in self.lc_tools} # Store callable tools by name (LangChain BaseTool instances)
        self.tool_names = [t.name for t in self.lc_tools] # Ordered list of tool names

        # Initialize state graph
        graph = StateGraph(AgentState)
        graph.add_node("llm", self.call_groq)

        # Add a node for each tool
        for tool_lc in self.lc_tools:
            graph.add_node(tool_lc.name, self.take_action_for(tool_lc.name))

        graph.add_node("refine_question", self.refine_question)
        graph.add_node("refine_answer", self.refine_answer)

        # Chain tools sequentially
        for x, y in zip(self.tool_names, self.tool_names[1:]):
            graph.add_edge(x, y)

        # Conditional branching after LLM step
        graph.add_conditional_edges(
            "llm",
            self.results_found,
            {
                "yes": self.tool_names[0],
                "no": "refine_question",
                "limit exceeded": END
            }
        )

        graph.add_edge("refine_question", "llm")

        graph.add_conditional_edges(self.tool_names[-1],
            self.relevent_answer,
            {
                "yes": "refine_answer",
                "no": "refine_question"
            }
        )

        graph.add_edge("refine_answer", END)

        graph.set_entry_point("llm")
        self.graph = graph.compile()

    # call_groq, refine_question, refine_answer, relevent_answer remain the same
    def call_groq(self, state: AgentState) -> AgentState:
        messages = state["messages"]
        if self.system:
            messages = [SystemMessage(content=self.system)] + messages
        response = self.llm.invoke(messages)
        return {"messages": [response]}

    def refine_question(self, state: AgentState) -> AgentState:
        last_msg = state["messages"][-1].content
        prompt = f"Refine the question: {last_msg} to be more specific and clear."
        messages = [SystemMessage(content=self.system), HumanMessage(content=prompt)]
        response = self.model.invoke(messages)
        return {"messages": [HumanMessage(content=response.content)]}

    def refine_answer(self, state: AgentState) -> AgentState:
        last_msg = state["messages"][-1].content
        prompt = f"Refine the answer: {last_msg} to be more specific and clear."
        messages = [SystemMessage(content=self.system), HumanMessage(content=prompt)]
        response = self.model.invoke(messages)
        return {"messages": [AIMessage(content=response.content)]}

    def relevent_answer(self, state: AgentState) -> str:
        last_msg = state["messages"][-1].content
        if last_msg == "No relevant Stack Overflow questions found for the query.":
            return "no"
        else:
            return "yes"

    async def results_found(self, state: AgentState) -> str:
        print("Checking if results are found...")
        if self.tries >= self.max_tries:
            self.tries = 0
            print("Max tries exceeded")
            return "limit exceeded"
        self.tries += 1
        query = state["messages"][0].content
        # try:
            # Use the LangChain tool directly here
            # The tool name here must match the @tool decorator name
        tool_response = await self.tools["get_urls"].ainvoke({"query": query}) # 'get_urls' is the correct name
        if tool_response: # Assuming get_urls returns a non-empty list on success
            return "yes"
        else:
            return "no"
        # except Exception as e:
            # pass
            # print("Tool call error in results_found:", e)
            # return "limit exceeded"

    def take_action_for(self, tool_name):
        """
        Returns a handler function that processes tool calls and triggers subsequent tools if needed.
        Args:
            tool_name (str): Name of the tool to handle.
        Returns:
            function: A state handler function for the tool.
        """
        async def _handler(state: AgentState):
            last_msg = state['messages'][-1]

            if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
                messages = []
                tool_calls = last_msg.tool_calls

                for t in tool_calls:
                    if t['name'] == tool_name:
                        print(f'Agent: Calling tool: {tool_name}')
                        
                        # Call the LangChain tool's invoke method (which MCP adapter provides)
                        raw_tool_result = await self.tools[t['name']].ainvoke(t['args'])
                        print("raw : ",raw_tool_result)
                        if isinstance(raw_tool_result, str): # <-- This condition will be TRUE for get_urls's raw output
                                try:
                                    result = json.loads(raw_tool_result) # <-- This will parse the JSON string into a Python dict
                                    print("modified    \n\n\n\n",result)
                                    print(f"DEBUG: Parsed tool '{tool_name}' string result into object.")
                                except Exception as e:
                                    print(f"WARNING: Tool '{tool_name}' error : {e}")
                                    result = raw_tool_result
                        messages.append(ToolMessage(
                            tool_call_id=t["id"],
                            name=t["name"],
                            content=result# Convert result to string for ToolMessage content
                        ))

                        # This logic for chaining tools needs to be robust.
                        # It should determine the next tool based on your graph's flow and
                        # correctly map the output of the current tool to the input of the next.
                        if tool_name in self.tool_names:
                            idx = self.tool_names.index(tool_name)
                            if idx + 1 < len(self.tool_names):
                                next_tool_lc = self.lc_tools[idx + 1]
                                next_tool_name = next_tool_lc.name
                                
                                args = {}
                                # Example specific argument mapping based on your tool chain:
                                if tool_name == 'get_urls' and next_tool_name == 'stack_overflow':
                                    # Assuming get_urls returns a list of URLs
                                    args['urls'] = result
                                elif tool_name == 'stack_overflow' and next_tool_name == 'summarize_stack_overflow':
                                    # Assuming stack_overflow returns a dictionary of answers
                                    args['query'] = state['messages'][0].content
                                    args['answers'] = result
                                # Add more elifs for other tool transitions if needed

                                messages.append(AIMessage(
                                    content=f"Triggering next tool: {next_tool_name}",
                                    tool_calls=[{
                                        "name": next_tool_name,
                                        "args": args,
                                        "id": f"synthetic-{next_tool_name}-{uuid.uuid4()}"
                                    }]
                                ))

                return {
                    "messages": messages
                }
            return {}
        return _handler


# --- Main Execution Flow ---
from langchain_groq import ChatGroq
from dotenv import load_dotenv
load_dotenv()

# Initialize the language model
model = ChatGroq(model="llama-3.3-70b-versatile") # Use the correct model name for Groq

print("Connecting to MCP server and loading tools...")

async def main():
    # Use MultiServerMCPClient to get the session and then load tools
    # The connections dict maps server names to their details (URL, transport etc.)
    # Replace "my_server" and the URL with your actual server configuration
    mcp_client_adapter = MultiServerMCPClient(
        connections={
            "my_server": {
                "transport": "streamable_http",
                "url": "http://localhost:8000/mcp", # Your FastMCP server URL
            }
        }
    )

    lc_tools: List[BaseTool] = []
    async with mcp_client_adapter.session("my_server") as session:
        # This is the magic line! It loads tools and converts them to LangChain's BaseTool format.
        lc_tools = await load_mcp_tools(session)
    
        print(f"Loaded LangChain-compatible tools: {[t.name for t in lc_tools]}")

        # Instantiate the Agent with the model and the LangChain-compatible tools
        abot = Agent(model, lc_tools, system="You are a helpful assistant that can search for information on Stack Overflow.")

        # Start conversation with a user question wrapped in a HumanMessage
        messages = HumanMessage(content="How to reverse a string in Python?")

        # Stream through the graph events and print responses
        print("\nStarting agent stream...")
        async for event in abot.graph.astream({"messages": messages}):
            print(event)

if __name__ == "__main__":
    asyncio.run(main())