import os
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

# Current available Groq models (as of Sept 2025)
AVAILABLE_MODELS = {
    "llama-3.3-70b-versatile": "Meta Llama 3.3 70B (Production)",
    "llama-3.1-8b-instant": "Meta Llama 3.1 8B (Production)", 
    "gemma2-9b-it": "Google Gemma 2 9B (Production)",
    "deepseek-r1-distill-llama-70b": "DeepSeek R1 Distill 70B (Preview)",
    "qwen/qwen3-32b": "Alibaba Qwen 3 32B (Preview)",
    "moonshotai/kimi-k2-instruct": "Moonshot AI Kimi K2 (Preview)"
}

def get_pdf_text(pdf_paths):
    """Extract text from multiple PDF files"""
    text = ""
    for pdf_path in pdf_paths:
        try:
            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
            pdf_reader = PdfReader(pdf_path)
            for page in pdf_reader.pages:
                extracted_text = page.extract_text()
                if extracted_text:  # Only add non-empty text
                    text += extracted_text + "\n"
        except Exception as e:
            raise Exception(f"Error reading PDF {pdf_path}: {str(e)}")
    
    if not text.strip():
        raise Exception("No text could be extracted from the provided PDFs")
    
    return text

def get_text_chunks(text):
    """Split text into smaller chunks for processing"""
    try:
        if not text.strip():
            raise ValueError("Input text is empty")
            
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        chunks = text_splitter.split_text(text)
        
        # Filter out very small chunks
        chunks = [chunk for chunk in chunks if len(chunk.strip()) > 50]
        
        if not chunks:
            raise ValueError("No valid text chunks created")
            
        return chunks
    except Exception as e:
        raise Exception(f"Error splitting text: {str(e)}")

def get_vector_store(text_chunks):
    """Create and save FAISS vector store from text chunks"""
    try:
        if not text_chunks:
            raise ValueError("No text chunks provided")
            
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}  # Specify device to avoid warnings
        )
        vector_store = FAISS.from_texts(texts=text_chunks, embedding=embeddings)
        
        # Save in the same directory as the script
        save_dir = os.path.dirname(os.path.abspath(__file__))
        index_path = os.path.join(save_dir, "faiss_index")
        vector_store.save_local(index_path)
        
        print(f"Vector store saved successfully at: {index_path}")
        print(f"Number of documents indexed: {len(text_chunks)}")
        
        return vector_store
    except Exception as e:
        raise Exception(f"Error creating vector store: {str(e)}")

def process_question(user_question, model_name="llama-3.3-70b-versatile"):
    """Process user question using RAG approach"""
    try:
        if not user_question.strip():
            raise ValueError("Question cannot be empty")
            
        # Validate model name
        if model_name not in AVAILABLE_MODELS:
            print(f"Warning: Model {model_name} not in known models list. Available models:")
            for model_id, description in AVAILABLE_MODELS.items():
                print(f"  - {model_id}: {description}")
            print("Proceeding with the provided model name...")
        
        # Load embeddings and vector store
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
        current_dir = os.path.dirname(os.path.abspath(__file__))
        index_path = os.path.join(current_dir, "faiss_index")
        
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"Vector store not found at {index_path}. Please run the PDF processing first.")
        
        vector_store = FAISS.load_local(
            index_path,
            embeddings,
            allow_dangerous_deserialization=True
        )
        
        # Get API key
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise Exception("GROQ_API_KEY not found in environment variables")
        
        # Initialize the model
        model = ChatGroq(
            api_key=groq_api_key,
            model=model_name,
            temperature=0.3,
            max_tokens=4096  # Reasonable limit for responses
        )
        
        # Create prompt template
        prompt = ChatPromptTemplate.from_template("""
        Answer the question as detailed as possible from the provided context. 
        If the answer is not in the provided context, just say "Answer is not available in the context". 
        Don't provide incorrect information.
        
        Context: {context}
        Question: {input}
        
        Answer:
        """)
        
        # Create retriever
        retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 4}
        )
        
        # Create the chains using the new approach
        document_chain = create_stuff_documents_chain(model, prompt)
        retrieval_chain = create_retrieval_chain(retriever, document_chain)
        
        # Process the question
        response = retrieval_chain.invoke({"input": user_question})
        
        return response["answer"]
        
    except Exception as e:
        raise Exception(f"Error processing question: {str(e)}")

