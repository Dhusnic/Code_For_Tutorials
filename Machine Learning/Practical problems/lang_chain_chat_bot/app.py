import streamlit as st
import os
from dotenv import load_dotenv
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain.schema  import HumanMessage, AIMessage
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.embeddings.spacy_embeddings import SpacyEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.tools.retriever import create_retriever_tool
from langchain_anthropic import ChatAnthropic
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")  # or "cuda" if you have GPU

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2",  encode_kwargs={"normalize_embeddings": True})

env_path = Path(__file__).resolve().parent.parent / "settings" / ".env"

load_dotenv(dotenv_path=env_path)

os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"

def pdf_read(pdf_doc):
    text = ""
    for pdf in pdf_doc:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text



def get_chunks(text):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_text(text)
    return chunks


def vector_store(text_chunks):
    
    vector_store = FAISS.from_texts(text_chunks, embedding=embeddings)
    vector_store.save_local("faiss_db")
    

def get_conversational_chain(tools,ques):
    #os.environ["ANTHROPIC_API_KEY"]=os.getenv["ANTHROPIC_API_KEY"]
    #llm = ChatAnthropic(model="claude-3-sonnet-20240229", temperature=0, api_key=os.getenv("ANTHROPIC_API_KEY"),verbose=True)
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0.3, google_api_key=os.getenv("GEMINI_API_KEY"))
    prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a helpful assistant. Answer the question as detailed as possible from the provided context, make sure to provide all the details, if the answer is not in
    provided context just say, "answer is not available in the context", don't provide the wrong answer""",
        ),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    tool=[tools]
    agent = create_tool_calling_agent(llm, tool, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tool, verbose=True)
    response=agent_executor.invoke({"input": ques})
    print(response)
    return response['output']
    
def user_input(user_question):
    new_db = FAISS.load_local("faiss_db", embeddings,allow_dangerous_deserialization=True)
    retriever=new_db.as_retriever()
    retrieval_chain= create_retriever_tool(retriever,"pdf_extractor","This tool is to give answer to queries from the pdf")
    return get_conversational_chain(retrieval_chain,user_question)
    
    
def main():
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
                
    user_question = st.chat_input("Ask a Question from the PDF Files")

    if user_question:
        st.session_state.chat_history.append(HumanMessage(content=user_question))
        with st.chat_message("user"):
            st.write(user_question)
            
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # response = st.session_state.conversation.predict(input=user_question)
                # print(response)
                # message = response
                # st.write(message)
                AI_msg = user_input(user_question)
                st.write("Reply: ", AI_msg)


        st.session_state.chat_history.append(AIMessage(content=AI_msg))
        
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
        
        st.title("Menu:")
        pdf_doc = st.file_uploader("Upload your PDF Files and Click on the Submit & Process Button", accept_multiple_files=True)
        if st.button("Submit & Process"):
            with st.spinner("Processing..."):
                raw_text = pdf_read(pdf_doc)
                text_chunks = get_chunks(raw_text)
                vector_store(text_chunks)
                st.success("Done")
    
    
    
if __name__ == "__main__":
    main()
    