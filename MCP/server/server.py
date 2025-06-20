import json
from mcp.server.fastmcp import FastMCP
from get_urls import get_url_tool
from StackOverflow import Stack_overflow_tool
from summarizer import StackOverflowSummarizer 
import logging  # Add logging
import traceback  # For error details

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVER_HOST = "0.0.0.0"  # Changed to allow external access
SERVER_PORT = 8000

mcp = FastMCP(
    name="trial_server",
    host=SERVER_HOST,
    port=SERVER_PORT,
)

# Add robust error handling to all tools
@mcp.tool()
def get_urls(query: str) -> dict:
    try:
        logger.info(f"get_urls called with query: {query}")
        result = get_url_tool(query)
        logger.info(f"Returning {len(result)} URLs")
        return {"urls": result}
    except Exception as e:
        logger.error(f"get_urls failed: {str(e)}\n{traceback.format_exc()}")
        return {"error": str(e)}

@mcp.tool()
def stack_overflow(urls: list) -> dict:
    try:
        logger.info(f"stack_overflow called with {len(urls)} URLs")
        result = Stack_overflow_tool(urls)
        return result  # Assuming this already returns a dict
    except Exception as e:
        logger.error(f"stack_overflow failed: {str(e)}\n{traceback.format_exc()}")
        return {"error": str(e)}

@mcp.tool()
def summarize_stack_overflow(answers: dict) -> dict:
    try:
        logger.info("summarize_stack_overflow called")
        result = StackOverflowSummarizer(answers)
        return {"summary": result}
    except Exception as e:
        logger.error(f"summarize_stack_overflow failed: {str(e)}\n{traceback.format_exc()}")
        return {"error": str(e)}

if __name__ == "__main__":
    print(f"Starting MCP HTTP server on http://{SERVER_HOST}:{SERVER_PORT}")
    print(f"Access docs at: http://localhost:{SERVER_PORT}/docs")
    mcp.run(transport="streamable-http")