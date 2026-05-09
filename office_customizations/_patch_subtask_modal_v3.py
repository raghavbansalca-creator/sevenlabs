"""
Restore the expanded subtask modal with End Date (required) + Assigned To (optional).
The previous patch chain left the subtask modal in its original 2-field state.
"""

import frappe


def run():
    doc = frappe.get_doc("Web Page", "master-task-board")
    js = doc.javascript

    # Match either the original 2-field state OR any partially-patched state
    # by anchoring on the function definition signature
    import re

    pattern = re.compile(
        r"function mtb_add_subtask\(parentTaskName,projectName\)\{.*?\n\}\n",
        re.S,
    )

    new_func = (
        "function mtb_add_subtask(parentTaskName,projectName){\n"
        "var priOpts=[{value:'Low',text:'Low'},{value:'Medium',text:'Medium'},{value:'High',text:'High'},{value:'Urgent',text:'Urgent'}];\n"
        "var empOpts=mtb_allEmployees.filter(function(e){return e.full_name;}).map(function(e){return {value:e.name,text:e.full_name};});\n"
        "mtb_modal('Add Subtask',[\n"
        "{name:'subject',type:'text',label:'Subtask Name',required:true},\n"
        "{name:'priority',type:'select',label:'Priority',options:priOpts,default:'Medium'},\n"
        "{name:'exp_end_date',type:'date',label:'End Date',required:true},\n"
        "{name:'assigned_to',type:'select',label:'Assigned To',options:empOpts}\n"
        "],'Create Subtask',function(v){\n"
        "var parentTask=mtb_allTasks.find(function(t){return t.name===parentTaskName;});\n"
        "frappe.call({method:'frappe.client.set_value',args:{doctype:'Task',name:parentTaskName,fieldname:'is_group',value:1},callback:function(){\n"
        "frappe.call({method:'frappe.client.insert',args:{doc:{doctype:'Task',subject:v.subject,project:projectName,parent_task:parentTaskName,priority:v.priority,exp_end_date:v.exp_end_date||null,custom_task_list:parentTask?parentTask.custom_task_list:null,status:'Open'}},callback:function(r){if(!r.exc){\n"
        "if(v.assigned_to&&r.message&&r.message.name){frappe.xcall('frappe.desk.form.assign_to.add',{doctype:'Task',name:r.message.name,assign_to:[v.assigned_to]}).then(function(){frappe.show_alert({message:'Subtask created!',indicator:'green'});mtb_refresh();});}\n"
        "else{frappe.show_alert({message:'Subtask created!',indicator:'green'});mtb_refresh();}\n"
        "}}});\n"
        "}});\n"
        "});\n"
        "}\n"
    )

    matches = pattern.findall(js)
    if not matches:
        frappe.throw("mtb_add_subtask not found")
    if len(matches) > 1:
        frappe.throw(f"Found {len(matches)} mtb_add_subtask definitions; aborting")

    js_new = pattern.sub(new_func, js, count=1)
    if js_new == js:
        frappe.throw("Replacement made no change")

    doc.javascript = js_new
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    print("mtb_add_subtask restored with End Date (required) + Assigned To (optional)")
