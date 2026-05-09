"""
Make assignee optional in:
  - Master Task Board "+ Add Task" modals (3 places — flip required:true → required:false on assigned_to)
  - Master Task Board "+ Add Subtask" modal (1 place)
  - Standard Frappe Task form (delete the "Assignee Required" Client Script)

The server-side after_insert hook (task_events.after_insert) now auto-assigns
to the creator if no assignee was picked, so blocking the user is unnecessary.
End-date remains required.

Idempotent.
"""

import frappe


CLIENT_SCRIPT_NAME = "office_customizations: Task assignee required"


def run():
    # 1. Master Task Board JS — flip assigned_to required
    doc = frappe.get_doc("Web Page", "master-task-board")
    js = doc.javascript

    old_block = (
        "{name:'exp_end_date',type:'date',label:'End Date',required:true},\n"
        "{name:'assigned_to',type:'select',label:'Assigned To',options:empOpts,required:true}"
    )
    new_block = (
        "{name:'exp_end_date',type:'date',label:'End Date',required:true},\n"
        "{name:'assigned_to',type:'select',label:'Assigned To',options:empOpts}"
    )

    occurrences = js.count(old_block)
    if occurrences == 0 and js.count(new_block) >= 4:
        print("  MTB modals: already patched (assigned_to optional)")
    elif occurrences == 4:  # 3 add-task + 1 subtask
        js = js.replace(old_block, new_block)
        doc.javascript = js
        doc.save(ignore_permissions=True)
        print(f"  MTB modals: assigned_to flipped to optional in {occurrences} places")
    else:
        frappe.throw(
            f"Anchor expected 4x; got {occurrences}. Aborting to avoid corruption."
        )

    # 2. Delete the "Assignee Required" Client Script
    if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        frappe.delete_doc("Client Script", CLIENT_SCRIPT_NAME, force=True, ignore_permissions=True)
        print(f"  Client Script removed: {CLIENT_SCRIPT_NAME}")
    else:
        print(f"  Client Script already absent: {CLIENT_SCRIPT_NAME}")

    frappe.db.commit()
    frappe.clear_cache(doctype="Task")
    print("Done — reload your browser tab to pick up the changes.")
