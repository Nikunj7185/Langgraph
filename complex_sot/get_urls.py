from typing import List
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

search_tool = TavilySearchResults(max_results=10)

class UrlsInput(BaseModel):
    query: str = Field(..., description="The complete user query.")

def get_urls(query: str) -> List[str] | str:
    """
    Takes a query string and returns a list of relevant Stack Overflow URLs
    using the TavilySearchResults tool.
    """
    results = search_tool.run("stackoverflow.com " + query)
    urls = [result['url'] for result in results if "stackoverflow.com" in result['url']]
    return urls

get_url_tool = StructuredTool.from_function(
    func=get_urls,
    name="get_url_tool",
    description="""Given any coding-related user query, it finds the most relevant URLs from Stack Overflow.
                   It returns a list of Stack Overflow links relevant to the query.""",
    args_schema=UrlsInput
)
