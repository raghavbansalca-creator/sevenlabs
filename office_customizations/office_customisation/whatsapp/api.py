import frappe
import re
import hashlib
from frappe import _
from datetime import datetime


# ─── Inbound: called by the webhook server on every incoming message ──────────

@frappe.whitelist()
def receive_message(phone, contact_name, msg_type, content, wa_timestamp, wa_message_id, raw_payload=None):
	"""
	Entry point called by the Node.js webhook server for every inbound WhatsApp message.
	1. Looks up Contact by phone number
	2. Creates WhatsApp Message doc
	3. If no Contact found → creates Lead (if enabled)
	4. Logs Communication against Contact / Lead / Customer (if enabled)
	"""
	settings = frappe.get_single("WhatsApp Settings")
	if not settings.enabled:
		return {"status": "disabled"}

	# Deduplicate: skip if we already have this message
	if frappe.db.exists("WhatsApp Message", {"wa_message_id": wa_message_id}):
		return {"status": "duplicate", "wa_message_id": wa_message_id}

	# Resolve ERPNext entities from phone number
	contact = _find_contact(phone)
	lead = None
	customer = None
	project = _find_project_for_phone(phone)

	if contact:
		customer = _find_customer_for_contact(contact)
	elif settings.auto_create_lead:
		lead = _create_lead(phone, contact_name)

	# Convert Unix timestamp to Frappe datetime string
	wa_dt = datetime.fromtimestamp(int(wa_timestamp)).strftime("%Y-%m-%d %H:%M:%S")

	# Create the WhatsApp Message record
	msg_doc = frappe.get_doc({
		"doctype": "WhatsApp Message",
		"direction": "Inbound",
		"phone_number": phone,
		"contact_name": contact_name,
		"wa_message_id": wa_message_id,
		"wa_timestamp": wa_dt,
		"status": "Received",
		"message_type": msg_type,
		"message_text": content,
		"erp_contact": contact,
		"erp_lead": lead,
		"erp_customer": customer,
		"erp_project": project,
		"raw_payload": raw_payload,
	})
	msg_doc.insert(ignore_permissions=True)

	# Log Communication
	if settings.auto_log_communication:
		_log_communication(
			contact=contact,
			lead=lead,
			customer=customer,
			sender_name=contact_name,
			content=content,
			comm_date=wa_dt,
			direction="Received",
		)

	frappe.db.commit()

	return {
		"status": "ok",
		"wa_message": msg_doc.name,
		"contact": contact,
		"lead": lead,
		"customer": customer,
		"project": project,
	}


# ─── Outbound: called from ERPNext UI buttons ─────────────────────────────────

@frappe.whitelist()
def send_message(phone, message, doc_type=None, doc_name=None, project=None):
	"""
	Send a WhatsApp text message via Meta Cloud API.
	Logs the outbound message as a WhatsApp Message doc and (optionally) a Communication.
	"""
	import requests

	settings = frappe.get_single("WhatsApp Settings")
	if not settings.enabled:
		frappe.throw(_("WhatsApp integration is not enabled. Go to WhatsApp Settings to activate it."))

	phone_number_id = settings.meta_phone_number_id
	access_token = settings.get_password("meta_access_token")

	if not phone_number_id or not access_token:
		frappe.throw(_("Meta Phone Number ID and Access Token must be configured in WhatsApp Settings."))

	# Send via Meta API
	url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
	response = requests.post(
		url,
		headers={
			"Authorization": f"Bearer {access_token}",
			"Content-Type": "application/json",
		},
		json={
			"messaging_product": "whatsapp",
			"to": phone,
			"type": "text",
			"text": {"body": message},
		},
		timeout=10,
	)

	result = response.json()
	if response.status_code != 200:
		frappe.throw(_(f"Meta API error: {result.get('error', {}).get('message', str(result))}"))

	wa_message_id = result.get("messages", [{}])[0].get("id", "")

	# Create outbound WhatsApp Message doc
	msg_doc = frappe.get_doc({
		"doctype": "WhatsApp Message",
		"direction": "Outbound",
		"phone_number": phone,
		"wa_message_id": wa_message_id,
		"wa_timestamp": frappe.utils.now_datetime(),
		"status": "Sent",
		"message_type": "text",
		"message_text": message,
		"erp_project": project or None,
	})
	msg_doc.insert(ignore_permissions=True)

	# Log Communication against the source doc if provided
	if doc_type and doc_name:
		_log_communication(
			contact=doc_name if doc_type == "Contact" else None,
			lead=doc_name if doc_type == "Lead" else None,
			customer=doc_name if doc_type == "Customer" else None,
			sender_name=frappe.session.user,
			content=message,
			comm_date=frappe.utils.now_datetime(),
			direction="Sent",
		)

	frappe.db.commit()

	return {"status": "ok", "wa_message_id": wa_message_id, "wa_message": msg_doc.name}


