"""
Rebuild fixtures/web_page.json from live data using bench's own export.
"""

import frappe


def run():
    pages = ["master-task-board", "my-tasks", "team-dashboard"]
    out = []
    for name in pages:
        if not frappe.db.exists("Web Page", name):
            print(f"  - {name}: not in DB, skipping")
            continue
        d = frappe.get_doc("Web Page", name).as_dict()
        # Strip volatile/non-portable fields
        for k in ["modified", "creation", "owner", "modified_by", "_user_tags",
                  "_comments", "_assign", "_liked_by", "idx"]:
            d.pop(k, None)
        out.append(d)
        print(f"  + {name}: {len(d.get('javascript') or '')} chars JS")

    import json
    path = "/home/frappe/frappe-bench/apps/office_customizations/office_customizations/fixtures/web_page.json"

    def default(o):
        # convert datetimes etc. to strings
        try:
            return str(o)
        except Exception:
            return None

    with open(path, "w") as f:
        json.dump(out, f, indent=1, default=default)
    print(f"\nFixture rewritten: {path}")
