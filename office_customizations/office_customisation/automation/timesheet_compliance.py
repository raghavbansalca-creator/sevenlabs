"""
Phase 2: Proactive Follow-Up Agent — Timesheet Compliance Checker
=================================================================
Runs daily at 6 PM. Checks if each team member has logged their
minimum required hours for the day.

Features:
  - Configurable minimum hours per person (default 6h full-time)
  - Counts actual hours from Timesheet Detail (time_logs child table)
  - Multi-day tracking: second nudge next morning if still incomplete
  - Escalation to manager after 2+ consecutive days missing
  - Weekly compliance report to manager (sent with weekly digest)
"""

import frappe
from frappe.utils import today, add_days, getdate, now_datetime, flt
import json

MANAGER_USER = "raghav.bansal@sevenlabs.in"
DEFAULT_MIN_HOURS = 6.0


def run():
    """Main entry point called by scheduler at 6 PM daily."""
    try:
        _run_compliance_check()
    except Exception:
        frappe.log_error("Timesheet Compliance Check failed", "SLV Phase 2")


def _run_compliance_check():
    from office_customizations.office_customisation.automation.notification_engine import send_direct

    today_date = today()
    today_dt = getdate(today_date)
    yesterday = add_days(today_date, -1)

    # Skip weekends
    if today_dt.weekday() in (5, 6):
        return

    active_users = _get_all_active_users()

    for user in active_users:
        user_name = frappe.db.get_value("User", user, "full_name") or user
        min_hours = _get_min_hours(user)

        # ── Check TODAY's hours (6 PM nudge) ──────────────────────────────
        today_hours = _get_hours_logged(user, today_date)

        if today_hours < min_hours:
            already_nudged = frappe.db.exists("Notification Log OC", {
                "user": user,
                "event_type": "Timesheet Nudge",
                "creation": [">=", today_date],
            })
            if not already_nudged:
                send_direct(
                    recipients=[user],
                    subject="Timesheet Reminder: {0}/{1} hours logged".format(
                        flt(today_hours, 1), flt(min_hours, 1)
                    ),
                    message=(
                        "Hi {0},<br><br>"
                        "You have logged <b>{1} hours</b> today "
                        "(minimum: {2} hours).<br>"
                        "Please complete your timesheet before end of day.<br><br>"
                        "<i>— SLV Automation</i>"
                    ).format(user_name, flt(today_hours, 1), flt(min_hours, 1)),
                    channel="All",
                    event_type="Timesheet Nudge",
                )

        # ── Check YESTERDAY's hours (morning follow-up) ──────────────────
        yesterday_dt = getdate(yesterday)
        if yesterday_dt.weekday() not in (5, 6):
            yesterday_hours = _get_hours_logged(user, yesterday)

            if yesterday_hours < min_hours:
                already_followed_up = frappe.db.exists("Notification Log OC", {
                    "user": user,
                    "event_type": "Timesheet Morning Follow-Up",
                    "creation": [">=", today_date],
                })
                if not already_followed_up:
                    send_direct(
                        recipients=[user],
                        subject="Yesterday's timesheet incomplete ({0}/{1}h)".format(
                            flt(yesterday_hours, 1), flt(min_hours, 1)
                        ),
                        message=(
                            "Hi {0},<br><br>"
                            "Your timesheet for <b>{1}</b> is still incomplete "
                            "({2}/{3} hours).<br>"
                            "Please fill it before 11 AM today.<br><br>"
                            "<i>— SLV Automation</i>"
                        ).format(user_name, yesterday, flt(yesterday_hours, 1), flt(min_hours, 1)),
                        channel="All",
                        event_type="Timesheet Morning Follow-Up",
                    )

        # ── Check consecutive missing days for escalation ─────────────────
        consecutive_missing = _count_consecutive_missing_days(user, min_hours)

        if consecutive_missing >= 2:
            already_escalated = frappe.db.exists("Notification Log OC", {
                "user": MANAGER_USER,
                "event_type": "Timesheet Escalation",
                "creation": [">=", today_date],
                "subject": ["like", "%{0}%".format(user_name)],
            })
            if not already_escalated:
                send_direct(
                    recipients=[MANAGER_USER],
                    subject="Timesheet Alert: {0} — {1} days missing".format(
                        user_name, consecutive_missing
                    ),
                    message=(
                        "<b>Timesheet Compliance Escalation</b><br><br>"
                        "<b>{0}</b> ({1}) has not filled timesheets "
                        "for <b>{2} consecutive working days</b>.<br><br>"
                        "Required: {3} hours/day<br>"
                        "Please follow up directly.<br><br>"
                        "<i>— SLV Automation</i>"
                    ).format(user_name, user, consecutive_missing, flt(min_hours, 1)),
                    channel="All",
                    event_type="Timesheet Escalation",
                )

    frappe.db.commit()


