import os, time, json, pathlib, subprocess
PRICES={ # $ per 1M tok
 "openai:gpt-4o":(5.00,15.00),"openai:gpt-4o-mini":(0.15,0.60),
 "anthropic:claude-sonnet-4":(3.00,15.00),
 "gemini:1.5-flash":(0.35,1.05)}
CAP={"openai":float(os.getenv("RELAY_CAP_OPENAI","5")),
     "anthropic":float(os.getenv("RELAY_CAP_ANTHROPIC","5")),
     "gemini":float(os.getenv("RELAY_CAP_GEMINI","2"))}
WARN=0.80; STORE=pathlib.Path.home()/".relay_budget.json"
def _m(): return time.strftime("%Y-%m")
def _load():
  if STORE.exists():
    d=json.loads(STORE.read_text())
    if d.get("month")==_m(): return d
  return {"month":_m(),"openai":0.0,"anthropic":0.0,"gemini":0.0}
def _save(d): STORE.write_text(json.dumps(d,indent=2))
def _toast(msg):
  try: subprocess.run(["osascript","-e",f'display notification "{msg}" with title "Relay"'],check=False)
  except: pass
def init_month(): _save(_load())
def check_and_add(provider, model, in_tok, out_tok, on_warn=None, on_block=None):
  d=_load(); pin,pout=PRICES.get(f"{provider}:{model}",(0.0,0.0))
  added=(in_tok/1_000_000)*pin+(out_tok/1_000_000)*pout
  used=d.get(provider,0.0)+added; cap=CAP.get(provider,0.0)
  if cap>0 and used>=cap:
    if on_block: on_block(provider,used,cap)
    _toast(f"{provider} cap hit: ${used:.2f}/${cap:.2f}. Blocked."); return (False,used,cap,added)
  if cap>0 and used>=cap*WARN:
    if on_warn: on_warn(provider,used,cap)
    _toast(f"{provider} near cap: ${used:.2f}/${cap:.2f}")
  d[provider]=used; _save(d); return (True,used,cap,added)