"""
/my-tasks — Variant B styling.

Replaces the over-condensed polish v1 patch:
  - DROPS: status/priority option abbreviations, date abbreviations,
           project-suffix stripping, hidden Start Date column.
  - KEEPS: coloured status & priority pills, completed-row treatment,
           project header gradient, tighter row padding.
  - ADDS:  Hides Progress column (col 7).
  - ADDS:  Variant B chat-bubble drawer styling for the existing
           click-💬 → expand thread drawer (.mtd-updates-row /
           .mtd-up-* classes already wired up by the page JS).
  - ADDS:  Tiny JS that injects coloured initial-avatars into each
           comment row (matches v2 mockup).

Idempotent. Safe to re-run.
"""

import frappe


SENTINEL = "/* mtd_variant_b_v1 */"

INJECTED_HTML = """<div id="my-tasks-dashboard"></div>
<style>/* mtd_variant_b_v1 */
/* ─── Mobile preview frame: hard-clip horizontal overflow ─── */
#mobile-preview-frame { overflow-x: hidden !important; }
#mobile-preview-frame .navbar,
#mobile-preview-frame .container,
#mobile-preview-frame .web-footer,
#mobile-preview-frame .page_content { max-width: 100% !important; box-sizing: border-box !important; }
/* Make sure no inner block escapes the frame */
#mobile-preview-frame #my-tasks-dashboard,
#mobile-preview-frame .mtd-task-table,
#mobile-preview-frame .mtd-project-card { max-width: 100% !important; box-sizing: border-box; }

/* ─── Tighter rows ─── */
#my-tasks-dashboard .mtd-task-table td { padding: 4px 8px !important; vertical-align: middle; }
#my-tasks-dashboard .mtd-task-table th { padding: 4px 8px !important; font-size: 10px !important; letter-spacing: 0.4px; }

/* ─── Task name single-line ellipsis ─── */
#my-tasks-dashboard .mtd-task-table td:nth-child(2) {
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 0;
}
#my-tasks-dashboard .mtd-task-link {
    font-size: 13px !important; white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis; display: inline-block; max-width: 100%; vertical-align: middle;
}

/* ─── Hide Progress column (col 7) — user said progress bars aren't useful ─── */
#my-tasks-dashboard .mtd-task-table th:nth-child(7),
#my-tasks-dashboard .mtd-task-table td:nth-child(7),
#my-tasks-dashboard .mtd-task-table colgroup col:nth-child(7) { display: none !important; }
/* Also hide progress bars if rendered in mobile cards */
#my-tasks-dashboard .mtd-progress-click,
#my-tasks-dashboard .mtd-progress-bar-wrap,
#my-tasks-dashboard .mtd-progress-pct { display: none !important; }

/* ─── Project header: gradient + accent ─── */
#my-tasks-dashboard .mtd-project-card { margin-bottom: 8px !important; border: 1px solid #E2E8F0; border-radius: 6px; overflow: hidden; }
#my-tasks-dashboard .mtd-project-header {
    padding: 8px 14px !important;
    background: linear-gradient(to right, #EBF8FF, #F7FAFC) !important;
    border-left: 3px solid #2490EF; cursor: pointer;
}
#my-tasks-dashboard .mtd-project-name { font-size: 13px !important; font-weight: 700 !important; color: #2B6CB0 !important; }

/* ─── Status & priority pills (compact, rounded, no native arrow) ─── */
#my-tasks-dashboard .mtd-status-select,
#my-tasks-dashboard .mtd-priority-select {
    border: none !important;
    padding: 2px 9px !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 11px !important;
    -webkit-appearance: none !important;
    -moz-appearance: none !important;
    appearance: none !important;
    background-image: none !important;
    cursor: pointer;
}
#my-tasks-dashboard .mtd-status-select   { min-width: 78px !important; }
#my-tasks-dashboard .mtd-priority-select { min-width: 64px !important; }
#my-tasks-dashboard .mtd-status-select[data-status="Open"]            { background: #BEE3F8 !important; color: #1A365D !important; }
#my-tasks-dashboard .mtd-status-select[data-status="Working"]         { background: #FAF089 !important; color: #5F370E !important; }
#my-tasks-dashboard .mtd-status-select[data-status="Pending Review"]  { background: #D6BCFA !important; color: #44337A !important; }
#my-tasks-dashboard .mtd-status-select[data-status="Completed"]       { background: #9AE6B4 !important; color: #1C4532 !important; }
#my-tasks-dashboard .mtd-status-select[data-status="Cancelled"]       { background: #E2E8F0 !important; color: #4A5568 !important; }
#my-tasks-dashboard .mtd-priority-select[data-priority="Low"]    { background: #9AE6B4 !important; color: #1C4532 !important; }
#my-tasks-dashboard .mtd-priority-select[data-priority="Medium"] { background: #FAF089 !important; color: #5F370E !important; }
#my-tasks-dashboard .mtd-priority-select[data-priority="High"]   { background: #FEB2B2 !important; color: #63171B !important; }
#my-tasks-dashboard .mtd-priority-select[data-priority="Urgent"] { background: #C53030 !important; color: #fff !important; }

/* ─── Assignee chip (Delegated tab): on desktop allow chip to be visible
       even when name td has overflow:hidden by relaxing whitespace inside ─── */
#my-tasks-dashboard .mtd-assignee-tag {
    display: inline-block !important;
    background: #EBF8FF !important;
    color: #2B6CB0 !important;
    padding: 2px 8px !important;
    border-radius: 10px !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    white-space: nowrap;
    margin-left: 6px !important;
    vertical-align: middle;
}

/* ─── Subtask row treatment (desktop) ─── */
#my-tasks-dashboard .mtd-task-table tr[data-mtd-subtask="1"] td:nth-child(2) > span:first-child {
    color: #2B6CB0 !important; font-weight: 700 !important; font-size: 13px !important;
    margin-right: 6px !important;
}
#my-tasks-dashboard .mtd-task-table tr[data-mtd-subtask="1"] .mtd-task-link {
    color: #4A5568 !important;
}

/* ─── Completed row treatment ─── */
#my-tasks-dashboard tr[data-mtd-status="Completed"] td { background: rgba(56, 161, 105, 0.05); }
#my-tasks-dashboard tr[data-mtd-status="Completed"] .mtd-task-link { color: #38A169 !important; text-decoration: line-through; opacity: 0.7; }
#my-tasks-dashboard tr[data-mtd-status="Completed"] .mtd-relative-due,
#my-tasks-dashboard tr[data-mtd-status="Completed"] .mtd-date-cell { color: #38A169 !important; opacity: 0.7; }
#my-tasks-dashboard tr[data-mtd-overdue="1"] td { background: rgba(229, 62, 62, 0.04); }
#my-tasks-dashboard tr[data-mtd-overdue="1"] .mtd-relative-due { color: #C53030 !important; }

/* ─── Date column readable ─── */
#my-tasks-dashboard .mtd-task-table td:nth-child(5),
#my-tasks-dashboard .mtd-task-table td:nth-child(6) {
    font-size: 12px; line-height: 1.3; color: #4A5568;
}
#my-tasks-dashboard .mtd-relative-due { display: block; font-size: 11px; font-weight: 600; }

/* ─── Filter / chip bar tighter ─── */
#my-tasks-dashboard .mtd-date-chip { padding: 4px 11px !important; font-size: 11px !important; }
#my-tasks-dashboard .mtd-filter-bar { gap: 6px !important; padding: 8px 12px !important; }
#my-tasks-dashboard .mtd-filter-bar select { padding: 4px 8px !important; font-size: 11px !important; }

/* ════════════════════════════════════════════════════════════════════
   VARIANT B — chat-bubble thread drawer
   Triggered by clicking the existing 💬 button (.mtd-updates-toggle).
   The page JS toggles tr.mtd-updates-row and calls loadTaskUpdates()
   which renders .mtd-up-scroll / .mtd-up-item / .mtd-up-compose into
   td[colspan="8"] inside .mtd-updates-list.
   We restyle those existing classes to look like the v2 mockup.
   ════════════════════════════════════════════════════════════════════ */

/* Hide the "💬 Updates" inline link the page JS adds under task names —
   the real action is the icon button in the actions column. */
#my-tasks-dashboard a.mtd-updates-toggle,
#my-tasks-dashboard span.mtd-updates-toggle:not(.mtd-update-btn) { display: none !important; }

/* Drawer container */
#my-tasks-dashboard tr.mtd-updates-row td {
    padding: 0 !important;
    background: #FAFBFC !important;
    border-bottom: 1px solid #E2E8F0 !important;
}
#my-tasks-dashboard .mtd-updates-list {
    padding: 14px 24px 16px 50px !important;
    margin: 0 !important;
    border-top: 0 !important;
}
#my-tasks-dashboard .mtd-updates-list::before {
    content: "Comments";
    display: block;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: #A0AEC0;
    font-weight: 700;
    margin-bottom: 10px;
}

/* Scrollable comments thread */
#my-tasks-dashboard .mtd-up-scroll {
    max-height: 320px !important;
    overflow-y: auto !important;
    padding: 0 !important;
    background: transparent !important;
    margin-bottom: 12px;
}

/* Each comment ─── chat-bubble layout */
#my-tasks-dashboard .mtd-up-item {
    padding: 0 !important;
    margin: 0 0 12px 0 !important;
    background: transparent !important;
    border: 0 !important;
    border-radius: 0 !important;
    display: flex !important;
    gap: 10px !important;
    align-items: flex-start !important;
}
/* Avatar (injected by JS into ::before slot via .mtd-up-avatar prefix) */
#my-tasks-dashboard .mtd-up-avatar {
    width: 24px; height: 24px;
    border-radius: 50%;
    color: #fff;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    font-weight: 700;
    flex-shrink: 0;
    margin-top: 1px;
}
/* Wrap header + body in a flex column */
#my-tasks-dashboard .mtd-up-item > .mtd-up-body-wrap {
    flex: 1 1 auto;
    min-width: 0;
}
#my-tasks-dashboard .mtd-up-header {
    display: flex !important; align-items: baseline !important; gap: 6px !important;
    margin-bottom: 3px;
}
#my-tasks-dashboard .mtd-up-author {
    font-size: 12px !important; font-weight: 600 !important; color: #2D3748 !important;
}
#my-tasks-dashboard .mtd-up-time {
    font-size: 11px !important; color: #A0AEC0 !important;
}
#my-tasks-dashboard .mtd-up-body {
    font-size: 13px !important;
    color: #2D3748 !important;
    line-height: 1.45 !important;
    margin-top: 2px !important;
    padding: 7px 12px !important;
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 0 8px 8px 8px !important;
    word-break: break-word;
}

/* Reply box — matches mockup */
#my-tasks-dashboard .mtd-up-compose {
    border-top: 0 !important;
    margin-top: 14px !important;
    padding: 0 !important;
}
#my-tasks-dashboard .mtd-up-compose textarea {
    border: 1px solid #E2E8F0 !important;
    background: #FFFFFF !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
    font-size: 13px !important;
    min-height: 38px !important;
    max-height: 120px !important;
    width: 100% !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02);
}
#my-tasks-dashboard .mtd-up-compose textarea:focus {
    outline: none !important;
    border-color: #2490EF !important;
    box-shadow: 0 0 0 2px rgba(36,144,239,0.15) !important;
}
#my-tasks-dashboard .mtd-up-compose-actions {
    margin-top: 6px !important;
    align-items: center !important;
}
#my-tasks-dashboard .mtd-up-post-btn {
    padding: 6px 16px !important;
    background: #2490EF !important;
    border: 0 !important;
    border-radius: 5px !important;
    color: #fff !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    cursor: pointer;
}
#my-tasks-dashboard .mtd-up-post-btn:hover { background: #1976D2 !important; }
#my-tasks-dashboard .mtd-up-link-input {
    border: 1px solid #E2E8F0 !important;
    border-radius: 5px !important;
    padding: 5px 9px !important;
    font-size: 11px !important;
}
#my-tasks-dashboard .mtd-up-empty {
    padding: 8px 0 14px !important;
    font-size: 12px !important;
    color: #A0AEC0 !important;
    text-align: left !important;
    font-style: italic;
}

/* Highlight the row whose drawer is open */
#my-tasks-dashboard tr.mtd-task-row.mtd-drawer-open td:not(.mtd-action-cell) { background: #EBF8FF !important; }
#my-tasks-dashboard .mtd-update-btn.active,
#my-tasks-dashboard .mtd-update-btn[data-mtd-active="1"] {
    background: #EBF8FF !important;
    color: #2B6CB0 !important;
    border-color: #2490EF !important;
}

/* ─── Mobile: keep all info, just stack ─── */
@media (max-width: 768px) {
    #my-tasks-dashboard .mtd-task-table thead { display: none !important; }
    #my-tasks-dashboard .mtd-task-table colgroup { display: none !important; }
    #my-tasks-dashboard .mtd-task-table { display: block !important; width: 100%; }
    #my-tasks-dashboard .mtd-task-table tbody { display: block !important; width: 100%; }

    #my-tasks-dashboard .mtd-task-table tr:not(.mtd-updates-row):not(.mtd-timelog-row) {
        display: flex !important;
        flex-wrap: wrap !important;
        align-items: center !important;
        gap: 6px 8px !important;
        padding: 10px 12px !important;
        border-bottom: 1px solid #E2E8F0 !important;
        background: #fff !important;
        width: 100% !important;
    }
    #my-tasks-dashboard .mtd-task-table td {
        padding: 0 !important; border: none !important; flex: 0 0 auto;
    }
    /* Hide left-border accent on mobile (only on real task rows — NOT on drawer rows
       whose only td is also nth-child(1) and would otherwise vanish) */
    #my-tasks-dashboard .mtd-task-table tr:not(.mtd-updates-row):not(.mtd-timelog-row) td:nth-child(1) { display: none !important; }
    /* Drawer + timelog rows: full-width block on mobile, ONLY when the page JS has
       opened them (inline style does not contain "none"). Closed rows keep their
       inline display:none. */
    #my-tasks-dashboard .mtd-task-table tr.mtd-updates-row:not([style*="none"]),
    #my-tasks-dashboard .mtd-task-table tr.mtd-timelog-row:not([style*="none"]) {
        display: block !important; width: 100% !important;
    }
    #my-tasks-dashboard .mtd-task-table tr.mtd-updates-row:not([style*="none"]) > td,
    #my-tasks-dashboard .mtd-task-table tr.mtd-timelog-row:not([style*="none"]) > td {
        display: block !important; width: 100% !important;
    }
    /* Task name = full width */
    #my-tasks-dashboard .mtd-task-table td:nth-child(2) {
        order: 1 !important; flex: 1 0 100% !important; max-width: 100% !important;
        font-size: 13px !important; font-weight: 500;
    }
    #my-tasks-dashboard .mtd-task-link {
        display: inline-block !important; max-width: 100% !important;
        white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important;
        color: #2D3748 !important; font-size: 13px !important; font-weight: 600;
        vertical-align: middle;
    }
    /* Mobile: assignee chip ALWAYS on its own line directly under the task name —
       prevents clipping when the name is long and ensures every Delegated row
       shows its assignee. */
    #my-tasks-dashboard .mtd-assignee-tag {
        display: block !important;
        margin: 4px 0 0 0 !important;
        font-size: 11px !important;
        padding: 2px 8px !important;
        background: #EBF8FF !important;
        color: #2B6CB0 !important;
        border-radius: 10px !important;
        width: fit-content !important;
        max-width: calc(100% - 4px) !important;
    }
    /* Subtask: row whose first child of name td is the ↳ arrow span.
       Make the arrow prominent and the name muted + smaller, so subtasks
       are visually subordinate to parent tasks. */
    #my-tasks-dashboard .mtd-task-table tr[data-mtd-subtask="1"] td:nth-child(2) {
        padding-left: 18px !important;
        position: relative;
    }
    #my-tasks-dashboard .mtd-task-table tr[data-mtd-subtask="1"] td:nth-child(2) > span:first-child {
        color: #2B6CB0 !important;
        font-weight: 700 !important;
        font-size: 14px !important;
        margin-right: 4px !important;
        display: inline-block !important;
        vertical-align: middle;
    }
    #my-tasks-dashboard .mtd-task-table tr[data-mtd-subtask="1"] .mtd-task-link {
        font-size: 12px !important;
        color: #718096 !important;
        font-weight: 500 !important;
    }
    /* Vertical guide line for subtasks */
    #my-tasks-dashboard .mtd-task-table tr[data-mtd-subtask="1"] {
        border-left: 3px solid #BEE3F8 !important;
        background: #FAFCFE !important;
    }
    /* Status, priority, dates inline */
    #my-tasks-dashboard .mtd-task-table td:nth-child(3) { order: 2 !important; }
    #my-tasks-dashboard .mtd-task-table td:nth-child(4) { order: 3 !important; }
    #my-tasks-dashboard .mtd-task-table td:nth-child(5) {
        order: 4 !important; font-size: 10px !important; color: #718096 !important;
    }
    #my-tasks-dashboard .mtd-task-table td:nth-child(5)::before { content: "Start: "; color: #A0AEC0; }
    #my-tasks-dashboard .mtd-task-table td:nth-child(6) {
        order: 5 !important; flex: 1 1 auto !important; text-align: right;
        font-size: 11px !important; color: #4A5568; font-weight: 600;
    }
    /* Actions: bigger touch targets — ≥36px */
    #my-tasks-dashboard .mtd-task-table td:nth-child(8) {
        order: 7 !important; flex: 0 0 auto !important; text-align: right;
        display: flex !important; gap: 6px !important; align-items: center;
    }
    #my-tasks-dashboard .mtd-task-table td:nth-child(8) button.mtd-timelog-btn,
    #my-tasks-dashboard .mtd-task-table td:nth-child(8) button.mtd-update-btn {
        min-width: 36px !important;
        min-height: 32px !important;
        padding: 6px 10px !important;
        font-size: 14px !important;
        line-height: 1 !important;
        border: 1px solid #E2E8F0 !important;
        background: #FFFFFF !important;
        border-radius: 6px !important;
        color: #4A5568 !important;
    }
    #my-tasks-dashboard .mtd-task-table td:nth-child(8) button.mtd-update-btn[data-mtd-active="1"] {
        background: #EBF8FF !important;
        color: #2B6CB0 !important;
        border-color: #2490EF !important;
    }

    /* Drawer fills mobile width */
    #my-tasks-dashboard .mtd-updates-list { padding: 12px 14px !important; }
}
</style>
<script>/* mtd_variant_b_v1 */
(function(){
    var AVATAR_PALETTE = [
        "#805AD5", "#38A169", "#DD6B20", "#3182CE", "#2B6CB0",
        "#D69E2E", "#319795", "#B83280", "#718096", "#C05621"
    ];

    function avatarColorFor(emailOrName) {
        if (!emailOrName) return "#718096";
        var s = String(emailOrName).toLowerCase();
        var hash = 0;
        for (var i = 0; i < s.length; i++) hash = ((hash << 5) - hash + s.charCodeAt(i)) & 0xffffffff;
        return AVATAR_PALETTE[Math.abs(hash) % AVATAR_PALETTE.length];
    }

    function initialsFor(authorText) {
        if (!authorText) return "?";
        var parts = String(authorText).trim().split(/[\\s\\.@_-]+/).filter(Boolean);
        if (parts.length === 0) return "?";
        if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
        return (parts[0][0] + parts[1][0]).toUpperCase();
    }

    /* Show ALL assignees in the chip (the page JS only shows the first).
       For each Delegated row, look up the task by name and rebuild the chip
       text to include every assignee. Also enables a chip on the "All" tab. */
    function decorateAssigneeChips() {
        var dash = document.getElementById('my-tasks-dashboard');
        if (!dash) return;
        // Active view tab
        var activeTab = dash.querySelector('.mtd-view-tab.active');
        var view = activeTab ? activeTab.textContent.trim().toLowerCase() : '';
        var showOnAll = view.indexOf('all') === 0;
        var showOnDelegated = view.indexOf('delegated') === 0;
        if (!showOnAll && !showOnDelegated) return;

        // We can't access the page IIFE's allTasks directly, so we fetch
        // _assign once and cache on window. Subsequent decorate() calls
        // reuse the cache so this fires only once per session.
        if (!window.__mtdAssignCache) {
            if (window.__mtdAssignFetching) return;
            window.__mtdAssignFetching = true;
            frappe.xcall('frappe.client.get_list', {
                doctype: 'Task',
                filters: { status: ['not in', ['Template', 'Cancelled']] },
                fields: ['name', '_assign'],
                limit_page_length: 0
            }).then(function(rows){
                window.__mtdAssignCache = {};
                (rows || []).forEach(function(r){ window.__mtdAssignCache[r.name] = r._assign; });
                window.__mtdAssignFetching = false;
                setTimeout(decorate, 30);
            }).catch(function(){ window.__mtdAssignFetching = false; });
            return;
        }
        var byName = {};
        Object.keys(window.__mtdAssignCache).forEach(function(name){
            byName[name] = { name: name, _assign: window.__mtdAssignCache[name] };
        });

        dash.querySelectorAll('.mtd-task-table tbody tr:not(.mtd-updates-row):not(.mtd-timelog-row)').forEach(function(tr){
            var btn = tr.querySelector('button.mtd-update-btn[data-task], button.mtd-timelog-btn[data-task]');
            var taskName = btn ? btn.getAttribute('data-task') : null;
            var t = taskName ? byName[taskName] : null;
            if (!t || !t._assign) return;
            var emails;
            try { emails = JSON.parse(t._assign); } catch(e) { return; }
            if (!emails || !emails.length) return;
            // On My Tasks/Delegated, exclude the current user from the chip
            var me = (frappe && frappe.session && frappe.session.user) || '';
            if (showOnDelegated) {
                emails = emails.filter(function(e){ return e !== me; });
            }
            if (!emails.length) return;
            var labels = emails.map(function(e){ return e.split('@')[0].replace(/\\./g,' '); });
            var nameTd = tr.children[1];
            if (!nameTd) return;
            var existing = nameTd.querySelector('.mtd-assignee-tag');
            var newText = '☞ ' + labels.join(', ');
            if (existing) {
                if (existing.textContent.trim() !== newText) existing.textContent = newText;
            } else if (showOnAll) {
                var span = document.createElement('span');
                span.className = 'mtd-assignee-tag';
                span.textContent = newText;
                nameTd.appendChild(document.createTextNode(' '));
                nameTd.appendChild(span);
            }
        });
    }

    function decorateSubtaskRows() {
        var dash = document.getElementById('my-tasks-dashboard');
        if (!dash) return;
        // A subtask row's name-td has a ↳ arrow span as its first child.
        dash.querySelectorAll('.mtd-task-table tbody tr:not(.mtd-updates-row):not(.mtd-timelog-row)').forEach(function(tr){
            var nameTd = tr.children[1];
            if (!nameTd) return;
            var first = nameTd.firstElementChild;
            var isSub = first && first.tagName === 'SPAN' && first.textContent.trim() === '↳';
            if (isSub) tr.setAttribute('data-mtd-subtask', '1');
            else tr.removeAttribute('data-mtd-subtask');
        });
    }

    function decorateStatusPills() {
        var dash = document.getElementById('my-tasks-dashboard');
        if (!dash) return;
        dash.querySelectorAll('.mtd-status-select').forEach(function(s){
            s.setAttribute('data-status', s.value);
            var tr = s.closest('tr');
            if (tr) {
                tr.setAttribute('data-mtd-status', s.value);
                var endTd = tr.querySelector('td:nth-child(6)');
                var hasOverdue = endTd && endTd.textContent && /overdue/i.test(endTd.textContent);
                if (hasOverdue && s.value !== 'Completed') tr.setAttribute('data-mtd-overdue', '1');
                else tr.removeAttribute('data-mtd-overdue');
            }
        });
        dash.querySelectorAll('.mtd-priority-select').forEach(function(s){
            s.setAttribute('data-priority', s.value);
        });
    }

    function decorateCommentRows() {
        var dash = document.getElementById('my-tasks-dashboard');
        if (!dash) return;
        // Each .mtd-up-item gets:
        //   1. an .mtd-up-avatar prepended (coloured initials)
        //   2. its header + body wrapped in .mtd-up-body-wrap so flex layout works
        dash.querySelectorAll('.mtd-up-item').forEach(function(item){
            if (item.dataset.mtdAvatar === '1') return;
            var authorEl = item.querySelector('.mtd-up-author');
            var author = authorEl ? authorEl.textContent.trim() : '';
            var color = avatarColorFor(author);
            var initials = initialsFor(author);

            var av = document.createElement('span');
            av.className = 'mtd-up-avatar';
            av.style.background = color;
            av.textContent = initials;

            // Wrap existing children into .mtd-up-body-wrap
            var wrap = document.createElement('div');
            wrap.className = 'mtd-up-body-wrap';
            while (item.firstChild) wrap.appendChild(item.firstChild);

            item.appendChild(av);
            item.appendChild(wrap);
            item.dataset.mtdAvatar = '1';
        });
    }

    function markOpenDrawer() {
        var dash = document.getElementById('my-tasks-dashboard');
        if (!dash) return;
        dash.querySelectorAll('tr.mtd-task-row.mtd-drawer-open').forEach(function(tr){
            tr.classList.remove('mtd-drawer-open');
        });
        dash.querySelectorAll('button.mtd-update-btn[data-mtd-active="1"]').forEach(function(b){
            b.removeAttribute('data-mtd-active');
        });
        dash.querySelectorAll('tr.mtd-updates-row').forEach(function(updRow){
            if (updRow.style.display === 'none' || updRow.offsetParent === null) return;
            var task = updRow.getAttribute('data-task');
            if (!task) return;
            var prev = updRow.previousElementSibling;
            if (prev && prev.tagName === 'TR') {
                prev.classList.add('mtd-task-row', 'mtd-drawer-open');
            }
            var btn = dash.querySelector('button.mtd-update-btn[data-task="' + task + '"]');
            if (btn) btn.setAttribute('data-mtd-active', '1');
        });
    }

    function decorate() {
        decorateSubtaskRows();
        decorateStatusPills();
        decorateAssigneeChips();
        decorateCommentRows();
        markOpenDrawer();
    }

    document.addEventListener('change', function(e){
        if (e.target && e.target.classList && (e.target.classList.contains('mtd-status-select') || e.target.classList.contains('mtd-priority-select'))) {
            setTimeout(decorate, 60);
        }
    });
    document.addEventListener('click', function(e){
        if (e.target && e.target.closest && e.target.closest('.mtd-updates-toggle, .mtd-update-btn')) {
            setTimeout(decorate, 80);
            setTimeout(decorate, 250);
        }
    });

    /* If URL has ?mobile=1, persistently force mobile preview mode:
       wrap content in a 390px-wide frame + promote @media (max-width:768px)
       rules to unconditional. Survives reloads — useful when iterating
       on mobile UX from a preview pane. */
    function applyMobilePreviewMode() {
        if (!/[?&]mobile=1\\b/.test(window.location.search)) return;
        if (document.getElementById('mobile-preview-frame')) return;
        // Wrap body content in a 390px frame
        var fr = document.createElement('div');
        fr.id = 'mobile-preview-frame';
        fr.style.cssText = 'max-width:390px;margin:0 auto;background:#fff;min-height:100vh;box-shadow:0 0 24px rgba(0,0,0,0.15);';
        var children = Array.from(document.body.children);
        document.body.appendChild(fr);
        children.forEach(function(c){ if (c !== fr) fr.appendChild(c); });
        document.body.style.background = '#F0F4F8';
        // Promote @media (max-width:768px) rules → unconditional
        for (var s = 0; s < document.styleSheets.length; s++) {
            var ss = document.styleSheets[s];
            try {
                var rules = ss.cssRules || ss.rules;
                if (!rules) continue;
                for (var i = 0; i < rules.length; i++) {
                    var r = rules[i];
                    if (r.constructor && r.constructor.name === 'CSSMediaRule' && /max-width:\\s*768/.test(r.conditionText || '')) {
                        for (var j = 0; j < r.cssRules.length; j++) {
                            try { ss.insertRule(r.cssRules[j].cssText, ss.cssRules.length); } catch(e) {}
                        }
                    }
                }
            } catch(e) {}
        }
    }

    function startObserver() {
        var dash = document.getElementById('my-tasks-dashboard');
        if (!dash) { setTimeout(startObserver, 500); return; }
        applyMobilePreviewMode();
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
    doc.main_section_html = INJECTED_HTML
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    print("Variant B styling applied to /my-tasks (main_section_html, {} chars).".format(len(INJECTED_HTML)))
