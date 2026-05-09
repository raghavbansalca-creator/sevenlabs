"""
SOP Discovery Engagement — parent DocType.

The 4 buttons on the form (Generate Round / Score Coverage / Compile / Reflect)
each call one of the whitelisted methods below. Each method:
  1. Builds the payload from this engagement's data
  2. POSTs to the local SOP-tool FastAPI bridge
  3. Saves the response back into this engagement's child tables

Bridge URL is read from site_config.json key `sop_tool_url`.
Default for local Docker dev: http://host.docker.internal:8090
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import frappe
import requests
from frappe.model.document import Document


def _bridge_url() -> str:
    return frappe.conf.get("sop_tool_url") or "http://host.docker.internal:8090"


def _post_bridge(path: str, payload: dict, timeout: int = 540) -> dict:
    url = _bridge_url().rstrip("/") + path
    try:
        r = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException as e:
        frappe.throw(f"Bridge unreachable at {url}: {e}")
    if r.status_code >= 400:
        frappe.throw(f"Bridge {path} returned HTTP {r.status_code}: {r.text[:1000]}")
    return r.json()


def _csv(val) -> list[str]:
    if not val:
        return []
    return [s.strip() for s in val.split(",") if s.strip()]


def _multiselect_values(rows: list, link_field: str) -> list[str]:
    """Pull link values out of a Table MultiSelect child rows list."""
    return [getattr(r, link_field) for r in (rows or []) if getattr(r, link_field, None)]


class SOPDiscoveryEngagement(Document):

    # ───────── intake → bridge payload ─────────

    def _intake_payload(self) -> dict:
        return {
            "client_name": self.client_name,
            "industry": self.industry or "",
            "sub_type": self.sub_type or None,
            "turnover_range": self.turnover_range or None,
            "employee_count": self.employee_count or None,
            "geography": self.geography or None,
            "what_they_sell": self.what_they_sell or None,
            "engagement_goals": _multiselect_values(self.engagement_goals, "goal"),
            "modules_in_scope": _multiselect_values(self.modules_in_scope, "module"),
            "current_systems": _multiselect_values(self.current_systems, "system"),
            "digital_maturity_notes": self.digital_maturity_notes or None,
            "parent_engagement_id": self.parent_engagement,
        }

    def _all_questions(self) -> list:
        """Fetch all SOP Round Question records linked to this engagement, ordered."""
        return frappe.get_all(
            "SOP Round Question",
            filters={"engagement": self.name},
            fields=["name", "round_number", "question_id", "module_code", "sop_section",
                    "goal_tags", "question_text", "why_now", "expected_answer_shape",
                    "answer", "evidence_quote", "answer_quality", "is_impromptu"],
            order_by="round_number asc, is_impromptu asc, question_id asc",
        )

    def _questions_for_round(self, rn: int, include_impromptu: bool = True) -> list:
        qs = self._all_questions()
        return [
            q for q in qs
            if int(q.get("round_number") or 0) == rn
            and (include_impromptu or not q.get("is_impromptu"))
        ]

    def _rounds_payload(self) -> list[dict]:
        """Build the prior_rounds list for the bridge.

        Includes the round's extra_observations and the impromptu Q&A captured
        in that round, so the next round generator can thread-pull on both.
        """
        out = []
        for r in (self.rounds or []):
            rn = int(r.round_number or 0)
            qs = self._questions_for_round(rn)
            impromptu = [q for q in qs if q.get("is_impromptu")]
            extra_obs = []
            if r.extra_observations:
                try:
                    extra_obs = json.loads(r.extra_observations)
                except Exception:
                    extra_obs = []
            out.append({
                "round_number": rn,
                "questions_asked": [q["question_text"] for q in qs if not q.get("is_impromptu")],
                "answers_captured": [(q.get("answer") or "") for q in qs if not q.get("is_impromptu")],
                "impromptu_qa": [
                    {
                        "question": q["question_text"],
                        "answer": q.get("answer") or "",
                        "module_code": q.get("module_code"),
                        "goal_tags": [t.strip() for t in (q.get("goal_tags") or "").split(",") if t.strip()],
                    }
                    for q in impromptu
                ],
                "extra_observations": extra_obs,
                "free_text_notes": r.free_text_notes or None,
            })
        return out

    # ───────── whitelisted button methods ─────────

    @frappe.whitelist()
    def generate_round(self, target_round_size: int = 18, focus_hint: str = "") -> dict:
        """Enqueue Round generation as a background job. Returns immediately with
        a placeholder round row (status='Generating') so the frontend poller can
        display a live progress badge.
        """
        # Decide the new round number
        rn = max((int(r.round_number or 0) for r in (self.rounds or [])), default=0) + 1

        # Refuse if a generation is already in flight
        for r in (self.rounds or []):
            if r.status == "Generating":
                frappe.throw(f"Round {r.round_number} is currently generating. Wait for it to finish before starting another.")

        # Create placeholder round so the JS poller has something to watch
        self.append("rounds", {
            "round_number": rn,
            "round_date": frappe.utils.nowdate(),
            "conducted_by": frappe.session.user,
            "status": "Generating",
            "processing_stage": "Queued",
            "focus_hint": focus_hint or "",
        })
        if self.status == "Intake":
            self.status = "In Progress"
        self.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.enqueue(
            "office_customizations.office_customisation.doctype.sop_discovery_engagement.sop_discovery_engagement.run_generate_round_job",
            engagement_name=self.name,
            round_number=rn,
            target_round_size=int(target_round_size),
            focus_hint=focus_hint or "",
            queue="long",
            timeout=900,  # 15 min ceiling — generation rarely needs more than 5
            job_name=f"generate_round_{self.name}_R{rn}",
        )
        return {"ok": True, "queued": True, "round_number": rn, "status": "Generating"}

    def _latest_process_completeness(self) -> list | None:
        """Pull the most recent coverage snapshot's process_completeness array, if any."""
        if not self.coverage_snapshots:
            return None
        latest = sorted(self.coverage_snapshots, key=lambda s: int(s.after_round or 0))[-1]
        if not latest.process_completeness_json:
            return None
        try:
            return json.loads(latest.process_completeness_json)
        except Exception:
            return None

    def _do_generate_round(self, round_number: int, target_round_size: int, focus_hint: str) -> dict:
        """Actual generation work, invoked from a background job."""
        rn = int(round_number)
        target_round = next((r for r in self.rounds if int(r.round_number or 0) == rn), None)
        if not target_round:
            raise ValueError(f"Round {rn} placeholder not found on engagement {self.name}")

        self._set_processing_stage(target_round, "Building payload")
        # Build prior_rounds excluding our placeholder (it has no Q&A yet)
        prior = [r for r in self._rounds_payload() if int(r["round_number"]) != rn]
        payload = {
            "intake": self._intake_payload(),
            "prior_rounds": prior,
            "target_round_size": int(target_round_size),
            "focus_hint": focus_hint or None,
            "latest_process_completeness": self._latest_process_completeness(),
        }

        self._set_processing_stage(target_round, "Calling AI (this is the long step)")
        result = _post_bridge("/round/generate", payload, timeout=780)

        self._set_processing_stage(target_round, "Saving questions")
        target_round.rationale = result.get("rationale", "")

        q_count = 0
        for q in result.get("questions", []):
            doc = frappe.get_doc({
                "doctype": "SOP Round Question",
                "engagement": self.name,
                "round_number": rn,
                "question_id": q.get("id"),
                "module_code": q.get("module"),
                "sop_section": q.get("sop_section"),
                "goal_tags": ", ".join(q.get("goal_tags", [])),
                "question_text": q.get("question_text"),
                "why_now": q.get("why_now"),
                "expected_answer_shape": q.get("expected_answer_shape"),
                "answer_quality": "Pending",
                "is_impromptu": 0,
            })
            doc.insert(ignore_permissions=True)
            q_count += 1

        # Direct DB write on the round + the rationale. Avoids the parent
        # engagement save() (race with concurrent jobs).
        frappe.db.set_value("SOP Discovery Round", target_round.name, {
            "status": "Generated",
            "processing_stage": "",
            "processing_error": "",
            "rationale": result.get("rationale", ""),
        }, update_modified=True)
        frappe.db.commit()
        return {"round_number": rn, "questions_count": q_count}

    @frappe.whitelist()
    def process_transcript(self, round_number: int = None) -> dict:
        """Enqueue transcript processing as a background job; return immediately.

        The actual bridge call + write-back happens in `run_process_transcript_job`
        (module-level, queued on the 'long' worker). This avoids tying up the web
        request for minutes — large transcripts can take 5-10+ min to process.

        Frontend polls round.status to detect completion:
            Processing → Answered  (success — answers + impromptu written back)
            Processing → Failed    (processing_error populated with traceback)
        """
        if not self.rounds:
            frappe.throw("No rounds yet — generate Round 1 and capture transcript first.")

        rn = int(round_number) if round_number else max(int(r.round_number or 0) for r in self.rounds)
        target_round = next((r for r in self.rounds if int(r.round_number or 0) == rn), None)
        if not target_round:
            frappe.throw(f"Round {rn} not found.")
        if not (target_round.transcript or "").strip():
            frappe.throw(f"Round {rn} has no transcript. Paste the meeting transcript first.")
        if target_round.status == "Processing":
            frappe.throw(f"Round {rn} is already being processed. Wait for it to finish (or fail) before retrying.")

        # Mark Processing + clear any previous error/stage
        target_round.status = "Processing"
        target_round.processing_stage = "Queued"
        target_round.processing_error = ""
        self.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.enqueue(
            "office_customizations.office_customisation.doctype.sop_discovery_engagement.sop_discovery_engagement.run_process_transcript_job",
            engagement_name=self.name,
            round_number=rn,
            queue="long",
            timeout=1500,  # 25 min ceiling — comfortable for 90-min real meetings
            job_name=f"process_transcript_{self.name}_R{rn}",
        )
        return {"ok": True, "queued": True, "round_number": rn, "status": "Processing"}

    # ───────── job worker (called by frappe.enqueue) ─────────

    def _set_processing_stage(self, round_doc, stage: str) -> None:
        """Update round.processing_stage in DB so frontend poller can show live progress."""
        try:
            frappe.db.set_value(
                "SOP Discovery Round",
                round_doc.name,
                "processing_stage",
                stage,
                update_modified=False,
            )
            frappe.db.commit()
        except Exception:
            # Stage update is decorative — never fail the job because of it
            pass

    def _do_process_transcript(self, round_number: int) -> dict:
        """The actual transcript-processing work, now invoked from a background job."""
        rn = int(round_number)
        target_round = next((r for r in self.rounds if int(r.round_number or 0) == rn), None)
        if not target_round:
            raise ValueError(f"Round {rn} not found on engagement {self.name}")

        self._set_processing_stage(target_round, "Building payload")
        all_qs = self._questions_for_round(rn, include_impromptu=False)
        original_qs = [
            {
                "question_id": q["question_id"],
                "module_code": q["module_code"],
                "sop_section": q["sop_section"],
                "goal_tags": [t.strip() for t in (q.get("goal_tags") or "").split(",") if t.strip()],
                "question_text": q["question_text"],
                "expected_answer_shape": q.get("expected_answer_shape") or "",
            }
            for q in all_qs
        ]
        payload = {
            "intake": self._intake_payload(),
            "original_questions": original_qs,
            "transcript": target_round.transcript,
        }
        # Generous bridge timeout — claude can take 5-10 min on a 90-min transcript
        self._set_processing_stage(target_round, "Calling AI (this is the long step)")
        result = _post_bridge("/round/process_transcript", payload, timeout=1320)

        self._set_processing_stage(target_round, "Writing answers")
        answered_map = {a["question_id"]: a for a in (result.get("answered_questions") or [])}
        updated = 0
        for q in all_qs:
            a = answered_map.get(q["question_id"])
            if not a:
                continue
            frappe.db.set_value("SOP Round Question", q["name"], {
                "answer": a.get("answer") or "",
                "evidence_quote": a.get("evidence_quote") or "",
                "answer_quality": a.get("answer_quality") or "Pending",
            }, update_modified=True)
            updated += 1

        self._set_processing_stage(target_round, "Adding impromptu Q&A")
        existing_imp_ids = {
            q["question_id"]
            for q in self._all_questions()
            if q.get("is_impromptu")
        }
        impromptu_added = 0
        next_idx = 1
        for i in result.get("impromptu_qa") or []:
            while f"i{next_idx}" in existing_imp_ids:
                next_idx += 1
            qid = f"i{next_idx}"
            existing_imp_ids.add(qid)
            doc = frappe.get_doc({
                "doctype": "SOP Round Question",
                "engagement": self.name,
                "round_number": rn,
                "question_id": qid,
                "module_code": i.get("module_code"),
                "sop_section": i.get("sop_section"),
                "goal_tags": ", ".join(i.get("goal_tags") or []),
                "question_text": i.get("question_text"),
                "answer": i.get("answer"),
                "evidence_quote": i.get("evidence_quote"),
                "answer_quality": i.get("answer_quality") or "Pending",
                "is_impromptu": 1,
            })
            doc.insert(ignore_permissions=True)
            impromptu_added += 1
            next_idx += 1

        # Persist extra in-scope observations (volunteered facts that aren't Q&A).
        # Stored as JSON on the round so JS + downstream Round 2 generator can
        # both consume them.
        extras = result.get("extra_observations") or []
        extras_json = json.dumps(extras, indent=2, ensure_ascii=False) if extras else ""

        # Direct DB write on the round — avoids self.save() on the parent
        # engagement, which would race with concurrent Score Coverage / user
        # edits and throw TimestampMismatchError. We commit per-row instead.
        frappe.db.set_value("SOP Discovery Round", target_round.name, {
            "extra_observations": extras_json,
            "status": "Answered",
            "transcript_processed_at": datetime.now(),
            "processing_error": "",
            "processing_stage": "",
        }, update_modified=True)
        frappe.db.commit()
        return {
            "round_number": rn,
            "answered_count": updated,
            "unanswered_count": len(result.get("unanswered_question_ids") or []),
            "impromptu_added": impromptu_added,
            "extra_observations_count": len(extras),
            "out_of_scope_count": len(result.get("out_of_scope_observations") or []),
            "summary": result.get("summary"),
        }

    # ───────── score_coverage (async) ─────────

    def _set_engagement_stage(self, stage_field: str, stage: str) -> None:
        """Update engagement-level processing_stage in DB so frontend poller
        can show live progress. Best-effort — never fails the job."""
        try:
            frappe.db.set_value(
                "SOP Discovery Engagement",
                self.name,
                stage_field,
                stage,
                update_modified=False,
            )
            frappe.db.commit()
        except Exception:
            pass

    @frappe.whitelist()
    def score_coverage(self) -> dict:
        """Enqueue coverage scoring as a background job; return immediately.

        The actual bridge call + write-back happens in `run_score_coverage_job`
        (module-level, queued on the 'long' worker). Frontend polls
        engagement.coverage_status to detect completion:
            Processing → Done    (success — snapshot appended)
            Processing → Failed  (coverage_error populated)
        """
        if not self.rounds:
            frappe.throw("No rounds yet — generate at least one round first.")
        if (self.coverage_status or "") == "Processing":
            frappe.throw("Score Coverage is already running. Wait for it to finish (or fail) before retrying.")

        # Mark Processing + clear any previous error/stage. Direct DB writes
        # avoid self.save() races with concurrent jobs.
        frappe.db.set_value("SOP Discovery Engagement", self.name, {
            "coverage_status": "Processing",
            "coverage_processing_stage": "Queued",
            "coverage_error": "",
        }, update_modified=True)
        frappe.db.commit()

        frappe.enqueue(
            "office_customizations.office_customisation.doctype.sop_discovery_engagement.sop_discovery_engagement.run_score_coverage_job",
            engagement_name=self.name,
            queue="long",
            timeout=900,  # 15 min — coverage rarely needs more than 3
            job_name=f"score_coverage_{self.name}",
        )
        return {"ok": True, "queued": True, "status": "Processing"}

    def _do_score_coverage(self) -> dict:
        """Actual coverage scoring work, invoked from a background job."""
        self._set_engagement_stage("coverage_processing_stage", "Building payload")
        payload = {"intake": self._intake_payload(), "rounds": self._rounds_payload()}

        self._set_engagement_stage("coverage_processing_stage", "Calling AI (this is the long step)")
        result = _post_bridge("/round/evaluate", payload, timeout=540)

        self._set_engagement_stage("coverage_processing_stage", "Saving snapshot")

        # Compute snapshot fields
        after_round = max(int(r.round_number or 0) for r in self.rounds)
        summary = result.get("summary", "")
        next_round_priorities = "\n".join(
            f"- {p}" for p in result.get("next_round_priorities", [])
        )
        coverage_json = json.dumps(result, indent=2, ensure_ascii=False)

        process_score = 0
        cost_score = 0
        erp_score = 0
        for gr in result.get("goal_readiness", []) or []:
            if gr.get("goal_id") == "G-PROCESS":
                process_score = gr.get("score") or 0
            elif gr.get("goal_id") == "G-COST":
                cost_score = gr.get("score") or 0
            elif gr.get("goal_id") == "G-ERP":
                erp_score = gr.get("score") or 0

        flows = result.get("process_completeness", []) or []
        process_completeness_json = json.dumps(flows, indent=2, ensure_ascii=False)
        flow_pcts = [int(f.get("completeness_pct") or 0) for f in flows]
        min_flow_pct = min(flow_pcts) if flow_pcts else 0
        all_flows_ready = bool(flow_pcts) and all(p >= 90 for p in flow_pcts)
        ai_says_ready = bool(result.get("end_to_end_ready"))
        end_to_end_ready = 1 if (all_flows_ready or ai_says_ready) else 0

        # Append a new SOP Coverage Snapshot child row directly in DB to avoid
        # parent self.save() and TimestampMismatchError under concurrent-edit
        # conditions.
        # Determine next idx.
        existing_idx = frappe.db.sql(
            """select coalesce(max(idx), 0) from `tabSOP Coverage Snapshot`
               where parent=%s and parenttype='SOP Discovery Engagement' and parentfield='coverage_snapshots'""",
            (self.name,),
        )
        next_idx = (existing_idx[0][0] or 0) + 1

        snap_doc = frappe.get_doc({
            "doctype": "SOP Coverage Snapshot",
            "parent": self.name,
            "parenttype": "SOP Discovery Engagement",
            "parentfield": "coverage_snapshots",
            "idx": next_idx,
            "after_round": after_round,
            "snapshot_at": datetime.now(),
            "summary": summary,
            "next_round_priorities": next_round_priorities,
            "coverage_json": coverage_json,
            "process_score": process_score,
            "cost_score": cost_score,
            "erp_score": erp_score,
            "process_completeness_json": process_completeness_json,
            "min_flow_completeness_pct": min_flow_pct,
            "end_to_end_ready": end_to_end_ready,
        })
        snap_doc.insert(ignore_permissions=True)

        # Update engagement-level fields directly. Bumps status to
        # "Sufficient — Ready to Compile" if end-to-end ready and currently In Progress.
        eng_updates = {
            "coverage_status": "Done",
            "coverage_processing_stage": "",
            "coverage_error": "",
        }
        # Reload current status from DB to avoid stomping a concurrent change.
        cur_status = frappe.db.get_value("SOP Discovery Engagement", self.name, "status")
        if end_to_end_ready and cur_status == "In Progress":
            eng_updates["status"] = "Sufficient — Ready to Compile"
        frappe.db.set_value("SOP Discovery Engagement", self.name, eng_updates, update_modified=True)
        frappe.db.commit()

        return {
            "after_round": after_round,
            "min_flow_completeness_pct": min_flow_pct,
            "end_to_end_ready": bool(end_to_end_ready),
        }

    # ───────── compile_sop (async) ─────────

    @frappe.whitelist()
    def compile_sop(self, output_for: str = "process_improvement", force: bool = False) -> dict:
        """Enqueue SOP compilation as a background job; return immediately.

        Gated on end_to_end_ready from the latest coverage snapshot — the SOP
        cannot be compiled while critical flow links are still uncovered. Pass
        force=True to override.

        Frontend polls engagement.compile_status:
            Processing → Done    (success — compiled_sop populated)
            Processing → Failed  (compile_error populated)
        """
        if not self.rounds:
            frappe.throw("No rounds to compile.")
        # Allow string/int truthiness from the JS layer
        force = str(force).lower() in ("1", "true", "yes") if not isinstance(force, bool) else force
        # Re-compile mode: if consultant_edits is non-empty AND a prior SOP
        # already exists, this is a refinement run — bypass the 90% gate.
        # The consultant already cleared it once; iterating on edits should
        # not be re-blocked.
        is_recompile = bool((self.consultant_edits or "").strip()) and bool(self.compiled_sop)
        if not force and not is_recompile:
            latest_snap = self.coverage_snapshots[-1] if self.coverage_snapshots else None
            if not latest_snap:
                frappe.throw("Run Score Coverage at least once before compiling — it computes the end-to-end readiness check.")
            if not latest_snap.end_to_end_ready:
                pct = latest_snap.min_flow_completeness_pct or 0
                frappe.throw(
                    f"Engagement is not yet end-to-end ready (lowest flow completeness: {pct}%). "
                    f"Generate more rounds until every in-scope flow ≥90%, or pass force=True to compile anyway."
                )
        if (self.compile_status or "") == "Processing":
            frappe.throw("Compile SOP is already running. Wait for it to finish (or fail) before retrying.")

        frappe.db.set_value("SOP Discovery Engagement", self.name, {
            "compile_status": "Processing",
            "compile_processing_stage": "Queued",
            "compile_error": "",
        }, update_modified=True)
        frappe.db.commit()

        frappe.enqueue(
            "office_customizations.office_customisation.doctype.sop_discovery_engagement.sop_discovery_engagement.run_compile_sop_job",
            engagement_name=self.name,
            output_for=output_for,
            queue="long",
            timeout=1500,  # 25 min — compile can take 2-5 min in practice
            job_name=f"compile_sop_{self.name}",
        )
        return {"ok": True, "queued": True, "status": "Processing"}

    def _do_compile_sop(self, output_for: str = "process_improvement") -> dict:
        """Actual SOP compile work, invoked from a background job.

        If `consultant_edits` is set on the engagement, the bridge merges
        them into the prior compiled SOP. Otherwise it produces a fresh compile.
        """
        self._set_engagement_stage("compile_processing_stage", "Building payload")
        consultant_edits = (self.consultant_edits or "").strip()
        prior_sop = (self.compiled_sop or "") if consultant_edits else ""
        if consultant_edits:
            self._set_engagement_stage("compile_processing_stage", "Merging consultant edits with prior draft")
        payload = {
            "intake": self._intake_payload(),
            "rounds": self._rounds_payload(),
            "output_for": output_for,
            "consultant_edits": consultant_edits or None,
            "prior_compiled_sop": prior_sop or None,
        }

        self._set_engagement_stage("compile_processing_stage", "Calling AI (this is the long step)")
        result = _post_bridge("/sop/compile", payload, timeout=1320)

        self._set_engagement_stage("compile_processing_stage", "Saving compiled SOP")

        markdown = result.get("markdown", "")
        char_count = result.get("char_count") or len(markdown)

        # Reload status so we don't stomp concurrent edits.
        cur_status = frappe.db.get_value("SOP Discovery Engagement", self.name, "status")
        eng_updates = {
            "compiled_sop": markdown,
            "compiled_output_for": output_for,
            "compiled_at": datetime.now(),
            "compile_status": "Done",
            "compile_processing_stage": "",
            "compile_error": "",
        }
        if cur_status in ("In Progress", "Sufficient — Ready to Compile"):
            eng_updates["status"] = "Compiled"
        frappe.db.set_value("SOP Discovery Engagement", self.name, eng_updates, update_modified=True)
        frappe.db.commit()
        return {"char_count": char_count}

    # ───────── consultant lessons → memory library (sync, fast) ─────────

    @frappe.whitelist()
    def save_lessons_to_memory(self) -> dict:
        """Append the consultant's `consultant_lessons` (one per line) to
        `memory/learnings/_consultant-rules.md` so future engagements load
        them in their memory bundle. Field is cleared on success.

        Routes the file write through the FastAPI bridge — the bridge runs on
        the host and has access to the memory/ folder; the queue worker runs
        inside Docker and does NOT have that path mounted.
        """
        raw = (self.consultant_lessons or "").strip()
        if not raw:
            frappe.throw("Nothing to save — write one or more lessons in 'Lessons for memory' first.")

        lessons = [line.strip() for line in raw.splitlines() if line.strip()]
        if not lessons:
            frappe.throw("All lines in 'Lessons for memory' are blank.")

        payload = {
            "client_name": self.client_name,
            "engagement_id": self.name,
            "industry": self.industry or None,
            "sub_type": self.sub_type or None,
            "modules_in_scope": _multiselect_values(self.modules_in_scope, "module"),
            "lessons": lessons,
        }
        result = _post_bridge("/memory/save_consultant_lesson", payload, timeout=30)

        # Clear the field on the engagement so the consultant knows it was committed
        frappe.db.set_value(
            "SOP Discovery Engagement", self.name,
            {"consultant_lessons": ""},
            update_modified=True,
        )
        frappe.db.commit()
        return {
            "ok": True,
            "lessons_saved": result.get("lessons_saved", len(lessons)),
            "memory_file": result.get("memory_file") or "(unknown)",
        }

    # ───────── reflect (async) ─────────

    @frappe.whitelist()
    def reflect(self) -> dict:
        """Enqueue reflection as a background job; return immediately.

        Frontend polls engagement.reflect_status:
            Processing → Done    (success — reflection_memo populated)
            Processing → Failed  (reflect_error populated)
        """
        if not (self.compiled_sop and self.coverage_snapshots):
            frappe.throw("Need compiled SOP + at least one coverage snapshot before reflection.")
        if (self.reflect_status or "") == "Processing":
            frappe.throw("Reflect is already running. Wait for it to finish (or fail) before retrying.")

        frappe.db.set_value("SOP Discovery Engagement", self.name, {
            "reflect_status": "Processing",
            "reflect_processing_stage": "Queued",
            "reflect_error": "",
        }, update_modified=True)
        frappe.db.commit()

        frappe.enqueue(
            "office_customizations.office_customisation.doctype.sop_discovery_engagement.sop_discovery_engagement.run_reflect_job",
            engagement_name=self.name,
            queue="long",
            timeout=600,  # 10 min — reflect is ~60s typically
            job_name=f"reflect_{self.name}",
        )
        return {"ok": True, "queued": True, "status": "Processing"}

    def _do_reflect(self) -> dict:
        """Actual reflection work, invoked from a background job."""
        self._set_engagement_stage("reflect_processing_stage", "Building payload")
        latest_cov = self.coverage_snapshots[-1]
        coverage_obj = json.loads(latest_cov.coverage_json or "{}")
        payload = {
            "intake": self._intake_payload(),
            "rounds": self._rounds_payload(),
            "coverage": coverage_obj,
            "compiled_sop_preview": (self.compiled_sop or "")[:5000],
        }

        self._set_engagement_stage("reflect_processing_stage", "Calling AI")
        result = _post_bridge("/agent/reflect", payload, timeout=540)

        self._set_engagement_stage("reflect_processing_stage", "Saving memo")
        memo_json = json.dumps(result.get("memo", {}), indent=2, ensure_ascii=False)
        frappe.db.set_value("SOP Discovery Engagement", self.name, {
            "reflection_memo": memo_json,
            "reflect_status": "Done",
            "reflect_processing_stage": "",
            "reflect_error": "",
        }, update_modified=True)
        frappe.db.commit()
        return {"memo_chars": len(memo_json)}


