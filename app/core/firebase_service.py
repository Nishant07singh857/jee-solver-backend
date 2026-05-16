import firebase_admin
from firebase_admin import firestore, auth
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Initialize Firestore
try:
    db = firestore.client()
    logger.info("✅ Firestore client initialized successfully")
except Exception as e:
    logger.error(f"❌ Firestore initialization failed: {e}")
    db = None

async def get_quiz_results(user_id: str) -> List[Dict[str, Any]]:
    """Get all quiz results for a user"""
    try:
        if not db:
            return []
            
        results_ref = db.collection('quizResults').where('userId', '==', user_id)
        docs = results_ref.stream()
        
        quiz_results = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            # Convert Firestore timestamp to datetime if needed
            if 'completedAt' in data and hasattr(data['completedAt'], 'timestamp'):
                data['completedAt'] = data['completedAt'].timestamp()
            quiz_results.append(data)
        
        logger.info(f"Retrieved {len(quiz_results)} quiz results for user {user_id}")
        return quiz_results
        
    except Exception as e:
        logger.error(f"Error getting quiz results for user {user_id}: {e}")
        return []

async def get_user_progress(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user progress data"""
    try:
        if not db:
            return None
            
        progress_ref = db.collection('userProgress').document(user_id)
        progress_doc = progress_ref.get()
        
        if progress_doc.exists:
            return progress_doc.to_dict()
        return None
        
    except Exception as e:
        logger.error(f"Error getting user progress for {user_id}: {e}")
        return None

async def update_user_progress(user_id: str, progress_data: Dict[str, Any]) -> bool:
    """Update user progress in Firebase"""
    try:
        if not db:
            return False
            
        progress_ref = db.collection('userProgress').document(user_id)
        progress_ref.set({
            **progress_data,
            'lastUpdated': datetime.now(),
            'userId': user_id
        }, merge=True)
        
        logger.info(f"Updated progress for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating progress for user {user_id}: {e}")
        return False

async def save_quiz_result(quiz_data: Dict[str, Any]) -> bool:
    """Save quiz result to Firebase"""
    try:
        if not db:
            return False
            
        quiz_ref = db.collection('quizResults').document()
        quiz_data['id'] = quiz_ref.id
        quiz_data['completedAt'] = datetime.now()
        
        quiz_ref.set(quiz_data)
        logger.info(f"Saved quiz result with ID: {quiz_ref.id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving quiz result: {e}")
        return False

async def get_user_bookmarks(user_id: str) -> List[Dict[str, Any]]:
    """Get user's bookmarked questions"""
    try:
        if not db:
            return []
            
        bookmarks_ref = db.collection('userBookmarks').document(user_id)
        bookmarks_doc = bookmarks_ref.get()
        
        if bookmarks_doc.exists:
            data = bookmarks_doc.to_dict()
            # Remove the document ID from the data
            data.pop('userId', None)
            return [{"id": k, **v} for k, v in data.items() if isinstance(v, dict)]
        return []
        
    except Exception as e:
        logger.error(f"Error getting bookmarks for user {user_id}: {e}")
        return []

async def save_user_bookmark(user_id: str, question_id: str, question_data: Dict[str, Any]) -> bool:
    """Save user bookmark"""
    try:
        if not db:
            return False
            
        bookmarks_ref = db.collection('userBookmarks').document(user_id)
        bookmarks_ref.set({
            question_id: {
                **question_data,
                'bookmarkedAt': datetime.now()
            }
        }, merge=True)
        
        logger.info(f"Saved bookmark for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving bookmark for user {user_id}: {e}")
        return False