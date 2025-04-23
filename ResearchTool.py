import requests
from langchain.tools import StructuredTool
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AnyMessage, AIMessage, SystemMessage, ToolMessage
class ResearchToolInput(BaseModel):
    url: str = Field(..., description="The URL of the web page to summarize")
    lang: str = Field(..., description="The target language for the summary (like 'hi' for Hindi)")

from langchain_groq import ChatGroq
model=ChatGroq(model='llama3-8b-8192')
    

def text_fetcher(url: str) -> str:
    """
    Fetches text from the given URL.
    """
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        clean_text = soup.get_text()
        return clean_text

    else:
        raise Exception(f"Failed to fetch text: {response.status_code}")
        
def summarizer(text:str, model) -> str:
    prompt=f'''
        You are a summarization model. I will provide you with a text, and your task is to summarize the main points concisely. While summarizing, please ensure to:

        1. Focus only on the core information, such as key arguments, facts, and findings.
        2. Ignore any irrelevant content such as advertisements, navigation menus, and any promotional material.
        3. Skip over repetitive or unrelated content that does not contribute to the paper's or article's primary purpose.
        4. Provide a clear, coherent summary in your response.

        Here is the text you need to summarize:

        {text}
    '''.strip()
    response = model.invoke([HumanMessage(content=prompt)])
    return response.content

def translater(text:str, lang:str, model) -> str:
    prompt=f'''
        You are a translation model. I will provide you with a text, and your task is to translate it into {lang}. While translating, please ensure to:

        1. Maintain the original meaning and context of the text.
        2. Use appropriate terminology and phrasing for the target language.
        3. Ensure grammatical correctness in the translated text.
        4. If the text is already in the target language, simply return it as is.
        5. Please strictly avoid adding any additional commentary or explanations like "Here is the translation" or "This is what it means".
        6. Do not include any extra information or context that is not part of the original text.

        Here is the text you need to translate:

        {text}
    '''.strip()
    response = model.invoke([HumanMessage(content=prompt)])
    return response.content

def tool_fn(url,lang) -> str:
    """
    Main function to fetch, summarize, and translate text from a given URL.
    """
    
    text = text_fetcher(url)
    summary = summarizer(text, model)
    translated=translater(summary,lang, model)
    
    return [{'Answer': translated}]


tool = StructuredTool.from_function(
    func=tool_fn,
    name="Research Summarizer",
    description="Fetches text from a URL, summarizes it, and translates it into the specified language.",
    args_schema=ResearchToolInput
)
    
