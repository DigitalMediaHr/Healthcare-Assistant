import streamlit as st
import os
from dotenv import load_dotenv
from docling.document_converter import DocumentConverter
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.prompts import PromptTemplate
import tempfile
load_dotenv()

def get_pdf_text(pdf_docs):
    text = ""
    converter = DocumentConverter()
    for pdf in pdf_docs:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(pdf.read())
            tmp_file_path = tmp_file.name
        try:
            result = converter.convert(tmp_file_path)
            text += result.document.export_to_markdown()
        finally:
            os.remove(tmp_file_path)
    return text


def get_text_chunks(text):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,  
        chunk_overlap=200,  
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    return text_splitter.split_text(text)

def get_vectorstore(text_chunks):
    embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"), model="text-embedding-3-large")
    return FAISS.from_texts(texts=text_chunks, embedding=embeddings)

def get_conversation_chain(vectorstore):
    llm = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o-mini")
    memory = ConversationBufferMemory(
        memory_key='chat_history', return_messages=True
    )

    custom_prompt = PromptTemplate(
    template = ("""You have access to the following context: {context}.  
        Use this information to answer the question: '{question}'.  
        Maintain the same style, tone, and explanation style as in the context.  
        Stick strictly to the details provided—do not add anything extra. 
        If the context does not contain the answer, simply respond with: "I'm sorry, I can't help you with that.
        You should respond like human and not like a robot."""
    )
    )
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 5} 
    )

    return ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        combine_docs_chain_kwargs={"prompt": custom_prompt}
    )

def handle_user_input(user_question):
    st.session_state.messages.append({"role": "user", "content": user_question})
    with st.chat_message("user"):
        st.markdown(user_question)
    with st.chat_message("assistant"):
        with st.spinner(""):
            response = st.session_state.conversation({'question': user_question})
            bot_response = response['chat_history'][-1].content
            st.session_state.messages.append({"role": "assistant", "content": bot_response})
            st.markdown(bot_response)

def main():
    st.set_page_config(page_title="Assistant", layout="wide")
    st.title("Healthcare Assistant")
    if "messages" not in st.session_state:
        st.session_state.messages = []
    with st.sidebar:
        st.subheader("Upload Your PDFs")
        pdf_docs = st.file_uploader("Upload PDFs here", accept_multiple_files=True)
        if st.button("Process PDFs") and pdf_docs:
            with st.spinner("Processing documents..."):
                raw_text = get_pdf_text(pdf_docs)
                text_chunks = get_text_chunks(raw_text)
                vectorstore = get_vectorstore(text_chunks)
                st.session_state.vectorstore = vectorstore
                st.session_state.conversation = get_conversation_chain(vectorstore)
                st.session_state.messages = []  
                st.success("Processing complete! You can now ask questions.")
    if "conversation" not in st.session_state:
        st.warning("Please upload and process PDF documents first.")
        return

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask a question:"):
        if st.session_state.get('last_question') != prompt:
            handle_user_input(prompt)
            st.session_state['last_question'] = prompt
            st.rerun()

if __name__ == '__main__':
    main()
