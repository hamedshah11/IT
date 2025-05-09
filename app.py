# -------------------------------------------------------------
# PK‑Tax Assistant — Model Duel  (judge = o3‑mini)
# -------------------------------------------------------------
import streamlit as st, openai, json, time, statistics

# --- 1. secrets -------------------------------------------------
openai.api_key   = st.secrets["OPENAI_API_KEY"]
ASSISTANT_A_ID   = st.secrets["ASSISTANT_A_ID"]
ASSISTANT_B_ID   = st.secrets["ASSISTANT_B_ID"]
JUDGE_MODEL      = "o3-mini"          # ←  use the o3‑mini model

# --- 2. page ----------------------------------------------------
st.set_page_config(page_title="PK‑Tax Assistant", page_icon="💰")
st.title("🇵🇰 Income‑Tax Assistant — Model Duel")

# --- 3. session -------------------------------------------------
if "history" not in st.session_state:
    st.session_state.history = []
if "tally" not in st.session_state:
    st.session_state.tally = {"A": [], "B": []}

if st.sidebar.button("🔄 New chat"):
    st.session_state.clear(); st.rerun()

def sidebar_scores():
    st.sidebar.markdown("### Leaderboard")
    for tag,lbl in (("A","Model A"),("B","Model B")):
        arr = st.session_state.tally[tag]
        if arr:
            st.sidebar.write(f"{lbl}: {statistics.mean(arr):.2f} on {len(arr)} Qs")
sidebar_scores()

# --- 4. replay --------------------------------------------------
for r,m in st.session_state.history:
    st.chat_message(r).markdown(m, unsafe_allow_html=True)

# --- 5. prompt --------------------------------------------------
prompt = (st.chat_input if hasattr(st,"chat_input") else st.text_input)(
    "Ask a tax question…"
)

# --- 6. helper: single run -------------------------------------
def answer_once(assistant_id: str, q: str) -> str:
    thread = openai.beta.threads.create()
    openai.beta.threads.messages.create(thread.id, role="user", content=q)
    run = openai.beta.threads.runs.create(thread.id, assistant_id=assistant_id)
    while run.status != "completed":
        time.sleep(0.4)
        run = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
    msg = openai.beta.threads.messages.list(thread.id, limit=1).data[0]
    return msg.content[0].text.value

# --- 7. main ----------------------------------------------------
if prompt:
    st.chat_message("user").markdown(prompt)
    st.session_state.history.append(("user", prompt))

    col1,col2 = st.columns(2)
    with col1:
        st.write("#### Model A")
        ans_a = answer_once(ASSISTANT_A_ID, prompt)
        st.write(ans_a)
    with col2:
        st.write("#### Model B")
        ans_b = answer_once(ASSISTANT_B_ID, prompt)
        st.write(ans_b)

    # ----- judge with o3‑mini -----------------------------------
    try:
        judge_json = openai.chat.completions.create(
            model=JUDGE_MODEL,
            temperature=0,
            response_format={"type":"json_object"},
            messages=[
                {"role":"system",
                 "content":"Return ONLY JSON like {\"A\":n,\"B\":n} with integers 0‑5."},
                {"role":"user",
                 "content":f"Q:{prompt}\n\nA:{ans_a}\n\nB:{ans_b}"},
            ],
        ).choices[0].message.content
        scores = json.loads(judge_json)
    except Exception as e:
        st.toast(f"⚠️ Judge failed: {e}")
        scores = {"A": 0, "B": 0}

    st.success(f"Auto‑scores → A **{scores['A']}** | B **{scores['B']}**")
    for tag in ("A","B"):
        st.session_state.tally[tag].append(scores[tag])

    # store bubbles
    html = (f"<div style='border-left:4px solid #0b8913;padding:8px'>"
            f"<b>Model A</b><br>{ans_a}</div>"
            f"<div style='border-left:4px solid #FFD700;padding:8px;margin-top:6px'>"
            f"<b>Model B</b><br>{ans_b}</div>")
    st.session_state.history.append(("assistant", html))

    sidebar_scores()      # refresh sidebar with new averages
