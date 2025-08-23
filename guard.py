#!/usr/bin/env python3
"""
guard.py
Permission handler that logs denials to permission_denies.log
Never mentions API keys - only Guard token issues.
"""

import os, time, yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Load permissions configuration
PERMISSIONS_FILE = Path(__file__).parent / "permissions.yaml"
PERMISSION_DENIES_LOG = Path(__file__).parent / "permission_denies.log"

class PermissionGuard:
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load permissions from YAML file."""
        try:
            with open(PERMISSIONS_FILE, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            # Fallback to basic config
            return {
                'agents': {
                    'Jenny': {'allowed_operations': ['read', 'write', 'network']},
                    'Luna': {'allowed_operations': ['read', 'write', 'network']},
                    'Claude': {'allowed_operations': ['read', 'write']}
                }
            }
    
    def check_permission(self, agent: str, operation: str, resource: str = "") -> bool:
        """Check if agent has permission for operation."""
        agent_config = self.config.get('agents', {}).get(agent)
        if not agent_config:
            self._log_denial(agent, operation, resource, "Agent not found in permissions")
            return False
            
        allowed_ops = agent_config.get('allowed_operations', [])
        if operation not in allowed_ops:
            self._log_denial(agent, operation, resource, f"Operation '{operation}' not allowed")
            return False
            
        return True
    
    def _log_denial(self, agent: str, operation: str, resource: str, reason: str):
        """Log permission denial - never mentions API keys."""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] DENIED: Agent={agent} Operation={operation} Resource={resource} Reason={reason}\\n"
        
        try:
            with open(PERMISSION_DENIES_LOG, 'a') as f:
                f.write(log_entry)
        except Exception:
            pass  # Don't fail if logging fails

# Global instance
guard = PermissionGuard()

def check_agent_permission(agent: str, operation: str, resource: str = "") -> bool:
    """Global function to check permissions."""
    return guard.check_permission(agent, operation, resource)