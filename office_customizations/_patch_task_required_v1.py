"""
Server-side enforcement: every Task must have an end date and at least one assignee.

Two pieces:
  1. Property Setter — makes `exp_end_date` a required field on the Task form
     (covers /app/task/new and any form-driven path).
  2. Client Script — on `before_save`, blocks save if the doc has no assignee
     in __onload.assignments (covers the standard Frappe form too).

API-driven creates (e.g. the Telegram bot) bypass the Client Script. The bot
fix in Layer 3 enforces assignee at that layer.

Run via:
  docker exec erpnext-slv-backend-1 bench --site frontend execute \
    office_customizations._patch_task_required_v1.run

Idempotent.
"""

import frappe


END_DATE_PROP = "office_customizations: exp_end_date reqd"
CLIENT_SCRIPT_NAME = "office_customizations: Task assignee required"
CLIENT_SCRIPT_BODY = """frappe.ui.form.on('Task', {
    before_save: function(frm) {
        // Allow save if status is Cancelled or Template — no assignment needed
        if (frm.doc.status === 'Cancelled' || frm.doc.status === 'Template') return;

        var assignments = (frm.doc.__onload && frm.doc.__onload.assignments) || [];
        if (!assignments.length) {
            frappe.throw({
                title: __('Assignee Required'),
                message: __('Please assign this task to at least one user before saving. Use the "Assigned to" widget on the right sidebar.')
            });
        }
    }
});"""


def run():
    # ─── 1. Property Setter: make exp_end_date required ─────────────────
    existing_ps = frappe.db.get_value(
        "Property Setter",
        {"doc_type": "Task", "field_name": "exp_end_date", "property": "reqd"},
        "name",
    )
    if existing_ps:
        ps = frappe.get_doc("Property Setter", existing_ps)
        if str(ps.value) != "1":
            ps.value = "1"
            ps.save(ignore_permissions=True)
            print(f"  Property Setter updated: exp_end_date.reqd = 1")
        else:
            print(f"  Property Setter already set: exp_end_date.reqd = 1")
    else:
        ps = frappe.get_doc({
            "doctype": "Property Setter",
            "doctype_or_field": "DocField",
            "doc_type": "Task",
            "field_name": "exp_end_date",
            "property": "reqd",
            "property_type": "Check",
            "value": "1",
        })
        ps.flags.ignore_permissions = True
        ps.insert()
        print(f"  Property Setter created: exp_end_date.reqd = 1")

    # ─── 2. Client Script: block save if no assignee ────────────────────
    if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        cs = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
        if cs.script != CLIENT_SCRIPT_BODY or cs.dt != "Task" or cs.view != "Form" or not cs.enabled:
            cs.script = CLIENT_SCRIPT_BODY
            cs.dt = "Task"
            cs.view = "Form"
            cs.enabled = 1
            cs.save(ignore_permissions=True)
            print(f"  Client Script updated: {CLIENT_SCRIPT_NAME}")
        else:
            print(f"  Client Script already up to date: {CLIENT_SCRIPT_NAME}")
    else:
        cs = frappe.get_doc({
            "doctype": "Client Script",
            "name": CLIENT_SCRIPT_NAME,
            "dt": "Task",
            "view": "Form",
            "enabled": 1,
            "script": CLIENT_SCRIPT_BODY,
        })
        cs.flags.ignore_permissions = True
        cs.insert()
        print(f"  Client Script created: {CLIENT_SCRIPT_NAME}")

    frappe.db.commit()
    frappe.clear_cache(doctype="Task")
    print("Done — cache cleared. Reload your browser tab to pick up the new rules.")
