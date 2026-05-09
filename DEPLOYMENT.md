# Deployment Runbook — `office_customizations` → `sevenlabs.m.erpnext.com`

**Last refreshed:** 2026-05-09 (covers task-board mandatory rules + Variant B mobile UI for /my-tasks + SOP Discovery Engagement system + WhatsApp/Telegram integration scaffolding)

---

## What's being deployed (high level)

### A. Mandatory rules on every task creation path
Every "create task" UI surface now blocks save unless **both** End Date and Assigned To are filled. The auto-assign-to-creator `after_insert` hook stays as a defensive backstop for any non-UI code path (server scripts, direct API).

| Surface | Required fields |
|---|---|
| `/my-tasks` → "+ Add Task" | Subject, Project, **Assigned To**, **End Date** |
| Master Task Board → "+ Add Task" (3 modals: global / project / list) | Task Name, Project, **Assigned To**, **End Date** |
| Master Task Board → "+Sub" (subtask) | Subtask Name, **Assigned To**, **End Date** |
| Project Task Board → "Add Task" / "Add Task to <list>" / "+Sub" | Task Name, **Assigned To**, **End Date** |
| Standard Frappe form `/app/task/new` | Subject, **End Date** (assignee covered by `after_insert` hook) |

Server-side belt-and-braces:
- Property Setter `Task.exp_end_date.reqd=1` — End Date required on every save path (form, API, batch import, scheduler scripts)
- `task_events.after_insert` — auto-assigns the creator within ~2s if no `_assign` value, so unassigned tasks cannot persist even if a code path bypasses UI validation
- `task_events.on_update` — sends the existing assignment notifications

### B. /my-tasks page redesign — Variant B
- Click 💬 → drawer expands inline below the row with the full comment thread (chat-bubble layout, coloured initial-avatars per author, timestamps) and a reply box
- Progress column hidden; Start Date kept; status/priority pills coloured; subtasks have blue ↳ + soft-blue left border
- New `?mobile=1` query param wraps the page in a 390px frame and force-promotes `@media (max-width:768px)` rules — useful for inspecting the mobile layout from any desktop browser without resizing the window

### C. SOP Discovery Engagement system (new module)
Custom DocTypes for capturing the multi-round discovery process when scoping a new client engagement (System / Module / Goal options, round questions, coverage snapshots). Plus `after_migrate` seeder that pre-populates the option lists on first install.

### D. WhatsApp / Telegram inbound integration scaffolding
DocTypes to map inbound WhatsApp / Telegram messages to projects + a lightweight settings store. Wires up via `app_include_js = quick_task.js` and `office_customisation/whatsapp/api.py`.

---

## Pre-deploy: live state verified clean

A 2026-05-09 survey via the API confirmed **no drift on live since the Apr 25 last-sync commit**:
- Custom Field — 0 modified after 2026-04-25
- Property Setter — 0 modified after 2026-04-25
- Client Script — 0 modified after 2026-04-25
- Web Page — 0 modified after 2026-04-25

Live's Web Pages (`my-tasks`, `master-task-board`, `team-dashboard`) are pure-stale relative to the local versions — no risk of overwriting unsynced UI customizations.

**One known live anomaly to clean up post-deploy:**
- `Property Setter "Task-exp_end_date-permlevel" = 1` exists on live. This was the rogue setter that locks End Date for non-admins. Removed from local fixtures already; needs explicit deletion on live (covered in step 4 below).

---

## Deploy steps

### 1. Push to GitHub
```bash
cd "Claude WORKSPACE/projects/erpnext/stacks/slv/custom-apps/office_customizations"
git push origin main
```

### 2. Pull + migrate on Frappe Cloud
Frappe Cloud → Sites → sevenlabs.m.erpnext.com → Apps → office_customizations → "Update Available" → click. This:
- Pulls latest from GitHub
- Runs `bench --site sevenlabs.m.erpnext.com migrate` (which installs the new SOP / WhatsApp DocTypes and re-imports `fixtures/*.json`)
- Restarts workers

