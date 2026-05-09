"""
Patch my-tasks page so the Employee permission failure doesn't break rendering
for non-admin users. We replace the frappe.xcall(...) for Employee with a
direct frappe.call that suppresses the global error message and resolves
gracefully when the user has no Employee record / no permission.

Idempotent.
"""

import frappe


def run():
    doc = frappe.get_doc("Web Page", "my-tasks")
    js = doc.javascript

    old = (
        'frappe.xcall("frappe.client.get_value", {\n'
        '                doctype: "Employee",\n'
        '                filters: { user_id: frappe.session.user, status: "Active" },\n'
        '                fieldname: ["name", "employee_name", "company"]\n'
        '            }).then(function (r) {\n'
        '                if (r && r.name) employeeInfo = r;\n'
        '            }).catch(function () {})'
    )

    new = (
        'new Promise(function (resolve) {\n'
        '                frappe.call({\n'
        '                    method: "frappe.client.get_value",\n'
        '                    type: "POST",\n'
        '                    args: {\n'
        '                        doctype: "Employee",\n'
        '                        filters: { user_id: frappe.session.user, status: "Active" },\n'
        '                        fieldname: ["name", "employee_name", "company"]\n'
        '                    },\n'
        '                    callback: function (r) {\n'
        '                        if (r && r.message && r.message.name) employeeInfo = r.message;\n'
        '                        resolve();\n'
        '                    },\n'
        '                    error: function () { resolve(); },\n'
        '                    freeze: false\n'
        '                });\n'
        '            })'
    )

    if old in js:
        js = js.replace(old, new)
        doc.javascript = js
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        print("my-tasks page patched: Employee xcall replaced with safe frappe.call")
    elif new in js:
        print("my-tasks page already patched")
    else:
        frappe.throw("Anchor not found — my-tasks JS may have drifted")
