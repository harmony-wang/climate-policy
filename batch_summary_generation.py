import os
from tempfile import NamedTemporaryFile
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

def process_pdf(api_key, pdf_path, questions_path, prompt_path):
    os.environ["OPENAI_API_KEY"] = api_key

    with open(pdf_path, "rb") as file:
        with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_pdf.write(file.read())
            temp_pdf_path = temp_pdf.name

    loader = PyPDFLoader(temp_pdf_path)
    docs = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=500)
    splits = text_splitter.split_documents(docs)

    vectorstore = FAISS.from_documents(
        documents=splits, embedding=OpenAIEmbeddings(model="text-embedding-3-large")
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 10})

    if os.path.exists(prompt_path):
        with open(prompt_path, "r") as file:
            system_prompt = file.read()
    else:
        raise FileNotFoundError(f"The specified file was not found: {prompt_path}")

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
        ]
    )

    llm = ChatOpenAI(model="gpt-4o")
    question_answer_chain = create_stuff_documents_chain(llm, prompt, document_variable_name="context")
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)

    if os.path.exists(questions_path):
        with open(questions_path, "r") as file:
            questions = [line.strip() for line in file.readlines() if line.strip()]
    else:
        raise FileNotFoundError(f"The specified file was not found: {questions_path}")

    qa_results = []
    for question in questions:
        result = rag_chain.invoke({"input": question})
        answer = result["answer"]

        qa_text = f"### Question: {question}\n**Answer:**\n{answer}\n"
        qa_results.append(qa_text)

    os.remove(temp_pdf_path)

    return qa_results

def main():
    # Get user input for directory path and API key
    directory_path = input("Enter the path to the folder containing the PDF plans: ").strip()
    api_key = input("Enter your OpenAI API key: ").strip()

    # Paths for prompt and questions files
    prompt_file_path = "summary_tool_system_prompt.md"
    questions_file_path = "summary_tool_questions.md"

    # Create output directory if it doesn't exist
    output_directory = "CAPS_Summaries"
    os.makedirs(output_directory, exist_ok=True)

    # Process each PDF in the directory
    for filename in os.listdir(directory_path):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(directory_path, filename)
            print(f"Processing {filename}...")

            try:
                results = process_pdf(api_key, pdf_path, questions_file_path, prompt_file_path)
                markdown_text = "\n".join(results)

                # Save the results to a Markdown file
                base_name = os.path.splitext(filename)[0]
                output_file_path = os.path.join(output_directory, f"{base_name}_Summary.md")
                with open(output_file_path, "w") as output_file:
                    output_file.write(markdown_text)

                print(f"Summary for {filename} saved to {output_file_path}")
            except Exception as e:
                print(f"An error occurred while processing {filename}: {e}")

if __name__ == "__main__":
    main()