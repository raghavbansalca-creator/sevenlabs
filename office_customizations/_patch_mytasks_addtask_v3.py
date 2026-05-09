"""
v3 — single self-contained patch for the /my-tasks "+ Add Task" feature.

Inserts:
  1) The button HTML next to Refresh
  2) The click handler next to the existing Refresh handler
  3) The modal function (HTML-based, works in website context)

Idempotent and self-healing — strips any partial v1/v2 state before applying.
"""

import frappe
import re


SENTINEL = "/* mtd_addtask_v3 */"


def run():
    doc = frappe.get_doc("Web Page", "my-tasks")
    js = doc.javascript

    if SENTINEL in js:
        print("Already on v3 — skipping")
        return

    # --- Strip prior partial states ---
    # Remove any v1/v2 modal function/comment markers
    js = re.sub(
        r'\n?    /\* mtd_addtask_(?:button_v1|modal_v2|v3) \*/.*?\n    \}\n',
        '\n',
        js,
        flags=re.S,
    )
    # Remove any add-task button HTML push
    js = re.sub(
        r"html\.push\('<button class=\"mtd-add-task-btn\"[^']*'\);",
        '',
        js,
    )
    # Remove any add-task click handler
    js = re.sub(
        r'\n\s*\$root\.find\("#mtd-add-task"\)\.off\("click"\)\.on\("click", function \(\) \{\n\s*mtdOpenAddTaskDialog\(\);\n\s*\}\);',
        '',
        js,
    )

    # --- 1. Insert button HTML next to Refresh ---
    refresh_html = (
        "html.push('<button class=\"mtd-refresh-btn\" id=\"mtd-refresh\">"
        "&#8635; Refresh</button>');"
    )
    add_btn_html = (
        "html.push('<button class=\"mtd-add-task-btn\" id=\"mtd-add-task\" "
        "style=\"background:#2490EF;color:#fff;border:none;border-radius:6px;"
        "padding:6px 12px;font-size:12px;font-weight:600;cursor:pointer;"
        "margin-right:6px;\">+ Add Task</button>');"
    )
    if refresh_html not in js:
        frappe.throw("Refresh button HTML anchor not found")
    js = js.replace(refresh_html, add_btn_html + refresh_html)

    # --- 2. Insert click handler ---
    refresh_handler = (
        '$root.find("#mtd-refresh").off("click").on("click", function () {\n'
        '            loadTasks();\n'
        '        });'
    )
    add_handler = (
        '\n\n        $root.find("#mtd-add-task").off("click").on("click", function () {\n'
        '            mtdOpenAddTaskDialog();\n'
        '        });'
    )
    if refresh_handler not in js:
        frappe.throw("Refresh click handler anchor not found")
    js = js.replace(refresh_handler, refresh_handler + add_handler)

    # --- 3. Append modal function ---
    modal_fn = """

    /* mtd_addtask_v3 */
    var mtd_projects_cache = null;
    var mtd_users_cache = null;

    function mtdLoadPickers() {
        var p1 = mtd_projects_cache ? Promise.resolve(mtd_projects_cache) :
            frappe.xcall("frappe.client.get_list", {
                doctype: "Project",
                fields: ["name", "project_name"],
                filters: {status: "Open"},
                order_by: "project_name asc",
                limit_page_length: 0
            }).then(function (r) { mtd_projects_cache = r || []; return mtd_projects_cache; });

        var p2 = mtd_users_cache ? Promise.resolve(mtd_users_cache) :
            frappe.xcall("frappe.client.get_list", {
                doctype: "User",
                fields: ["name", "full_name"],
                filters: {enabled: 1, user_type: "System User"},
                order_by: "full_name asc",
                limit_page_length: 0
            }).then(function (r) { mtd_users_cache = (r || []).filter(function (u) { return u.full_name; }); return mtd_users_cache; });

        return Promise.all([p1, p2]);
    }

    function mtdOpenAddTaskDialog() {
        mtdLoadPickers().then(function (results) {
            var projects = results[0];
            var users = results[1];

            var modalId = "mtd_modal_" + Date.now();
            var html = '<div class="modal fade" id="' + modalId + '" tabindex="-1" role="dialog" style="display:none;">';
            html += '<div class="modal-dialog" style="width:480px;"><div class="modal-content" style="border-radius:6px;">';
            html += '<div class="modal-header" style="border-bottom:1px solid #E2E8F0;padding:14px 16px;background:#F7FAFC;">';
            html += '<button type="button" class="close" data-dismiss="modal" style="opacity:0.7;font-size:22px;border:none;background:none;cursor:pointer;">&#215;</button>';
            html += '<h4 style="margin:0;font-weight:600;font-size:15px;">+ Add Task</h4></div>';
            html += '<div class="modal-body" style="padding:16px;">';

            html += '<div style="margin-bottom:12px;"><label style="display:block;font-size:12px;font-weight:500;margin-bottom:4px;">Task Name <span style="color:#E53E3E;">*</span></label>';
            html += '<input type="text" id="mtd_f_subject" class="form-control" style="font-size:12px;padding:6px 8px;width:100%;box-sizing:border-box;border:1px solid #CBD5E0;border-radius:4px;" /></div>';

            html += '<div style="margin-bottom:12px;"><label style="display:block;font-size:12px;font-weight:500;margin-bottom:4px;">Project <span style="color:#E53E3E;">*</span></label>';
            html += '<select id="mtd_f_project" class="form-control" style="font-size:12px;padding:6px 8px;width:100%;box-sizing:border-box;border:1px solid #CBD5E0;border-radius:4px;">';
            html += '<option value="">-- Select project --</option>';
            projects.forEach(function (p) { html += '<option value="' + p.name + '">' + (p.project_name || p.name) + '</option>'; });
            html += '</select></div>';

            html += '<div style="margin-bottom:12px;"><label style="display:block;font-size:12px;font-weight:500;margin-bottom:4px;">Priority</label>';
            html += '<select id="mtd_f_priority" class="form-control" style="font-size:12px;padding:6px 8px;width:100%;box-sizing:border-box;border:1px solid #CBD5E0;border-radius:4px;">';
            ["Low", "Medium", "High", "Urgent"].forEach(function (p) {
                html += '<option value="' + p + '"' + (p === "Medium" ? " selected" : "") + '>' + p + '</option>';
            });
            html += '</select></div>';

            html += '<div style="margin-bottom:12px;"><label style="display:block;font-size:12px;font-weight:500;margin-bottom:4px;">Assigned To <span style="color:#E53E3E;">*</span></label>';
            html += '<select id="mtd_f_assignee" class="form-control" style="font-size:12px;padding:6px 8px;width:100%;box-sizing:border-box;border:1px solid #CBD5E0;border-radius:4px;">';
            html += '<option value="">-- Select assignee --</option>';
            users.forEach(function (u) { html += '<option value="' + u.name + '">' + u.full_name + '</option>'; });
            html += '</select></div>';

            html += '<div style="margin-bottom:12px;"><label style="display:block;font-size:12px;font-weight:500;margin-bottom:4px;">End Date <span style="color:#E53E3E;">*</span></label>';
            html += '<input type="date" id="mtd_f_end_date" class="form-control" style="font-size:12px;padding:6px 8px;width:100%;box-sizing:border-box;border:1px solid #CBD5E0;border-radius:4px;" /></div>';

            html += '</div>';
            html += '<div class="modal-footer" style="border-top:1px solid #E2E8F0;padding:10px 14px;background:#F7FAFC;">';
            html += '<button type="button" class="btn btn-default" data-dismiss="modal">Cancel</button>';
            html += '<button type="button" class="btn btn-primary" id="mtd_create_btn" style="font-weight:600;">Create Task</button>';
            html += '</div></div></div></div>';

            $("body").append(html);
            var $modal = $("#" + modalId);

            $modal.find("#mtd_create_btn").on("click", function () {
                var subject = $modal.find("#mtd_f_subject").val().trim();
                var project = $modal.find("#mtd_f_project").val();
                var end_date = $modal.find("#mtd_f_end_date").val();
                var priority = $modal.find("#mtd_f_priority").val();
                var assignee = $modal.find("#mtd_f_assignee").val();

                var invalid = [];
                if (!subject) { invalid.push("#mtd_f_subject"); }
                if (!project) { invalid.push("#mtd_f_project"); }
                if (!end_date) { invalid.push("#mtd_f_end_date"); }
                if (!assignee) { invalid.push("#mtd_f_assignee"); }
                $modal.find("#mtd_f_subject, #mtd_f_project, #mtd_f_end_date, #mtd_f_assignee").css("border-color", "#CBD5E0");
                if (invalid.length) {
                    invalid.forEach(function (s) { $modal.find(s).css("border-color", "#E53E3E"); });
                    frappe.show_alert({message: "Please fill required fields", indicator: "red"});
                    return;
                }

                frappe.call({
                    method: "frappe.client.insert",
                    args: {
                        doc: {
                            doctype: "Task",
                            subject: subject,
                            project: project,
                            priority: priority,
                            exp_end_date: end_date,
                            status: "Open"
                        }
                    },
                    callback: function (r) {
                        if (r.exc) return;
                        var task_name = r.message && r.message.name;
                        var done = function () {
                            $modal.modal("hide");
                            frappe.show_alert({message: "Task created!", indicator: "green"});
                            loadTasks();
                        };
                        if (assignee && task_name) {
                            frappe.xcall("frappe.desk.form.assign_to.add", {
                                doctype: "Task",
                                name: task_name,
                                assign_to: [assignee]
                            }).then(done);
                        } else {
                            done();
                        }
                    }
                });
            });

            $modal.on("hidden.bs.modal", function () { $modal.remove(); });
            $modal.modal("show");
        });
    }
"""

    js_stripped = js.rstrip()
    if js_stripped.endswith("})();"):
        js = js_stripped[:-len("})();")] + modal_fn + "\n})();\n"
    elif js_stripped.endswith("})()"):
        js = js_stripped[:-len("})()")] + modal_fn + "\n})()\n"
    else:
        js = js_stripped + "\n" + modal_fn + "\n"

    doc.javascript = js
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    print("Patched my-tasks v3: button + handler + modal.")
