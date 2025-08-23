#!/bin/zsh
set -e

echo "🔧 Fixing Streamlit deprecated calls..."
sed -i '' 's/st\.experimental_rerun()/st.rerun()/g' ~/Documents/Updated_Relay_Files/app.py || true

echo "🛠 Patching agent dicts for missing keys..."
PATCH_FILE=~/Documents/Updated_Relay_Files/app_patch.py
cat > $PATCH_FILE <<'EOF'
import streamlit as st

def safe_render_agent_card(agent_name):
    agent = st.session_state.agents[agent_name]
    # Use .get() with defaults
    on_call = agent.get("on_call", False)
    status = agent.get("status", "idle")
    notes = agent.get("notes", "")
    st.write(f"### {agent_name}")
    st.write(f"On call: {on_call}")
    st.write(f"Status: {status}")
    st.write(f"Notes: {notes}")

# Replace original render call
st.session_state.safe_render = safe_render_agent_card
EOF

# Inject patch if not already included
if ! grep -q "safe_render_agent_card" ~/Documents/Updated_Relay_Files/app.py; then
  echo "from app_patch import safe_render_agent_card as render_agent_card" >> ~/Documents/Updated_Relay_Files/app.py
fi

echo "🚀 Booting Relay + Agents..."
RELAY_DIR="$HOME/Documents/Updated_Relay_Files"
APP_ENTRY="app.py"

cd "$RELAY_DIR"
python3 -m venv .venv || true
source .venv/bin/activate
pip -q install --upgrade pip
[ -f requirements.txt ] && pip -q install -r requirements.txt

pkill -f "streamlit run $APP_ENTRY" 2>/dev/null || true
nohup streamlit run "$APP_ENTRY" --server.port=8502 >/tmp/relay.log 2>&1 &

sleep 3
if curl -fsS http://localhost:8502/_stcore/health >/dev/null; then
  echo "✅ Relay running at http://localhost:8502"
else
  echo "⚠️ Relay is starting (check /tmp/relay.log)"
nano ~/Documents/AI_Relay_Files/scripts/fix_and_launch.command/Users/joebudds/Documents/Updated_Relay_Filescd /Users/joebudds/Documents/Updated_Relay_Files
git remote -v



fi