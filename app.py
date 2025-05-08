# -----------------------------------------------
# PK‑Tax Assistant  –  Two‑Model Duel   (app.py)
# -----------------------------------------------
import streamlit as st, openai, json, csv, os, statistics
from datetime import datetime

# ── 1. secrets & OpenAI ─────────────────────────
def get_secret(key: str):
    """First try .streamlit/secrets.toml, else env var; error if missing."""
    val = st.secrets.get(key) or os.getenv(key)
    if val is None:
        st.error(f"Missing secret: {key}. Set it in secrets.toml or env vars.")
        st.stop()
    return val

openai.api_key   = get_secret("OPENAI_API_KEY")
ASSISTANT_A_ID   = get_secret("ASSISTANT_A_ID")
ASSISTANT_B_ID   = get_secret("ASSISTANT_B_ID")
JUDGE_MODEL      = "gpt-4o-mini"           # cheap grader
CSV_FEEDBACK     = "votes.csv"

# ── 2. page & dark theme ───────────────────────
st.set_page_config(page_title="PK‑Tax Assistant", page_icon="💰")
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

# ── 4. sidebar leaderboard & reset ─────────────
if st.sidebar.button("🔄 New chat"):
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("### Leaderboard (avg score)")
for tag, label in (("A", "Model A"), ("B", "Model B")):
    scores = st.session_state.tally[tag]
    if scores:
        st.sidebar.write(f"{label}: {statistics.mean(scores):.2f} on {len(scores)} Qs")

# ── 5. replay old messages ─────────────────────
for m in st.session_state.history:
    st.chat_message(m["role"]).markdown(m["content"], unsafe_allow_html=True)

# ── 6. sample questions expander ───────────────
if not st.session_state.history:
    with st.expander("❓ Need inspiration? Click a sample…"):
        qs = [
            "Do I have to file if my salary is Rs 550,000?",
            "Advance tax on selling property?",
            "How is a yearly bonus taxed?",
            "Penalty for filing return 2 months late?",
        ]
        cols = st.columns(2)
        for i, q in enumerate(qs):
            if cols[i % 2].button(q):
                st.session_state.example = q

# ── 7. input box (NO value= arg) ───────────────
if "example" in st.session_state:
    st.caption(f"💡 Try this: **{st.session_state.example}**")

prompt = st.chat_input("Ask a tax question…")

# ── 8. helpers ─────────────────────────────────
def stream_answer(aid: str) -> str:
    """Run an assistant with streaming and return the full text."""
    collected, holder = "", st.empty()
    for chunk in openai.beta.threads.runs.create_and_stream(
        thread_id=st.session_state.thread_id,
        assistant_id=aid,
    ):
        delta = chunk.delta.get("content", [{}])[0].get("text", {}).get("value", "")
        if delta:
            collected += delta
            holder.markdown(collected + "▌")
    holder.markdown(collected)
    return collected

def feedback_ui(key: str, model_tag: str, q: str, ans: str):
    c1, c2 = st.columns([1, 1])
    if c1.button("👍", key=f"u{key}"):
        record_vote(model_tag, 1, q, ans)
        st.toast("Thanks for the 👍!")
    if c2.button("👎", key=f"d{key}"):
        record_vote(model_tag, -1, q, ans)
        st.toast("Got it – we’ll improve!")

def record_vote(model: str, score: int, q: str, ans: str):
    row = [datetime.utcnow().isoformat(), model, score, q, ans]
    new_file = not os.path.exists(CSV_FEEDBACK)
    with open(CSV_FEEDBACK, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["time", "model", "score", "question", "answer"])
        writer.writerow(row)

# ── 9. main flow ───────────────────────────────
if prompt:
    # store user msg
    st.chat_message("user").markdown(prompt)
    st.session_state.history.append({"role": "user", "content": prompt})
    openai.beta.threads.messages.create(
        thread_id=st.session_state.thread_id, role="user", content=prompt
    )

    # get answers
    colA, colB = st.columns(2)
    with colA:
        st.markdown("#### **Model A**")
        ans_a = stream_answer(ASSISTANT_A_ID)
        feedback_ui("A" + str(len(st.session_state.tally["A"])), "A", prompt, ans_a)
    with colB:
        st.markdown("#### **Model B**")
        ans_b = stream_answer(ASSISTANT_B_ID)
        feedback_ui("B" + str(len(st.session_state.tally["B"])), "B", prompt, ans_b)

    # auto‑grade via judge model
    rubric = (
        "You are an income‑tax expert. Score each answer 0‑5 for legal accuracy, clarity, "
        "and completeness. Reply JSON only: {\"A\":x,\"B\":y}."
    )
    judge = openai.chat.completions.create(
        model=JUDGE_MODEL, temperature=0,
        messages=[
            {"role": "system", "content": rubric},
            {"role": "user",   "content":
             f"QUESTION:\n{prompt}\n\nAnswer A:\n{ans_a}\n\nAnswer B:\n{ans_b}"},
        ],
    )
    scores = json.loads(judge.choices[0].message.content)
    st.success(f"Auto‑scores → Model A **{scores['A']}** | Model B **{scores['B']}**")
    for tag in ("A", "B"):
        st.session_state.tally[tag].append(scores[tag])

    # store assistant bubbles in history
    bubbles = (
        f"<div class='bubble'><strong>Model A</strong><br>{ans_a}</div>"
        f"<div class='bubble'><strong>Model B</strong><br>{ans_b}</div>"
    )
    st.session_state.history.append({"role": "assistant", "content": bubbles})
