import random
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from questions_agent import QuestionBankAgent, QuestionGeneratorAgent
from questions_storage import QuestionStorageAgent
from evaluator_and_Report_Generator import HybridEvaluator, InterviewReportGenerator

class InterviewOrchestrator:
    def __init__(self, api_key: str = None):
        """Initialize the interview orchestrator with all agents"""
        self.question_bank = QuestionBankAgent()
        self.question_generator = QuestionGeneratorAgent(self.question_bank)
        self.storage_agent = QuestionStorageAgent()
        self.evaluator = HybridEvaluator(api_key)
        self.report_generator = InterviewReportGenerator()
        
        # Interview state management
        self.current_interview = None
        self.interview_history = []
        
    def start_interview(self, 
                       role: str, 
                       candidate_info: Dict = None, 
                       question_count: int = 6) -> Dict[str, Any]:
        """Start a new interview session"""
        
        # Generate interview ID
        interview_id = self._generate_interview_id()
        
        # Get questions for the role
        questions = self._select_interview_questions(role, question_count)
        
        # If not enough questions are available after selection, fall back to all questions
        if len(questions) < question_count:
            all_questions = self.storage_agent.get_questions_by_criteria(role=role, count=question_count)
            # If all questions is still not enough, take all questions and supplement with generated questions
            if len(all_questions) < question_count:
                generated_questions = self.question_generator.generate_interview_questions(role=role, count=question_count - len(all_questions))
                all_questions.extend(generated_questions)
            questions = self._balance_question_selection(all_questions, question_count)

        # Initialize interview session
        self.current_interview = {
            'interview_id': interview_id,
            'role': role,
            'candidate_info': candidate_info or {},
            'questions': questions,
            'responses': [],
            'evaluations': [],
            'start_time': datetime.now().isoformat(),
            'current_question_index': 0,
            'status': 'in_progress',
            'has_asked_follow_up': False # Add state for follow-up question
        }
        
        # Store new generated questions if any
        for question in questions:
            if question.get('generated', False):
                self.storage_agent.store_question(question)
        
        return {
            'interview_id': interview_id,
            'total_questions': len(questions),
            'first_question': questions[0] if questions else None,
            'status': 'started'
        }
    
    def _select_interview_questions(self, role: str, count: int) -> List[Dict]:
        """Intelligently select questions for the interview"""
        
        # Try to get best questions from storage first
        stored_questions = self.storage_agent.get_best_questions(role, count)
        
        # If we don't have enough effective questions, generate new ones
        if len(stored_questions) < count:
            needed_count = count - len(stored_questions)
            generated_questions = self.question_generator.generate_interview_questions(
                role, needed_count
            )
            
            # Combine stored and generated questions
            all_questions = stored_questions + generated_questions
        else:
            all_questions = stored_questions[:count]
        
        # Ensure variety in question types and difficulties
        balanced_questions = self._balance_question_selection(all_questions, count)
        
        return balanced_questions
    
    def _balance_question_selection(self, questions: List[Dict], target_count: int) -> List[Dict]:
        """Ensure balanced selection across types and difficulties"""
        
        if len(questions) <= target_count:
            return questions
        
        # Group questions by difficulty
        difficulty_groups = {
            'basic': [q for q in questions if q.get('difficulty') == 'basic'],
            'intermediate': [q for q in questions if q.get('difficulty') == 'intermediate'],
            'advanced': [q for q in questions if q.get('difficulty') == 'advanced']
        }
        
        # Aim for balanced distribution
        target_distribution = {
            'basic': target_count // 3,
            'intermediate': target_count // 3, 
            'advanced': target_count // 3
        }
        
        # Distribute remaining if not even
        remaining = target_count % 3
        for difficulty in ['intermediate', 'basic', 'advanced']:
            if remaining > 0:
                target_distribution[difficulty] += 1
                remaining -= 1
        
        selected_questions = []
        
        # Select from each difficulty level
        for difficulty, target_num in target_distribution.items():
            available = difficulty_groups.get(difficulty, [])
            # Sort by effectiveness and take the best ones
            available.sort(key=lambda x: x.get('effectiveness_score', 0), reverse=True)
            selected_questions.extend(available[:target_num])
        
        # If we still need more questions, fill with remaining best questions
        if len(selected_questions) < target_count:
            remaining = [q for q in questions if q not in selected_questions]
            remaining.sort(key=lambda x: x.get('effectiveness_score', 0), reverse=True)
            selected_questions.extend(remaining[:target_count - len(selected_questions)])
        
        return selected_questions[:target_count]
    
    def get_current_question(self) -> Optional[Dict]:
        """Get the current question for the active interview"""
        if not self.current_interview:
            return None
        
        questions = self.current_interview['questions']
        current_index = self.current_interview['current_question_index']
        
        if current_index < len(questions):
            return questions[current_index]
        
        return None
    
    def submit_answer(self, response: str) -> Dict[str, Any]:
        """Process candidate's answer and move to next question"""
        if not self.current_interview:
            return {'error': 'No active interview session'}
        
        current_question = self.get_current_question()
        if not current_question:
            return {'error': 'No current question available'}
        
        # Evaluate the response
        evaluation = self.evaluator.evaluate_comprehensive(current_question, response)
        
        # Store response and evaluation
        self.current_interview['responses'].append({
            'question_id': current_question['id'],
            'response': response,
            'timestamp': datetime.now().isoformat()
        })
        
        self.current_interview['evaluations'].append(evaluation)
        
        # Update question performance in storage
        self.storage_agent.update_question_performance(
            current_question['id'],
            evaluation['score']
        )

        # Decide on next action
        return self._determine_next_action(evaluation)
    
    def _determine_next_action(self, evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """Determine next action based on evaluation score and interview state"""
        score = evaluation.get('score', 0)
        is_last_question = self.current_interview['current_question_index'] == len(self.current_interview['questions']) - 1

        # Check if we should ask a follow-up
        if score < 60 and not self.current_interview.get('has_asked_follow_up'):
            # Only ask a follow-up for the current question
            self.current_interview['has_asked_follow_up'] = True
            follow_up_question = self.question_generator.generate_follow_up_question(
                self.get_current_question(), evaluation
            )
            # We don't advance the question index here, we just return the follow-up
            return {
                'status': 'follow_up',
                'evaluation': evaluation,
                'follow_up_question': follow_up_question,
            }
        
        # Move to next question or complete interview
        self.current_interview['current_question_index'] += 1
        self.current_interview['has_asked_follow_up'] = False # Reset for the next main question
        
        if self.current_interview['current_question_index'] >= len(self.current_interview['questions']):
            return self._complete_interview()
        else:
            next_question = self.get_current_question()
            return {
                'status': 'continue',
                'evaluation': evaluation,
                'next_question': next_question,
                'progress': {
                    'current': self.current_interview['current_question_index'],
                    'total': len(self.current_interview['questions']),
                    'percentage': ((self.current_interview['current_question_index']) / len(self.current_interview['questions'])) * 100
                }
            }
    
    def _complete_interview(self) -> Dict[str, Any]:
        """Complete the interview and generate final report"""
        if not self.current_interview:
            return {'error': 'No active interview to complete'}
        
        # Mark interview as completed
        self.current_interview['status'] = 'completed'
        self.current_interview['end_time'] = datetime.now().isoformat()
        
        # Generate comprehensive report
        final_report = self.report_generator.generate_final_report(
            self.current_interview['evaluations'],
            self.current_interview['role']
        )
        
        # Store interview in history
        self.interview_history.append(self.current_interview.copy())
        
        # Clear current interview
        interview_data = self.current_interview
        self.current_interview = None
        
        return {
            'status': 'completed',
            'interview_id': interview_data['interview_id'],
            'final_report': final_report,
            'total_time': self._calculate_interview_duration(interview_data)
        }
    
    def _generate_interview_id(self) -> str:
        """Generate unique interview ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = random.randint(1000, 9999)
        return f"interview_{timestamp}_{random_suffix}"
    
    def _calculate_interview_duration(self, interview_data: Dict) -> Dict[str, Any]:
        """Calculate total interview duration"""
        if 'start_time' not in interview_data or 'end_time' not in interview_data:
            return {'error': 'Missing timestamp data'}
        
        try:
            start_time = datetime.fromisoformat(interview_data['start_time'])
            end_time = datetime.fromisoformat(interview_data['end_time'])
            duration = end_time - start_time
            
            return {
                'total_seconds': duration.total_seconds(),
                'total_minutes': round(duration.total_seconds() / 60, 1),
                'formatted': str(duration).split('.')[0]  # Remove microseconds
            }
        except Exception as e:
            return {'error': f'Error calculating duration: {str(e)}'}
    
    def get_interview_status(self) -> Dict[str, Any]:
        """Get current interview status"""
        if not self.current_interview:
            return {'status': 'no_active_interview'}
        
        return {
            'status': self.current_interview['status'],
            'interview_id': self.current_interview['interview_id'],
            'role': self.current_interview['role'],
            'progress': {
                'current_question': self.current_interview['current_question_index'] + 1,
                'total_questions': len(self.current_interview['questions']),
                'percentage': ((self.current_interview['current_question_index']) / len(self.current_interview['questions'])) * 100
            },
            'elapsed_time': self._get_elapsed_time()
        }
    
    def _get_elapsed_time(self) -> Dict[str, Any]:
        """Calculate elapsed time for current interview"""
        if not self.current_interview or 'start_time' not in self.current_interview:
            return {'error': 'No active interview or missing start time'}
        
        try:
            start_time = datetime.fromisoformat(self.current_interview['start_time'])
            current_time = datetime.now()
            elapsed = current_time - start_time
            
            return {
                'seconds': elapsed.total_seconds(),
                'minutes': round(elapsed.total_seconds() / 60, 1),
                'formatted': str(elapsed).split('.')[0]
            }
        except Exception as e:
            return {'error': f'Error calculating elapsed time: {str(e)}'}
    
    def pause_interview(self) -> Dict[str, Any]:
        """Pause the current interview"""
        if not self.current_interview:
            return {'error': 'No active interview to pause'}
        
        self.current_interview['status'] = 'paused'
        self.current_interview['pause_time'] = datetime.now().isoformat()
        
        return {'status': 'paused', 'message': 'Interview paused successfully'}
    
    def resume_interview(self) -> Dict[str, Any]:
        """Resume a paused interview"""
        if not self.current_interview:
            return {'error': 'No interview to resume'}
        
        if self.current_interview['status'] != 'paused':
            return {'error': 'Interview is not in paused state'}
        
        self.current_interview['status'] = 'in_progress'
        self.current_interview['resume_time'] = datetime.now().isoformat()
        
        current_question = self.get_current_question()
        return {
            'status': 'resumed',
            'current_question': current_question,
            'message': 'Interview resumed successfully'
        }
    
    def get_interview_history(self, limit: int = 10) -> List[Dict]:
        """Get recent interview history"""
        return self.interview_history[-limit:] if self.interview_history else []
    
    def get_system_analytics(self) -> Dict[str, Any]:
        """Get overall system analytics"""
        storage_analytics = self.storage_agent.get_analytics()
        
        return {
            'question_bank_stats': storage_analytics,
            'total_interviews_conducted': len(self.interview_history),
            'active_interview': self.current_interview is not None,
            'system_status': 'operational'
        }
