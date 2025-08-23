# /Users/joebudds/Documents/Updated_Relay_Files/app.py
# Relay Dashboard (Jenny / Claude / Luna)
# - Clean API vs Guard separation
# - Env key sanitizing (no newline/whitespace bugs)
# - Clear Model vs Agent status, no cross-contamination
# - Sidebar Agent Boxes: Hold-to-activate (3s), Join/End convo, Talk toggle
# - Memory/CI, Uploads, Voice (macOS say), optional multi-LLM fanout
# - Works even if agent_fs_guard.py is missing (safe stubs)

import os, re, json, time, shlex, subprocess, typing, requests
from datetime import datetime, timezone
from pathlib import Path
import streamlit as st

def ensure_agent_state():
    st.session_state.setdefault("agent_status", {})
    for n in ["Jenny","Luna","Claude"]:
        st.session_state["agent_status"].setdefault(n, {"running": False, "token": "", "last": ""})

from relay_budget import init_month, check_and_add

# -- BUDGET MONKEYPATCH --
try:
    import requests, json
    _orig_post = requests.post
    def _estimate_tokens(payload):
        try:
            s=json.dumps(payload) if not isinstance(payload,str) else payload
            # rough est: 4 chars ≈ 1 token
            return max(1, len(s)//4)
        except Exception:
            return 400
    def _detect(url, payload):
        u = (url or "")
        if "openai.com" in u:
            prov="openai"; model=(payload.get("model") if isinstance(payload,dict) else "gpt-4o") or "gpt-4o"
        elif "anthropic.com" in u:
            prov="anthropic"; model=(payload.get("model") if isinstance(payload,dict) else "claude-sonnet-4") or "claude-sonnet-4"
        elif "generativelanguage.googleapis.com" in u:
            prov="gemini"; model="1.5-flash"
        else:
            prov="other"; model="unknown"
        return prov, model
    def _warn(p,used,cap):
        try: st.warning(f"⚠️ {p} nearing cap: ${used:.2f}/${cap:.2f}")
        except Exception: pass
    def _block(p,used,cap):
        try: st.error(f"⛔ {p} cap hit (${used:.2f}/${cap:.2f}). Blocking call.")
        except Exception: pass
    def post(url, *a, **k):
        payload = k.get("json") or k.get("data") or {}
        prov, model = _detect(url, payload if isinstance(payload,dict) else {})
        if prov in ("openai","anthropic","gemini"):
            in_est = _estimate_tokens(payload)
            out_est = int((payload.get("max_tokens") if isinstance(payload,dict) else 512) or 512)
            ok,used,cap,added = check_and_add(prov, model, in_est, out_est, _warn, _block)
            if not ok:
                class _Fake: status_code=402; text="Budget cap reached"; 
                def json(self): return {"error":"budget_cap","provider":prov,"used":used,"cap":cap}
                return _Fake()
        return _orig_post(url, *a, **k)
    requests.post = post
except Exception as _e:
    pass
# -- /BUDGET MONKEYPATCH --

# ----- Pricing & model selector -----
PRICES = {
    # OpenAI
    "gpt-4o":            {"provider":"OpenAI","in":5.00,"out":15.00,"ctx":"128k"},   # $/MTok
    "gpt-4o-mini":       {"provider":"OpenAI","in":0.15,"out":0.60,"ctx":"128k"},
    # Anthropic
    "claude-sonnet-4":   {"provider":"Anthropic","in":3.00,"out":15.00,"ctx":"200k"},
    # Add more as you like...
}
def cheapest_model():
    # rank by (in+out) per MTok
    return min(PRICES.items(), key=lambda kv: kv[1]["in"]+kv[1]["out"])[0]

def key_status():
    return {
        "OpenAI":   bool(os.getenv("OPENAI_API_KEY")),
        "Anthropic":bool(os.getenv("ANTHROPIC_API_KEY")),
        "Gemini":   bool(os.getenv("GEMINI_API_KEY")),
    }

# =========================
# SAFE GUARD IMPORT (with stubs)
# =========================
GUARD_OK = True
try:
    from agent_fs_guard import (
        list_agents,
        register_agent,
        issue_token,
        list_active_tokens,
        revoke_token,
        check_token,
        DEFAULT_SCOPES,
    )
except Exception:
    GUARD_OK = False
    DEFAULT_SCOPES = {"read","write","list"}
    _TOKENS: dict[str, dict] = {}
    def list_agents(): return ["Jenny","Claude","Luna"]
    def register_agent(name, desc=""): return True
    def issue_token(agent: str, scopes: list[str]|None=None, ttl_minutes: int=30):
        import secrets, time as _t
        tok = "t_"+secrets.token_hex(16)
        exp = _t.time() + ttl_minutes*60
        _TOKENS[tok] = {"agent":agent,"scopes":set(scopes or ["read"]), "exp":exp}
        return tok, {"expires_at": datetime.utcfromtimestamp(exp).isoformat()+"Z"}
    def list_active_tokens(agent: str):
        import time as _t
        now = _t.time()
        return {t:v for t,v in _TOKENS.items() if v["agent"]==agent and v["exp"]>now}
    def revoke_token(tok: str): return _TOKENS.pop(tok, None) is not None
    def check_token(tok: str, needed_scope: str, expected_agent: str|None=None):
        import time as _t
        v = _TOKENS.get(tok); 
        return bool(v and v["exp"]>_t.time() and (expected_agent in (None, v["agent"])) and needed_scope in v["scopes"])

# =========================
# UTIL: Now / Files
# =========================
APP_DIR = Path.home() / "Documents" / "Updated_Relay_Files"
APP_DIR.mkdir(parents=True, exist_ok=True)
def _now_iso(): return datetime.now(timezone.utc).isoformat()

# =========================
# ENV KEYS: sanitize + load
# =========================
def _sanitize_env(v: str|None) -> str:
    if not v: return ""
    # strip CR/LF, tabs, spaces, quotes
    return re.sub(r'[\r\n\t ]+', '', v.strip().strip('"').strip("'"))

def load_env_keys() -> dict:
    # normalize alternate names → primary names
    if os.getenv("OPENAI_APIKEY") and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_APIKEY")
    if os.getenv("OPENAI_KEY") and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_KEY")

    for k in ("OPENAI_API_KEY","ANTHROPIC_API_KEY","GEMINI_API_KEY"):
        if os.getenv(k):
            os.environ[k] = _sanitize_env(os.getenv(k))

    return {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY",""),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY",""),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY",""),
    }

