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
    messages: Annotated[list[AnyMessage], add_messages]
    
class Agent:
    def __init__(self, model, tools, system=""):
        self.model = model
        self.llm = model.bind_tools(tools)
        self.system = system
        self.tools = {t.name: t for t in tools}
        self.tool_names = [t.name for t in tools]
        self.tries=0
        self.max_tries=3

        # Build the state graph
        graph = StateGraph(AgentState)
        graph.add_node("llm", self.call_groq)

        for tool in tools:
            graph.add_node(tool.name, self.take_action_for(tool.name))

        graph.add_node("refine_question", self.refine_question)
        graph.add_node("refine_answer", self.refine_answer)

        # Sequential chaining of tools (if needed)
        for x, y in zip(self.tool_names, self.tool_names[1:]):
            graph.add_edge(x, y)

        # Conditional branching based on result
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
        # graph.add_edge(self.tool_names[-1], "refine_answer")
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
    
    def relevent_answer(self,state: AgentState) -> str:
        last_msg = state["messages"][-1].content
        if last_msg=="No relevant Stack Overflow questions found for the query.":
            return "no"
        else:
            return "yes"

    def results_found(self, state: AgentState) -> str:
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
        def _handler(state: AgentState):
            last_msg = state['messages'][-1]

            if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
                messages = []
                tool_calls = last_msg.tool_calls

                for t in tool_calls:
                    if t['name'] == tool_name:
                        
                        print(f'Calling tool: {tool_name}')
                        results=[]
                        result = self.tools[t['name']].invoke(t['args'])
                        results.append(result)
                        messages.append(ToolMessage(
                            tool_call_id=t["id"],
                            name=t["name"],
                            content=str(result)
                        ))
                        if tool_name in self.tool_names:
                            idx = self.tool_names.index(tool_name)
                            
                            if idx + 1 < len(self.tool_names):
                                next_tool = self.tool_names[idx + 1]
                                arg = list(self.tools[next_tool].args_schema.model_json_schema()['properties'].keys())
                                args={}
                                if "query" in arg:
                                    args["query"]=state['messages'][0].content
                                    arg.remove("query")
                                for x,y in zip(arg,results):
                                    args[x]=y
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

            return {}

        return _handler

from langchain_groq import ChatGroq
from dotenv import load_dotenv
load_dotenv()

model=ChatGroq(model="llama-3.3-70b-versatile")
abot=Agent(model,[get_url_tool,Stack_overflow_tool,StackOverflowSummarizer],system="You are a helpful assistant")

messages=HumanMessage(content="How to reverse a string in Python?")
for event in abot.graph.stream({"messages": messages}):
    print(event)
