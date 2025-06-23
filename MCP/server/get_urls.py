from typing import List
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

# Initialize the Tavily search tool with a maximum of 10 results
search_tool = TavilySearchResults(max_results=10)

class UrlsInput(BaseModel):
    """
    Schema for the input to the get_urls function.
    
    Attributes:
        query (str): The complete user query.
    """
    query: str = Field(..., description="The complete user query.")

def get_urls(query: str) -> List[str] | str:
    """
    Takes a query string and returns a list of relevant Stack Overflow URLs
    using the TavilySearchResults tool.

    Args:
        query (str): A coding-related user query.

    Returns:
        List[str]: A list of Stack Overflow URLs relevant to the query.
    """
    # Perform a web search prefixed with "stackoverflow.com" to bias results
    results = search_tool.run("stackoverflow.com " + query)

    # Filter results to include only valid Stack Overflow question URLs
    urls = [result['url'] for result in results if "https://stackoverflow.com/questions/" in result['url']]
    print(urls)
    return urls

# Wrap the get_urls function as a LangChain StructuredTool
get_url_tool = StructuredTool.from_function(
    func=get_urls,
    name="get_url_tool",
    description=(
        "Given any coding-related user query, it finds the most relevant URLs from Stack Overflow. "
        "It returns a list of Stack Overflow links relevant to the query."
    ),
    args_schema=UrlsInput
)
