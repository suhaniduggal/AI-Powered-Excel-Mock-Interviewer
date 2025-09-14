import json
import random
import re
from typing import List, Dict, Any
from datetime import datetime

class QuestionBankAgent:
    """Manages a predefined bank of question templates and categories."""
    def __init__(self):
        self.question_categories = {
            "basic_formulas": ["SUM", "AVERAGE", "COUNT", "MAX", "MIN"],
            "lookup_functions": ["VLOOKUP", "HLOOKUP", "INDEX", "MATCH"],
            "data_analysis": ["PIVOT", "FILTER", "SORT", "SUBTOTAL"],
            "advanced_formulas": ["IF", "SUMIF", "COUNTIF", "NESTED"],
            "data_manipulation": ["CONCATENATE", "TEXT", "DATE", "TIME"],
            "scenario_based": ["DASHBOARD", "REPORTING", "ANALYSIS"]
        }
        
        self.role_focus = {
            "finance": ["basic_formulas", "lookup_functions", "scenario_based"],
            "operations": ["data_analysis", "data_manipulation", "scenario_based"],
            "data_analytics": ["advanced_formulas", "data_analysis", "lookup_functions"]
        }
        
        self.initialize_base_questions()
    
    def initialize_base_questions(self):
        """Create foundational question templates."""
        self.base_questions = [
            {
                "template": "What function would you use to {action} in Excel?",
                "variations": {
                    "action": ["sum values in a range", "find the average", "count non-empty cells"]
                },
                "category": "basic_formulas",
                "difficulty": "basic"
            },
            {
                "template": "How would you {task} in a large dataset?",
                "variations": {
                    "task": ["remove duplicates", "find unique values", "filter specific criteria"]
                },
                "category": "data_analysis",
                "difficulty": "intermediate"
            },
            {
                "template": "Explain the difference between {concept1} and {concept2}.",
                "variations": {
                    "concept1": ["VLOOKUP", "absolute references", "SUMIF"],
                    "concept2": ["INDEX-MATCH", "relative references", "SUMIFS"]
                },
                "category": "advanced_formulas",
                "difficulty": "advanced"
            }
        ]

    def _fill_template(self, template: Dict) -> str:
        """Fills a question template with a random variation."""
        question_text = template['template']
        for key, values in template['variations'].items():
            question_text = question_text.replace(f"{{{key}}}", random.choice(values))
        return question_text

    def _extract_keywords(self, question_text: str) -> List[str]:
        """Extracts keywords from a generated question."""
        return re.findall(r'\b\w+\b', question_text.lower())

class QuestionGeneratorAgent:
    """Generates new questions based on role, difficulty, and templates."""
    def __init__(self, question_bank: QuestionBankAgent):
        self.question_bank = question_bank
        self.used_questions = set()
    
    def generate_interview_questions(self, role: str, count: int = 6) -> List[Dict]:
        """Generate personalized questions for a specific role."""
        questions = []
        categories = self.question_bank.role_focus.get(role, ["basic_formulas"])
        
        # Ensure a balanced difficulty progression
        difficulty_distribution = {
            "basic": count // 3 + (1 if count % 3 > 0 else 0),
            "intermediate": count // 3 + (1 if count % 3 > 1 else 0), 
            "advanced": count // 3
        }
        
        for difficulty, num_questions in difficulty_distribution.items():
            for _ in range(num_questions):
                question = self._use_template_question(categories, difficulty)
                if question:
                    questions.append(question)
        
        return questions
    
    def _use_template_question(self, categories: List[str], difficulty: str) -> Dict:
        """Generate question from a template."""
        suitable_templates = [
            t for t in self.question_bank.base_questions 
            if t['category'] in categories and t['difficulty'] == difficulty
        ]
        
        if not suitable_templates:
            return None
        
        template = random.choice(suitable_templates)
        # Corrected line: Call the method from the question_bank object
        question_text = self.question_bank._fill_template(template)
        
        return {
            "id": hash(question_text) % 10000,
            "question": question_text,
            "type": "formula" if "function" in question_text.lower() else "concept",
            "category": template['category'],
            "difficulty": difficulty,
            "keywords": self.question_bank._extract_keywords(question_text),
            "generated": True,
            "created_date": datetime.now().isoformat(),
            "target_roles": self._determine_roles_from_category(template['category'])
        }
    
    def _determine_roles_from_category(self, category: str) -> List[str]:
        """Determines target roles for a given question category."""
        roles = []
        for role, categories in self.question_bank.role_focus.items():
            if category in categories:
                roles.append(role)
        return roles
