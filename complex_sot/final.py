from StackOverflow import Stack_overflow_tool
from get_urls import get_url_tool
from summarizer import StackOverflowSummarizer

from typing import Annotated, Dict, Any
from typing_extensions import TypedDict
from langchain_core.messages import SystemMessage, ToolMessage, HumanMessage, AIMessage, AnyMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
import uuid

class AgentState(TypedDict):
    """
    TypedDict to represent the state of the agent during interaction.

    Attributes:
        messages (list[AnyMessage]): List of messages exchanged so far, annotated to use 'add_messages' for
                                    graph state management.
    """
    messages: Annotated[list[AnyMessage], add_messages]
    
class Agent:
    """
    A conversational agent that uses an LLM and multiple tools integrated via a state graph for
    sequential and conditional message processing.

    Attributes:
        model: The language model instance (e.g., ChatGroq).
        llm: The language model bound with tools for invocation.
        system (str): Optional system prompt context.
        tools (dict): Mapping of tool names to tool instances.
        tool_names (list): Ordered list of tool names.
        tries (int): Counter for the number of attempts.
        max_tries (int): Maximum allowed tries before stopping.
        graph (StateGraph): Compiled graph managing the agent's conversational states and transitions.
    """
    def __init__(self, model, tools, system=""):
        self.model = model
        self.llm = model.bind_tools(tools)  # Bind tools for tool usage during model calls
        self.system = system
        self.tools = {t.name: t for t in tools}
        self.tool_names = [t.name for t in tools]
        self.tries = 0
        self.max_tries = 3

        # Initialize state graph for conversation flow management
        graph = StateGraph(AgentState)
        graph.add_node("llm", self.call_groq)

        # Add a node for each tool to handle invoking the tool action
        for tool in tools:
            graph.add_node(tool.name, self.take_action_for(tool.name))

        # Add nodes to refine questions and answers if needed
        graph.add_node("refine_question", self.refine_question)
        graph.add_node("refine_answer", self.refine_answer)

        # Chain tools sequentially (tool_1 -> tool_2 -> tool_3 ...)
        for x, y in zip(self.tool_names, self.tool_names[1:]):
            graph.add_edge(x, y)

        # Conditional branching after LLM step:
        # - If results found: go to first tool
        # - If no results: refine the question
        # - If max tries exceeded: end conversation
        graph.add_conditional_edges(
            "llm",
            self.results_found,
            {
                "yes": self.tool_names[0],
                "no": "refine_question",
                "limit exceeded": END
            }
        )

        graph.add_edge("refine_question", "llm")  # After refining question, try LLM again

        # After last tool runs, decide whether to refine answer or refine question
        graph.add_conditional_edges(self.tool_names[-1],
            self.relevent_answer,
            {
                "yes": "refine_answer",
                "no": "refine_question"
            }
        )

        graph.add_edge("refine_answer", END)  # After refining answer, end conversation

        graph.set_entry_point("llm")  # Start from the LLM node
        self.graph = graph.compile()

    def call_groq(self, state: AgentState) -> AgentState:
        """
        Invokes the LLM with the current messages plus optional system prompt.

        Args:
            state (AgentState): Current agent state including message history.

        Returns:
            AgentState: New state with the LLM response message.
        """
        messages = state["messages"]
        if self.system:
            messages = [SystemMessage(content=self.system)] + messages
        response = self.llm.invoke(messages)
        return {"messages": [response]}

    def refine_question(self, state: AgentState) -> AgentState:
        """
        Refines the last question in the conversation to be clearer or more specific.

        Args:
            state (AgentState): Current agent state with messages.

        Returns:
            AgentState: New state with the refined question as a HumanMessage.
        """
        last_msg = state["messages"][-1].content
        prompt = f"Refine the question: {last_msg} to be more specific and clear."
        messages = [SystemMessage(content=self.system), HumanMessage(content=prompt)]
        response = self.model.invoke(messages)
        return {"messages": [HumanMessage(content=response.content)]}

    def refine_answer(self, state: AgentState) -> AgentState:
        """
        Refines the last answer given by the model to be more specific and clear.

        Args:
            state (AgentState): Current agent state with messages.

        Returns:
            AgentState: New state with the refined answer as an AIMessage.
        """
        last_msg = state["messages"][-1].content
        prompt = f"Refine the answer: {last_msg} to be more specific and clear."
        messages = [SystemMessage(content=self.system), HumanMessage(content=prompt)]
        response = self.model.invoke(messages)
        return {"messages": [AIMessage(content=response.content)]}
    
    def relevent_answer(self, state: AgentState) -> str:
        """
        Checks if the last answer message indicates relevant Stack Overflow answers found.

        Args:
            state (AgentState): Current agent state with messages.

        Returns:
            str: "yes" if relevant answers found, else "no".
        """
        last_msg = state["messages"][-1].content
        if last_msg == "No relevant Stack Overflow questions found for the query.":
            return "no"
        else:
            return "yes"

    def results_found(self, state: AgentState) -> str:
        """
        Determines if relevant results are found for the user's query by calling the URL tool.

        Args:
            state (AgentState): Current agent state with messages.

        Returns:
            str: One of "yes", "no", or "limit exceeded" based on conditions.
        """
        if self.tries >= self.max_tries:
            self.tries = 0
            print("Max tries exceeded")
            return "limit exceeded"
        self.tries += 1
        query = state["messages"][0].content
        try:
            tool_response = self.tools["get_url_tool"].invoke({"query": query})
            if tool_response:
                return "yes"
            else:
                return "no"
        except Exception as e:
            print("Tool call error:", e)
            return "limit exceeded"

    def take_action_for(self, tool_name):
        """
        Returns a handler function that processes tool calls and triggers subsequent tools if needed.

        Args:
            tool_name (str): Name of the tool to handle.

        Returns:
            function: A state handler function for the tool.
        """
        def _handler(state: AgentState):
            last_msg = state['messages'][-1]

            # Process tool calls only if the last message is from AI and has tool calls
            if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
                messages = []
                tool_calls = last_msg.tool_calls

                for t in tool_calls:
                    if t['name'] == tool_name:
                        
                        print(f'Calling tool: {tool_name}')
                        results = []
                        result = self.tools[t['name']].invoke(t['args'])
                        results.append(result)
                        messages.append(ToolMessage(
                            tool_call_id=t["id"],
                            name=t["name"],
                            content=str(result)
                        ))

                        # If there is a next tool, prepare its arguments and trigger it
                        if tool_name in self.tool_names:
                            idx = self.tool_names.index(tool_name)
                            if idx + 1 < len(self.tool_names):
                                next_tool = self.tool_names[idx + 1]
                                arg = list(self.tools[next_tool].args_schema.model_json_schema()['properties'].keys())
                                args = {}
                                if "query" in arg:
                                    args["query"] = state['messages'][0].content
                                    arg.remove("query")
                                for x, y in zip(arg, results):
                                    args[x] = y
                                messages.append(AIMessage(
                                    content=f"Triggering next tool: {next_tool}",
                                    tool_calls=[{
                                        "name": next_tool,
                                        "args": args,
                                        "id": f"synthetic-{next_tool}-{t['id']}"
                                    }]
                                ))

                return {
                    "messages": messages
                }

            # Return empty dict if no applicable tool calls found
            return {}

        return _handler


from langchain_groq import ChatGroq
from dotenv import load_dotenv
load_dotenv()

# Initialize the language model
model = ChatGroq(model="llama-3.3-70b-versatile")

# Instantiate the Agent with the model, tools, and optional system prompt
abot = Agent(model, [get_url_tool, Stack_overflow_tool, StackOverflowSummarizer], system="You are a helpful assistant")

# Start conversation with a user question wrapped in a HumanMessage
messages = HumanMessage(content="How to reverse a string in Python?")

# Stream through the graph events and print responses
for event in abot.graph.stream({"messages": messages}):
    print(event)