# ─── Status update: delivery receipts from webhook ────────────────────────────

@frappe.whitelist()
def update_status(wa_message_id, status):
	"""Update delivery status of an outbound message (delivered/read/failed)."""
	name = frappe.db.get_value("WhatsApp Message", {"wa_message_id": wa_message_id}, "name")
	if name:
		frappe.db.set_value("WhatsApp Message", name, "status", status.capitalize())
		frappe.db.commit()
	return {"status": "ok"}


# ─── Internal helpers ─────────────────────────────────────────────────────────

# ─── Option 1: WhatsApp Export Chat Parser ───────────────────────────────────

@frappe.whitelist()
def import_chat_export(project, chat_text, group_name="", my_name="Raghav"):
	"""
	Parse a WhatsApp exported chat .txt and bulk-create WhatsApp Message docs.

	Supports:
	  Android/India: "DD/MM/YYYY, HH:MM - Name: Message"
	  iOS:           "[DD/MM/YYYY, HH:MM:SS] Name: Message"

	Args:
	    project:    ERPNext Project name to link messages to
	    chat_text:  Raw content of the WhatsApp exported .txt file
	    group_name: Display name of the group (used as chat_source)
	    my_name:    Your WhatsApp display name — messages from this name become Outbound

	Returns:
	    dict with counts: imported, skipped_system, skipped_duplicate, errors
	"""
	# Regex patterns for both export formats
	ANDROID = re.compile(
		r'^(\d{1,2}/\d{1,2}/\d{4}),\s(\d{1,2}:\d{2})\s[-\u2013]\s(.+?):\s(.+)$'
	)
	IOS = re.compile(
		r'^\[(\d{1,2}/\d{1,2}/\d{4}),\s(\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AP]M)?)\]\s(.+?):\s(.+)$'
	)

	# System messages to skip (not real chat messages)
	SKIP_PATTERNS = [
		'Messages and calls are end-to-end encrypted',
		'created group', 'added you', 'added ', ' left',
		'changed the group', 'joined using this group', 'invite link',
		'changed their phone number', 'changed the subject',
		'This message was deleted', 'You deleted this message',
		'changed this group', 'security code changed',
		'pinned a message', 'removed', 'is now an admin',
	]

	stats = {"imported": 0, "skipped_system": 0, "skipped_duplicate": 0, "errors": 0}
	lines = chat_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')

	parsed = []          # list of (date_str, time_str, sender, message)
	current = None       # accumulates multi-line messages

	for line in lines:
		line = line.strip()
		if not line:
			continue

		m = ANDROID.match(line) or IOS.match(line)
		if m:
			# Save previous buffered message
			if current:
				parsed.append(current)
			current = (m.group(1), m.group(2), m.group(3).strip(), m.group(4).strip())
		else:
			# Continuation of previous message (line wrap)
			if current:
				current = (current[0], current[1], current[2], current[3] + '\n' + line)
			# else: orphan line before first message (header, etc.) — ignore

	if current:
		parsed.append(current)

	for date_str, time_str, sender, message in parsed:
		# Skip system messages
		if any(p.lower() in message.lower() or p.lower() in sender.lower() for p in SKIP_PATTERNS):
			stats["skipped_system"] += 1
			continue

		# Convert date + time to Frappe datetime
		try:
			time_clean = time_str.strip().replace('\u202f', ' ')
			# Try multiple formats
			wa_dt = None
			for fmt in ('%d/%m/%Y %H:%M', '%m/%d/%Y %H:%M', '%d/%m/%Y %I:%M %p',
						'%d/%m/%Y %H:%M:%S', '%m/%d/%Y %H:%M:%S'):
				try:
					wa_dt = datetime.strptime(f"{date_str} {time_clean}", fmt)
					break
				except ValueError:
					continue
			if not wa_dt:
				stats["errors"] += 1
				continue
		except Exception:
			stats["errors"] += 1
			continue

		wa_dt_str = wa_dt.strftime('%Y-%m-%d %H:%M:%S')

		# Determine direction
		is_mine = sender.strip().lower() == my_name.strip().lower()
		direction = "Outbound" if is_mine else "Inbound"

		# Handle media placeholder
		content = message
		msg_type = "text"
		if message in ('<Media omitted>', '‎<Media omitted>'):
			content = '[Media]'
			msg_type = "other"
		elif message.startswith('audio omitted') or 'audio omitted' in message.lower():
			msg_type = "audio"
			content = '[Audio]'
		elif message.startswith('image omitted') or 'image omitted' in message.lower():
			msg_type = "image"
			content = '[Image]'
		elif message.startswith('video omitted') or 'video omitted' in message.lower():
			msg_type = "video"
			content = '[Video]'
		elif message.startswith('document omitted') or 'document omitted' in message.lower():
			msg_type = "document"
			content = '[Document]'

		# Synthetic unique ID for deduplication — hash of project+sender+timestamp+content
		uid_src = f"{project}|{sender}|{wa_dt_str}|{content[:80]}"
		synthetic_id = "EXPORT-" + hashlib.md5(uid_src.encode()).hexdigest()[:16]

		# Skip duplicate
		if frappe.db.exists("WhatsApp Message", {"wa_message_id": synthetic_id}):
			stats["skipped_duplicate"] += 1
			continue

		try:
			doc = frappe.get_doc({
				"doctype": "WhatsApp Message",
				"direction": direction,
				"phone_number": "export",       # no real phone for exported messages
				"contact_name": sender,
				"wa_message_id": synthetic_id,
				"wa_timestamp": wa_dt_str,
				"status": "Received" if direction == "Inbound" else "Sent",
				"message_type": msg_type,
				"message_text": content,
				"erp_project": project,
				"raw_payload": f'{{"source":"export","group":"{group_name}","sender":"{sender}"}}',
			})
			doc.insert(ignore_permissions=True)
			stats["imported"] += 1
		except Exception as e:
			frappe.log_error(f"WA import error: {e}", "WhatsApp Import")
			stats["errors"] += 1

	frappe.db.commit()
	return stats


