"""
SLV Automation Scheduler
========================
Scheduled tasks that trigger notifications automatically.

Flat structure — no manager hierarchy:
  - Task notifications → assigned user(s) + task owner (allocator)
  - Timesheet reminders → each individual user
  - Manager digest + escalations → raghav.bansal@sevenlabs.in only
  - Escalation chain: overdue → assigned user → 24h → Raghav → 48h → Raghav again
"""

import frappe
from frappe.utils import today, add_days, getdate, now_datetime, cint
import json

MANAGER_USER = "raghav.bansal@sevenlabs.in"

# ── Helper: Get assigned users from _assign field ─────────────────────────────

def get_assigned_users(task):
    """Extract assigned user emails from a task's _assign JSON field."""
    assign = task.get("_assign")
    if not assign:
        return []
    if isinstance(assign, str):
        try:
            assign = json.loads(assign)
        except (json.JSONDecodeError, TypeError):
            return []
    return [u for u in assign if u]


def get_task_recipients(task):
    """Get all people who should be notified about a task: assigned + owner."""
    recipients = set(get_assigned_users(task))
    # Also notify the task owner (person who created/allocated it)
    if task.owner and task.owner != "Administrator":
        recipients.add(task.owner)
    return list(recipients)


def get_all_active_users():
    """Get all enabled system users (excluding Administrator and Guest)."""
    return frappe.get_all(
        "User",
        filters={
            "enabled": 1,
            "user_type": "System User",
            "name": ["not in", ["Administrator", "Guest"]],
        },
        pluck="name",
    )


# ── Daily: Task Overdue Notifications ─────────────────────────────────────────

def notify_overdue_tasks():
    """
    Runs daily. Finds all open tasks past their due date.
    Notifies assigned users + task owner.
    Skips tasks that were already notified today (via Notification Log OC).
    """
    from office_customizations.office_customisation.automation.notification_engine import send_notification

    overdue_tasks = frappe.get_all(
        "Task",
        filters={
            "status": ["in", ["Open", "Working", "Pending Review", "Overdue"]],
            "exp_end_date": ["<", today()],
            "exp_end_date": ["is", "set"],
        },
        fields=["name", "subject", "project", "exp_end_date", "priority", "_assign", "owner"],
    )

    today_date = today()

    for task in overdue_tasks:
        # Skip if already notified today for this task
        already_sent = frappe.db.exists("Notification Log OC", {
            "reference_doctype": "Task",
            "reference_name": task.name,
            "event_type": "Task Overdue",
            "creation": [">=", today_date],
        })
        if already_sent:
            continue

        recipients = get_task_recipients(task)
        if not recipients:
            continue

        days_overdue = (getdate(today_date) - getdate(task.exp_end_date)).days
        task["days_overdue"] = days_overdue

        send_notification(
            recipients=recipients,
            template_name="Task Overdue",
            context={"task": task},
            reference_doctype="Task",
            reference_name=task.name,
        )

    frappe.db.commit()


# ── Daily: Task Due Today Notifications ───────────────────────────────────────

def notify_tasks_due_today():
    """
    Runs daily. Finds all open tasks due today.
    Notifies assigned users + task owner.
    """
    from office_customizations.office_customisation.automation.notification_engine import send_notification

    due_today = frappe.get_all(
        "Task",
        filters={
            "status": ["in", ["Open", "Working", "Pending Review"]],
            "exp_end_date": today(),
        },
        fields=["name", "subject", "project", "exp_end_date", "priority", "_assign", "owner"],
    )

    for task in due_today:
        already_sent = frappe.db.exists("Notification Log OC", {
            "reference_doctype": "Task",
            "reference_name": task.name,
            "event_type": "Task Due Today",
            "creation": [">=", today()],
        })
        if already_sent:
            continue

        recipients = get_task_recipients(task)
        if not recipients:
            continue

        send_notification(
            recipients=recipients,
            template_name="Task Due Today",
            context={"task": task},
            reference_doctype="Task",
            reference_name=task.name,
        )

    frappe.db.commit()


# ── Daily: Timesheet Missing Notifications ────────────────────────────────────

