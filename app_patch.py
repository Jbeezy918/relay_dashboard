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
