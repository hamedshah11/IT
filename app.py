# -----------------------------------------------------------
# PK‑Tax Assistant — Two‑Model Duel (IDs kept in secrets)
# -----------------------------------------------------------
import streamlit as st, openai, json, statistics

# 1️⃣  API key and assistant IDs live in secrets.toml
openai.api_key   = st.secrets["OPENAI_API_KEY"]
ASSISTANT_A_ID   = st.secrets["ASSISTANT_A_ID"]   # e.g. "asst_********"
ASSISTANT_B_ID   = st.secrets["ASSISTANT_B_ID"]   # e.g. "asst_********"
JUDGE_MODEL      = "gpt-4o-mini"                  # grader model

st.set_page_config(page_title="PK‑Tax Duel", page_icon="⚖️")
st.title("🇵🇰 Income‑Tax Assistant — Model Duel")

# ---------- Session state ----------
if "thread_id" not in st.session_state:
    st.session_state.thread_id = openai.beta.threads.create().id
if "history" not in st.session_state:
    st.session_state.history = []
if "tally" not in st.session_state:
    st.session_state.tally = {"A": [], "B": []}

# “New chat” button
if st.sidebar.button("🔄  New chat"):
    st.session_state.clear()
    st.rerun()

# ---------- Replay history ----------
for m in st.session_state.history:
    st.chat_message(m["role"]).markdown(m["content"])

# ---------- User prompt ----------
prompt = st.chat_input("Ask a tax question…")
if prompt:
    st.chat_message("user").markdown(prompt)
    st.session_state.history.append({"role": "user", "content": prompt})

    openai.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=prompt
    )

    # helper to run one assistant
    def run_assistant(aid):
        run = openai.beta.threads.runs.create_and_poll(
            thread_id=st.session_state.thread_id,
            assistant_id=aid
        )
        if run.status != "completed":
            return f"❌ run ended: {run.status}"
        msg = openai.beta.threads.messages.list(
            thread_id=st.session_state.thread_id,
            limit=1
        ).data[0]
        return msg.content[0].text.value

    answer_a = run_assistant(ASSISTANT_A_ID)
    answer_b = run_assistant(ASSISTANT_B_ID)

    # side‑by‑side display
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### **Model A**")
        st.write(answer_a)
    with col2:
        st.markdown("#### **Model B**")
        st.write(answer_b)

    # auto‑grade
    rubric = (
        "You are an income‑tax expert. Score each answer 0‑5 for legal accuracy, "
        "clarity and completeness. Reply only JSON like {\"A\": 4, \"B\": 2}."
    )
    judge = openai.chat.completions.create(
        model=JUDGE_MODEL, temperature=0,
        messages=[
            {"role": "system", "content": rubric},
            {"role": "user",   "content":
             f"QUESTION:\n{prompt}\n\nAnswer A:\n{answer_a}\n\nAnswer B:\n{answer_b}"}
        ]
    )
    try:
        scores = json.loads(judge.choices[0].message.content)
    except Exception:
        scores = {"A": 0, "B": 0}

    st.success(f"Auto‑scores → Model A **{scores['A']}** / Model B **{scores['B']}**")

    for k in ("A", "B"):
        st.session_state.tally[k].append(scores[k])

    # leaderboard
    st.sidebar.markdown("### Leaderboard (avg score)")
    for k, label in (("A", "Model A"), ("B", "Model B")):
        lst = st.session_state.tally[k]
        if lst:
            st.sidebar.write(f"{label}: {statistics.mean(lst):.2f} on {len(lst)} Qs")

    # log
    combined = f"**Model A**\n{answer_a}\n\n---\n\n**Model B**\n{answer_b}"
    st.session_state.history.append({"role": "assistant", "content": combined})