def notify_missing_timesheets():
    """
    Runs daily (except weekends). Checks if each user submitted a timesheet yesterday.
    If not, sends a reminder.
    """
    from office_customizations.office_customisation.automation.notification_engine import send_notification

    yesterday = add_days(today(), -1)

    # Skip weekends (Saturday=5, Sunday=6)
    if getdate(yesterday).weekday() in (5, 6):
        return

    active_users = get_all_active_users()

    for user in active_users:
        # Check if user has any timesheet entry for yesterday
        has_timesheet = frappe.db.exists("Timesheet", {
            "owner": user,
            "start_date": ["<=", yesterday],
            "end_date": [">=", yesterday],
            "docstatus": ["in", [0, 1]],  # Draft or Submitted
        })

        if has_timesheet:
            continue

        # Skip if already reminded today
        already_sent = frappe.db.exists("Notification Log OC", {
            "user": user,
            "event_type": "Timesheet Missing",
            "creation": [">=", today()],
        })
        if already_sent:
            continue

        user_name = frappe.db.get_value("User", user, "full_name") or user

        send_notification(
            recipients=[user],
            template_name="Timesheet Missing",
            context={"date": yesterday, "user_name": user_name},
        )

    frappe.db.commit()


# ── Daily: Escalation Check ──────────────────────────────────────────────────

