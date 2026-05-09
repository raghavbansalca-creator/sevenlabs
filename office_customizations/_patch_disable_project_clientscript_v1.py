"""
Disable the duplicate "Project" Client Script.

The same logic (project task board UI) is loaded via doctype_js hook from
public/js/project_task_board.js. The Client Script is an older copy that
overrides the JS file and contains the pre-mandatory-fields version of
add_new_task. Disable it so the JS file's version takes effect.

Also updates the fixture so re-imports don't re-enable.

Idempotent.
"""

import frappe
import json
import os


def run():
    # 1. Disable the live Client Script
    if frappe.db.exists("Client Script", "Project"):
        cs = frappe.get_doc("Client Script", "Project")
        if cs.enabled:
            cs.enabled = 0
            cs.save(ignore_permissions=True)
            print("  Live Client Script 'Project' disabled")
        else:
            print("  Live Client Script 'Project' already disabled")
    else:
        print("  No live 'Project' Client Script — nothing to disable")

    # 2. Update the fixture so re-imports don't re-enable
    fixture_path = "/home/frappe/frappe-bench/apps/office_customizations/office_customizations/fixtures/client_script.json"
    if os.path.exists(fixture_path):
        with open(fixture_path) as f:
            data = json.load(f)
        for e in data:
            if e.get("name") == "Project" and e.get("dt") == "Project":
                e["enabled"] = 0
        with open(fixture_path, "w") as f:
            json.dump(data, f, indent=1)
        print("  Fixture updated: Project Client Script enabled=0")

    frappe.db.commit()
    frappe.clear_cache()
