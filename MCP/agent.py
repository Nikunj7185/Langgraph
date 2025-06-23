from fastmcp import Client
import asyncio

# The Client automatically uses StreamableHttpTransport for HTTP URLs
client = Client("http://localhost:8000/mcp")

async def main():
    async with client:
        tools = await client.list_tools()
        print(f"Available tools: {tools}   {type(tools[0])}")
        result=await client.call_tool(tools[0].name,{'query':"how to reverse a string in python?"})
        print(f"Using tool:{result}  {type(result)}")

asyncio.run(main())