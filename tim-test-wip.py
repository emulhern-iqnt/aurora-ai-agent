import streamlit as st
from llama_index.llms.ollama import Ollama

# Page configuration
st.set_page_config(
    page_title="LlamaIndex Chatbot",
    page_icon="🦙",
    layout="centered"
)

from llama_index.core.llms import ChatMessage, MessageRole

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


# Initialize the Ollama LLM model
@st.cache_resource
def get_llm():
    return Ollama(model="llama3.2", base_url="http://44.200.48.59:11434", request_timeout=120.0)


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

        # Get LLM response
        llm = get_llm()
        response = chat_with_string(llm, prompt)

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