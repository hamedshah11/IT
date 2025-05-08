# -----------------------------------------------------------
# PK‑Tax Assistant  ·  Two‑Model Duel  (works on all versions)
# -----------------------------------------------------------
import streamlit as st, openai, json, csv, os, statistics
from datetime import datetime

# ── 1.  Secrets ----------------------------------------------------
openai.api_key = st.secrets["OPENAI_API_KEY"]
ASSISTANT_A_ID = st.secrets["ASSISTANT_A_ID"]
ASSISTANT_B_ID = st.secrets["ASSISTANT_B_ID"]
JUDGE_MODEL    = "gpt-4o-mini"
CSV_FILE       = "votes.csv"         # thumbs‑up / down log

# ── 2.  Basic page -------------------------------------------------
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

# ── 3.  Session state ---------------------------------------------
if "thread_id" not in st.session_state:
    st.session_state.thread_id = openai.beta.threads.create().id
if "history" not in st.session_state:
    st.session_state.history = []
if "tally" not in st.session_state:
    st.session_state.tally = {"A": [], "B": []}

# ── 4.  Sidebar  (leaderboard & reset) -----------------------------
if st.sidebar.button("🔄 New chat"):
    st.session_state.clear(); st.rerun()

st.sidebar.markdown("### Leaderboard")
for tag, lbl in (("A","Model A"), ("B","Model B")):
    data = st.session_state.tally[tag]
    if data:
        st.sidebar.write(f"{lbl}: {statistics.mean(data):.2f} on {len(data)} Qs")

# ── 5.  Replay chat history ---------------------------------------
for m in st.session_state.history:
    st.chat_message(m["role"]).markdown(m["content"], unsafe_allow_html=True)

# ── 6.  Example questions panel -----------------------------------
if not st.session_state.history:
    with st.expander("❓ Need inspiration?"):
        examples = [
            "Do I need to file if my salary is Rs 550,000?",
            "What advance tax applies when I sell property?",
            "How is a yearly bonus taxed?",
            "Penalty for filing return 2 months late?",
        ]
        cols = st.columns(2)
        for i,q in enumerate(examples):
            if cols[i%2].button(q):
                st.session_state.prefill = q

# ── 7.  Input helper (works on any Streamlit) ----------------------
def get_prompt(label="Ask a tax question…"):
    if hasattr(st, "chat_input"):              # Streamlit ≥1.26
        return st.chat_input(label)
    return st.text_input(label)                # older Streamlit

if "prefill" in st.session_state:
    st.caption(f"💡 Try asking: **{st.session_state.prefill}**")
    st.session_state.pop("prefill")

prompt = get_prompt()

# ── 8.  Utility functions -----------------------------------------
def stream_answer(aid: str) -> str:
    txt, holder = "", st.empty()
    for chunk in openai.beta.threads.runs.create_and_stream(
        thread_id=st.session_state.thread_id,
        assistant_id=aid,
    ):
        delta = chunk.delta.get("content", [{}])[0].get("text", {}).get("value", "")
        if delta:
            txt += delta
            holder.markdown(txt + "▌")
    holder.markdown(txt)
    return txt

def record_vote(model: str, score: int, q: str, ans: str):
    new = not os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time","model","score","question","answer"])
        w.writerow([datetime.utcnow().isoformat(), model, score, q, ans])

def vote_buttons(key: str, model: str, q: str, ans: str):
    c1, c2 = st.columns(2)
    if c1.button("👍", key="u"+key):
        record_vote(model, 1, q, ans); st.toast("Thanks!")
    if c2.button("👎", key="d"+key):
        record_vote(model, -1, q, ans); st.toast("Noted!")

# ── 9.  Main flow --------------------------------------------------
if prompt:
    # user bubble
    st.chat_message("user").markdown(prompt)
    st.session_state.history.append({"role":"user","content":prompt})
    openai.beta.threads.messages.create(
        thread_id=st.session_state.thread_id, role="user", content=prompt)

    # assistants
    colA, colB = st.columns(2)
    with colA:
        st.markdown("#### Model A")
        ans_a = stream_answer(ASSISTANT_A_ID)
        vote_buttons("A"+str(len(st.session_state.tally["A"])), "A", prompt, ans_a)
    with colB:
        st.markdown("#### Model B")
        ans_b = stream_answer(ASSISTANT_B_ID)
        vote_buttons("B"+str(len(st.session_state.tally["B"])), "B", prompt, ans_b)

    # auto‑grade
    rubric = ("Score each answer 0‑5 for legal accuracy, clarity, completeness. "
              "Return JSON only: {\"A\":x,\"B\":y}.")
    judge = openai.chat.completions.create(
        model=JUDGE_MODEL, temperature=0,
        messages=[
            {"role":"system","content":rubric},
            {"role":"user",
             "content":f"Q: {prompt}\n\nA:\n{ans_a}\n\nB:\n{ans_b}"},
        ])
    scores = json.loads(judge.choices[0].message.content)
    st.success(f"Auto‑scores → A **{scores['A']}** | B **{scores['B']}**")
    for t in ("A","B"):
        st.session_state.tally[t].append(scores[t])

    # assistant bubbles to history
    bubbles = (
        f"<div class='bubble'><strong>Model A</strong><br>{ans_a}</div>"
        f"<div class='bubble'><strong>Model B</strong><br>{ans_b}</div>"
    )
    st.session_state.history.append({"role":"assistant","content":bubbles})
