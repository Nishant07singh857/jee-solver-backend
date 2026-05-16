from fastapi import APIRouter, File, UploadFile, HTTPException
import google.generativeai as genai
import os
import io
from PIL import Image

router = APIRouter()

@router.post("/check-attempt")
async def check_attempt(file: UploadFile = File(...)):
    try:
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            raise HTTPException(status_code=500, detail="Gemini key not configured")
        
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-2.5-flash")

        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        
        prompt = (
            "You are an expert IIT JEE Examiner. The attached image contains a student's handwritten attempt at a Physics, Chemistry, or Math question. "
            "Your job is NOT just to provide the correct solution. Your job is to act like a strict but helpful teacher: "
            "1. Read the student's steps. "
            "2. Identify the EXACT step where they made a mistake (e.g., calculation error, wrong formula, conceptual mistake). "
            "3. If their approach is completely correct, congratulate them! "
            "4. If there is a mistake, explain why it's wrong and then provide the correct next steps to reach the final answer. "
            "Keep the tone encouraging."
        )

        response = model.generate_content([prompt, image])
        
        return {"feedback": response.text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Examiner Error: {str(e)}")
