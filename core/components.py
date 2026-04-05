import streamlit as st
from core.ai import ask_ai

def render_ai_chat(section_key, title, topic):
    """Standardized AI Chat component used across all modules."""
    chat_key = f"{section_key}_chat"
    input_key = f"{section_key}_chat_input"

    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    st.markdown("---")
    with st.expander(f"💬 {title}", expanded=False):
        if st.session_state[chat_key]:
            for chat in st.session_state[chat_key]:
                label = "Assistant" if chat["role"] == "assistant" else "You"
                # Using standard Streamlit components for chat ensures theme compatibility
                with st.chat_message(chat["role"]):
                    st.markdown(f"**{label}:** {chat['content']}")

        with st.form(f"{section_key}_ai_form", clear_on_submit=True):
            user_input = st.text_area(
                "Ask anything",
                key=input_key,
                height=100,
                placeholder=f"Ask about {topic}...",
            )
            submitted = st.form_submit_button("Ask AI", use_container_width=True)

        if submitted and user_input.strip():
            cleaned_input = user_input.strip()
            st.session_state[chat_key].append({
                "role": "user",
                "content": cleaned_input
            })

            prompt = f"""
                You are a senior data engineer at a top tech company.
                Answer the following question on {topic}.

                Question:
                {cleaned_input}

                Requirements:
                - Detailed structured answer with at least 2 real-world examples.
                - Interview-ready explanation with trade-offs and edge cases.
                - Concise but insightful.

                Format:
                - Definition
                - Explanation
                - Real-world examples
                - Interview insights
                """

            response = ask_ai(prompt)
            st.session_state[chat_key].append({
                "role": "assistant",
                "content": response
            })
            st.rerun()