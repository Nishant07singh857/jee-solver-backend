import os
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

KNOWLEDGE_BASE_DIR = "knowledge_base"
FAISS_INDEX_PATH = "faiss_index"

def build_brain():
    print("🧠 Scanning for PDFs in 'knowledge_base' folder and subfolders...")
    
    pdf_files = []
    for root, dirs, files in os.walk(KNOWLEDGE_BASE_DIR):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
                
    if not pdf_files:
        print("❌ No PDFs found! Please put some NCERT or HC Verma PDFs inside 'backend/knowledge_base/'.")
        return

    documents = []
    for pdf_path in pdf_files:
        print(f"📖 Reading book: {os.path.basename(pdf_path)}...")
        try:
            loader = PyPDFLoader(pdf_path)
            documents.extend(loader.load())
        except Exception as e:
            print(f"⚠️ Error reading {os.path.basename(pdf_path)}: {e}")

    print(f"✅ Loaded {len(documents)} pages in total.")

    print("✂️ Chunking text into smaller paragraphs...")
    # Split text into chunks of 1000 characters with 200 character overlap
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(documents)
    print(f"✅ Created {len(chunks)} chunks.")

    print("🤖 Converting text to Vectors (Embedding) using local Mac M2... (Don't worry, it's a very light model!)")
    # Using a very lightweight model that will NOT heat up your Mac M2
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    print("💾 Saving Vectors to FAISS Database...")
    db = FAISS.from_documents(chunks, embeddings)
    db.save_local(FAISS_INDEX_PATH)

    print("🎉 Done! Your AI now has a local brain. You can run this again whenever you add new PDFs.")

if __name__ == "__main__":
    build_brain()
