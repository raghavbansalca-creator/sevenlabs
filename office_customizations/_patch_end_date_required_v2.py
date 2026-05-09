"""
Corrective patch — ensure End Date has required:true in MTB modals.
Earlier patch chain left it without required.
"""

import frappe


def run():
    doc = frappe.get_doc("Web Page", "master-task-board")
    js = doc.javascript

    old = "{name:'exp_end_date',type:'date',label:'End Date'},"
    new = "{name:'exp_end_date',type:'date',label:'End Date',required:true},"

    cnt = js.count(old)
    if cnt == 0 and js.count(new) >= 4:
        print("End Date already required in all places.")
        return
    js = js.replace(old, new)
    doc.javascript = js
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"Set required:true on End Date in {cnt} places.")
