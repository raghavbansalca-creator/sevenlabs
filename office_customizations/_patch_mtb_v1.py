"""
One-shot patch to enforce mandatory assignee + end-date in Master Task Board modals.

Run inside the container via:
  docker exec erpnext-slv-backend-1 bench --site frontend execute office_customizations._patch_mtb_v1.run

Idempotent — safe to run twice.
"""

import frappe


def run():
    doc = frappe.get_doc("Web Page", "master-task-board")
    js = doc.javascript
    original_len = len(js)

    # ─────────────────────────────────────────────────────────────────────
    # Edit 1: Mark `assigned_to` and `exp_end_date` required across the
    # three add-task modals (they share the exact same field-array snippet).
    # The pattern occurs 3x — one replace covers all three.
    # ─────────────────────────────────────────────────────────────────────
    old_field_block = (
        "{name:'exp_end_date',type:'date',label:'End Date'},\n"
        "{name:'assigned_to',type:'select',label:'Assigned To',options:empOpts}"
    )
    new_field_block = (
        "{name:'exp_end_date',type:'date',label:'End Date',required:true},\n"
        "{name:'assigned_to',type:'select',label:'Assigned To',options:empOpts,required:true}"
    )

    occurrences = js.count(old_field_block)
    already_patched = js.count(new_field_block)

    print(f"  add-task modals: pattern hits = {occurrences}, already patched = {already_patched}")

    if occurrences == 0 and already_patched >= 3:
        print("  add-task modals: already patched, skipping Edit 1")
    else:
        if occurrences != 3:
            frappe.throw(
                f"Edit 1 anchor expected 3x, got {occurrences}x. Aborting to avoid corruption."
            )
        js = js.replace(old_field_block, new_field_block)
        print("  add-task modals: patched 3 occurrences")

    # ─────────────────────────────────────────────────────────────────────
    # Edit 2: Extend `mtb_add_subtask` to also require assignee + end date.
    # Currently it only takes subject + priority.
    # ─────────────────────────────────────────────────────────────────────
    old_subtask = (
        "function mtb_add_subtask(parentTaskName,projectName){\n"
        "var priOpts=[{value:'Low',text:'Low'},{value:'Medium',text:'Medium'},{value:'High',text:'High'},{value:'Urgent',text:'Urgent'}];\n"
        "mtb_modal('Add Subtask',[\n"
        "{name:'subject',type:'text',label:'Subtask Name',required:true},\n"
        "{name:'priority',type:'select',label:'Priority',options:priOpts,default:'Medium'}\n"
        "],'Create Subtask',function(v){\n"
        "var parentTask=mtb_allTasks.find(function(t){return t.name===parentTaskName;});\n"
        "frappe.call({method:'frappe.client.set_value',args:{doctype:'Task',name:parentTaskName,fieldname:'is_group',value:1},callback:function(){\n"
        "frappe.call({method:'frappe.client.insert',args:{doc:{doctype:'Task',subject:v.subject,project:projectName,parent_task:parentTaskName,priority:v.priority,custom_task_list:parentTask?parentTask.custom_task_list:null,status:'Open'}},callback:function(r){if(!r.exc){frappe.show_alert({message:'Subtask created!',indicator:'green'});mtb_refresh();}}});\n"
        "}});\n"
        "});\n"
        "}"
    )

    new_subtask = (
        "function mtb_add_subtask(parentTaskName,projectName){\n"
        "var priOpts=[{value:'Low',text:'Low'},{value:'Medium',text:'Medium'},{value:'High',text:'High'},{value:'Urgent',text:'Urgent'}];\n"
        "var empOpts=mtb_allEmployees.filter(function(e){return e.full_name;}).map(function(e){return {value:e.name,text:e.full_name};});\n"
        "mtb_modal('Add Subtask',[\n"
        "{name:'subject',type:'text',label:'Subtask Name',required:true},\n"
        "{name:'priority',type:'select',label:'Priority',options:priOpts,default:'Medium'},\n"
        "{name:'exp_end_date',type:'date',label:'End Date',required:true},\n"
        "{name:'assigned_to',type:'select',label:'Assigned To',options:empOpts,required:true}\n"
        "],'Create Subtask',function(v){\n"
        "var parentTask=mtb_allTasks.find(function(t){return t.name===parentTaskName;});\n"
        "frappe.call({method:'frappe.client.set_value',args:{doctype:'Task',name:parentTaskName,fieldname:'is_group',value:1},callback:function(){\n"
        "frappe.call({method:'frappe.client.insert',args:{doc:{doctype:'Task',subject:v.subject,project:projectName,parent_task:parentTaskName,priority:v.priority,exp_end_date:v.exp_end_date||null,custom_task_list:parentTask?parentTask.custom_task_list:null,status:'Open'}},callback:function(r){if(!r.exc){\n"
        "if(v.assigned_to&&r.message&&r.message.name){frappe.xcall('frappe.desk.form.assign_to.add',{doctype:'Task',name:r.message.name,assign_to:[v.assigned_to]}).then(function(){frappe.show_alert({message:'Subtask created!',indicator:'green'});mtb_refresh();});}\n"
        "else{frappe.show_alert({message:'Subtask created!',indicator:'green'});mtb_refresh();}\n"
        "}}});\n"
        "}});\n"
        "});\n"
        "}"
    )

    if old_subtask in js:
        js = js.replace(old_subtask, new_subtask)
        print("  subtask modal: patched")
    elif new_subtask in js:
        print("  subtask modal: already patched, skipping Edit 2")
    else:
        frappe.throw("Edit 2 anchor not found — subtask function source may have drifted. Aborting.")

    # ─────────────────────────────────────────────────────────────────────
    # Save
    # ─────────────────────────────────────────────────────────────────────
    if js == doc.javascript:
        print("No changes needed.")
        return

    doc.javascript = js
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    new_len = len(js)
    print(f"Saved. Length: {original_len} -> {new_len} (+{new_len - original_len} chars)")
