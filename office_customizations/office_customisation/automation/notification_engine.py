"""
SLV Notification Engine
=======================
Central notification dispatch module for Seven Labs Vision office automation.

Supports two channels:
  1. ERPNext (in-app bell notification + email)
  2. Telegram (via separate notification bot)

Every notification is logged to the Notification Log OC DocType for audit trail.

Usage:
    from office_customizations.office_customisation.automation.notification_engine import (
        send_notification,
        send_direct,
    )

    # Using a template (preferred for automated jobs)
    send_notification(
        recipients=["user@example.com"],
        template_name="Task Overdue Reminder",
        context={"task_name": "GST Filing", "due_date": "2026-03-15", "days_overdue": 5},
        reference_doctype="Task",
        reference_name="TASK-00123",
    )

    # Direct message (no template, for one-off use)
    send_direct(
        recipients=["user@example.com"],
        subject="Quick Note",
        message="Please check the Quintrans reconciliation.",
        channel="ERPNext",
    )
"""

import frappe
from frappe.utils import now_datetime, get_datetime, get_time, cstr
from datetime import datetime, time as dt_time
import json
import requests


# ── Public API ────────────────────────────────────────────────────────────────


def send_notification(
	recipients,
	template_name,
	context=None,
	reference_doctype=None,
	reference_name=None,
	force_channel=None,
):
	"""
	Send a notification using a Notification Template.

	Args:
	    recipients: str or list of user emails
	    template_name: name of Notification Template record
	    context: dict of Jinja2 variables for rendering
	    reference_doctype: optional DocType reference
	    reference_name: optional document name reference
	    force_channel: override template/preference channel ("ERPNext" or "Telegram")
	"""
	settings = _get_settings()
	if not settings.enabled:
		return

	if isinstance(recipients, str):
		recipients = [recipients]

	context = context or {}
	context["site_url"] = frappe.utils.get_url()
	context["date"] = now_datetime().strftime("%d-%m-%Y")

	# Load template
	try:
		template = frappe.get_doc("Notification Template", template_name)
	except frappe.DoesNotExistError:
		frappe.log_error(
			f"Notification Template '{template_name}' not found",
			"SLV Notification Engine",
		)
		return

	if not template.enabled:
		return

	# Render subject and message
	subject = _render_template(template.subject, context)
	message = _render_template(template.message, context)

	channel = force_channel or template.channel

	for user in recipients:
		_dispatch_to_user(
			user=user,
			subject=subject,
			message=message,
			channel=channel,
			template_name=template_name,
			event_type=template.event_type,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			settings=settings,
		)


def send_direct(
	recipients,
	subject,
	message,
	channel="All",
	reference_doctype=None,
	reference_name=None,
	event_type="Custom",
):
	"""
	Send a notification directly without a template.

	Args:
	    recipients: str or list of user emails
	    subject: notification subject
	    message: notification body
	    channel: "ERPNext", "Telegram", or "All"
	    reference_doctype: optional DocType reference
	    reference_name: optional document name reference
	    event_type: event type for logging
	"""
	settings = _get_settings()
	if not settings.enabled:
		return

	if isinstance(recipients, str):
		recipients = [recipients]

	for user in recipients:
		_dispatch_to_user(
			user=user,
			subject=subject,
			message=message,
			channel=channel,
			template_name=None,
			event_type=event_type,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			settings=settings,
		)


def send_bulk_digest(
	recipients,
	subject,
	items,
	header_template="",
	item_template="",
	footer_template="",
	context=None,
	reference_doctype=None,
	event_type="Weekly Manager Digest",
):
	"""
	Send a digest-style notification with multiple items grouped together.
	Avoids spamming users with individual notifications.

	Args:
	    recipients: list of user emails
	    subject: digest subject
	    items: list of dicts, each rendered through item_template
	    header_template: Jinja2 string for the top of the message
	    item_template: Jinja2 string rendered for each item
	    footer_template: Jinja2 string for the bottom
	    context: shared context dict
	    reference_doctype: optional DocType reference
	    event_type: event type for logging
	"""
	settings = _get_settings()
	if not settings.enabled:
		return

	context = context or {}
	context["site_url"] = frappe.utils.get_url()
	context["date"] = now_datetime().strftime("%d-%m-%Y")
	context["item_count"] = len(items)

	# Render header
	parts = []
	if header_template:
		parts.append(_render_template(header_template, context))

	# Render each item
	for item in items:
		item_context = {**context, **item}
		parts.append(_render_template(item_template, item_context))

	# Render footer
	if footer_template:
		context["item_count"] = len(items)
		parts.append(_render_template(footer_template, context))

	message = "\n".join(parts)

	if isinstance(recipients, str):
		recipients = [recipients]

	for user in recipients:
		_dispatch_to_user(
			user=user,
			subject=subject,
			message=message,
			channel="All",
			template_name=None,
			event_type=event_type,
			reference_doctype=reference_doctype,
			reference_name=None,
			settings=settings,
		)


