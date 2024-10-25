import os
import streamlit as st
from io import BytesIO
from tempfile import NamedTemporaryFile
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import re

# Function to remove code block markers from the answer
def remove_code_blocks(text):
    # Remove starting and ending code block markers
    code_block_pattern = r"^```(?:\w+)?\n(.*?)\n```$"
    match = re.match(code_block_pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
        return text

# Function to process PDF, run Q&A, and return results
def process_pdf(api_key, uploaded_file, questions_path, prompt_path, display_placeholder):
    # Set up OpenAI API key
    os.environ["OPENAI_API_KEY"] = api_key

    # Temporarily save the uploaded file to disk
    with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        temp_pdf.write(uploaded_file.read())  # Write the uploaded file to the temp file
        temp_pdf_path = temp_pdf.name

    # Load multiple PDF documents using PyPDFLoader
    file_paths = ["Resilient_Los_Angeles_Plan.pdf", "JacksonvilleFL.pdf"]
    docs = []
    for file_path in file_paths:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File does not exist: {file_path}")
    loader = PyPDFLoader(file_path)
    docs.extend(loader.load())

    # Split the document into smaller chunks for embedding
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=500)
    splits = text_splitter.split_documents(docs)

    # Create vector store and retriever
    vectorstore = FAISS.from_documents(
        documents=splits, embedding=OpenAIEmbeddings(model="text-embedding-3-large")
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 10})

    # Read the system prompt from a Markdown (.md) file
    if os.path.exists(prompt_path):
        with open(prompt_path, "r") as file:
            system_prompt = file.read()
    else:
        raise FileNotFoundError(f"The specified file was not found: {prompt_path}")

    # Ensure the system prompt includes {context} for document input
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
        ]
    )

    # Create the retrieval and question-answering chains
    llm = ChatOpenAI(model="gpt-4o")
    question_answer_chain = create_stuff_documents_chain(llm, prompt, document_variable_name="context")
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)

    # Load questions from a Markdown file
    if os.path.exists(questions_path):
        with open(questions_path, "r") as file:
            questions = [line.strip() for line in file.readlines() if line.strip()]
    else:
        raise FileNotFoundError(f"The specified file was not found: {questions_path}")

    # Generate question and answer pairs incrementally
    qa_results = []
    for question in questions:
        result = rag_chain.invoke({"input": question})
        answer = result["answer"]

        # Remove code block markers from the answer
        answer = remove_code_blocks(answer)

        qa_text = f"### Question: {question}\n**Answer:**\n{answer}\n"
        qa_results.append(qa_text)
        # Update the placeholder with each new Q&A pair
        display_placeholder.markdown("\n".join(qa_results), unsafe_allow_html=True)

    # Clean up the temporary file
    os.remove(temp_pdf_path)

    return qa_results

# Streamlit app layout
st.title("Climate Policy Summary Tool")

# Input OpenAI API key
api_key = st.text_input("Enter your OpenAI API key:", type="password")

# File upload section for PDF
uploaded_file = st.file_uploader("Upload a PDF document", type="pdf")

# Define static paths for prompt and questions
prompt_file_path = "summary_tool_system_prompt.md"
questions_file_path = "summary_tool_questions.md"

# When user clicks "Generate"
if st.button("Generate") and api_key and uploaded_file:
    # Create a placeholder to update with each Q&A
    display_placeholder = st.empty()

    with st.spinner("Processing..."):
        try:
            results = process_pdf(api_key, uploaded_file, questions_file_path, prompt_file_path, display_placeholder)
            
            # Allow the user to download the results as a Markdown file
            markdown_text = "\n".join(results)
            st.download_button(
                label="Download Results as Markdown",
                data=markdown_text,
                file_name="qa_results.md",
                mime="text/markdown"
            )
        except Exception as e:
            st.error(f"An error occurred: {e}")
