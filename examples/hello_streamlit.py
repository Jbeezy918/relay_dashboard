#!/usr/bin/env python3
"""
Hello Streamlit Demo
Simple demo showing title, input box, and text-to-speech response.
"""
import streamlit as st
import os
import requests
import time

def text_to_speech_demo(text: str) -> bool:
    """Simple TTS demo - returns True if successful (mock for now)"""
    if not text.strip():
        return False
    
    # Mock TTS - in real implementation would use ElevenLabs or similar
    st.info(f"🔊 Speaking: '{text}'")
    time.sleep(1)  # Simulate speech duration
    return True

def main():
    st.set_page_config(
        page_title="Hello Streamlit Demo",
        page_icon="👋",
        layout="centered"
    )
    
    st.title("👋 Hello Streamlit Demo")
    st.markdown("---")
    
    st.write("**Simple interactive demo with voice output**")
    
    # Input section
    user_input = st.text_input(
        "Enter some text:", 
        placeholder="Type something to hear it spoken...",
        key="demo_input"
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗣️ Speak Text", disabled=not user_input.strip()):
            if user_input.strip():
                success = text_to_speech_demo(user_input)
                if success:
                    st.success("✅ Text spoken successfully!")
                else:
                    st.error("❌ Failed to speak text")
    
    with col2:
        if st.button("🔄 Clear"):
            st.rerun()
    
    # Status section
    st.markdown("---")
    st.subheader("📊 Status")
    
    # Check for API keys
    has_elevenlabs = bool(os.getenv("ELEVENLABS_API_KEY"))
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("ElevenLabs TTS", "✅ Ready" if has_elevenlabs else "⚠️ No API Key")
    
    with col2:
        st.metric("Demo Mode", "🟢 Active")
    
    # Instructions
    if not has_elevenlabs:
        st.warning("💡 Add ELEVENLABS_API_KEY to .env for real TTS functionality")
    
    st.markdown("---")
    st.caption("This is a simple Streamlit demo showcasing basic interactivity.")

if __name__ == "__main__":
    main()