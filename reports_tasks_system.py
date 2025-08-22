#!/usr/bin/env python3
"""
Reports & Tasks Management System
Comprehensive task tracking with voicemail ingestion, auto-assignment, and AI helpers.
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

# Import NLIP for agent communication
from nlip_integration import NLIPOrchestrator
from nlip_protocol import Priority

class TaskStatus(Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"  
    BLOCKED = "blocked"
    DONE = "done"

class TaskPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class TaskSource(Enum):
    VOICEMAIL = "voicemail"
    EMAIL = "email"
    MANUAL = "manual"
    SYSTEM = "system"

@dataclass
class Task:
    """Core task data structure"""
    task_id: str
    title: str
    description: str
    source: TaskSource
    excerpt: str
    tags: List[str]
    assignee: str
    due_date: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    created_at: str
    updated_at: str
    subtasks: List[Dict[str, Any]] = None
    links: List[str] = None
    comments: List[Dict[str, Any]] = None
    attachments: List[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.subtasks is None:
            self.subtasks = []
        if self.links is None:
            self.links = []
        if self.comments is None:
            self.comments = []
        if self.attachments is None:
            self.attachments = []
        if self.metadata is None:
            self.metadata = {}

@dataclass
class VoicemailRecord:
    """Voicemail record with transcription"""
    voicemail_id: str
    filepath: str
    transcription: str
    confidence: float
    duration_seconds: float
    created_at: str
    processed: bool = False
    generated_tasks: List[str] = None

    def __post_init__(self):
        if self.generated_tasks is None:
            self.generated_tasks = []

class TaskManager:
    """Core task management system"""
    
    def __init__(self, db_path: str = "tasks.db"):
        self.db_path = db_path
        self.nlip = NLIPOrchestrator()
        self._init_database()
        
        # Keyword-to-assignee mapping for auto-assignment
        self.assignment_rules = {
            "bank": "Jenny",
            "banking": "Jenny", 
            "financial": "Jenny",
            "security": "Demo",
            "vulnerability": "Demo",
            "code": "Claude",
            "deploy": "Claude",
            "social": "Lexi",
            "instagram": "Lexi",
            "facebook": "Lexi",
            "legal": "Ava",
            "compliance": "Ava",
            "contract": "Ava"
        }
    
    def _init_database(self):
        """Initialize SQLite database for task persistence"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                source TEXT NOT NULL,
                excerpt TEXT,
                tags TEXT, -- JSON array
                assignee TEXT,
                due_date TEXT,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                subtasks TEXT, -- JSON array
                links TEXT, -- JSON array  
                comments TEXT, -- JSON array
                attachments TEXT, -- JSON array
                metadata TEXT -- JSON object
            )
        """)
        
        # Voicemails table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS voicemails (
                voicemail_id TEXT PRIMARY KEY,
                filepath TEXT NOT NULL,
                transcription TEXT,
                confidence REAL,
                duration_seconds REAL,
                created_at TEXT NOT NULL,
                processed BOOLEAN DEFAULT 0,
                generated_tasks TEXT -- JSON array of task_ids
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_voicemails_processed ON voicemails(processed)")
        
        conn.commit()
        conn.close()
    
    def create_task(self, task: Task) -> str:
        """Create new task and persist to database"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO tasks (
                task_id, title, description, source, excerpt, tags, assignee, 
                due_date, status, priority, created_at, updated_at, subtasks, 
                links, comments, attachments, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.task_id, task.title, task.description, task.source.value,
            task.excerpt, json.dumps(task.tags), task.assignee, task.due_date,
            task.status.value, task.priority.value, task.created_at, task.updated_at,
            json.dumps(task.subtasks), json.dumps(task.links), json.dumps(task.comments),
            json.dumps(task.attachments), json.dumps(task.metadata)
        ))
        
        conn.commit()
        conn.close()
        
        return task.task_id
    
    def get_tasks(self, filters: Dict[str, Any] = None) -> List[Task]:
        """Get tasks with optional filtering"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT * FROM tasks"
        params = []
        
        if filters:
            conditions = []
            if "status" in filters:
                conditions.append("status = ?")
                params.append(filters["status"])
            if "assignee" in filters:
                conditions.append("assignee = ?")
                params.append(filters["assignee"])
            if "source" in filters:
                conditions.append("source = ?")
                params.append(filters["source"])
            if "date_from" in filters:
                conditions.append("created_at >= ?")
                params.append(filters["date_from"])
            if "date_to" in filters:
                conditions.append("created_at <= ?")
                params.append(filters["date_to"])
                
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        tasks = []
        for row in rows:
            task = Task(
                task_id=row[0], title=row[1], description=row[2], 
                source=TaskSource(row[3]), excerpt=row[4],
                tags=json.loads(row[5]) if row[5] else [],
                assignee=row[6], due_date=row[7],
                status=TaskStatus(row[8]), priority=TaskPriority(row[9]),
                created_at=row[10], updated_at=row[11],
                subtasks=json.loads(row[12]) if row[12] else [],
                links=json.loads(row[13]) if row[13] else [],
                comments=json.loads(row[14]) if row[14] else [],
                attachments=json.loads(row[15]) if row[15] else [],
                metadata=json.loads(row[16]) if row[16] else {}
            )
            tasks.append(task)
        
        return tasks
    
    def update_task_status(self, task_id: str, status: TaskStatus) -> bool:
        """Update task status"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?
        """, (status.value, datetime.now(timezone.utc).isoformat(), task_id))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected > 0
    
    def get_task_stats(self) -> Dict[str, int]:
        """Get task statistics for dashboard"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        for status in TaskStatus:
            cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = ?", (status.value,))
            stats[status.value] = cursor.fetchone()[0]
        
        conn.close()
        return stats
    
    def auto_assign_task(self, task_text: str, tags: List[str]) -> str:
        """Auto-assign task based on keywords and content"""
        
        text_lower = task_text.lower()
        tag_text = " ".join(tags).lower()
        combined_text = f"{text_lower} {tag_text}"
        
        # Check assignment rules
        for keyword, assignee in self.assignment_rules.items():
            if keyword in combined_text:
                return assignee
        
        # Default assignment logic
        if any(word in combined_text for word in ["urgent", "asap", "emergency"]):
            return "Claude"  # Orchestrator handles urgent items
        elif any(word in combined_text for word in ["review", "check", "approve"]):
            return "Jenny"  # Pragmatic reviewer
        else:
            return "Claude"  # Default to orchestrator
    
    def extract_tags_from_text(self, text: str) -> List[str]:
        """Extract relevant tags from text using keyword matching"""
        
        tag_keywords = {
            "financial": ["bank", "banking", "money", "payment", "invoice", "bill"],
            "security": ["security", "vulnerability", "hack", "breach", "ssl", "auth"],
            "urgent": ["urgent", "asap", "emergency", "critical", "immediately"],
            "social_media": ["instagram", "facebook", "twitter", "social", "post", "content"],
            "legal": ["legal", "compliance", "contract", "terms", "policy", "gdpr"],
            "technical": ["code", "deploy", "server", "api", "database", "bug"],
            "meeting": ["meeting", "call", "zoom", "conference", "appointment"],
            "deadline": ["deadline", "due", "by today", "this week", "tomorrow"]
        }
        
        text_lower = text.lower()
        extracted_tags = []
        
        for tag, keywords in tag_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                extracted_tags.append(tag)
        
        return extracted_tags


