from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import google.generativeai as genai
import os
from firebase_admin import firestore

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

        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        system_prompt = (
            "You are an expert IIT JEE Mentor named JARVIS. "
            "You MUST reply in conversational 'Hinglish' (Hindi written in English alphabet). "
            "Example: 'Dekho bhai, jab object rotate karta hai to centrifugal force lagta hai.' "
            "Explain complex concepts simply, like a friendly Indian elder brother/mentor. "
            "Keep the answer under 3-4 short sentences. Make it suitable for text-to-speech. "
            "No markdown, no complex symbols. End with an encouraging note in Hinglish like 'Phod denge exam!'."
        ) + memory_context
        
        response = model.generate_content(f"{system_prompt}\n\nStudent Query: {request.query}")
        
        return {"response": response.text.replace("*", "").replace("#", "")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
