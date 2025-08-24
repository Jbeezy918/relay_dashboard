# Relay Dashboard

Multi-Agent AI Communication Hub with integrated voice I/O and demo capabilities.

## Quick Start

```bash
cd ~/Updated_Relay_Files/relay_dashboard
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill: OPENAI_API_KEY, ANTHROPIC_API_KEY, ELEVENLABS_API_KEY (if used)
streamlit run app.py --server.port 8503
```

## API Keys Required

Add these to your `.env` file:

- `OPENAI_API_KEY` - For GPT models and Jenny agent
- `ANTHROPIC_API_KEY` - For Claude models  
- `ELEVENLABS_API_KEY` - For text-to-speech functionality (optional)

## Features

- 🤖 **Multi-Agent System**: Demo, Bob the Builder, Lexi, Jenny, Luna, Cannon, Ava
- 🎯 **Agent Specialization**: Each agent has specific capabilities and domains
- 🎤 **Voice I/O**: Text-to-speech integration with ElevenLabs
- 📊 **Dashboard**: Real-time agent status and system metrics
- 🚀 **Demo Mode**: Interactive Streamlit examples

## Testing the Demo

1. Launch the main dashboard: `streamlit run app.py --server.port 8503`
2. Click "🚀 Run Hello Demo" in the sidebar
3. The demo will open on port 8504: http://localhost:8504
4. Test the interactive voice features

## Agent Capabilities

| Agent | Role | Specialties |
|-------|------|-------------|
| Demo | Cybersecurity AI | Code analysis, vulnerability detection, network scanning |
| Bob the Builder | AI Engineer | Agent creation, app development, API wiring |  
| Jenny | Communication | Marketing, reminders, customer follow-up |
| Luna | Organization | Calendar, scheduling, email tracking |
| Cannon | Execution | Automation, command execution, scripting |
| Lexi | Social Media | Branding, content creation, marketing |
| Ava | Compliance | Legal review, policy scanning, contracts |

## Development

The system includes autonomous agent behaviors, daily briefing compilation, and cloud sync capabilities. All agents are registered in `AGENT_REGISTRY` with defined permissions and capabilities.

## Notes

- Agents respond based on specialized domains and task analysis
- Voice features require ElevenLabs API key
- Demo mode works without API keys (mock responses)
- Cloud sync optional (configure in settings)
