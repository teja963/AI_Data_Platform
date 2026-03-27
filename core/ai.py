from groq import Groq
import streamlit as st


def get_client():
    try:
        return Groq(api_key=st.secrets["GROQ_API_KEY"])
    except:
        return None


def ask_ai(prompt, system_prompt="You are a SQL expert helping a student. Be clear and structured."):
    client = get_client()

    if client is None:
        return "⚠️ AI not configured. Add GROQ_API_KEY."

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # ✅ UPDATED MODEL
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"❌ AI Error: {str(e)}"
