import streamlit as st
import requests
import os
import re
from dotenv import load_dotenv

# -----------------
# CONFIG & KEYS
# -----------------
load_dotenv()
API_KEY = st.secrets.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
MODEL = "openai/gpt-oss-20b:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

if not API_KEY:
    st.error("API key not found. Please set OPENROUTER_API_KEY in Streamlit secrets or environment.")
    st.stop()

# -----------------
# UTILITIES
# -----------------
def ask_openrouter(prompt, timeout=60):
    """Send a prompt to the OpenRouter API and return the model's text reply."""
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

def strip_numbering(line):
    return re.sub(r'^\s*\d+\s*[\).\:-]?\s*', '', line).strip()

# -----------------
# STRICT LLM HELPERS
# -----------------
def check_answer_with_llm(question, student_answer):
    prompt = (
        "You are an examiner. Determine if the student's answer is correct "
        "STRICTLY based on the tutorial below. Ignore outside knowledge. "
        "Reply with a single word 'CORRECT' or 'INCORRECT' at the start, "
        "followed by one short sentence of feedback. Do NOT reveal the correct answer.\n\n"
        "=== TUTORIAL START ===\n"
        f"{st.session_state.lesson}\n"
        "=== TUTORIAL END ===\n\n"
        f"Question: {question}\n"
        f"Student Answer: {student_answer}\n"
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
        "You are a helpful tutor. Provide a short hint that nudges the student toward the answer "
        "without revealing it. Use ONLY the information in the tutorial. "
        "Do not add new facts.\n\n"
        "=== TUTORIAL START ===\n"
        f"{st.session_state.lesson}\n"
        "=== TUTORIAL END ===\n\n"
        f"Question: {question}\n"
        f"(For your reference only) Answer: {answer_text}\n"
        "Hint:"
    )
    return ask_openrouter(prompt)

# -----------------
# SESSION STATE INIT
# -----------------
defaults = {
    "page": "home",
    "lesson": "",
    "subject": "",
    "concept": "",
    "quiz": [],
    "current_q": 0,
    "score": 0,
    "hints_used": {},
    "difficulty_grade": 6,
    "quiz_feedback": None,
    "last_tutorial_signature": None
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# -----------------
# TUTORIAL SYNC (ROBUST AUTO REGENERATION)
# -----------------
def ensure_tutorial_uptodate():
    sig = (st.session_state.subject, st.session_state.concept, st.session_state.difficulty_grade)
    if st.session_state.get("last_tutorial_signature") != sig and st.session_state.subject and st.session_state.concept:
        with st.spinner("Updating tutorial for the new settings..."):
            st.session_state.lesson = ask_openrouter(
                f"You are an expert {st.session_state.subject} teacher for Grade {st.session_state.difficulty_grade}."
                f" Create a clear, structured tutorial for the topic '{st.session_state.concept}'."
                f" The tutorial must be entirely self-contained and sufficient for answering basic conceptual questions."
                f" Include short sections with headings, key definitions, examples, and a brief summary."
                f" Keep language age-appropriate for Grade {st.session_state.difficulty_grade} in India."
            )
        st.session_state.last_tutorial_signature = sig
        st.session_state.quiz = []
        st.session_state.current_q = 0
        st.session_state.score = 0
        st.session_state.hints_used = {}

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
    except:
        st.session_state.difficulty_grade = 6

    if st.button("Generate Tutorial") and concept.strip():
        st.session_state.subject = subject
        st.session_state.concept = concept.strip()
        st.session_state.page = "tutorial"
        st.rerun()

# -----------------
# TUTORIAL PAGE
# -----------------
elif st.session_state.page == "tutorial":
    ensure_tutorial_uptodate()

    st.title("📖 Tutorial")
    st.write(st.session_state.lesson or "No tutorial yet.")

    col_left, col_mid, col_right = st.columns([1, 2, 1])
    with col_left:
        if st.button("⬅ Easier"):
            if st.session_state.difficulty_grade > 1:
                st.session_state.difficulty_grade -= 1
                st.rerun()
    with col_mid:
        st.markdown(f"**Difficulty (grade): Grade {st.session_state.difficulty_grade}**")
        st.progress(st.session_state.difficulty_grade / 12)
    with col_right:
        if st.button("Harder ➡"):
            if st.session_state.difficulty_grade < 12:
                st.session_state.difficulty_grade += 1
                st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Understood, let's move to quiz"):
            with st.spinner("Generating quiz questions..."):
                quiz_text = ask_openrouter(
                    "You are a careful examiner. Generate exactly 10 quiz questions ONLY (no answers in this step). "
                    "CRITICAL RULES: Questions must be answerable directly and exclusively from the tutorial below; "
                    "do not use outside knowledge; do not invent facts. "
                    f"Context: Subject={st.session_state.subject}, Grade={st.session_state.difficulty_grade}, "
                    f"Topic='{st.session_state.concept}'. "
                    "Write each question on a new line without numbering.\n\n"
                    "=== TUTORIAL START ===\n"
                    f"{st.session_state.lesson}\n"
                    "=== TUTORIAL END ==="
                )

            with st.spinner("Generating answers for the quiz..."):
                answers_text = ask_openrouter(
                    "Provide concise, correct answers to the following quiz questions. "
                    "CRITICAL RULES: Answers must be found verbatim or paraphrased from the tutorial below; "
                    "do not use outside knowledge; if an answer cannot be derived strictly from the tutorial, reply with 'INSUFFICIENT'. "
                    f"Context: Subject={st.session_state.subject}, Grade={st.session_state.difficulty_grade}, "
                    f"Topic='{st.session_state.concept}'. "
                    "One short answer per line, aligned with the questions order.\n\n"
                    "=== TUTORIAL START ===\n"
                    f"{st.session_state.lesson}\n"
                    "=== TUTORIAL END ===\n\n"
                    "=== QUESTIONS START ===\n"
                    f"{quiz_text}\n"
                    "=== QUESTIONS END ==="
                )

            q_lines = [strip_numbering(l) for l in quiz_text.splitlines() if l.strip()]
            a_lines = [strip_numbering(l) for l in answers_text.splitlines() if l.strip()]
            pairs = list(zip(q_lines, a_lines))
            filtered = [{"question": q, "answer": a} for q, a in pairs if a.lower().strip() != "insufficient"]

            st.session_state.quiz = filtered[:10]
            st.session_state.current_q = 0
            st.session_state.score = 0
            st.session_state.hints_used = {}
            st.session_state.page = "quiz"
            st.session_state.quiz_feedback = None
            st.rerun()

    with col2:
        if st.button("Give me a better tutorial"):
            st.session_state.last_tutorial_signature = None
            st.rerun()

# -----------------
# QUIZ PAGE
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
