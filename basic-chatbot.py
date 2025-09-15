import streamlit as st
import requests

from llama_index.llms.ollama import Ollama
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import ReActAgent
import re
import asyncio
from llama_index.core.workflow import Context

llm: Ollama = Ollama(base_url="http://44.200.48.59:11434", model="llama3.2")
llm2 = OpenAI(model="gpt-4o-mini")

#print(llm.complete("Tell me a joke"))

API_URL = "https://api.aurora-dev.sinchlab.com/AuroraService/v1/"
USERNAME = "fb4b663c9ae241a58ac8239f910ca88c"
PASSWORD = "3a112f0cca8648378e4a2291f64a0b78"
OLLAMA_URL = "http://44.200.48.59:11434/api/tags"

# def get_regions():
#     url = API_URL+"regions"
#     payload = {}
#     headers = {
#         'x-username': 'edmul1@on.sinch.com',
#         'Authorization': 'Basic ZmI0YjY2M2M5YWUyNDFhNThhYzgyMzlmOTEwY2E4OGM6M2ExMTJmMGNjYTg2NDgzNzhlNGEyMjkxZjY0YTBiNzg=',
#         'Cookie': 'JSESSIONID=DCC3B6C89D58E18F6EA692202C234C52'
#     }
#
#     response = requests.request("GET", url, headers=headers, data=payload, verify=False)
#     if response.status_code == 200:
#         #return response.json().get("regions", [])
#         return response.json().get("regions", [])
#     return response
#
# def get_order_count_by_region(region_id):
#     payload = {}
#     url = API_URL+"/orders?regionId="+region_id
#     headers = {
#         'x-username': 'edmul1@on.sinch.com',
#         'Authorization': 'Basic ZmI0YjY2M2M5YWUyNDFhNThhYzgyMzlmOTEwY2E4OGM6M2ExMTJmMGNjYTg2NDgzNzhlNGEyMjkxZjY0YTBiNzg=',
#         'Cookie': 'JSESSIONID=DCC3B6C89D58E18F6EA692202C234C52'
#     }
#     response = requests.request("GET", url, headers=headers, data=payload, verify=False)
#     if response.status_code == 200:
#         return response.json().get("totalCount", 0)
#     return 0

def api_response(suffix, params=None):
    url = API_URL + suffix
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    payload = {}
    headers = {
        'x-username': 'edmul1@on.sinch.com',
        'Authorization': 'Basic ZmI0YjY2M2M5YWUyNDFhNThhYzgyMzlmOTEwY2E4OGM6M2ExMTJmMGNjYTg2NDgzNzhlNGEyMjkxZjY0YTBiNzg=',
        'Cookie': 'JSESSIONID=DCC3B6C89D58E18F6EA692202C234C52'
    }

    response = requests.request("GET", url, headers=headers, data=payload, verify=False)

    if response.status_code == 200:
        data = response.json()
        return data
    else:
        return "Error contacting API."

# Wrap our function as a Tool
post_search_tool = FunctionTool.from_defaults(
    fn=api_response,
    name="PostSearchTool",
    description="Get all orders from the API",
)

async def get_agent():
    agent = ReActAgent(
    tools=[post_search_tool],
    llm=llm,
    verbose=True
    )
    return agent

async def handle_user_message(
    message_content: str,
    agent: ReActAgent,
    agent_context: Context,
    verbose: bool = False,
):
    handler = agent.run(message_content, ctx=agent_context)
    # async for event in handler.stream_events():
    #     if verbose and type(event) == ToolCall:
    #         print(f"Calling tool {event.tool_name} with kwargs {event.tool_kwargs}")
    #     elif verbose and type(event) == ToolCallResult:
    #         print(f"Tool {event.tool_name} returned {event.tool_output}")

    response = await handler
    return str(response)



async def main():

    # get the agent
    agent = await get_agent()

    # create the agent context
    agent_context = Context(agent)

    while True:
        user_input = input("Enter your message: ")
        if user_input == "exit":
            break
        print("User: ", user_input)
        response = await handle_user_message(user_input, agent, agent_context, verbose=False)
        print("Agent: ", response)

asyncio.run(main())

#Query the API to get all region IDs
#"https://api.aurora-dev.sinchlab.com/AuroraService/v1/regions"
#For each region ID, query the API to get all the orders in that region
#https://api.aurora-dev.sinchlab.com/AuroraService/v1/orders?regionId=APAC
#The above will have a 'totalCount' field which indicates how many orders are in that region
#start with the basic url.
# if the user mentions regions, call the main api with /regions endpoints
#https://api.aurora-dev.sinchlab.com/AuroraService/v1/orders?assignedUsername=virsha@on.sinch.com
#https://api.aurora-dev.sinchlab.com/AuroraService/v1/workgroups
#If the search button is pressed, check the user input for keywords
#if the user mentions workgroups, call the /workgroups endpoint.
#   Same for the /orders and /regions endpoints
#For each workgroup, call the /orders endpoint with the workgroup ID
#if the user mentions orders, call the /orders endpoint
#if the user mentions regions, call the /regions endpoint
#if the user mentions customers, call the /customers endpoint

