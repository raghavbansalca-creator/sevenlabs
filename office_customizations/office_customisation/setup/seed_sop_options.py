"""
Seed the SOP Goal / Module / System lookup DocTypes with default options.

Idempotent — safe to run on every migrate. Adds anything missing, leaves
manually-added entries alone.

Wire-up: called from hooks.py `after_migrate` (so option lists are always fresh).
"""

from __future__ import annotations

import frappe


GOALS = [
    {
        "goal_id": "G-ERP",
        "label": "ERPNext Implementation",
        "description": "Map every transaction flow + master data + permission roles so we can plan an ERPNext rollout.",
    },
    {
        "goal_id": "G-COST",
        "label": "Cost Optimization",
        "description": "Identify cost components, wastage points, vendor concentration, working-capital cycle gaps.",
    },
    {
        "goal_id": "G-PROCESS",
        "label": "Process Improvement",
        "description": "Surface bottlenecks, automation candidates, role mismatches, single-person-knowledge risks.",
    },
]

MODULES = [
    ("01-Sales",        "Sales Model & Channels",      ""),
    ("02-Product",      "Product / Service Knowledge", ""),
    ("03-CRM",          "CRM & Lead Management",       ""),
    ("04-O2C",          "Order-to-Cash",               ""),
    ("05-Purchase",     "Purchase & Procurement",      ""),
    ("06-Production",   "Manufacturing / Production",  "Manufacturing, Construction"),
    ("07-Inventory",    "Inventory & Warehousing",     "Manufacturing, Construction, Trading, Retail"),
    ("08-Logistics",    "Supply Chain / Logistics",    "Manufacturing, Trading, Distribution, Retail, Construction"),
    ("09-HR-Payroll",   "HR & Payroll",                ""),
    ("10-Finance",      "Finance & Accounting",        ""),
    ("11-Business-Ops", "Business Operations",         ""),
    ("12-Compliance",   "Statutory & Compliance",      ""),
    ("13-Tech-Stack",   "Technology Stack",            ""),
    ("14-Controls",     "Controls & Approvals",        ""),
]

SYSTEMS = [
    ("Tally",                  "Accounting"),
    ("Tally Prime",            "Accounting"),
    ("Marg ERP",               "ERP"),
    ("Busy Accounting",        "Accounting"),
    ("ERPNext",                "ERP"),
    ("SAP Business One",       "ERP"),
    ("SAP S/4HANA",            "ERP"),
    ("Oracle NetSuite",        "ERP"),
    ("Zoho One",               "ERP"),
    ("Zoho Books",             "Accounting"),
    ("Zoho CRM",               "CRM"),
    ("HubSpot",                "CRM"),
    ("Salesforce",             "CRM"),
    ("LeadSquared",            "CRM"),
    ("Microsoft Excel",        "Spreadsheet"),
    ("Google Sheets",          "Spreadsheet"),
    ("WhatsApp",               "Messaging"),
    ("WhatsApp Business",      "Messaging"),
    ("Slack",                  "Messaging"),
    ("Microsoft Teams",        "Messaging"),
    ("Telegram",               "Messaging"),
    ("Manual registers",       "Manual / Paper"),
    ("Printed forms / slips",  "Manual / Paper"),
    ("Custom in-house tool",   "Custom"),
    ("None — verbal only",     "Other"),
]


def _ensure(doctype: str, name_field: str, name_value: str, fields: dict) -> bool:
    """Insert if not exists. Returns True if created."""
    if frappe.db.exists(doctype, name_value):
        return False
    doc = frappe.get_doc({"doctype": doctype, name_field: name_value, **fields})
    doc.insert(ignore_permissions=True)
    return True


def run() -> dict:
    created = {"goals": 0, "modules": 0, "systems": 0}
    for g in GOALS:
        if _ensure("SOP Goal Option", "goal_id", g["goal_id"], {"label": g["label"], "description": g["description"]}):
            created["goals"] += 1
    for code, name, typical in MODULES:
        if _ensure("SOP Module Option", "module_code", code, {"module_name": name, "typical_for": typical}):
            created["modules"] += 1
    for sys_name, cat in SYSTEMS:
        if _ensure("SOP System Option", "system_name", sys_name, {"category": cat}):
            created["systems"] += 1
    frappe.db.commit()
    print(f"SOP option seeding: {created}")
    return created


if __name__ == "__main__":
    run()