ENV = load_env_keys()

def get_api_status():
    return {
        "OpenAI":  bool(ENV.get("OPENAI_API_KEY")),
        "Anthropic": bool(ENV.get("ANTHROPIC_API_KEY")),
        "Gemini":   bool(ENV.get("GEMINI_API_KEY")),
    }

# =========================
# STREAMLIT SETTINGS + CSS
# =========================
ensure_agent_state()
init_month()
st.set_page_config(
    page_title="Relay Dashboard — Jenny / Claude / Luna",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Relay Dashboard with clean API/Guard separation."}
)

st.markdown("""
<style>
h1, h2, h3 { font-weight:700 !important; color:#111 !important; }
section[data-testid="stSidebar"] h3 { font-weight:700 !important; color:#111 !important; }
.badge-key { display:inline-flex;align-items:center;gap:6px;padding:2px 8px;border-radius:999px;border:1px solid #c6e7c6;background:#e9f8ef;font-weight:600;}
.badge-key.bad {border-color:#f2b7b7;background:#fdeaea;}
:root{ --bg:#0b1b2b; --card:#10233a; --ring:#1f3b5b; --ink:#eaf2ff; --muted:#93a8c9;
       --ok:#22c55e; --err:#ef4444; --warn:#f59e0b; --accent:#60a5fa; }
* { box-sizing: border-box; }
/* Darker, bolder section headers */
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
  color:#111 !important; font-weight:700 !important;
}
/* Key pills row */
.pill  {display:inline-flex;align-items:center;gap:6px;
        padding:6px 10px;border-radius:999px;border:1px solid #ddd;
        font-weight:600;margin-right:8px}
.ok  {background:#e9f8ef;border-color:#b8e8c7;color:#0a7a28}
.bad {background:#fdeaea;border-color:#f2b7b7;color:#a50000}
.pill .name {min-width:90px; display:inline-block;}
/* Top toolbar */
.toolbar {display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.toolbar .left {display:flex;align-items:center;gap:12px}
.gear {font-weight:700}
h1,h2,h3 { color: var(--ink); }
.small { color: var(--muted); font-size: 12px; }
.pill-ok { border-color:#b8e8c7; background:#e9f8ef; color:#0a7a28; }
.pill-bad { border-color:#f2b7b7; background:#fdeaea; color:#a50000; }
.pill-warn { border-color:#f7e3b0; background:#fff7e0; color:#8a6d1a; }
.box { border:2px solid var(--ring); background:var(--card); border-radius:14px; padding:10px; }
.agent-name { font-weight:800; font-size:16px; }
.agent-row { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
.dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
.dot.ok{ background: var(--ok); } .dot.err{ background: var(--err); } .dot.idle{ background:#6b7280; }
.btn { display:inline-block; padding:6px 10px; border-radius:10px; border:1px solid #29486d; background:#132945; color:#cfe3ff; margin-right:6px; cursor:pointer; }
.btn:hover{ filter:brightness(1.08); }
.progress-wrap { background:#143253; border-radius:999px; height:8px; overflow:hidden; margin:6px 0 2px; }
.fill { height:100%; width:0%; background: linear-gradient(90deg, #4f9cff, #22c55e); }
.conv-box { height: 520px; overflow-y:auto; border:1px solid #ddd; background:#fafafa;
            border-radius:8px; padding:12px; }
hr { border: 0; border-top: 1px solid #234; margin: 8px 0; }
</style>
""", unsafe_allow_html=True)

