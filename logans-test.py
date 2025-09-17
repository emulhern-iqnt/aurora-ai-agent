import dotenv
import asyncio
import requests
import yaml
import sys
import httpx

from llama_index.llms.ollama import Ollama
from llama_index.tools.mcp import McpToolSpec, BasicMCPClient, McpToolSpec
from llama_index.core.agent.workflow import FunctionAgent, ToolCallResult, ToolCall
from llama_index.core.workflow import Context
from llama_index.tools.openapi import OpenAPIToolSpec

limit = 10000
sys.setrecursionlimit(limit)

dotenv.load_dotenv()

# Load LLM
# llm = OpenAI(model="gpt-4o")
llm = Ollama(
    model="gpt-oss:20b",
    # model="llama4:latest",
    request_timeout=60.0,
    # Manually set the context window to limit memory usage
    context_window=8000,
    temperature=0.3,
    # base_url='https://aigateway.inteliquent.com',
)

SYSTEM_PROMPT = """\
You are an AI assistant for Tool Calling.

Before you help a user, you need to work with tools to interact with Our Database
"""


async def get_agent(tools: McpToolSpec):
    tools = await tools.to_tool_list_async()
    agent = FunctionAgent(
        name="Agent",
        description="An agent that can work with Our Database software.",
        tools=tools,
        llm=llm,
        system_prompt=SYSTEM_PROMPT,
    )
    return agent


async def handle_user_message(
        message_content: str,
        agent: FunctionAgent,
        agent_context: Context,
        verbose: bool = False,
):
    handler = agent.run(message_content, ctx=agent_context)
    async for event in handler.stream_events():
        if verbose and type(event) == ToolCall:
            print(f"Calling tool {event.tool_name} with kwargs {event.tool_kwargs}")
        elif verbose and type(event) == ToolCallResult:
            print(f"Tool {event.tool_name} returned {event.tool_output}")

    response = await handler
    return str(response)


async def main():
    mcp_client = BasicMCPClient("http://localhost:8084/sse")
    tools = McpToolSpec(client=mcp_client)
    # open_api_spec = OpenAPIToolSpec(url='http://localhost:8083/openapi.yml')
    # f = requests.get('http://localhost:8083/openapi.yml').text
    # open_api_spec = yaml.safe_load(f)
    # print(open_api_spec)
    # tool_spec = OpenAPIToolSpec(spec=open_api_spec)
    # tools=tool_spec.to_tool_list()

    # get the agent
    agent = await get_agent(tools)

    # create the agent context
    agent_context = Context(agent)

    # Run the agent!
    while True:
        user_input = input("Enter your message: ")
        if user_input == "exit":
            break
        print("User: ", user_input)
        response = await handle_user_message(user_input, agent, agent_context, verbose=False)
        print("Agent: ", response)


# Run the main function
asyncio.run(main())




