# 🎯 AI-Powered JEE Solver & Simulator

A production-grade, highly scalable web platform designed to help students conquer the Joint Entrance Examination (JEE) Main and Advanced. This platform combines an authentic NTA-style mock test environment with advanced AI doubt solving, infinite question generation, and deep performance analytics.

## ✨ Billion-Dollar Features (India's First)

- **🎙️ JARVIS Voice Mentor (Hinglish):** A floating, glowing AI orb that listens to your voice and explains complex physics/math concepts in natural Hindi/English (Hinglish) audio. Powered by Gemini 2.5 Flash & Web Speech API.
- **⚔️ 1v1 Real-Time Ranked Battles:** Matchmaking system where students compete live on the same 5 questions. Fast answers give more points. Includes real-time synced timers and leaderboards.
- **🧠 AI Step-by-Step Examiner:** Upload your handwritten solution. Instead of just giving the answer, the AI acts like a strict teacher, finds the *exact step* you made a calculation or formula mistake, and explains why.
- **💰 Gamification & JEE Coins:** Daily streaks, battle rewards, and a global leaderboard. Students earn "JEE Coins" for logging in and winning 1v1 battles.
- **🔮 AI Vector Memory:** JARVIS remembers each student! The system automatically stores a profile of the student's weaknesses. The next time they ask a doubt, JARVIS reminds them of their past mistakes.
- **📸 Photo Doubt Solver (Gemini Vision):** Snap a photo of any complex math, physics, or chemistry problem, and get an instant, step-by-step breakdown using Gemini 2.5 Flash Vision.
- **♾️ Infinite Question Bank (AI Generated):** A backend cron job utilizes Groq (Llama 3) to continuously generate high-quality, syllabus-aligned questions directly into a custom JSONL dataset and Firebase.
- **NTA Mock Test Simulator:** A pixel-perfect recreation of the official NTA JEE interface, complete with a strict timer, question status palette, and auto-submission.
- **Smart Analytics & Mistake Bank:** Tracks accuracy, time-per-question, and automatically schedules missed questions using spaced repetition (3, 7, and 14-day intervals).

## 🛠️ Technology Stack

**Frontend:**
- Next.js (React.js)
- GSAP (Advanced Animations)
- Three.js (3D Background Effects)
- CSS Modules & Vanilla CSS (Tailored UI)
- Firebase Auth (Authentication)

**Backend:**
- FastAPI (Python)
- Firebase Firestore (NoSQL Database)
- Groq API (Llama 3 70B) & Google Gemini API (AI capabilities)

## 🚀 Getting Started

### Prerequisites
- Node.js (v18+)
- Python (3.10+)
- Firebase Account & Service Account Key
- API Keys for Groq and Gemini

### Backend Setup
1. Navigate to the `backend/` directory: `cd backend`
2. Create a virtual environment: `python -m venv venv`
3. Activate the environment: `source venv/bin/activate` (Mac/Linux) or `venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Place your `serviceAccountKey.json` from Firebase into the backend root.
6. Create a `.env` file and add your API keys:
   ```env
   GEMINI_API_KEY=your_gemini_key
   GROQ_API_KEY=your_groq_key
   ```
7. Start the FastAPI server: `uvicorn main:app --reload --port 8000`

### Frontend Setup
1. Navigate to the `frontend/` directory: `cd frontend`
2. Install dependencies: `npm install`
3. Create a `.env.local` file with your Firebase config.
4. Start the development server: `npm run dev`
5. Open [http://localhost:3000](http://localhost:3000) in your browser.

## 🧠 Custom Dataset Generation
To continuously generate new questions for your database and local fine-tuning:
```bash
cd backend
python cron_generate_groq.py
```
This script handles rate limits elegantly and prepares data in `.jsonl` format.

## 📄 License
This project is for educational purposes. All JEE trademarks belong to the National Testing Agency (NTA).