# ───────── module-level entrypoints for frappe.enqueue ─────────

def _mark_round_failed(engagement_name: str, round_number: int, traceback_text: str) -> None:
    """Best-effort: mark the round as Failed with a truncated traceback in processing_error.

    Uses direct frappe.db.set_value to avoid TimestampMismatchError from a
    parent-engagement save under concurrent-edit conditions.
    """
    try:
        rows = frappe.get_all(
            "SOP Discovery Round",
            filters={"parent": engagement_name, "round_number": int(round_number)},
            fields=["name"],
            limit_page_length=1,
        )
        if not rows:
            return
        frappe.db.set_value("SOP Discovery Round", rows[0]["name"], {
            "status": "Failed",
            "processing_error": traceback_text[-2000:],
            "processing_stage": "",
        }, update_modified=True)
        frappe.db.commit()
    except Exception:
        # Even the error-write failed — just log via frappe.log_error in caller
        pass


def run_process_transcript_job(engagement_name: str, round_number: int):
    """Background-worker entrypoint for transcript processing. Flips the round's
    status to Answered (success) or Failed (error, with traceback)."""
    import traceback

    try:
        engagement = frappe.get_doc("SOP Discovery Engagement", engagement_name)
        result = engagement._do_process_transcript(round_number)
        frappe.logger().info(
            f"Process transcript OK: {engagement_name} R{round_number} — "
            f"{result['answered_count']} answered, {result['impromptu_added']} impromptu, "
            f"{result.get('extra_observations_count', 0)} extras"
        )
    except Exception:
        err = traceback.format_exc()
        _mark_round_failed(engagement_name, round_number, err)
        frappe.log_error(message=err, title=f"Process Transcript failed: {engagement_name} R{round_number}")
        raise


