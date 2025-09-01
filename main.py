# main.py
import os
import sys
from dotenv import load_dotenv # <--- ADD THIS LINE
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials

# --- Initialization & Configuration ---

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Initialize Firebase Admin SDK
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    print("✅ Firebase initialized successfully.")
except Exception as e:
    print(f"❌ Firebase initialization failed: {e}")


# --- FastAPI App Setup ---

app = FastAPI(title="JEE Solver API")

# Import your endpoint routers
from app.api.v1.endpoints import questions

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Routers ---
app.include_router(questions.router, prefix="/api/v1/questions", tags=["Questions"])


# --- Root and Test Endpoints ---

@app.get("/")
def root():
    return {"message": "Welcome to the JEE Solver API. The Question Bank is ready!"}