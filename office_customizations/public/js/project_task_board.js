frappe.ui.form.on("Project", {
    refresh: function(frm) {
        if (frm.doc.name && !frm.is_new()) {
            setTimeout(function() {
                inject_tab_bar(frm);
                load_project_tasks(frm);
            }, 100);
        }
    }
});

var allEmployees = [];
var projectTasks = [];
var taskLists = [];
var projectWaMessages = [];
var projectWaMappings = [];
var projectTgGroups = [];
var currentTab = "Details";

function load_employees() {
    frappe.call({
        method: "frappe.client.get_list",
        args: { doctype: "User", fields: ["name", "full_name"], filters: {enabled: 1}, limit_page_length: 500 },
        async: false,
        callback: function(r) { allEmployees = r.message || []; }
    });
}

function load_task_lists() {
    frappe.call({
        method: "frappe.client.get_list",
        args: { doctype: "Task List", fields: ["name"], filters: {project: cur_frm.doc.name}, limit_page_length: 100 },
        async: false,
        callback: function(r) { taskLists = r.message || []; }
    });
}

function inject_tab_bar(frm) {
    var $layout = frm.page.main.find('.form-layout');
    if ($layout.find('.custom-form-tabs').length) return;

    load_employees();
    load_task_lists();

    var tabHtml = '<div class="custom-form-tabs" style="border-bottom:1px solid #d1d8dd;margin-bottom:15px;display:flex;padding:0 15px;">';
    tabHtml += '<button class="custom-tab-btn active" data-tab="Details" style="background:none;border:none;padding:10px 20px;font-weight:600;font-size:13px;color:#2d3436;border-bottom:2px solid #2490EF;cursor:pointer;outline:none;">Details</button>';
    tabHtml += '<button class="custom-tab-btn" data-tab="Task Board" style="background:none;border:none;padding:10px 20px;font-weight:600;font-size:13px;color:#8D99A6;border-bottom:2px solid transparent;cursor:pointer;outline:none;">Task Board</button>';
    tabHtml += '<button class="custom-tab-btn" data-tab="WhatsApp" style="background:none;border:none;padding:10px 20px;font-weight:600;font-size:13px;color:#8D99A6;border-bottom:2px solid transparent;cursor:pointer;outline:none;">&#128172; WhatsApp <span id="wa-tab-badge" style="display:none;background:#25D366;color:#fff;font-size:10px;padding:1px 6px;border-radius:10px;margin-left:4px;font-weight:700;">0</span></button>';
    tabHtml += '<button class="custom-tab-btn" data-tab="Telegram" style="background:none;border:none;padding:10px 20px;font-weight:600;font-size:13px;color:#8D99A6;border-bottom:2px solid transparent;cursor:pointer;outline:none;">&#9992; Telegram <span id="tg-tab-badge" style="display:none;background:#0088cc;color:#fff;font-size:10px;padding:1px 6px;border-radius:10px;margin-left:4px;font-weight:700;">0</span></button>';
    tabHtml += '</div>';
    $layout.prepend(tabHtml);

    $('.custom-tab-btn').on('click', function() { switch_tab($(this).data('tab'), frm); });

    var $formPage = $layout.find('.form-page');
    var tbHtml = '<div id="task-board-container" style="display:none;padding:0 15px 15px 15px;">';
    tbHtml += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">';
    tbHtml += '<div style="display:flex;align-items:center;gap:10px;">';
    tbHtml += '<h5 style="margin:0;font-weight:700;font-size:15px;color:#2d3436;">Task Board</h5>';
    tbHtml += '<span id="task-count-badge" style="background:#E8F5E9;color:#2E7D32;font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600;">0 tasks</span>';
    tbHtml += '</div>';
    tbHtml += '<div style="display:flex;gap:8px;">';
    tbHtml += '<button class="btn btn-default btn-xs" onclick="add_new_task_list()" style="font-weight:500;">+ New List</button>';
    tbHtml += '<button class="btn btn-primary btn-xs" onclick="add_new_task()" style="font-weight:600;">+ Add Task</button>';
    tbHtml += '<button class="btn btn-default btn-xs" onclick="refresh_task_board()" style="font-weight:500;">\u21bb Refresh</button>';
    tbHtml += '</div></div>';
    tbHtml += '<div id="task-board-groups"></div>';
    tbHtml += '</div>';

    // WhatsApp conversation log container
    var waHtml = '<div id="wa-chat-container" style="display:none;padding:0 15px 15px 15px;">';
    waHtml += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">';
    waHtml += '<div style="display:flex;align-items:center;gap:10px;">';
    waHtml += '<h5 style="margin:0;font-weight:700;font-size:15px;color:#2d3436;">&#128172; WhatsApp</h5>';
    waHtml += '<span id="wa-msg-count-badge" style="background:#DCF8C6;color:#128C7E;font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600;">0 messages</span>';
    waHtml += '</div>';
    waHtml += '<div style="display:flex;gap:8px;">';
    waHtml += '<button class="btn btn-primary btn-xs" onclick="show_wa_send_dialog()" style="background:#25D366;border-color:#25D366;font-weight:600;">&#128228; Send to Client</button>';
    waHtml += '<button class="btn btn-default btn-xs" onclick="show_wa_numbers_dialog()" style="font-weight:500;">&#128222; Manage Numbers</button>';
    waHtml += '<button class="btn btn-default btn-xs" onclick="show_import_chat_dialog()" style="font-weight:500;">&#128229; Import Chat</button>';
    waHtml += '<button class="btn btn-default btn-xs" onclick="refresh_wa_chat()" style="font-weight:500;">&#8635; Refresh</button>';
    waHtml += '</div></div>';
    waHtml += '<div id="wa-numbers-bar" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px;"></div>';
    waHtml += '<div id="wa-messages" style="height:480px;overflow-y:auto;background:#FAFAFA;border:1px solid #e0e0e0;border-radius:8px;padding:0;">';
    waHtml += '<div style="text-align:center;color:#888;font-size:12px;padding:40px 0;">Loading conversations...</div>';
    waHtml += '</div>';
    waHtml += '</div>';

    $formPage.before(tbHtml);
    $formPage.before(waHtml);

    // Telegram conversation log container
    var tgHtml = '<div id="tg-chat-container" style="display:none;padding:0 15px 15px 15px;">';
    tgHtml += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">';
    tgHtml += '<div style="display:flex;align-items:center;gap:10px;">';
    tgHtml += '<h5 style="margin:0;font-weight:700;font-size:15px;color:#2d3436;">&#9992; Telegram</h5>';
    tgHtml += '<span id="tg-msg-count-badge" style="background:#D4EDFF;color:#0088cc;font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600;">0 messages</span>';
    tgHtml += '</div>';
    tgHtml += '<div style="display:flex;gap:8px;">';
    tgHtml += '<button class="btn btn-primary btn-xs" onclick="show_tg_send_dialog()" style="background:#0088cc;border-color:#0088cc;font-weight:600;">&#128228; Send to Client</button>';
    tgHtml += '<button class="btn btn-default btn-xs" onclick="show_tg_groups_dialog()" style="font-weight:500;">&#9992; Manage Chats</button>';
    tgHtml += '<button class="btn btn-default btn-xs" onclick="refresh_tg_chat()" style="font-weight:500;">&#8635; Refresh</button>';
    tgHtml += '</div></div>';
    tgHtml += '<div id="tg-groups-bar" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px;"></div>';
    tgHtml += '<div id="tg-messages" style="height:480px;overflow-y:auto;background:#FAFAFA;border:1px solid #e0e0e0;border-radius:8px;padding:0;">';
    tgHtml += '<div style="text-align:center;color:#888;font-size:12px;padding:40px 0;">Loading conversations...</div>';
    tgHtml += '</div>';
    tgHtml += '</div>';

    $formPage.before(tgHtml);
}

