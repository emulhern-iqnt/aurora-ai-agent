import streamlit as st
import requests

from llama_index.llms.ollama import Ollama
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import ReActAgent
import re

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

def internal_chatbot_response(message):
    return llm.complete(message)

# Wrap our function as a Tool
post_search_tool = FunctionTool.from_defaults(
    fn=api_response,
    name="PostSearchTool",
    description="Get all orders from the API",
)

agent = ReActAgent(
    tools=[post_search_tool],
    llm=llm2,
    verbose=True
)

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
        if re.search(r"customer", search, re.IGNORECASE):
            customers = api_response("customers")
            for customer in customers.get("customers", []):
                customer_id = customer.get("id")
                orders = api_response("orders", params={"customerId": customer_id})
                count = orders.get("pageInfo", {}).get("totalCount", 0)
                results.append((f"Customer: {customer_id}", count))
        elif re.search(r"region", search, re.IGNORECASE):
            regions = api_response("regions")
            for region in regions.get("regions", []):
                region_id = region.get("id")
                orders = api_response("orders", params={"regionId": region_id})
                count = orders.get("pageInfo", {}).get("totalCount", 0)
                results.append((f"Region: {region_id}", count))
        elif re.search(r"workgroup", search, re.IGNORECASE):
            workgroups = api_response("workgroups")
            for wg in workgroups.get("workgroups", []):
                wg_id = wg.get("id")
                orders = api_response("orders", params={"workgroupId": wg_id})
                count = orders.get("pageInfo", {}).get("totalCount", 0)
                results.append((f"Workgroup: {wg_id}", count))
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

