"""
UI polish for /my-tasks:
  - Coloured status & priority pills (background + text)
  - Completed rows: green tint + strikethrough + dimmed
  - Tighter row padding (6px → 4px)
  - Smaller font sizes for mobile
  - Project header more prominent (gradient + left border)
  - Mobile media query hides Start Date + Progress columns

Done purely via main_section_html injection (CSS + a tiny MutationObserver
that sets data-* attrs the CSS can match). No edits to the existing JS logic.

Idempotent.
"""

import frappe


SENTINEL = "/* mtd_ui_polish_v2 */"

INJECTED_HTML = """<div id="my-tasks-dashboard"></div>
<style>/* mtd_ui_polish_v2 */
/* Tighter rows everywhere */
#my-tasks-dashboard .mtd-task-table td { padding: 3px 6px !important; vertical-align: middle; }
#my-tasks-dashboard .mtd-task-table th { padding: 3px 6px !important; font-size: 9px !important; letter-spacing: 0.4px; }

/* Task name ALWAYS single line with ellipsis (never wraps) */
#my-tasks-dashboard .mtd-task-table td:nth-child(2) {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 0; /* lets the column shrink */
}
#my-tasks-dashboard .mtd-task-link {
    font-size: 12px !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    display: inline-block;
    max-width: 100%;
    vertical-align: middle;
}

/* Assignee chip on Delegated: smaller, less visually heavy */
#my-tasks-dashboard .mtd-assignee-tag {
    font-size: 10px !important;
    padding: 1px 5px !important;
    background: #EBF8FF !important;
    color: #2C5282 !important;
    border-radius: 8px !important;
    margin-left: 4px !important;
    vertical-align: middle;
}

/* Hide Start Date column ALWAYS — it's barely used and adds noise */
#my-tasks-dashboard .mtd-task-table th:nth-child(5),
#my-tasks-dashboard .mtd-task-table td:nth-child(5),
#my-tasks-dashboard .mtd-task-table colgroup col:nth-child(5) { display: none !important; }

/* Project header: gradient + left accent */
#my-tasks-dashboard .mtd-project-card { margin-bottom: 6px !important; border: 1px solid #E2E8F0; border-radius: 6px; overflow: hidden; }
#my-tasks-dashboard .mtd-project-header { padding: 6px 12px !important; background: linear-gradient(to right, #EBF8FF, #F7FAFC) !important; border-left: 3px solid #2490EF; cursor: pointer; }
#my-tasks-dashboard .mtd-project-name { font-size: 12px !important; font-weight: 700 !important; color: #2B6CB0 !important; }

/* Status & priority — compact pills with no dropdown arrow */
#my-tasks-dashboard .mtd-status-select,
#my-tasks-dashboard .mtd-priority-select {
    border: none !important;
    padding: 2px 8px !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 10px !important;
    -webkit-appearance: none !important;
    -moz-appearance: none !important;
    appearance: none !important;
    background-image: none !important;
    cursor: pointer;
}
#my-tasks-dashboard .mtd-status-select { min-width: 50px !important; max-width: 75px !important; }
#my-tasks-dashboard .mtd-priority-select { min-width: 38px !important; max-width: 60px !important; }
/* Status colours */
#my-tasks-dashboard .mtd-status-select[data-status="Open"]            { background: #BEE3F8 !important; color: #1A365D !important; }
#my-tasks-dashboard .mtd-status-select[data-status="Working"]         { background: #FAF089 !important; color: #5F370E !important; }
#my-tasks-dashboard .mtd-status-select[data-status="Pending Review"]  { background: #D6BCFA !important; color: #44337A !important; }
#my-tasks-dashboard .mtd-status-select[data-status="Completed"]       { background: #9AE6B4 !important; color: #1C4532 !important; }
#my-tasks-dashboard .mtd-status-select[data-status="Cancelled"]       { background: #E2E8F0 !important; color: #4A5568 !important; }
/* Priority colours */
#my-tasks-dashboard .mtd-priority-select[data-priority="Low"]    { background: #9AE6B4 !important; color: #1C4532 !important; }
#my-tasks-dashboard .mtd-priority-select[data-priority="Medium"] { background: #FAF089 !important; color: #5F370E !important; }
#my-tasks-dashboard .mtd-priority-select[data-priority="High"]   { background: #FEB2B2 !important; color: #63171B !important; }
#my-tasks-dashboard .mtd-priority-select[data-priority="Urgent"] { background: #C53030 !important; color: #fff !important; }

/* Completed row treatment */
#my-tasks-dashboard tr[data-mtd-status="Completed"] td { background: rgba(56, 161, 105, 0.05); }
#my-tasks-dashboard tr[data-mtd-status="Completed"] .mtd-task-link { color: #38A169 !important; text-decoration: line-through; opacity: 0.7; }
/* Don't show overdue red on dates of completed tasks */
#my-tasks-dashboard tr[data-mtd-status="Completed"] .mtd-relative-due,
#my-tasks-dashboard tr[data-mtd-status="Completed"] .mtd-abs-date { color: #38A169 !important; opacity: 0.6; }

/* Overdue subtle highlight */
#my-tasks-dashboard tr[data-mtd-overdue="1"] td { background: rgba(229, 62, 62, 0.03); }

/* Date column */
#my-tasks-dashboard .mtd-task-table td:nth-child(6) { font-size: 11px; line-height: 1.3; }

/* Filter / chip bar tighter */
#my-tasks-dashboard .mtd-date-chip { padding: 3px 10px !important; font-size: 11px !important; }
#my-tasks-dashboard .mtd-filter-bar { gap: 4px !important; padding: 6px 0 !important; }
#my-tasks-dashboard .mtd-filter-bar select { padding: 3px 6px !important; font-size: 11px !important; }

/* Mobile: multi-row card showing EVERY field from the desktop view, just stacked */
@media (max-width: 768px) {
    #my-tasks-dashboard .mtd-task-table thead { display: none !important; }
    #my-tasks-dashboard .mtd-task-table colgroup { display: none !important; }
    #my-tasks-dashboard .mtd-task-table { display: block !important; width: 100%; border-collapse: collapse; }
    #my-tasks-dashboard .mtd-task-table tbody { display: block !important; width: 100%; }

    /* Each main row = wrapping flex card */
    #my-tasks-dashboard .mtd-task-table tr:not(.mtd-updates-row):not(.mtd-timelog-row):not(.mtd-comments-row) {
        display: flex !important;
        flex-wrap: wrap !important;
        align-items: center !important;
        gap: 5px 8px !important;
        padding: 9px 12px !important;
        border-bottom: 1px solid #E2E8F0 !important;
        background: #fff !important;
        width: 100% !important;
    }
    /* Aux rows hidden until page toggles open */
    #my-tasks-dashboard .mtd-task-table tr.mtd-updates-row,
    #my-tasks-dashboard .mtd-task-table tr.mtd-timelog-row,
    #my-tasks-dashboard .mtd-task-table tr.mtd-comments-row { display: none !important; }
    #my-tasks-dashboard .mtd-task-table tr.mtd-updates-row.open,
    #my-tasks-dashboard .mtd-task-table tr.mtd-timelog-row.open,
    #my-tasks-dashboard .mtd-task-table tr.mtd-comments-row.open { display: block !important; }

    /* Reset td default styling */
    #my-tasks-dashboard .mtd-task-table td {
        padding: 0 !important;
        border: none !important;
        flex: 0 0 auto;
    }
    /* Hide left-border accent only (everything else stays) */
    #my-tasks-dashboard .mtd-task-table td:nth-child(1) { display: none !important; }

    /* ── Row 1: Task name (full width, with subtask arrow + assignee on its own line) ── */
    #my-tasks-dashboard .mtd-task-table td:nth-child(2) {
        order: 1 !important;
        flex: 1 0 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        font-size: 13px !important;
        font-weight: 500;
        overflow: hidden;
    }
    /* Subtask arrow more visible */
    #my-tasks-dashboard .mtd-task-table td:nth-child(2) > span:first-child {
        display: inline-block !important;
        font-size: 12px !important;
        color: #2B6CB0 !important;
        font-weight: 700;
        margin-right: 4px;
    }
    /* Task link: inline with arrow, single-line ellipsis on the link itself */
    #my-tasks-dashboard .mtd-task-link {
        display: inline-block !important;
        max-width: calc(100% - 28px) !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        white-space: nowrap !important;
        vertical-align: middle !important;
        color: #2D3748 !important;
        font-size: 13px !important;
        font-weight: 500;
    }
    /* Assignee chip: own row below task name, prominent */
    #my-tasks-dashboard .mtd-assignee-tag {
        display: block !important;
        margin: 4px 0 0 0 !important;
        font-size: 11px !important;
        padding: 2px 8px !important;
        background: #EDF2F7 !important;
        color: #2D3748 !important;
        border-radius: 10px !important;
        width: fit-content;
    }

    /* ── Row 2: Status, Priority, dates, progress, actions ── */
    #my-tasks-dashboard .mtd-task-table td:nth-child(3) { order: 2 !important; flex: 0 0 auto !important; }
    #my-tasks-dashboard .mtd-task-table td:nth-child(4) { order: 3 !important; flex: 0 0 auto !important; }
    /* Start date — show inline with end date as small */
    #my-tasks-dashboard .mtd-task-table td:nth-child(5) {
        order: 4 !important;
        font-size: 10px !important;
        color: #718096 !important;
        display: block !important;
    }
    #my-tasks-dashboard .mtd-task-table td:nth-child(5)::before { content: "Start: "; color: #A0AEC0; }
    /* End date + relative due */
    #my-tasks-dashboard .mtd-task-table td:nth-child(6) {
        order: 5 !important;
        flex: 1 1 auto !important;
        text-align: right;
        font-size: 11px !important;
        line-height: 1.2;
        color: #4A5568;
        white-space: nowrap;
        font-weight: 600;
    }
    #my-tasks-dashboard .mtd-task-table td:nth-child(6) .mtd-abs-date { display: inline !important; font-size: 10px !important; color: #718096; font-weight: 500; }
    #my-tasks-dashboard .mtd-task-table td:nth-child(6) .mtd-abs-date::after { content: " · "; color: #CBD5E0; }
    #my-tasks-dashboard tr[data-mtd-overdue="1"] .mtd-relative-due { color: #C53030 !important; }
    #my-tasks-dashboard tr[data-mtd-status="Completed"] .mtd-relative-due,
    #my-tasks-dashboard tr[data-mtd-status="Completed"] .mtd-abs-date { color: #38A169 !important; opacity: 0.7; }
    /* Progress bar — own row, full width */
    #my-tasks-dashboard .mtd-task-table td:nth-child(7) {
        order: 6 !important;
        flex: 1 0 60% !important;
        font-size: 10px !important;
        color: #718096 !important;
    }
    /* Actions */
    #my-tasks-dashboard .mtd-task-table td:nth-child(8) { order: 7 !important; flex: 0 0 auto !important; text-align: right; }
    #my-tasks-dashboard .mtd-task-link {
        font-size: 13px !important;
        font-weight: 500;
        line-height: 1.3;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        display: block;          /* fill container, not inline */
        width: 100%;
    }

    /* Status / priority pills tight */
    #my-tasks-dashboard .mtd-status-select { min-width: 70px !important; max-width: 110px !important; font-size: 10px !important; padding: 3px 6px !important; }
    #my-tasks-dashboard .mtd-priority-select { min-width: 55px !important; max-width: 85px !important; font-size: 10px !important; padding: 3px 6px !important; }

    /* Date column: small text, right-aligned, just "Due in X days" line dominant */
    #my-tasks-dashboard .mtd-task-table td:nth-child(6) {
        font-size: 10px !important;
        line-height: 1.2;
        color: #4A5568;
    }

    /* Actions: compact icon row, right-aligned */
    #my-tasks-dashboard .mtd-task-table td:nth-child(8) > * {
        padding: 3px 5px !important;
        font-size: 12px !important;
        margin-left: 2px !important;
    }

    /* Assignee chip in Delegated tab — tight */
    #my-tasks-dashboard .mtd-assignee-tag {
        font-size: 10px !important;
        padding: 1px 5px !important;
        margin-left: 4px !important;
    }

    /* Project header sticky look */
    #my-tasks-dashboard .mtd-project-name { font-size: 12px !important; }
    /* Filter dropdowns wrap */
    #my-tasks-dashboard .mtd-filter-bar { flex-wrap: wrap !important; }
    /* Tabs compact */
    #my-tasks-dashboard .mtd-view-tab { padding: 6px 4px !important; font-size: 11px !important; }
}

/* Very narrow phones */
@media (max-width: 420px) {
    #my-tasks-dashboard .mtd-task-table tr { padding: 6px 8px; gap: 3px 4px; }
    #my-tasks-dashboard .mtd-task-link { font-size: 12px !important; }
    #my-tasks-dashboard .mtd-status-select { min-width: 60px !important; max-width: 90px !important; font-size: 9px !important; }
    #my-tasks-dashboard .mtd-priority-select { min-width: 48px !important; max-width: 70px !important; font-size: 9px !important; }
    #my-tasks-dashboard .mtd-task-table td:nth-child(6) { font-size: 9px !important; }
}
</style>
<script>/* mtd_ui_polish_v1 */
(function(){
    function stripProjectSuffix(dash) {
        // Collect all visible project-header names so we can strip them from task titles
        var pnames = [];
        dash.querySelectorAll('.mtd-project-name').forEach(function(el){
            var t = el.textContent.trim();
            if (t) pnames.push(t);
        });
        if (!pnames.length) return;
        // Sort longest-first so "Test1 Pvt Ltd" wins over "Test1"
        pnames.sort(function(a,b){ return b.length - a.length; });

        dash.querySelectorAll('.mtd-task-link').forEach(function(link){
            if (link.dataset.mtdSuffixStripped === '1') return;
            var orig = link.textContent;
            var t = orig;
            for (var i = 0; i < pnames.length; i++) {
                var p = pnames[i];
                var s1 = ' — ' + p;  // em-dash
                var s2 = ' - ' + p;
                if (t.length > s1.length && t.slice(-s1.length) === s1) {
                    t = t.slice(0, -s1.length); break;
                }
                if (t.length > s2.length && t.slice(-s2.length) === s2) {
                    t = t.slice(0, -s2.length); break;
                }
            }
            if (t !== orig) {
                link.textContent = t;
                link.title = orig; // keep full name as hover tooltip
            }
            link.dataset.mtdSuffixStripped = '1';
        });
    }

    var STATUS_ABBR = { "Open":"Open", "Working":"WIP", "Pending Review":"PR", "Completed":"Done", "Cancelled":"Cxl", "Overdue":"Ovd" };
    var PRIO_ABBR   = { "Low":"Lo", "Medium":"Med", "High":"Hi", "Urgent":"Urg" };

    function abbreviateOptions(dash) {
        dash.querySelectorAll('.mtd-status-select option').forEach(function(o){
            var v = o.getAttribute('value');
            if (STATUS_ABBR[v] && o.textContent !== STATUS_ABBR[v]) o.textContent = STATUS_ABBR[v];
        });
        dash.querySelectorAll('.mtd-priority-select option').forEach(function(o){
            var v = o.getAttribute('value');
            if (PRIO_ABBR[v] && o.textContent !== PRIO_ABBR[v]) o.textContent = PRIO_ABBR[v];
        });
    }

    function abbreviateDates(dash) {
        // End-date cell is the 6th td. Walk text nodes:
        //   1) Wrap the absolute date text in a span (so CSS can hide on mobile)
        //   2) Rewrite "X days overdue" → "X D.O." etc.
        dash.querySelectorAll('.mtd-task-table tbody tr td:nth-child(6)').forEach(function(td){
            // Wrap any direct text-node child into a span.mtd-abs-date
            var children = Array.from(td.childNodes);
            children.forEach(function(n){
                if (n.nodeType === Node.TEXT_NODE && n.textContent.trim()) {
                    var span = document.createElement('span');
                    span.className = 'mtd-abs-date';
                    span.textContent = n.textContent;
                    n.parentNode.replaceChild(span, n);
                }
            });
            // Now abbreviate the relative-due span text
            var walker = document.createTreeWalker(td, NodeFilter.SHOW_TEXT, null);
            var nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
            nodes.forEach(function(n){
                var t = n.textContent;
                if (!t) return;
                var nt = t
                    .replace(/(\d+)\s+days?\s+overdue/i, '$1 D.O.')
                    .replace(/Due in (\d+)\s+days?/i, '$1 D.L.')
                    .replace(/Due in (\d+)\s+months?/i, '$1mo')
                    .replace(/Due today/i, 'Today')
                    .replace(/Due tomorrow/i, 'Tom.');
                if (nt !== t) n.textContent = nt;
            });
        });
    }

    function decorate() {
        var dash = document.getElementById('my-tasks-dashboard');
        if (!dash) return;
        dash.querySelectorAll('.mtd-status-select').forEach(function(s){
            s.setAttribute('data-status', s.value);
            var tr = s.closest('tr');
            if (tr) {
                tr.setAttribute('data-mtd-status', s.value);
                var endTd = tr.querySelector('td:nth-child(6)');
                var hasOverdue = endTd && endTd.textContent && /(overdue|D\.O\.)/i.test(endTd.textContent);
                if (hasOverdue && s.value !== 'Completed') tr.setAttribute('data-mtd-overdue', '1');
                else tr.removeAttribute('data-mtd-overdue');
            }
        });
        dash.querySelectorAll('.mtd-priority-select').forEach(function(s){
            s.setAttribute('data-priority', s.value);
        });
        stripProjectSuffix(dash);
        abbreviateOptions(dash);
        abbreviateDates(dash);
    }
    document.addEventListener('change', function(e){
        if (e.target && e.target.classList && (e.target.classList.contains('mtd-status-select') || e.target.classList.contains('mtd-priority-select'))) {
            setTimeout(decorate, 60);
        }
    });
    function startObserver() {
        var dash = document.getElementById('my-tasks-dashboard');
        if (!dash) { setTimeout(startObserver, 500); return; }
        var obs = new MutationObserver(function(){ setTimeout(decorate, 30); });
        obs.observe(dash, {childList: true, subtree: true});
        decorate();
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', startObserver);
    } else {
        startObserver();
    }
})();
</script>"""


def run():
    doc = frappe.get_doc("Web Page", "my-tasks")

    # Always overwrite (so re-runs of the patch update the CSS)
    doc.main_section_html = INJECTED_HTML
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    print("UI polish v1 applied to my-tasks main_section_html.")
