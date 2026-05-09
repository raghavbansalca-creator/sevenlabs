"""
Phase 2: Status Transition Nudges — Task Doc Events
====================================================
Real-time triggers that fire on Task save/create via doc_events in hooks.py.

Flat structure — no manager hierarchy:
  - Notifications go to assigned user(s) + task owner (allocator)
  - Escalations go to Raghav (MANAGER_USER) only
  - No "project lead" or "reviewer" concept

Triggers:
  1. Task assigned to someone → assignment notification with context
  2. Task status → Pending Review → notify task owner (allocator) + Raghav
  3. Task status → Completed → notify owner, check dependent tasks
  4. Task created with no assignee → notify Raghav
  5. Task stuck in Working for 3+ days → check-in nudge (via scheduled scan)
  6. Task status → Completed (when overdue) → notify Raghav
"""

import frappe
from frappe.utils import today, getdate, date_diff, now_datetime
import json

MANAGER_USER = "raghav.bansal@sevenlabs.in"


def on_update(doc, method):
    """Fires on every Task save. Detects changes and sends appropriate notifications."""
    from office_customizations.office_customisation.automation.notification_engine import (
        send_direct,
    )

    before = doc.get_doc_before_save()
    if not before:
        return  # New doc — handled by after_insert

    # ── 1. New assignment detection ───────────────────────────────────────
    old_assign = _parse_assign(before.get("_assign"))
    new_assign = _parse_assign(doc.get("_assign"))
    newly_assigned = new_assign - old_assign

    if newly_assigned:
        site_url = frappe.utils.get_url()
        task_link = "{0}/app/task/{1}".format(site_url, doc.name)
        project_info = " (Project: {0})".format(doc.project) if doc.project else ""
        assigner_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user

        for user in newly_assigned:
            user_name = frappe.db.get_value("User", user, "full_name") or user
            send_direct(
                recipients=[user],
                subject="New Task Assigned: {0}".format(doc.subject),
                message=(
                    "Hi {0},<br><br>"
                    "You have been assigned a new task:<br>"
                    "<b><a href='{1}'>{2}</a></b>{3}<br><br>"
                    "Priority: {4}<br>"
                    "Status: {5}<br>"
                    "Due: {6}<br>"
                    "Assigned by: {7}<br><br>"
                    "<i>— SLV Automation</i>"
                ).format(
                    user_name, task_link, doc.subject, project_info,
                    doc.priority, doc.status,
                    _format_date(doc.exp_end_date),
                    assigner_name,
                ),
                channel="All",
                reference_doctype="Task",
                reference_name=doc.name,
                event_type="Task Assigned",
            )

    # ── 2. Status changed to Pending Review ───────────────────────────────
    if before.status != "Pending Review" and doc.status == "Pending Review":
        _notify_pending_review(doc)

    # ── 3. Status changed to Completed ────────────────────────────────────
    if before.status != "Completed" and doc.status == "Completed":
        _handle_task_completed(doc, before)

    # ── 4. Status changed to Cancelled ────────────────────────────────────
    if before.status != "Cancelled" and doc.status == "Cancelled":
        _notify_task_cancelled(doc)


def after_insert(doc, method):
    """Fires after a new Task is created.

    If the task has no assignee, auto-assign it to the creator (doc.owner).
    Defers via the short queue so that any explicit assign_to.add follow-up
    (separate API request from the bot or UI) has a chance to land first.
    The deferred job re-checks for any ToDo and skips if one already exists.
    """
    creator = doc.owner
    if not creator or creator == "Administrator":
        return

    frappe.enqueue(
        "office_customizations.office_customisation.doc_events.task_events._auto_assign_to_creator_deferred",
        queue="short",
        task_name=doc.name,
        creator=creator,
    )


def _auto_assign_to_creator_deferred(task_name, creator):
    """Run in a background job. Skip if any ToDo exists for the task."""
    import time
    time.sleep(2)
    if not frappe.db.exists("Task", task_name):
        return
    has_todo = frappe.db.exists("ToDo", {
        "reference_type": "Task",
        "reference_name": task_name,
    })
    if has_todo:
        return
    try:
        from frappe.desk.form.assign_to import add as assign_add
        # Run as Administrator so the assignment can be created on docs
        # owned by users without write-access on ToDo for arbitrary users.
        frappe.set_user("Administrator")
        subject = frappe.db.get_value("Task", task_name, "subject") or task_name
        assign_add({
            "doctype": "Task",
            "name": task_name,
            "assign_to": [creator],
            "description": subject,
        })
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Task auto-assign-to-creator failed")