def _find_project_for_phone(phone):
	"""Find project mapped to this phone via WhatsApp Project Mapping."""
	last10 = _normalize_phone(phone)
	if not last10:
		return None
	result = frappe.db.sql(
		"""
		SELECT project FROM `tabWhatsApp Project Mapping`
		WHERE RIGHT(REPLACE(REPLACE(REPLACE(phone_number, ' ', ''), '-', ''), '+', ''), 10) = %s
		LIMIT 1
		""",
		last10,
		as_dict=True,
	)
	return result[0].project if result else None


# ─── Project tab helpers ──────────────────────────────────────────────────────

@frappe.whitelist()
def get_project_messages(project, limit=100):
	"""Fetch all WhatsApp messages linked to a project, oldest first (for chat view)."""
	return frappe.get_all(
		"WhatsApp Message",
		filters={"erp_project": project},
		fields=[
			"name", "direction", "source", "phone_number", "contact_name",
			"message_type", "message_text", "wa_timestamp", "status", "media_file", "tg_chat_id",
		],
		order_by="wa_timestamp asc",
		limit=int(limit),
	)


@frappe.whitelist()
def get_project_mappings(project):
	"""Get phone numbers mapped to this project."""
	return frappe.get_all(
		"WhatsApp Project Mapping",
		filters={"project": project},
		fields=["name", "phone_number", "label"],
		order_by="creation asc",
	)


