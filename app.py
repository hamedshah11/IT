import time, streamlit as st, openai, os

openai.api_key = st.secrets["OPENAI_API_KEY"]
ASSISTANT_ID   = st.secrets["ASSISTANT_ID"]

st.set_page_config(page_title="PK-Tax Assistant", page_icon="💰")
st.title("🇵🇰 Income-Tax Assistant")

# ---- Session state -------------------------------------------------
if "thread_id" not in st.session_state:
    st.session_state.thread_id = openai.beta.threads.create().id
if "history" not in st.session_state:
    st.session_state.history = []

# ---- Replay chat history ------------------------------------------
for msg in st.session_state.history:
    st.chat_message(msg["role"]).markdown(msg["content"])

# ---- Handle user input --------------------------------------------
prompt = st.chat_input("Ask a tax question…")
if prompt:
    st.chat_message("user").markdown(prompt)
    st.session_state.history.append({"role": "user", "content": prompt})

    openai.beta.threads.messages.create(
        thread_id = st.session_state.thread_id,
        role      = "user",
        content   = prompt)

    # **** Streamlined helper call ****
    run = openai.beta.threads.runs.create_and_poll(         # NEW
        thread_id    = st.session_state.thread_id,
        assistant_id = ASSISTANT_ID
    )

    if run.status == "completed":
        msg = openai.beta.threads.messages.list(
            thread_id = st.session_state.thread_id,
            limit     = 1).data[0]

        if msg.content[0].type == "text":                   # SAFEGUARD
            reply = msg.content[0].text.value
        else:
            reply = "⚠️ Assistant returned non-text content."
    else:
        reply = f"❌ Run ended with status: {run.status}"

    st.chat_message("assistant").markdown(reply)
    st.session_state.history.append(
        {"role": "assistant", "content": reply})