class VoicemailProcessor:
    """Process voicemails and generate tasks automatically"""
    
    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager
        self.uploads_dir = Path("uploads")
        self.uploads_dir.mkdir(exist_ok=True)
    
    def transcribe_voicemail(self, audio_filepath: str) -> Tuple[str, float]:
        """Transcribe voicemail audio file (placeholder implementation)"""
        
        # In production, integrate with speech-to-text service like:
        # - OpenAI Whisper API
        # - Google Speech-to-Text  
        # - Azure Speech Services
        # - AWS Transcribe
        
        # For demo, return mock transcription
        filename = Path(audio_filepath).name
        mock_transcriptions = {
            "bank_call.wav": ("Hi, this is Sarah from First National Bank. We need you to review and approve the new business account setup documents by Friday. The account number is 12345678. Please call back at 555-0123.", 0.95),
            "security_alert.wav": ("This is an urgent security alert. We detected suspicious activity on your website. Please have your security team investigate immediately and call us back.", 0.88),
            "meeting_request.wav": ("Hello, this is Jennifer from ABC Corp. We'd like to schedule a meeting next Tuesday to discuss the contract terms. Please confirm your availability.", 0.92)
        }
        
        return mock_transcriptions.get(filename, ("Transcription not available for this file.", 0.0))
    
    def process_voicemail_file(self, filepath: str) -> VoicemailRecord:
        """Process a single voicemail file"""
        
        voicemail_id = hashlib.md5(filepath.encode()).hexdigest()
        created_at = datetime.now(timezone.utc).isoformat()
        
        # Get file duration (mock implementation)
        duration = 45.0  # seconds
        
        # Transcribe audio
        transcription, confidence = self.transcribe_voicemail(filepath)
        
        # Create voicemail record
        voicemail = VoicemailRecord(
            voicemail_id=voicemail_id,
            filepath=filepath,
            transcription=transcription,
            confidence=confidence,
            duration_seconds=duration,
            created_at=created_at
        )
        
        # Save to database
        self._save_voicemail(voicemail)
        
        return voicemail
    
    def _save_voicemail(self, voicemail: VoicemailRecord):
        """Save voicemail record to database"""
        
        conn = sqlite3.connect(self.task_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO voicemails (
                voicemail_id, filepath, transcription, confidence, 
                duration_seconds, created_at, processed, generated_tasks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            voicemail.voicemail_id, voicemail.filepath, voicemail.transcription,
            voicemail.confidence, voicemail.duration_seconds, voicemail.created_at,
            voicemail.processed, json.dumps(voicemail.generated_tasks)
        ))
        
        conn.commit()
        conn.close()
    
    def generate_tasks_from_voicemail(self, voicemail: VoicemailRecord) -> List[Task]:
        """Generate tasks automatically from voicemail transcription"""
        
        if not voicemail.transcription or voicemail.confidence < 0.5:
            return []
        
        # Extract key information
        text = voicemail.transcription
        tags = self.task_manager.extract_tags_from_text(text)
        assignee = self.task_manager.auto_assign_task(text, tags)
        
        # Determine priority based on keywords
        priority = TaskPriority.NORMAL
        urgent_keywords = ["urgent", "emergency", "asap", "immediately", "critical"]
        if any(keyword in text.lower() for keyword in urgent_keywords):
            priority = TaskPriority.URGENT
        
        # Extract potential due date
        due_date = None
        if "by friday" in text.lower():
            # Calculate next Friday
            today = datetime.now()
            days_ahead = 4 - today.weekday()  # Friday is 4
            if days_ahead <= 0:
                days_ahead += 7
            due_date = (today + timedelta(days=days_ahead)).isoformat()
        
        # Create task
        task_id = f"vm_{voicemail.voicemail_id}_{int(datetime.now().timestamp())}"
        
        # Generate title from first sentence
        sentences = text.split('.')
        title = sentences[0][:100] + "..." if len(sentences[0]) > 100 else sentences[0]
        
        task = Task(
            task_id=task_id,
            title=title,
            description=text,
            source=TaskSource.VOICEMAIL,
            excerpt=text[:200] + "..." if len(text) > 200 else text,
            tags=tags,
            assignee=assignee,
            due_date=due_date,
            status=TaskStatus.NEW,
            priority=priority,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            metadata={
                "voicemail_id": voicemail.voicemail_id,
                "confidence": voicemail.confidence,
                "duration": voicemail.duration_seconds
            }
        )
        
        # Save task
        self.task_manager.create_task(task)
        
        # Update voicemail record
        voicemail.generated_tasks.append(task_id)
        voicemail.processed = True
        self._save_voicemail(voicemail)
        
        return [task]


