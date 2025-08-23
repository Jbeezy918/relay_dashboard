#!/usr/bin/env python3
"""
agent_orchestrator.py
- Gives Claude a voice notification on finish.
- Ensures Jenny & Luna are registered + tokened.
- Approval gate: Claude asks Jenny & Luna; majority approve => proceed.
Usage:
  python3 agent_orchestrator.py --wake
  python3 agent_orchestrator.py --announce "Training sync completed."
  python3 agent_orchestrator.py --approve "Push new app build to prod after tests pass."
  python3 agent_orchestrator.py --launch-app   # optional: start Streamlit
"""
import os, shlex, subprocess, json, time, argparse, sys
from pathlib import Path
from datetime import datetime, timezone

# ---------- ENV / GUARD ----------
APP_DIR = Path.home()/ "Documents" / "Updated_Relay_Files"
os.chdir(APP_DIR)

USE_GUARD_PRO = os.getenv("USE_GUARD_PRO","1") == "1"
if USE_GUARD_PRO:
    from agent_fs_guard_pro import list_agents, register_agent, issue_token, list_active_tokens, revoke_token, check_token, DEFAULT_SCOPES, seconds_left
else:
    from agent_fs_guard import list_agents, register_agent, issue_token, list_active_tokens, revoke_token, check_token, DEFAULT_SCOPES
    def seconds_left(_): return None

# ---------- TTS (Claude + friends) ----------
def tts_say(text: str, voice="Samantha", rate_wpm=185):
    """Prefer ElevenLabs if configured; else macOS 'say'; else print."""
    if not text: return
    el_key = os.getenv("ELEVENLABS_API_KEY")
    el_voice = os.getenv("ELEVENLABS_VOICE_ID")
    try:
        if el_key and el_voice:
            import requests
            r = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{el_voice}",
                headers={"xi-api-key": el_key, "accept":"audio/mpeg","content-type":"application/json"},
                json={"text": text, "model_id":"eleven_monolingual_v1","voice_settings":{"stability":0.55,"similarity_boost":0.55}}
            )
            r.raise_for_status()
            out = APP_DIR / f"_tts_claude_{int(time.time())}.mp3"
            out.write_bytes(r.content)
            # play (macOS, afplay; else fallback to mpg123 if installed)
            try:
                subprocess.run(["afplay", str(out)], check=False)
            except Exception:
                subprocess.run(["mpg123", str(out)], check=False)
            return
        # macOS fallback
        if sys.platform == "darwin":
            cmd = f'say -v {shlex.quote(voice)} -r {int(rate_wpm)} {shlex.quote(text)}'
            subprocess.Popen(cmd, shell=True)
            return
    except Exception:
        pass
    print(f"[TTS] {text}")

# ---------- Agent helpers ----------
AGENTS = ["Jenny","Luna","Claude"]

def ensure_agents_and_tokens(ttl_minutes=120, scopes=("read","write","list")):
    # register if missing; issue tokens if none active
    existing = set(list_agents())
    for a in AGENTS:
        if a not in existing:
            register_agent(a, notes=f"Auto-registered {a}")
    issued = {}
    for a in AGENTS:
        active = list_active_tokens(agent=a)
        # keep the newest active if present
        if active:
            tok = sorted(active.items(), key=lambda kv: kv[1].get("expires_at",""))[-1][0]
            issued[a] = tok
        else:
            tok, _info = issue_token(agent=a, scopes=list(scopes), ttl_minutes=ttl_minutes)
            issued[a] = tok
    return issued

# ---------- LLM calls (Jenny/Luna approvers) ----------
def openai_chat(prompt: str) -> str | None:
    key = os.getenv("OPENAI_API_KEY")
    if not key: return None
    import requests
    body = {"model":"gpt-4o-mini","messages":[
        {"role":"system","content":"You are Jenny, a pragmatic reviewer. Approve only if the plan is safe, reversible, and logged. Answer strictly with APPROVE or HOLD and one short reason."},
        {"role":"user","content":prompt}
    ],"max_tokens":120}
    try:
        r = requests.post("https://api.openai.com/v1/chat/completions",
                          headers={"Authorization":f"Bearer {key}"}, json=body, timeout=25)
        if r.status_code==200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None
    return None

def anthropic_chat(prompt: str) -> str | None:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key: return None
    import requests
    body = {"model":"claude-3-5-sonnet-20240620","max_tokens":200,
            "system":"You are Luna, a cautious second reviewer. Reply only: APPROVE or HOLD, plus one-line reason.",
            "messages":[{"role":"user","content":prompt}]}
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
                          headers={"x-api-key":key,"anthropic-version":"2023-06-01","content-type":"application/json"},
                          json=body, timeout=25)
        if r.status_code==200:
            return r.json()["content"][0]["text"].strip()
    except Exception:
        return None
    return None

def normalize_vote(text: str | None) -> str:
    if not text: return "HOLD"
    t = text.upper()
    return "APPROVE" if "APPROVE" in t and "HOLD" not in t else ("HOLD" if "HOLD" in t else "HOLD")

def approval_gate(task_summary: str) -> dict:
    """Ask Jenny(OpenAI) and Luna(Anthropic). Majority rules. Returns dict with votes."""
    j = openai_chat(task_summary)
    l = anthropic_chat(task_summary)
    j_vote = normalize_vote(j)
    l_vote = normalize_vote(l)
    votes = [j_vote, l_vote]
    decision = "APPROVE" if votes.count("APPROVE") >= 1 and "HOLD" not in votes else "HOLD"  # conservative tie→HOLD unless at least one approve and none explicit hold (adjust if desired)
    return {"jenny_raw": j, "luna_raw": l, "jenny": j_vote, "luna": l_vote, "decision": decision}

# ---------- Streamlit launcher (optional) ----------
def launch_streamlit():
    # runs in background; open browser
    try:
        subprocess.Popen(["streamlit","run","app.py"], cwd=str(APP_DIR))
        tts_say("Dashboard launching.")
    except Exception as e:
        print("Launch failed:", e)

# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wake", action="store_true", help="Register agents and issue tokens")
    ap.add_argument("--announce", type=str, help="Claude speaks this line")
    ap.add_argument("--approve", type=str, help="Ask Jenny & Luna to approve this task")
    ap.add_argument("--launch-app", action="store_true", help="Start Streamlit dashboard")
    args = ap.parse_args()

    if args.wake:
        tokens = ensure_agents_and_tokens()
        # save a small token snapshot (local only)
        snap = APP_DIR / "_agent_tokens.json"
        snap.write_text(json.dumps(tokens, indent=2))
        tts_say("Agents awake. Tokens issued.")

    if args.launch_app:
        launch_streamlit()

    if args.approve:
        res = approval_gate(args.approve)
        summary = f"Jenny: {res['jenny']} | Luna: {res['luna']} → Decision: {res['decision']}"
        print(summary)
        tts_say(f"Review result. {res['decision'].title()}.")
        # if HOLD, make it loud
        if res["decision"] == "HOLD":
            tts_say("Stopping for approval. Please review in the dashboard.")
        else:
            tts_say("Green light. Continuing.")

    if args.announce:
        tts_say(args.announce)

    if not any([args.wake, args.launch_app, args.approve, args.announce]):
        ap.print_help()

if __name__ == "__main__":
    main()