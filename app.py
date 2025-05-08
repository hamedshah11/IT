# -------------------------------------------------------
# PK‑Tax Assistant  –  Duel Edition  (sync, cloud‑safe)
# -------------------------------------------------------
import streamlit as st, openai, json, csv, os, statistics
from datetime import datetime

# 1.  Secrets  ───────────────────────────────────────────
openai.api_key = st.secrets["OPENAI_API_KEY"]
A_ID = st.secrets["ASSISTANT_A_ID"]
B_ID = st.secrets["ASSISTANT_B_ID"]
JUDGE = "gpt-4o-mini"; CSV = "votes.csv"

# 2.  Simple page style  ─────────────────────────────────
st.set_page_config(page_title="PK‑Tax Assistant", page_icon="💰")
st.write("## 🇵🇰 Income‑Tax Assistant — Model Duel")

# 3.  State buckets  ─────────────────────────────────────
if "thread_id" not in st.session_state:
    st.session_state.thread_id = openai.beta.threads.create().id
if "log" not in st.session_state:
    st.session_state.log = []            # chat history
if "tally" not in st.session_state:
    st.session_state.tally = {"A": [], "B": []}

# 4.  Prompt input  (robust to old Streamlit)  ───────────
prompt = st.text_input("Ask a tax question…")

# 5.  Helpers  ───────────────────────────────────────────
def answer_from(aid: str) -> str:
    """Blocking helper that works on every SDK."""
    run = openai.beta.threads.runs.create_and_poll(
        thread_id=st.session_state.thread_id,
        assistant_id=aid,
    )
    msg = openai.beta.threads.messages.list(
        thread_id=st.session_state.thread_id, limit=1
    ).data[0]
    return msg.content[0].text.value

def vote(model: str, score: int, q: str, ans: str):
    new = not os.path.exists(CSV)
    with open(CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["utc", "model", "score", "question", "answer"])
        w.writerow([datetime.utcnow().isoformat(), model, score, q, ans])

# 6.  Main flow  ─────────────────────────────────────────
if prompt:
    st.session_state.log.append(("user", prompt))
    openai.beta.threads.messages.create(
        thread_id=st.session_state.thread_id, role="user", content=prompt
    )

    col1, col2 = st.columns(2)
    with col1:
        st.write("#### Model A")
        ans_a = answer_from(A_ID)
        st.write(ans_a)
        if st.button("👍 A"): vote("A", 1, prompt, ans_a)
        if st.button("👎 A"): vote("A", -1, prompt, ans_a)
    with col2:
        st.write("#### Model B")
        ans_b = answer_from(B_ID)
        st.write(ans_b)
        if st.button("👍 B"): vote("B", 1, prompt, ans_b)
        if st.button("👎 B"): vote("B", -1, prompt, ans_b)

    # grading
    rubric = ("Score A and B 0‑5 for accuracy / clarity / completeness. "
              "Return JSON {\"A\":x,\"B\":y}.")
    judge = openai.chat.completions.create(
        model=JUDGE, temperature=0,
        messages=[
            {"role":"system","content":rubric},
            {"role":"user",
             "content":f"Q:{prompt}\n\nA:{ans_a}\n\nB:{ans_b}"}
        ])
    scores = json.loads(judge.choices[0].message.content)
    st.success(f"Auto‑scores → A **{scores['A']}** | B **{scores['B']}**")
    for tag in ("A","B"):
        st.session_state.tally[tag].append(scores[tag])

# 7.  Leaderboard  ───────────────────────────────────────
st.sidebar.write("### Leaderboard")
for tag,lbl in (("A","Model A"),("B","Model B")):
    d = st.session_state.tally[tag]
    if d:
        st.sidebar.write(f"{lbl}: {statistics.mean(d):.2f} on {len(d)} Qs")