# =========================
# SESSION STATE
# =========================
def _ss(key, default): 
    if key not in st.session_state: st.session_state[key] = default

AGENTS = ["Jenny","Claude","Luna"]
_ss("agent_status", {a:"idle" for a in AGENTS})         # idle | ready | error
_ss("agent_progress", {a:0 for a in AGENTS})            # 0..100
_ss("agent_hold_start", {a:0.0 for a in AGENTS})        # timestamp
_ss("in_combo", {a:False for a in AGENTS})
_ss("talk_on", {a:True for a in AGENTS})
_ss("guard_tokens", {a:"" for a in AGENTS})
_ss("conversation_history", [])
_ss("formatted_conversation","")
_ss("errors", [])
_ss("voice_enabled", True)
_ss("voice_name", "Samantha")
_ss("voice_rate", 175)

# =========================
# TTS (macOS say)
# =========================
def tts_speak(text: str, enabled: bool = True, voice: str = "Samantha", rate: int = 175):
    if not enabled or not text: return
    try:
        words_per_min = max(120, min(300, int(rate)))
        cmd = f'say -v {shlex.quote(voice)} -r {words_per_min} {shlex.quote(text)}'
        subprocess.Popen(cmd, shell=True)
    except Exception:
        pass

# =========================
# MESSAGES / MEMORY (light)
# =========================
MEMORY_LOG = APP_DIR / "memory_log.jsonl"
def add_conv(role_label: str, text: str, color: str):
    block = f"<div style='margin-bottom:8px'><b style='color:{color}'>{role_label}:</b> {text}</div>"
    st.session_state.formatted_conversation += block
