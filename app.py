import streamlit as st
import json
from evaluator_and_Report_Generator import HybridEvaluator, InterviewReportGenerator
from questions_storage import QuestionStorageAgent
from questions_agent import QuestionBankAgent, QuestionGeneratorAgent
import time
from interview_orchestrator import InterviewOrchestrator

st.set_page_config(
    page_title="Excel Mock Interviewer",
    page_icon="📊"
)

# Initialize session state first
if 'evaluations' not in st.session_state:
    st.session_state.evaluations = []
if 'current_question_index' not in st.session_state:
    st.session_state.current_question_index = 0
if 'interview_started' not in st.session_state:
    st.session_state.interview_started = False
if 'selected_questions' not in st.session_state:
    st.session_state.selected_questions = None
if 'question_manager' not in st.session_state:
    st.session_state.question_manager = None
if 'orchestrator' not in st.session_state:
    st.session_state.orchestrator = InterviewOrchestrator(api_key=st.secrets.get("GEMINI_API_KEY"))
if 'last_evaluation' not in st.session_state:
    st.session_state.last_evaluation = None
if 'name' not in st.session_state:
    st.session_state.name = ""
if 'show_intro' not in st.session_state:
    st.session_state.show_intro = True


def start_interview_session(name: str, role: str):
    """Initializes the interview and sets the session state."""
    st.session_state.name = name
    st.session_state.selected_role = role
    
    interview_data = st.session_state.orchestrator.start_interview(
        role=role,
        candidate_info={"name": name}
    )
    
    # Store the interview data in session state
    st.session_state.interview_started = True
    st.session_state.current_question = interview_data['first_question']
    st.session_state.current_question_index = 0
    st.session_state.show_intro = False
    
    st.rerun()

def submit_user_response(response: str):
    """Handles the user's answer submission."""
    if st.session_state.current_question:
        # Use the orchestrator's submit_answer method
        result = st.session_state.orchestrator.submit_answer(response)

        # Update the session state based on the result
        st.session_state.last_evaluation = result.get('evaluation')

        if result['status'] == 'completed':
            st.session_state.interview_completed = True
            st.session_state.final_report = result['final_report']
        elif result['status'] == 'follow_up':
            st.session_state.current_question = result['follow_up_question']
        elif result['status'] == 'continue':
            st.session_state.current_question_index = result['progress']['current']
            st.session_state.current_question = result['next_question']

        st.rerun()

def main():
    st.title("🤖 AI Excel Mock Interviewer")
    
    if st.session_state.show_intro:
        st.write("### Welcome to the AI Excel Mock Interviewer!")
        st.write("This interview will assess your Excel skills across different areas.")
        st.write("Please provide your full name and select your target role to start.")
        
        with st.form(key='intro_form'):
            name = st.text_input("Your Full Name:")
            role = st.selectbox("Select your target role:", ["finance", "operations", "data_analytics"])
            submit_button = st.form_submit_button("Start Interview")
            
            if submit_button:
                if name.strip():
                    start_interview_session(name, role)
                else:
                    st.error("Please enter your name to begin.")
    
    elif st.session_state.get('interview_completed', False):
        st.write("## 📊 Interview Assessment Complete")

        report = st.session_state.final_report
        
        # Check if a valid report was generated
        if 'hiring_decision' in report:
            # Executive Decision Box
            decision = report['hiring_decision']['decision']
            
            if decision == "STRONG HIRE":
                st.success(f"**{decision}** - Score: {report['overall_score']}/100")
            elif decision == "CONDITIONAL HIRE":
                st.warning(f"**{decision}** - Score: {report['overall_score']}/100")
            else:
                st.error(f"**{decision}** - Score: {report['overall_score']}/100")

            # Executive Summary
            st.write("### Executive Summary")
            st.write(report['executive_summary'])

            # Quick Metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Technical Skills", f"{report['detailed_scores']['technical_accuracy']}/100")
            with col2:
                st.metric("Depth of Knowledge", f"{report['detailed_scores']['depth_of_understanding']}/100")
            with col3:
                st.metric("Practical Application", f"{report['detailed_scores']['practical_application']}/100")

            # Critical Issues (if any)
            if report.get('critical_gaps'):
                st.write("### ⚠️ Critical Issues")
                for gap in report['critical_gaps']:
                    st.write(f"• {gap}")

            # Hiring Decision Rationale
            st.write("### Decision Rationale")
            st.write(report['recommendation_rationale'])

            # Next Steps
            st.write("### Recommended Next Steps")
            for step in report['next_steps']:
                st.write(f"✓ {step}")
        else:
            st.error("There was an issue generating the final report. Please try the interview again.")
            
        if st.button("Start New Interview"):
            st.session_state.clear()
            st.rerun()

    else:
        # Interview in progress
        questions = st.session_state.orchestrator.current_interview['questions']
        current_question = st.session_state.current_question
        current_index = st.session_state.current_question_index

        if current_question:
            # Show progress
            progress = (current_index) / len(questions)
            st.progress(progress)
            
            # Show current question
            st.write(f"**Question {current_index + 1} of {len(questions)}**")
            st.write(f"**{current_question['question']}**")
            
            # Show evaluation of the last question, if available
            if st.session_state.last_evaluation:
                with st.expander("Show AI Evaluation for Previous Answer"):
                    st.write(f"**Score:** {st.session_state.last_evaluation['score']}/100")
                    st.write(f"**Overall Feedback:** {st.session_state.last_evaluation['overall_feedback']}")
                    st.write("**Strengths:**")
                    for s in st.session_state.last_evaluation['strengths']:
                        st.write(f"- {s}")
                    st.write("**Areas for Improvement:**")
                    for i in st.session_state.last_evaluation['improvements']:
                        st.write(f"- {i}")

            # Text area for response
            response = st.text_area(
                "Your answer:", 
                key=f"q_{current_index}",
                height=150,
                placeholder="Please provide your detailed answer here..."
            )
            
            # Submit button
            if st.button("Submit Answer", type="primary"):
                if response.strip():
                    submit_user_response(response)
                else:
                    st.error("Please provide an answer before submitting.")
        else:
            # This handles the immediate transition from the intro form
            # to the first question without requiring a second click.
            # The orchestrator is already initialized.
            interview_data = st.session_state.orchestrator.start_interview(
                role=st.session_state.selected_role,
                candidate_info={"name": st.session_state.name}
            )
            st.session_state.current_question = interview_data['first_question']
            st.session_state.current_question_index = 0
            st.rerun()

if __name__ == "__main__":
    main()
