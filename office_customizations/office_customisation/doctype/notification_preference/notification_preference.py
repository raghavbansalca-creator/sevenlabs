import frappe
from frappe.model.document import Document


class NotificationPreference(Document):
	def validate(self):
		if self.primary_channel in ("Telegram", "All") and not self.telegram_chat_id:
			frappe.msgprint(
				f"Telegram chat ID is not set for {self.user_full_name}. "
				"Telegram notifications will fall back to ERPNext until chat ID is configured.",
				indicator="orange",
				alert=True,
			)
