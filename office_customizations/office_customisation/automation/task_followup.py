"""
Phase 2: Proactive Follow-Up Agent — Daily Task Follow-Up
=========================================================
Runs daily at 9 AM. Scans all open tasks and sends ONE grouped digest
per user covering:
  1. Overdue tasks (past due date)
  2. Due today
  3. Due this week (next 7 days)
  4. No tasks assigned alert

Smart features:
  - Groups all reminders into a single digest per user (no spam)
  - Respects quiet hours (handled by notification_engine)
  - Tracks via Notification Log OC to avoid duplicate sends
  - Sends manager summary to MANAGER_USER
"""

import frappe
from frappe.utils import today, add_days, getdate, now_datetime
import json

MANAGER_USER = "raghav.bansal@sevenlabs.in"


def run():
    """Main entry point called by scheduler at 9 AM daily."""
    try:
        _run_daily_followup()
    except Exception:
        frappe.log_error("Daily Task Follow-Up failed", "SLV Phase 2")


def _run_daily_followup():
    from office_customizations.office_customisation.automation.notification_engine import (
        send_direct,
    )

    today_date = today()
    today_dt = getdate(today_date)
    week_end = add_days(today_date, 6)

    # Skip weekends
    if today_dt.weekday() in (5, 6):
        return

    # ── Fetch all relevant tasks in bulk ──────────────────────────────────
    open_statuses = ["Open", "Working", "Pending Review", "Overdue"]

    all_tasks = frappe.get_all(
        "Task",
        filters={
            "status": ["in", open_statuses],
        },
        fields=[
            "name", "subject", "project", "status", "priority",
            "exp_end_date", "_assign", "owner",
        ],
        limit_page_length=0,
    )

    # ── Categorize tasks per user ─────────────────────────────────────────
    # user_data[email] = {overdue: [], due_today: [], due_this_week: []}
    user_data = {}
    all_active_users = _get_all_active_users()

    for user in all_active_users:
        user_data[user] = {
            "overdue": [],
            "due_today": [],
            "due_this_week": [],
        }

    for task in all_tasks:
        recipients = _get_task_recipients(task)
        due = getdate(task.exp_end_date) if task.exp_end_date else None

        for user in recipients:
            if user not in user_data:
                user_data[user] = {"overdue": [], "due_today": [], "due_this_week": []}

            if due and due < today_dt:
                days_overdue = (today_dt - due).days
                task_info = task.copy()
                task_info["days_overdue"] = days_overdue
                user_data[user]["overdue"].append(task_info)
            elif due and due == today_dt:
                user_data[user]["due_today"].append(task)
            elif due and today_dt < due <= getdate(week_end):
                user_data[user]["due_this_week"].append(task)

    # ── Track users with no tasks assigned ────────────────────────────────
    users_with_tasks = set()
    for task in all_tasks:
        for user in _get_assigned_users(task):
            users_with_tasks.add(user)

    # ── Send per-user digest ──────────────────────────────────────────────
    manager_summary = {
        "total_overdue": 0,
        "total_due_today": 0,
        "total_due_week": 0,
        "users_notified": 0,
        "users_no_tasks": [],
    }

    for user, data in user_data.items():
        overdue = data["overdue"]
        due_today = data["due_today"]
        due_week = data["due_this_week"]

        # Skip if nothing to report
        has_no_tasks = user not in users_with_tasks and user != MANAGER_USER
        if not overdue and not due_today and not due_week and not has_no_tasks:
            continue

        # Check if already sent today
        already_sent = frappe.db.exists("Notification Log OC", {
            "user": user,
            "event_type": "Daily Task Digest",
            "creation": [">=", today_date],
        })
        if already_sent:
            continue

        # Build digest message
        user_name = frappe.db.get_value("User", user, "full_name") or user
        msg = _build_digest_message(user_name, overdue, due_today, due_week, has_no_tasks)
        subject = _build_digest_subject(overdue, due_today, due_week)

        send_direct(
            recipients=[user],
            subject=subject,
            message=msg,
            channel="All",
            event_type="Daily Task Digest",
        )

        manager_summary["total_overdue"] = manager_summary["total_overdue"] + len(overdue)
        manager_summary["total_due_today"] = manager_summary["total_due_today"] + len(due_today)
        manager_summary["total_due_week"] = manager_summary["total_due_week"] + len(due_week)
        manager_summary["users_notified"] = manager_summary["users_notified"] + 1
        if has_no_tasks:
            manager_summary["users_no_tasks"].append(user_name)

    # ── Send manager summary ──────────────────────────────────────────────
    _send_manager_summary(manager_summary)

    frappe.db.commit()


