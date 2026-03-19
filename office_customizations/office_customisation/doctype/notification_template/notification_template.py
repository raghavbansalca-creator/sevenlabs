import frappe
from frappe.model.document import Document


class NotificationTemplate(Document):
	def validate(self):
		"""Validate Jinja2 syntax in subject and message."""
		from jinja2 import Environment, exceptions as jinja_exc

		env = Environment()
		for field in ("subject", "message"):
			template_str = self.get(field)
			if template_str:
				try:
					env.parse(template_str)
				except jinja_exc.TemplateSyntaxError as e:
					frappe.throw(
						f"Invalid Jinja2 syntax in {field}: {e.message} (line {e.lineno})",
						title="Template Syntax Error",
					)
