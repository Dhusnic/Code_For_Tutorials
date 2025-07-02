import streamlit as st
import os
from dotenv import load_dotenv
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain.schema  import HumanMessage, AIMessage
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI

        
env_path = Path(__file__).resolve().parent.parent / "settings" / ".env"

load_dotenv(dotenv_path=env_path)

st.set_page_config(page_title="LangChain Chatbot", page_icon=":robot_face:", layout="centered")
st.title("Dhusnic Infant DM Chatbot")
st.subheader("Welcome to the Dhusnic Infant DM Chatbot")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
    
if "chat_model" not in st.session_state:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",  # or gemini-pro-vision for image support
        temperature=0.7,
        google_api_key=os.getenv("GEMINI_API_KEY")
    )
    
    
    memory = ConversationBufferMemory(return_messages=True)
    
    
    st.session_state.conversation = ConversationChain(
        llm=llm,
        memory = memory,
        verbose=True
    )
    
for message in st.session_state.chat_history:
    if isinstance(message, HumanMessage):
        with st.chat_message("user"):
            st.write(message.content)
    elif isinstance(message, AIMessage):
        with st.chat_message("assistant"):
            st.write(message.content)
            
user_input = st.chat_input("Enter your message here")
if user_input:
    st.session_state.chat_history.append(HumanMessage(content=user_input))
    
    with st.chat_message("user"):
        st.write(user_input)
        
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = st.session_state.conversation(user_input)
            print(response.get("response","no response is available"))
            message = response.get("response","no response is available")
            st.write(message)
            st.session_state.chat_history.append(AIMessage(content=message))

    st.session_state.chat_history.append(AIMessage(content=message))
    
with st.sidebar:
    st.title("Options")
    
    if st.button("Clear Chat"):
        st.session_state.chat_history = []
    
        memory = ConversationBufferMemory(return_messages=True)
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",  # or gemini-pro-vision for image support
            temperature=0.7,
            google_api_key=os.getenv("GEMINI_API_KEY")
        )
        
        st.rerun()
    st.subheader("About")
    
    st.markdown(
        """
        This is a Dhusnic Infant DM Chatbot built using LangChain, Google Gemini, and Streamlit.
        - **LangChain**: A framework for developing applications powered by language models.
        - **Google Gemini**: A large language model developed by Google.
        - **Streamlit**: A Python library for creating web applications.
        
        """)
    
    
    
    
    