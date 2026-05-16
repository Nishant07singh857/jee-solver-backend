# app/services/progress_calculator.py
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)

class ProgressCalculator:
    
    @staticmethod
    def calculate_overall_progress(quiz_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall progress statistics"""
        if not quiz_results:
            return ProgressCalculator.get_empty_progress()
        
        try:
            total_questions = 0
            correct_answers = 0
            subject_stats = {
                "Physics": {"total": 0, "correct": 0, "accuracy": 0},
                "Chemistry": {"total": 0, "correct": 0, "accuracy": 0},
                "Maths": {"total": 0, "correct": 0, "accuracy": 0}
            }
            topic_stats = {
                "Physics": {},
                "Chemistry": {},
                "Maths": {}
            }
            
            # Process each quiz result
            for result in quiz_results:
                total_questions += result.get("totalQuestions", 0)
                correct_answers += result.get("correctAnswers", 0)
                
                # Process subject-wise data
                subject = result.get("subject", "Physics")
                if subject in subject_stats:
                    subject_stats[subject]["total"] += result.get("totalQuestions", 0)
                    subject_stats[subject]["correct"] += result.get("correctAnswers", 0)
                
                # Process topic-wise data from individual questions
                for question in result.get("questions", []):
                    q_subject = question.get("subject", subject)
                    q_topic = question.get("topic", "General")
                    
                    if q_subject in topic_stats:
                        if q_topic not in topic_stats[q_subject]:
                            topic_stats[q_subject][q_topic] = {"total": 0, "correct": 0}
                        
                        topic_stats[q_subject][q_topic]["total"] += 1
                        if question.get("isCorrect", False):
                            topic_stats[q_subject][q_topic]["correct"] += 1
            
            # Calculate overall accuracy
            overall_accuracy = (correct_answers / total_questions * 100) if total_questions > 0 else 0
            
            # Calculate subject performances
            subject_performance = []
            for subject, stats in subject_stats.items():
                accuracy = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
                subject_performance.append({
                    "name": subject,
                    "accuracy": round(accuracy, 1),
                    "total": stats["total"],
                    "correct": stats["correct"],
                    "color": ProgressCalculator.get_subject_color(subject)
                })
            
            # Calculate streak
            streak = ProgressCalculator.calculate_streak(quiz_results)
            
            # Calculate rank
            rank = ProgressCalculator.calculate_rank(overall_accuracy)
            
            return {
                "overall": {
                    "totalQuestions": total_questions,
                    "correctAnswers": correct_answers,
                    "accuracy": round(overall_accuracy, 1),
                    "streak": streak,
                    "rank": rank
                },
                "subjects": subject_performance,
                "topics": topic_stats
            }
            
        except Exception as e:
            logger.error(f"Error calculating overall progress: {e}")
            return ProgressCalculator.get_empty_progress()
    
    @staticmethod
    def calculate_weekly_progress(quiz_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Calculate weekly progress data"""
        weekly_data = []
        today = datetime.now().date()
        
        try:
            for i in range(6, -1, -1):
                date = today - timedelta(days=i)
                date_str = date.isoformat()
                
                day_questions = 0
                day_correct = 0
                
                for result in quiz_results:
                    completed_at = result.get("completedAt")
                    if completed_at:
                        # Handle different timestamp formats
                        if isinstance(completed_at, datetime):
                            result_date = completed_at.date()
                        elif hasattr(completed_at, 'date'):
                            result_date = completed_at.date()
                        else:
                            # Assume it's a timestamp or string
                            try:
                                result_date = datetime.fromisoformat(str(completed_at)).date()
                            except:
                                continue
                        
                        if result_date == date:
                            day_questions += result.get("totalQuestions", 0)
                            day_correct += result.get("correctAnswers", 0)
                
                day_accuracy = (day_correct / day_questions * 100) if day_questions > 0 else 0
                
                weekly_data.append({
                    "day": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][date.weekday()],
                    "accuracy": round(day_accuracy, 1),
                    "questions": day_questions,
                    "date": date_str
                })
            
            return weekly_data
            
        except Exception as e:
            logger.error(f"Error calculating weekly progress: {e}")
            # Return empty weekly data
            return [{"day": day, "accuracy": 0, "questions": 0} for day in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]]
    
    @staticmethod
    def calculate_streak(quiz_results: List[Dict[str, Any]]) -> int:
        """Calculate current streak of active days"""
        if not quiz_results:
            return 0
        
        try:
            unique_days = set()
            for result in quiz_results:
                completed_at = result.get("completedAt")
                if completed_at:
                    if isinstance(completed_at, datetime):
                        date = completed_at.date()
                    elif hasattr(completed_at, 'date'):
                        date = completed_at.date()
                    else:
                        try:
                            date = datetime.fromisoformat(str(completed_at)).date()
                        except:
                            continue
                    unique_days.add(date)
            
            sorted_dates = sorted(unique_days, reverse=True)
            today = datetime.now().date()
            
            streak = 0
            current_date = today
            
            for date in sorted_dates:
                if date == current_date:
                    streak += 1
                    current_date -= timedelta(days=1)
                else:
                    break
            
            return streak
            
        except Exception as e:
            logger.error(f"Error calculating streak: {e}")
            return 0
    
    @staticmethod
    def calculate_rank(accuracy: float) -> str:
        """Calculate rank based on accuracy"""
        if accuracy >= 90: return "Top 5%"
        elif accuracy >= 80: return "Top 15%"
        elif accuracy >= 70: return "Top 30%"
        elif accuracy >= 60: return "Top 50%"
        elif accuracy >= 50: return "Top 70%"
        elif accuracy > 0: return "Needs Improvement"
        return "Start Practicing"
    
    @staticmethod
    def get_subject_color(subject: str) -> str:
        """Get color for each subject"""
        colors = {
            "Physics": "#3b82f6",
            "Chemistry": "#22c55e",
            "Maths": "#f97316"
        }
        return colors.get(subject, "#6b7280")
    
    @staticmethod
    def get_empty_progress() -> Dict[str, Any]:
        """Return empty progress structure"""
        return {
            "overall": {
                "totalQuestions": 0,
                "correctAnswers": 0,
                "accuracy": 0,
                "streak": 0,
                "rank": "Start Practicing"
            },
            "subjects": [
                {"name": "Physics", "accuracy": 0, "total": 0, "correct": 0, "color": "#3b82f6"},
                {"name": "Chemistry", "accuracy": 0, "total": 0, "correct": 0, "color": "#22c55e"},
                {"name": "Maths", "accuracy": 0, "total": 0, "correct": 0, "color": "#f97316"}
            ],
            "topics": {
                "Physics": {},
                "Chemistry": {},
                "Maths": {}
            }
        }
    
    @staticmethod
    def _extract_topic_scores(topic_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract topic scores for ML analysis"""
        topic_scores = {}
        for subject, topics in topic_data.items():
            for topic, stats in topics.items():
                if isinstance(stats, dict) and stats.get("total", 0) > 0:
                    accuracy = (stats.get("correct", 0) / stats.get("total", 1)) * 100
                    topic_scores[f"{subject}_{topic}"] = accuracy
        return topic_scores