import streamlit as st
import requests
import os
from dotenv import load_dotenv

# -----------------
# CONFIG
# -----------------
load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "openai/gpt-oss-20b:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

if not API_KEY:
    st.error("API key not found. Please set OPENROUTER_API_KEY in your .env file.")
    st.stop()


def ask_openrouter(prompt):
    """Send a prompt to the OpenRouter API and return the model's reply."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        resp = requests.post(API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ Error contacting API: {e}"


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
    st.session_state.hints_used = 0


# -----------------
# HOME PAGE
# -----------------
if st.session_state.page == "home":
    st.title("📚 AI Learning Assistant")

    grade = st.selectbox("Select Grade", [f"Grade {i}" for i in range(1, 13)])
    subject = st.selectbox("Select Subject", ["Physics", "Chemistry", "Biology", "Mathematics"])
    concept = st.text_input("Enter the concept you want to study")

    if st.button("Generate Tutorial") and concept.strip():
        st.session_state.lesson = ask_openrouter(
            f"Create a clear, structured, and engaging tutorial for {grade} {subject} on '{concept}'. "
            "Make it suitable for a student, use simple language and bullet points if needed."
        )
        st.session_state.page = "tutorial"
        st.rerun()


# -----------------
# TUTORIAL PAGE
# -----------------
elif st.session_state.page == "tutorial":
    st.title("📖 Tutorial")
    st.write(st.session_state.lesson)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Understood, let's move to quiz"):
            quiz_text = ask_openrouter(
                f"Generate 10 quiz questions (only questions) for the topic based on the following tutorial:\n\n"
                f"{st.session_state.lesson}\n\n"
                "Provide them in numbered format without answers."
            )
            answers_text = ask_openrouter(
                f"For the following quiz questions, provide the correct answers in the same numbered list:\n\n{quiz_text}"
            )

            questions = quiz_text.strip().split("\n")
            answers = answers_text.strip().split("\n")
            quiz_data = []
            for q, a in zip(questions, answers):
                quiz_data.append({
                    "question": q.strip(),
                    "answer": a.strip().split(". ", 1)[-1]
                })

            st.session_state.quiz = quiz_data
            st.session_state.current_q = 0
            st.session_state.score = 0
            st.session_state.hints_used = 0
            st.session_state.page = "quiz"
            st.rerun()

    with col2:
        if st.button("Give me a better tutorial"):
            st.session_state.lesson = ask_openrouter(
                f"Re-explain this topic in a simpler and easier manner:\n\n{st.session_state.lesson}"
            )
            st.rerun()


# -----------------
# QUIZ PAGE
# -----------------
elif st.session_state.page == "quiz":
    st.title("📝 Quiz Time")
    q_index = st.session_state.current_q

    if q_index >= len(st.session_state.quiz):
        st.success(f"✅ Quiz completed! Final Score: {st.session_state.score}/{len(st.session_state.quiz)}")
        if st.button("Restart"):
            st.session_state.page = "home"
            st.rerun()
    else:
        q_data = st.session_state.quiz[q_index]
        st.subheader(f"Question {q_index+1}: {q_data['question']}")

        answer = st.text_input("Your answer:")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Submit"):
                correct_answer = q_data["answer"].strip().lower()
                if answer.strip().lower() == correct_answer:
                    st.success("✅ Correct!")
                    st.session_state.score += 1
                else:
                    st.error(f"❌ Incorrect! Correct answer: {q_data['answer']}")
                st.session_state.current_q += 1
                st.session_state.hints_used = 0
                st.rerun()

        with col2:
            if st.button("Hint"):
                if st.session_state.hints_used < 3:
                    hint = ask_openrouter(
                        f"Provide a helpful hint for the following quiz question without giving the full answer:\n\n"
                        f"{q_data['question']}\n\n"
                        f"Correct answer: {q_data['answer']}"
                    )
                    st.info(f"💡 Hint {st.session_state.hints_used+1}: {hint}")
                    st.session_state.hints_used += 1
                else:
                    st.warning("⚠️ No more hints allowed for this question.")

        with col3:
            st.write(f"Score: {st.session_state.score}")

