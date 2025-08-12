import streamlit as st
import requests
import os
import re
from dotenv import load_dotenv

# -----------------
# CONFIG
# -----------------
load_dotenv()
API_KEY = st.secrets.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
MODEL = "openai/gpt-oss-20b:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

if not API_KEY:
    st.error("API key not found. Please set OPENROUTER_API_KEY in your Streamlit secrets or local environment.")
    st.stop()

def ask_openrouter(prompt, timeout=30):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ Error contacting API: {e}"

def check_answer_with_llm(question, student_answer):
    prompt = (
        f"Question: {question}\n"
        f"Student Answer: {student_answer}\n\n"
        "Evaluate whether the student's answer is correct. "
        "Reply starting with a single word 'CORRECT' or 'INCORRECT'. "
        "Optionally add one short sentence of feedback after that word. "
        "Do NOT reveal the correct answer."
    )
    resp = ask_openrouter(prompt)
    if isinstance(resp, str):
        first_line = resp.strip().splitlines()[0].strip().lower()
        if first_line.startswith("correct"):
            return True, resp
        else:
            return False, resp
    return False, str(resp)

def generate_hint(question, answer_text):
    prompt = (
        f"Question: {question}\n"
        f"Correct answer (for your reference): {answer_text}\n\n"
        "Provide a short hint that nudges the student toward the answer but does NOT reveal it."
    )
    return ask_openrouter(prompt)

def strip_numbering(line):
    return re.sub(r'^\s*\d+\s*[\).\:-]?\s*', '', line).strip()

# -----------------
# STATE INIT
# -----------------
if "page" not in st.session_state:
    st.session_state.page = "home"
if "lesson" not in st.session_state:
    st.session_state.lesson = ""
if "quiz" not in st.session_state:
    st.session_state.quiz = []
if "current_q" not in st.session_state:
    st.session_state.current_q = 0
if "score" not in st.session_state:
    st.session_state.score = 0
if "hints_used" not in st.session_state:
    st.session_state.hints_used = {}
if "difficulty_grade" not in st.session_state:
    st.session_state.difficulty_grade = 6
if "quiz_feedback" not in st.session_state:
    st.session_state.quiz_feedback = None  # stores tuple (is_correct, feedback)

# -----------------
# HOME PAGE
# -----------------
if st.session_state.page == "home":
    st.title("📚 AI Learning Assistant")
    grade_option = st.selectbox("Select Grade", [f"Grade {i}" for i in range(1, 13)])
    subject = st.selectbox("Select Subject", ["Physics", "Chemistry", "Biology", "Mathematics"])
    concept = st.text_input("Enter the concept you want to study")

    try:
        st.session_state.difficulty_grade = int(grade_option.split()[1])
    except Exception:
        st.session_state.difficulty_grade = 6

    if st.button("Generate Tutorial") and concept.strip():
        prompt = (
            f"Create a clear, structured, and engaging tutorial for Grade {st.session_state.difficulty_grade} "
            f"{subject} on the topic '{concept}'. Make it suitable for a student."
        )
        with st.spinner("Generating tutorial..."):
            resp = ask_openrouter(prompt)
        st.session_state.lesson = resp
        st.session_state.quiz = []
        st.session_state.current_q = 0
        st.session_state.score = 0
        st.session_state.hints_used = {}
        st.session_state.page = "tutorial"
        st.rerun()

