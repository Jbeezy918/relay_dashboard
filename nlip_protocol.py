#!/usr/bin/env python3
"""
Natural Language Instruction Protocol (NLIP) for Agent Communication
Provides structured messaging format and ontology alignment for agent interactions.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass, asdict
import hashlib


class MessageType(Enum):
    """Standard NLIP message types"""
    INSTRUCTION = "instruction"
    RESPONSE = "response"
    REQUEST = "request"
    ACKNOWLEDGMENT = "ack"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    CAPABILITY_QUERY = "capability_query"
    CAPABILITY_RESPONSE = "capability_response"


class Priority(Enum):
    """Message priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class AgentRole(Enum):
    """Standardized agent role ontology"""
    CYBERSECURITY = "cybersecurity_ai"
    EXECUTOR = "execution_agent"
    BUILDER = "ai_engineer"
    SOCIAL_MEDIA = "social_media_specialist"
    LEGAL = "legal_compliance_advisor"
    REVIEWER = "pragmatic_reviewer"
    CAUTIOUS_REVIEWER = "cautious_reviewer"
    ORCHESTRATOR = "orchestrator"


@dataclass
class AgentCapability:
    """Represents a single agent capability"""
    name: str
    description: str
    input_format: str
    output_format: str
    permissions_required: List[str]
    risk_level: str = "low"


@dataclass
class AgentOntology:
    """Standardized agent ontology for alignment"""
    agent_id: str
    role: AgentRole
    capabilities: List[AgentCapability]
    permissions_level: str
    trust_score: float = 0.5
    linked_agents: List[str] = None
    
    def __post_init__(self):
        if self.linked_agents is None:
            self.linked_agents = []


@dataclass
class NLIPMessage:
    """Core NLIP message structure"""
    message_id: str
    timestamp: str
    sender_id: str
    recipient_id: str
    message_type: MessageType
    priority: Priority
    content: Dict[str, Any]
    metadata: Dict[str, Any] = None
    requires_response: bool = False
    correlation_id: Optional[str] = None
    expires_at: Optional[str] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if not self.message_id:
            self.message_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format"""
        data = asdict(self)
        data['message_type'] = self.message_type.value
        data['priority'] = self.priority.value
        return data

    def to_json(self) -> str:
        """Convert message to JSON string"""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NLIPMessage':
        """Create message from dictionary"""
        data['message_type'] = MessageType(data['message_type'])
        data['priority'] = Priority(data['priority'])
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'NLIPMessage':
        """Create message from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)