def _notify_pending_review(doc):
    """
    Notify task owner (allocator) + Raghav that work is ready for review.
    Flat structure: no project lead / reviewer concept.
    """
    from office_customizations.office_customisation.automation.notification_engine import send_direct

    site_url = frappe.utils.get_url()
    task_link = "{0}/app/task/{1}".format(site_url, doc.name)
    worker_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user

    # Notify: task owner (allocator) + Raghav, excluding the person who set it
    recipients = set()
    if doc.owner and doc.owner != "Administrator" and doc.owner != frappe.session.user:
        recipients.add(doc.owner)
    recipients.add(MANAGER_USER)
    # Don't notify the person who marked it Pending Review
    recipients.discard(frappe.session.user)

    if not recipients:
        return

    for recipient in recipients:
        send_direct(
            recipients=[recipient],
            subject="Ready for Review: {0}".format(doc.subject),
            message=(
                "<b>Task ready for review</b><br><br>"
                "Task: <a href='{0}'>{1}</a><br>"
                "Project: {2}<br>"
                "Submitted by: {3}<br><br>"
                "Please review and update the status.<br><br>"
                "<i>— SLV Automation</i>"
            ).format(
                task_link, doc.subject,
                doc.project or "N/A",
                worker_name,
            ),
            channel="All",
            reference_doctype="Task",
            reference_name=doc.name,
            event_type="Task Pending Review",
        )


def _handle_task_completed(doc, before):
    """Handle task completion: notify owner, check dependents, handle overdue."""
    from office_customizations.office_customisation.automation.notification_engine import send_direct

    site_url = frappe.utils.get_url()
    completer_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user

    # Notify task owner (allocator) that task is done
    if doc.owner and doc.owner != frappe.session.user and doc.owner != "Administrator":
        task_link = "{0}/app/task/{1}".format(site_url, doc.name)
        send_direct(
            recipients=[doc.owner],
            subject="Task Completed: {0}".format(doc.subject),
            message=(
                "<b>Task Completed</b><br><br>"
                "Task: <a href='{0}'>{1}</a><br>"
                "Project: {2}<br>"
                "Completed by: {3}<br><br>"
                "<i>— SLV Automation</i>"
            ).format(task_link, doc.subject, doc.project or "N/A", completer_name),
            channel="ERPNext",
            reference_doctype="Task",
            reference_name=doc.name,
            event_type="Task Completed",
        )

    # If overdue completion, notify manager
    if doc.exp_end_date and getdate(doc.exp_end_date) < getdate(today()):
        days_late = date_diff(today(), doc.exp_end_date)
        send_direct(
            recipients=[MANAGER_USER],
            subject="Overdue Task Completed: {0} ({1}d late)".format(doc.subject, days_late),
            message=(
                "<b>Overdue Task Now Completed</b><br><br>"
                "Task: {0}<br>"
                "Project: {1}<br>"
                "Was due: {2}<br>"
                "Completed: {3} ({4} days late)<br>"
                "Completed by: {5}<br><br>"
                "<i>— SLV Automation</i>"
            ).format(
                doc.subject, doc.project or "N/A",
                _format_date(doc.exp_end_date),
                today(), days_late, completer_name,
            ),
            channel="ERPNext",
            reference_doctype="Task",
            reference_name=doc.name,
            event_type="Task Completed Late",
        )

    # ── Auto-open dependent tasks ─────────────────────────────────────────
    _activate_dependent_tasks(doc)


def _activate_dependent_tasks(completed_task):
    """
    Find tasks that depend on the completed task and auto-open them.
    In Frappe Task, dependent tasks are stored via Task Depends On child table.
    """
    from office_customizations.office_customisation.automation.notification_engine import send_direct

    # Find tasks that list this task as a dependency
    dependent_links = frappe.get_all(
        "Task Depends On",
        filters={"task": completed_task.name},
        fields=["parent"],
    )

    if not dependent_links:
        return

    site_url = frappe.utils.get_url()

    for link in dependent_links:
        dep_task = frappe.get_doc("Task", link.parent)

        # Only activate if the dependent task is still Open/on hold
        if dep_task.status not in ("Open", "Hold"):
            continue

        # Check if ALL dependencies are completed
        all_deps = frappe.get_all(
            "Task Depends On",
            filters={"parent": dep_task.name},
            fields=["task"],
        )
        all_complete = True
        for dep in all_deps:
            dep_status = frappe.db.get_value("Task", dep.task, "status")
            if dep_status != "Completed":
                all_complete = False
                break

        if not all_complete:
            continue

        # All dependencies met — notify assignees
        assigned = _parse_assign(dep_task.get("_assign"))
        if assigned:
            task_link = "{0}/app/task/{1}".format(site_url, dep_task.name)
            for user in assigned:
                user_name = frappe.db.get_value("User", user, "full_name") or user
                send_direct(
                    recipients=[user],
                    subject="Task Unblocked: {0}".format(dep_task.subject),
                    message=(
                        "Hi {0},<br><br>"
                        "All dependencies for your task are now complete:<br>"
                        "<b><a href='{1}'>{2}</a></b><br>"
                        "Project: {3}<br><br>"
                        "Dependency completed: {4}<br>"
                        "You can now proceed with this task.<br><br>"
                        "<i>— SLV Automation</i>"
                    ).format(
                        user_name, task_link, dep_task.subject,
                        dep_task.project or "N/A",
                        completed_task.subject,
                    ),
                    channel="All",
                    reference_doctype="Task",
                    reference_name=dep_task.name,
                    event_type="Task Unblocked",
                )


