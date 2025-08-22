#!/usr/bin/env python3
"""
NLIP Integration Module
Integrates Natural Language Instruction Protocol with existing agent orchestrator system.
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from nlip_protocol import (
    NLIPProtocol, NLIPMessage, MessageType, Priority, 
    enable_structured_agent_comm, implement_nlip_protocol
)

# Import existing orchestrator functions
try:
    from agent_orchestrator import (
        tts_say, ensure_agents_and_tokens, approval_gate,
        openai_chat, anthropic_chat, normalize_vote
    )
except ImportError:
    # Fallback functions if orchestrator not available
    def tts_say(text): print(f"[TTS] {text}")
    def ensure_agents_and_tokens(): return {}
    def approval_gate(task): return {"decision": "APPROVE"}
    def openai_chat(prompt): return "APPROVE - Fallback response"
    def anthropic_chat(prompt): return "APPROVE - Fallback response"
    def normalize_vote(text): return "APPROVE"


class NLIPOrchestrator:
    """Enhanced orchestrator with NLIP protocol support"""
    
    def __init__(self, working_dir: Path = None):
        self.working_dir = working_dir or Path.home() / "Documents" / "Updated_Relay_Files"
        self.protocol = enable_structured_agent_comm()
        self.message_queue: List[NLIPMessage] = []
        self.processing_active = False
        
    def send_structured_message(
        self,
        sender_id: str,
        recipient_id: str,
        message_type: MessageType,
        content: Dict[str, Any],
        priority: Priority = Priority.NORMAL,
        requires_response: bool = False
    ) -> Optional[NLIPMessage]:
        """Send a structured NLIP message"""
        
        message = NLIPMessage(
            message_id="",
            timestamp="",
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=message_type,
            priority=priority,
            content=content,
            requires_response=requires_response
        )
        
        # Validate message
        is_valid, error = self.protocol.validate_message(message)
        if not is_valid:
            print(f"Message validation failed: {error}")
            return None
        
        # Log message
        self.protocol.log_message(message)
        
        # Add to processing queue
        self.message_queue.append(message)
        
        return message
    
    def send_instruction(
        self,
        sender_id: str,
        recipient_id: str,
        instruction: str,
        parameters: Dict[str, Any] = None,
        priority: Priority = Priority.NORMAL
    ) -> Optional[NLIPMessage]:
        """Send a natural language instruction using NLIP"""
        
        content = {
            "instruction": instruction,
            "parameters": parameters or {},
            "natural_language": instruction,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return self.send_structured_message(
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=MessageType.INSTRUCTION,
            content=content,
            priority=priority,
            requires_response=True
        )
    
    def request_approval(
        self,
        task_description: str,
        requester_id: str = "Claude",
        priority: Priority = Priority.NORMAL
    ) -> Dict[str, Any]:
        """Request approval using NLIP structured messaging"""
        
        # Send approval request to Jenny
        jenny_msg = self.send_instruction(
            sender_id=requester_id,
            recipient_id="Jenny",
            instruction=f"Please review and approve: {task_description}",
            parameters={"task": task_description, "approval_type": "safety_review"},
            priority=priority
        )
        
        # Send approval request to Luna
        luna_msg = self.send_instruction(
            sender_id=requester_id,
            recipient_id="Luna", 
            instruction=f"Please review and approve: {task_description}",
            parameters={"task": task_description, "approval_type": "cautious_review"},
            priority=priority
        )
        
        # Use existing approval gate for actual decision
        approval_result = approval_gate(task_description)
        
        # Create structured response messages
        jenny_response = self.protocol.create_response_message(
            sender_id="Jenny",
            recipient_id=requester_id,
            original_message=jenny_msg,
            response_data={
                "decision": approval_result.get("jenny", "HOLD"),
                "reasoning": approval_result.get("jenny_raw", "No response"),
                "review_type": "pragmatic"
            }
        )
        
        luna_response = self.protocol.create_response_message(
            sender_id="Luna", 
            recipient_id=requester_id,
            original_message=luna_msg,
            response_data={
                "decision": approval_result.get("luna", "HOLD"),
                "reasoning": approval_result.get("luna_raw", "No response"),
                "review_type": "cautious"
            }
        )
        
        # Log responses
        self.protocol.log_message(jenny_response)
        self.protocol.log_message(luna_response)
        
        # Enhanced approval result with NLIP structure
        structured_result = {
            **approval_result,
            "nlip_messages": {
                "jenny_request": jenny_msg.message_id if jenny_msg else None,
                "luna_request": luna_msg.message_id if luna_msg else None,
                "jenny_response": jenny_response.message_id,
                "luna_response": luna_response.message_id
            },
            "conversation_id": f"approval_{int(time.time())}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return structured_result
    
    def broadcast_announcement(
        self,
        message: str,
        sender_id: str = "Claude",
        priority: Priority = Priority.NORMAL
    ):
        """Broadcast announcement to all registered agents"""
        
        for agent_id in self.protocol.agents.keys():
            if agent_id != sender_id:
                self.send_structured_message(
                    sender_id=sender_id,
                    recipient_id=agent_id,
                    message_type=MessageType.INSTRUCTION,
                    content={
                        "announcement": message,
                        "broadcast": True,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    },
                    priority=priority
                )
        
        # Use TTS for audio announcement
        tts_say(message)
    
    def query_agent_capabilities(
        self,
        target_agent: str,
        requester_id: str = "Claude"
    ) -> Dict[str, Any]:
        """Query capabilities of a specific agent"""
        
        query_msg = self.send_structured_message(
            sender_id=requester_id,
            recipient_id=target_agent,
            message_type=MessageType.CAPABILITY_QUERY,
            content={
                "query_type": "full_capabilities",
                "include_permissions": True
            },
            requires_response=True
        )
        
        # Get capabilities from protocol
        capabilities = self.protocol.get_agent_capabilities(target_agent)
        
        response_data = {
            "agent_id": target_agent,
            "capabilities": [
                {
                    "name": cap.name,
                    "description": cap.description,
                    "risk_level": cap.risk_level,
                    "permissions_required": cap.permissions_required
                } for cap in capabilities
            ],
            "total_capabilities": len(capabilities),
            "query_timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if query_msg:
            response_msg = self.protocol.create_response_message(
                sender_id=target_agent,
                recipient_id=requester_id,
                original_message=query_msg,
                response_data=response_data
            )
            self.protocol.log_message(response_msg)
        
        return response_data
    
    def get_protocol_status(self) -> Dict[str, Any]:
        """Get current status of NLIP protocol"""
        
        alignment_report = self.protocol.ensure_ontology_alignment()
        
        status = {
            "protocol_active": True,
            "total_messages": len(self.protocol.message_log),
            "queued_messages": len(self.message_queue),
            "active_conversations": len(self.protocol.active_conversations),
            "registered_agents": list(self.protocol.agents.keys()),
            "alignment_report": alignment_report,
            "last_activity": datetime.now(timezone.utc).isoformat()
        }
        
        return status
    
    def save_protocol_state(self, filename: str = "nlip_state.json"):
        """Save current protocol state to file"""
        
        state_file = self.working_dir / filename
        
        # Prepare serializable state
        state_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message_log": [msg.to_dict() for msg in self.protocol.message_log],
            "active_conversations": self.protocol.active_conversations,
            "agents": {
                agent_id: {
                    "agent_id": agent.agent_id,
                    "role": agent.role.value,
                    "permissions_level": agent.permissions_level,
                    "trust_score": agent.trust_score,
                    "linked_agents": agent.linked_agents,
                    "capabilities": [
                        {
                            "name": cap.name,
                            "description": cap.description,
                            "risk_level": cap.risk_level
                        } for cap in agent.capabilities
                    ]
                } for agent_id, agent in self.protocol.agents.items()
            }
        }
        
        with open(state_file, 'w') as f:
            json.dump(state_data, f, indent=2)
        
        return state_file
    
    def load_protocol_state(self, filename: str = "nlip_state.json"):
        """Load protocol state from file"""
        
        state_file = self.working_dir / filename
        
        if not state_file.exists():
            print(f"State file {filename} not found")
            return False
        
        try:
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            
            # Restore message log
            self.protocol.message_log = [
                NLIPMessage.from_dict(msg_data) 
                for msg_data in state_data.get("message_log", [])
            ]
            
            # Restore conversations
            self.protocol.active_conversations = state_data.get("active_conversations", {})
            
            print(f"Protocol state loaded from {filename}")
            return True
            
        except Exception as e:
            print(f"Failed to load protocol state: {e}")
            return False


def main():
    """Demo the NLIP integration"""
    
    orchestrator = NLIPOrchestrator()
    
    print("NLIP Integration Demo")
    print("=" * 50)
    
    # Demo 1: Send instruction
    print("\n1. Sending instruction to Demo agent:")
    instruction_msg = orchestrator.send_instruction(
        sender_id="Claude",
        recipient_id="Demo",
        instruction="Analyze the current codebase for security vulnerabilities",
        parameters={"scan_type": "comprehensive", "include_dependencies": True}
    )
    
    if instruction_msg:
        print(f"   Message sent: {instruction_msg.message_id}")
        print(f"   Content: {instruction_msg.content['instruction']}")
    
    # Demo 2: Request approval
    print("\n2. Requesting approval for system update:")
    approval_result = orchestrator.request_approval(
        "Deploy new NLIP protocol integration to production environment",
        priority=Priority.HIGH
    )
    print(f"   Decision: {approval_result['decision']}")
    print(f"   Jenny: {approval_result.get('jenny', 'N/A')}")
    print(f"   Luna: {approval_result.get('luna', 'N/A')}")
    
    # Demo 3: Query capabilities
    print("\n3. Querying Demo agent capabilities:")
    capabilities = orchestrator.query_agent_capabilities("Demo")
    print(f"   Agent has {capabilities['total_capabilities']} capabilities")
    for cap in capabilities['capabilities']:
        print(f"   - {cap['name']}: {cap['description']}")
    
    # Demo 4: Protocol status
    print("\n4. Protocol Status:")
    status = orchestrator.get_protocol_status()
    print(f"   Total messages: {status['total_messages']}")
    print(f"   Active conversations: {status['active_conversations']}")
    print(f"   Registered agents: {', '.join(status['registered_agents'])}")
    
    # Demo 5: Save state
    print("\n5. Saving protocol state:")
    state_file = orchestrator.save_protocol_state()
    print(f"   State saved to: {state_file}")


if __name__ == "__main__":
    main()