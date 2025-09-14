import json
import re
from typing import Dict, List, Any
import streamlit as st
import google.generativeai as genai
from datetime import datetime


# ------------------------------
# 1. AI Reviewer Class
# ------------------------------
class AIAnswerReviewer:
    def __init__(self, api_key: str = None):
        
        api_key = api_key or st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)

        
        self.model = genai.GenerativeModel(model_name="gemini-1.5-flash")

    def review_answer(self, question: Dict, response: str) -> Dict[str, Any]:
        """Main function to review and evaluate answers using AI"""

        
        prompt = self._create_evaluation_prompt(question, response)

        try:
            
            api_response = self.model.generate_content([prompt])
            ai_response = api_response.text
            return self._parse_ai_evaluation(ai_response)

        except Exception as e:
            # Fallback evaluation
            return self._fallback_evaluation(question, response, str(e))

    def _create_evaluation_prompt(self, question: Dict, response: str) -> str:
        """Create evaluation prompt"""

        question_text = question.get("question", "")
        question_type = question.get("type", "general")
        difficulty = question.get("difficulty", "medium")
        expected_keywords = question.get("keywords", [])

        return f"""
You are an expert Excel interviewer evaluating candidate responses.

Your job is to:
1. Assess technical accuracy of Excel knowledge
2. Evaluate depth of understanding  
3. Check for practical application skills
4. Provide constructive feedback

Rate answers on a scale of 0-100 and provide specific feedback.

EXCEL INTERVIEW QUESTION:
Type: {question_type}
Difficulty: {difficulty}
Question: "{question_text}"

CANDIDATE'S RESPONSE:
"{response}"

EVALUATION CRITERIA:
- Technical accuracy of Excel functions/formulas mentioned
- Depth of understanding shown
- Practical application and problem-solving approach
- Communication clarity

{f"Expected concepts to cover: {', '.join(expected_keywords)}" if expected_keywords else ""}

Please evaluate this response and provide detailed feedback in this EXACT JSON format:
{{
    "score": 85,
    "technical_accuracy": 90,
    "depth": 80,
    "practical_application": 85,
    "strengths": ["List specific strengths"],
    "improvements": ["List areas for improvement"],
    "overall_feedback": "Brief overall assessment"
}}

Return ONLY the JSON, no other text.
"""

    def _parse_ai_evaluation(self, ai_response: str) -> Dict[str, Any]:
        """Parse JSON response from Gemini"""

        try:
            
            json_match = re.search(r"\{[\s\S]*\}", ai_response)
            if json_match:
                evaluation_data = json.loads(json_match.group())
                return {
                    "score": evaluation_data.get("score", 50),
                    "technical_accuracy": evaluation_data.get("technical_accuracy", 50),
                    "depth": evaluation_data.get("depth", 50),
                    "practical_application": evaluation_data.get("practical_application", 50),
                    "strengths": evaluation_data.get("strengths", []),
                    "improvements": evaluation_data.get("improvements", []),
                    "overall_feedback": evaluation_data.get("overall_feedback", "Response evaluated"),
                    "evaluation_source": "AI",
                }
            else:
                return self._parse_text_response(ai_response)

        except json.JSONDecodeError:
            return self._parse_text_response(ai_response)

    def _parse_text_response(self, response: str) -> Dict[str, Any]:
        """Fallback when Gemini output is not JSON"""

        score = 70  # default
        for line in response.split("\n"):
            if "score" in line.lower() or "/100" in line:
                numbers = re.findall(r"\d+", line)
                if numbers:
                    score = min(int(numbers[0]), 100)
                    break

        return {
            "score": score,
            "technical_accuracy": score,
            "depth": max(score - 10, 0),
            "practical_application": max(score - 5, 0),
            "strengths": ["AI provided feedback"],
            "improvements": ["See detailed feedback below"],
            "overall_feedback": response[:200] + "..." if len(response) > 200 else response,
            "evaluation_source": "AI_Text",
        }

    def _fallback_evaluation(self, question: Dict, response: str, error: str) -> Dict[str, Any]:
        """Rule-based backup if Gemini fails"""

        score = 40
        words = len(response.split())
        if words > 30:
            score += 25
        elif words > 15:
            score += 15
        elif words > 5:
            score += 10

        excel_functions = ["SUM", "AVERAGE", "VLOOKUP", "IF", "COUNT", "PIVOT", "INDEX", "MATCH"]
        found_functions = [func for func in excel_functions if func.lower() in response.lower()]
        if found_functions:
            score += 20
        if "=" in response or "()" in response:
            score += 15

        return {
            "score": min(score, 100),
            "technical_accuracy": min(score, 100),
            "depth": max(score - 10, 0),
            "practical_application": max(score - 5, 0),
            "strengths": ["Response provided"] + ([f"Mentioned: {', '.join(found_functions[:2])}"] if found_functions else []),
            "improvements": ["Could provide more detail", "Add specific Excel function examples"],
            "overall_feedback": f"Fallback evaluation (Gemini API error: {error[:50]}...)",
            "evaluation_source": "Fallback",
        }