class AITaskHelper:
    """AI-powered task assistance"""
    
    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager
    
    def suggest_next_step(self, task: Task) -> str:
        """Suggest next step for a task"""
        
        # Analysis based on task content and status
        suggestions = {
            TaskStatus.NEW: [
                "Review task details and requirements",
                "Assign to appropriate team member",
                "Set priority and due date",
                "Break down into subtasks if complex"
            ],
            TaskStatus.IN_PROGRESS: [
                "Check progress with assignee",
                "Review any blockers or dependencies", 
                "Update status or add comments",
                "Prepare for review or testing"
            ],
            TaskStatus.BLOCKED: [
                "Identify and resolve blocking issues",
                "Escalate to appropriate person",
                "Update timeline and notify stakeholders",
                "Consider alternative approaches"
            ]
        }
        
        base_suggestions = suggestions.get(task.status, ["Review task status"])
        
        # Add context-specific suggestions
        if "bank" in task.description.lower():
            base_suggestions.append("Contact bank representative")
        if "urgent" in task.tags:
            base_suggestions.insert(0, "Prioritize immediate action")
        
        return base_suggestions[0]  # Return top suggestion
    
    def summarize_task(self, task: Task) -> str:
        """Generate task summary"""
        
        summary_parts = []
        
        # Basic info
        summary_parts.append(f"Task: {task.title}")
        summary_parts.append(f"Status: {task.status.value.title()}")
        summary_parts.append(f"Assigned to: {task.assignee}")
        
        # Priority and due date
        if task.priority != TaskPriority.NORMAL:
            summary_parts.append(f"Priority: {task.priority.value.title()}")
        
        if task.due_date:
            summary_parts.append(f"Due: {task.due_date[:10]}")  # Date only
        
        # Tags
        if task.tags:
            summary_parts.append(f"Tags: {', '.join(task.tags)}")
        
        # Progress
        if task.subtasks:
            completed = sum(1 for st in task.subtasks if st.get('completed'))
            summary_parts.append(f"Subtasks: {completed}/{len(task.subtasks)} completed")
        
        return " | ".join(summary_parts)
    
    def auto_assign_task(self, task: Task) -> str:
        """AI-powered automatic task assignment"""
        
        return self.task_manager.auto_assign_task(task.description, task.tags)