function switch_tab(tabName, frm) {
    currentTab = tabName;
    var $layout = frm.page.main.find('.form-layout');
    var $formPage = $layout.find('.form-page');
    var $taskBoard = $('#task-board-container');
    var $waChat = $('#wa-chat-container');
    var $tgChat = $('#tg-chat-container');
    $('.custom-tab-btn').each(function() {
        if ($(this).data('tab') === tabName) {
            $(this).css({'color':'#2d3436','border-bottom':'2px solid #2490EF'}).addClass('active');
        } else {
            $(this).css({'color':'#8D99A6','border-bottom':'2px solid transparent'}).removeClass('active');
        }
    });
    if (tabName === "Details") {
        $formPage.show(); $taskBoard.hide(); $waChat.hide(); $tgChat.hide();
    } else if (tabName === "Task Board") {
        $formPage.hide(); $taskBoard.show(); $waChat.hide(); $tgChat.hide();
        load_project_tasks(frm); setTimeout(function() { render_task_board(frm); }, 300);
    } else if (tabName === "WhatsApp") {
        $formPage.hide(); $taskBoard.hide(); $waChat.show(); $tgChat.hide();
        load_wa_data(frm);
    } else if (tabName === "Telegram") {
        $formPage.hide(); $taskBoard.hide(); $waChat.hide(); $tgChat.show();
        load_tg_data(frm);
    }
}

function load_project_tasks(frm) {
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Task", filters: { project: frm.doc.name },
            fields: ["name","subject","status","priority","exp_start_date","exp_end_date","_assign","is_group","parent_task","progress","custom_task_list"],
            order_by: "creation asc", limit_page_length: 500
        },
        async: false,
        callback: function(r) { projectTasks = r.message || []; }
    });
}

