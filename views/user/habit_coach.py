"""

AI Habit Tracker SaaS
AI Habit Coach Page — Production Quality

"""
from typing import List, Dict, Any

import streamlit as st
from database import get_db
from auth import auth
import utils
import ui_components


def init_session_state() -> None:
    if "coach_messages" not in st.session_state:
        st.session_state.coach_messages = [
            {
                "role": "assistant",
                "content": f"Hello {utils.get_display_name()}! 👋 I am your AI Habit Coach. I've analyzed your progress, streaks, and reflections. How can I help you build better habits today?"
            }
        ]


@st.cache_data(show_spinner=False, ttl=600)
def fetch_active_habits(user_id: str) -> List[Dict[str, Any]]:
    db = get_db()
    try:
        response = db.table("habits").select("title, frequency, target_count").eq("user_id", user_id).eq("is_active", True).execute()
        return response.data or []
    except Exception:
        return []


@st.cache_data(show_spinner=False, ttl=300)
def build_user_context(user_id: str) -> str:
    stats = utils.get_dashboard_statistics()
    active_habits = fetch_active_habits(user_id)
    journals = utils.get_recent_journal_entries(limit=3)
    achievements = utils.get_user_achievements(limit=3)

    context = [
        "--- USER DATA CONTEXT ---",
        f"Name: {utils.get_display_name()}",
        f"Current Streak: {stats['current_streak']} days",
        f"Longest Streak: {stats['longest_streak']} days",
        f"Today's Completion Rate: {stats['completion_percentage']}%",
        f"Total Habits: {stats['total_habits']}",
        f"Completed Today: {stats['completed_today']}",
        f"Failed Today: {stats['failed_today']}",
        f"Skipped Today: {stats['skipped_today']}",
        f"Total Earned Achievements: {stats['achievements']}",
        "\nActive Habits List:"
    ]
    if active_habits:
        for h in active_habits:
            context.append(f"- {h['title']} ({h['frequency']}, target: {h['target_count']})")
    else:
        context.append("- User has no active habits currently.")

    context.append("\nRecent Journal Reflections:")
    if journals:
        for j in journals:
            content_preview = j['content'][:150].replace('\n', ' ')
            context.append(f"- Date: {j['entry_date']}, Mood Score (1-10): {j['mood_score']}, Reflection: {content_preview}...")
    else:
        context.append("- No recent journals.")

    context.append("\nRecent Achievements Unlocked:")
    if achievements:
        for a in achievements:
            context.append(f"- {a['title']}: {a['description']}")
    else:
        context.append("- No achievements unlocked recently.")

    context.append("--- END OF USER DATA CONTEXT ---")
    return "\n".join(context)


def get_system_prompt(context: str) -> str:
    return f"""You are an elite, highly motivational, and empathetic AI Habit Coach.
Your goal is to help the user build consistency, overcome procrastination, and achieve their goals.

You have access to the user's current habit data, streaks, journal entries, and achievements:
{context}

RULES:
1. Be concise, actionable, and encouraging. Avoid massive walls of text.
2. Structure your responses with clear bullet points or short paragraphs.
3. Reference their specific habits, journal moods, or achievements when relevant.
4. If they ask for advice, suggest routines that fit their current progress.
5. NEVER reveal the raw system context data block. Interpret it naturally as a coach would.
6. Adopt a professional yet friendly "coach" tone.
"""


def generate_ai_response(user_message: str, context: str) -> str:
    try:
        import google.generativeai as genai

        api_key = st.secrets.get("GEMINI_API_KEY")
        if not api_key:
            return "⚠️ Gemini API key not found in secrets. Please configure `GEMINI_API_KEY`."

        genai.configure(api_key=api_key)
        selected_model = utils.get_setting("selected_ai_model", "gemini-1.5-flash")
        try:
            model = genai.GenerativeModel(selected_model)
            prompt = f"{get_system_prompt(context)}\n\nConversation History:\n{conversation}\n\nCurrent User Question:\n{user_message}"
            response = model.generate_content(prompt)
        except Exception:
            # Fallback to gemini-1.5-flash
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"{get_system_prompt(context)}\n\nConversation History:\n{conversation}\n\nCurrent User Question:\n{user_message}"
            response = model.generate_content(prompt)

        if hasattr(response, "text"):
            return response.text
        return "⚠️ Gemini did not return a text response."
    except Exception as e:
        return f"⚠️ AI Error: {e}"


def clear_chat_history() -> None:
    st.session_state.coach_messages = [
        {
            "role": "assistant",
            "content": f"Chat cleared. I'm ready for a fresh start, {utils.get_display_name()}! How can I support you?"
        }
    ]
    st.rerun()


def export_chat_history() -> str:
    export_text = f"# AI Habit Coach Conversation Export\n**Date:** {utils.now().strftime('%Y-%m-%d %H:%M')}\n**User:** {utils.get_display_name()}\n\n---\n\n"
    for msg in st.session_state.coach_messages:
        role = "🤖 Coach" if msg["role"] == "assistant" else "👤 You"
        export_text += f"### {role}\n{msg['content']}\n\n"
    return export_text


def render_top_stats() -> None:
    stats = utils.get_dashboard_statistics()
    with st.expander("📊 Your Progress & Quick Actions", expanded=False):
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("🔥 Streak", f"{stats['current_streak']}d")
        with col2:
            st.metric("⭐ Best", f"{stats['longest_streak']}d")
        with col3:
            st.metric("📈 Completion", f"{stats['completion_percentage']}%")
        with col4:
            st.metric("🎯 Active", stats['total_habits'])
        with col5:
            st.metric("🏆 Achievements", stats['achievements'])

        st.write("")
        col_btn1, col_btn2, _ = st.columns([2, 2, 6])
        with col_btn1:
            if st.button("🧹 Clear Conversation", use_container_width=True, key="btn_clear_chat"):
                clear_chat_history()
        with col_btn2:
            st.download_button(
                label="📥 Export Chat (MD)",
                data=export_chat_history(),
                file_name=f"coach_export_{utils.today().isoformat()}.md",
                mime="text/markdown",
                use_container_width=True,
                key="btn_export_chat"
            )


def render_chat_and_input(user_id: str) -> None:
    chat_container = st.container(height=520, border=False)

    with chat_container:
        for message in st.session_state.coach_messages:
            role = message["role"]
            avatar = "🤖" if role == "assistant" else "👤"
            with st.chat_message(role, avatar=avatar):
                st.markdown(message["content"])

    prompt = st.chat_input("Ask your coach for advice, motivation, or habit strategy...")
    if prompt:
        st.session_state.coach_messages.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)
            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Analyzing habits and formulating advice..."):
                    context = build_user_context(user_id)
                    ai_response = generate_ai_response(prompt, context)
                    st.markdown(ai_response)

        st.session_state.coach_messages.append({"role": "assistant", "content": ai_response})
        st.rerun()


def main() -> None:
    auth.require_login()
    if not utils.get_setting("ai_enabled", True):
        st.error("AI Coach is currently disabled by the administrator.")
        return

    user_id = auth.get_user_id()
    if not user_id:
        st.stop()

    init_session_state()

    ui_components.render_hero(
        title="AI Habit Coach",
        subtitle="Your personal, data-driven assistant for building consistency and achieving your goals.",
        icon="🤖"
    )

    if "GEMINI_API_KEY" not in st.secrets:
        st.warning("⚠️ Gemini API key not found in secrets. Chat functionality will not work until a key is added.")

    render_top_stats()
    render_chat_and_input(user_id)


if __name__ == "__main__":
    main()