# -------------------------------------------------------------
# PK‑Tax Assistant — Model‑Duel demo (official pattern only)
# -------------------------------------------------------------
import streamlit as st, openai, os, json, time, statistics

# ========= 1.  Secrets (Streamlit Cloud: set in Settings → Secrets) ==========
openai.api_key = st.secrets["OPENAI_API_KEY"]
ASSISTANT_A_ID = st.secrets["ASSISTANT_A_ID"]      # already configured in dashboard
ASSISTANT_B_ID = st.secrets["ASSISTANT_B_ID"]

# ========= 2.  UI basics =====================================================
st.set_page_config(page_title="PK‑Tax Assistant", page_icon="💰")
st.write("## 🇵🇰 Income‑Tax Assistant — Model Duel")

# ========= 3.  Session buckets ==============================================
for key in ("thread_A", "thread_B", "history", "tally"):
    if key not in st.session_state:
        if key == "tally":
            st.session_state[key] = {"A": [], "B": []}
        elif key.startswith("thread"):
            st.session_state[key] = openai.beta.threads.create().id
        else:
            st.session_state[key] = []

# ========= 4.  Helper: run assistant synchronously ===========================
def get_answer(thread_id: str, assistant_id: str, question: str) -> str:
    """Adds user msg, starts a run; polls until done; returns assistant text."""
    # step 2 – add the user message
    openai.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=question,
    )
    # step 3 – start a run
    run = openai.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )
    # step 4 – poll
    while run.status not in ("completed", "failed", "cancelled", "expired"):
        time.sleep(0.4)
        run = openai.beta.threads.runs.retrieve(thread_id, run.id)
    if run.status != "completed":
        return f"⚠️ run ended with status {run.status}"
    # step 5 – read the newest assistant message
    msg = openai.beta.threads.messages.list(
        thread_id=thread_id, limit=1).data[0]
    return msg.content[0].text.value

# ========= 5.  Sidebar leaderboard ==========================================
if st.sidebar.button("🔄 New chat"):
    st.session_state.clear(); st.rerun()

st.sidebar.markdown("### Leaderboard")
for tag, label in (("A", "Model A"), ("B", "Model B")):
    data = st.session_state.tally[tag]
    if data:
        st.sidebar.write(f"{label}: {statistics.mean(data):.2f} on {len(data)} Qs")

# ========= 6.  Replay old chat messages =====================================
for role, txt in st.session_state.history:
    st.chat_message(role).markdown(txt, unsafe_allow_html=True)

# ========= 7.  Prompt input (works on any Streamlit build) ===================
prompt = (st.chat_input if hasattr(st, "chat_input") else st.text_input)(
    "Ask a tax question…"
)

# ========= 8.  Main flow =====================================================
if prompt:
    # log user
    st.chat_message("user").markdown(prompt)
    st.session_state.history.append(("user", prompt))

    # Ask both assistants (separate threads)
    col1, col2 = st.columns(2)
    with col1:
        st.write("#### Model A")
        ans_a = get_answer(st.session_state.thread_A, ASSISTANT_A_ID, prompt)
        st.write(ans_a)
    with col2:
        st.write("#### Model B")
        ans_b = get_answer(st.session_state.thread_B, ASSISTANT_B_ID, prompt)
        st.write(ans_b)

    # simple grading with gpt‑4o‑mini (optional)
    judge = openai.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role":"system","content":
             "Score A and B from 0‑5 for accuracy, clarity, completeness. "
             "Respond JSON: {\"A\":x,\"B\":y}."},
            {"role":"user",
             "content":f"Q: {prompt}\n\nA:\n{ans_a}\n\nB:\n{ans_b}"},
        ])
    try:
        scores = json.loads(judge.choices[0].message.content)
    except Exception:
        scores = {"A": 0, "B": 0}
    st.success(f"Auto‑scores → A **{scores['A']}** | B **{scores['B']}**")
    for tag in ("A","B"): st.session_state.tally[tag].append(scores[tag])

    # store assistant replies in history
    html = (f"<div style='border-left:4px solid #0b8913;padding:8px;'>"
            f"<b>Model A</b><br>{ans_a}</div>"
            f"<div style='border-left:4px solid #FFD700;padding:8px;margin-top:4px;'>"
            f"<b>Model B</b><br>{ans_b}</div>")
    st.session_state.history.append(("assistant", html))