@frappe.whitelist()
def add_project_mapping(project, phone_number, label=""):
	"""Create a new WhatsApp Project Mapping entry."""
	doc = frappe.get_doc({
		"doctype": "WhatsApp Project Mapping",
		"project": project,
		"phone_number": phone_number,
		"label": label,
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok", "name": doc.name}


@frappe.whitelist()
def delete_project_mapping(name):
	"""Remove a phone number from a project's mapping."""
	frappe.delete_doc("WhatsApp Project Mapping", name, ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok"}


def _normalize_phone(phone):
	"""Strip all non-digit characters and return last 10 digits (Indian numbers)."""
	digits = "".join(c for c in phone if c.isdigit())
	return digits[-10:] if len(digits) >= 10 else digits


def _find_contact(phone):
	"""Find a Contact whose stored phone number matches the last 10 digits."""
	last10 = _normalize_phone(phone)
	if not last10:
		return None

	# Check Contact Phone child table
	result = frappe.db.sql(
		"""
		SELECT cp.parent
		FROM `tabContact Phone` cp
		WHERE RIGHT(REPLACE(REPLACE(REPLACE(cp.phone, ' ', ''), '-', ''), '+', ''), 10) = %s
		LIMIT 1
		""",
		last10,
		as_dict=True,
	)
	if result:
		return result[0].parent

	# Check direct mobile_no field on Contact
	result = frappe.db.sql(
		"""
		SELECT name FROM `tabContact`
		WHERE RIGHT(REPLACE(REPLACE(REPLACE(mobile_no, ' ', ''), '-', ''), '+', ''), 10) = %s
		LIMIT 1
		""",
		last10,
		as_dict=True,
	)
	return result[0].name if result else None


def _find_customer_for_contact(contact_name):
	"""Return the Customer linked to a Contact via Dynamic Link."""
	result = frappe.db.sql(
		"""
		SELECT dl.link_name
		FROM `tabDynamic Link` dl
		WHERE dl.parenttype = 'Contact'
		  AND dl.parent = %s
		  AND dl.link_doctype = 'Customer'
		LIMIT 1
		""",
		contact_name,
		as_dict=True,
	)
	return result[0].link_name if result else None


def _create_lead(phone, contact_name):
	"""Create a new Lead for an unknown WhatsApp number."""
	lead = frappe.get_doc({
		"doctype": "Lead",
		"lead_name": contact_name or f"WA {phone}",
		"mobile_no": phone,
		"source": "Other",
		"status": "Lead",
	})
	lead.insert(ignore_permissions=True)
	return lead.name


def _log_communication(contact, lead, customer, sender_name, content, comm_date, direction):
	"""Log a Communication doc against the best available ERPNext entity."""
	if customer:
		ref_doctype, ref_name = "Customer", customer
	elif contact:
		ref_doctype, ref_name = "Contact", contact
	elif lead:
		ref_doctype, ref_name = "Lead", lead
	else:
		return  # Nothing to link against

	subject_prefix = "WhatsApp from" if direction == "Received" else "WhatsApp to"
	comm = frappe.get_doc({
		"doctype": "Communication",
		"communication_type": "Communication",
		"communication_medium": "Phone",
		"sent_or_received": direction,
		"reference_doctype": ref_doctype,
		"reference_name": ref_name,
		"subject": f"{subject_prefix} {sender_name}",
		"content": content,
		"sender_full_name": sender_name,
		"communication_date": comm_date,
	})
	comm.insert(ignore_permissions=True)


# ─── Media pipeline ───────────────────────────────────────────────────────────

@frappe.whitelist()
def attach_media_to_message(wa_message_id, filename, base64_content, mimetype=None):
	"""
	Called by the webhook server (Evolution API) after fetching base64 media.
	Decodes base64, saves as a Frappe File doc attached to the WA Message,
	and updates the media_file field on the doc.
	"""
	import base64 as b64

	try:
		content_bytes = b64.b64decode(base64_content)
	except Exception:
		return {"status": "decode_error"}

	file_url = _attach_file(wa_message_id, filename, content_bytes)
	if file_url:
		return {"status": "ok", "file_url": file_url}
	return {"status": "not_found"}


@frappe.whitelist()
def fetch_and_attach_meta_media(wa_message_id, media_id, filename, mimetype=None):
	"""
	Called by the webhook server for Meta Cloud API media messages.
	Downloads from Meta's temporary URL (using stored access token) and attaches.
	"""
	import requests

	settings = frappe.get_single("WhatsApp Settings")
	access_token = settings.get_password("meta_access_token")
	if not access_token:
		return {"status": "no_token"}

	# Step 1: Get the temporary download URL from Meta
	try:
		url_res = requests.get(
			f"https://graph.facebook.com/v19.0/{media_id}",
			headers={"Authorization": f"Bearer {access_token}"},
			timeout=10,
		)
		media_url = url_res.json().get("url")
		if not media_url:
			frappe.log_error(f"Meta media URL not found for id={media_id}: {url_res.text}", "WhatsApp Media")
			return {"status": "url_error"}
	except Exception as e:
		frappe.log_error(f"Meta media URL fetch error: {e}", "WhatsApp Media")
		return {"status": "url_error"}

	# Step 2: Download the actual file
	try:
		dl_res = requests.get(
			media_url,
			headers={"Authorization": f"Bearer {access_token}"},
			timeout=30,
		)
		if dl_res.status_code != 200:
			return {"status": "download_error", "http": dl_res.status_code}
	except Exception as e:
		frappe.log_error(f"Meta media download error: {e}", "WhatsApp Media")
		return {"status": "download_error"}

	file_url = _attach_file(wa_message_id, filename, dl_res.content)
	return {"status": "ok", "file_url": file_url} if file_url else {"status": "not_found"}


def _attach_file(wa_message_id, filename, content_bytes):
	"""
	Internal helper: save raw bytes as a Frappe File doc attached to a WhatsApp Message.
	Updates the media_file field and returns the file_url, or None on failure.
	"""
	from frappe.utils.file_manager import save_file

	name = frappe.db.get_value("WhatsApp Message", {"wa_message_id": wa_message_id}, "name")
	if not name:
		return None

	try:
		f = save_file(filename, content_bytes, "WhatsApp Message", name, is_private=False)
		frappe.db.set_value("WhatsApp Message", name, "media_file", f.file_url)
		frappe.db.commit()
		return f.file_url
	except Exception as e:
		frappe.log_error(f"WA media attach error for {wa_message_id}: {e}", "WhatsApp Media")
		return None


# ─── Telegram integration ─────────────────────────────────────────────────────

@frappe.whitelist()
def receive_telegram_message(sender_id, sender_name, msg_type, content,
                              timestamp, tg_message_id, tg_chat_id,
                              chat_title="", raw_payload=""):
	"""Process incoming Telegram message (individual or group)."""

	# Dedup check
	if frappe.db.exists("WhatsApp Message", {"wa_message_id": tg_message_id}):
		return {"status": "duplicate"}

	# Find project by Telegram chat ID
	project = frappe.db.get_value(
		"Telegram Group Mapping",
		{"tg_chat_id": str(tg_chat_id)},
		"project",
	)

	# Convert Unix timestamp
	try:
		wa_dt = datetime.fromtimestamp(int(timestamp))
	except Exception:
		wa_dt = frappe.utils.now_datetime()

	# Create message doc
	doc = frappe.get_doc({
		"doctype": "WhatsApp Message",
		"direction": "Inbound",
		"source": "Telegram",
		"phone_number": str(sender_id),
		"contact_name": sender_name,
		"message_type": msg_type,
		"message_text": content,
		"wa_message_id": tg_message_id,
		"wa_timestamp": wa_dt,
		"status": "Received",
		"tg_chat_id": str(tg_chat_id),
		"erp_project": project,
		"raw_payload": raw_payload,
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	return {
		"status": "ok",
		"wa_message": doc.name,
		"project": project,
	}


@frappe.whitelist()
def send_telegram_message(tg_chat_id, message, project=None):
	"""Send a text message to a Telegram group/chat via the Bot API."""
	import requests

	settings = frappe.get_single("WhatsApp Settings")
	if not settings.telegram_enabled:
		frappe.throw("Telegram integration is not enabled")

	token = settings.get_password("telegram_bot_token")
	if not token:
		frappe.throw("Telegram bot token not configured in WhatsApp Settings")

	res = requests.post(
		f"https://api.telegram.org/bot{token}/sendMessage",
		json={"chat_id": int(tg_chat_id), "text": message},
		timeout=10,
	)
	result = res.json()

	if not result.get("ok"):
		frappe.throw(f"Telegram send failed: {result.get('description', 'Unknown error')}")

	tg_msg = result["result"]
	tg_msg_id = f"TG-{tg_chat_id}-{tg_msg['message_id']}"

	# Log the outbound message
	doc = frappe.get_doc({
		"doctype": "WhatsApp Message",
		"direction": "Outbound",
		"source": "Telegram",
		"phone_number": "",
		"contact_name": "SLV Office",
		"message_type": "text",
		"message_text": message,
		"wa_message_id": tg_msg_id,
		"wa_timestamp": frappe.utils.now_datetime(),
		"status": "Sent",
		"tg_chat_id": str(tg_chat_id),
		"erp_project": project,
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	return {"status": "ok", "wa_message": doc.name}


@frappe.whitelist()
def send_telegram_media(tg_chat_id, file_url, media_type="document", caption="", project=None):
	"""Send a media file to a Telegram group/chat."""
	import requests

	settings = frappe.get_single("WhatsApp Settings")
	token = settings.get_password("telegram_bot_token")
	if not token:
		frappe.throw("Telegram bot token not configured")

	# Resolve file path to full URL or local file
	site_url = frappe.utils.get_url()
	full_url = f"{site_url}{file_url}" if file_url.startswith("/") else file_url

	method_map = {
		"image": "sendPhoto",
		"video": "sendVideo",
		"audio": "sendAudio",
		"document": "sendDocument",
	}
	method = method_map.get(media_type, "sendDocument")
	field = {"sendPhoto": "photo", "sendVideo": "video", "sendAudio": "audio", "sendDocument": "document"}.get(method, "document")

	payload = {"chat_id": int(tg_chat_id)}
	if caption:
		payload["caption"] = caption

	# Download the file from ERPNext and send to Telegram
	file_content = requests.get(full_url, timeout=15).content
	filename = file_url.split("/")[-1]

	res = requests.post(
		f"https://api.telegram.org/bot{token}/{method}",
		data=payload,
		files={field: (filename, file_content)},
		timeout=30,
	)
	result = res.json()

	if not result.get("ok"):
		frappe.throw(f"Telegram media send failed: {result.get('description', 'Unknown error')}")

	return {"status": "ok"}


@frappe.whitelist()
def get_telegram_groups(project=None):
	"""Get Telegram groups mapped to a project."""
	filters = {}
	if project:
		filters["project"] = project
	return frappe.get_all(
		"Telegram Group Mapping",
		filters=filters,
		fields=["name", "project", "tg_chat_id", "group_name"],
	)


@frappe.whitelist()
def add_telegram_group_mapping(project, tg_chat_id, group_name=""):
	"""Map a Telegram group to a project."""
	doc = frappe.get_doc({
		"doctype": "Telegram Group Mapping",
		"project": project,
		"tg_chat_id": str(tg_chat_id),
		"group_name": group_name,
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok", "name": doc.name}


@frappe.whitelist()
def delete_telegram_group_mapping(name):
	"""Remove a Telegram group mapping."""
	frappe.delete_doc("Telegram Group Mapping", name, ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok"}
