from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import google.generativeai as genai
import os
from firebase_admin import firestore

# RAG Imports
try:
    from langchain_community.vectorstores import FAISS
    from langchain_huggingface import HuggingFaceEmbeddings
    
    FAISS_INDEX_PATH = "faiss_index"
    print("🤖 Loading offline FAISS Brain into RAM for AI Mentor...")
    # allow_dangerous_deserialization is required for local trusted FAISS indexes in recent versions
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    rag_brain = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
    print("✅ RAG Brain (FAISS) loaded successfully!")
except Exception as e:
    print(f"⚠️ FAISS Brain not loaded. AI will run without RAG. Error: {e}")
    rag_brain = None

router = APIRouter()

class VoiceQuery(BaseModel):
    query: str
    uid: str = None

@router.post("/ask")
async def ask_mentor(request: VoiceQuery):
    try:
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            raise HTTPException(status_code=500, detail="Gemini key not configured")
        
        # Fetch AI Memory from Firebase
        memory_context = ""
        if request.uid:
            db = firestore.client()
            user_ref = db.collection("users").document(request.uid)
            user_doc = user_ref.get()
            if user_doc.exists:
                data = user_doc.to_dict()
                memory = data.get("ai_memory", "")
                if memory:
                    memory_context = f"\n\nStudent's Past Weaknesses & Memory: {memory}. Address them if relevant."

        # Fetch RAG Context from FAISS Book Index
        rag_context = ""
        if rag_brain:
            try:
                # Fetch top 2 most relevant paragraphs from the 4000+ page textbook brain
                docs = rag_brain.similarity_search(request.query, k=2)
                if docs:
                    context_text = "\n".join([doc.page_content for doc in docs])
                    rag_context = f"\n\n[OFFICIAL TEXTBOOK REFERENCE]\n{context_text}\n\n(Use the above official textbook reference to answer the student accurately if relevant.)"
            except Exception as e:
                print(f"⚠️ RAG Search Error: {e}")

        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        system_prompt = (
            "You are an expert IIT JEE Mentor named JARVIS. "
            "You MUST reply in conversational 'Hinglish' (Hindi written in English alphabet). "
            "Example: 'Dekho bhai, jab object rotate karta hai to centrifugal force lagta hai.' "
            "Explain complex concepts simply, like a friendly Indian elder brother/mentor. "
            "Keep the answer under 3-4 short sentences. Make it suitable for text-to-speech. "
            "No markdown, no complex symbols. End with an encouraging note in Hinglish like 'Phod denge exam!'."
        ) + memory_context + rag_context
        
        response = model.generate_content(f"{system_prompt}\n\nStudent Query: {request.query}")
        
        return {"response": response.text.replace("*", "").replace("#", "")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
