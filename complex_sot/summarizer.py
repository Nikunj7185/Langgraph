from typing import List, Dict
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage

# Initialize the language model from Groq's LLaMA 3 8B 8192 model
model = ChatGroq(model="llama3-8b-8192")

class StackOverflowSummaryInput(BaseModel):
    """
    Pydantic schema defining the input structure for the StackOverflow summarizer tool.
    
    Attributes:
        query (str): The user's original coding query to find relevant Stack Overflow content.
        stackoverflow_data (List[Dict]): List of Stack Overflow questions and answers.
            Each dictionary entry must have:
                - 'question': The question text.
                - 'answers': A list of dictionaries with keys:
                    'Upvotes' (int), 'Body' (str), and 'Link' (str).
    """
    query: str = Field(..., description="The user's original coding query.")
    stackoverflow_data: List[Dict] = Field(
        ..., 
        description=(
            "List of questions and answers from the StackOverflow Tool. "
            "Each entry is a dict with 'question' and 'answers'. "
            "'answers' is a list of dicts with 'Upvotes', 'Body', and 'Link'."
        )
    )

def similarity_filter(query: str, questions: List[Dict]) -> List[Dict]:
    """
    Uses the language model to filter and return the most relevant Stack Overflow questions 
    that are semantically similar to the user's query.
    
    Args:
        query (str): The user's coding question or query.
        questions (List[Dict]): List of question dicts from Stack Overflow.
        
    Returns:
        List[Dict]: Filtered list of question dicts deemed relevant by the LLM.
    """
    # Construct a prompt to ask the LLM which questions are relevant
    prompt = f"""
Given the user query: "{query}", identify which of the following questions are relevant.
Respond with a list of the most relevant questions (1-5) that are semantically similar.

Questions:
{[q['question'] for q in questions]}

Just return the relevant questions as a new line character separated list.
If no questions are relevant, return an empty string.
"""
    # Invoke the LLM with the prompt
    response = model.invoke([HumanMessage(content=prompt)]).content
    
    # Parse the response into a list of question strings
    relevant_questions = response.strip().split('\n')
    
    # Filter the original questions list to only include those returned by the LLM
    return [q for q in questions if q['question'] in relevant_questions]

def summarize_answers(query: str, stackoverflow_data: List[Dict]) -> str:
    """
    Summarizes the most helpful and highly upvoted answers from relevant Stack Overflow questions 
    based on the user's query.
    
    Args:
        query (str): The user's coding query.
        stackoverflow_data (List[Dict]): List of Stack Overflow questions and their answers.
        
    Returns:
        str: A concise summary of the most relevant and insightful answers.
    """
    # First, filter the questions to the relevant subset using similarity_filter
    relevant_data = similarity_filter(query, stackoverflow_data)

    if not relevant_data:
        return "No relevant Stack Overflow questions found for the query."

    # Aggregate the context of relevant questions and answers
    context = ""
    for item in relevant_data:
        context += f"\n\nQuestion: {item['question']}\n"
        for ans in item['answers']:
            context += f"Upvotes: {ans['Upvotes']}\nAnswer: {ans['Body']}\n"

    # Prepare a prompt to the LLM to summarize the relevant answers
    prompt = f"""
You are a coding assistant. Summarize the most helpful and highly upvoted answers for the following user query:
"{query}"

Here are the relevant Stack Overflow answers:
{context}

Only include the most insightful and concise information. Mention if multiple solutions exist.
"""
    # Call the LLM to get the summary
    response = model.invoke([HumanMessage(content=prompt)])
    return response.content

# Create a StructuredTool instance for integration with LangChain workflows
StackOverflowSummarizer = StructuredTool.from_function(
    func=summarize_answers,
    name="StackOverflowSummarizer",
    description=(
        "Summarizes relevant and highly upvoted Stack Overflow answers based on a user's coding query. "
        "Only includes questions that are semantically similar to the user's query."
    ),
    args_schema=StackOverflowSummaryInput
)
