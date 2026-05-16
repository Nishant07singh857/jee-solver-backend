from fastapi import APIRouter

router = APIRouter()

@router.get("/overall/{user_id}")
def get_overall_progress(user_id: str):
    return {
        "status": "success",
        "data": {
            "total_score": 0,
            "accuracy": 0,
            "questions_attempted": 0,
            "level": "Beginner"
        }
    }

@router.get("/weekly/{user_id}")
def get_weekly_progress(user_id: str):
    return {
        "status": "success",
        "data": []
    }

@router.get("/topic-heatmap/{user_id}")
def get_topic_heatmap(user_id: str):
    return {
        "status": "success",
        "data": {}
    }

@router.get("/subject/{user_id}")
def get_subject_progress(user_id: str):
    return {
        "status": "success",
        "data": {
            "Physics": 0,
            "Chemistry": 0,
            "Maths": 0
        }
    }