def run_generate_round_job(engagement_name: str, round_number: int, target_round_size: int, focus_hint: str):
    """Background-worker entrypoint for round generation. Flips the round's
    status from Generating → Generated (success) or Failed (error)."""
    import traceback

    try:
        engagement = frappe.get_doc("SOP Discovery Engagement", engagement_name)
        result = engagement._do_generate_round(round_number, target_round_size, focus_hint)
        frappe.logger().info(
            f"Generate round OK: {engagement_name} R{round_number} — "
            f"{result['questions_count']} questions"
        )
    except Exception:
        err = traceback.format_exc()
        _mark_round_failed(engagement_name, round_number, err)
        frappe.log_error(message=err, title=f"Generate Round failed: {engagement_name} R{round_number}")
        raise


def _mark_engagement_failed(engagement_name: str, status_field: str, stage_field: str,
                             error_field: str, traceback_text: str) -> None:
    """Best-effort: mark an engagement-level long-job as Failed with a truncated
    traceback. Mirrors `_mark_round_failed` but at the engagement level."""
    try:
        frappe.db.set_value("SOP Discovery Engagement", engagement_name, {
            status_field: "Failed",
            stage_field: "",
            error_field: traceback_text[-2000:],
        }, update_modified=True)
        frappe.db.commit()
    except Exception:
        # Even the error-write failed — caller logs via frappe.log_error
        pass