class NLIPProtocol:
    """Main NLIP protocol implementation"""
    
    def __init__(self):
        self.agents: Dict[str, AgentOntology] = {}
        self.message_log: List[NLIPMessage] = []
        self.active_conversations: Dict[str, List[str]] = {}
        
    def register_agent(self, agent_ontology: AgentOntology):
        """Register an agent in the protocol"""
        self.agents[agent_ontology.agent_id] = agent_ontology
        
    def get_agent_capabilities(self, agent_id: str) -> List[AgentCapability]:
        """Get capabilities for a specific agent"""
        if agent_id in self.agents:
            return self.agents[agent_id].capabilities
        return []
    
    def create_instruction_message(
        self,
        sender_id: str,
        recipient_id: str,
        instruction: str,
        parameters: Dict[str, Any] = None,
        priority: Priority = Priority.NORMAL,
        requires_response: bool = True
    ) -> NLIPMessage:
        """Create a structured instruction message"""
        content = {
            "instruction": instruction,
            "parameters": parameters or {},
            "natural_language": instruction
        }
        
        return NLIPMessage(
            message_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=MessageType.INSTRUCTION,
            priority=priority,
            content=content,
            requires_response=requires_response
        )
    
    def create_response_message(
        self,
        sender_id: str,
        recipient_id: str,
        original_message: NLIPMessage,
        response_data: Any,
        success: bool = True
    ) -> NLIPMessage:
        """Create a response message"""
        content = {
            "response_to": original_message.message_id,
            "success": success,
            "data": response_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return NLIPMessage(
            message_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=MessageType.RESPONSE,
            priority=original_message.priority,
            content=content,
            correlation_id=original_message.message_id
        )
    
    def create_capability_query(
        self,
        sender_id: str,
        recipient_id: str,
        capability_filter: Optional[str] = None
    ) -> NLIPMessage:
        """Create a capability query message"""
        content = {
            "query_type": "capabilities",
            "filter": capability_filter
        }
        
        return NLIPMessage(
            message_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=MessageType.CAPABILITY_QUERY,
            priority=Priority.NORMAL,
            content=content,
            requires_response=True
        )
    
    def validate_message(self, message: NLIPMessage) -> tuple[bool, Optional[str]]:
        """Validate message format and content"""
        try:
            # Check required fields
            if not message.sender_id or not message.recipient_id:
                return False, "Missing sender_id or recipient_id"
            
            if not message.content:
                return False, "Message content is empty"
            
            # Check if agents exist
            if message.sender_id not in self.agents:
                return False, f"Sender agent {message.sender_id} not registered"
            
            if message.recipient_id not in self.agents:
                return False, f"Recipient agent {message.recipient_id} not registered"
            
            # Check permissions
            sender = self.agents[message.sender_id]
            recipient = self.agents[message.recipient_id]
            
            if message.recipient_id not in sender.linked_agents:
                return False, f"Agent {message.sender_id} not authorized to communicate with {message.recipient_id}"
            
            return True, None
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def log_message(self, message: NLIPMessage):
        """Log message to protocol history"""
        self.message_log.append(message)
        
        # Track conversations
        conv_key = f"{message.sender_id}_{message.recipient_id}"
        if conv_key not in self.active_conversations:
            self.active_conversations[conv_key] = []
        self.active_conversations[conv_key].append(message.message_id)
    
    def get_conversation_history(self, agent1: str, agent2: str) -> List[NLIPMessage]:
        """Get conversation history between two agents"""
        conv_key1 = f"{agent1}_{agent2}"
        conv_key2 = f"{agent2}_{agent1}"
        
        message_ids = []
        if conv_key1 in self.active_conversations:
            message_ids.extend(self.active_conversations[conv_key1])
        if conv_key2 in self.active_conversations:
            message_ids.extend(self.active_conversations[conv_key2])
        
        return [msg for msg in self.message_log if msg.message_id in message_ids]
    
    def ensure_ontology_alignment(self) -> Dict[str, Any]:
        """Ensure all agents align on communication ontology"""
        alignment_report = {
            "total_agents": len(self.agents),
            "role_distribution": {},
            "capability_coverage": {},
            "trust_scores": {},
            "alignment_status": "aligned"
        }
        
        for agent_id, agent in self.agents.items():
            # Role distribution
            role = agent.role.value
            alignment_report["role_distribution"][role] = alignment_report["role_distribution"].get(role, 0) + 1
            
            # Capability coverage
            for cap in agent.capabilities:
                alignment_report["capability_coverage"][cap.name] = alignment_report["capability_coverage"].get(cap.name, 0) + 1
            
            # Trust scores
            alignment_report["trust_scores"][agent_id] = agent.trust_score
        
        return alignment_report


def enable_structured_agent_comm():
    """Initialize and configure NLIP protocol"""
    protocol = NLIPProtocol()
    
    # Register standard agents from the codebase
    agents_config = [
        {
            "agent_id": "Jenny",
            "role": AgentRole.REVIEWER,
            "capabilities": [
                AgentCapability("approval_review", "Reviews tasks for safety and reversibility", "dict", "approval_decision", ["read", "review"])
            ],
            "permissions_level": "high-trust",
            "linked_agents": ["Luna", "Claude", "Demo", "Cannon"]
        },
        {
            "agent_id": "Luna", 
            "role": AgentRole.CAUTIOUS_REVIEWER,
            "capabilities": [
                AgentCapability("cautious_review", "Provides cautious secondary review", "dict", "approval_decision", ["read", "review"])
            ],
            "permissions_level": "high-trust",
            "linked_agents": ["Jenny", "Claude", "Demo", "Cannon"]
        },
        {
            "agent_id": "Claude",
            "role": AgentRole.ORCHESTRATOR,
            "capabilities": [
                AgentCapability("task_orchestration", "Orchestrates multi-agent tasks", "dict", "task_result", ["read", "write", "execute"]),
                AgentCapability("tts_announcement", "Text-to-speech announcements", "string", "audio", ["write"])
            ],
            "permissions_level": "orchestrator",
            "linked_agents": ["Jenny", "Luna", "Demo", "Cannon", "Bob", "Lexi", "Ava"]
        },
        {
            "agent_id": "Demo",
            "role": AgentRole.CYBERSECURITY,
            "capabilities": [
                AgentCapability("code_analysis", "Analyzes code for vulnerabilities", "string", "analysis_report", ["read"]),
                AgentCapability("network_scanning", "Scans network for vulnerabilities", "dict", "scan_results", ["read", "scan"])
            ],
            "permissions_level": "high-risk",
            "linked_agents": ["Jenny", "Luna", "Claude"]
        }
    ]
    
    for agent_config in agents_config:
        ontology = AgentOntology(**agent_config)
        protocol.register_agent(ontology)
    
    return protocol


def implement_nlip_protocol():
    """Main implementation function"""
    protocol = enable_structured_agent_comm()
    
    # Ensure ontology alignment
    alignment_report = protocol.ensure_ontology_alignment()
    
    print("NLIP Protocol Initialized")
    print(f"Registered {alignment_report['total_agents']} agents")
    print("Ontology alignment:", alignment_report['alignment_status'])
    
    return protocol, alignment_report


if __name__ == "__main__":
    protocol, report = implement_nlip_protocol()
    print(json.dumps(report, indent=2))