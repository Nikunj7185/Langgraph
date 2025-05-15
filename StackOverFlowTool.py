from langchain_community.tools.tavily_search import TavilySearchResults
import re
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langchain.tools import StructuredTool
import requests
from bs4 import BeautifulSoup

from langchain_groq import ChatGroq
model=ChatGroq(model='llama3-8b-8192')

class StackOverFlowToolInput(BaseModel):
    query: str = Field(..., description="The complete user query.")

tavily_tool=TavilySearchResults(max_results=10)


# Function to beautify the HTML body
def beautify_html_body(body):
    soup = BeautifulSoup(body, "html.parser")
    return soup.get_text()

# Function to fetch answers for a question and sort them by upvotes
def get_answers_for_question(question_id):
    url = f"https://api.stackexchange.com/2.3/questions/{question_id}/answers"
    params = {
        'order': 'desc',
        'sort': 'activity',
        'site': 'stackoverflow',
        'filter': 'withbody'
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        answers = response.json().get('items', [])
        if answers:
            accepted_answer_id = response.json().get('accepted_answer_id', None)
            # Beautify body and prepare answers list
            result = []
            for answer in answers:
                is_accepted = "✅ Accepted" if answer['answer_id'] == accepted_answer_id else ""
                body = beautify_html_body(answer['body'])
                answer_info = {
                    'is_accepted': is_accepted,
                    'body': body[:300] + "..." if len(body) > 300 else body,  # Limiting body preview to 300 characters
                    'upvotes': answer['score'],
                    'link': f"https://stackoverflow.com/a/{answer['answer_id']}"
                }
                result.append(answer_info)
            # Sort answers by upvotes in descending order
            result.sort(key=lambda x: x['upvotes'], reverse=True)
            return result
        else:
            return "No answers found."
    else:
        return f"Error: {response.status_code}"

def extract_question_id(url):
    # Use regex to find the numeric ID in the URL
    match = re.search(r"/questions/(\d+)", url)
    if match:
        return match.group(1)
    return None

def answers(query)-> dict:
    """
    This function takes a query string, searches for relevant Stack Overflow questions,
    and retrieves the top two answers for each question.
    
    Returns a dictionary where the keys are question IDs and the values are dictionaries containing the question
    and its top answers (max 5) arranged based on the number of upvotes.
    """
    urls=[]
    qs=[]
    response=tavily_tool.invoke(f'stack overflow {query}')
    for result in response:
        if "https://stackoverflow.com" not in result['url']:
            continue
        urls.append(result['url'])
        qs.append(result['title'])
    if not urls:
        return None
    if len(urls) > 2:
        urls = urls[:2]
    q_ids=[]
    for url in urls:
        q_id=extract_question_id(url)
        if q_id is not None:
            q_ids.append(q_id)
    id_qestion={x:y for x,y in zip(q_ids,qs)}
    question_answers={}
    if id_qestion is None:
        return None
    for id,question in id_qestion.items():
        answers = get_answers_for_question(id)
        if len(answers) > 5 and isinstance(answers, list):
            answers = answers[:5]
        temp=[{"answer":answer['body'],
                "upvotes":answer['upvotes'],
                } for answer in answers]
        question_answers[question] = temp
    return question_answers

def tool_fn(query: str) -> dict:
    """
    Main function to fetch answers for a given query.
    """
    print(f"Query: {query}")
    answer = answers(query)
    if answer is None:
        return {"Answer":"NOT FOUND ON STACKOVERFLOW"}
    prompt=f"""
        You are a helpful Stack Overflow assistant. You are given:

        1. A user query. query: {query}
        2. A Stackoverflow answers dictionary  where:
        - Each key is a Stack Overflow question.
        - Each value is a list of answers (dictionaries) with the fields:
            - 'answer': the answer text
            - 'upvotes': the number of upvotes it received
            
        dictionary: {answer}

        Your task is to:

        1. Filter and select only the questions that are semantically similar to the user query (based on question titles).
        2. If none of the questions are relevant to the user query, respond with:
        "NOT FOUND ON STACKOVERFLOW"
        3. If relevant questions are found, answer the user query using only the information from the associated answers.
        4. If there are multiple answers, prioritize those with higher upvotes. In case of contradictory answers, prefer the one with more upvotes.
        5. Do not use any external knowledge beyond what is provided in the answers.""".strip()
    response = model.invoke([HumanMessage(content=prompt)])
    return {"Answer":response.content}

Stack_overflow_tool = StructuredTool.from_function(
    func=tool_fn,
    name="StackOverflow Tool",
    description="""Given any coding-related user query, it finds the most relevant answers from Stack Overflow, 
                   focusing on upvoted responses. The tool can handle debugging errors, code issues, and any coding-related 
                   questions that require assistance. It should be used to answer all coding-related inquiries.""",
    args_schema=StackOverFlowToolInput
)

    
        
if __name__ == "__main__":
    query = "How to reverse a list in Python?"
    result = tool_fn(query)
    print(result)
    
        
        
        
        
        
        
        
    
    