### 3. Run the patch scripts (one-time, idempotent)
Frappe Cloud → site → "Bench Console" → paste:

```python
import office_customizations._patch_task_required_v1 as p; p.run()
import office_customizations._patch_mtb_v1 as p; p.run()
import office_customizations._patch_mtb_required_v2 as p; p.run()
import office_customizations._patch_mytasks_employee_v1 as p; p.run()
import office_customizations._patch_assignee_optional_v1 as p; p.run()
import office_customizations._patch_end_date_required_v2 as p; p.run()
import office_customizations._patch_subtask_modal_v3 as p; p.run()
import office_customizations._patch_mytasks_addtask_v3 as p; p.run()
import office_customizations._patch_mytasks_variant_b_v1 as p; p.run()
import office_customizations._patch_disable_project_clientscript_v1 as p; p.run()
```

Each script is idempotent (safe to re-run if a step fails or the migrate clobbers a Web Page JS field). Order matters only insofar as `_patch_disable_project_clientscript_v1` must come last so the new `project_task_board.js` from the doctype_js hook actually wins.

### 4. Delete the rogue Property Setter
Same Bench Console:
```python
frappe.db.delete("Property Setter", {"name": "Task-exp_end_date-permlevel"})
frappe.db.commit()
```

### 5. Re-export fixtures on live (optional but recommended)
Captures the just-applied Web Page customisations back into the fixture JSONs so future migrates don't revert them. Frappe Cloud usually doesn't allow `bench export-fixtures` directly — instead, run `_rebuild_web_page_fixtures.py` from the Bench Console:
```python
import office_customizations._rebuild_web_page_fixtures as p; p.run()
```
Then commit the regenerated `fixtures/web_page.json` back to GitHub (next push). Frappe Cloud will pick it up on the next migrate.

### 6. Clear caches + restart
```python
frappe.clear_cache()
frappe.clear_website_cache()
```
And tell users to hard-reload (Cmd+Shift+R / Ctrl+Shift+R) once. Frappe inlines `doctype_js` into the meta response which browsers cache aggressively.

---

## Hetzner Telegram bot (if deploying bot changes too)
```bash
ssh root@65.109.169.102
cd /root/slv-bot/      # or wherever it lives
git pull               # if version-controlled
systemctl restart slv-bot
journalctl -u slv-bot -n 50 -f
```

---

## Post-deploy smoke test (5 min)

1. **Standard Frappe form** `/app/task/new`:
   - Save without End Date → blocked with mandatory error
   - Save with End Date but no Assigned To → goes through, then within ~3s the creator is auto-assigned (visible in the Assigned to field)

2. **Master Task Board** `/master-task-board`:
   - Click `+ Add Task`. Both `End Date *` and `Assigned To *` should be marked required
   - Submit without filling them → "Please fill required fields" alert, modal stays open
   - Click `+Sub` on any task → subtask modal shows the same `*` markers

3. **Project Task Board** (open any project, scroll to Task Board section):
   - Click `Add Task` → modal shows `Task Name` `Assigned To` `End Date` all marked `*`
   - Submit blank → Frappe pops "Missing Values Required: Assigned To, End Date"

4. **/my-tasks** page (any team member):
   - Click `+ Add Task` → Task Name / Project / Assigned To / End Date all marked `*`
   - Submit blank → assignee + end-date borders go red, "Please fill required fields" alert
   - Click 💬 on a task with comments → drawer expands with chat-bubble thread, reply box at the bottom
   - Mobile preview: navigate to `/my-tasks?mobile=1` from a desktop browser → page renders in a 390px-wide phone frame with the responsive layout, persists on reload

5. **SOP Discovery Engagement** `/app/sop-discovery-engagement/new`:
   - Form should render. Option lists (System / Module / Goal) should be pre-seeded by the `after_migrate` hook

