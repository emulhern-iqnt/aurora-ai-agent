#TODO:
#If the chatbot answers a question and I respond 'yes', it currently doesn't respond properly
# --forgets the history

import streamlit as st
from llama_index.core.agent import ReActAgent
from llama_index.llms.ollama import Ollama
import asyncio
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec
from llama_index.core.agent.workflow import FunctionAgent
from threading import Thread  # added

from llama_index.llms.litellm import LiteLLM

# Page configuration
st.set_page_config(
    page_title="LlamaIndex Chatbot",
    page_icon="🦙",
    layout="centered"
)

from llama_index.core.llms import ChatMessage, MessageRole

SYSTEM_PROMPT = (
    "You are an AI assistant for Tool Calling."

    "Before you help a user, you need to work with tools"
    
    "Do not construct any URLs yourself in the model; always use the tool and return ONLY the tool's output as the final answer."
    "In general, prefer using available tools whenever they match the user's intent, and treat tool outputs as authoritative."
    "When a tool is invoked, you MUST base your final answer ONLY on the tool's returned output. "
    "Do NOT perform your own arithmetic or re-calculate results. "
)

def chat_with_string(llm, prompt_or_messages):
    """
    Wrapper to allow passing either a plain string or a list of ChatMessages.
    """
    if isinstance(prompt_or_messages, str):
        messages = [ChatMessage(role=MessageRole.USER, content=prompt_or_messages)]
    else:
        # assume it's already a list of ChatMessages
        messages = prompt_or_messages

    return llm.chat(messages=messages)

# Create a single background asyncio loop for the session and a helper to run coroutines on it
@st.cache_resource
def get_async_runner():
    loop = asyncio.new_event_loop()
    thread = Thread(target=loop.run_forever, daemon=True)
    thread.start()

    def run(coro):
        # Run a coroutine on the persistent loop and wait for its result
        return asyncio.run_coroutine_threadsafe(coro, loop).result()

    return loop, thread, run

#Initialize the MCP client
@st.cache_resource
def get_agent():
    """
    Build an MCP-enabled agent that can call tools exposed by your MCP server.
    """
    #agent_llm = get_llm()
    agent_llm = get_llm_2()
    _loop, _thread, run_async = get_async_runner()

    async def _build():
        # Adjust URL if your MCP server runs elsewhere
        mcp_client = BasicMCPClient("http://127.0.0.1:6969/sse")
        mcp_tool_spec = McpToolSpec(client=mcp_client)
        tools = await mcp_tool_spec.to_tool_list_async()
        return ReActAgent(
            name="MCP-Ollama-Agent",
            description="Uses Ollama LLM and MCP tools",
            tools=tools,
            llm=agent_llm,
            system_prompt=SYSTEM_PROMPT,  # ensure tool output is authoritative
        )

    # Build the agent once on the persistent loop (avoid asyncio.run here)
    return run_async(_build())

# Initialize the Ollama LLM model
@st.cache_resource
def get_llm():
    return Ollama(
        model="llama3.2",
        base_url="http://44.200.48.59:11434",
        request_timeout=120.0,
        temperature=0.0,  # reduce creative deviations to avoid self-doing math
    )
# Need to run:
# socat TCP-LISTEN:8000,fork,reuseaddr OPENSSL:aigateway.inteliquent.com:443,verify=0
# In order to get this working
@st.cache_resource
def get_llm_2():
    llm: LiteLLM = LiteLLM(
        api_base="http://localhost:8000",
        api_key="sk-B-KCtMPQ6mlr9yKA-O4BPw",
        model="openai/llama3.3:latest"
    )
    return llm

# Initialize chat history in session state if it doesn't exist
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! I'm a chatbot powered by Llama 3.2. How can I help you today?"}
    ]

# Display chat title
st.title("🦙 LlamaIndex Chatbot")
st.markdown("Chat with Llama 3.2 using this simple interface!")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle user input
if prompt := st.chat_input("Ask something..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display assistant response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()

        # Use MCP-enabled agent to produce the response (tools available from your MCP server)
        agent = get_agent()
        _loop, _thread, run_async = get_async_runner()

        def run_agent(q: str) -> str:
            async def _run():
                result = await agent.run(q)
                return str(result)
            # Run on the persistent loop instead of calling asyncio.run
            return run_async(_run())

        response = run_agent(prompt)

        # Add assistant response to chat history
        message_placeholder.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

# Add a sidebar with information
with st.sidebar:
    st.markdown("## About")
    st.markdown("This is a simple chatbot built with Streamlit and LlamaIndex.")
    st.markdown("It uses the Ollama model Llama 3.2 to generate responses.")
    st.markdown("---")
    st.markdown("Made with ❤️ using Streamlit")