def create_sample_tasks_and_voicemails(task_manager: TaskManager, voicemail_processor: VoicemailProcessor):
    """Create sample data for testing"""
    
    # Sample tasks
    sample_tasks = [
        Task(
            task_id="task_001",
            title="Review bank account setup documents",
            description="Sarah from First National Bank called about reviewing business account documents",
            source=TaskSource.VOICEMAIL,
            excerpt="Need to review and approve new business account setup...",
            tags=["financial", "urgent", "deadline"],
            assignee="Jenny",
            due_date=(datetime.now() + timedelta(days=2)).isoformat(),
            status=TaskStatus.NEW,
            priority=TaskPriority.HIGH,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat()
        ),
        Task(
            task_id="task_002", 
            title="Investigate security alert",
            description="Urgent security alert about suspicious website activity",
            source=TaskSource.VOICEMAIL,
            excerpt="Detected suspicious activity on website...",
            tags=["security", "urgent", "technical"],
            assignee="Demo",
            due_date=datetime.now().isoformat(),
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.URGENT,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat()
        )
    ]
    
    for task in sample_tasks:
        task_manager.create_task(task)
    
    return len(sample_tasks)


def main():
    """Demo the Reports & Tasks system"""
    
    print("Reports & Tasks Management System")
    print("=" * 50)
    
    # Initialize system
    task_manager = TaskManager()
    voicemail_processor = VoicemailProcessor(task_manager)
    ai_helper = AITaskHelper(task_manager)
    
    # Create sample data
    print("\n📝 Creating sample tasks...")
    created_count = create_sample_tasks_and_voicemails(task_manager, voicemail_processor)
    print(f"   Created {created_count} sample tasks")
    
    # Show statistics
    print("\n📊 Task Statistics:")
    stats = task_manager.get_task_stats()
    for status, count in stats.items():
        print(f"   {status.title()}: {count}")
    
    # Show all tasks
    print("\n📋 Current Tasks:")
    tasks = task_manager.get_tasks()
    for task in tasks:
        print(f"   [{task.status.value.upper()}] {task.title} -> {task.assignee}")
        print(f"       Tags: {', '.join(task.tags)}")
        print(f"       Next: {ai_helper.suggest_next_step(task)}")
    
    print("\n🎉 Reports & Tasks system ready!")
    print(f"   Database: {task_manager.db_path}")
    print(f"   Total tasks: {len(tasks)}")


if __name__ == "__main__":
    main()