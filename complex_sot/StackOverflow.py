import re
from typing import List
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langchain.tools import StructuredTool
import requests
from bs4 import BeautifulSoup
from langchain_groq import ChatGroq

# Initialize the Groq model (LLaMA 3)
model = ChatGroq(model='llama3-8b-8192')


class StackOverFlowToolInput(BaseModel):
    """
    Schema for the input to the Stack Overflow scraping tool.

    Attributes:
        urls (List[str]): List of Stack Overflow question URLs.
    """
    urls: List[str] = Field(..., description="List of Stack Overflow question URLs.")


def extract_question_id(url):
    """
    Extracts the question ID from a Stack Overflow URL.

    Args:
        url (str): A Stack Overflow question URL.

    Returns:
        str | None: The question ID if found, else None.
    """
    match = re.search(r"/questions/(\d+)", url)
    if match:
        return match.group(1)
    return None


def beautify_html_body(body):
    """
    Converts HTML content into clean, readable text.

    Args:
        body (str): HTML content.

    Returns:
        str: Plain text content.
    """
    soup = BeautifulSoup(body, "html.parser")
    return soup.get_text()


def get_answers_for_question(question_id):
    """
    Fetches top answers for a given Stack Overflow question using the Stack Exchange API.

    Args:
        question_id (str): The Stack Overflow question ID.

    Returns:
        list[dict] | str: List of top answers with upvotes, body, and link. 
                          Returns a message string if no answers or an error occurs.
    """
    url = f"https://api.stackexchange.com/2.3/questions/{question_id}/answers"
    params = {
        'order': 'desc',
        'sort': 'votes',
        'site': 'stackoverflow',
        'filter': 'withbody'
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        answers = response.json().get('items', [])
        if answers:
            result = []
            for answer in answers:
                body = beautify_html_body(answer['body'])
                answer_info = {
                    'upvotes': answer['score'],
                    'body': body[:300] + "..." if len(body) > 300 else body,
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


def tool_fn(urls: List[str]):
    """
    Main function to retrieve questions and top answers from Stack Overflow given a list of URLs.

    Args:
        urls (List[str]): List of Stack Overflow question URLs.

    Returns:
        List[dict]: A list containing questions with their top answers.
    """
    results = []

    for url in urls:
        question_id = extract_question_id(url)
        if question_id is None:
            continue

        # Fetch question details
        question_url = f"https://api.stackexchange.com/2.3/questions/{question_id}"
        params = {
            'order': 'desc',
            'sort': 'activity',
            'site': 'stackoverflow',
            'filter': 'withbody'
        }
        response = requests.get(question_url, params=params)
        if response.status_code != 200:
            continue
        items = response.json().get('items', [])
        if not items:
            continue
        title = items[0]['title']

        # Fetch and format answers
        ans_list = get_answers_for_question(question_id)
        if isinstance(ans_list, str):
            formatted_answers = [ans_list]
        else:
            formatted_answers = []
            for ans in ans_list:
                formatted_answers.append({
                    'Upvotes': ans['upvotes'],
                    'Body': ans['body'],
                    'Link': ans['link']
                })

        results.append({
            'question': title,
            'answers': formatted_answers[:4]  # Limit to top 4 answers
        })
    return results


# ✅ Define the StructuredTool for LangChain with schema and description
Stack_overflow_tool = StructuredTool.from_function(
    func=tool_fn,
    name="stack_overflow_tool",
    description="""Given a list of Stack Overflow URLs, returns the top answers (based on upvotes) 
                   with their content and links. Useful for debugging and resolving programming issues.""",
    args_schema=StackOverFlowToolInput
)
