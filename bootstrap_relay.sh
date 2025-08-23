#!/bin/zsh
set -euo pipefail

# --- 0) Clean Claude token mode ---
claude /logout >/dev/null 2>&1 || true
unset CLAUDE_API_TOKEN CLAUDE_TOKEN CLAUDE_SESSION OPENAI_KEY OPENAI_APIKEY

mkdir -p ~/api_keys_secure
VAULT=~/api_keys_secure/load_keys.sh

# --- 1) Ensure keys present (prompt if missing) ---
if [ ! -f "$VAULT" ]; then
  read -s "OA?Paste NEW OPENAI key: "; echo
  read -s "AN?Paste NEW ANTHROPIC key: "; echo
  cat > "$VAULT" <<EOF
export OPENAI_API_KEY="$(printf '%s' "$OA" | tr -d '\r\n\t ')"
export ANTHROPIC_API_KEY="$(printf '%s' "$AN" | tr -d '\r\n\t ')"
echo "✅ Keys loaded"
EOF
fi
source "$VAULT"

# --- 2) Sanity checks (expect 200) ---
_openai_status=$(curl -sS -D - -o /dev/null https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | head -n1 || true)
_anth_status=$(curl -sS -D - -o /dev/null https://api.anthropic.com/v1/models \
  -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" | head -n1 || true)

case "$_openai_status" in (HTTP/*200*);; (*) echo "❌ OpenAI key rejected."; exit 2;; esac
case "$_anth_status"  in (HTTP/*200*);; (*) echo "❌ Anthropic key rejected."; exit 3;; esac
echo "✅ Keys OK. Launching…"

# --- 3) Launch agents + dashboard ---
cd ~/Documents/Updated_Relay_Files
[ -f jenny.py ] && (python3 jenny.py &) || true
[ -f luna.py ]  && (python3 luna.py  &) || true
exec streamlit run app.py
