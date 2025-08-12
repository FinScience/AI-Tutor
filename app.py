import streamlit as st
import requests
import os
import re
from dotenv import load_dotenv

# -----------------
# CONFIG
# -----------------
# load_dotenv kept so local env fallback works if you want, but primary is st.secrets
load_dotenv()
API_KEY = st.secrets.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
MODEL = "openai/gpt-oss-20b:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

if not API_KEY:
    st.error("API key not found. Please set OPENROUTER_API_KEY in your Streamlit secrets or local environment.")
    st.stop()

# helper to call OpenRouter
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
        # bubble up a string error (UI will show it)
        return f"❌ Error contacting API: {e}"

# LLM-based answer checker
def check_answer_with_llm(question, student_answer):
    """
    Ask the LLM to evaluate the student's answer.
    The LLM is instructed to respond with a single first word: 'CORRECT' or 'INCORRECT',
    optionally followed by a short explanation.
    """
    prompt = (
        f"Question: {question}\n"
        f"Student Answer: {student_answer}\n\n"
        "Evaluate whether the student's answer is correct. "
        "Reply starting with a single word 'CORRECT' or 'INCORRECT' (caps or any case ok). "
        "Optionally add one short sentence of feedback after that word. "
        "Do NOT reveal the correct answer if the student's answer is incorrect."
    )
    resp = ask_openrouter(prompt)
    if isinstance(resp, str):
        first_line = resp.strip().splitlines()[0].strip().lower()
        if first_line.startswith("correct"):
            return True, resp
        else:
            return False, resp
    return False, str(resp)

# hint generator (live)
def generate_hint(question, answer_text):
    prompt = (
        f"Question: {question}\n"
        f"Correct answer (for your reference): {answer_text}\n\n"
        "Provide a short hint that nudges the student toward the answer but does NOT reveal it. "
        "Hint should be one or two short sentences."
    )
    return ask_openrouter(prompt)

# utility to clean numbered lines like "1. What is..." -> "What is..."
def strip_numbering(line):
    return re.sub(r'^\s*\d+\s*[\).\:-]?\s*', '', line).strip()

# -----------------
# STATE INIT (keep your original keys & flow)
# -----------------
if "page" not in st.session_state:
    st.session_state.page = "home"
if "lesson" not in st.session_state:
    st.session_state.lesson = ""
if "quiz" not in st.session_state:
    st.session_state.quiz = []  # list of dicts {"question":..., "answer":...}
if "current_q" not in st.session_state:
    st.session_state.current_q = 0
if "score" not in st.session_state:
    st.session_state.score = 0
# hints_used now a dict mapping q_index -> count (so each question gets its own counter)
if "hints_used" not in st.session_state:
    st.session_state.hints_used = {}
# difficulty stored separately (numeric grade 1..12), initial value derived from UI later
if "difficulty_grade" not in st.session_state:
    st.session_state.difficulty_grade = 6

# -----------------
# HOME PAGE (keep same look)
# -----------------
if st.session_state.page == "home":
    st.title("📚 AI Learning Assistant")

    # original UI: grade shown as "Grade X" — we keep that and also update numeric difficulty
    grade_option = st.selectbox("Select Grade", [f"Grade {i}" for i in range(1, 13)])
    subject = st.selectbox("Select Subject", ["Physics", "Chemistry", "Biology", "Mathematics"])
    concept = st.text_input("Enter the concept you want to study")

    # set numeric difficulty based on selected grade so tutorial generation uses it
    try:
        st.session_state.difficulty_grade = int(grade_option.split()[1])
    except Exception:
        st.session_state.difficulty_grade = 6

    if st.button("Generate Tutorial") and concept.strip():
        prompt = (
            f"Create a clear, structured, and engaging tutorial for Grade {st.session_state.difficulty_grade} "
            f"{subject} on the topic '{concept}'. Make it suitable for a student, use simple language, short paragraphs "
            "and bullet points if needed. Return text only."
        )
        with st.spinner("Generating tutorial..."):
            resp = ask_openrouter(prompt)
        st.session_state.lesson = resp
        # reset quiz-related state
        st.session_state.quiz = []
        st.session_state.current_q = 0
        st.session_state.score = 0
        st.session_state.hints_used = {}
        st.session_state.page = "tutorial"
        st.rerun()

