import os
import sys
from dotenv import load_dotenv 
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


try:
    cred = credentials.Certificate("serviceAccountKey.json")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    print(" Firebase initialized successfully.")
except Exception as e:
    print(f" Firebase initialization failed: {e}")


app = FastAPI(title="JEE Solver API")

from app.api.v1.endpoints import questions, solutions, auth, progress, ml, mentor, examiner, users

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(questions.router, prefix="/api/v1/questions", tags=["Questions"])
app.include_router(solutions.router, prefix="/api/v1/solutions", tags=["Solutions"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(progress.router, prefix="/api/v1/progress", tags=["Progress"])
app.include_router(ml.router, prefix="/api/v1/ml", tags=["ML Analysis"])
app.include_router(mentor.router, prefix="/api/v1/mentor", tags=["Mentor"])
app.include_router(examiner.router, prefix="/api/v1/examiner", tags=["Examiner"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])

@app.get("/")
def root():
    return {"message": "Welcome to the JEE Solver API. The Question Bank is ready!"}

@app.get("/api/v1/health")
def health_check():
    return {"status": "ok", "message": "API is running"}