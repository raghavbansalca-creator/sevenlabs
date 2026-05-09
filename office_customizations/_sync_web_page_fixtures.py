"""
Pull live Web Page records back into fixtures/web_page.json so the patches
applied via _patch_mtb_v1, _patch_mytasks_addtask_v3, etc. survive bench migrate.

Run via:
  docker exec erpnext-slv-backend-1 bench --site frontend execute \
    office_customizations._sync_web_page_fixtures.run
"""

import frappe
import json
import os


FIXTURE_PATH = "/home/frappe/frappe-bench/apps/office_customizations/office_customizations/fixtures/web_page.json"
PAGES = ["master-task-board", "my-tasks", "team-dashboard"]


def run():
    if not os.path.exists(FIXTURE_PATH):
        print(f"Fixture not found: {FIXTURE_PATH}")
        return

    with open(FIXTURE_PATH) as f:
        fixture = json.load(f)

    by_name = {e.get("name"): e for e in fixture}

    updated = 0
    for page_name in PAGES:
        if not frappe.db.exists("Web Page", page_name):
            print(f"  - {page_name}: not in DB, skipping")
            continue
        live = frappe.get_doc("Web Page", page_name)
        if page_name not in by_name:
            print(f"  - {page_name}: not in fixture, skipping")
            continue

        fixture_entry = by_name[page_name]
        # Update the JS-related text fields only (skip datetime/non-string fields)
        for field in ("javascript", "main_section", "main_section_html", "context_script", "css"):
            live_val = live.get(field)
            if live_val is not None and fixture_entry.get(field) != live_val:
                fixture_entry[field] = live_val
                updated += 1
        print(f"  + {page_name}: synced (any field updates: {updated})")

    with open(FIXTURE_PATH, "w") as f:
        json.dump(fixture, f, indent=1)
    print(f"\nFixture file updated: {FIXTURE_PATH}")
    print("Now bench migrate won't revert your Web Page patches.")