def _build_digest_subject(overdue, due_today, due_week):
    """Build a concise subject line."""
    parts = []
    if overdue:
        parts.append(f"{len(overdue)} overdue")
    if due_today:
        parts.append(f"{len(due_today)} due today")
    if due_week:
        parts.append(f"{len(due_week)} due this week")
    if parts:
        return "Daily Task Summary: " + ", ".join(parts)
    return "Daily Task Summary"


def _build_digest_message(user_name, overdue, due_today, due_week, has_no_tasks):
    """Build a single HTML digest message for a user."""
    site_url = frappe.utils.get_url()
    parts = [f"Good morning {user_name},<br><br>"]
    parts.append(f"Here is your task summary for {getdate(today()).strftime('%d %b %Y')}:<br><br>")

    if overdue:
        parts.append(f"<b style='color:#e74c3c;'>Overdue Tasks ({len(overdue)})</b><br>")
        # Sort by days overdue descending
        for t in sorted(overdue, key=lambda x: x.get("days_overdue", 0), reverse=True):
            link = f"{site_url}/app/task/{t.name}"
            parts.append(
                f"&bull; <a href='{link}'>{t.subject}</a> "
                f"— {t.get('days_overdue', '?')} days overdue "
                f"(Project: {t.project or 'N/A'}, Priority: {t.priority})<br>"
            )
        parts.append("<br>")

    if due_today:
        parts.append(f"<b style='color:#f39c12;'>Due Today ({len(due_today)})</b><br>")
        for t in due_today:
            link = f"{site_url}/app/task/{t.name}"
            parts.append(
                f"&bull; <a href='{link}'>{t.subject}</a> "
                f"— Status: {t.status} "
                f"(Project: {t.project or 'N/A'}, Priority: {t.priority})<br>"
            )
        parts.append("<br>")

    if due_week:
        parts.append(f"<b style='color:#3498db;'>Due This Week ({len(due_week)})</b><br>")
        for t in sorted(due_week, key=lambda x: getdate(x.exp_end_date) if x.exp_end_date else getdate("2099-12-31")):
            link = f"{site_url}/app/task/{t.name}"
            due_str = getdate(t.exp_end_date).strftime("%d %b") if t.exp_end_date else "?"
            parts.append(
                f"&bull; <a href='{link}'>{t.subject}</a> "
                f"— Due: {due_str} "
                f"(Project: {t.project or 'N/A'})<br>"
            )
        parts.append("<br>")

    if has_no_tasks:
        parts.append(
            "<b>No tasks currently assigned to you.</b> "
            "Please check with your project lead for work allocation.<br><br>"
        )

    if not overdue and not due_today and not due_week and not has_no_tasks:
        parts.append("All clear! No urgent tasks today.<br>")

    parts.append("<br><i>— SLV Automation</i>")
    return "".join(parts)


def _send_manager_summary(summary):
    """Send a brief summary to the manager about today's follow-up run."""
    from office_customizations.office_customisation.automation.notification_engine import send_direct

    if summary["users_notified"] == 0:
        return  # Nothing happened, don't bother manager

    already_sent = frappe.db.exists("Notification Log OC", {
        "user": MANAGER_USER,
        "event_type": "Daily Follow-Up Summary",
        "creation": [">=", today()],
    })
    if already_sent:
        return

    msg_parts = [
        "<b>Daily Follow-Up Agent Report</b><br><br>",
        f"Notifications sent to: {summary['users_notified']} team members<br>",
        f"Total overdue tasks flagged: {summary['total_overdue']}<br>",
        f"Total tasks due today: {summary['total_due_today']}<br>",
        f"Total tasks due this week: {summary['total_due_week']}<br>",
    ]

    if summary["users_no_tasks"]:
        msg_parts.append(f"<br><b>Users with no tasks:</b> {', '.join(summary['users_no_tasks'])}<br>")

    msg_parts.append("<br><i>— SLV Automation (Phase 2)</i>")

    send_direct(
        recipients=[MANAGER_USER],
        subject=f"Follow-Up Agent: {summary['users_notified']} users notified, {summary['total_overdue']} overdue",
        message="".join(msg_parts),
        channel="ERPNext",
        event_type="Daily Follow-Up Summary",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_assigned_users(task):
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


def _get_task_recipients(task):
    """Get all people who should be notified: assigned + owner."""
    recipients = set(_get_assigned_users(task))
    if task.owner and task.owner != "Administrator":
        recipients.add(task.owner)
    return list(recipients)


def _get_all_active_users():
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


# ── Whitelisted test trigger ─────────────────────────────────────────────────

@frappe.whitelist()
def trigger_daily_followup():
    """Manually trigger daily follow-up for testing. System Manager only."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw("Only System Manager can trigger this")
    _run_daily_followup()
    frappe.db.commit()
    return {"status": "ok", "message": "Daily follow-up triggered"}
