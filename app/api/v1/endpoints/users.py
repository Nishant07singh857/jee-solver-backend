from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from firebase_admin import firestore
from typing import Optional
import google.generativeai as genai
import os

router = APIRouter()

class UpdateCoins(BaseModel):
    uid: str
    amount: int
    reason: str = "battle"

class UpdateMemory(BaseModel):
    uid: str
    topic: str
    context: str = ""

class LeaderboardQuery(BaseModel):
    limit: int = 20

@router.post("/update-coins")
async def update_coins(request: UpdateCoins):
    """Add or subtract JEE Coins for a user."""
    try:
        db = firestore.client()
        user_ref = db.collection("users").document(request.uid)
        user_doc = user_ref.get()

        if user_doc.exists:
            data = user_doc.to_dict()
            current = data.get("jeeCoins", 0)
            new_total = max(0, current + request.amount)
            user_ref.update({"jeeCoins": new_total})
        else:
            new_total = max(0, request.amount)
            user_ref.set({"jeeCoins": new_total}, merge=True)

        return {"success": True, "newBalance": new_total, "reason": request.reason}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save-memory")
async def save_memory(request: UpdateMemory):
    """Save a weak topic or interaction to user's AI memory for JARVIS personalization."""
    try:
        db = firestore.client()
        user_ref = db.collection("users").document(request.uid)
        user_doc = user_ref.get()

        gemini_key = os.getenv("GEMINI_API_KEY")
        
        existing_memory = ""
        if user_doc.exists:
            existing_memory = user_doc.to_dict().get("ai_memory", "")

        # Use Gemini to smartly summarize and merge memory
        if gemini_key and existing_memory:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-2.5-flash")
            merge_prompt = (
                f"You maintain a concise student weakness profile for a JEE aspirant. "
                f"Current profile: '{existing_memory}'. "
                f"New data: student asked about '{request.topic}'. Context: '{request.context}'. "
                f"Merge this into an updated profile in under 100 words. "
                f"Keep only the most important weakness areas. Return ONLY the updated profile text, no explanation."
            )
            resp = model.generate_content(merge_prompt)
            new_memory = resp.text.strip().replace("*", "").replace("#", "")
        else:
            # First memory entry or no API key
            new_memory = f"Weak in: {request.topic}. {request.context}".strip()

        user_ref.set({"ai_memory": new_memory}, merge=True)

        return {"success": True, "memory": new_memory}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leaderboard")
async def get_leaderboard(limit: int = 20):
    """Get top players by JEE Coins for the global leaderboard."""
    try:
        db = firestore.client()
        users_ref = db.collection("users").order_by("jeeCoins", direction=firestore.Query.DESCENDING).limit(limit)
        docs = users_ref.stream()

        leaderboard = []
        rank = 1
        for doc in docs:
            data = doc.to_dict()
            leaderboard.append({
                "rank": rank,
                "uid": doc.id,
                "name": data.get("displayName", data.get("name", "Anonymous")),
                "coins": data.get("jeeCoins", 0),
                "streak": data.get("streak", 0),
                "battleWins": data.get("battleWins", 0),
            })
            rank += 1

        return {"leaderboard": leaderboard}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update-streak")
async def update_streak(uid: str):
    """Update daily login streak for a user."""
    try:
        from datetime import datetime, timedelta
        db = firestore.client()
        user_ref = db.collection("users").document(uid)
        user_doc = user_ref.get()

        today = datetime.now().strftime("%Y-%m-%d")

        if user_doc.exists:
            data = user_doc.to_dict()
            last_active = data.get("lastActiveDate", "")
            current_streak = data.get("streak", 0)

            if last_active == today:
                return {"streak": current_streak, "message": "Already counted today"}
            
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            if last_active == yesterday:
                new_streak = current_streak + 1
            else:
                new_streak = 1  # Reset streak

            # Bonus coins for streaks
            bonus = 0
            if new_streak == 7:
                bonus = 100
            elif new_streak == 30:
                bonus = 500
            elif new_streak % 7 == 0:
                bonus = 50

            current_coins = data.get("jeeCoins", 0)
            user_ref.update({
                "streak": new_streak,
                "lastActiveDate": today,
                "jeeCoins": current_coins + 10 + bonus  # 10 daily + bonus
            })
            return {"streak": new_streak, "bonus": bonus, "dailyCoins": 10}
        else:
            user_ref.set({
                "streak": 1,
                "lastActiveDate": today,
                "jeeCoins": 10
            }, merge=True)
            return {"streak": 1, "bonus": 0, "dailyCoins": 10}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
