#!/usr/bin/env python3
"""
Reports & Tasks Tab for Streamlit Dashboard
Integrates with the main app.py to provide task management interface.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from reports_tasks_system import TaskManager, VoicemailProcessor, AITaskHelper, TaskStatus, TaskPriority, TaskSource

def render_reports_tasks_tab():
    """Render the complete Reports & Tasks tab"""
    
    # Initialize systems
    if 'task_manager' not in st.session_state:
        st.session_state.task_manager = TaskManager()
        st.session_state.voicemail_processor = VoicemailProcessor(st.session_state.task_manager)
        st.session_state.ai_helper = AITaskHelper(st.session_state.task_manager)
    
    task_manager = st.session_state.task_manager
    ai_helper = st.session_state.ai_helper
    
    st.header("📋 Reports & Tasks")
    
    # Top Stats Row
    render_task_stats(task_manager)
    
    # Filters Section
    filters = render_filters()
    
    # Get filtered tasks
    tasks = task_manager.get_tasks(filters)
    
    # Records Table
    render_tasks_table(tasks, task_manager, ai_helper)
    
    # Task Drawer (if task selected)
    if 'selected_task_id' in st.session_state and st.session_state.selected_task_id:
        render_task_drawer(st.session_state.selected_task_id, task_manager, ai_helper)
    
    # Voicemail Upload Section
    render_voicemail_upload(st.session_state.voicemail_processor)

def render_task_stats(task_manager):
    """Render top statistics cards"""
    
    stats = task_manager.get_task_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="🆕 New",
            value=stats.get('new', 0),
            delta=None,
            help="Newly created tasks awaiting assignment"
        )
    
    with col2:
        st.metric(
            label="🔄 In Progress", 
            value=stats.get('in_progress', 0),
            delta=None,
            help="Tasks currently being worked on"
        )
    
    with col3:
        st.metric(
            label="🚫 Blocked",
            value=stats.get('blocked', 0),
            delta=None,
            help="Tasks blocked by dependencies or issues"
        )
    
    with col4:
        st.metric(
            label="✅ Done",
            value=stats.get('done', 0),
            delta=None,
            help="Completed tasks"
        )

def render_filters():
    """Render filter controls and return filter dict"""
    
    st.subheader("🔍 Filters")
    
    col1, col2, col3 = st.columns(3)
    
    filters = {}
    
    with col1:
        # Date filter
        date_filter = st.selectbox(
            "📅 Date Range",
            ["All Time", "Today", "This Week", "This Month", "Custom"],
            help="Filter tasks by creation date"
        )
        
        if date_filter == "Today":
            filters['date_from'] = datetime.now().strftime("%Y-%m-%d")
        elif date_filter == "This Week":
            week_start = datetime.now() - timedelta(days=datetime.now().weekday())
            filters['date_from'] = week_start.strftime("%Y-%m-%d")
        elif date_filter == "This Month":
            month_start = datetime.now().replace(day=1)
            filters['date_from'] = month_start.strftime("%Y-%m-%d")
        elif date_filter == "Custom":
            start_date = st.date_input("Start Date")
            end_date = st.date_input("End Date")
            if start_date:
                filters['date_from'] = start_date.isoformat()
            if end_date:
                filters['date_to'] = end_date.isoformat()
    
    with col2:
        # Source and Assignee filters
        source_filter = st.selectbox(
            "📞 Source",
            ["All", "voicemail", "email", "manual", "system"],
            help="Filter by task source"
        )
        if source_filter != "All":
            filters['source'] = source_filter
        
        assignee_filter = st.selectbox(
            "👤 Assignee", 
            ["All", "Jenny", "Claude", "Me", "Demo", "Luna", "Lexi", "Ava"],
            help="Filter by assigned person/agent"
        )
        if assignee_filter != "All":
            filters['assignee'] = assignee_filter
    
    with col3:
        # Status and Priority filters
        status_filter = st.selectbox(
            "📊 Status",
            ["All", "new", "in_progress", "blocked", "done"],
            help="Filter by task status"
        )
        if status_filter != "All":
            filters['status'] = status_filter
        
        priority_filter = st.selectbox(
            "⚡ Priority",
            ["All", "urgent", "high", "normal", "low"],
            help="Filter by priority level"
        )
        # Priority filter would need additional query logic
    
    return filters

def render_tasks_table(tasks, task_manager, ai_helper):
    """Render the main tasks table"""
    
    st.subheader("📄 Tasks")
    
    if not tasks:
        st.info("No tasks found matching the current filters.")
        return
    
    # Convert tasks to DataFrame for display
    task_data = []
    for task in tasks:
        task_data.append({
            "Title": task.title,
            "Source": f"📞" if task.source == TaskSource.VOICEMAIL else 
                     f"📧" if task.source == TaskSource.EMAIL else
                     f"✋" if task.source == TaskSource.MANUAL else "🤖",
            "Excerpt": task.excerpt[:50] + "..." if len(task.excerpt) > 50 else task.excerpt,
            "Tags": ", ".join(task.tags[:3]) + ("..." if len(task.tags) > 3 else ""),
            "Assignee": task.assignee,
            "Due": task.due_date[:10] if task.due_date else "No due date",
            "Status": task.status.value.title(),
            "Priority": task.priority.value.title(),
            "task_id": task.task_id
        })
    
    df = pd.DataFrame(task_data)
    
    # Display table with selection
    selected_indices = st.dataframe(
        df[["Title", "Source", "Excerpt", "Tags", "Assignee", "Due", "Status", "Priority"]], 
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    # Handle row selection
    if selected_indices and len(selected_indices['selection']['rows']) > 0:
        selected_row = selected_indices['selection']['rows'][0]
        selected_task_id = df.iloc[selected_row]['task_id']
        st.session_state.selected_task_id = selected_task_id

def render_task_drawer(task_id, task_manager, ai_helper):
    """Render task detail drawer"""
    
    # Get task details
    tasks = task_manager.get_tasks({'task_id': task_id})
    if not tasks:
        st.error("Task not found")
        return
    
    task = tasks[0]
    
    st.subheader(f"📝 Task Details: {task.title}")
    
    # Close button
    if st.button("❌ Close", key="close_task_drawer"):
        if 'selected_task_id' in st.session_state:
            del st.session_state.selected_task_id
        st.rerun()
    
    # Task info columns
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Status:** {task.status.value.title()}")
        st.write(f"**Priority:** {task.priority.value.title()}")
        st.write(f"**Assignee:** {task.assignee}")
        st.write(f"**Source:** {task.source.value.title()}")
    
    with col2:
        st.write(f"**Created:** {task.created_at[:19]}")
        st.write(f"**Updated:** {task.updated_at[:19]}")
        if task.due_date:
            st.write(f"**Due Date:** {task.due_date[:19]}")
        st.write(f"**Tags:** {', '.join(task.tags) if task.tags else 'None'}")
    
    # Description
    st.write("**Description:**")
    st.text_area("", value=task.description, height=100, disabled=True, key=f"desc_{task_id}")
    
    # Status update
    col1, col2, col3 = st.columns(3)
    
    with col1:
        new_status = st.selectbox(
            "Update Status",
            [status.value for status in TaskStatus],
            index=[status.value for status in TaskStatus].index(task.status.value),
            key=f"status_{task_id}"
        )
        
        if st.button("Update Status", key=f"update_{task_id}"):
            task_manager.update_task_status(task_id, TaskStatus(new_status))
            st.success("Status updated!")
            st.rerun()
    
    # AI Helpers
    st.write("**🤖 AI Helpers:**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💡 Suggest Next Step", key=f"suggest_{task_id}"):
            suggestion = ai_helper.suggest_next_step(task)
            st.info(f"**Next Step:** {suggestion}")
    
    with col2:
        if st.button("📄 Summarize", key=f"summary_{task_id}"):
            summary = ai_helper.summarize_task(task)
            st.info(f"**Summary:** {summary}")
    
    with col3:
        if st.button("👤 Auto-assign", key=f"assign_{task_id}"):
            new_assignee = ai_helper.auto_assign_task(task)
            st.info(f"**Suggested Assignee:** {new_assignee}")

def render_voicemail_upload(voicemail_processor):
    """Render voicemail upload and processing section"""
    
    st.subheader("📞 Voicemail Processing")
    
    # Upload section
    uploaded_file = st.file_uploader(
        "Upload Voicemail Audio",
        type=['wav', 'mp3', 'ogg', 'm4a'],
        help="Upload voicemail files for automatic transcription and task generation"
    )
    
    if uploaded_file is not None:
        # Save uploaded file
        upload_path = f"uploads/{uploaded_file.name}"
        with open(upload_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"File uploaded: {uploaded_file.name}")
        
        if st.button("🎯 Process Voicemail", key="process_vm"):
            with st.spinner("Processing voicemail..."):
                # Process voicemail
                voicemail = voicemail_processor.process_voicemail_file(upload_path)
                
                # Generate tasks
                tasks = voicemail_processor.generate_tasks_from_voicemail(voicemail)
                
                if tasks:
                    st.success(f"Generated {len(tasks)} tasks from voicemail!")
                    
                    # Display generated tasks
                    for task in tasks:
                        st.write(f"**📋 {task.title}**")
                        st.write(f"   Assigned to: {task.assignee}")
                        st.write(f"   Tags: {', '.join(task.tags)}")
                        st.write(f"   Priority: {task.priority.value}")
                else:
                    st.warning("No tasks could be generated from this voicemail.")
    
    # Processing status
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📊 View Processing Stats", key="vm_stats"):
            # Get voicemail statistics
            st.info("Voicemail processing statistics would be displayed here")
    
    with col2:
        if st.button("🔄 Refresh Tasks", key="refresh_tasks"):
            st.rerun()

# Example usage for integration with main app.py
if __name__ == "__main__":
    st.set_page_config(page_title="Reports & Tasks", layout="wide")
    render_reports_tasks_tab()