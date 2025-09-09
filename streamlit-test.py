import streamlit as st
import requests
from llama_index.llms.ollama import Ollama

from llama_index.core.tools import FunctionTool


llm: Ollama = Ollama(base_url="http://44.200.48.59:11434", model="llama3.2")
print(llm.complete("Tell me a joke"))

from llama_index.llms.openai import OpenAI
from llama_index.core.agent import FunctionAgent
from llama_index.core.agent import ReActAgent


llm2 = OpenAI(model="gpt-4o-mini")

API_URL = "https://api.aurora-dev.sinchlab.com/AuroraService/v1/"
USERNAME = "fb4b663c9ae241a58ac8239f910ca88c"
PASSWORD = "3a112f0cca8648378e4a2291f64a0b78"

# Set up Ollama with your base_url and model
#OLLAMA_URL = "http://44.200.48.59:11434"
OLLAMA_URL = "http://44.200.48.59:11434/api/tags"
#OLLAMA_URL = "http://api.aurora-dev.sinchlab.com/AuroraService/v1/orders"
#llm = Ollama(base_url=OLLAMA_URL, model="llama3.2")


def get_regions():
    url = API_URL+"regions"
    payload = {}
    headers = {
        'x-username': 'edmul1@on.sinch.com',
        'Authorization': 'Basic ZmI0YjY2M2M5YWUyNDFhNThhYzgyMzlmOTEwY2E4OGM6M2ExMTJmMGNjYTg2NDgzNzhlNGEyMjkxZjY0YTBiNzg=',
        'Cookie': 'JSESSIONID=DCC3B6C89D58E18F6EA692202C234C52'
    }

    response = requests.request("GET", url, headers=headers, data=payload, verify=False)
    if response.status_code == 200:
        #return response.json().get("regions", [])
        return response.json().get("regions", [])
    return response

def get_order_count(region_id):
    payload = {}
    url = API_URL+"/orders?regionId="+region_id
    headers = {
        'x-username': 'edmul1@on.sinch.com',
        'Authorization': 'Basic ZmI0YjY2M2M5YWUyNDFhNThhYzgyMzlmOTEwY2E4OGM6M2ExMTJmMGNjYTg2NDgzNzhlNGEyMjkxZjY0YTBiNzg=',
        'Cookie': 'JSESSIONID=DCC3B6C89D58E18F6EA692202C234C52'
    }
    response = requests.request("GET", url, headers=headers, data=payload, verify=False)
    if response.status_code == 200:
        return response.json().get("totalCount", 0)
    return 0

def api_response():
    url = API_URL+"orders"
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

agent = ReActAgent(
    tools=[post_search_tool],
    llm=llm2,
    verbose=True
)

def chatbot_response(message):
    return llm.complete(message)

st.title("Ollama Chatbot Web UI")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

user_input = st.text_input("You:", "")

search = st.text_input("Search for orders/regions:")
#st.write("Basic API Response:", api_response())
#st.write("Regions from API:", get_regions())

if st.button("Send"):
    if search:
        regions = get_regions()
        results = []
        for region in regions:
            region_id = region.get("id")
            region_name = region.get("name", region_id)
            if search.lower() in region_name.lower():
                count = get_order_count(region_id)
                results.append((region_name, count))
        if results:
            for name, count in results:
                st.write(f"Region: `{name}` — Orders: `{count}`")
        else:
            st.write("No matching regions found.")
    if user_input:
        st.session_state.chat_history.append(("You", user_input))
        bot_reply = chatbot_response(user_input)
        st.session_state.chat_history.append(("Bot", bot_reply))

for speaker, message in st.session_state.chat_history:
    st.write(f"**{speaker}:** {message}")



#Query the API to get all region IDs
#"https://api.aurora-dev.sinchlab.com/AuroraService/v1/regions"
#For each region ID, query the API to get all the orders in that region
#https://api.aurora-dev.sinchlab.com/AuroraService/v1/orders?regionId=APAC
#The above will have a 'totalCount' field which indicates how many orders are in that region