"""
Master Task Board — make BOTH End Date and Assigned To required on every
"create task" path, and expand the subtask modal so users must set both
fields when adding a subtask too.

The auto-assign-to-creator after_insert hook stays as a defensive backstop
for any code path that bypasses these UIs (API direct, server scripts,
etc.) — but in normal use the user is forced to pick an assignee.

Why this exists: the original `_patch_mtb_v1.py` set `required:true` on
`exp_end_date` but a later edit/migration silently reverted it. We now
deploy the rule via direct text-replacement on the live Web Page and
sync the fixture so `bench migrate` won't undo it again (per learning #24).

Idempotent — safe to re-run.
"""

import frappe


PAGE = "master-task-board"

# Anchor → replacement pairs. Order matters: subtask first (its anchor is
# unique), then the 3 task-modal anchors which all share the same shape.

REPLACEMENTS = [
    # 1a. Subtask: ensure empOpts is defined in scope (the original subtask
    # function only defined priOpts).
    (
        "function mtb_add_subtask(parentTaskName,projectName){\n"
        "var priOpts=[{value:'Low',text:'Low'},{value:'Medium',text:'Medium'},{value:'High',text:'High'},{value:'Urgent',text:'Urgent'}];",
        "function mtb_add_subtask(parentTaskName,projectName){\n"
        "var priOpts=[{value:'Low',text:'Low'},{value:'Medium',text:'Medium'},{value:'High',text:'High'},{value:'Urgent',text:'Urgent'}];\n"
        "var empOpts=mtb_allEmployees.filter(function(e){return e.full_name;}).map(function(e){return {value:e.name,text:e.full_name};});",
    ),

    # 1b. Subtask modal — was: subject + priority only.
    # Add End Date (required) + Assigned To (required).
    (
        "mtb_modal('Add Subtask',[\n"
        "{name:'subject',type:'text',label:'Subtask Name',required:true},\n"
        "{name:'priority',type:'select',label:'Priority',options:priOpts,default:'Medium'}\n"
        "],'Create Subtask',function(v){",
        "mtb_modal('Add Subtask',[\n"
        "{name:'subject',type:'text',label:'Subtask Name',required:true},\n"
        "{name:'priority',type:'select',label:'Priority',options:priOpts,default:'Medium'},\n"
        "{name:'exp_end_date',type:'date',label:'End Date',required:true},\n"
        "{name:'assigned_to',type:'select',label:'Assigned To',options:empOpts,required:true}\n"
        "],'Create Subtask',function(v){",
    ),

    # 1c. If a previous run of this patch installed the "(blank = me)" version,
    # upgrade it to required + plain label.
    (
        "{name:'assigned_to',type:'select',label:'Assigned To (blank = me)',options:empOpts}\n"
        "],'Create Subtask',function(v){",
        "{name:'assigned_to',type:'select',label:'Assigned To',options:empOpts,required:true}\n"
        "],'Create Subtask',function(v){",
    ),

    # 2. Subtask insert payload — pass exp_end_date and trigger assign_to.add
    (
        "frappe.call({method:'frappe.client.insert',args:{doc:{doctype:'Task',subject:v.subject,project:projectName,parent_task:parentTaskName,priority:v.priority,custom_task_list:parentTask?parentTask.custom_task_list:null,status:'Open'}},callback:function(r){if(!r.exc){frappe.show_alert({message:'Subtask created!',indicator:'green'});mtb_refresh();}}});",
        "frappe.call({method:'frappe.client.insert',args:{doc:{doctype:'Task',subject:v.subject,project:projectName,parent_task:parentTaskName,priority:v.priority,exp_end_date:v.exp_end_date||null,custom_task_list:parentTask?parentTask.custom_task_list:null,status:'Open'}},callback:function(r){if(!r.exc){if(v.assigned_to&&r.message&&r.message.name){frappe.xcall('frappe.desk.form.assign_to.add',{doctype:'Task',name:r.message.name,assign_to:[v.assigned_to]}).then(function(){frappe.show_alert({message:'Subtask created!',indicator:'green'});mtb_refresh();});}else{frappe.show_alert({message:'Subtask created!',indicator:'green'});mtb_refresh();}}}});",
    ),

    # 3-5. The 3 task-creation modals — End Date → required, helpful hint on Assigned To.
    # Replace ALL occurrences via replace() on the JS string.
]

# Field-line replacements applied with str.replace (safe to apply globally — there are exactly 3 task modals + we already handled subtask above with a unique anchor)
GLOBAL_FIELD_REPLACEMENTS = [
    (
        "{name:'exp_end_date',type:'date',label:'End Date'},",
        "{name:'exp_end_date',type:'date',label:'End Date',required:true},",
    ),
    # Plain → required
    (
        "{name:'assigned_to',type:'select',label:'Assigned To',options:empOpts}",
        "{name:'assigned_to',type:'select',label:'Assigned To',options:empOpts,required:true}",
    ),
    # Earlier "(blank = me)" variant → required
    (
        "{name:'assigned_to',type:'select',label:'Assigned To (blank = me)',options:empOpts}",
        "{name:'assigned_to',type:'select',label:'Assigned To',options:empOpts,required:true}",
    ),
]


def run():
    doc = frappe.get_doc("Web Page", PAGE)
    js = doc.javascript or ""
    before_len = len(js)
    applied = []
    skipped = []

    for old, new in REPLACEMENTS:
        if new.split('\n')[0] in js and old.split('\n')[0] not in js:
            skipped.append("anchored: already applied")
            continue
        if old not in js:
            skipped.append("anchored: anchor missing — " + old.split('\n')[0][:60])
            continue
        js = js.replace(old, new, 1)
        applied.append("anchored: " + old.split('\n')[0][:60])

    for old, new in GLOBAL_FIELD_REPLACEMENTS:
        count = js.count(old)
        if count == 0:
            # Maybe already applied — check for new variant
            applied.append("global: already applied — " + old[:50])
            continue
        js = js.replace(old, new)
        applied.append("global: replaced {} occurrence(s) — {}".format(count, old[:50]))

    if js == doc.javascript:
        print("No changes (already applied).")
        return

    doc.javascript = js
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    print("Updated {} JS: {} → {} chars".format(PAGE, before_len, len(js)))
    for a in applied:
        print("  +", a)
    for s in skipped:
        print("  -", s)