def append_jsonl(path: Path, obj: dict): 
    with path.open("a", encoding="utf-8") as fh: fh.write(json.dumps(obj, ensure_ascii=False)+"\n")

# =========================
# MODEL CALLS (Separated)
# =========================
def call_openai(messages: list[dict]) -> str:
    key = ENV.get("OPENAI_API_KEY","")
    if not key: return "(OpenAI disabled: missing API key)"
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model":"gpt-4o-mini", "messages":messages, "max_tokens":300},
            timeout=25
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        if r.status_code == 401:
            return "(OpenAI error: invalid API key)"
        return f"(OpenAI HTTP {r.status_code}) {r.text[:150]}"
    except Exception as e:
        return f"(OpenAI request error) {e}"

def call_anthropic(messages: list[dict], system: str="") -> str:
    key = ENV.get("ANTHROPIC_API_KEY","")
    if not key: return "(Anthropic disabled: missing API key)"
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version":"2023-06-01", "content-type":"application/json"},
            json={"model":"claude-3-5-sonnet-20240620","system":system,"messages":messages,"max_tokens":300},
            timeout=25
        )
        if r.status_code == 200:
            return r.json()["content"][0]["text"]
        if r.status_code == 401:
            return "(Anthropic error: invalid API key)"
        return f"(Anthropic HTTP {r.status_code}) {r.text[:150]}"
    except Exception as e:
        return f"(Anthropic request error) {e}"

def call_gemini(prompt: str) -> str:
    key = ENV.get("GEMINI_API_KEY","")
    if not key: return "(Gemini disabled: missing API key)"
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={key}",
            headers={"Content-Type":"application/json"},
            json={"contents":[{"parts":[{"text":prompt}]}]},
            timeout=25
        )
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        if r.status_code == 401:
            return "(Gemini error: invalid API key)"
        return f"(Gemini HTTP {r.status_code}) {r.text[:150]}"
    except Exception as e:
        return f"(Gemini request error) {e}"

def build_messages(user_text: str, history: list[dict]) -> list[dict]:
    sys = "You are Jenny, helpful, concise, and kind. Mirror the user's energy and keep it simple."
    msgs = [{"role":"system","content":sys}]
    for m in history[-8:]:
        msgs.append(m)
    msgs.append({"role":"user","content":user_text})
    return msgs

# =========================
# SIDEBAR: STATUS + AGENT BOXES
# =========================
st.sidebar.markdown("### ⚙️ Status")

api_stat = get_api_status()
cols = st.sidebar.columns(3)
for (name, ok), c in zip(api_stat.items(), cols):
    with c:
        st.markdown(f"<div class='pill {'pill-ok' if ok else 'pill-bad'}'>{name}: {'✅' if ok else '❌ Missing key'}</div>", unsafe_allow_html=True)

st.sidebar.markdown("### 🛡️ Guard")
if "Jenny" not in list_agents():
    try: register_agent("Jenny","Core assistant")
    except Exception: pass

pick_agent = st.sidebar.selectbox("Agent for Token Ops", AGENTS, index=0)
tok = st.sidebar.text_input("Paste token (optional)", value=st.session_state["guard_tokens"].get(pick_agent,""), type="password")
st.session_state["guard_tokens"][pick_agent] = tok

colA, colB = st.sidebar.columns(2)
with colA:
    if st.button("Issue Token", use_container_width=True):
        t, info = issue_token(agent=pick_agent, scopes=["read","write","list"], ttl_minutes=60)
        st.session_state["guard_tokens"][pick_agent] = t
        st.success("Token issued.")
        st.code(t, language="text")
with colB:
    act = list_active_tokens(pick_agent)
    if act:
        tok_to_revoke = st.selectbox("Active tokens", options=list(act.keys()), index=0)
        if st.button("Revoke", use_container_width=True):
            if revoke_token(tok_to_revoke):
                st.success("Revoked.")
            else:
                st.error("Revoke failed.")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🤖 Agents")