def _notify_task_cancelled(doc):
    """Notify assigned users when a task is cancelled."""
    from office_customizations.office_customisation.automation.notification_engine import send_direct

    assigned = _parse_assign(doc.get("_assign"))
    if not assigned:
        return

    canceller_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user

    for user in assigned:
        if user == frappe.session.user:
            continue
        user_name = frappe.db.get_value("User", user, "full_name") or user
        send_direct(
            recipients=[user],
            subject="Task Cancelled: {0}".format(doc.subject),
            message=(
                "Hi {0},<br><br>"
                "The following task has been cancelled:<br>"
                "<b>{1}</b><br>"
                "Project: {2}<br>"
                "Cancelled by: {3}<br><br>"
                "<i>— SLV Automation</i>"
            ).format(user_name, doc.subject, doc.project or "N/A", canceller_name),
            channel="ERPNext",
            reference_doctype="Task",
            reference_name=doc.name,
            event_type="Task Cancelled",
        )


# ── Scheduled: Stuck Task Scanner (runs every 4 hours) ───────────────────────

def scan_stuck_tasks():
    """
    Finds tasks stuck in 'Working' status for 3+ days without updates.
    Sends a check-in nudge to the assignee.
    Called by scheduler every 4 hours.
    """
    from office_customizations.office_customisation.automation.notification_engine import send_direct

    three_days_ago = frappe.utils.add_days(today(), -3)

    stuck_tasks = frappe.get_all(
        "Task",
        filters={
            "status": "Working",
            "modified": ["<", three_days_ago],
        },
        fields=["name", "subject", "project", "status", "priority", "_assign", "owner", "modified"],
    )

    site_url = frappe.utils.get_url()

    for task in stuck_tasks:
        # Skip if already nudged today
        already_nudged = frappe.db.exists("Notification Log OC", {
            "reference_doctype": "Task",
            "reference_name": task.name,
            "event_type": "Task Stuck Check-In",
            "creation": [">=", today()],
        })
        if already_nudged:
            continue

        assigned = _parse_assign(task.get("_assign"))
        days_stuck = date_diff(today(), task.modified)
        task_link = "{0}/app/task/{1}".format(site_url, task.name)

        recipients = list(assigned) if assigned else []
        if task.owner and task.owner != "Administrator":
            recipients.append(task.owner)
        recipients = list(set(recipients))

        if not recipients:
            continue

        for user in recipients:
            user_name = frappe.db.get_value("User", user, "full_name") or user
            send_direct(
                recipients=[user],
                subject="Check-in: {0} (Working for {1} days)".format(task.subject, days_stuck),
                message=(
                    "Hi {0},<br><br>"
                    "Your task <b><a href='{1}'>{2}</a></b> has been in "
                    "'Working' status for <b>{3} days</b> without updates.<br>"
                    "Project: {4}<br><br>"
                    "Are you still working on this? Need any help?<br>"
                    "Please update the task status or add a comment.<br><br>"
                    "<i>— SLV Automation</i>"
                ).format(user_name, task_link, task.subject, days_stuck, task.project or "N/A"),
                channel="All",
                reference_doctype="Task",
                reference_name=task.name,
                event_type="Task Stuck Check-In",
            )

    frappe.db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_assign(raw):
    """Parse _assign field into a set of user emails."""
    if not raw:
        return set()
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return set(u for u in parsed if u)
        except (json.JSONDecodeError, TypeError):
            return set()
    if isinstance(raw, list):
        return set(u for u in raw if u)
    return set()


def _format_date(dt):
    """Format a date for display."""
    if not dt:
        return "Not set"
    try:
        return getdate(dt).strftime("%d %b %Y")
    except Exception:
        return str(dt)