def run_score_coverage_job(engagement_name: str):
    """Background-worker entrypoint for coverage scoring. Flips the engagement's
    coverage_status from Processing → Done (success) or Failed (error)."""
    import traceback

    try:
        engagement = frappe.get_doc("SOP Discovery Engagement", engagement_name)
        result = engagement._do_score_coverage()
        frappe.logger().info(
            f"Score Coverage OK: {engagement_name} after R{result['after_round']} — "
            f"min flow {result['min_flow_completeness_pct']}%, "
            f"end_to_end_ready={result['end_to_end_ready']}"
        )
    except Exception:
        err = traceback.format_exc()
        _mark_engagement_failed(
            engagement_name, "coverage_status", "coverage_processing_stage", "coverage_error", err
        )
        frappe.log_error(message=err, title=f"Score Coverage failed: {engagement_name}")
        raise


def run_compile_sop_job(engagement_name: str, output_for: str = "process_improvement"):
    """Background-worker entrypoint for SOP compilation. Flips the engagement's
    compile_status from Processing → Done (success) or Failed (error)."""
    import traceback

    try:
        engagement = frappe.get_doc("SOP Discovery Engagement", engagement_name)
        result = engagement._do_compile_sop(output_for=output_for)
        frappe.logger().info(
            f"Compile SOP OK: {engagement_name} — {result['char_count']} chars"
        )
    except Exception:
        err = traceback.format_exc()
        _mark_engagement_failed(
            engagement_name, "compile_status", "compile_processing_stage", "compile_error", err
        )
        frappe.log_error(message=err, title=f"Compile SOP failed: {engagement_name}")
        raise


def run_reflect_job(engagement_name: str):
    """Background-worker entrypoint for reflection. Flips the engagement's
    reflect_status from Processing → Done (success) or Failed (error)."""
    import traceback

    try:
        engagement = frappe.get_doc("SOP Discovery Engagement", engagement_name)
        result = engagement._do_reflect()
        frappe.logger().info(
            f"Reflect OK: {engagement_name} — {result['memo_chars']} chars memo"
        )
    except Exception:
        err = traceback.format_exc()
        _mark_engagement_failed(
            engagement_name, "reflect_status", "reflect_processing_stage", "reflect_error", err
        )
        frappe.log_error(message=err, title=f"Reflect failed: {engagement_name}")
        raise