def render_agent_box(name: str):
    status = st.session_state.get("agent_status", {}).get(name, {"running": False, "token": "", "last": ""})
    dot = f"<span class='dot {'ok' if status=='ready' else ('err' if status=='error' else 'idle')}'></span>"
    with st.sidebar.container(border=False):
        st.markdown(f"<div class='box'>", unsafe_allow_html=True)
        st.markdown(f"<div class='agent-row'>{dot} <span class='agent-name'>{name}</span>"
                    f"<span style='margin-left:auto' class='small'>{'Ready' if status=='ready' else ('Failure' if status=='error' else 'Idle')}</span></div>", unsafe_allow_html=True)
        # progress
        prog_key = f"prog_{name}"
        progress = st.session_state["agent_progress"][name]
        st.markdown(f"<div class='progress-wrap'><div class='fill' style='width:{progress}%;'></div></div>", unsafe_allow_html=True)

        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            if st.button("Hold 3s", key=f"hold_{name}", use_container_width=True):
                st.session_state["agent_hold_start"][name] = time.time()
                # simulate hold progress
                for p in range(0, 101, 5):
                    st.session_state["agent_progress"][name] = p
                    time.sleep(0.06)
                    st.experimental_rerun()
        with c2:
            if st.button("Join", key=f"join_{name}", use_container_width=True):
                st.session_state["in_combo"][name] = True
                st.toast(f"{name} joined convo 📞", icon="✅")
        with c3:
            if st.button("End", key=f"end_{name}", use_container_width=True):
                st.session_state["in_combo"][name] = False
                st.toast(f"{name} left convo ⛔", icon="⚠️")

        # after potential hold, decide success/failure
        start = st.session_state["agent_hold_start"][name]
        if start and (time.time() - start) >= 3:
            ok = True if name!="Luna" else (time.time() % 10 >= 1)  # 90% pass feel
            st.session_state["agent_status"][name] = "ready" if ok else "error"
            st.session_state["agent_progress"][name] = 100 if ok else 100
            st.session_state["agent_hold_start"][name] = 0.0
            st.experimental_rerun()

        # talk toggle
        st.session_state["talk_on"][name] = st.checkbox("Talk", value=st.session_state["talk_on"][name], key=f"talk_{name}")
        st.markdown("</div>", unsafe_allow_html=True)  # box end

for a in AGENTS:
    render_agent_box(a)

# =========================
# TITLE + PAGE
# =========================
st.markdown("<div class='toolbar'><div class='left'><span class='gear'>⚙️ Settings</span></div><div><span class='gear'>🔑 Keys</span></div></div>", unsafe_allow_html=True)

# Keys row
ks = key_status()
def pill(name, ok):
    cls = "ok" if ok else "bad"
    icon = "🔑" if ok else "❗"
    label = f"{name}: {'OK' if ok else 'No key'}"
    return f"<span class='pill {cls}'><span>{icon}</span><span class='name'>{label}</span></span>"
row = "".join([pill("OpenAI", ks["OpenAI"]), pill("Anthropic", ks["Anthropic"]), pill("Gemini", ks["Gemini"])])
st.markdown(row, unsafe_allow_html=True)

st.title("Relay Dashboard")

# =========================
# UPLOADS
# =========================
st.subheader("📎 Upload Documents")
up = st.file_uploader("Drop files", type=["txt","md","json","csv","py","log","pdf","jpg","jpeg","png","doc","docx"], accept_multiple_files=True)
if up:
    for f in up:
        name = f.name
        data = f.read()
        snippet = ""
        if any(name.lower().endswith(ext) for ext in (".txt",".md",".json",".csv",".py",".log")):
            try: snippet = data.decode("utf-8", errors="replace")[:400]
            except Exception: snippet = "(could not decode text)"
        elif any(name.lower().endswith(ext) for ext in (".jpg",".jpeg",".png")):
            snippet = "(image uploaded)"
        elif name.lower().endswith(".pdf"):
            snippet = "(PDF uploaded)"
        else:
            snippet = "(uploaded)"
        add_conv("Document", f"({name}) {snippet}", "#444")
        st.success(f"Processed: {name}")