function render_task_board(frm) {
    $('#task-count-badge').text(projectTasks.length + ' task' + (projectTasks.length !== 1 ? 's' : ''));

    var html = '';

    // Group 1: Tasks grouped by each Task List
    taskLists.forEach(function(tl) {
        var listTasks = projectTasks.filter(function(t) { return t.custom_task_list === tl.name && !t.parent_task; });
        var listSubtasks = projectTasks.filter(function(t) { return t.custom_task_list === tl.name && t.parent_task; });
        var totalInList = listTasks.length + listSubtasks.length;

        html += '<div class="task-list-group" style="background:#fff;border:1px solid #d1d8dd;border-radius:8px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,0.06);">';

        // Group header
        html += '<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 15px;background:linear-gradient(to right,#F7FAFC,#EDF2F7);border-bottom:1px solid #E2E8F0;border-radius:8px 8px 0 0;">';
        html += '<div style="display:flex;align-items:center;gap:8px;">';
        html += '<span class="editable-task-list" data-name="' + tl.name + '" style="font-weight:700;font-size:14px;color:#2D3748;cursor:pointer;">📁 ' + (tl.title || tl.name) + '</span>';
        //html += '<span style="font-weight:700;font-size:14px;color:#2D3748;">\ud83d\udcc1 ' + tl.name + '</span>';
        html += '<span style="background:#E2E8F0;color:#4A5568;font-size:10px;padding:2px 6px;border-radius:8px;font-weight:600;">' + totalInList + '</span>';
        html += '</div>';
        html += '<div style="display:flex;gap:6px;">';
        html += '<button class="btn btn-xs" onclick="add_task_to_list(\'' + tl.name.replace(/'/g, "\\'") + '\')" style="background:#EBF8FF;color:#2B6CB0;border:1px solid #BEE3F8;font-size:10px;padding:2px 8px;">+ Task</button>';
        html += '<button class="btn btn-xs" onclick="delete_task_list(\'' + tl.name.replace(/'/g, "\\'") + '\')" style="background:#FFF5F5;color:#E53E3E;border:1px solid #FED7D7;font-size:10px;padding:2px 6px;">\u2715</button>';
        html += '</div></div>';

        // Task table for this list
        if (totalInList > 0) {
            html += '<div style="overflow-x:auto;">';
            html += build_task_table(listTasks, projectTasks);
            html += '</div>';
        } else {
            html += '<div style="padding:20px;text-align:center;color:#A0AEC0;font-size:12px;">No tasks in this list</div>';
        }
        html += '</div>';
    });

    // Group 2: Unassigned tasks (no task list)
    var unassigned = projectTasks.filter(function(t) { return !t.custom_task_list && !t.parent_task; });
    var unassignedSubs = projectTasks.filter(function(t) { return !t.custom_task_list && t.parent_task; });
    var unassignedTotal = unassigned.length + unassignedSubs.length;

    if (unassignedTotal > 0 || projectTasks.length === 0) {
        html += '<div class="task-list-group" style="background:#fff;border:1px solid #d1d8dd;border-radius:8px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,0.06);">';
        html += '<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 15px;background:linear-gradient(to right,#FAFBFC,#F0F0F0);border-bottom:1px solid #E2E8F0;border-radius:8px 8px 0 0;">';
        html += '<div style="display:flex;align-items:center;gap:8px;">';
        html += '<span style="font-weight:700;font-size:14px;color:#718096;">\ud83d\udccb Unassigned Tasks</span>';
        html += '<span style="background:#E2E8F0;color:#4A5568;font-size:10px;padding:2px 6px;border-radius:8px;font-weight:600;">' + unassignedTotal + '</span>';
        html += '</div>';
        html += '<button class="btn btn-xs" onclick="add_new_task()" style="background:#EBF8FF;color:#2B6CB0;border:1px solid #BEE3F8;font-size:10px;padding:2px 8px;">+ Task</button>';
        html += '</div>';

        if (unassignedTotal > 0) {
            html += '<div style="overflow-x:auto;">';
            html += build_task_table(unassigned, projectTasks);
            html += '</div>';
        } else {
            html += '<div style="padding:20px;text-align:center;color:#A0AEC0;font-size:12px;">No tasks. Click + Add Task to create one.</div>';
        }
        html += '</div>';
    }

    $('#task-board-groups').html(html);
    attach_task_events();
}

function build_task_table(parentTasks, allTasks) {
    var h = '<table style="width:100%;table-layout:fixed;min-width:1100px;border-collapse:collapse;font-size:12px;">';
    h += '<thead style="background:#F7FAFC;border-bottom:1px solid #CBD5E0;"><tr>';
    h += '<th style="padding:8px;text-align:left;border-right:1px solid #E2E8F0;font-weight:600;color:#4A5568;width:200px;">Task</th>';
    h += '<th style="padding:8px;text-align:center;border-right:1px solid #E2E8F0;font-weight:600;color:#4A5568;width:100px;">Status</th>';
    h += '<th style="padding:8px;text-align:center;border-right:1px solid #E2E8F0;font-weight:600;color:#4A5568;width:80px;">Priority</th>';
    h += '<th style="padding:8px;text-align:center;border-right:1px solid #E2E8F0;font-weight:600;color:#4A5568;width:100px;">Start Date</th>';
    h += '<th style="padding:8px;text-align:center;border-right:1px solid #E2E8F0;font-weight:600;color:#4A5568;width:100px;">End Date</th>';
    h += '<th style="padding:8px;text-align:center;border-right:1px solid #E2E8F0;font-weight:600;color:#4A5568;width:120px;">Assigned To</th>';
    h += '<th style="padding:8px;text-align:center;border-right:1px solid #E2E8F0;font-weight:600;color:#4A5568;width:70px;">Progress</th>';
    h += '<th style="padding:8px;text-align:center;font-weight:600;color:#4A5568;width:75px;">Actions</th>';
    h += '</tr></thead><tbody>';

    parentTasks.forEach(function(task) {
        h += render_task_row(task, 0);
        var subs = allTasks.filter(function(t) { return t.parent_task === task.name; });
        subs.forEach(function(sub) { h += render_task_row(sub, 1); });
    });

    h += '</tbody></table>';
    return h;
}

function render_task_row(task, level) {
    var indent = level > 0 ? 'padding-left:28px;' : '';
    var prefix = level > 0 ? '<span style="color:#CBD5E0;margin-right:4px;">\u2514</span> ' : '';
    var rowBg = level > 0 ? 'background:#F7FAFC;' : '';

    var assignedEmail = '';
    if (task._assign) { try { var arr = JSON.parse(task._assign); if (arr.length) assignedEmail = arr[0]; } catch(e) {} }

    var startDt = task.exp_start_date ? task.exp_start_date.split(' ')[0] : '';
    var endDt = task.exp_end_date ? task.exp_end_date.split(' ')[0] : '';
    var startDisplay = startDt ? format_date_display(startDt) : '';
    var endDisplay = endDt ? format_date_display(endDt) : '';

    var statusBg = {Open:'#EBF8FF',Working:'#FFFFF0','Pending Review':'#FAF5FF',Completed:'#F0FFF4',Cancelled:'#F7FAFC',Overdue:'#FFF5F5'};
    var statusColors = {Open:'#3182CE',Working:'#D69E2E','Pending Review':'#805AD5',Completed:'#38A169',Cancelled:'#A0AEC0',Overdue:'#E53E3E'};
    var priBg = {Low:'#F0FFF4',Medium:'#FFFFF0',High:'#FFF5F5',Urgent:'#FFF5F5'};
    var priColors = {Low:'#38A169',Medium:'#D69E2E',High:'#E53E3E',Urgent:'#C53030'};
    var progress = task.progress || 0;

    var row = '<tr data-task="' + task.name + '" style="border-bottom:1px solid #E2E8F0;' + rowBg + '">';

    row += '<td style="' + indent + 'padding:8px;border-right:1px solid #E2E8F0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">';
    row += prefix + '<a href="/app/task/' + task.name + '" style="color:#2B6CB0;text-decoration:none;font-weight:500;" title="' + (task.subject || task.name) + '">' + (task.subject || task.name) + '</a></td>';

    row += '<td style="padding:8px;border-right:1px solid #E2E8F0;text-align:center;"><select class="task-field-select" data-task="' + task.name + '" data-field="status" style="appearance:menulist;padding:3px 4px;border:1px solid #E2E8F0;border-radius:4px;font-size:11px;width:100%;background:' + (statusBg[task.status]||'#fff') + ';color:' + (statusColors[task.status]||'#4A5568') + ';font-weight:600;cursor:pointer;">';
    ['Open','Working','Pending Review','Overdue','Completed','Cancelled'].forEach(function(s) { row += '<option value="' + s + '"' + (task.status===s?' selected':'') + '>' + s + '</option>'; });
    row += '</select></td>';

    row += '<td style="padding:8px;border-right:1px solid #E2E8F0;text-align:center;"><select class="task-field-select" data-task="' + task.name + '" data-field="priority" style="appearance:menulist;padding:3px 4px;border:1px solid #E2E8F0;border-radius:4px;font-size:11px;width:100%;background:' + (priBg[task.priority]||'#fff') + ';color:' + (priColors[task.priority]||'#4A5568') + ';font-weight:600;cursor:pointer;">';
    ['Low','Medium','High','Urgent'].forEach(function(p) { row += '<option value="' + p + '"' + (task.priority===p?' selected':'') + '>' + p + '</option>'; });
    row += '</select></td>';

    row += '<td style="padding:8px;border-right:1px solid #E2E8F0;text-align:center;"><div class="task-date-display" data-task="' + task.name + '" data-field="exp_start_date" data-value="' + startDt + '" style="cursor:pointer;padding:4px 6px;border:1px solid transparent;border-radius:4px;background:#F7FAFC;font-size:11px;display:flex;align-items:center;justify-content:center;gap:3px;min-height:28px;">';
    row += startDisplay ? '<span>' + startDisplay + '</span>' : '<span style="color:#A0AEC0;">Set date</span>';
    row += ' <span style="font-size:10px;">\ud83d\udcc5</span></div></td>';

    row += '<td style="padding:8px;border-right:1px solid #E2E8F0;text-align:center;"><div class="task-date-display" data-task="' + task.name + '" data-field="exp_end_date" data-value="' + endDt + '" style="cursor:pointer;padding:4px 6px;border:1px solid transparent;border-radius:4px;background:#F7FAFC;font-size:11px;display:flex;align-items:center;justify-content:center;gap:3px;min-height:28px;">';
    row += endDisplay ? '<span>' + endDisplay + '</span>' : '<span style="color:#A0AEC0;">Set date</span>';
    row += ' <span style="font-size:10px;">\ud83d\udcc5</span></div></td>';

    row += '<td style="padding:8px;border-right:1px solid #E2E8F0;text-align:center;"><select class="task-assigned-select" data-task="' + task.name + '" style="appearance:menulist;padding:3px 4px;border:1px solid #E2E8F0;border-radius:4px;font-size:11px;width:100%;cursor:pointer;">';
    row += '<option value="">-- Unassigned --</option>';
    allEmployees.forEach(function(emp) { row += '<option value="' + emp.name + '"' + (assignedEmail===emp.name?' selected':'') + '>' + (emp.full_name||emp.name) + '</option>'; });
    row += '</select></td>';

    row += '<td style="padding:8px;border-right:1px solid #E2E8F0;text-align:center;"><div style="display:flex;flex-direction:column;align-items:center;gap:2px;"><div style="width:100%;background:#E2E8F0;border-radius:3px;height:6px;overflow:hidden;"><div style="background:' + (progress>=100?'#38A169':'#2490EF') + ';height:100%;width:' + progress + '%;border-radius:3px;"></div></div><span class="task-progress-text" style="font-size:10px;color:#718096;cursor:pointer;" data-task="' + task.name + '">' + progress + '%</span></div></td>';

    row += '<td style="padding:8px;text-align:center;"><div style="display:flex;gap:4px;justify-content:center;">';
    if (level === 0) row += '<button class="btn btn-xs task-add-subtask-btn" data-task="' + task.name + '" style="background:#EBF8FF;color:#2B6CB0;border:1px solid #BEE3F8;font-size:10px;padding:2px 6px;border-radius:3px;">+Sub</button>';
    row += '<button class="btn btn-xs task-delete-btn" data-task="' + task.name + '" style="background:#FFF5F5;color:#E53E3E;border:1px solid #FED7D7;font-size:10px;padding:2px 6px;border-radius:3px;">\u2715</button>';
    row += '</div></td></tr>';
    return row;
}

function format_date_display(dateStr) {
    if (!dateStr) return '';
    var p = dateStr.split('-');
    return p.length === 3 ? p[2]+'-'+p[1]+'-'+p[0] : dateStr;
}

function attach_task_events() {
    $('.task-field-select').off('change').on('change', function() {
        update_task_field($(this).data('task'), $(this).data('field'), $(this).val());
    });
    $('.task-assigned-select').off('change').on('change', function() {
        var userEmail = $(this).val();
        if (userEmail) {
            frappe.xcall('frappe.desk.form.assign_to.add', { doctype:'Task', name:$(this).data('task'), assign_to:[userEmail] })
            .then(function() { frappe.show_alert({message:'Assigned', indicator:'green'}); });
        }
    });
    $('.task-date-display').off('click').on('click', function() {
        open_date_picker($(this).data('task'), $(this).data('field'), $(this).attr('data-value')||'');
    });
    $('.task-date-display').on('mouseenter', function() { $(this).css({'background':'#EDF2F7','border-color':'#CBD5E0'}); })
    .on('mouseleave', function() { $(this).css({'background':'#F7FAFC','border-color':'transparent'}); });
    $('.task-progress-text').off('click').on('click', function() {
        var taskName = $(this).data('task');
        var task = projectTasks.find(function(t) { return t.name === taskName; });
        var d = new frappe.ui.Dialog({ title:'Set Progress', fields:[{fieldname:'progress',fieldtype:'Percent',label:'Progress (%)',default:task?task.progress:0}],
            primary_action_label:'Save', primary_action:function(v) { update_task_field(taskName,'progress',v.progress); d.hide(); setTimeout(function(){render_task_board(cur_frm);},500); } });
        d.show();
    });

    // Add Subtask
    $('.task-add-subtask-btn').off('click').on('click', function(e) {
        e.preventDefault();
        add_subtask($(this).data('task'));
    });

    // Delete Task
    $('.task-delete-btn').off('click').on('click', function(e) {
        e.preventDefault();
        delete_task($(this).data('task'));
    });

    // ===== Inline Rename Task List =====
    $('.editable-task-list').off('click').on('click', function() {

        var oldName = $(this).data('name');
        var currentText = $(this).text().replace('📁','').trim();
        var $el = $(this);

        var input = $('<input type="text" class="form-control input-xs" style="height:24px;font-size:12px;width:160px;">');
        input.val(currentText);

        $el.replaceWith(input);
        input.focus();

        input.on('blur keypress', function(e) {

            if (e.type === 'blur' || e.which === 13) {

                var newName = input.val().trim();

                if (!newName || newName === currentText) {
                    load_task_lists();
                    render_task_board(cur_frm);
                    return;
                }

                frappe.call({
                    method: 'frappe.client.rename_doc',
                    args: {
                        doctype: 'Task List',
                        old_name: oldName,
                        new_name: newName,
                        merge: 0
                    },
                    callback: function(r) {
                        if (!r.exc) {
                            frappe.show_alert({
                                message: 'Renamed',
                                indicator: 'green'
                            });

                            load_task_lists();
                            load_project_tasks(cur_frm);
                            render_task_board(cur_frm);
                        }
                    }
                });
            }
        });
    });
}

function update_task_field(taskName, fieldName, value) {
    frappe.call({ method:'frappe.client.set_value', args:{doctype:'Task',name:taskName,fieldname:fieldName,value:value},
        callback: function(r) { if(!r.exc) { var t=projectTasks.find(function(x){return x.name===taskName;}); if(t) t[fieldName]=value; frappe.show_alert({message:'Updated',indicator:'green'}); } } });
}

function open_date_picker(taskName, fieldName, currentValue) {
    var label = fieldName==='exp_start_date'?'Start Date':'End Date';
    var d = new frappe.ui.Dialog({ title:'Set '+label, fields:[{fieldname:'date_field',fieldtype:'Date',label:label,default:currentValue||''}],
        primary_action_label:'Save', primary_action:function(v) { update_task_field(taskName,fieldName,v.date_field||null); d.hide();
        setTimeout(function(){load_project_tasks(cur_frm);render_task_board(cur_frm);},500); } });
    d.show();
}

// ===== TASK LIST MANAGEMENT =====
window.add_new_task_list = function() {
    var d = new frappe.ui.Dialog({
        title: 'Create New Task List',
        fields: [{fieldname:'list_name',fieldtype:'Data',label:'List Name',reqd:1}],
        primary_action_label: 'Create',
        primary_action: function(v) {
            frappe.call({ method:'frappe.client.insert', args:{doc:{doctype:'Task List',title:v.list_name, project: cur_frm.doc.name}},
                callback: function(r) {
                    if(!r.exc) { d.hide(); frappe.show_alert({message:'List created!',indicator:'green'}); load_task_lists(); render_task_board(cur_frm); }
                } });
        }
    });
    d.show();
};

window.delete_task_list = function(listName) {
    var tasksInList = projectTasks.filter(function(t){return t.custom_task_list===listName;});
    var msg = 'Delete list <b>' + listName + '</b>?';
    if (tasksInList.length > 0) msg += '<br><small style="color:#E53E3E;">' + tasksInList.length + ' task(s) will be moved to Unassigned.</small>';
    frappe.confirm(msg, function() {
        // Unassign tasks from this list first
        var promises = tasksInList.map(function(t) {
            return frappe.xcall('frappe.client.set_value',{doctype:'Task',name:t.name,fieldname:'custom_task_list',value:null});
        });
        Promise.all(promises).then(function() {
            frappe.call({ method:'frappe.client.delete', args:{doctype:'Task List',name:listName},
                callback: function(r) {
                    if(!r.exc) { frappe.show_alert({message:'List deleted',indicator:'orange'}); load_task_lists(); load_project_tasks(cur_frm); render_task_board(cur_frm); }
                } });
        });
    });
};

window.add_task_to_list = function(listName) {
    var d = new frappe.ui.Dialog({
        title: 'Add Task to ' + listName,
        fields: [
            {fieldname:'subject',fieldtype:'Data',label:'Task Name',reqd:1},
            {fieldname:'priority',fieldtype:'Select',label:'Priority',options:'Low\nMedium\nHigh\nUrgent',default:'Medium'},
            {fieldname:'assigned_to',fieldtype:'Link',label:'Assigned To',options:'User',reqd:1},
            {fieldname:'col_break',fieldtype:'Column Break'},
            {fieldname:'exp_start_date',fieldtype:'Date',label:'Start Date'},
            {fieldname:'exp_end_date',fieldtype:'Date',label:'End Date',reqd:1}
        ],
        primary_action_label: 'Create',
        primary_action: function(v) {
            frappe.call({ method:'frappe.client.insert',
                args:{doc:{doctype:'Task',subject:v.subject,project:cur_frm.doc.name,priority:v.priority,custom_task_list:listName,exp_start_date:v.exp_start_date||null,exp_end_date:v.exp_end_date||null,status:'Open'}},
                callback: function(r) { if(!r.exc && r.message && r.message.name) {
                    var task_name = r.message.name;
                    var done = function() { d.hide(); frappe.show_alert({message:'Task added to '+listName,indicator:'green'}); load_project_tasks(cur_frm); render_task_board(cur_frm); };
                    if (v.assigned_to) {
                        frappe.xcall('frappe.desk.form.assign_to.add',{doctype:'Task',name:task_name,assign_to:[v.assigned_to]}).then(done);
                    } else { done(); }
                } }
            });
        }
    });
    d.show();
};

window.add_new_task = function() {
    var tlOpts = '';
    taskLists.forEach(function(tl) { tlOpts += '\n' + tl.name; });
    var d = new frappe.ui.Dialog({
        title: 'Add New Task',
        fields: [
            {fieldname:'subject',fieldtype:'Data',label:'Task Name',reqd:1},
            {fieldname:'priority',fieldtype:'Select',label:'Priority',options:'Low\nMedium\nHigh\nUrgent',default:'Medium'},
            {fieldname:'custom_task_list',fieldtype:'Select',label:'Task List',options:'\n'+tlOpts.trim()},
            {fieldname:'assigned_to',fieldtype:'Link',label:'Assigned To',options:'User',reqd:1},
            {fieldname:'col_break',fieldtype:'Column Break'},
            {fieldname:'exp_start_date',fieldtype:'Date',label:'Start Date'},
            {fieldname:'exp_end_date',fieldtype:'Date',label:'End Date',reqd:1}
        ],
        primary_action_label: 'Create Task',
        primary_action: function(v) {
            frappe.call({ method:'frappe.client.insert',
                args:{doc:{doctype:'Task',subject:v.subject,project:cur_frm.doc.name,priority:v.priority,custom_task_list:v.custom_task_list||null,exp_start_date:v.exp_start_date||null,exp_end_date:v.exp_end_date||null,status:'Open'}},
                callback: function(r) { if(!r.exc && r.message && r.message.name) {
                    var task_name = r.message.name;
                    var done = function() { d.hide(); frappe.show_alert({message:'Task created!',indicator:'green'}); load_project_tasks(cur_frm); render_task_board(cur_frm); };
                    if (v.assigned_to) {
                        frappe.xcall('frappe.desk.form.assign_to.add',{doctype:'Task',name:task_name,assign_to:[v.assigned_to]}).then(done);
                    } else { done(); }
                } }
            });
        }
    });
    d.show();
};

window.refresh_task_board = function() {
    load_task_lists(); load_project_tasks(cur_frm); render_task_board(cur_frm);
    frappe.show_alert({message:'Refreshed',indicator:'blue'});
};

function add_subtask(parentTaskName) {
    var parentTask = projectTasks.find(function(t){return t.name===parentTaskName;});
    var d = new frappe.ui.Dialog({
        title: 'Add Subtask',
        fields: [
            {fieldname:'subject',fieldtype:'Data',label:'Subtask Name',reqd:1},
            {fieldname:'priority',fieldtype:'Select',label:'Priority',options:'Low\nMedium\nHigh\nUrgent',default:'Medium'},
            {fieldname:'assigned_to',fieldtype:'Link',label:'Assigned To',options:'User',reqd:1},
            {fieldname:'col_break',fieldtype:'Column Break'},
            {fieldname:'exp_end_date',fieldtype:'Date',label:'End Date',reqd:1}
        ],
        primary_action_label: 'Create Subtask',
        primary_action: function(v) {
            frappe.call({ method:'frappe.client.set_value', args:{doctype:'Task',name:parentTaskName,fieldname:'is_group',value:1},
                callback: function() {
                    frappe.call({ method:'frappe.client.insert',
                        args:{doc:{doctype:'Task',subject:v.subject,project:cur_frm.doc.name,parent_task:parentTaskName,priority:v.priority,custom_task_list:parentTask?parentTask.custom_task_list:null,exp_end_date:v.exp_end_date||null,status:'Open'}},
                        callback: function(r) { if(!r.exc && r.message && r.message.name) {
                            var task_name = r.message.name;
                            var done = function() { d.hide(); frappe.show_alert({message:'Subtask created!',indicator:'green'}); load_project_tasks(cur_frm); render_task_board(cur_frm); };
                            if (v.assigned_to) {
                                frappe.xcall('frappe.desk.form.assign_to.add',{doctype:'Task',name:task_name,assign_to:[v.assigned_to]}).then(done);
                            } else { done(); }
                        } }
                    });
                } });
        }
    });
    d.show();
}

function delete_task(taskName) {
    frappe.confirm('Delete task <b>'+taskName+'</b>?', function() {
        frappe.call({ method:'frappe.client.delete', args:{doctype:'Task',name:taskName},
            callback: function(r) { if(!r.exc) { frappe.show_alert({message:'Deleted',indicator:'orange'}); load_project_tasks(cur_frm); render_task_board(cur_frm); } } });
    });
}

// ═══════════════════════════════════════════════════════════════════════════════
// WHATSAPP TAB
// ═══════════════════════════════════════════════════════════════════════════════

function load_wa_data(frm) {
    var project = frm.doc.name;
    frappe.call({
        method: 'office_customizations.office_customisation.whatsapp.api.get_project_mappings',
        args: { project: project },
        callback: function(r) {
            projectWaMappings = r.message || [];
            render_wa_numbers_bar();
        }
    });
    frappe.call({
        method: 'office_customizations.office_customisation.whatsapp.api.get_project_messages',
        args: { project: project, limit: 100 },
        callback: function(r) {
            projectWaMessages = r.message || [];
            render_wa_chat_messages();
        }
    });

    // Auto-refresh every 5 seconds while WhatsApp tab is active
    if (typeof waAutoRefreshTimer !== 'undefined' && waAutoRefreshTimer) clearInterval(waAutoRefreshTimer);
    waAutoRefreshTimer = setInterval(function() {
        if (currentTab !== 'WhatsApp') { clearInterval(waAutoRefreshTimer); waAutoRefreshTimer = null; return; }
        frappe.call({
            method: 'office_customizations.office_customisation.whatsapp.api.get_project_messages',
            args: { project: project, limit: 100 },
            async: true,
            callback: function(r) {
                var all = r.message || [];
                var waMsgs = all.filter(function(m) { return !m.source || m.source === 'WhatsApp'; });
                if (waMsgs.length !== projectWaMessages.filter(function(m) { return !m.source || m.source === 'WhatsApp'; }).length) {
                    projectWaMessages = all;
                    render_wa_chat_messages();
                }
            }
        });
    }, 5000);
}

function render_wa_numbers_bar() {
    var html = '';
    if (projectWaMappings.length === 0) {
        html = '<span style="font-size:11px;color:#aaa;font-style:italic;">No numbers linked yet. Click "Manage Numbers" to add.</span>';
    } else {
        projectWaMappings.forEach(function(m) {
            html += '<span style="background:#DCF8C6;color:#128C7E;font-size:11px;padding:3px 10px;border-radius:12px;display:inline-flex;align-items:center;gap:5px;font-weight:500;">';
            html += '&#128222; ' + (m.label || m.phone_number);
            html += ' <span style="color:#999;font-size:10px;">' + m.phone_number + '</span>';
            html += '</span>';
        });
    }
    $('#wa-numbers-bar').html(html);
}


// ═══════════════════════════════════════════════════════════════════════════════
// SHARED: Conversation Timeline Renderer
// ═══════════════════════════════════════════════════════════════════════════════

function render_conversation_timeline(msgs, accentColor, outboundBg) {
    var html = '';
    var lastDate = '';

    msgs.forEach(function(msg) {
        var msgDate = '';
        var msgTime = '';
        if (msg.wa_timestamp) {
            var d = new Date(msg.wa_timestamp);
            var today = new Date();
            var yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
            var dStr = d.toDateString();
            msgDate = dStr === today.toDateString() ? 'Today' : (dStr === yesterday.toDateString() ? 'Yesterday' : d.toLocaleDateString('en-IN', {day:'numeric',month:'short',year:'numeric'}));
            msgTime = d.toLocaleTimeString('en-IN', {hour:'2-digit', minute:'2-digit', hour12:true});
        }
        if (msgDate && msgDate !== lastDate) {
            html += '<div style="background:#F0F0F0;padding:4px 14px;font-size:11px;color:#888;font-weight:600;border-bottom:1px solid #e0e0e0;">' + msgDate + '</div>';
            lastDate = msgDate;
        }

        var isOut = msg.direction === 'Outbound';
        var icon = isOut ? '&#128228;' : '&#128229;';
        var name = msg.contact_name || msg.phone_number || 'Unknown';
        var rowBg = isOut ? outboundBg : '#fff';
        var borderLeft = isOut ? '3px solid ' + accentColor : '3px solid #e0e0e0';

        // Status ticks for outbound
        var statusHtml = '';
        if (isOut) {
            if (msg.status === 'Read') statusHtml = '<span style="color:#53BDEB;margin-left:6px;">&#10003;&#10003;</span>';
            else if (msg.status === 'Delivered') statusHtml = '<span style="color:#aaa;margin-left:6px;">&#10003;&#10003;</span>';
            else if (msg.status === 'Sent') statusHtml = '<span style="color:#aaa;margin-left:6px;">&#10003;</span>';
            else if (msg.status === 'Failed') statusHtml = '<span style="color:#e53e3e;margin-left:6px;">&#10007;</span>';
        }

        // Message content
        var textContent = frappe.utils.escape_html(msg.message_text || '');

        // Media attachment rendering
        var mediaHtml = '';
        var mediaUrl = msg.media_file || '';
        if (msg.message_type === 'image' && mediaUrl) {
            mediaHtml = '<div style="margin-top:4px;"><img src="' + mediaUrl + '" style="max-width:180px;max-height:140px;border-radius:4px;cursor:pointer;border:1px solid #e0e0e0;" onclick="window.open(\'' + mediaUrl + '\',\'_blank\')" loading="lazy"></div>';
            if (textContent === '[Image]') textContent = '';
        } else if (msg.message_type === 'audio' && mediaUrl) {
            mediaHtml = '<div style="margin-top:4px;"><audio controls style="max-width:220px;height:32px;"><source src="' + mediaUrl + '"></audio></div>';
            if (textContent === '[Audio]' || textContent === '[Voice Note]') textContent = '';
        } else if (msg.message_type === 'video' && mediaUrl) {
            mediaHtml = '<div style="margin-top:4px;"><video controls style="max-width:200px;max-height:120px;border-radius:4px;"><source src="' + mediaUrl + '"></video></div>';
            if (textContent === '[Video]' || textContent === '[Video Note]') textContent = '';
        } else if (msg.message_type === 'document' && mediaUrl) {
            var docName = msg.message_text || 'Document';
            mediaHtml = '<div style="margin-top:4px;"><a href="' + mediaUrl + '" target="_blank" style="display:inline-flex;align-items:center;gap:4px;background:#f5f5f5;padding:4px 10px;border-radius:4px;color:#2B6CB0;text-decoration:none;font-size:12px;border:1px solid #e0e0e0;">&#128196; ' + frappe.utils.escape_html(docName) + '</a></div>';
            textContent = '';
        } else if (msg.message_type === 'image') {
            textContent = '&#128247; ' + (textContent || 'Image');
        } else if (msg.message_type === 'audio') {
            textContent = '&#127925; ' + (textContent || 'Audio');
        } else if (msg.message_type === 'video') {
            textContent = '&#127909; ' + (textContent || 'Video');
        } else if (msg.message_type === 'document' && !mediaUrl) {
            textContent = '&#128196; ' + (textContent || 'Document');
        }

        html += '<div style="display:flex;align-items:flex-start;padding:8px 14px;border-bottom:1px solid #f0f0f0;background:' + rowBg + ';border-left:' + borderLeft + ';">';
        html += '<div style="min-width:70px;flex-shrink:0;font-size:11px;color:#999;padding-top:2px;">' + msgTime + '</div>';
        html += '<div style="min-width:20px;flex-shrink:0;font-size:13px;padding-top:1px;">' + icon + '</div>';
        html += '<div style="min-width:130px;max-width:130px;flex-shrink:0;font-size:12px;font-weight:600;color:#333;padding-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="' + frappe.utils.escape_html(name) + '">' + frappe.utils.escape_html(name) + '</div>';
        html += '<div style="flex:1;font-size:13px;color:#444;line-height:1.45;word-wrap:break-word;overflow-wrap:break-word;">';
        if (textContent) html += textContent;
        if (mediaHtml) html += mediaHtml;
        html += '</div>';
        html += '<div style="flex-shrink:0;padding-top:2px;">' + statusHtml + '</div>';
        html += '</div>';
    });

    return html;
}

function render_wa_chat_messages() {
    var msgs = projectWaMessages.filter(function(m) { return !m.source || m.source === 'WhatsApp'; });
    var $area = $('#wa-messages');

    var count = msgs.length;
    $('#wa-msg-count-badge').text(count + ' message' + (count !== 1 ? 's' : ''));
    var $badge = $('#wa-tab-badge');
    if (count > 0) { $badge.text(count).show(); } else { $badge.hide(); }

    if (count === 0) {
        $area.html('<div style="text-align:center;color:#888;font-size:13px;padding:60px 20px;">No messages yet.<br><small>Add a phone number mapping, then messages from that number will appear here.</small></div>');
        return;
    }

    $area.html(render_conversation_timeline(msgs, '#25D366', '#DCF8C6'));
    var el = $area[0];
    if (el) el.scrollTop = el.scrollHeight;
}

window.refresh_wa_chat = function() {
    load_wa_data(cur_frm);
    frappe.show_alert({message: 'WhatsApp refreshed', indicator: 'blue'});
};


window.show_wa_numbers_dialog = function() {
    var project = cur_frm.doc.name;
    var d = new frappe.ui.Dialog({
        title: 'Manage WhatsApp Numbers — ' + project,
        fields: [
            { fieldtype: 'HTML', fieldname: 'current_numbers_html', label: '' },
            { fieldtype: 'Section Break', label: 'Add New Number' },
            { fieldname: 'phone_number', fieldtype: 'Data', label: 'Phone Number', description: 'With country code, no + or spaces. E.g. 919876543210' },
            { fieldname: 'label', fieldtype: 'Data', label: 'Label', description: 'E.g. Arjun Mehta - Client, or PR Products Group Chat' },
        ],
        primary_action_label: 'Add Number',
        primary_action: function(v) {
            if (!v.phone_number) { frappe.show_alert({message:'Enter a phone number',indicator:'orange'}); return; }
            frappe.call({
                method: 'office_customizations.office_customisation.whatsapp.api.add_project_mapping',
                args: { project: project, phone_number: v.phone_number, label: v.label || '' },
                callback: function(r) {
                    if (!r.exc) {
                        frappe.show_alert({message: 'Number added!', indicator: 'green'});
                        d.hide();
                        load_wa_data(cur_frm);
                    }
                }
            });
        }
    });

    // Render current mappings list
    var listHtml = '<div style="margin-bottom:8px;">';
    if (projectWaMappings.length === 0) {
        listHtml += '<p style="color:#aaa;font-size:12px;font-style:italic;">No numbers linked to this project yet.</p>';
    } else {
        projectWaMappings.forEach(function(m) {
            listHtml += '<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0;">';
            listHtml += '<div><span style="font-weight:600;font-size:13px;">&#128222; ' + (m.label || m.phone_number) + '</span> <span style="color:#999;font-size:11px;">' + m.phone_number + '</span></div>';
            listHtml += '<button class="btn btn-xs" style="background:#FFF5F5;color:#E53E3E;border:1px solid #FED7D7;" onclick="remove_wa_mapping(\'' + m.name + '\')">Remove</button>';
            listHtml += '</div>';
        });
    }
    listHtml += '</div>';
    d.fields_dict.current_numbers_html.$wrapper.html(listHtml);
    d.show();
};

// ─── Import Chat Export ───────────────────────────────────────────────────────

window.show_import_chat_dialog = function() {
    var project = cur_frm.doc.name;
    var d = new frappe.ui.Dialog({
        title: '&#128229; Import WhatsApp Chat Export',
        fields: [
            {
                fieldname: 'instructions',
                fieldtype: 'HTML',
                options: '<div style="background:#FFF8E1;border:1px solid #FFE082;border-radius:6px;padding:10px 14px;margin-bottom:4px;font-size:12px;line-height:1.6;">'
                    + '<b>How to export from WhatsApp:</b><br>'
                    + 'Open the group/chat &rarr; <b>&#8942;</b> &rarr; More &rarr; <b>Export Chat</b> &rarr; Without Media<br>'
                    + 'You&rsquo;ll get a <code>.txt</code> file. Open it and paste the full contents below.'
                    + '</div>'
            },
            {
                fieldname: 'group_name',
                fieldtype: 'Data',
                label: 'Group / Chat Name',
                description: 'E.g. "PR Products Team" or "Arjun Mehta" — for your reference only'
            },
            {
                fieldname: 'my_name',
                fieldtype: 'Data',
                label: 'Your WhatsApp Display Name',
                default: 'Raghav',
                description: 'Exactly as it appears in the chat — used to mark your messages as Outbound',
                reqd: 1
            },
            {
                fieldname: 'chat_text',
                fieldtype: 'Code',
                label: 'Paste Chat Export Here',
                reqd: 1,
                description: 'Paste the full .txt content (all lines, no editing needed)'
            }
        ],
        primary_action_label: 'Import Messages',
        primary_action: function(v) {
            if (!v.chat_text || !v.my_name) {
                frappe.show_alert({message: 'Fill in all required fields', indicator: 'orange'});
                return;
            }

            d.hide();
            frappe.show_alert({message: 'Importing... please wait', indicator: 'blue'});

            frappe.call({
                method: 'office_customizations.office_customisation.whatsapp.api.import_chat_export',
                args: {
                    project:    project,
                    chat_text:  v.chat_text,
                    group_name: v.group_name || '',
                    my_name:    v.my_name
                },
                timeout: 60,
                callback: function(r) {
                    if (r.exc) {
                        frappe.show_alert({message: 'Import failed. Check error log.', indicator: 'red'});
                        return;
                    }
                    var s = r.message;
                    var msg = '<b>' + s.imported + ' messages imported</b>';
                    if (s.skipped_duplicate > 0) msg += '<br>' + s.skipped_duplicate + ' duplicates skipped';
                    if (s.skipped_system  > 0) msg += '<br>' + s.skipped_system  + ' system messages skipped';
                    if (s.errors         > 0) msg += '<br><span style="color:#e53e3e;">' + s.errors + ' errors</span>';

                    frappe.msgprint({
                        title: 'Import Complete',
                        message: msg,
                        indicator: s.imported > 0 ? 'green' : 'orange'
                    });

                    if (s.imported > 0) {
                        load_wa_data(cur_frm);
                    }
                }
            });
        }
    });
    d.show();
};

// ═══════════════════════════════════════════════════════════════════════════════
// TELEGRAM TAB — Completely independent from WhatsApp
// ═══════════════════════════════════════════════════════════════════════════════

var projectTgMessages = [];

var waAutoRefreshTimer = null;
var tgAutoRefreshTimer = null;

function load_tg_data(frm) {
    var project = frm.doc.name;
    frappe.call({
        method: 'office_customizations.office_customisation.whatsapp.api.get_telegram_groups',
        args: { project: project },
        callback: function(r) {
            projectTgGroups = r.message || [];
            render_tg_groups_bar();
        }
    });
    frappe.call({
        method: 'office_customizations.office_customisation.whatsapp.api.get_project_messages',
        args: { project: project, limit: 100 },
        callback: function(r) {
            var all = r.message || [];
            projectTgMessages = all.filter(function(m) { return m.source === 'Telegram'; });
            // Sort by timestamp to ensure correct chronological order
            projectTgMessages.sort(function(a, b) {
                return new Date(a.wa_timestamp) - new Date(b.wa_timestamp);
            });
            render_tg_chat_messages();
        }
    });

    // Auto-refresh every 5 seconds while Telegram tab is active
    if (tgAutoRefreshTimer) clearInterval(tgAutoRefreshTimer);
    tgAutoRefreshTimer = setInterval(function() {
        if (currentTab !== 'Telegram') { clearInterval(tgAutoRefreshTimer); tgAutoRefreshTimer = null; return; }
        frappe.call({
            method: 'office_customizations.office_customisation.whatsapp.api.get_project_messages',
            args: { project: project, limit: 100 },
            async: true,
            callback: function(r) {
                var all = r.message || [];
                var tgMsgs = all.filter(function(m) { return m.source === 'Telegram'; });
                if (tgMsgs.length !== projectTgMessages.length) {
                    projectTgMessages = tgMsgs;
                    projectTgMessages.sort(function(a, b) {
                        return new Date(a.wa_timestamp) - new Date(b.wa_timestamp);
                    });
                    render_tg_chat_messages();
                }
            }
        });
    }, 5000);
}

function render_tg_groups_bar() {
    var html = '';
    if (projectTgGroups.length === 0) {
        html = '<span style="font-size:11px;color:#aaa;font-style:italic;">No Telegram groups linked. Click "Manage Groups" to add.</span>';
    } else {
        projectTgGroups.forEach(function(g) {
            html += '<span style="background:#D4EDFF;color:#0088cc;font-size:11px;padding:3px 10px;border-radius:12px;display:inline-flex;align-items:center;gap:5px;font-weight:500;">';
            html += '&#9992; ' + (g.group_name || g.tg_chat_id);
            html += '</span>';
        });
    }
    $('#tg-groups-bar').html(html);
}


function render_tg_chat_messages() {
    var msgs = projectTgMessages;
    var $area = $('#tg-messages');

    var count = msgs.length;
    $('#tg-msg-count-badge').text(count + ' message' + (count !== 1 ? 's' : ''));
    var $badge = $('#tg-tab-badge');
    if (count > 0) { $badge.text(count).show(); } else { $badge.hide(); }

    if (count === 0) {
        $area.html('<div style="text-align:center;color:#888;font-size:13px;padding:60px 20px;">No Telegram messages yet.<br><small>Add a Telegram chat mapping, then messages will appear here.</small></div>');
        return;
    }

    $area.html(render_conversation_timeline(msgs, '#0088cc', '#D4EDFF'));
    var el = $area[0];
    if (el) el.scrollTop = el.scrollHeight;
}

window.refresh_tg_chat = function() {
    load_tg_data(cur_frm);
    frappe.show_alert({message: 'Telegram refreshed', indicator: 'blue'});
};


// ═══════════════════════════════════════════════════════════════════════════════
// SEND TO CLIENT — Dialogs for WhatsApp and Telegram
// ═══════════════════════════════════════════════════════════════════════════════

window.show_wa_send_dialog = function() {
    var project = cur_frm.doc.name;
    var recipientOptions = projectWaMappings.map(function(m) {
        return { label: (m.label || m.phone_number) + ' (' + m.phone_number + ')', value: m.phone_number };
    });
    if (recipientOptions.length === 0) {
        frappe.show_alert({message: 'No WhatsApp numbers mapped. Click "Manage Numbers" first.', indicator: 'orange'});
        return;
    }

    var d = new frappe.ui.Dialog({
        title: '&#128228; Send to Client via WhatsApp',
        fields: [
            { fieldname: 'recipient', fieldtype: 'Select', label: 'Recipient', reqd: 1,
              options: recipientOptions.map(function(o) { return o.value; }).join('\n'),
              description: recipientOptions.map(function(o) { return o.value + ' = ' + o.label; }).join('<br>')
            },
            { fieldtype: 'Section Break', label: 'Message' },
            { fieldname: 'message', fieldtype: 'Small Text', label: 'Message text (optional)' },
            { fieldtype: 'Section Break', label: 'Attachment (optional)' },
            { fieldname: 'link_url', fieldtype: 'Data', label: 'Paste a link',
              description: 'Google Sheet, OneDrive, or any URL \u2014 will be sent as text' },
            { fieldname: 'attach_file', fieldtype: 'Attach', label: 'Or upload a file',
              description: 'PDF, Excel, image, or any file' },
        ],
        size: 'large',
        primary_action_label: 'Send',
        primary_action: function(v) {
            var fullMsg = (v.message || '').trim();
            if (v.link_url) {
                fullMsg = fullMsg ? fullMsg + '\n\n' + v.link_url : v.link_url;
            }
            if (!fullMsg && !v.attach_file) {
                frappe.show_alert({message: 'Add a message, link, or file to send', indicator: 'orange'});
                return;
            }

            d.hide();
            frappe.show_alert({message: 'Sending...', indicator: 'blue'});

            if (fullMsg) {
                frappe.call({
                    method: 'office_customizations.office_customisation.whatsapp.api.send_message',
                    args: { phone: v.recipient, message: fullMsg, project: project },
                    callback: function(r) {
                        if (!r.exc) frappe.show_alert({message: 'Message sent via WhatsApp!', indicator: 'green'});
                        load_wa_data(cur_frm);
                    }
                });
            }
            // File attachment sending would require Meta Cloud API media upload
            // For now, show the file was uploaded to ERPNext
            if (v.attach_file) {
                frappe.show_alert({message: 'File uploaded. WhatsApp media sending requires Meta API setup.', indicator: 'orange'});
            }
        }
    });
    if (recipientOptions.length === 1) {
        d.set_value('recipient', recipientOptions[0].value);
    }
    d.show();
};

window.show_tg_send_dialog = function() {
    var project = cur_frm.doc.name;
    if (projectTgGroups.length === 0) {
        frappe.show_alert({message: 'No Telegram chats mapped. Click "Manage Chats" first.', indicator: 'orange'});
        return;
    }

    var d = new frappe.ui.Dialog({
        title: '&#128228; Send to Client via Telegram',
        fields: [
            { fieldname: 'recipient', fieldtype: 'Select', label: 'Recipient', reqd: 1,
              options: projectTgGroups.map(function(g) { return g.tg_chat_id; }).join('\n'),
              description: projectTgGroups.map(function(g) { return g.tg_chat_id + ' = ' + (g.group_name || 'Chat'); }).join('<br>')
            },
            { fieldtype: 'Section Break', label: 'Message' },
            { fieldname: 'message', fieldtype: 'Small Text', label: 'Message text (optional)' },
            { fieldtype: 'Section Break', label: 'Attachment (optional)' },
            { fieldname: 'link_url', fieldtype: 'Data', label: 'Paste a link',
              description: 'Google Sheet, OneDrive, or any URL \u2014 will be sent as text' },
            { fieldname: 'attach_file', fieldtype: 'Attach', label: 'Or upload a file',
              description: 'PDF, Excel, image, or any file \u2014 sent directly to Telegram' },
        ],
        size: 'large',
        primary_action_label: 'Send',
        primary_action: function(v) {
            var fullMsg = (v.message || '').trim();
            if (v.link_url) {
                fullMsg = fullMsg ? fullMsg + '\n\n' + v.link_url : v.link_url;
            }
            if (!fullMsg && !v.attach_file) {
                frappe.show_alert({message: 'Add a message, link, or file to send', indicator: 'orange'});
                return;
            }

            d.hide();
            frappe.show_alert({message: 'Sending...', indicator: 'blue'});

            // Send text/link message
            if (fullMsg) {
                frappe.call({
                    method: 'office_customizations.office_customisation.whatsapp.api.send_telegram_message',
                    args: { tg_chat_id: v.recipient, message: fullMsg, project: project },
                    callback: function(r) {
                        if (!r.exc) frappe.show_alert({message: 'Message sent via Telegram!', indicator: 'green'});
                        load_tg_data(cur_frm);
                    }
                });
            }

            // Send file attachment
            if (v.attach_file) {
                var mediaType = 'document';
                var lower = v.attach_file.toLowerCase();
                if (lower.match(/\.(jpg|jpeg|png|gif|webp)$/)) mediaType = 'image';
                else if (lower.match(/\.(mp4|mov|avi)$/)) mediaType = 'video';
                else if (lower.match(/\.(mp3|ogg|wav)$/)) mediaType = 'audio';

                frappe.call({
                    method: 'office_customizations.office_customisation.whatsapp.api.send_telegram_media',
                    args: { tg_chat_id: v.recipient, file_url: v.attach_file, media_type: mediaType, caption: v.message || '', project: project },
                    callback: function(r) {
                        if (!r.exc) frappe.show_alert({message: 'File sent via Telegram!', indicator: 'green'});
                        load_tg_data(cur_frm);
                    }
                });
            }
        }
    });
    if (projectTgGroups.length === 1) {
        d.set_value('recipient', projectTgGroups[0].tg_chat_id);
    }
    d.show();
};

window.remove_wa_mapping = function(name) {
    frappe.call({
        method: 'office_customizations.office_customisation.whatsapp.api.delete_project_mapping',
        args: { name: name },
        callback: function(r) {
            if (!r.exc) {
                frappe.show_alert({message: 'Removed', indicator: 'orange'});
                load_wa_data(cur_frm);
                // Close dialog if open
                if (frappe.ui.Dialog._active_dialog) frappe.ui.Dialog._active_dialog.hide();
            }
        }
    });
};

// ─── Telegram Group Management ────────────────────────────────────────────────

window.show_tg_groups_dialog = function() {
    var project = cur_frm.doc.name;
    var d = new frappe.ui.Dialog({
        title: 'Manage Telegram Chats \u2014 ' + project,
        fields: [
            { fieldtype: 'HTML', fieldname: 'current_groups_html', label: '' },
            { fieldtype: 'Section Break', label: 'Add Telegram Chat' },
            { fieldname: 'tg_chat_id', fieldtype: 'Data', label: 'Telegram Chat ID', description: 'Send /chatid to the bot in any chat (group or individual) to get the ID' },
            { fieldname: 'group_name', fieldtype: 'Data', label: 'Chat Name', description: 'E.g. "PR Products Team" (group) or "Arjun Mehta" (individual)' },
        ],
        primary_action_label: 'Add Chat',
        primary_action: function(v) {
            if (!v.tg_chat_id) { frappe.show_alert({message:'Enter a Telegram Chat ID',indicator:'orange'}); return; }
            frappe.call({
                method: 'office_customizations.office_customisation.whatsapp.api.add_telegram_group_mapping',
                args: { project: project, tg_chat_id: v.tg_chat_id, group_name: v.group_name || '' },
                callback: function(r) {
                    if (!r.exc) {
                        frappe.show_alert({message: 'Telegram chat added!', indicator: 'green'});
                        d.hide();
                        load_tg_data(cur_frm);
                    }
                }
            });
        }
    });

    var listHtml = '<div style="margin-bottom:8px;">';
    if (projectTgGroups.length === 0) {
        listHtml += '<p style="color:#aaa;font-size:12px;font-style:italic;">No Telegram chats linked to this project yet.</p>';
    } else {
        projectTgGroups.forEach(function(g) {
            var icon = String(g.tg_chat_id).startsWith('-') ? '&#128101;' : '&#128100;';
            listHtml += '<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0;">';
            listHtml += '<div><span style="font-weight:600;font-size:13px;">' + icon + ' ' + (g.group_name || g.tg_chat_id) + '</span> <span style="color:#999;font-size:11px;">ID: ' + g.tg_chat_id + '</span></div>';
            listHtml += '<button class="btn btn-xs" style="background:#FFF5F5;color:#E53E3E;border:1px solid #FED7D7;" onclick="remove_tg_group(\'' + g.name + '\')">Remove</button>';
            listHtml += '</div>';
        });
    }
    listHtml += '</div>';
    d.fields_dict.current_groups_html.$wrapper.html(listHtml);
    d.show();
};

window.remove_tg_group = function(name) {
    frappe.call({
        method: 'office_customizations.office_customisation.whatsapp.api.delete_telegram_group_mapping',
        args: { name: name },
        callback: function(r) {
            if (!r.exc) {
                frappe.show_alert({message: 'Removed', indicator: 'orange'});
                load_wa_data(cur_frm);
                if (frappe.ui.Dialog._active_dialog) frappe.ui.Dialog._active_dialog.hide();
            }
        }
    });
};