# -----------------
# TUTORIAL PAGE
# -----------------
elif st.session_state.page == "tutorial":
    st.title("📖 Tutorial")
    st.write(st.session_state.lesson or "No tutorial yet.")

    col_left, col_mid, col_right = st.columns([1, 2, 1])
    with col_left:
        if st.button("⬅ Easier"):
            if st.session_state.difficulty_grade > 1:
                st.session_state.difficulty_grade -= 1
                with st.spinner("Regenerating easier tutorial..."):
                    prompt = (
                        f"Create a clear, structured tutorial for Grade {st.session_state.difficulty_grade} "
                        f"on the same topic."
                    )
                    st.session_state.lesson = ask_openrouter(prompt)
                    st.session_state.quiz = []
                    st.session_state.current_q = 0
                    st.session_state.score = 0
                    st.session_state.hints_used = {}
                    st.rerun()

    with col_mid:
        st.markdown(f"**Difficulty (grade): Grade {st.session_state.difficulty_grade}**")
        st.progress(st.session_state.difficulty_grade / 12)

    with col_right:
        if st.button("Harder ➡"):
            if st.session_state.difficulty_grade < 12:
                st.session_state.difficulty_grade += 1
                with st.spinner("Regenerating harder tutorial..."):
                    prompt = (
                        f"Create a clear, structured tutorial for Grade {st.session_state.difficulty_grade} "
                        f"on the same topic."
                    )
                    st.session_state.lesson = ask_openrouter(prompt)
                    st.session_state.quiz = []
                    st.session_state.current_q = 0
                    st.session_state.score = 0
                    st.session_state.hints_used = {}
                    st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Understood, let's move to quiz"):
            concept = "the topic"  # safe fallback if needed
            with st.spinner("Generating quiz questions..."):
                quiz_text = ask_openrouter(
                    f"Generate 10 quiz questions (only questions) based on the following tutorial:\n\n"
                    f"{st.session_state.lesson}"
                )
            with st.spinner("Generating answers for the quiz..."):
                answers_text = ask_openrouter(
                    f"For the following quiz questions, provide the correct answers:\n\n{quiz_text}"
                )
            q_lines = [line for line in quiz_text.splitlines() if line.strip()]
            a_lines = [line for line in answers_text.splitlines() if line.strip()]
            questions = [strip_numbering(l) for l in q_lines]
            answers = [strip_numbering(l) for l in a_lines]
            length = min(len(questions), len(answers))
            quiz_data = [{"question": questions[i], "answer": answers[i]} for i in range(length)]
            while len(quiz_data) < 10:
                quiz_data.append({"question": f"Short question about {concept}", "answer": ""})
            st.session_state.quiz = quiz_data[:10]
            st.session_state.current_q = 0
            st.session_state.score = 0
            st.session_state.hints_used = {}
            st.session_state.page = "quiz"
            st.session_state.quiz_feedback = None
            st.rerun()

    with col2:
        if st.button("Give me a better tutorial"):
            with st.spinner("Regenerating tutorial..."):
                new_tut = ask_openrouter(
                    f"Re-explain this topic in a simpler and clearer manner suitable for Grade {st.session_state.difficulty_grade}:\n\n"
                    f"{st.session_state.lesson}"
                )
                st.session_state.lesson = new_tut
                st.rerun()

# -----------------
# QUIZ PAGE (pause on wrong answer)
# -----------------
elif st.session_state.page == "quiz":
    st.title("📝 Quiz Time")
    q_index = st.session_state.current_q

    if not st.session_state.quiz:
        st.error("No quiz available. Go back to the tutorial.")
    else:
        total_q = len(st.session_state.quiz)
        if q_index >= total_q:
            st.success(f"✅ Quiz completed! Final Score: {st.session_state.score}/{total_q}")
            if st.button("Restart"):
                st.session_state.page = "home"
                st.rerun()
        else:
            q_data = st.session_state.quiz[q_index]
            st.subheader(f"Question {q_index+1}: {q_data['question']}")
            st.info(f"Score: {st.session_state.score}/{total_q}")
            hints_for_q = st.session_state.hints_used.get(str(q_index), 0)

            if st.session_state.quiz_feedback is None:
                answer = st.text_input("Your answer:", key=f"answer_{q_index}")
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("Submit", key=f"submit_{q_index}"):
                        if not answer.strip():
                            st.warning("Please provide an answer before submitting.")
                        else:
                            with st.spinner("Checking answer..."):
                                is_correct, feedback = check_answer_with_llm(q_data["question"], answer)
                            st.session_state.quiz_feedback = (is_correct, feedback)
                            if is_correct:
                                st.session_state.score += 1
                            st.rerun()
                with col2:
                    if st.button("Hint", key=f"hint_{q_index}"):
                        if hints_for_q >= 3:
                            st.warning("⚠️ No more hints allowed for this question.")
                        else:
                            with st.spinner("Generating hint..."):
                                hint_text = generate_hint(q_data["question"], q_data.get("answer", ""))
                            st.session_state.hints_used[str(q_index)] = hints_for_q + 1
                            st.info(f"💡 Hint {st.session_state.hints_used[str(q_index)]}: {hint_text}")
                with col3:
                    st.write(f"Hints used: {hints_for_q}/3")
            else:
                is_correct, feedback = st.session_state.quiz_feedback
                if is_correct:
                    st.success("✅ Correct!")
                else:
                    st.error("❌ Incorrect!")
                lines = feedback.strip().splitlines()
                if len(lines) > 1:
                    st.write("Feedback:", "\n".join(lines[1:]).strip())

                if st.button("Next Question ➡"):
                    st.session_state.current_q += 1
                    st.session_state.quiz_feedback = None
                    st.rerun()
