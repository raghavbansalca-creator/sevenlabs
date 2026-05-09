/**
 * SOP Discovery Engagement — form buttons that drive the AI agent
 * + inline Q&A Review block.
 */

const QUALITY_COLOR = {
    "Specific":      "#2dd36f",   // green
    "Multi-part":    "#ffc409",   // amber
    "Vague":         "#f7b801",   // dark amber
    "Wrong-target":  "#eb445a",   // red
    "Dodged":        "#eb445a",
    "Not-addressed": "#92949c",   // grey
    "Pending":       "#cccccc"
};

function _esc(s) {
    return (s == null ? "" : String(s))
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

// ─── Background-job poller for /process_transcript ────────────────────────
// The Process Transcript call enqueues a long-running job and returns
// immediately. We do TWO things from the browser:
//   1. A 1-second ticker that updates a live "Processing R1 • 0m 47s" badge
//      in the form's title bar so the user always sees motion.
//   2. A 10-second poller that re-fetches the engagement and watches
//      round.status. When it flips Processing → Answered (success) or
//      Processing → Failed (error), both timers stop and the form reloads.
const PROCESS_POLL_INTERVAL_MS = 10000;
const PROCESS_TICK_INTERVAL_MS = 1000;
const PROCESS_POLL_MAX_MIN = 25;

// Global poller registry so refresh()-triggered re-calls of
// maybe_resume_polling don't spawn duplicate pollers (which was the source of
// stacked-toast bug + backwards-ticking timer).
window._slv_active_pollers = window._slv_active_pollers || {};

function _poller_key(docname, suffix) {
    return `${docname}::${suffix}`;
}

// Silently catch Frappe's TimestampMismatchError dialog and reload instead of
// nagging the user. Long background jobs bump the engagement's modified
// timestamp on completion, which then collides with any pending JS save.
(function() {
    if (window._slv_msgprint_patched) return;
    window._slv_msgprint_patched = true;
    if (!window.frappe || !frappe.msgprint) return;
    const _orig = frappe.msgprint;
    frappe.msgprint = function(opts, ...rest) {
        const candidates = [];
        if (typeof opts === "string") candidates.push(opts);
        else if (opts && typeof opts === "object") {
            ["message","title","indicator"].forEach(k => {
                if (typeof opts[k] === "string") candidates.push(opts[k]);
            });
        }
        for (const c of candidates) {
            if (/has been modified after you have opened it/i.test(c)
                || /TimestampMismatchError/i.test(c)) {
                // Silently reload the doc — background job has updated it,
                // user's stale in-memory copy must be replaced.
                try { if (window.cur_frm) cur_frm.reload_doc(); } catch (e) {}
                return;
            }
        }
        return _orig.apply(this, [opts, ...rest]);
    };
})();

function _format_elapsed(ms) {
    const s = Math.floor(ms / 1000);
    const m = Math.floor(s / 60);
    return m > 0 ? `${m}m ${(s % 60).toString().padStart(2, '0')}s` : `${s}s`;
}

function _set_processing_indicator(frm, round_number, started_at_ms, stage, label_prefix) {
    if (!frm.page || !frm.page.set_indicator) return;
    const elapsed = _format_elapsed(Date.now() - started_at_ms);
    const prefix = label_prefix || 'Processing';
    const label = stage
        ? `${prefix} R${round_number} • ${stage} • ${elapsed}`
        : `${prefix} R${round_number} • ${elapsed}`;
    frm.page.set_indicator(label, 'orange');
}

function _clear_processing_indicator(frm) {
    if (frm.page && frm.page.clear_indicator) {
        frm.page.clear_indicator();
    }
}

// Generic background-job watcher. Used for both Generate Round
// (in_progress_status='Generating', done_status='Generated') and
// Process Transcript (in_progress_status='Processing', done_status='Answered').
function start_background_job(frm, round_number, opts) {
    opts = opts || {};
    const in_progress_status = opts.in_progress_status || 'Processing';
    const done_status = opts.done_status || 'Answered';
    const label_prefix = opts.label_prefix || 'Processing';
    const start_alert_msg = opts.start_alert ||
        __('{0} R{1} in background. Live progress shows in the title bar — safe to leave the page.', [label_prefix, round_number]);
    const success_msg = opts.success_msg ||
        __('Round {0} done — refreshing form.', [round_number]);
    const fail_title = opts.fail_title ||
        __('Job failed for Round {0}', [round_number]);

    // ── DEDUP — if a poller for this round+done_status is already running,
    // do not spawn another. This eliminates the stacked-toast and
    // ticking-backwards-elapsed-time bugs caused by frm.refresh() firing
    // multiple times during long jobs.
    const reg_key = _poller_key(frm.docname, `R${round_number}:${done_status}`);
    if (window._slv_active_pollers[reg_key]) {
        return;  // already watching — refuse to duplicate
    }

    const started_at_ms = Date.now();
    let last_stage = '';
    let stopped = false;

    frappe.show_alert({message: start_alert_msg, indicator: 'blue'}, 8);

    const ticker = setInterval(() => {
        if (stopped) return;
        _set_processing_indicator(frm, round_number, started_at_ms, last_stage, label_prefix);
    }, PROCESS_TICK_INTERVAL_MS);

    const stop = () => {
        stopped = true;
        clearInterval(ticker);
        _clear_processing_indicator(frm);
        delete window._slv_active_pollers[reg_key];
    };

    window._slv_active_pollers[reg_key] = {stop: stop, started_at_ms: started_at_ms};

    const poll_once = () => {
        if (stopped) return;
        const elapsed_min = (Date.now() - started_at_ms) / 60000;
        if (elapsed_min > PROCESS_POLL_MAX_MIN) {
            stop();
            frappe.show_alert({
                message: __('Still {0} after {1} min — open the round to check status manually.',
                            [in_progress_status, PROCESS_POLL_MAX_MIN]),
                indicator: 'orange'
            }, 10);
            return;
        }
        frappe.db.get_doc(frm.doctype, frm.docname).then(doc => {
            if (stopped) return;
            const r = (doc.rounds || []).find(x => parseInt(x.round_number, 10) === parseInt(round_number, 10));
            if (!r) {
                setTimeout(poll_once, PROCESS_POLL_INTERVAL_MS);
                return;
            }
            last_stage = r.processing_stage || '';
            if (r.status === done_status) {
                stop();
                frappe.show_alert({message: success_msg, indicator: 'green'}, 8);
                frm.reload_doc();
            } else if (r.status === 'Failed') {
                stop();
                const err = (r.processing_error || '(no error details captured)').toString();
                frappe.msgprint({
                    title: fail_title,
                    message: '<pre style="white-space:pre-wrap; max-height:300px; overflow:auto;">' + _esc(err.slice(-1500)) + '</pre>',
                    indicator: 'red'
                });
                frm.reload_doc();
            } else {
                setTimeout(poll_once, PROCESS_POLL_INTERVAL_MS);
            }
        }).catch(() => {
            setTimeout(poll_once, PROCESS_POLL_INTERVAL_MS);
        });
    };

    // NOTE: do NOT call frm.reload_doc() here — that triggers refresh() →
    // maybe_resume_polling() and would have caused a duplicate poller before
    // dedup was added. The first poll cycle re-reads the doc from DB anyway.
    setTimeout(poll_once, PROCESS_POLL_INTERVAL_MS);
}

// ─── Engagement-level background-job poller ───────────────────────────────
// Used for Score Coverage / Compile SOP / Reflect — these are engagement-wide
// operations (no per-round status), so they poll a top-level field on the
// engagement doc (e.g. coverage_status: Processing → Done | Failed).
function _set_engagement_indicator(frm, started_at_ms, stage, label_prefix) {
    if (!frm.page || !frm.page.set_indicator) return;
    const elapsed = _format_elapsed(Date.now() - started_at_ms);
    const prefix = label_prefix || 'Processing';
    const label = stage
        ? `${prefix} • ${stage} • ${elapsed}`
        : `${prefix} • ${elapsed}`;
    frm.page.set_indicator(label, 'orange');
}

function start_background_engagement_job(frm, opts) {
    opts = opts || {};
    const status_field = opts.status_field;            // e.g. 'coverage_status'
    const stage_field = opts.stage_field;              // e.g. 'coverage_processing_stage'
    const error_field = opts.error_field;              // e.g. 'coverage_error'
    const done_status = opts.done_status || 'Done';
    const in_progress_status = opts.in_progress_status || 'Processing';
    const label_prefix = opts.label_prefix || 'Processing';
    const start_alert_msg = opts.start_alert ||
        __('{0} in background. Live progress shows in the title bar — safe to leave the page.', [label_prefix]);
    const success_msg = opts.success_msg ||
        __('{0} done — refreshing form.', [label_prefix]);
    const fail_title = opts.fail_title ||
        __('{0} job failed', [label_prefix]);
    const max_min = opts.max_min || PROCESS_POLL_MAX_MIN;

    // ── DEDUP — same logic as start_background_job; key by status_field
    const reg_key = _poller_key(frm.docname, status_field);
    if (window._slv_active_pollers[reg_key]) {
        return;  // already watching
    }

    const started_at_ms = Date.now();
    let last_stage = '';
    let stopped = false;

    frappe.show_alert({message: start_alert_msg, indicator: 'blue'}, 8);

    const ticker = setInterval(() => {
        if (stopped) return;
        _set_engagement_indicator(frm, started_at_ms, last_stage, label_prefix);
    }, PROCESS_TICK_INTERVAL_MS);

    const stop = () => {
        stopped = true;
        clearInterval(ticker);
        _clear_processing_indicator(frm);
        delete window._slv_active_pollers[reg_key];
    };

    window._slv_active_pollers[reg_key] = {stop: stop, started_at_ms: started_at_ms};

    const poll_once = () => {
        if (stopped) return;
        const elapsed_min = (Date.now() - started_at_ms) / 60000;
        if (elapsed_min > max_min) {
            stop();
            frappe.show_alert({
                message: __('Still {0} after {1} min — open the engagement\'s Background job state section to check status manually.',
                            [in_progress_status, max_min]),
                indicator: 'orange'
            }, 10);
            return;
        }
        frappe.db.get_doc(frm.doctype, frm.docname).then(doc => {
            if (stopped) return;
            const status_val = doc[status_field] || '';
            last_stage = doc[stage_field] || '';
            if (status_val === done_status) {
                stop();
                frappe.show_alert({message: success_msg, indicator: 'green'}, 8);
                frm.reload_doc();
            } else if (status_val === 'Failed') {
                stop();
                const err = (doc[error_field] || '(no error details captured)').toString();
                frappe.msgprint({
                    title: fail_title,
                    message: '<pre style="white-space:pre-wrap; max-height:300px; overflow:auto;">' + _esc(err.slice(-1500)) + '</pre>',
                    indicator: 'red'
                });
                frm.reload_doc();
            } else {
                setTimeout(poll_once, PROCESS_POLL_INTERVAL_MS);
            }
        }).catch(() => {
            setTimeout(poll_once, PROCESS_POLL_INTERVAL_MS);
        });
    };

    setTimeout(poll_once, PROCESS_POLL_INTERVAL_MS);
}

function start_background_score_coverage(frm) {
    start_background_engagement_job(frm, {
        status_field: 'coverage_status',
        stage_field: 'coverage_processing_stage',
        error_field: 'coverage_error',
        in_progress_status: 'Processing',
        done_status: 'Done',
        label_prefix: 'Scoring coverage',
        start_alert: __('Scoring coverage in background. Live progress shows in the title bar.'),
        success_msg: __('Coverage scored — refreshing form.'),
        fail_title: __('Score Coverage failed'),
        max_min: 15,
    });
}

function start_background_compile(frm) {
    start_background_engagement_job(frm, {
        status_field: 'compile_status',
        stage_field: 'compile_processing_stage',
        error_field: 'compile_error',
        in_progress_status: 'Processing',
        done_status: 'Done',
        label_prefix: 'Compiling SOP',
        start_alert: __('Compiling SOP in background (2-5 min). Live progress shows in the title bar.'),
        success_msg: __('SOP compiled — refreshing form.'),
        fail_title: __('Compile SOP failed'),
        max_min: 25,
    });
}

function start_background_reflect(frm) {
    start_background_engagement_job(frm, {
        status_field: 'reflect_status',
        stage_field: 'reflect_processing_stage',
        error_field: 'reflect_error',
        in_progress_status: 'Processing',
        done_status: 'Done',
        label_prefix: 'Reflecting',
        start_alert: __('Reflecting on engagement in background. Live progress shows in the title bar.'),
        success_msg: __('Reflection memo saved — refreshing form.'),
        fail_title: __('Reflect failed'),
        max_min: 10,
    });
}

// Convenience wrappers
function start_background_process(frm, round_number) {
    start_background_job(frm, round_number, {
        in_progress_status: 'Processing',
        done_status: 'Answered',
        label_prefix: 'Processing transcript',
        success_msg: __('Round {0} processed — refreshing form.', [round_number]),
        fail_title: __('Transcript processing failed for Round {0}', [round_number]),
    });
}

function start_background_generation(frm, round_number) {
    start_background_job(frm, round_number, {
        in_progress_status: 'Generating',
        done_status: 'Generated',
        label_prefix: 'Generating',
        start_alert: __('Generating R{0} in background. Live progress shows in the title bar.', [round_number]),
        success_msg: __('Round {0} questions generated — refreshing form.', [round_number]),
        fail_title: __('Round generation failed for Round {0}', [round_number]),
    });
}

// Auto-resume polling on page load if a round is mid-Processing/Generating
// or an engagement-level long job (coverage/compile/reflect) is mid-Processing
// (e.g. user closed the tab and reopened it).
function maybe_resume_polling(frm) {
    (frm.doc.rounds || []).forEach(r => {
        if (r.status === 'Processing') {
            setTimeout(() => start_background_process(frm, r.round_number), 1500);
        } else if (r.status === 'Generating') {
            setTimeout(() => start_background_generation(frm, r.round_number), 1500);
        }
    });
    if (frm.doc.coverage_status === 'Processing') {
        setTimeout(() => start_background_score_coverage(frm), 1500);
    }
    if (frm.doc.compile_status === 'Processing') {
        setTimeout(() => start_background_compile(frm), 1500);
    }
    if (frm.doc.reflect_status === 'Processing') {
        setTimeout(() => start_background_reflect(frm), 1500);
    }
}

function _q_card(q) {
    const qcolor = QUALITY_COLOR[q.answer_quality || "Pending"];
    const imp_badge = q.is_impromptu
        ? `<span style="background:#805ad5; color:#fff; padding:1px 6px; border-radius:3px; font-size:9px; font-weight:700; margin-left:4px;">IMPROMPTU</span>` : "";
    return `
    <div style="border:1px solid #e2e8f0; border-left:3px solid ${qcolor}; border-radius:4px; padding:10px 14px; margin-bottom:8px; background:#fff;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
        <div style="font-size:11px; color:#4a5568; font-weight:600;">
            <span style="background:#edf2f7; padding:1px 6px; border-radius:3px;">${_esc(q.question_id)}</span>
            <span style="margin-left:8px;">${_esc(q.module_code)}</span>
            <span style="color:#a0aec0;"> / </span>
            <span>${_esc(q.sop_section)}</span>
            ${imp_badge}
        </div>
        <div style="display:flex; gap:6px; align-items:center;">
            <span style="background:${qcolor}; color:#fff; padding:2px 8px; border-radius:3px; font-size:10px; font-weight:700;">
                ${_esc(q.answer_quality || "Pending")}
            </span>
            <a href="/app/sop-round-question/${encodeURIComponent(q.name)}"
               style="font-size:11px; color:#3182ce; text-decoration:none;">edit ✎</a>
        </div>
      </div>
      <div style="font-size:13px; color:#1a202c; line-height:1.5; margin-bottom:6px;">
        <strong>Q:</strong> ${_esc(q.question_text)}
      </div>
      ${q.answer ? `
        <div style="font-size:13px; color:#2d3748; line-height:1.5; padding:8px 10px; background:#f7fafc; border-radius:3px; margin-bottom:6px;">
            <strong style="color:#2b6cb0;">A:</strong> ${_esc(q.answer)}
        </div>` : `
        <div style="font-size:11px; color:#a0aec0; font-style:italic; margin-bottom:6px;">— no answer captured yet —</div>
        `}
      ${q.evidence_quote ? `
        <div style="font-size:11px; color:#718096; line-height:1.4; padding:4px 10px; border-left:2px solid #cbd5e0; font-style:italic;">
            "${_esc(q.evidence_quote)}"
        </div>` : ""}
      ${q.goal_tags ? `
        <div style="margin-top:6px; font-size:10px;">
            ${q.goal_tags.split(",").map(t => `<span style="display:inline-block; background:#edf2f7; color:#4a5568; padding:1px 6px; border-radius:3px; margin-right:4px;">${_esc(t.trim())}</span>`).join("")}
        </div>` : ""}
    </div>`;
}

function _extras_block(extras) {
    if (!extras || !extras.length) {
        return `<div style="padding:10px 14px; background:#f7fafc; border:1px dashed #cbd5e0; border-radius:4px; color:#718096; font-size:12px; font-style:italic;">No extra observations captured for this round.</div>`;
    }
    let html = `<div style="background:#fffaf0; border:1px solid #f6ad55; border-left:3px solid #ed8936; border-radius:4px; padding:10px 14px;">`;
    extras.forEach((e, i) => {
        const last = i === extras.length - 1;
        html += `<div style="margin-bottom:${last ? '0' : '8px'}; padding-bottom:${last ? '0' : '8px'}; border-bottom:${last ? 'none' : '1px dashed #fbd38d'};">
            <div style="font-size:12px; color:#1a202c; line-height:1.5;">
                <span style="background:#feebc8; padding:1px 5px; border-radius:3px; font-size:10px; font-weight:600; margin-right:6px;">${_esc(e.module_code || '?')}</span>
                ${_esc(e.observation || '')}
            </div>
            ${e.thread_to_pull ? `<div style="font-size:11px; color:#9c4221; font-style:italic; margin-top:3px;">↳ thread to pull: ${_esc(e.thread_to_pull)}</div>` : ''}
            ${e.evidence_quote ? `<div style="font-size:10px; color:#718096; margin-top:3px; padding-left:8px; border-left:2px solid #fbd38d; font-style:italic;">"${_esc(e.evidence_quote)}"</div>` : ''}
        </div>`;
    });
    html += `</div>`;
    return html;
}

function _section_header(label, count, color) {
    return `<h6 style="margin:14px 0 8px; padding-bottom:4px; border-bottom:1px solid #e2e8f0; font-size:12px; text-transform:uppercase; letter-spacing:0.5px; color:${color || '#2d3748'};">
        ${label}${count != null ? ` <span style="font-weight:400; color:#a0aec0;">(${count})</span>` : ''}
    </h6>`;
}

function _round_panel(rn, round_qs, round_meta) {
    const orig_qs = round_qs.filter(q => !q.is_impromptu);
    const imp_qs = round_qs.filter(q => q.is_impromptu);
    const extras = round_meta.extras || [];
    const totals = {Specific:0, "Multi-part":0, Vague:0, "Wrong-target":0, Dodged:0, "Not-addressed":0, Pending:0};
    round_qs.forEach(q => { totals[q.answer_quality || "Pending"] = (totals[q.answer_quality || "Pending"] || 0) + 1; });

    // Header strip
    let html = `<div style="display:flex; gap:14px; flex-wrap:wrap; padding:8px 12px; background:#f7fafc;
                    border:1px solid #e2e8f0; border-radius:6px; margin-bottom:12px; align-items:center;">
        <div style="font-weight:600; font-size:13px;">Round ${rn}</div>
        <div style="font-size:11px; color:#4a5568;">${round_meta.date || ''} • status: <strong>${_esc(round_meta.status || 'Pending')}</strong></div>
        <div style="font-size:11px; color:#4a5568;">${orig_qs.length} questions • ${imp_qs.length} impromptu • ${extras.length} extras</div>
        <div style="display:flex; gap:6px; flex-wrap:wrap;">`;
    Object.entries(totals).filter(([_,v])=>v>0).forEach(([k,v]) => {
        html += `<span style="display:inline-block; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:600;
                              background:${QUALITY_COLOR[k]}; color:#fff;">${v} ${k}</span>`;
    });
    html += `</div></div>`;

    // 1. Original questionnaire (numbered q1..qN)
    html += _section_header('📋 Original questionnaire', orig_qs.length);
    if (orig_qs.length) {
        orig_qs.forEach(q => { html += _q_card(q); });
    } else {
        html += `<div style="color:#a0aec0; font-style:italic; font-size:12px; padding:6px 10px;">No original questions for this round.</div>`;
    }

    // 2. Impromptu Q&A (i1, i2, ...) — questions client effectively answered without being asked
    html += _section_header('✦ Impromptu Q&A captured', imp_qs.length, '#805ad5');
    if (imp_qs.length) {
        imp_qs.forEach(q => { html += _q_card(q); });
    } else {
        html += `<div style="color:#a0aec0; font-style:italic; font-size:12px; padding:6px 10px;">No impromptu Q&A captured for this round.</div>`;
    }

    // 3. Extra observations — volunteered facts not in Q&A form
    html += _section_header('⚑ Extra observations (threads to pull next round)', extras.length, '#9c4221');
    html += _extras_block(extras);

    // 4. Transcript (collapsed by default)
    const transcript = round_meta.transcript || '';
    html += _section_header('📜 Meeting transcript', transcript ? transcript.length + ' chars' : 'not pasted', '#4a5568');
    if (transcript) {
        const tid = `transcript_r${rn}`;
        html += `<details style="margin-top:6px;">
            <summary style="cursor:pointer; font-size:12px; color:#3182ce; padding:6px 10px; background:#edf2f7; border-radius:4px; user-select:none;">show / hide raw transcript</summary>
            <pre style="font-family:'SF Mono', Menlo, monospace; font-size:11px; line-height:1.5; padding:10px 14px; background:#1a202c; color:#cbd5e0; border-radius:4px; max-height:400px; overflow:auto; white-space:pre-wrap; margin-top:6px;">${_esc(transcript)}</pre>
        </details>`;
    } else {
        html += `<div style="color:#a0aec0; font-style:italic; font-size:12px; padding:6px 10px;">No transcript pasted yet for this round.</div>`;
    }

    return html;
}

function render_completeness(frm) {
    const wrap = frm.get_field('completeness_html');
    if (!wrap || !wrap.$wrapper) return;
    const snaps = (frm.doc.coverage_snapshots || [])
        .slice()
        .sort((a, b) => (a.after_round || 0) - (b.after_round || 0));
    if (!snaps.length) {
        wrap.$wrapper.html(`<div style="padding:14px; background:#f7fafc; border:1px dashed #cbd5e0; border-radius:6px; font-size:12px; color:#718096;">
            Run <strong>AI → Score Coverage</strong> after at least one round to see the end-to-end completeness check across each in-scope business flow.
        </div>`);
        return;
    }
    const latest = snaps[snaps.length - 1];
    let flows = [];
    try { flows = JSON.parse(latest.process_completeness_json || '[]'); }
    catch (e) { flows = []; }

    const ready = !!latest.end_to_end_ready;
    const min_pct = latest.min_flow_completeness_pct || 0;
    const banner_color = ready ? '#2dd36f' : (min_pct >= 60 ? '#ed8936' : '#eb445a');
    const banner_text = ready
        ? `✓ End-to-end ready — every in-scope flow is ≥90%. Compile SOP is unlocked.`
        : `⏳ Not yet end-to-end ready — lowest flow completeness is ${min_pct}%. Generate more rounds to drive every flow to ≥90% before compiling.`;

    let html = `<div style="margin-bottom:12px; padding:10px 14px; background:${banner_color}; color:#fff; border-radius:6px; font-size:13px; font-weight:600;">${banner_text}</div>`;

    if (!flows.length) {
        html += `<div style="padding:10px 14px; background:#f7fafc; border:1px dashed #cbd5e0; border-radius:6px; font-size:12px; color:#718096;">No flow definitions matched this engagement's industry + module scope. Check flows.py if expected.</div>`;
        wrap.$wrapper.html(html);
        return;
    }

    flows.forEach(f => {
        const pct = parseInt(f.completeness_pct || 0, 10);
        const flow_color = pct >= 90 ? '#2dd36f' : (pct >= 60 ? '#ed8936' : '#eb445a');
        html += `<details style="margin-bottom:10px; border:1px solid #e2e8f0; border-radius:6px; overflow:hidden;" ${pct >= 90 ? '' : 'open'}>
            <summary style="cursor:pointer; padding:10px 14px; background:#fff; user-select:none; display:flex; justify-content:space-between; align-items:center;">
                <div style="font-size:13px; font-weight:600; color:#1a202c;">
                    ${_esc(f.flow_id)} <span style="color:#4a5568; font-weight:500;">— ${_esc(f.flow_name || '')}</span>
                </div>
                <div style="display:flex; gap:8px; align-items:center;">
                    <div style="width:120px; height:8px; background:#edf2f7; border-radius:4px; overflow:hidden;">
                        <div style="width:${pct}%; height:100%; background:${flow_color};"></div>
                    </div>
                    <span style="font-size:13px; font-weight:700; color:${flow_color}; min-width:42px; text-align:right;">${pct}%</span>
                </div>
            </summary>
            <div style="padding:8px 14px; background:#f7fafc; border-top:1px solid #e2e8f0;">`;
        (f.links || []).forEach(L => {
            const status = (L.status || '').toLowerCase();
            const dot = status === 'covered' ? '🟢'
                      : status === 'partial' ? '🟡'
                      : status === 'missing' ? '🔴'
                      : '⚪';
            const status_color = status === 'covered' ? '#2dd36f'
                               : status === 'partial' ? '#ed8936'
                               : status === 'missing' ? '#eb445a'
                               : '#a0aec0';
            html += `<div style="margin:6px 0; padding:6px 10px; background:#fff; border-radius:4px; border-left:3px solid ${status_color};">
                <div style="font-size:12px; color:#1a202c;">
                    <span style="margin-right:6px;">${dot}</span>
                    <strong>${_esc(L.link || '')}</strong>
                    <span style="color:#718096; margin-left:6px; font-weight:500; text-transform:uppercase; font-size:10px; letter-spacing:0.5px;">${_esc(L.status || '')}</span>
                </div>`;
            if (L.evidence) {
                html += `<div style="font-size:11px; color:#4a5568; margin-top:3px; padding-left:22px;">↳ evidence: ${_esc(L.evidence)}</div>`;
            }
            if (L.missing) {
                html += `<div style="font-size:11px; color:#9c4221; margin-top:3px; padding-left:22px; font-style:italic;">⚠ missing: ${_esc(L.missing)}</div>`;
            }
            html += `</div>`;
        });
        html += `</div></details>`;
    });

    wrap.$wrapper.html(html);
}

function render_qa_review(frm) {
    const wrap = frm.get_field('qa_review_html');
    if (!wrap || !wrap.$wrapper) return;
    wrap.$wrapper.html('<div class="text-muted" style="padding:8px;">Loading rounds…</div>');

    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "SOP Round Question",
            filters: {engagement: frm.doc.name},
            fields: ["name", "round_number", "question_id", "module_code", "sop_section",
                     "goal_tags", "is_impromptu", "answer_quality",
                     "question_text", "why_now", "expected_answer_shape",
                     "answer", "evidence_quote"],
            order_by: "round_number asc, is_impromptu asc, question_id asc",
            limit_page_length: 0
        },
        callback: (r) => {
            const qs = r.message || [];
            const rounds = (frm.doc.rounds || []).slice().sort((a,b) => +a.round_number - +b.round_number);

            if (!rounds.length && !qs.length) {
                wrap.$wrapper.html('<div class="text-muted" style="padding:8px;">No rounds yet. Use AI → Generate Round 1 to start.</div>');
                return;
            }

            // Group questions by round
            const byRound = {};
            qs.forEach(q => {
                const rn = q.round_number || 1;
                (byRound[rn] = byRound[rn] || []).push(q);
            });

            // Build per-round metadata: date, status, transcript, extras
            const round_meta = {};
            rounds.forEach(rd => {
                let extras = [];
                if (rd.extra_observations) {
                    try { extras = JSON.parse(rd.extra_observations) || []; }
                    catch (e) { extras = []; }
                }
                round_meta[rd.round_number] = {
                    status: rd.status,
                    date: rd.round_date,
                    transcript: rd.transcript,
                    extras: extras,
                };
            });

            // Round numbers we'll show tabs for — union of rounds-table + question-table sources
            const round_nums = Array.from(new Set([
                ...rounds.map(r => +r.round_number),
                ...Object.keys(byRound).map(n => +n)
            ])).sort((a,b) => a - b);

            // Default active = the latest round with a transcript, else latest round, else 1
            let active_rn = round_nums[round_nums.length - 1] || 1;
            for (const rn of round_nums.slice().reverse()) {
                if (round_meta[rn] && (round_meta[rn].transcript || '').trim()) { active_rn = rn; break; }
            }

            // Tab navigation
            let html = `<div style="display:flex; gap:4px; border-bottom:2px solid #e2e8f0; margin-bottom:12px; flex-wrap:wrap;">`;
            round_nums.forEach(rn => {
                const meta = round_meta[rn] || {};
                const status = meta.status || 'Pending';
                const status_color = (status === 'Answered') ? '#2dd36f'
                                   : (status === 'Processing') ? '#ed8936'
                                   : (status === 'Failed') ? '#eb445a'
                                   : '#a0aec0';
                const is_active = rn === active_rn;
                html += `<button class="sop-round-tab" data-rn="${rn}"
                    style="padding:8px 16px; border:none; border-bottom:3px solid ${is_active ? '#3182ce' : 'transparent'};
                           background:${is_active ? '#fff' : 'transparent'}; cursor:pointer;
                           font-size:13px; font-weight:${is_active ? '700' : '500'};
                           color:${is_active ? '#1a202c' : '#4a5568'}; outline:none; position:relative; top:2px;">
                    Round ${rn}
                    <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${status_color}; margin-left:6px; vertical-align:middle;"></span>
                </button>`;
            });
            html += `</div>`;

            // Tab panels (one per round)
            round_nums.forEach(rn => {
                const round_qs = byRound[rn] || [];
                const meta = round_meta[rn] || {extras: []};
                html += `<div class="sop-round-panel" data-rn="${rn}" style="display:${rn === active_rn ? 'block' : 'none'};">`;
                html += _round_panel(rn, round_qs, meta);
                html += `</div>`;
            });

            wrap.$wrapper.html(html);

            // Wire up tab clicks
            wrap.$wrapper.find('.sop-round-tab').on('click', function() {
                const rn = parseInt($(this).attr('data-rn'), 10);
                wrap.$wrapper.find('.sop-round-tab').each(function() {
                    const this_rn = parseInt($(this).attr('data-rn'), 10);
                    const is_active = this_rn === rn;
                    $(this).css({
                        'border-bottom': '3px solid ' + (is_active ? '#3182ce' : 'transparent'),
                        'background': is_active ? '#fff' : 'transparent',
                        'font-weight': is_active ? '700' : '500',
                        'color': is_active ? '#1a202c' : '#4a5568'
                    });
                });
                wrap.$wrapper.find('.sop-round-panel').hide();
                wrap.$wrapper.find(`.sop-round-panel[data-rn="${rn}"]`).show();
            });
        }
    });
}



