import frappe, json, os, sys

NAMES = ["my-tasks", "master-task-board", "tasks-mockup-v2"]

def run():
    out = []
    for name in NAMES:
        if not frappe.db.exists("Web Page", name):
            print("skip (not found):", name)
            continue
        d = frappe.get_doc("Web Page", name).as_dict()
        for k in ["modified", "creation", "owner", "modified_by", "_user_tags",
                  "_comments", "_assign", "_liked_by", "idx",
                  "modified_by", "docstatus"]:
            d.pop(k, None)
        out.append(d)
    path = "/home/frappe/frappe-bench/apps/office_customizations/office_customizations/fixtures/web_page.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("Wrote", len(out), "Web Page fixture entries to", path)