---

## Files changed in this deploy

### Server-side
- `office_customizations/hooks.py` — added `Project` doctype_js, `SOP Discovery Engagement` doctype_js, `app_include_js`/`web_include_js` for quick_task, `after_migrate` seeder
- `office_customizations/office_customisation/doc_events/task_events.py` — `after_insert` auto-assign-to-creator + assignment-notification updates
- `office_customizations/office_customisation/setup/seed_sop_options.py` — pre-populates SOP option lists
- `office_customizations/office_customisation/whatsapp/api.py` — inbound WhatsApp endpoint stubs

### DocTypes (new)
- `sop_coverage_snapshot`, `sop_discovery_engagement`, `sop_discovery_round`, `sop_engagement_goal`, `sop_engagement_module`, `sop_engagement_system`, `sop_goal_option`, `sop_module_option`, `sop_round_question`, `sop_system_option`
- `task_list`, `telegram_group_mapping`, `whatsapp_message`, `whatsapp_project_mapping`, `whatsapp_settings`

### Front-end
- `office_customizations/public/js/project_task_board.js` — assigned_to now `reqd:1` on all 3 modals
- `office_customizations/public/js/quick_task.js` — global Quick Task helper
- `office_customizations/public/js/sop_discovery_engagement.js` — SOP form button injections
- `office_customizations/public/js/task_dashboard/` — task dashboard component bundle

### Patch scripts (idempotent — run on Bench Console after deploy)
- `_patch_task_required_v1.py` — Property Setter `Task.exp_end_date.reqd=1` + Client Script blocking save without assignee
- `_patch_mtb_v1.py` — Master Task Board: marks subject + end_date as `required:true` in 3 task-creation modals; expands subtask modal
- `_patch_mtb_required_v2.py` — Master Task Board: assigned_to also `required:true` (May 9 update)
- `_patch_mytasks_employee_v1.py` — wraps the Employee xcall in a safe Promise so non-admin /my-tasks doesn't 403
- `_patch_assignee_optional_v1.py` — flips `required:true` → optional on assigned_to where the auto-assign hook covers it (superseded by v2 above; kept for historical idempotency)
- `_patch_end_date_required_v2.py` — corrective patch for End Date required
- `_patch_subtask_modal_v3.py` — restores expanded subtask modal with End Date + Assigned To
- `_patch_mytasks_addtask_v3.py` — adds + Add Task button + HTML modal to /my-tasks Web Page; assignee marked required
- `_patch_mytasks_variant_b_v1.py` — Variant B drawer styling for /my-tasks (chat-bubble comments, coloured avatars, mobile 390px frame, hidden Progress column)
- `_patch_disable_project_clientscript_v1.py` — disables the stale duplicate "Project" Client Script (28KB) so doctype_js wins

### Fixtures (will re-import on `bench migrate`)
- `fixtures/web_page.json` — `my-tasks` + `master-task-board` Web Pages with the latest JS/main_section_html
- `fixtures/property_setter.json` — `Task.exp_end_date.reqd=1`, rogue permlevel removed
- `fixtures/client_script.json` — adjustments for assignee handling

---

## Rollback

If something breaks:
1. **Property Setter**: delete `Task-exp_end_date-reqd` via Bench Console to lift the End Date requirement; existing tasks are not affected
2. **after_insert hook**: edit `task_events.py::after_insert` to `return` immediately and run `bench restart`; existing assignments stay
3. **Web Page JS**: each `_patch_*.py` script has a corresponding earlier version in git; you can `git checkout` and re-run to restore an older modal layout
4. **DocTypes**: SOP and WhatsApp DocTypes are new — they can be uninstalled by removing them from `hooks.py` `fixtures` block and running `bench --site <site> remove-from-installed-apps office_customizations` (NOT recommended; prefer fixing forward)