# -----------------
# TUTORIAL PAGE (same look, with new difficulty controls + meter)
# -----------------
elif st.session_state.page == "tutorial":
    st.title("📖 Tutorial")
    st.write(st.session_state.lesson or "No tutorial yet.")

    # add difficulty controls and a visual meter (grades 1..12)
    col_left, col_mid, col_right = st.columns([1, 2, 1])

    with col_left:
        if st.button("⬅ Easier"):
            if st.session_state.difficulty_grade > 1:
                st.session_state.difficulty_grade -= 1
                # regenerate tutorial at easier grade
                with st.spinner("Regenerating easier tutorial..."):
                    prompt = (
                        f"Create a clear, structured tutorial for Grade {st.session_state.difficulty_grade} "
                        f"on the same topic. Make it simpler and more accessible for that grade."
                    )
                    st.session_state.lesson = ask_openrouter(prompt)
                    # reset quiz state
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
                        f"on the same topic. Make it slightly more advanced for that grade."
                    )
                    st.session_state.lesson = ask_openrouter(prompt)
                    st.session_state.quiz = []
                    st.session_state.current_q = 0
                    st.session_state.score = 0
                    st.session_state.hints_used = {}
                    st.rerun()

    # original two buttons kept with same labels and flow
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Understood, let's move to quiz"):
            # Generate questions and answers as before (two LLM calls)
            with st.spinner("Generating quiz questions..."):
                quiz_text = ask_openrouter(
                    f"Generate 10 quiz questions (only questions) for the topic based on the following tutorial:\n\n"
                    f"{st.session_state.lesson}\n\n"
                    "Provide them in numbered format without answers."
                )
            with st.spinner("Generating answers for the quiz..."):
                answers_text = ask_openrouter(
                    f"For the following quiz questions, provide the correct answers in the same numbered list:\n\n{quiz_text}"
                )

            # Parse questions & answers robustly
            q_lines = [line for line in quiz_text.splitlines() if line.strip()]
            a_lines = [line for line in answers_text.splitlines() if line.strip()]

            questions = [strip_numbering(l) for l in q_lines]
            answers = [strip_numbering(l) for l in a_lines]

            # if lengths don't match, try a simple fallback: pair by index
            length = min(len(questions), len(answers))
            quiz_data = []
            for i in range(length):
                quiz_data.append({
                    "question": questions[i],
                    "answer": answers[i]
                })

            # If model returned fewer than 10, try to pad with generic questions (rare)
            while len(quiz_data) < 10:
                quiz_data.append({
                    "question": f"Short question about {concept}",
                    "answer": ""
                })

            st.session_state.quiz = quiz_data[:10]
            st.session_state.current_q = 0
            st.session_state.score = 0
            st.session_state.hints_used = {}
            st.session_state.page = "quiz"
            st.rerun()

    with col2:
        if st.button("Give me a better tutorial"):
            with st.spinner("Regenerating tutorial in clearer style..."):
                new_tut = ask_openrouter(
                    f"Re-explain this topic in a simpler and clearer manner suitable for Grade {st.session_state.difficulty_grade}:\n\n"
                    f"{st.session_state.lesson}"
                )
                st.session_state.lesson = new_tut
                st.rerun()

# -----------------
# QUIZ PAGE (same look, now using LLM to evaluate answers and update score live)
# -----------------
elif st.session_state.page == "quiz":
    st.title("📝 Quiz Time")
    q_index = st.session_state.current_q

    # guard
    if not st.session_state.quiz:
        st.error("No quiz available. Go back to the tutorial and start the quiz.")
    else:
        total_q = len(st.session_state.quiz)

        # quiz complete
        if q_index >= total_q:
            st.success(f"✅ Quiz completed! Final Score: {st.session_state.score}/{total_q}")
            if st.button("Restart"):
                st.session_state.page = "home"
                st.rerun()
        else:
            q_data = st.session_state.quiz[q_index]
            st.subheader(f"Question {q_index+1}: {q_data['question']}")

            # Live score displayed
            st.info(f"Score: {st.session_state.score}/{total_q}")

            # show existing hint count for this question
            hints_for_q = st.session_state.hints_used.get(str(q_index), 0)

            # text input keyed per question so it persists when rerun
            answer = st.text_input("Your answer:", key=f"answer_{q_index}")

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("Submit", key=f"submit_{q_index}"):
                    if not answer.strip():
                        st.warning("Please provide an answer before submitting.")
                    else:
                        # Use LLM to check the student's answer rather than direct string compare
                        with st.spinner("Checking answer..."):
                            is_correct, feedback = check_answer_with_llm(q_data["question"], answer)
                        if is_correct:
                            st.success("✅ Correct!")
                            st.session_state.score += 1
                        else:
                            st.error("❌ Incorrect!")
                            # show short feedback from the LLM if available
                            # (we avoid printing the full correct answer to preserve learning)
                            lines = feedback.strip().splitlines()
                            if len(lines) > 1:
                                st.write("Feedback:", "\n".join(lines[1:]).strip())
                        # after evaluating, move to next question
                        st.session_state.current_q += 1
                        # reset hint count for next question handled by hints_used map
                        st.rerun()

            with col2:
                if st.button("Hint", key=f"hint_{q_index}"):
                    if hints_for_q >= 3:
                        st.warning("⚠️ No more hints allowed for this question.")
                    else:
                        # generate hint using LLM (live)
                        correct_answer_text = q_data.get("answer", "")
                        with st.spinner("Generating hint..."):
                            hint_text = generate_hint(q_data["question"], correct_answer_text)
                        # increment hint count
                        st.session_state.hints_used[str(q_index)] = hints_for_q + 1
                        st.info(f"💡 Hint {st.session_state.hints_used[str(q_index)]}: {hint_text}")

            with col3:
                st.write(f"Hints used: {hints_for_q}/3")
                st.write(f"Score: {st.session_state.score}/{total_q}")

