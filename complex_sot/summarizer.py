from typing import List, Dict
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage

# Load your LLM
model = ChatGroq(model="llama3-8b-8192")

# Pydantic schema for the tool input
class StackOverflowSummaryInput(BaseModel):
    query: str = Field(..., description="The user's original coding query.")
    stackoverflow_data: List[Dict] = Field(
        ..., 
        description="""List of questions and answers from the StackOverflow Tool.
        Each entry should be a dictionary with a 'question' and an 'answers' key.
        The 'answers' key contains a list of dictionaries with 'Upvotes', 'Body', and 'Link'."""
    )

# Function to filter relevant questions using the LLM
def similarity_filter(query: str, questions: List[Dict]) -> List[Dict]:
    prompt = f"""
Given the user query: "{query}", identify which of the following questions are relevant.
Respond with a list of the most relevant questions (1-5) that are semantically similar.

Questions:
{[q['question'] for q in questions]}

Just return the relevant questions as a new line character seperated list.
If no questions are relevant, return an empty string.
"""
    response = model.invoke([HumanMessage(content=prompt)]).content
    relevant_questions = response.strip().split('\n')
    return [q for q in questions if q['question'] in relevant_questions]

# Main summarization function
def summarize_answers(query: str, stackoverflow_data: List[Dict]) -> str:
    relevant_data = similarity_filter(query, stackoverflow_data)

    if not relevant_data:
        return "No relevant Stack Overflow questions found for the query."

    context = ""
    for item in relevant_data:
        context += f"\n\nQuestion: {item['question']}\n"
        for ans in item['answers']:
            context += f"Upvotes: {ans['Upvotes']}\nAnswer: {ans['Body']}\n"

    prompt = f"""
You are a coding assistant. Summarize the most helpful and highly upvoted answers for the following user query:
"{query}"

Here are the relevant Stack Overflow answers:
{context}

Only include the most insightful and concise information. Mention if multiple solutions exist.
"""
    response = model.invoke([HumanMessage(content=prompt)])
    return response.content

# Create the StructuredTool
StackOverflowSummarizer = StructuredTool.from_function(
    func=summarize_answers,
    name="StackOverflowSummarizer",
    description="""Summarizes relevant and highly upvoted Stack Overflow answers based on a user's coding query. 
                   Only includes questions that are semantically similar to the user's query.""",
    args_schema=StackOverflowSummaryInput
)
