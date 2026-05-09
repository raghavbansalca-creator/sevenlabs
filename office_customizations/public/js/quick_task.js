/**
 * Quick Task — Global Floating Action Button
 *
 * Adds a "+" FAB on every desk page + Ctrl+Shift+T shortcut.
 * Opens a minimal dialog to create a task in < 5 seconds.
 * Auto-detects project context if user is on a Project form.
 *
 * Part of office_customizations app — loaded via app_include_js.
 */

(function () {
	"use strict";

	// Prevent double-init
	if (window.__slv_quick_task_loaded) return;
	window.__slv_quick_task_loaded = true;

	// ─── CONFIG ───────────────────────────────────────────────
	const FAB_SIZE = 48;
	const FAB_SIZE_MOBILE = 56; // Larger touch target on mobile
	const FAB_BOTTOM = 24;
	const FAB_RIGHT = 24;
	const SHORTCUT_KEY = "T"; // Ctrl+Shift+T

	function is_mobile() {
		return window.innerWidth <= 768;
	}

	// ─── INJECT FAB ──────────────────────────────────────────
	function inject_fab() {
		if (document.getElementById("slv-quick-task-fab")) return;

		const fab = document.createElement("button");
		fab.id = "slv-quick-task-fab";
		fab.title = "Quick Task (Ctrl+Shift+T)";

		var size = is_mobile() ? FAB_SIZE_MOBILE : FAB_SIZE;
		var iconSize = is_mobile() ? 26 : 22;
		fab.innerHTML = '<svg width="' + iconSize + '" height="' + iconSize + '" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>';

		Object.assign(fab.style, {
			position: "fixed",
			bottom: FAB_BOTTOM + "px",
			right: FAB_RIGHT + "px",
			width: size + "px",
			height: size + "px",
			borderRadius: "50%",
			background: "linear-gradient(135deg, #2490EF 0%, #1B6FD1 100%)",
			border: "none",
			boxShadow: "0 4px 14px rgba(36,144,239,0.4)",
			cursor: "pointer",
			zIndex: "1050",
			display: "flex",
			alignItems: "center",
			justifyContent: "center",
			transition: "transform 0.15s ease, box-shadow 0.15s ease",
			// Mobile: prevent iOS tap highlight and ensure touch works
			WebkitTapHighlightColor: "transparent",
			touchAction: "manipulation",
		});

		fab.addEventListener("mouseenter", function () {
			fab.style.transform = "scale(1.1)";
			fab.style.boxShadow = "0 6px 20px rgba(36,144,239,0.55)";
		});
		fab.addEventListener("mouseleave", function () {
			fab.style.transform = "scale(1)";
			fab.style.boxShadow = "0 4px 14px rgba(36,144,239,0.4)";
		});

		fab.addEventListener("click", open_quick_task_dialog);
		document.body.appendChild(fab);
	}

	// ─── KEYBOARD SHORTCUT ───────────────────────────────────
	document.addEventListener("keydown", function (e) {
		if (e.ctrlKey && e.shiftKey && e.key === SHORTCUT_KEY) {
			e.preventDefault();
			open_quick_task_dialog();
		}
	});

	// ─── AUTO-DETECT CONTEXT ─────────────────────────────────
	function detect_project() {
		// If user is on a Project form, grab the project name
		if (
			cur_frm &&
			cur_frm.doctype === "Project" &&
			cur_frm.doc.name
		) {
			return cur_frm.doc.name;
		}
		// If user is on a Task form, grab the task's project
		if (
			cur_frm &&
			cur_frm.doctype === "Task" &&
			cur_frm.doc.project
		) {
			return cur_frm.doc.project;
		}
		return "";
	}

	// ─── QUICK TASK DIALOG ──────────────────────────────────
	function open_quick_task_dialog() {
		const detected_project = detect_project();

		const d = new frappe.ui.Dialog({
			title: "Quick Task",
			size: "small",
			fields: [
				{
					fieldname: "subject",
					fieldtype: "Data",
					label: "What needs to be done?",
					reqd: 1,
					placeholder: "e.g. File GSTR-1 for Cona",
				},
				{
					fieldtype: "Column Break",
				},
				{
					fieldname: "project",
					fieldtype: "Link",
					label: "Project",
					options: "Project",
					reqd: 1,
					default: detected_project,
					placeholder: "Select project...",
				},
				{
					fieldtype: "Section Break",
				},
				{
					fieldname: "priority",
					fieldtype: "Select",
					label: "Priority",
					options: "Low\nMedium\nHigh\nUrgent",
					default: "Medium",
				},
				{
					fieldtype: "Column Break",
				},
				{
					fieldname: "exp_end_date",
					fieldtype: "Date",
					label: "Due Date",
				},
				{
					fieldtype: "Section Break",
				},
				{
					fieldname: "assigned_to",
					fieldtype: "Link",
					label: "Assign To",
					options: "User",
					default: frappe.session.user,
				},
				{
					fieldtype: "Column Break",
				},
				{
					fieldname: "parent_task",
					fieldtype: "Link",
					label: "Parent Task",
					options: "Task",
					depends_on: "project",
					get_query: function () {
						var project = d.get_value("project");
						return {
							filters: {
								project: project,
								is_group: 1,
							},
						};
					},
				},
				{
					fieldtype: "Section Break",
				},
				{
					fieldname: "description",
					fieldtype: "Small Text",
					label: "Notes (optional)",
					placeholder: "Any extra context...",
				},
			],
			primary_action_label: "Create Task",
			primary_action: function (values) {
				create_task(d, values);
			},
		});

		// Focus the subject field immediately
		d.show();
		setTimeout(function () {
			d.fields_dict.subject.$input.focus();
		}, 200);

		// Allow Enter key on subject to submit (quick fire)
		d.fields_dict.subject.$input.on("keydown", function (e) {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				var values = d.get_values();
				if (values && values.subject) {
					create_task(d, values);
				}
			}
		});
	}

	// ─── CREATE TASK ─────────────────────────────────────────
	function create_task(dialog, values) {
		dialog.disable_primary_action();

		var task_data = {
			doctype: "Task",
			subject: values.subject,
			priority: values.priority || "Medium",
			status: "Open",
		};

		if (values.project) task_data.project = values.project;
		if (values.exp_end_date) task_data.exp_end_date = values.exp_end_date;
		if (values.description) task_data.description = values.description;
		if (values.parent_task) task_data.parent_task = values.parent_task;

		// Set start date to today
		task_data.exp_start_date = frappe.datetime.get_today();

		frappe.xcall("frappe.client.insert", { doc: task_data }).then(function (doc) {
			// Assign if specified
			if (values.assigned_to) {
				return frappe.xcall("frappe.desk.form.assign_to.add", {
					doctype: "Task",
					name: doc.name,
					assign_to: [values.assigned_to],
				}).then(function () {
					return doc;
				});
			}
			return doc;
		}).then(function (doc) {
			dialog.hide();
			frappe.show_alert({
				message: __("Task <b>{0}</b> created", [doc.name]),
				indicator: "green",
			}, 5);

			// Refresh current view if relevant
			if (cur_frm && cur_frm.doctype === "Project" && cur_frm.doc.name === values.project) {
				cur_frm.reload_doc();
			}
			if (cur_list && cur_list.doctype === "Task") {
				cur_list.refresh();
			}
		}).catch(function (err) {
			dialog.enable_primary_action();
			frappe.msgprint({
				title: __("Error"),
				message: __("Could not create task. Please try again."),
				indicator: "red",
			});
			console.error("Quick Task error:", err);
		});
	}

	// ─── RESIZE HANDLER ──────────────────────────────────────
	// Adjust FAB size when switching between desktop/mobile
	window.addEventListener("resize", function () {
		var fab = document.getElementById("slv-quick-task-fab");
		if (!fab) return;
		var size = is_mobile() ? FAB_SIZE_MOBILE : FAB_SIZE;
		var iconSize = is_mobile() ? 26 : 22;
		fab.style.width = size + "px";
		fab.style.height = size + "px";
		fab.innerHTML = '<svg width="' + iconSize + '" height="' + iconSize + '" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>';
	});

	// ─── INIT ────────────────────────────────────────────────
	// Ensure FAB is on EVERY page — desk, portal, list, form, report, etc.
	$(document).ready(function () {
		// Inject FAB after a short delay to ensure desk is loaded
		setTimeout(inject_fab, 500);

		// Re-inject on Frappe SPA navigation (covers all page types)
		$(document).on("page-change", function () {
			setTimeout(inject_fab, 300);
		});

		// Also listen to route-change for list/form/report navigations
		if (frappe.router && frappe.router.on) {
			frappe.router.on("change", function () {
				setTimeout(inject_fab, 300);
			});
		}

		// MutationObserver fallback: if FAB gets removed by any page
		// re-render, re-inject it automatically
		var observer = new MutationObserver(function () {
			if (!document.getElementById("slv-quick-task-fab")) {
				inject_fab();
			}
		});
		observer.observe(document.body, { childList: true, subtree: false });
	});
})();
