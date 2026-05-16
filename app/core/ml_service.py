# app/services/ml_service.py
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.cluster import KMeans
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class JEEMLAnalyzer:
    def __init__(self):
        self.performance_model = None
        self.clustering_model = None
        self.load_models()
    
    def load_models(self):
        """Initialize ML models"""
        try:
            self.performance_model = RandomForestRegressor(n_estimators=100, random_state=42)
            self.clustering_model = KMeans(n_clusters=4, random_state=42)
            logger.info("✅ ML models initialized successfully")
        except Exception as e:
            logger.error(f"❌ Model initialization failed: {e}")
    
    def analyze_student_performance(self, student_data):
        """Comprehensive performance analysis with ML"""
        try:
            features = self._extract_features(student_data)
            
            # Performance prediction
            predicted_score = self._predict_performance(features)
            
            # Weak area identification
            weak_areas = self._identify_weak_areas(student_data)
            
            # Learning pattern analysis
            learning_insights = self._analyze_learning_patterns(student_data)
            
            # Rank prediction
            rank_prediction = self._predict_rank(features)
            
            return {
                "performance_metrics": {
                    "predicted_score": round(predicted_score, 1),
                    "current_level": self._get_performance_level(predicted_score),
                    "improvement_potential": self._calculate_improvement_potential(features),
                    "consistency_score": self._calculate_consistency(student_data)
                },
                "weak_areas": weak_areas,
                "learning_insights": learning_insights,
                "rank_prediction": rank_prediction,
                "recommendations": self._generate_recommendations(weak_areas, learning_insights)
            }
        except Exception as e:
            logger.error(f"Performance analysis error: {e}")
            return self._get_fallback_analysis()
    
    def _extract_features(self, student_data):
        """Extract features for ML models"""
        features = []
        
        # Basic performance features
        features.extend([
            student_data.get('overall_accuracy', 0),
            student_data.get('physics_accuracy', 0),
            student_data.get('chemistry_accuracy', 0),
            student_data.get('maths_accuracy', 0),
            student_data.get('total_questions', 0),
            student_data.get('current_streak', 0)
        ])
        
        # Topic distribution features
        topic_scores = student_data.get('topic_scores', {})
        if topic_scores:
            scores = list(topic_scores.values())
            features.extend([
                np.mean(scores) if scores else 0,
                np.std(scores) if len(scores) > 1 else 0,
                min(scores) if scores else 0,
                max(scores) if scores else 0
            ])
        else:
            features.extend([0, 0, 0, 0])
        
        # Time-based features
        weekly_data = student_data.get('weekly_progress', [])
        if weekly_data:
            recent_accuracy = [day.get('accuracy', 0) for day in weekly_data[-3:]]
            features.append(np.mean(recent_accuracy) if recent_accuracy else 0)
        else:
            features.append(0)
        
        return np.array(features).reshape(1, -1)
    
    def _predict_performance(self, features):
        """Predict future performance score"""
        base_score = np.mean(features[0][:4])  # Average subject accuracy
        streak_bonus = min(features[0][5] * 0.5, 10)  # Streak bonus
        consistency_bonus = (100 - features[0][7]) * 0.1  # Lower std deviation is better
        
        predicted = base_score + streak_bonus + consistency_bonus
        return min(predicted, 100)
    
    def _identify_weak_areas(self, student_data):
        """Identify weak topics using clustering"""
        topic_scores = student_data.get('topic_scores', {})
        
        if len(topic_scores) < 3:
            return [{"topic": topic, "score": score, "priority": "high"} 
                   for topic, score in topic_scores.items() if score < 60]
        
        # Convert to features for clustering
        topic_features = []
        topic_names = []
        for topic, stats in topic_scores.items():
            if isinstance(stats, dict):
                score = stats.get('accuracy', 0)
                attempts = stats.get('total', 1)
            else:
                score = stats
                attempts = 1
                
            topic_features.append([score, attempts])
            topic_names.append(topic)
        
        # Perform clustering
        try:
            clusters = self.clustering_model.fit_predict(topic_features)
            
            # Find weakest cluster
            cluster_avgs = {}
            for i in range(self.clustering_model.n_clusters):
                cluster_scores = [topic_features[j][0] for j in range(len(topic_features)) if clusters[j] == i]
                cluster_avgs[i] = np.mean(cluster_scores) if cluster_scores else 0
            
            weakest_cluster = min(cluster_avgs, key=cluster_avgs.get)
            
            weak_areas = []
            for i, topic in enumerate(topic_names):
                if clusters[i] == weakest_cluster and topic_features[i][0] < 70:
                    priority = "high" if topic_features[i][0] < 50 else "medium"
                    weak_areas.append({
                        "topic": topic,
                        "score": round(topic_features[i][0], 1),
                        "priority": priority,
                        "recommendation": self._get_topic_recommendation(topic, topic_features[i][0])
                    })
            
            return weak_areas
        except Exception as e:
            logger.error(f"Clustering error: {e}")
            return []
    
    def _analyze_learning_patterns(self, student_data):
        """Analyze learning patterns and behaviors"""
        weekly_data = student_data.get('weekly_progress', [])
        
        if len(weekly_data) < 3:
            return {"pattern": "insufficient_data", "suggestion": "Practice more to get insights"}
        
        # Analyze trend
        accuracies = [day.get('accuracy', 0) for day in weekly_data]
        questions = [day.get('questions', 0) for day in weekly_data]
        
        # Calculate trends
        accuracy_trend = self._calculate_trend(accuracies)
        activity_trend = self._calculate_trend(questions)
        
        # Determine learning pattern
        if accuracy_trend > 0.5 and activity_trend > 0:
            pattern = "rapid_improver"
        elif accuracy_trend > 0 and activity_trend > 0:
            pattern = "steady_learner"
        elif accuracy_trend < -0.5:
            pattern = "needs_attention"
        else:
            pattern = "consistent_performer"
        
        return {
            "learning_pattern": pattern,
            "accuracy_trend": round(accuracy_trend, 2),
            "activity_level": "high" if np.mean(questions) > 20 else "medium" if np.mean(questions) > 10 else "low",
            "optimal_study_time": self._suggest_study_time(weekly_data),
            "weekly_consistency": self._calculate_weekly_consistency(weekly_data)
        }
    
    def _predict_rank(self, features):
        """Predict JEE rank based on performance"""
        base_accuracy = np.mean(features[0][:4])
        
        # Convert accuracy to approximate rank
        if base_accuracy >= 90:
            rank_range = "1-1000"
        elif base_accuracy >= 80:
            rank_range = "1000-5000"
        elif base_accuracy >= 70:
            rank_range = "5000-15000"
        elif base_accuracy >= 60:
            rank_range = "15000-50000"
        else:
            rank_range = "50000+"
        
        return {
            "predicted_rank_range": rank_range,
            "confidence": "medium",
            "improvement_tips": self._get_rank_improvement_tips(base_accuracy)
        }
    
    def _calculate_trend(self, values):
        """Calculate trend using linear regression"""
        if len(values) < 2:
            return 0
        
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        return slope
    
    def _get_performance_level(self, score):
        """Get performance level description"""
        if score >= 90: return "Excellent"
        elif score >= 80: return "Very Good"
        elif score >= 70: return "Good"
        elif score >= 60: return "Average"
        else: return "Needs Improvement"
    
    def _get_topic_recommendation(self, topic, score):
        """Get specific recommendations for topics"""
        if score < 40:
            return f"Focus on basic concepts of {topic}. Start with theory and simple problems."
        elif score < 60:
            return f"Practice more {topic} problems. Focus on understanding concepts thoroughly."
        elif score < 80:
            return f"Good progress in {topic}. Practice advanced problems and time management."
        else:
            return f"Excellent in {topic}. Maintain practice and help others learn."
    
    def _get_rank_improvement_tips(self, accuracy):
        """Get rank improvement tips"""
        tips = []
        if accuracy < 60:
            tips.extend(["Focus on strengthening basic concepts", "Practice regularly", "Analyze mistakes carefully"])
        elif accuracy < 75:
            tips.extend(["Work on speed and accuracy", "Practice mock tests", "Identify and improve weak areas"])
        else:
            tips.extend(["Focus on advanced problems", "Improve time management", "Take full-length mock tests regularly"])
        return tips
    
    def _get_fallback_analysis(self):
        """Provide fallback analysis when ML fails"""
        return {
            "performance_metrics": {
                "predicted_score": 0,
                "current_level": "Calculating...",
                "improvement_potential": 0,
                "consistency_score": 0
            },
            "weak_areas": [],
            "learning_insights": {"pattern": "analyzing", "suggestion": "Complete more quizzes for better insights"},
            "rank_prediction": {"predicted_rank_range": "Calculating...", "confidence": "low"},
            "recommendations": ["Practice more questions to get personalized insights"]
        }

# Global instance
ml_analyzer = JEEMLAnalyzer()