# =========================
# CONVERSATION
# =========================
st.subheader("🧾 Budget & Alerts")
st.caption("Warns at 80%, blocks at 100%. Caps via env: RELAY_CAP_OPENAI / _ANTHROPIC / _GEMINI.")

st.subheader("💬 Conversation")

# ----- Model picker with pricing -----
st.subheader("🧰 Model & Cost")
opts = list(PRICES.keys()) + ["(cheapest)"]
choice = st.selectbox("Choose model", opts, index=opts.index("(cheapest)"))
model_selected = cheapest_model() if choice=="(cheapest)" else choice
meta = PRICES[model_selected]
st.caption(f"Using **{model_selected}** ({meta['provider']}) — input ${meta['in']}/MTok, output ${meta['out']}/MTok, ctx {meta['ctx']}.")

# TODO: pass `model_selected` into your request code where you call the provider
conv_container = st.container()
with conv_container:
    if st.session_state.formatted_conversation:
        st.markdown(f"<div class='conv-box'>{st.session_state.formatted_conversation}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='conv-box' style='display:flex;align-items:center;justify-content:center;color:#666;'>Start a convo on the right →</div>", unsafe_allow_html=True)

msg = st.text_area("Type your message:", height=120, placeholder="Ask anything…")
send_btn = st.button("📤 Send")

if send_btn and msg.strip():
    add_conv("You", msg.strip(), "#0b6efd")
    st.session_state.conversation_history.append({"role":"user","content":msg.strip()})

    # Decide which agents are in-combo
    active = [a for a in AGENTS if st.session_state["in_combo"][a] and st.session_state["agent_status"][a]=="ready"]

    replies: dict[str,str] = {}
    messages = build_messages(msg.strip(), st.session_state.conversation_history)

    if "Jenny" in active and ENV.get("OPENAI_API_KEY"):
        replies["Jenny"] = call_openai(messages)
    if "Claude" in active:
        # Claude reply via Anthropic if key, else emulate politely
        if ENV.get("ANTHROPIC_API_KEY"):
            replies["Claude"] = call_anthropic([m for m in messages if m["role"]!="system"], system=messages[0]["content"])
        else:
            replies["Claude"] = "(Claude disabled: missing Anthropic key)"
    if "Luna" in active:
        # Use Gemini (if available) otherwise simple echo
        if ENV.get("GEMINI_API_KEY"):
            replies["Luna"] = call_gemini(msg.strip())
        else:
            replies["Luna"] = "(Luna disabled: missing Gemini key)"

    if not active:
        replies["System"] = "No agent joined. Swipe/Join on sidebar first."

    # Render replies
    for who, text in replies.items():
        add_conv(who, text, "#b00020" if who in ("Jenny","Claude","Luna") else "#333")
        st.session_state.conversation_history.append({"role":"assistant","content":text})
        # speak primary reply if agent Talk is on
        if who in AGENTS and st.session_state["talk_on"][who]:
            tts_speak(text, enabled=st.session_state["voice_enabled"], voice=st.session_state["voice_name"], rate=st.session_state["voice_rate"])

    # log memory
    try:
        append_jsonl(MEMORY_LOG, {"ts":_now_iso(), "msg":msg.strip(), "replies":replies})
    except Exception:
        pass

# =========================
# FOOTER + HINTS
# =========================
st.markdown("---")
st.markdown("**Hints**: Use the sidebar → `Hold 3s` to prep an agent (border turns green on success). `Join` to bring them into the convo. Keys are read **only** from environment; Guard tokens are local and separate. Missing keys won’t block other providers.")
