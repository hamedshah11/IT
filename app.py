# -------------------------------------------------------------
# PK‑Tax Assistant – Two‑Model Duel (stable / cloud‑safe)
# -------------------------------------------------------------
import streamlit as st, openai, json, csv, os, statistics, time
from datetime import datetime

# 1. Secrets ----------------------------------------------------
openai.api_key = st.secrets["OPENAI_API_KEY"]
ASSISTANT_A_ID = st.secrets["ASSISTANT_A_ID"]  # model A
ASSISTANT_B_ID = st.secrets["ASSISTANT_B_ID"]  # model B
JUDGE_MODEL    = "gpt-4o-mini"
CSV_FILE       = "votes.csv"

# 2. Page style -------------------------------------------------
st.set_page_config(page_title="PK‑Tax Assistant", page_icon="💰")
st.markdown(
    """
    <style>
      html,body,div,span{font-family:'Inter',sans-serif;}
      .bubble{background:#20232a;border-left:4px solid #0b8913;
              border-radius:8px;padding:12px;margin-bottom:8px}
    </style>""",
    unsafe_allow_html=True,
)
st.write("## 🇵🇰 Income‑Tax Assistant — Model Duel")

# 3. Session state ---------------------------------------------
if "thread_A" not in st.session_state:
    st.session_state.thread_A = openai.beta.threads.create().id
if "thread_B" not in st.session_state:
    st.session_state.thread_B = openai.beta.threads.create().id
if "history" not in st.session_state:
    st.session_state.history = []
if "tally" not in st.session_state:
    st.session_state.tally = {"A": [], "B": []}

# Reset chat
if st.sidebar.button("🔄 New chat"):
    st.session_state.clear()
    st.rerun()

# Leaderboard
st.sidebar.markdown("### Leaderboard")
for tag, lbl in (("A", "Model A"), ("B", "Model B")):
    data = st.session_state.tally[tag]
    if data:
        st.sidebar.write(f"{lbl}: {statistics.mean(data):.2f} on {len(data)} Qs")

# Replay history
for role, msg in st.session_state.history:
    st.chat_message(role).markdown(msg, unsafe_allow_html=True)

# 4. Prompt input (chat_input if available) ---------------------
if hasattr(st, "chat_input"):
    prompt = st.chat_input("Ask a tax question…")
else:
    prompt = st.text_input("Ask a tax question…")

# 5. Helpers ----------------------------------------------------
def run_and_get_answer(thread_id: str, assistant_id: str) -> str:
    """Create a run, poll until finished, return assistant text."""
    run = openai.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )
    while run.status not in ("completed", "failed", "cancelled", "expired"):
        time.sleep(0.4)
        run = openai.beta.threads.runs.retrieve(
            thread_id=thread_id, run_id=run.id
        )
    if run.status != "completed":
        return f"⚠️ run ended with status {run.status}"
    msg = openai.beta.threads.messages.list(
        thread_id=thread_id, limit=1
    ).data[0]
    return msg.content[0].text.value

def record_vote(model: str, score: int, q: str, ans: str):
    new_file = not os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["utc", "model", "score", "question", "answer"])
        w.writerow([datetime.utcnow().isoformat(), model, score, q, ans])

# 6. Main flow --------------------------------------------------
if prompt:
    # store user message
    st.chat_message("user").markdown(prompt)
    st.session_state.history.append(("user", prompt))

    # answer with model A then model B (parallel threads)
    col1, col2 = st.columns(2)

    with col1:
        st.write("#### Model A")
        ans_a = run_and_get_answer(st.session_state.thread_A, ASSISTANT_A_ID)
        st.write(ans_a)
        if st.button("👍 A"):
            record_vote("A", 1, prompt, ans_a)
        if st.button("👎 A"):
            record_vote("A", -1, prompt, ans_a)

    with col2:
        st.write("#### Model B")
        ans_b = run_and_get_answer(st.session_state.thread_B, ASSISTANT_B_ID)
        st.write(ans_b)
        if st.button("👍 B"):
            record_vote("B", 1, prompt, ans_b)
        if st.button("👎 B"):
            record_vote("B", -1, prompt, ans_b)

    # auto-grade via judge model
    rubric = ("Score A and B 0‑5 for accuracy, clarity, completeness. "
              "Return JSON: {\"A\":x,\"B\":y}.")
    judge = openai.chat.completions.create(
        model=JUDGE_MODEL, temperature=0,
        messages=[
            {"role":"system","content":rubric},
            {"role":"user",
             "content":f"Q: {prompt}\n\nA:\n{ans_a}\n\nB:\n{ans_b}"},
        ])
    try:
        scores = json.loads(judge.choices[0].message.content)
    except Exception:
        scores = {"A": 0, "B": 0}
    st.success(f"Auto‑scores → A **{scores['A']}** | B **{scores['B']}**")
    for tag in ("A", "B"):
        st.session_state.tally[tag].append(scores[tag])

    # add assistant bubbles to history
    bubbles = (
        f"<div class='bubble'><strong>Model A</strong><br>{ans_a}</div>"
        f"<div class='bubble'><strong>Model B</strong><br>{ans_b}</div>"
    )
    st.session_state.history.append(("assistant", bubbles))
