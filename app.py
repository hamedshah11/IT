# -----------------------------------------------------------
# PK‑Tax Assistant — Two‑Model Duel w/ UI Extras
# -----------------------------------------------------------
import streamlit as st, openai, json, statistics, csv, os
from datetime import datetime
from itertools import zip_longest

# ========= CONFIG ==========
openai.api_key   = st.secrets["OPENAI_API_KEY"]
ASSISTANT_A_ID   = st.secrets["ASSISTANT_A_ID"]
ASSISTANT_B_ID   = st.secrets["ASSISTANT_B_ID"]
JUDGE_MODEL      = "gpt-4o-mini"          # cheap grader
CSV_FEEDBACK     = "votes.csv"            # stored locally

THEME_PRIMARY    = "#0b8913"              # 🇵🇰 green

# ========= PAGE & THEME ==========
st.set_page_config(page_title="PK‑Tax Assistant", page_icon="💰")
st.markdown(
    f"""
    <style>
    html,body,div,span {{ font-family: 'Inter', sans-serif; }}
    .stChatInput > div {{ background:#1f2227!important;border-radius:8px }}
    .bubble {{ background:#20232a;border-left:4px solid {THEME_PRIMARY};
               border-radius:8px;padding:12px;margin-bottom:8px }}
    </style>""",
    unsafe_allow_html=True,
)

# ========= SESSION STATE ==========
if "thread_id" not in st.session_state:
    st.session_state.thread_id = openai.beta.threads.create().id
if "history" not in st.session_state:
    st.session_state.history = []
if "tally" not in st.session_state:
    st.session_state.tally = {"A": [], "B": []}

# ========= SIDEBAR ==========
if st.sidebar.button("🔄  New chat"):
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("### Leaderboard (avg score)")
for k, lbl in (("A", "Model A"), ("B", "Model B")):
    lst = st.session_state.tally[k]
    if lst:
        st.sidebar.write(f"{lbl}: {statistics.mean(lst):.2f} on {len(lst)} Qs")

# ========= REPLAY HISTORY ==========
for msg in st.session_state.history:
    st.chat_message(msg["role"]).markdown(msg["content"], unsafe_allow_html=True)

# ========= EXAMPLE QUESTIONS ==========
if not st.session_state.history:
    with st.expander("❓ Need inspiration?  Click a sample…"):
        samples = [
            "Do I have to file if my salary is Rs 550,000?",
            "What advance tax is deducted when I sell property?",
            "How is a yearly bonus taxed?",
            "Penalty for filing my return 2 months late?",
        ]
        cols = st.columns(2)
        for i, q in enumerate(samples):
            if cols[i % 2].button(q):
                st.session_state.example = q

# ========= USER INPUT ==========
prefill = st.session_state.pop("example", "")
prompt  = st.chat_input("Ask a tax question…", value=prefill)

# ========= FUNCTIONS ==========
def stream_assistant(aid: str) -> str:
    """Run assistant in streaming mode and return full answer."""
    chunks, collected = [], ""
    with st.chat_message("assistant"):
        ph = st.empty()
        for chunk in openai.beta.threads.runs.create_and_stream(
            thread_id=st.session_state.thread_id,
            assistant_id=aid,
        ):
            delta = (
                chunk.delta.get("content", [{}])[0].get("text", {}).get("value", "")
            )
            if delta:
                collected += delta
                ph.markdown(collected + "▌")
        ph.markdown(collected)
    return collected

def log_vote(model_tag: str, score: int, q: str, a: str):
    row = [datetime.utcnow().isoformat(), model_tag, score, q, a]
    header = ["timestamp", "model", "score", "question", "answer"]
    exists = os.path.isfile(CSV_FEEDBACK)
    with open(CSV_FEEDBACK, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(header)
        writer.writerow(row)

def show_feedback(key: str, model_tag: str, question: str, answer: str):
    col1, col2 = st.columns([1, 1])
    if col1.button("👍", key=f"up{key}"):
        log_vote(model_tag, 1, question, answer)
        st.toast("Thanks for the 👍!")
    if col2.button("👎", key=f"dn{key}"):
        log_vote(model_tag, -1, question, answer)
        st.toast("Appreciate the feedback!")

# ========= MAIN FLOW ==========
if prompt:
    # store user msg
    st.chat_message("user").markdown(prompt)
    st.session_state.history.append({"role": "user", "content": prompt})

    openai.beta.threads.messages.create(
        thread_id=st.session_state.thread_id, role="user", content=prompt
    )

    # run both assistants streaming side‑by‑side
    colA, colB = st.columns(2)
    with colA:
        st.markdown("#### **Model A**")
        answer_a = stream_assistant(ASSISTANT_A_ID)
        show_feedback("A" + str(len(st.session_state.tally["A"])), "A", prompt, answer_a)

    with colB:
        st.markdown("#### **Model B**")
        answer_b = stream_assistant(ASSISTANT_B_ID)
        show_feedback("B" + str(len(st.session_state.tally["B"])), "B", prompt, answer_b)

    # auto‑grade with judge model
    rubric = (
        "You are an income‑tax expert. Score each answer 0‑5 for legal accuracy, "
        "clarity and completeness. Reply only JSON like {\"A\": 4, \"B\": 3}."
    )
    judge = openai.chat.completions.create(
        model=JUDGE_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": rubric},
            {
                "role": "user",
                "content": f"QUESTION:\n{prompt}\n\nAnswer A:\n{answer_a}\n\nAnswer B:\n{answer_b}",
            },
        ],
    )
    try:
        scores = json.loads(judge.choices[0].message.content)
    except Exception:
        scores = {"A": 0, "B": 0}

    st.success(
        f"Auto‑scores → Model A **{scores['A']}**  |  Model B **{scores['B']}**",
        icon="✅",
    )

    for k in ("A", "B"):
        st.session_state.tally[k].append(scores[k])

    # add combined assistant message to history (for scrollback)
    combined_html = (
        f"<div class='bubble'><strong>Model A</strong><br>{answer_a}</div>"
        f"<div class='bubble'><strong>Model B</strong><br>{answer_b}</div>"
    )
    st.session_state.history.append({"role": "assistant", "content": combined_html})