def process_question_simple(user_question, model_name="llama-3.3-70b-versatile"):
    """Simplified version without retrieval chain"""
    try:
        if not user_question.strip():
            raise ValueError("Question cannot be empty")
            
        # Load embeddings and vector store
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
        current_dir = os.path.dirname(os.path.abspath(__file__))
        index_path = os.path.join(current_dir, "faiss_index")
        
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"Vector store not found at {index_path}. Please run the PDF processing first.")
        
        vector_store = FAISS.load_local(
            index_path,
            embeddings,
            allow_dangerous_deserialization=True
        )
        
        # Get relevant documents
        docs = vector_store.similarity_search(user_question, k=4)
        
        if not docs:
            return "No relevant documents found for your question."
        
        # Prepare context from documents
        context = "\n\n".join([doc.page_content for doc in docs])
        
        # Get API key
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise Exception("GROQ_API_KEY not found in environment variables")
        
        # Initialize the model
        model = ChatGroq(
            api_key=groq_api_key,
            model=model_name,
            temperature=0.3,
            max_tokens=4096
        )
        
        # Create the prompt
        prompt_text = f"""
        Answer the question as detailed as possible from the provided context. 
        If the answer is not in the provided context, just say "Answer is not available in the context". 
        Don't provide incorrect information.
        
        Context: {context}
        Question: {user_question}
        
        Answer:
        """
        
        # Get response from model
        response = model.invoke(prompt_text)
        
        return response.content
        
    except Exception as e:
        raise Exception(f"Error processing question: {str(e)}")

def list_available_models():
    """List current available Groq models"""
    print("Available Groq Models:")
    print("=" * 50)
    for model_id, description in AVAILABLE_MODELS.items():
        print(f"ID: {model_id}")
        print(f"Description: {description}")
        print("-" * 30)

def test_api_connection(model_name="llama-3.3-70b-versatile"):
    """Test if the API connection and model work"""
    try:
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            return False, "GROQ_API_KEY not found in environment variables"
        
        model = ChatGroq(
            api_key=groq_api_key,
            model=model_name,
            temperature=0.3,
            max_tokens=50
        )
        
        response = model.invoke("Hello, this is a test. Please respond with 'API working correctly.'")
        return True, f"API working. Response: {response.content[:100]}"
        
    except Exception as e:
        return False, f"API test failed: {str(e)}"

def main():
    """Example of how to use the RAG system"""
    try:
        print("=== Groq RAG System ===")
        
        # Test API connection first
        print("Testing API connection...")
        api_working, message = test_api_connection()
        print(f"API Test Result: {message}")
        
        if not api_working:
            print("Please check your GROQ_API_KEY and try again.")
            return
        
        # List available models
        list_available_models()
        
        # Example usage
        print("\n=== Processing PDFs ===")
        # Step 1: Process PDFs (run this once to create the vector store)
        pdf_paths = ["path/to/your/document1.pdf", "path/to/your/document2.pdf"]
        
        # Uncomment these lines when you have actual PDF files
        # raw_text = get_pdf_text(pdf_paths)
        # text_chunks = get_text_chunks(raw_text)
        # get_vector_store(text_chunks)
        # print("Vector store created successfully!")
        
        print("\n=== Example Questions ===")
        # Step 2: Ask questions (uncomment when you have a vector store)
        # question = "What is the main topic discussed in the documents?"
        # answer = process_question(question)
        # print(f"Question: {question}")
        # print(f"Answer: {answer}")
        
        print("Setup complete! Uncomment the PDF processing lines to use with your documents.")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()