import streamlit as st
from llama_index.llms.ollama import Ollama
import asyncio
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec
from llama_index.core.agent.workflow import FunctionAgent

# Page configuration
st.set_page_config(
    page_title="LlamaIndex Chatbot",
    page_icon="🦙",
    layout="centered"
)
#Intialize MCP Client
@st.cache_resource
def build_agent():
    llm = get_llm()
    async def _build():
        # Update this URL if your MCP server runs elsewhere
        tools = await mcp_tool_spec.to_tool_list_async()
        return FunctionAgent(
            name="MCP-Ollama-Agent",
            description="Uses Ollama LLM and MCP tools",
            tools=tools,
            llm=llm,
        )

    return asyncio.run(_build())

# Initialize the Ollama LLM model
@st.cache_resource
def get_llm():
    return Ollama(model="llama3.2", base_url="http://44.200.48.59:11434", request_timeout=120.0)

@st.cache_resource
def get_agent():
    llm = get_llm()
    def build_agent():
        async def _build():
            # Update this URL if your MCP server runs elsewhere
            mcp_client = BasicMCPClient("http://localhost:6969/sse")
            mcp_tool_spec = McpToolSpec(client=mcp_client)
            tools = await mcp_tool_spec.to_tool_list_async()
            return FunctionAgent(
                name="MCP-Ollama-Agent",
                description="Uses Ollama LLM and MCP tools",
                tools=tools,
                llm=llm,
            )
        return asyncio.run(_build())
    return build_agent

# Initialize chat history in session state if it doesn't exist
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! I'm a chatbot powered by Llama 3.2 and MCP tools. How can I help you today?"}
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

        # Use the MCP-enabled agent
        agent = get_agent()
        def run_agent(q: str) -> str:
            async def _run():
                result = await agent.run(q)
                return str(result)
            return asyncio.run(_run())

        response_text = run_agent(prompt)

        # Add assistant response to chat history
        message_placeholder.markdown(response_text)
        st.session_state.messages.append({"role": "assistant", "content": response_text})

# Add a sidebar with information
with st.sidebar:
    st.markdown("## About")
    st.markdown("This is a simple chatbot built with Streamlit and LlamaIndex.")
    st.markdown("It uses the Ollama model Llama 3.2 and MCP-discovered tools to generate and execute responses.")
    st.markdown("---")
    st.markdown("Made with ❤️ using Streamlit")