# ------------------------------
# 2. Hybrid Evaluator
# ------------------------------
class HybridEvaluator:
    def __init__(self, api_key: str = None):
        self.ai_reviewer = AIAnswerReviewer(api_key)

    def evaluate_comprehensive(self, question: Dict, response: str) -> Dict[str, Any]:
        ai_eval = self.ai_reviewer.review_answer(question, response)

        word_count = len(response.split())
        char_count = len(response.strip())

        return {
            **ai_eval,
            "response_length": {
                "words": word_count,
                "characters": char_count,
                "quality": "detailed" if word_count > 20 else "brief" if word_count > 5 else "minimal",
            },
            "timestamp": datetime.now().isoformat(),
            "question_id": question.get("id", "unknown"),
        }


# ------------------------------
# 3. Interview Report Generator
# ------------------------------
class InterviewReportGenerator:
    def __init__(self):
        self.hiring_thresholds = {
            "finance": {"minimum_score": 75, "critical_skills": ["lookup_functions", "advanced_formulas"]},
            "operations": {"minimum_score": 70, "critical_skills": ["data_manipulation", "basic_formulas"]},
            "data_analytics": {"minimum_score": 80, "critical_skills": ["data_analysis", "advanced_formulas"]},
        }

    def generate_final_report(self, evaluations: List[Dict], role: str = "general") -> Dict[str, Any]:
        # If there are no evaluations, create a report with a score of 0
        if not evaluations:
            avg_score = 0
            technical_avg = 0
            depth_avg = 0
            practical_avg = 0
            hiring_decision = self._make_hiring_decision(avg_score, role, evaluations)
            skills_assessment = self._assess_critical_skills(evaluations)
            executive_summary = "Candidate did not provide any answers. The system could not conduct an assessment."
            critical_gaps = ["CRITICAL: No answers provided for evaluation."]
            recommendation_rationale = "Candidate did not engage in the interview process."
            next_steps = ["Reject application", "No data available to assess skills"]

            return {
                "overall_score": avg_score,
                "hiring_decision": hiring_decision,
                "executive_summary": executive_summary,
                "detailed_scores": {
                    "technical_accuracy": technical_avg,
                    "depth_of_understanding": depth_avg,
                    "practical_application": practical_avg,
                },
                "skills_breakdown": skills_assessment,
                "critical_gaps": critical_gaps,
                "recommendation_rationale": recommendation_rationale,
                "next_steps": next_steps,
            }

        # Original logic for when there are evaluations
        avg_score = sum(e["score"] for e in evaluations) / len(evaluations)
        technical_avg = sum(e.get("technical_accuracy", 0) for e in evaluations) / len(evaluations)
        depth_avg = sum(e.get("depth", 0) for e in evaluations) / len(evaluations)
        practical_avg = sum(e.get("practical_application", 0) for e in evaluations) / len(evaluations)

        hiring_decision = self._make_hiring_decision(avg_score, role, evaluations)
        skills_assessment = self._assess_critical_skills(evaluations)
        executive_summary = self._generate_executive_summary(avg_score, hiring_decision, skills_assessment)

        return {
            "overall_score": round(avg_score, 1),
            "hiring_decision": hiring_decision,
            "executive_summary": executive_summary,
            "detailed_scores": {
                "technical_accuracy": round(technical_avg, 1),
                "depth_of_understanding": round(depth_avg, 1),
                "practical_application": round(practical_avg, 1),
            },
            "skills_breakdown": skills_assessment,
            "critical_gaps": self._identify_critical_gaps(evaluations, role),
            "recommendation_rationale": self._get_recommendation_rationale(avg_score, hiring_decision),
            "next_steps": self._get_next_steps(hiring_decision),
        }

    def _make_hiring_decision(self, avg_score: float, role: str, evaluations: List[Dict]) -> Dict[str, Any]:
        threshold = self.hiring_thresholds.get(role, {}).get("minimum_score", 70)

        if avg_score >= 85:
            decision, confidence = "STRONG HIRE", "High"
        elif avg_score >= threshold:
            decision, confidence = "CONDITIONAL HIRE", "Medium"
        elif avg_score >= 50:
            decision, confidence = "NO HIRE - TRAINING REQUIRED", "High"
        else:
            decision, confidence = "REJECT", "High"

        critical_failures = sum(1 for e in evaluations if e["score"] < 30)
        if critical_failures > len(evaluations) // 2:
            decision, confidence = "REJECT", "High"

        return {"decision": decision, "confidence": confidence, "meets_threshold": avg_score >= threshold}

    def _assess_critical_skills(self, evaluations: List[Dict]) -> Dict[str, str]:
        skills = {s: "WEAK" for s in ["formula_knowledge", "data_manipulation", "analytical_thinking", "attention_to_detail"]}
        total_score = sum(e["score"] for e in evaluations) / len(evaluations)

        if total_score >= 80:
            for s in skills: skills[s] = "STRONG"
        elif total_score >= 60:
            for s in skills: skills[s] = "ADEQUATE"

        return skills

    def _identify_critical_gaps(self, evaluations: List[Dict], role: str) -> List[str]:
        gaps = []
        avg_score = sum(e["score"] for e in evaluations) / len(evaluations)

        if avg_score < 30:
            gaps.append("CRITICAL: Lacks basic Excel formula knowledge")
        if avg_score < 50:
            gaps.append("MAJOR: Cannot perform essential Excel functions")

        if len([e for e in evaluations if e["score"] < 40]) > 2:
            gaps.append("PATTERN: Consistent poor performance across multiple areas")

        if role == "finance" and avg_score < 70:
            gaps.append("FINANCE CRITICAL: Insufficient Excel skills for financial analysis")
        elif role == "data_analytics" and avg_score < 75:
            gaps.append("ANALYTICS CRITICAL: Cannot handle data analysis requirements")

        return gaps[:3]

    def _generate_executive_summary(self, avg_score: float, hiring_decision: Dict, skills: Dict) -> str:
        decision = hiring_decision["decision"]
        if decision == "STRONG HIRE":
            return f"**RECOMMEND FOR HIRE**: Strong Excel proficiency (Score: {avg_score:.0f}/100). Ready for immediate deployment."
        elif decision == "CONDITIONAL HIRE":
            return f"**CONDITIONAL HIRE**: Adequate Excel foundation (Score: {avg_score:.0f}/100) but requires training."
        elif decision == "NO HIRE - TRAINING REQUIRED":
            return f"**NOT RECOMMENDED**: Lacks essential Excel skills (Score: {avg_score:.0f}/100). Needs extensive training."
        else:
            return f"**REJECT**: Insufficient Excel knowledge (Score: {avg_score:.0f}/100). Not suitable even with training."

    def _get_recommendation_rationale(self, avg_score: float, hiring_decision: Dict) -> str:
        decision = hiring_decision["decision"]
        if decision == "STRONG HIRE":
            return "Consistently high performance across Excel areas. Ready to contribute."
        elif decision == "CONDITIONAL HIRE":
            return "Solid foundation with trainable gaps (2-4 weeks training)."
        elif decision == "NO HIRE - TRAINING REQUIRED":
            return "Major gaps requiring 6-8 weeks of training."
        else:
            return "Critical deficiencies. Training won’t be enough."

    def _get_next_steps(self, hiring_decision: Dict) -> List[str]:
        decision = hiring_decision["decision"]
        if decision == "STRONG HIRE":
            return ["Proceed with job offer", "Assign Excel-heavy tasks", "Consider mentoring role"]
        elif decision == "CONDITIONAL HIRE":
            return ["Hire with training plan", "Assign mentor", "Re-evaluate after 1 month"]
        elif decision == "NO HIRE - TRAINING REQUIRED":
            return ["Do not hire", "Recommend Excel fundamentals course", "Reconsider after certification"]
        else:
            return ["Reject application", "Do not consider for Excel roles", "Focus on other candidates"]

