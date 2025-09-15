import streamlit as st
import requests

from llama_index.llms.ollama import Ollama
from llama_index.core.tools import FunctionTool
#from llama_index.llms.openai import OpenAI
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core import Settings

import re
import asyncio
from llama_index.core.workflow import Context

llm: Ollama = Ollama(base_url="http://44.200.48.59:11434", model="llama3.2")
Settings.llm = llm
Settings.embed_model = None

#llm2 = OpenAI(model="gpt-4o-mini")
# llm = Ollama(
#     model="gpt-oss:20b",
#     # model="llama4:latest",
#     request_timeout=60.0,
#     # Manually set the context window to limit memory usage
#     context_window=8000,
#     temperature=0.3,
#     # base_url='https://aigateway.inteliquent.com',
# )

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
# Create a tool from your API call function
my_api_tool = QueryEngineTool(
    query_engine=RetrieverQueryEngine.from_args(retriever=lambda q: [api_response(q)]), # Simplified for demonstration
    metadata=ToolMetadata(
        name="my_api",
        description="This tool can be used to query data from a custom API by providing a search query.",
    ),
)
agent = ReActAgent(tools=[my_api_tool], llm=llm, verbose=True)

def internal_chatbot_response(message):
    return llm.complete(message)

st.title("Ollama Chatbot Web UI")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

user_input = st.text_input("Chatbot Message:", "")
if st.button("Send to Chatbot"):
    if user_input:
        st.session_state.chat_history.append(("You", user_input))
        bot_reply = internal_chatbot_response(user_input)
        st.session_state.chat_history.append(("Bot", bot_reply))

search = st.text_input("Search Aurora Orders:")
if st.button("Search"):
    if search:
        results = []
        response = agent.run(search)
        results.append(("Aurora", response))
        # if re.search(r"customer", search, re.IGNORECASE):
        #     customers = api_response("customers")
        #     for customer in customers.get("customers", []):
        #         customer_id = customer.get("id")
        #         orders = api_response("orders", params={"customerId": customer_id})
        #         count = orders.get("pageInfo", {}).get("totalCount", 0)
        #         results.append((f"Customer: {customer_id}", count))
        # elif re.search(r"region", search, re.IGNORECASE):
        #     regions = api_response("regions")
        #     for region in regions.get("regions", []):
        #         region_id = region.get("id")
        #         orders = api_response("orders", params={"regionId": region_id})
        #         count = orders.get("pageInfo", {}).get("totalCount", 0)
        #         results.append((f"Region: {region_id}", count))
        # elif re.search(r"workgroup", search, re.IGNORECASE):
        #     workgroups = api_response("workgroups")
        #     for wg in workgroups.get("workgroups", []):
        #         wg_id = wg.get("id")
        #         orders = api_response("orders", params={"workgroupId": wg_id})
        #         count = orders.get("pageInfo", {}).get("totalCount", 0)
        #         results.append((f"Workgroup: {wg_id}", count))
        if results:
            for name, count in results:
                st.write(f"{name} — Orders: `{count}`")
        else:
            st.write("No matching aggregator found.")

for speaker, message in st.session_state.chat_history:
    st.write(f"**{speaker}:** {message}")



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