frappe.ui.form.on('SOP Discovery Engagement', {
    refresh(frm) {
        if (frm.is_new()) return;

        // View Questions — primary navigation to the proper list view
        frm.add_custom_button(__('View Questions'), () => {
            frappe.set_route('List', 'SOP Round Question', {engagement: frm.doc.name});
        });

        // Render the inline Q&A review HTML
        render_qa_review(frm);

        // Render the process-completeness panel (end-to-end readiness check)
        render_completeness(frm);

        // If a round is mid-Processing (e.g. user reloaded the page during a
        // long job), auto-resume the live progress badge + poller.
        maybe_resume_polling(frm);

        // Round 1 / Next Round
        const round_label = (frm.doc.rounds && frm.doc.rounds.length)
            ? __('Generate Next Round')
            : __('Generate Round 1');

        frm.add_custom_button(round_label, () => {
            frappe.prompt(
                [
                    {fieldname: 'target_round_size', label: 'Number of questions', fieldtype: 'Int', default: 18, reqd: 1},
                    {fieldname: 'focus_hint', label: 'Focus hint (optional)', fieldtype: 'Small Text',
                     description: 'e.g. "deep on procurement, skip HR"'}
                ],
                (values) => {
                    frm.call('generate_round', values).then((r) => {
                        if (r.message && r.message.queued) {
                            start_background_generation(frm, r.message.round_number);
                        }
                    });
                },
                __('Generate discovery round'),
                __('Generate')
            );
        }, __('AI'));

        // Paste Transcript — quick dialog to paste + optionally process in one go
        if (frm.doc.rounds && frm.doc.rounds.length) {
            const latest_round = frm.doc.rounds.reduce(
                (acc, r) => (r.round_number > (acc.round_number || 0) ? r : acc),
                frm.doc.rounds[0]
            );
            frm.add_custom_button(__('Paste Transcript ({0})', ['R' + latest_round.round_number]), () => {
                const round_options = frm.doc.rounds
                    .map(r => `${r.round_number}\t(${r.status || 'Generated'})`)
                    .join('\n');
                frappe.prompt(
                    [
                        {
                            fieldname: 'round_pick', label: 'Round', fieldtype: 'Select',
                            options: frm.doc.rounds.map(r => String(r.round_number)).join('\n'),
                            default: String(latest_round.round_number), reqd: 1
                        },
                        {
                            fieldname: 'transcript', label: 'Paste meeting transcript here',
                            fieldtype: 'Text Editor', reqd: 1,
                            default: latest_round.transcript || '',
                            description: 'Paste the full meeting transcript. Long pastes are fine — even 30K+ chars.'
                        },
                        {
                            fieldname: 'process_now', label: 'Process with AI immediately after saving',
                            fieldtype: 'Check', default: 1,
                            description: 'Map answers + capture impromptu Q&A (60-180s)'
                        }
                    ],
                    (values) => {
                        // Save transcript to the chosen round
                        const target_rn = parseInt(values.round_pick, 10);
                        const round_doc = frm.doc.rounds.find(r => r.round_number == target_rn);
                        // Strip HTML — Text Editor returns HTML, we want plain text
                        const stripped = (values.transcript || '').replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
                        frappe.model.set_value(round_doc.doctype, round_doc.name, 'transcript', stripped);
                        frm.save().then(() => {
                            if (values.process_now) {
                                frm.call('process_transcript', {round_number: target_rn}).then((r) => {
                                    if (r.message && r.message.queued) {
                                        start_background_process(frm, r.message.round_number);
                                    }
                                });
                            } else {
                                frappe.show_alert({message: __('Transcript saved.'), indicator: 'green'});
                                frm.reload_doc();
                            }
                        });
                    },
                    __('Paste meeting transcript'),
                    __('Save')
                );
            }, __('AI'));
        }

        // Process Transcript — only if at least one round has a transcript (kept as backup)
        const round_with_transcript = (frm.doc.rounds || []).find(r => (r.transcript || '').trim().length > 0);
        if (round_with_transcript) {
            frm.add_custom_button(__('Process Transcript (Round {0})', [round_with_transcript.round_number]), () => {
                frm.call('process_transcript', {round_number: round_with_transcript.round_number}).then((r) => {
                    if (r.message && r.message.queued) {
                        start_background_process(frm, r.message.round_number);
                    }
                });
            }, __('AI'));
        }

        // Score coverage
        if (frm.doc.rounds && frm.doc.rounds.length) {
            frm.add_custom_button(__('Score Coverage'), () => {
                frm.call('score_coverage').then((r) => {
                    if (r.message && r.message.queued) {
                        start_background_score_coverage(frm);
                    }
                });
            }, __('AI'));
        }

        // Compile SOP
        if (frm.doc.rounds && frm.doc.rounds.length) {
            frm.add_custom_button(__('Compile SOP'), () => {
                frappe.prompt(
                    [{
                        fieldname: 'output_for', label: 'Compile for',
                        fieldtype: 'Select',
                        options: 'process_improvement\ncost\nerp\ncombined',
                        default: 'process_improvement', reqd: 1
                    }],
                    (values) => {
                        frm.call('compile_sop', values).then((r) => {
                            if (r.message && r.message.queued) {
                                start_background_compile(frm);
                            }
                        });
                    },
                    __('Compile SOP'),
                    __('Compile')
                );
            }, __('AI'));
        }

        // Re-compile SOP with consultant edits — only show if there are edits to merge
        if (frm.doc.compiled_sop && (frm.doc.consultant_edits || '').trim()) {
            frm.add_custom_button(__('Re-compile with my edits'), () => {
                frappe.confirm(
                    __('Re-compile the SOP, merging your consultant edits with the prior draft? Compile usually takes 2-4 min in background.'),
                    () => {
                        frm.call('compile_sop', {output_for: frm.doc.compiled_output_for || 'process_improvement'}).then((r) => {
                            if (r.message && r.message.queued) {
                                start_background_compile(frm);
                            }
                        });
                    }
                );
            }, __('AI'));
        }

        // Save consultant lessons to permanent memory
        if ((frm.doc.consultant_lessons || '').trim()) {
            frm.add_custom_button(__('Save lessons to memory'), () => {
                frm.call('save_lessons_to_memory').then((r) => {
                    if (r.message && r.message.ok) {
                        const m = r.message;
                        frappe.show_alert({
                            message: __('Saved {0} lesson(s) to {1}. Future engagements will load these.',
                                        [m.lessons_saved, m.memory_file]),
                            indicator: 'green'
                        }, 8);
                        frm.reload_doc();
                    }
                });
            }, __('AI'));
        }

        // Reflect
        if (frm.doc.compiled_sop) {
            frm.add_custom_button(__('Reflect & Improve'), () => {
                frm.call('reflect').then((r) => {
                    if (r.message && r.message.queued) {
                        start_background_reflect(frm);
                    }
                });
            }, __('AI'));
        }
    }
});