# ── Internal Dispatch Logic ───────────────────────────────────────────────────


def _dispatch_to_user(
	user,
	subject,
	message,
	channel,
	template_name,
	event_type,
	reference_doctype,
	reference_name,
	settings,
):
	"""Route a notification to the right channel(s) for a specific user."""
	pref = _get_user_preference(user)

	# Determine which channels to use
	channels_to_send = _resolve_channels(channel, pref, settings)

	for ch in channels_to_send:
		# Check quiet hours for Telegram
		if ch == "Telegram" and _is_quiet_hours(pref, settings):
			_log_notification(
				user=user,
				channel=ch,
				template_name=template_name,
				event_type=event_type,
				subject=subject,
				message=message,
				status="Skipped",
				error_message="Quiet hours - notification suppressed",
				reference_doctype=reference_doctype,
				reference_name=reference_name,
			)
			# Fall back to ERPNext during quiet hours
			if "ERPNext" not in channels_to_send:
				_send_erpnext(user, subject, message, reference_doctype, reference_name)
				_log_notification(
					user=user,
					channel="ERPNext",
					template_name=template_name,
					event_type=event_type,
					subject=subject,
					message=message,
					status="Sent",
					error_message=None,
					reference_doctype=reference_doctype,
					reference_name=reference_name,
				)
			continue

		# Dispatch
		success = False
		error = None

		try:
			if ch == "ERPNext":
				_send_erpnext(user, subject, message, reference_doctype, reference_name)
				success = True
			elif ch == "Telegram":
				chat_id = pref.telegram_chat_id if pref else None
				if chat_id:
					_send_telegram(chat_id, subject, message, settings)
					success = True
				else:
					error = "No Telegram chat ID configured"
					# Fall back to ERPNext
					_send_erpnext(user, subject, message, reference_doctype, reference_name)
					_log_notification(
						user=user,
						channel="ERPNext",
						template_name=template_name,
						event_type=event_type,
						subject=subject,
						message=message,
						status="Sent",
						error_message="Fallback from Telegram (no chat ID)",
						reference_doctype=reference_doctype,
						reference_name=reference_name,
					)
		except Exception as e:
			error = cstr(e)
			frappe.log_error(
				f"Notification failed for {user} via {ch}: {error}",
				"SLV Notification Engine",
			)

		_log_notification(
			user=user,
			channel=ch,
			template_name=template_name,
			event_type=event_type,
			subject=subject,
			message=message,
			status="Sent" if success else "Failed",
			error_message=error,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
		)


def _resolve_channels(requested_channel, pref, settings):
	"""
	Determine which channel(s) to actually use.

	Logic:
	- "ERPNext" or "Telegram" → use that specific channel
	- "All" → respect user preference, or fall back to default
	"""
	if requested_channel in ("ERPNext", "Telegram"):
		return [requested_channel]

	# "All" — check user preference
	if pref and pref.enabled:
		user_channel = pref.primary_channel
		if user_channel == "All":
			return ["ERPNext", "Telegram"]
		return [user_channel]

	# No preference set — use global default
	default = settings.default_channel
	if default == "All":
		return ["ERPNext", "Telegram"]
	return [default]


# ── Channel Adapters ──────────────────────────────────────────────────────────


def _send_erpnext(user, subject, message, reference_doctype=None, reference_name=None):
	"""Send via ERPNext's built-in notification system (bell icon + email)."""
	notification = frappe.new_doc("Notification Log")
	notification.for_user = user
	notification.from_user = "Administrator"
	notification.subject = subject
	notification.type = "Alert"

	if reference_doctype and reference_name:
		notification.document_type = reference_doctype
		notification.document_name = reference_name

	notification.email_content = message
	notification.insert(ignore_permissions=True)

	# Also send email (Frappe handles this if user has email notifications enabled)
	try:
		frappe.sendmail(
			recipients=[user],
			subject=f"[SLV] {subject}",
			message=message,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			now=True,
		)
	except Exception:
		# Email failure shouldn't block the notification
		pass


