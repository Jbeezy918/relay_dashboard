#!/usr/bin/env python3
"""
Agent Ontology Alignment System
Ensures all agents align on shared vocabulary, concepts, and communication protocols.
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from nlip_protocol import AgentOntology, AgentCapability, AgentRole, NLIPProtocol


class AlignmentStatus(Enum):
    """Ontology alignment status levels"""
    ALIGNED = "aligned"
    DRIFT_DETECTED = "drift_detected" 
    MISALIGNED = "misaligned"
    CRITICAL_MISMATCH = "critical_mismatch"


@dataclass
class ConceptDefinition:
    """Standardized concept definition for agent alignment"""
    concept_id: str
    name: str
    description: str
    synonyms: List[str]
    related_concepts: List[str]
    usage_context: str
    examples: List[str]
    version: str = "1.0"


@dataclass
class AlignmentMetrics:
    """Metrics for measuring ontology alignment quality"""
    concept_coverage: float  # % of concepts covered by all agents
    vocabulary_consistency: float  # % consistency in terminology usage
    capability_overlap: float  # % overlap in agent capabilities
    trust_coherence: float  # consistency in trust relationships
    communication_efficiency: float  # success rate of message understanding
    last_alignment_check: str
    alignment_score: float  # overall alignment quality (0-1)


class OntologyAlignmentSystem:
    """System for ensuring agent ontology alignment"""
    
    def __init__(self, nlip_protocol: NLIPProtocol):
        self.protocol = nlip_protocol
        self.shared_ontology: Dict[str, ConceptDefinition] = {}
        self.alignment_history: List[AlignmentMetrics] = []
        self.concept_versions: Dict[str, List[str]] = {}
        
        # Initialize core concepts
        self._initialize_core_concepts()
    
    def _initialize_core_concepts(self):
        """Initialize core shared concepts for agent alignment"""
        
        core_concepts = [
            ConceptDefinition(
                concept_id="task_approval",
                name="Task Approval",
                description="Process of reviewing and authorizing tasks before execution",
                synonyms=["approval", "authorization", "review", "clearance"],
                related_concepts=["safety_review", "risk_assessment", "consensus"],
                usage_context="Used when agents need permission to execute high-risk operations",
                examples=["Jenny approves code deployment", "Luna reviews system changes"]
            ),
            ConceptDefinition(
                concept_id="agent_capability",
                name="Agent Capability",
                description="Specific functional ability of an agent",
                synonyms=["skill", "function", "ability", "competency"],
                related_concepts=["permissions", "scope", "authorization"],
                usage_context="Defines what an agent can do within the system",
                examples=["code_analysis", "network_scanning", "text_generation"]
            ),
            ConceptDefinition(
                concept_id="trust_level",
                name="Trust Level",
                description="Degree of confidence in an agent's reliability and safety",
                synonyms=["trust_score", "reliability", "confidence"],
                related_concepts=["permissions", "authorization", "verification"],
                usage_context="Determines what operations an agent is allowed to perform",
                examples=["high-trust for reviewers", "standard trust for workers"]
            ),
            ConceptDefinition(
                concept_id="message_priority",
                name="Message Priority",
                description="Urgency level for inter-agent communications",
                synonyms=["urgency", "importance", "priority_level"],
                related_concepts=["scheduling", "resource_allocation", "attention"],
                usage_context="Helps agents prioritize which messages to process first",
                examples=["critical for security alerts", "normal for routine tasks"]
            ),
            ConceptDefinition(
                concept_id="safety_review",
                name="Safety Review",
                description="Assessment of potential risks and safety implications",
                synonyms=["risk_assessment", "safety_check", "hazard_analysis"],
                related_concepts=["approval", "verification", "validation"],
                usage_context="Required before executing potentially dangerous operations",
                examples=["code deployment review", "system modification check"]
            )
        ]
        
        for concept in core_concepts:
            self.shared_ontology[concept.concept_id] = concept
            self.concept_versions[concept.concept_id] = [concept.version]
    
    def add_concept(self, concept: ConceptDefinition) -> bool:
        """Add new concept to shared ontology"""
        
        # Check for conflicts
        if concept.concept_id in self.shared_ontology:
            existing = self.shared_ontology[concept.concept_id]
            if existing.version != concept.version:
                # Version update
                self.concept_versions[concept.concept_id].append(concept.version)
            
        self.shared_ontology[concept.concept_id] = concept
        return True
    
    def validate_agent_alignment(self, agent_id: str) -> Dict[str, Any]:
        """Validate that an agent aligns with shared ontology"""
        
        if agent_id not in self.protocol.agents:
            return {"aligned": False, "error": "Agent not found"}
        
        agent = self.protocol.agents[agent_id]
        validation_results = {
            "agent_id": agent_id,
            "alignment_checks": {},
            "issues": [],
            "recommendations": [],
            "overall_alignment": True
        }
        
        # Check capability alignment
        capability_names = [cap.name for cap in agent.capabilities]
        
        for cap_name in capability_names:
            if cap_name not in [concept.name for concept in self.shared_ontology.values()]:
                # Check for synonyms
                found_match = False
                for concept in self.shared_ontology.values():
                    if cap_name.lower() in [syn.lower() for syn in concept.synonyms]:
                        found_match = True
                        validation_results["recommendations"].append(
                            f"Consider using standard term '{concept.name}' instead of '{cap_name}'"
                        )
                        break
                
                if not found_match:
                    validation_results["issues"].append(
                        f"Capability '{cap_name}' not found in shared ontology"
                    )
                    validation_results["overall_alignment"] = False
        
        # Check trust level consistency
        if agent.trust_score < 0 or agent.trust_score > 1:
            validation_results["issues"].append("Trust score outside valid range [0,1]")
            validation_results["overall_alignment"] = False
        
        # Check role consistency
        role_capabilities = {
            AgentRole.CYBERSECURITY: ["code_analysis", "vulnerability_detection", "network_scanning"],
            AgentRole.REVIEWER: ["approval_review", "safety_assessment"],
            AgentRole.EXECUTOR: ["script_execution", "command_running"],
            AgentRole.BUILDER: ["system_building", "deployment"],
            AgentRole.ORCHESTRATOR: ["task_coordination", "agent_management"]
        }
        
        expected_caps = role_capabilities.get(agent.role, [])
        agent_cap_names = [cap.name.lower() for cap in agent.capabilities]
        
        for expected_cap in expected_caps:
            if expected_cap.lower() not in agent_cap_names:
                validation_results["recommendations"].append(
                    f"Consider adding capability '{expected_cap}' for role {agent.role.value}"
                )
        
        return validation_results
    
    def compute_alignment_metrics(self) -> AlignmentMetrics:
        """Compute comprehensive alignment metrics"""
        
        if not self.protocol.agents:
            return AlignmentMetrics(0, 0, 0, 0, 0, datetime.now(timezone.utc).isoformat(), 0)
        
        # Concept coverage
        all_capabilities = set()
        for agent in self.protocol.agents.values():
            all_capabilities.update(cap.name for cap in agent.capabilities)
        
        ontology_concepts = set(concept.name for concept in self.shared_ontology.values())
        coverage = len(all_capabilities & ontology_concepts) / len(ontology_concepts) if ontology_concepts else 0
        
        # Vocabulary consistency  
        synonym_matches = 0
        total_terms = len(all_capabilities)
        
        for cap_name in all_capabilities:
            for concept in self.shared_ontology.values():
                if cap_name.lower() in [syn.lower() for syn in concept.synonyms + [concept.name]]:
                    synonym_matches += 1
                    break
        
        vocabulary_consistency = synonym_matches / total_terms if total_terms > 0 else 0
        
        # Capability overlap
        agent_capabilities = {}
        for agent_id, agent in self.protocol.agents.items():
            agent_capabilities[agent_id] = set(cap.name for cap in agent.capabilities)
        
        if len(agent_capabilities) > 1:
            overlaps = []
            agents_list = list(agent_capabilities.items())
            for i in range(len(agents_list)):
                for j in range(i + 1, len(agents_list)):
                    agent1_caps = agents_list[i][1]
                    agent2_caps = agents_list[j][1]
                    overlap = len(agent1_caps & agent2_caps) / len(agent1_caps | agent2_caps)
                    overlaps.append(overlap)
            capability_overlap = sum(overlaps) / len(overlaps) if overlaps else 0
        else:
            capability_overlap = 1.0
        
        # Trust coherence
        trust_scores = [agent.trust_score for agent in self.protocol.agents.values()]
        trust_variance = sum((score - sum(trust_scores)/len(trust_scores))**2 for score in trust_scores) / len(trust_scores)
        trust_coherence = 1.0 - min(trust_variance, 1.0)  # Lower variance = higher coherence
        
        # Communication efficiency (based on successful message validations)
        successful_messages = sum(1 for msg in self.protocol.message_log 
                                if self.protocol.validate_message(msg)[0])
        total_messages = len(self.protocol.message_log)
        communication_efficiency = successful_messages / total_messages if total_messages > 0 else 1.0
        
        # Overall alignment score
        alignment_score = (coverage + vocabulary_consistency + capability_overlap + 
                         trust_coherence + communication_efficiency) / 5
        
        metrics = AlignmentMetrics(
            concept_coverage=coverage,
            vocabulary_consistency=vocabulary_consistency,
            capability_overlap=capability_overlap,
            trust_coherence=trust_coherence,
            communication_efficiency=communication_efficiency,
            last_alignment_check=datetime.now(timezone.utc).isoformat(),
            alignment_score=alignment_score
        )
        
        self.alignment_history.append(metrics)
        return metrics
    
    def detect_alignment_drift(self, threshold: float = 0.1) -> Dict[str, Any]:
        """Detect if ontology alignment has drifted from baseline"""
        
        if len(self.alignment_history) < 2:
            return {"drift_detected": False, "message": "Insufficient history for drift detection"}
        
        current = self.alignment_history[-1]
        previous = self.alignment_history[-2]
        
        drift_analysis = {
            "drift_detected": False,
            "drift_metrics": {},
            "severity": "none",
            "recommendations": []
        }
        
        # Check each metric for significant drift
        metrics_to_check = [
            ("concept_coverage", current.concept_coverage, previous.concept_coverage),
            ("vocabulary_consistency", current.vocabulary_consistency, previous.vocabulary_consistency),
            ("capability_overlap", current.capability_overlap, previous.capability_overlap),
            ("trust_coherence", current.trust_coherence, previous.trust_coherence),
            ("communication_efficiency", current.communication_efficiency, previous.communication_efficiency)
        ]
        
        for metric_name, current_val, previous_val in metrics_to_check:
            drift_amount = abs(current_val - previous_val)
            
            if drift_amount > threshold:
                drift_analysis["drift_detected"] = True
                drift_analysis["drift_metrics"][metric_name] = {
                    "current": current_val,
                    "previous": previous_val,
                    "drift_amount": drift_amount,
                    "direction": "decrease" if current_val < previous_val else "increase"
                }
        
        # Determine severity
        if drift_analysis["drift_detected"]:
            max_drift = max(
                drift_analysis["drift_metrics"][metric]["drift_amount"] 
                for metric in drift_analysis["drift_metrics"]
            )
            
            if max_drift > 0.3:
                drift_analysis["severity"] = "critical"
                drift_analysis["recommendations"].append("Immediate realignment required")
            elif max_drift > 0.2:
                drift_analysis["severity"] = "high"
                drift_analysis["recommendations"].append("Schedule alignment review")
            else:
                drift_analysis["severity"] = "moderate"
                drift_analysis["recommendations"].append("Monitor alignment trends")
        
        return drift_analysis
    
    def generate_alignment_report(self) -> Dict[str, Any]:
        """Generate comprehensive alignment report"""
        
        current_metrics = self.compute_alignment_metrics()
        
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alignment_metrics": asdict(current_metrics),
            "agent_validations": {},
            "concept_inventory": {
                "total_concepts": len(self.shared_ontology),
                "concepts": list(self.shared_ontology.keys())
            },
            "drift_analysis": self.detect_alignment_drift(),
            "recommendations": []
        }
        
        # Validate each agent
        for agent_id in self.protocol.agents:
            report["agent_validations"][agent_id] = self.validate_agent_alignment(agent_id)
        
        # Overall recommendations
        if current_metrics.alignment_score < 0.7:
            report["recommendations"].append("Overall alignment below acceptable threshold")
        
        if current_metrics.concept_coverage < 0.8:
            report["recommendations"].append("Low concept coverage - consider expanding shared ontology")
        
        if current_metrics.communication_efficiency < 0.9:
            report["recommendations"].append("Communication issues detected - review message validation")
        
        return report
    
    def save_ontology(self, filepath: str):
        """Save shared ontology to file"""
        
        ontology_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
            "concepts": {
                concept_id: asdict(concept) 
                for concept_id, concept in self.shared_ontology.items()
            },
            "concept_versions": self.concept_versions,
            "alignment_history": [asdict(metrics) for metrics in self.alignment_history[-10:]]  # Last 10 entries
        }
        
        with open(filepath, 'w') as f:
            json.dump(ontology_data, f, indent=2)


def ensure_all_agents_align_on_ontology(nlip_protocol: NLIPProtocol) -> Dict[str, Any]:
    """Main function to ensure agent ontology alignment"""
    
    alignment_system = OntologyAlignmentSystem(nlip_protocol)
    
    # Generate comprehensive alignment report
    report = alignment_system.generate_alignment_report()
    
    # Save ontology state
    alignment_system.save_ontology("shared_ontology.json")
    
    return report


if __name__ == "__main__":
    from nlip_protocol import enable_structured_agent_comm
    
    protocol = enable_structured_agent_comm()
    alignment_report = ensure_all_agents_align_on_ontology(protocol)
    
    print("Ontology Alignment Report")
    print("=" * 50)
    print(f"Overall alignment score: {alignment_report['alignment_metrics']['alignment_score']:.2f}")
    print(f"Concept coverage: {alignment_report['alignment_metrics']['concept_coverage']:.2f}")
    print(f"Communication efficiency: {alignment_report['alignment_metrics']['communication_efficiency']:.2f}")
    
    if alignment_report['drift_analysis']['drift_detected']:
        print(f"⚠️  Alignment drift detected (severity: {alignment_report['drift_analysis']['severity']})")
    else:
        print("✅ No significant alignment drift detected")