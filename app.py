# -------------------------------------------------------------
# PK‑Tax Assistant — Model Duel (one new thread per question)
# -------------------------------------------------------------
import streamlit as st, openai, json, time, statistics, os

# ── 1.  secrets ───────────────────────────────────────────────
openai.api_key   = st.secrets["OPENAI_API_KEY"]
ASSISTANT_A_ID   = st.secrets["ASSISTANT_A_ID"]
ASSISTANT_B_ID   = st.secrets["ASSISTANT_B_ID"]
JUDGE_MODEL      = "gpt-4o-mini"

# ── 2.  page ui  ──────────────────────────────────────────────
st.set_page_config(page_title="PK‑Tax Assistant", page_icon="💰")
st.title("🇵🇰 Income‑Tax Assistant — Model Duel")

# ── 3.  session state ────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "tally" not in st.session_state:
    st.session_state.tally = {"A": [], "B": []}

# reset
if st.sidebar.button("🔄 New chat"):
    st.session_state.clear(); st.rerun()

# leaderboard
st.sidebar.markdown("### Leaderboard")
for tag,lbl in (("A","Model A"),("B","Model B")):
    data = st.session_state.tally[tag]
    if data:
        st.sidebar.write(f"{lbl}: {statistics.mean(data):.2f} on {len(data)} Qs")

# history replay
for role, txt in st.session_state.history:
    st.chat_message(role).markdown(txt, unsafe_allow_html=True)

# prompt input
prompt = (st.chat_input if hasattr(st,"chat_input") else st.text_input)(
    "Ask a tax question…"
)

# ── 4.  helper to call assistant synchronously ───────────────
def get_answer(assistant_id: str, question: str) -> str:
    """
    Create a fresh thread, add the user message, run the assistant,
    poll until completed, return assistant reply text.
    """
    # step 1: new thread
    thread = openai.beta.threads.create()

    # step 2: user message
    openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=question,
    )

    # step 3: start run
    run = openai.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id,
    )

    # step 4: poll until done
    while run.status not in ("completed", "failed", "cancelled", "expired"):
        time.sleep(0.4)
        run = openai.beta.threads.runs.retrieve(
            thread_id=thread.id,   # ← keyword args fix
            run_id=run.id,
        )

    if run.status != "completed":
        return f"⚠️ run finished with status {run.status}"

    # step 5: read latest assistant message
    msg = openai.beta.threads.messages.list(
        thread_id=thread.id,
        limit=1
    ).data[0]
    return msg.content[0].text.value

# ── 5.  main flow ────────────────────────────────────────────
if prompt:
    st.chat_message("user").markdown(prompt)
    st.session_state.history.append(("user", prompt))

    col1, col2 = st.columns(2)
    with col1:
        st.write("#### Model A")
        ans_a = get_answer(ASSISTANT_A_ID, prompt)
        st.write(ans_a)
    with col2:
        st.write("#### Model B")
        ans_b = get_answer(ASSISTANT_B_ID, prompt)
        st.write(ans_b)

    # auto‑judge
    judge = openai.chat.completions.create(
        model=JUDGE_MODEL,
        temperature=0,
        messages=[
            {"role":"system","content":
             "Score A and B 0‑5 for accuracy, clarity, completeness. "
             "Return JSON {\"A\":x,\"B\":y}."},
            {"role":"user",
             "content":f"Q:{prompt}\n\nA:{ans_a}\n\nB:{ans_b}"},
        ])
    try:
        scores = json.loads(judge.choices[0].message.content)
    except Exception:
        scores = {"A": 0, "B": 0}

    st.success(f"Auto‑scores → A **{scores['A']}** | B **{scores['B']}**")
    for tag in ("A","B"):
        st.session_state.tally[tag].append(scores[tag])

    # log answers
    html = (f"<div style='border-left:4px solid #0b8913;padding:8px;'>"
            f"<b>Model A</b><br>{ans_a}</div>"
            f"<div style='border-left:4px solid #FFD700;padding:8px;margin-top:6px;'>"
            f"<b>Model B</b><br>{ans_b}</div>")
    st.session_state.history.append(("assistant", html))