def _send_telegram(chat_id, subject, message, settings):
	"""Send via Telegram Bot API."""
	if not settings.telegram_enabled:
		raise Exception("Telegram notifications are disabled in settings")

	token = settings.get_password("telegram_bot_token")
	if not token:
		raise Exception("Telegram bot token not configured")

	# Format for Telegram (supports basic HTML)
	text = f"<b>{subject}</b>\n\n{message}"

	# Truncate if too long (Telegram limit: 4096 chars)
	if len(text) > 4000:
		text = text[:3997] + "..."

	url = f"https://api.telegram.org/bot{token}/sendMessage"
	payload = {
		"chat_id": chat_id,
		"text": text,
		"parse_mode": "HTML",
		"disable_web_page_preview": True,
	}

	resp = requests.post(url, json=payload, timeout=10)
	if resp.status_code != 200:
		error_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
		raise Exception(f"Telegram API error ({resp.status_code}): {error_data}")


# ── Helper Functions ──────────────────────────────────────────────────────────


def _get_settings():
	"""Get the SLV Notification Settings singleton. Creates with defaults if missing."""
	try:
		return frappe.get_single("SLV Notification Settings")
	except Exception:
		# First-time setup: return a mock with defaults
		return frappe._dict(
			enabled=True,
			default_channel="ERPNext",
			telegram_enabled=False,
			quiet_hours_enabled=True,
			quiet_hours_start="21:00:00",
			quiet_hours_end="09:00:00",
			escalation_enabled=True,
			level_1_delay_hours=24,
			level_2_delay_hours=48,
			final_escalation_user=None,
		)


def _get_user_preference(user):
	"""Get Notification Preference for a user. Returns None if not configured."""
	try:
		return frappe.get_doc("Notification Preference", user)
	except frappe.DoesNotExistError:
		return None


def _is_quiet_hours(pref, settings):
	"""Check if current time falls within quiet hours (for Telegram suppression)."""
	if not settings.quiet_hours_enabled:
		return False

	# Use user override if set, otherwise global
	if pref and pref.override_quiet_hours:
		start = pref.quiet_hours_start
		end = pref.quiet_hours_end
	else:
		start = settings.quiet_hours_start
		end = settings.quiet_hours_end

	if not start or not end:
		return False

	now = now_datetime().time()

	# Parse time fields (they come as strings like "21:00:00")
	if isinstance(start, str):
		start = datetime.strptime(start, "%H:%M:%S").time()
	if isinstance(end, str):
		end = datetime.strptime(end, "%H:%M:%S").time()

	# Handle overnight quiet hours (e.g., 21:00 to 09:00)
	if start > end:
		return now >= start or now <= end
	else:
		return start <= now <= end


def _render_template(template_str, context):
	"""Render a Jinja2 template string with the given context."""
	if not template_str:
		return ""
	try:
		return frappe.render_template(template_str, context)
	except Exception as e:
		frappe.log_error(
			f"Template render error: {e}\nTemplate: {template_str[:200]}",
			"SLV Notification Engine",
		)
		return template_str  # Return raw template as fallback


def _log_notification(
	user,
	channel,
	template_name,
	event_type,
	subject,
	message,
	status,
	error_message,
	reference_doctype,
	reference_name,
):
	"""Create an audit log entry in Notification Log OC."""
	try:
		log = frappe.new_doc("Notification Log OC")
		log.user = user
		log.channel = channel
		log.template = template_name
		log.event_type = event_type or ""
		log.subject = subject
		log.message = message[:2000] if message else ""  # Truncate long messages
		log.status = status
		log.error_message = error_message
		log.sent_at = now_datetime()
		log.reference_doctype = reference_doctype
		log.reference_name = reference_name
		log.insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception as e:
		# Logging failure should never break the notification flow
		frappe.log_error(
			f"Failed to log notification: {e}",
			"SLV Notification Engine - Log Error",
		)


# ── Whitelisted API (callable from Client Scripts or Telegram bot) ────────────


@frappe.whitelist()
def test_notification(user=None, channel="ERPNext"):
	"""
	Test the notification engine by sending a test message.
	Callable from ERPNext console: frappe.call('office_customizations.office_customisation.automation.notification_engine.test_notification')
	"""
	user = user or frappe.session.user
	send_direct(
		recipients=[user],
		subject="Test Notification from SLV Automation",
		message="If you're seeing this, the SLV Notification Engine is working correctly. This is a test message.",
		channel=channel,
		event_type="Custom",
	)
	return {"status": "ok", "message": f"Test notification sent to {user} via {channel}"}


@frappe.whitelist()
def get_notification_stats(days=7):
	"""
	Get notification statistics for the last N days.
	Useful for monitoring dashboard.
	"""
	from_date = frappe.utils.add_days(frappe.utils.today(), -int(days))

	stats = frappe.db.sql(
		"""
		SELECT
			channel,
			status,
			COUNT(*) as count
		FROM `tabNotification Log OC`
		WHERE DATE(sent_at) >= %s
		GROUP BY channel, status
		ORDER BY channel, status
		""",
		(from_date,),
		as_dict=True,
	)

	return stats
