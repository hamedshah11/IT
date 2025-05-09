# -------------------------------------------------------------
# PK‑Tax Assistant — Model Duel  (robust judge + JSON mode)
# -------------------------------------------------------------
import streamlit as st, openai, json, time, statistics

# ── 1. secrets ───────────────────────────────────────────────
openai.api_key   = st.secrets["OPENAI_API_KEY"]
ASSISTANT_A_ID   = st.secrets["ASSISTANT_A_ID"]
ASSISTANT_B_ID   = st.secrets["ASSISTANT_B_ID"]
JUDGE_MODEL      = "gpt-4o-mini"

# ── 2. page & theme ──────────────────────────────────────────
st.set_page_config(page_title="PK‑Tax Assistant", page_icon="💰")
st.title("🇵🇰 Income‑Tax Assistant — Model Duel")

# ── 3. session ──────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "tally" not in st.session_state:
    st.session_state.tally = {"A": [], "B": []}

if st.sidebar.button("🔄 New chat"):
    st.session_state.clear(); st.rerun()

st.sidebar.markdown("### Leaderboard")
for tag,lbl in (("A","Model A"),("B","Model B")):
    arr = st.session_state.tally[tag]
    if arr:
        st.sidebar.write(f"{lbl}: {statistics.mean(arr):.2f} on {len(arr)} Qs")

for r,m in st.session_state.history:
    st.chat_message(r).markdown(m, unsafe_allow_html=True)

prompt = (st.chat_input if hasattr(st,"chat_input") else st.text_input)(
    "Ask a tax question…"
)

# ── 4. assistant helper ─────────────────────────────────────
def answer_once(assistant_id: str, q: str) -> str:
    thread = openai.beta.threads.create()
    openai.beta.threads.messages.create(thread_id=thread.id, role="user", content=q)
    run = openai.beta.threads.runs.create(thread_id=thread.id, assistant_id=assistant_id)
    while run.status not in ("completed","failed","cancelled","expired"):
        time.sleep(0.4)
        run = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
    if run.status != "completed":
        return f"⚠️ run ended with status {run.status}"
    msg = openai.beta.threads.messages.list(thread.id, limit=1).data[0]
    return msg.content[0].text.value

# ── 5. main flow ────────────────────────────────────────────
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

    # ── 6. robust judge (JSON mode + error handling) ────────
    judge_scores = {"A": 0, "B": 0}   # default
    try:
        judge_resp = openai.chat.completions.create(
            model         = JUDGE_MODEL,
            temperature   = 0,
            response_format = {"type": "json_object"},   # JSON mode 🗸 :contentReference[oaicite:0]{index=0}
            messages=[
                {"role":"system",
                 "content":
                 "You are an expert evaluator. Return ONLY valid JSON like "
                 "{\"A\":3,\"B\":5} (integers 0‑5). No other text."},
                {"role":"user",
                 "content":f"QUESTION: {prompt}\n\nAnswer A:\n{ans_a}\n\nAnswer B:\n{ans_b}"}
            ],
        )
        judge_scores = judge_resp.choices[0].message.content
        judge_scores = json.loads(judge_scores)           # guaranteed JSON in JSON‑mode
        assert all(k in judge_scores for k in ("A","B"))
    except Exception as e:
        st.toast(f"⚠️ Judge failed ({e}); defaulting to 0,0")

    st.success(f"Auto‑scores → A **{judge_scores['A']}** | B **{judge_scores['B']}**")
    for k in ("A","B"):
        st.session_state.tally[k].append(judge_scores[k])

    # save bubbles
    html = (f"<div style='border-left:4px solid #0b8913;padding:8px'>"
            f"<b>Model A</b><br>{ans_a}</div>"
            f"<div style='border-left:4px solid #FFD700;padding:8px;margin-top:6px'>"
            f"<b>Model B</b><br>{ans_b}</div>")
    st.session_state.history.append(("assistant", html))
