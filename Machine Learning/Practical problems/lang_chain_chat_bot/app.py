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
    

def get_conversational_chain(tools, ques):
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0.3, google_api_key=os.getenv("GEMINI_API_KEY"))
    
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a helpful assistant. Answer the question as detailed as possible from the provided context. If the answer is not in the context, just say, "answer is not available in the context".""",
            ),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )
    
    tool = [tools]
    agent = create_tool_calling_agent(llm, tool, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tool, verbose=True)
    
    response = agent_executor.invoke({"input": ques})
    
    used_tool = response.get("intermediate_steps", [])[0][0].tool if "intermediate_steps" in response else None
    print(f"Used tool: {used_tool}")
    
    return {
        "output": response["output"],
        "source": "PDF" if used_tool == "pdf_extractor" else "General"
    }

    
def user_input(user_question):
    faiss_exists = os.path.exists("faiss_db") and os.path.isfile("faiss_db/index.pkl")

    if faiss_exists:
        new_db = FAISS.load_local("faiss_db", embeddings, allow_dangerous_deserialization=True)
        retriever = new_db.as_retriever()
        retrieval_tool = create_retriever_tool(retriever, "pdf_extractor", "This tool is to give answer to queries from the PDF")
        
        result = get_conversational_chain(retrieval_tool, user_question)
        return result
    else:
        # fallback to general chat
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0.5, google_api_key=os.getenv("GEMINI_API_KEY"))
        response = llm.invoke(user_question)
        return {
            "output": response.content,
            "source": "General"
        }

    
    
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
                result = user_input(user_question)
                AI_msg = result["output"]
                source = result["source"]
                
                if source == "PDF":
                    st.write("📄 **From PDF**")
                elif source == "General":
                    st.write("🤖 **General Response**")
                elif source == "Error":
                    st.write("⚠️ " + AI_msg)
                else:
                    st.write("💬 Response:")

                st.write(AI_msg)



        st.session_state.chat_history.append(AIMessage(content=AI_msg))
        
    with st.sidebar:
        st.title("Options")
        if not os.path.exists("faiss_db") or not os.path.isfile("faiss_db/index.pkl"):
            st.info("You can chat normally or upload PDFs for document-based answers.")
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
    