def check_escalations():
    """
    Runs daily. Checks overdue tasks that haven't been acted on.
    Level 1: 24h+ overdue → notify manager (Raghav)
    Level 2: 48h+ overdue → notify manager again with urgency
    """
    from office_customizations.office_customisation.automation.notification_engine import send_direct

    settings = frappe.get_single("SLV Notification Settings")
    if not settings.escalation_enabled:
        return

    level_1_days = max(1, cint(settings.level_1_delay_hours) // 24)
    level_2_days = max(2, cint(settings.level_2_delay_hours) // 24)

    level_1_date = add_days(today(), -level_1_days)
    level_2_date = add_days(today(), -level_2_days)

    manager = settings.final_escalation_user or MANAGER_USER

    # Level 2 escalations (most urgent first)
    level_2_tasks = frappe.get_all(
        "Task",
        filters={
            "status": ["in", ["Open", "Working", "Pending Review", "Overdue"]],
            "exp_end_date": ["<=", level_2_date],
            "exp_end_date": ["is", "set"],
        },
        fields=["name", "subject", "project", "exp_end_date", "priority", "_assign", "owner"],
    )

    for task in level_2_tasks:
        already_sent = frappe.db.exists("Notification Log OC", {
            "reference_doctype": "Task",
            "reference_name": task.name,
            "event_type": "Task Escalation Level 2",
            "creation": [">=", today()],
        })
        if already_sent:
            continue

        assigned = get_assigned_users(task)
        assigned_names = ", ".join(
            [frappe.db.get_value("User", u, "full_name") or u for u in assigned]
        ) if assigned else "Unassigned"
        days = (getdate(today()) - getdate(task.exp_end_date)).days

        send_direct(
            recipients=[manager],
            subject=f"URGENT Escalation: {task.subject} ({days}d overdue)",
            message=f"<b>Level 2 Escalation</b><br>"
                    f"Task: {task.subject}<br>"
                    f"Project: {task.project}<br>"
                    f"Due: {task.exp_end_date}<br>"
                    f"Overdue by: {days} days<br>"
                    f"Assigned to: {assigned_names}<br>"
                    f"Priority: {task.priority}<br><br>"
                    f"This task requires immediate attention.",
            channel="All",
            reference_doctype="Task",
            reference_name=task.name,
            event_type="Task Escalation Level 2",
        )

    # Level 1 escalations (skip tasks already at level 2)
    level_2_names = [t.name for t in level_2_tasks]
    level_1_tasks = frappe.get_all(
        "Task",
        filters={
            "status": ["in", ["Open", "Working", "Pending Review", "Overdue"]],
            "exp_end_date": ["<=", level_1_date],
            "exp_end_date": [">", level_2_date],
        },
        fields=["name", "subject", "project", "exp_end_date", "priority", "_assign", "owner"],
    )

    for task in level_1_tasks:
        if task.name in level_2_names:
            continue

        already_sent = frappe.db.exists("Notification Log OC", {
            "reference_doctype": "Task",
            "reference_name": task.name,
            "event_type": "Task Escalation Level 1",
            "creation": [">=", today()],
        })
        if already_sent:
            continue

        assigned = get_assigned_users(task)
        assigned_names = ", ".join(
            [frappe.db.get_value("User", u, "full_name") or u for u in assigned]
        ) if assigned else "Unassigned"
        days = (getdate(today()) - getdate(task.exp_end_date)).days

        send_direct(
            recipients=[manager],
            subject=f"Escalation: {task.subject} ({days}d overdue)",
            message=f"<b>Level 1 Escalation</b><br>"
                    f"Task: {task.subject}<br>"
                    f"Project: {task.project}<br>"
                    f"Due: {task.exp_end_date}<br>"
                    f"Overdue by: {days} days<br>"
                    f"Assigned to: {assigned_names}<br>"
                    f"Priority: {task.priority}",
            channel="All",
            reference_doctype="Task",
            reference_name=task.name,
            event_type="Task Escalation Level 1",
        )

    frappe.db.commit()


# ── Weekly: Manager Digest ────────────────────────────────────────────────────

def send_weekly_digest():
    """
    Runs weekly (Monday). Sends Raghav a summary of:
    - Tasks completed last week
    - Tasks still overdue
    - Timesheet compliance per user
    - Upcoming deadlines this week
    """
    from office_customizations.office_customisation.automation.notification_engine import send_direct

    week_start = add_days(today(), -7)
    week_end = add_days(today(), -1)
    this_week_end = add_days(today(), 6)

    # Completed tasks last week
    completed = frappe.get_all(
        "Task",
        filters={
            "status": "Completed",
            "completed_on": ["between", [week_start, week_end]],
        },
        fields=["subject", "project", "owner", "_assign"],
    )

    # Still overdue
    overdue = frappe.get_all(
        "Task",
        filters={
            "status": ["in", ["Open", "Working", "Pending Review", "Overdue"]],
            "exp_end_date": ["<", today()],
            "exp_end_date": ["is", "set"],
        },
        fields=["subject", "project", "exp_end_date", "_assign"],
    )

    # Due this week
    upcoming = frappe.get_all(
        "Task",
        filters={
            "status": ["in", ["Open", "Working", "Pending Review"]],
            "exp_end_date": ["between", [today(), this_week_end]],
        },
        fields=["subject", "project", "exp_end_date", "_assign", "priority"],
    )

    # Timesheet compliance last week
    active_users = get_all_active_users()
    ts_compliance = []
    for user in active_users:
        ts_count = frappe.db.count("Timesheet", {
            "owner": user,
            "start_date": [">=", week_start],
            "docstatus": ["in", [0, 1]],
        })
        user_name = frappe.db.get_value("User", user, "full_name") or user
        ts_compliance.append({"user": user_name, "count": ts_count})

    # Build digest message
    msg_parts = [f"<b>Weekly Team Summary</b><br>Week: {week_start} to {week_end}<br><hr>"]

    msg_parts.append(f"<b>Completed Last Week:</b> {len(completed)}<br>")
    for t in completed[:10]:
        msg_parts.append(f"  - {t.subject} ({t.project})<br>")

    msg_parts.append(f"<br><b>Currently Overdue:</b> {len(overdue)}<br>")
    for t in overdue[:10]:
        assigned = get_assigned_users(t)
        who = ", ".join([frappe.db.get_value("User", u, "full_name") or u for u in assigned]) if assigned else "Unassigned"
        msg_parts.append(f"  - {t.subject} (due {t.exp_end_date}, {who})<br>")

    msg_parts.append(f"<br><b>Due This Week:</b> {len(upcoming)}<br>")
    for t in upcoming[:10]:
        assigned = get_assigned_users(t)
        who = ", ".join([frappe.db.get_value("User", u, "full_name") or u for u in assigned]) if assigned else "Unassigned"
        msg_parts.append(f"  - {t.subject} (due {t.exp_end_date}, {t.priority}, {who})<br>")

    msg_parts.append(f"<br><b>Timesheet Compliance (last week):</b><br>")
    for tc in sorted(ts_compliance, key=lambda x: x["count"]):
        status = "OK" if tc["count"] > 0 else "MISSING"
        msg_parts.append(f"  - {tc['user']}: {tc['count']} timesheets ({status})<br>")

    message = "".join(msg_parts)

    send_direct(
        recipients=[MANAGER_USER],
        subject=f"Weekly Team Summary ({week_start} to {week_end})",
        message=message,
        channel="All",
        event_type="Weekly Manager Digest",
    )

    frappe.db.commit()


# ── Doc Event: Task Assignment Changed ────────────────────────────────────────

def on_task_update(doc, method):
    """
    Fires on Task save. Detects new assignments and sends notifications.
    Also detects status changes to 'Completed'.
    """
    from office_customizations.office_customisation.automation.notification_engine import send_notification, send_direct

    # Check if _assign changed (new assignment)
    old_assign = set()
    if doc.get_doc_before_save():
        old_raw = doc.get_doc_before_save().get("_assign") or "[]"
        if isinstance(old_raw, str):
            try:
                old_assign = set(json.loads(old_raw))
            except (json.JSONDecodeError, TypeError):
                pass

    new_raw = doc.get("_assign") or "[]"
    if isinstance(new_raw, str):
        try:
            new_assign = set(json.loads(new_raw))
        except (json.JSONDecodeError, TypeError):
            new_assign = set()
    else:
        new_assign = set(new_raw) if new_raw else set()

    newly_assigned = new_assign - old_assign

    if newly_assigned:
        for user in newly_assigned:
            send_notification(
                recipients=[user],
                template_name="Task Assigned",
                context={"task": doc},
                reference_doctype="Task",
                reference_name=doc.name,
            )

    # Check if status changed to Completed
    if doc.get_doc_before_save():
        old_status = doc.get_doc_before_save().status
        if old_status != "Completed" and doc.status == "Completed":
            # Notify the task owner (allocator) that task is done
            if doc.owner and doc.owner != frappe.session.user and doc.owner != "Administrator":
                assigned_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
                send_direct(
                    recipients=[doc.owner],
                    subject=f"Task Completed: {doc.subject}",
                    message=f"<b>Task Completed</b><br>"
                            f"Task: {doc.subject}<br>"
                            f"Project: {doc.project}<br>"
                            f"Completed by: {assigned_name}",
                    channel="ERPNext",
                    reference_doctype="Task",
                    reference_name=doc.name,
                    event_type="Task Completed",
                )

            # Also notify manager if it was overdue
            if doc.exp_end_date and getdate(doc.exp_end_date) < getdate(today()):
                send_direct(
                    recipients=[MANAGER_USER],
                    subject=f"Overdue Task Completed: {doc.subject}",
                    message=f"<b>Overdue Task Now Completed</b><br>"
                            f"Task: {doc.subject}<br>"
                            f"Project: {doc.project}<br>"
                            f"Was due: {doc.exp_end_date}<br>"
                            f"Completed: {today()}",
                    channel="ERPNext",
                    reference_doctype="Task",
                    reference_name=doc.name,
                    event_type="Task Completed",
                )


# ── Combined Daily Runner ────────────────────────────────────────────────────

def run_daily_notifications():
    """Single entry point for all daily notification jobs."""
    try:
        notify_tasks_due_today()
    except Exception:
        frappe.log_error("Daily: notify_tasks_due_today failed", "SLV Scheduler")

    try:
        notify_overdue_tasks()
    except Exception:
        frappe.log_error("Daily: notify_overdue_tasks failed", "SLV Scheduler")

    try:
        notify_missing_timesheets()
    except Exception:
        frappe.log_error("Daily: notify_missing_timesheets failed", "SLV Scheduler")

    try:
        check_escalations()
    except Exception:
        frappe.log_error("Daily: check_escalations failed", "SLV Scheduler")


def run_weekly_digest():
    """Single entry point for weekly digest."""
    try:
        send_weekly_digest()
    except Exception:
        frappe.log_error("Weekly: send_weekly_digest failed", "SLV Scheduler")