def _get_hours_logged(user, date):
    """
    Get total hours logged by a user on a specific date.
    Checks Timesheet Detail (time_logs child table) for accuracy.
    """
    result = frappe.db.sql(
        """
        SELECT COALESCE(SUM(td.hours), 0) as total_hours
        FROM `tabTimesheet Detail` td
        JOIN `tabTimesheet` ts ON td.parent = ts.name
        WHERE ts.owner = %s
          AND DATE(td.from_time) = %s
          AND ts.docstatus IN (0, 1)
        """,
        (user, date),
        as_dict=True,
    )

    if result:
        return flt(result[0].total_hours, 2)
    return 0.0


def _get_min_hours(user):
    """
    Get minimum required hours for a user.
    Checks Employee designation for part-time/intern hints.
    Falls back to default (6 hours).
    """
    try:
        employee = frappe.db.get_value(
            "Employee",
            {"user_id": user, "status": "Active"},
            ["designation"],
            as_dict=True,
        )

        if employee and employee.designation:
            desg = employee.designation.lower()
            if "part" in desg or "half" in desg:
                return 4.0
            if "intern" in desg:
                return 3.0
    except Exception:
        pass

    return DEFAULT_MIN_HOURS


def _count_consecutive_missing_days(user, min_hours):
    """
    Count how many consecutive working days (backwards from today)
    the user has failed to meet minimum hours.
    """
    count = 0
    check_date = add_days(today(), -1)

    for _ in range(7):
        dt = getdate(check_date)
        if dt.weekday() in (5, 6):
            check_date = add_days(check_date, -1)
            continue

        hours = _get_hours_logged(user, check_date)
        if hours < min_hours:
            count = count + 1
        else:
            break

        check_date = add_days(check_date, -1)

    return count


# ── Weekly Compliance Report (called from weekly digest) ──────────────────────

def get_weekly_compliance_report():
    """
    Generate weekly timesheet compliance data for the manager digest.
    Returns a dict with per-user compliance stats for the past week.
    """
    week_start = add_days(today(), -7)
    active_users = _get_all_active_users()
    report = []

    for user in active_users:
        user_name = frappe.db.get_value("User", user, "full_name") or user
        min_hours = _get_min_hours(user)

        working_days = 0
        compliant_days = 0
        total_hours = 0.0

        check_date = week_start
        for _ in range(7):
            dt = getdate(check_date)
            if dt.weekday() not in (5, 6):
                working_days = working_days + 1
                day_hours = _get_hours_logged(user, check_date)
                total_hours = total_hours + day_hours
                if day_hours >= min_hours:
                    compliant_days = compliant_days + 1
            check_date = add_days(check_date, 1)

        expected_hours = working_days * min_hours
        compliance_pct = (compliant_days / working_days * 100) if working_days > 0 else 0

        report.append({
            "user": user,
            "user_name": user_name,
            "working_days": working_days,
            "compliant_days": compliant_days,
            "total_hours": flt(total_hours, 1),
            "expected_hours": flt(expected_hours, 1),
            "compliance_pct": flt(compliance_pct, 0),
        })

    return sorted(report, key=lambda x: x["compliance_pct"])


# ── Helpers ───────────────────────────────────────────────────────────────────

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
def trigger_compliance_check():
    """Manually trigger compliance check for testing. System Manager only."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw("Only System Manager can trigger this")
    _run_compliance_check()
    frappe.db.commit()
    return {"status": "ok", "message": "Timesheet compliance check triggered"}
