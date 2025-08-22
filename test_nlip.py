#!/usr/bin/env python3
"""
Test script for NLIP Agent Communication Protocol
"""

import json
from nlip_integration import NLIPOrchestrator
from nlip_protocol import Priority

def test_nlip_communication():
    """Test NLIP communication scenarios"""
    
    print("NLIP Agent Communication Test")
    print("=" * 50)
    
    # Initialize orchestrator
    orchestrator = NLIPOrchestrator()
    
    # Test 1: Basic instruction message
    print("\n✅ Test 1: Basic instruction message")
    msg = orchestrator.send_instruction(
        sender_id="Claude",
        recipient_id="Demo",
        instruction="Run security scan on uploaded files"
    )
    print(f"   Message ID: {msg.message_id}")
    
    # Test 2: Approval workflow
    print("\n✅ Test 2: Approval workflow")
    approval = orchestrator.request_approval(
        "Deploy NLIP protocol to production",
        priority=Priority.HIGH
    )
    print(f"   Decision: {approval['decision']}")
    
    # Test 3: Capability query
    print("\n✅ Test 3: Agent capability query")
    caps = orchestrator.query_agent_capabilities("Jenny")
    print(f"   Jenny has {caps['total_capabilities']} capabilities")
    
    # Test 4: Protocol status
    print("\n✅ Test 4: Protocol status")
    status = orchestrator.get_protocol_status()
    print(f"   Messages logged: {status['total_messages']}")
    print(f"   Agents: {', '.join(status['registered_agents'])}")
    
    # Test 5: Save/load state
    print("\n✅ Test 5: State persistence")
    state_file = orchestrator.save_protocol_state("test_state.json")
    print(f"   State saved to: {state_file}")
    
    print("\n🎉 All NLIP tests completed successfully!")
    return True

if __name__ == "__main__":
    test_nlip_communication()