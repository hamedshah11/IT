# -----------------------------------------------
# PK‑Tax Assistant – Two‑Model Duel  (app.py)
# -----------------------------------------------
import streamlit as st, openai, json, csv, os, statistics
from datetime import datetime

# ── 1. secrets ─────────────────────────────────
openai.api_key = st.secrets["OPENAI_API_KEY"]
ASSISTANT_A_ID = st.secrets["ASSISTANT_A_ID"]
ASSISTANT_B_ID = st.secrets["ASSISTANT_B_ID"]
JUDGE_MODEL    = "gpt-4o-mini"
CSV_FEEDBACK   = "votes.csv"

# ── 2. page look & feel ────────────────────────
st.set_page_config(page_title="PK‑Tax Assistant", page_icon="💰", layout="centered")
st.markdown(
    """
    <style>
      html,body,div,span{font-family:'Inter',sans-serif;}
      .bubble{background:#20232a;border-left:4px solid #0b8913;
              border-radius:8px;padding:12px;margin-bottom:8px}
      .stChatInput > div{background:#1f2227!important;border-radius:8px}
    </style>""",
    unsafe_allow_html=True,
)

# ── 3. session state ───────────────────────────
if "thread_id" not in st.session_state:
    st.session_state.thread_id = openai.beta.threads.create().id
if "history" not in st.session_state:
    st.session_state.history = []
if "tally" not in st.session_state:
    st.session_state.tally = {"A": [], "B": []}

# ── 4. sidebar ─────────────────────────────────
if st.sidebar.button("🔄 New chat"):
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("### Leaderboard")
for tag, label in (("A", "Model A"), ("B", "Model B")):
    lst = st.session_state.tally[tag]
    if lst:
        st.sidebar.write(f"{label}: {statistics.mean(lst):.2f} on {len(lst)} Qs")

# ── 5. replay history ──────────────────────────
for m in st.session_state.history:
    st.chat_message(m["role"]).markdown(m["content"], unsafe_allow_html=True)

# ── 6. sample questions panel ──────────────────
if not st.session_state.history:
    with st.expander("❓ Need inspiration?"):
        q_samples = [
            "Do I have to file if my salary is Rs 550,000?",
            "Advance tax on selling property?",
            "How is a yearly bonus taxed?",
            "Penalty for filing the return 2 months late?",
        ]
        cols = st.columns(2)
        for i, q in enumerate(q_samples):
            if cols[i % 2].button(q):
                st.session_state.prefill = q

# ── 7. optional hint (NO pre‑fill) ─────────────
if "prefill" in st.session_state:
    st.caption(f"💡 Try asking: **{st.session_state.prefill}**")
    st.session_state.pop("prefill")

# ↓↓↓  ABSOLUTELY NO `value=` KWARG HERE ↓↓↓
prompt = st.chat_input("Ask a tax question…")
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

# ── 8. helpers ─────────────────────────────────
def stream_answer(aid: str) -> str:
    out, holder = "", st.empty()
    for chunk in openai.beta.threads.runs.create_and_stream(
        thread_id=st.session_state.thread_id,
        assistant_id=aid,
    ):
        delta = chunk.delta.get("content", [{}])[0].get("text", {}).get("value", "")
        if delta:
            out += delta
            holder.markdown(out + "▌")
    holder.markdown(out)
    return out

def record_vote(model: str, score: int, q: str, ans: str):
    new_file = not os.path.exists(CSV_FEEDBACK)
    with open(CSV_FEEDBACK, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["time", "model", "score", "question", "answer"])
        writer.writerow([datetime.utcnow().isoformat(), model, score, q, ans])

def feedback_buttons(key: str, model: str, q: str, ans: str):
    c1, c2 = st.columns(2)
    if c1.button("👍", key="u"+key):
        record_vote(model, 1, q, ans); st.toast("Thanks for the 👍!")
    if c2.button("👎", key="d"+key):
        record_vote(model, -1, q, ans); st.toast("Feedback noted!")

# ── 9. main logic ─────────────────────────────
if prompt:
    # a) echo user msg
    st.chat_message("user").markdown(prompt)
    st.session_state.history.append({"role": "user", "content": prompt})
    openai.beta.threads.messages.create(
        thread_id=st.session_state.thread_id, role="user", content=prompt
    )

    # b) run assistants
    colA, colB = st.columns(2)
    with colA:
        st.markdown("#### Model A")
        ans_a = stream_answer(ASSISTANT_A_ID)
        feedback_buttons("A"+str(len(st.session_state.tally["A"])), "A", prompt, ans_a)
    with colB:
        st.markdown("#### Model B")
        ans_b = stream_answer(ASSISTANT_B_ID)
        feedback_buttons("B"+str(len(st.session_state.tally["B"])), "B", prompt, ans_b)

    # c) judge
    rubric = (
        "You are an income‑tax expert. Score each answer 0‑5 for legal accuracy, "
        "clarity and completeness. Reply JSON only: {\"A\":x, \"B\":y}."
    )
    judge = openai.chat.completions.create(
        model=JUDGE_MODEL, temperature=0,
        messages=[
            {"role": "system", "content": rubric},
            {"role": "user",
             "content": f"Q: {prompt}\n\nA:\n{ans_a}\n\nB:\n{ans_b}"},
        ],
    )
    scores = json.loads(judge.choices[0].message.content)
    st.success(f"Auto‑scores → A **{scores['A']}** | B **{scores['B']}**")
    for tag in ("A", "B"):
        st.session_state.tally[tag].append(scores[tag])

    # d) log assistant bubbles
    bubbles = (
        f"<div class='bubble'><strong>Model A</strong><br>{ans_a}</div>"
        f"<div class='bubble'><strong>Model B</strong><br>{ans_b}</div>"
    )
    st.session_state.history.append({"role": "assistant", "content": bubbles})
