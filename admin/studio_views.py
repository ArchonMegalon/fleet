import html
from typing import Any, Dict, List


ROLE_DESCRIPTIONS = {
    "designer": "Canon, boundaries, milestones, and contradiction-driven design patches.",
    "product_governor": "Whole-product pulse, reroute or freeze decisions, and lane selection across code, docs, queue, policy, and canon.",
}


def studio_role_label(role_name: Any) -> str:
    clean = str(role_name or "").strip().replace("-", "_")
    if not clean:
        return "Designer"
    return " ".join(part.capitalize() for part in clean.split("_") if part) or "Designer"


def studio_role_description(role_name: Any) -> str:
    clean = str(role_name or "").strip().replace("-", "_")
    return ROLE_DESCRIPTIONS.get(clean, "")


def studio_target_items(config: Dict[str, Any]) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for project in config.get("projects", []):
        project_id = str(project.get("id") or "").strip()
        if not project_id:
            continue
        items.append(
            {
                "target_type": "project",
                "target_id": project_id,
                "label": f"project:{project_id} — {str(project.get('path') or '').strip()}",
            }
        )
    for group in config.get("project_groups", []):
        group_id = str(group.get("id") or "").strip()
        if not group_id:
            continue
        members = ", ".join(str(item).strip() for item in (group.get("projects") or []) if str(item).strip())
        items.append(
            {
                "target_type": "group",
                "target_id": group_id,
                "label": f"group:{group_id} — {members or 'no members recorded'}",
            }
        )
    items.append({"target_type": "fleet", "target_id": "fleet", "label": "fleet:fleet — /docker/fleet"})
    return items


def studio_target_options_html(config: Dict[str, Any], selected: str = "") -> str:
    options: List[str] = []
    for item in studio_target_items(config):
        value = f"{item['target_type']}:{item['target_id']}"
        sel = " selected" if value == selected else ""
        options.append(f'<option value="{html.escape(value)}"{sel}>{html.escape(item["label"])}</option>')
    return "\n".join(options)


def studio_role_options_html(config: Dict[str, Any], selected: str = "designer") -> str:
    roles = dict((config.get("studio", {}) or {}).get("roles") or {})
    if not roles:
        roles = {"designer": {}}
    options: List[str] = []
    for role_name in roles.keys():
        clean_role = str(role_name or "").strip() or "designer"
        sel = " selected" if clean_role == selected else ""
        options.append(
            f'<option value="{html.escape(clean_role)}"{sel}>{html.escape(studio_role_label(clean_role))}</option>'
        )
    return "\n".join(options)


def studio_kickoff_templates(config: Dict[str, Any], *, limit: int = 6) -> List[Dict[str, Any]]:
    templates: List[Dict[str, Any]] = []
    groups = list(config.get("project_groups") or [])
    for group in groups:
        group_id = str(group.get("id") or "").strip()
        if not group_id:
            continue
        member_projects = [str(item).strip() for item in (group.get("projects") or []) if str(item).strip()]
        member_summary = ", ".join(member_projects[:6]) or "the member projects"
        public_targets = list((((group.get("deployment") or {}).get("public_surface") or {}).get("targets") or []))
        templates.append(
            {
                "template_id": f"group-{group_id}-coordinated-pass",
                "priority": 10,
                "target_key": f"group:{group_id}",
                "role": "program_manager",
                "title": f"{group_id}: coordinated publish pass",
                "summary": f"Ask Studio for one defensive multi-target publish packet across {member_summary}.",
                "detail": "Use this when the group needs one scoped pass that can publish per-target artifacts instead of hand-waving a giant summary.",
                "message": (
                    f"Review group {group_id} across {member_summary}. Draft one coordinated proposal that stays defensive and only covers work with a real chance of landing soon. "
                    "Use proposal.targets for the publish packet instead of collapsing everything into one scope. "
                    "For each target, include only the artifacts, feedback notes, or queue overlays that are justified by current repo truth. "
                    "Call out missing evidence, blocker risk, and anything that is still too speculative to publish."
                ),
                "multi_target": True,
            }
        )
        if public_targets:
            public_target_names = ", ".join(
                str(item.get("name") or item.get("surface") or "").strip()
                for item in public_targets[:4]
                if str(item.get("name") or item.get("surface") or "").strip()
            )
            templates.append(
                {
                    "template_id": f"group-{group_id}-public-surface-sweep",
                    "priority": 20,
                    "target_key": f"group:{group_id}",
                    "role": "auditor",
                    "title": f"{group_id}: public surface sweep",
                    "summary": f"Audit the current public surface for {group_id} and draft only the per-target fixes worth publishing.",
                    "detail": f"Best when the group has multiple visible surfaces ({public_target_names or 'public routes'}) and needs one coordinated cleanup pass.",
                    "message": (
                        f"Audit the public-facing surfaces for group {group_id}. Use proposal.targets to prepare a coordinated multi-target packet for any repo or scope that needs a concrete fix. "
                        "Keep the tone defensive: this is pre-alpha, so prefer honest caveats, proof-first fixes, and only the smallest publishable changes that actually reduce confusion or breakage. "
                        "If a target is not ready, say so plainly instead of inventing polish."
                    ),
                    "multi_target": True,
                }
            )
    templates.append(
        {
            "template_id": "fleet-canon-contradiction-sweep",
            "priority": 34,
            "target_key": "fleet:fleet",
            "role": "designer",
            "title": "Fleet: canon contradiction and design patch",
            "summary": "Ask Studio for one design packet that separates real canon contradictions from mere repo-local churn.",
            "detail": "Use this when the question is whether product truth itself needs a patch: boundary change, contract change, milestone correction, or governor-loop canon.",
            "message": (
                "Review the current Fleet and Chummer design posture for canon contradictions, missing seams, public-story drift, and milestone or blocker truth drift. "
                "Use proposal.targets for any coordinated publish packet that spans multiple scopes. "
                "Only treat evidence as design input after it is synthesized into a contradiction or missing seam. "
                "Use proposal.control_decision.change_class to classify the change, name the affected canonical files explicitly, and only publish artifacts that belong in canon rather than repo-local workaround notes."
            ),
            "multi_target": True,
        }
    )
    templates.append(
        {
            "template_id": "fleet-product-pulse",
            "priority": 35,
            "target_key": "fleet:fleet",
            "role": "product_governor",
            "title": "Fleet: product pulse and reroute check",
            "summary": "Ask Studio for one whole-product packet that separates code fixes from docs, queue, policy, and freeze decisions.",
            "detail": "Use this when the real question is not just 'what is broken', but 'what kind of action should happen next across the program'.",
            "message": (
                "Review the current product pulse across release health, support or feedback clusters, blocker pressure, design drift, and public-promise drift. "
                "Use proposal.targets for any coordinated publish packet. "
                "Be explicit about whether each issue belongs in code, docs, queue, policy, canon, freeze, or reroute work, and do not hide whole-product risk behind repo-local summaries."
            ),
            "multi_target": True,
        }
    )
    templates.append(
        {
            "template_id": "fleet-cross-group-blocker-triage",
            "priority": 30,
            "target_key": "fleet:fleet",
            "role": "auditor",
            "title": "Fleet: cross-group blocker triage",
            "summary": "Let Studio prepare one cross-group packet for the blockers actually worth touching next.",
            "detail": "Useful when pain is spread across several repos and you need a bounded answer instead of a vague fleet-wide rant.",
            "message": (
                "Review the current Fleet state across groups and identify the smallest set of blockers worth addressing next. "
                "Use proposal.targets for any coordinated publish packet so each affected target gets its own artifacts or feedback note. "
                "Stay brutally realistic: if the likely outcome is 'nothing safe to publish yet', say that clearly and explain why."
            ),
            "multi_target": True,
        }
    )
    templates.append(
        {
            "template_id": "fleet-runway-rebalance",
            "priority": 40,
            "target_key": "fleet:fleet",
            "role": "healer",
            "title": "Fleet: runway rebalance",
            "summary": "Ask for a coordinated packet that trims queue noise and protects the slices most likely to finish.",
            "detail": "Best when the queue is technically full but operationally full of nonsense.",
            "message": (
                "Inspect Fleet runway, queue pressure, and active blockers. Draft a defensive multi-target packet using proposal.targets where needed so the most credible near-term slices get cleaner queue truth, while speculative or noisy work gets cut back. "
                "Do not promise heroics. Prefer boring, survivable changes that improve odds instead of pretending certainty exists."
            ),
            "multi_target": True,
        }
    )
    templates.sort(key=lambda item: (int(item.get("priority") or 999), str(item.get("title") or "")))
    return templates[: max(1, int(limit or 1))]


def render_studio_template_card_html(template: Dict[str, Any], *, td_fn) -> str:
    title = td_fn(template.get("title") or "Studio kickoff")
    summary = td_fn(template.get("summary") or "")
    detail = td_fn(template.get("detail") or "")
    target_key = str(template.get("target_key") or "").strip()
    role = str(template.get("role") or "designer").strip() or "designer"
    kickoff_title = str(template.get("title") or "").strip()
    message = str(template.get("message") or "").strip()
    role_detail = td_fn(studio_role_description(role))
    return f"""
            <div class="attention-item">
              <strong>{title}</strong>
              <div class="muted">{summary}</div>
              <div class="muted">scope {td_fn(target_key)} · role {td_fn(studio_role_label(role))} · {'multi-target' if template.get('multi_target') else 'single-target'}</div>
              <div class="muted">{role_detail}</div>
              <div class="muted">{detail}</div>
              <form method="post" action="/api/admin/studio/sessions">
                <input type="hidden" name="target_key" value="{html.escape(target_key)}" />
                <input type="hidden" name="role" value="{html.escape(role)}" />
                <input type="hidden" name="title" value="{html.escape(kickoff_title)}" />
                <input type="hidden" name="message" value="{html.escape(message)}" />
                <button class="action-btn secondary" type="submit">Start template</button>
              </form>
            </div>
            """


def summarize_publish_target_outcome(
    target: Dict[str, Any],
    *,
    project_map: Dict[str, Dict[str, Any]],
    group_map: Dict[str, Dict[str, Any]],
    cockpit_summary: Dict[str, Any],
) -> str:
    target_type = str(target.get("target_type") or "").strip()
    target_id = str(target.get("target_id") or "").strip()
    if target_type == "project":
        project = dict(project_map.get(target_id) or {})
        if not project:
            return "project missing from current runtime status"
        bits = [f"runtime {str(project.get('runtime_status') or 'unknown').strip()}"]
        current_slice = str(project.get("current_slice") or "").strip()
        if current_slice:
            bits.append(f"slice {current_slice}")
        next_action = str(project.get("next_action") or "").strip()
        if next_action:
            bits.append(next_action)
        return " · ".join(bits)
    if target_type == "group":
        group = dict(group_map.get(target_id) or {})
        if not group:
            return "group missing from current runtime status"
        bits = [f"status {str(group.get('status') or 'unknown').strip()}"]
        phase = str(group.get("phase") or "").strip()
        if phase:
            bits.append(f"phase {phase}")
        bits.append("dispatchable" if bool(group.get("dispatch_ready")) else "dispatch-blocked")
        return " · ".join(bits)
    if target_type == "fleet":
        bits = [f"health {str(cockpit_summary.get('fleet_health') or 'unknown').strip()}"]
        blocked_groups = cockpit_summary.get("blocked_groups")
        if blocked_groups is not None:
            bits.append(f"blocked groups {blocked_groups}")
        open_incidents = cockpit_summary.get("open_incidents")
        if open_incidents is not None:
            bits.append(f"incidents {open_incidents}")
        return " · ".join(bits)
    return "no current outcome summary"


def classify_publish_target_outcome(outcome_text: Any) -> str:
    lower = str(outcome_text or "").strip().lower()
    if not lower:
        return "unknown"
    if "missing from current runtime status" in lower:
        return "missing"
    if "dispatch-blocked" in lower or " blocked" in lower or lower.startswith("blocked") or "incidents " in lower:
        return "blocked"
    if (
        "wait for review" in lower
        or "dispatch_pending" in lower
        or "runtime running" in lower
        or "phase delivery" in lower
        or "review" in lower
        or "audit_required" in lower
    ):
        return "active"
    return "aligned"


def summarize_publish_event_assessment(published_targets: List[Dict[str, Any]]) -> Dict[str, str]:
    counts = {"aligned": 0, "active": 0, "blocked": 0, "missing": 0, "unknown": 0}
    for target in published_targets:
        counts[classify_publish_target_outcome(target.get("current_outcome"))] += 1
    nonzero = {key: value for key, value in counts.items() if value}
    if not nonzero:
        return {"state": "unknown", "summary": "no current target outcome recorded"}
    priority = ["missing", "blocked", "active", "aligned", "unknown"]
    state = next((key for key in priority if counts[key]), "unknown")
    if len(nonzero) > 1:
        state = "mixed"
    summary_parts = []
    for key in ("missing", "blocked", "active", "aligned", "unknown"):
        value = counts[key]
        if not value:
            continue
        label = {
            "missing": "missing",
            "blocked": "blocked",
            "active": "still moving",
            "aligned": "aligned",
            "unknown": "unknown",
        }[key]
        noun = "target" if value == 1 else "targets"
        summary_parts.append(f"{value} {noun} {label}")
    return {"state": state, "summary": " · ".join(summary_parts)}


def enrich_publish_event_views(
    events: List[Dict[str, Any]],
    *,
    project_items: List[Dict[str, Any]],
    group_items: List[Dict[str, Any]],
    cockpit_summary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    project_map = {
        str(item.get("id") or "").strip(): dict(item)
        for item in project_items
        if str(item.get("id") or "").strip()
    }
    group_map = {
        str(item.get("id") or "").strip(): dict(item)
        for item in group_items
        if str(item.get("id") or "").strip()
    }
    items: List[Dict[str, Any]] = []
    for event in events:
        item = dict(event)
        enriched_targets: List[Dict[str, Any]] = []
        for target in item.get("published_targets") or []:
            if not isinstance(target, dict):
                continue
            target_payload = dict(target)
            target_payload["current_outcome"] = summarize_publish_target_outcome(
                target_payload,
                project_map=project_map,
                group_map=group_map,
                cockpit_summary=cockpit_summary,
            )
            enriched_targets.append(target_payload)
        item["published_targets"] = enriched_targets
        assessment = summarize_publish_event_assessment(enriched_targets)
        item["outcome_state"] = assessment["state"]
        item["outcome_summary"] = assessment["summary"]
        items.append(item)
    return items


def render_studio_proposal_row_html(
    proposal: Dict[str, Any],
    *,
    td_fn,
    render_action_fn,
) -> str:
    proposal_id = int(proposal.get("id") or 0)
    publish_mode_actions = list(proposal.get("publish_mode_actions") or [])
    control_summary = str(proposal.get("control_decision_summary") or "").strip()
    return f"""
            <tr>
              <td>{td_fn(proposal.get('id'))}</td>
              <td>{td_fn(proposal.get('status') or 'pending')}</td>
              <td>{td_fn(proposal.get('role'))}</td>
              <td>{td_fn(proposal.get('target_type'))}:{td_fn(proposal.get('target_id'))}</td>
              <td><div>{td_fn(proposal.get('title'))}</div><div class="muted">{td_fn(proposal.get('summary'))}</div><div class="muted">{td_fn(control_summary or ('session ' + str((proposal.get('session') or {}).get('status') or proposal.get('session_status') or 'unknown')))}</div></td>
              <td><div>{td_fn(proposal.get('targets_summary') or '<single target>')}</div><div class="muted">{td_fn(proposal.get('recommended_publish_mode') or 'publish_artifacts_and_feedback')}</div></td>
              <td><div class="actions">{render_action_fn({'label': 'Preview', 'focus_id': f'studio-proposal-{proposal_id}', 'method': 'focus'})}{''.join(render_action_fn(action) for action in publish_mode_actions[:2])}</div></td>
            </tr>
            """


def render_studio_proposal_focus_html(
    proposal: Dict[str, Any],
    *,
    td_fn,
    render_action_fn,
) -> str:
    proposal_id = int(proposal.get("id") or 0)
    proposal_payload = proposal.get("proposal") or {}
    recent_messages = list(proposal.get("recent_message_lines") or [])
    active_run = dict(proposal.get("active_run") or {})
    publish_mode_actions = list(proposal.get("publish_mode_actions") or [])
    target_lines = "".join(f"<li>{td_fn(line)}</li>" for line in (proposal.get("target_lines") or []))
    file_lines = "".join(f"<li>{td_fn(line)}</li>" for line in (proposal.get("file_lines") or []))
    canon_lines = "".join(f"<li>{td_fn(line)}</li>" for line in (proposal.get("affected_canon_files") or [])) or "<li>No canon files listed.</li>"
    recent_message_html = "".join(
        f"<li><strong>{td_fn(item.get('label'))}</strong> <span class=\"muted\">{td_fn(item.get('created_at'))}</span><pre>{html.escape(str(item.get('content') or ''))}</pre></li>"
        for item in recent_messages
    ) or "<li>No recent Studio messages.</li>"
    active_run_html = ""
    if active_run:
        active_run_html = (
            f"<p><strong>Active run:</strong> #{td_fn(active_run.get('id'))} · {td_fn(active_run.get('status'))} · {td_fn(active_run.get('model'))}</p>"
            f"<p><strong>Started:</strong> {td_fn(active_run.get('started_at'))}</p>"
            f"<p><strong>Log preview:</strong></p><pre>{html.escape(str(active_run.get('log_preview') or ''))}</pre>"
            f"<p><strong>Final preview:</strong></p><pre>{html.escape(str(active_run.get('final_preview') or ''))}</pre>"
        )
    return f"""
            <div id="studio-proposal-{proposal_id}" class="focus-template">
              <h3>{td_fn(proposal.get('title') or f'Studio proposal #{proposal_id}')}</h3>
              <p class="muted">{td_fn(proposal.get('summary') or '')}</p>
              <p><strong>Scope:</strong> {td_fn(proposal.get('target_type'))}:{td_fn(proposal.get('target_id'))}</p>
              <p><strong>Role:</strong> {td_fn(proposal.get('role'))}</p>
              <p><strong>Session:</strong> #{td_fn(proposal.get('session_id'))} · {td_fn(proposal.get('session_status') or 'unknown')} · {td_fn(proposal.get('session_scope') or '')}</p>
              <p><strong>Session summary:</strong> {td_fn(proposal.get('session_summary') or 'No session summary yet.')}</p>
              <p><strong>Recommended publish mode:</strong> {td_fn(proposal.get('recommended_publish_mode') or 'publish_artifacts_and_feedback')}</p>
              <p><strong>Control decision:</strong> {td_fn(proposal.get('control_decision_summary') or 'No structured decision recorded.')}</p>
              <p><strong>Decision reason:</strong> {td_fn(proposal.get('control_decision_reason') or '')}</p>
              <p><strong>Exit condition:</strong> {td_fn(proposal.get('control_decision_exit_condition') or '')}</p>
              <p><strong>Draft root:</strong> {td_fn(proposal.get('draft_dir') or 'No draft directory recorded')}</p>
              <p><strong>Targets:</strong></p>
              <ul>{target_lines}</ul>
              <p><strong>Files:</strong></p>
              <ul>{file_lines}</ul>
              <p><strong>Affected canon files:</strong></p>
              <ul>{canon_lines}</ul>
              <p><strong>Recent session messages:</strong></p>
              <ul>{recent_message_html}</ul>
              {active_run_html}
              <p><strong>Feedback note:</strong></p>
              <pre>{html.escape(str(proposal.get('feedback_note') or proposal_payload.get('feedback_note') or ''))}</pre>
              <div class="actions">
                {''.join(render_action_fn(action) for action in publish_mode_actions)}
                {render_action_fn({'label': 'Open Studio', 'href': f"/studio?session={proposal.get('session_id')}", 'method': 'get'})}
              </div>
              <form method="post" action="/api/admin/studio/sessions/{proposal.get('session_id')}/message">
                <label>Follow-up message<br><textarea name="message" required placeholder="Tell Studio what to tighten, clarify, or retarget from admin."></textarea></label><br><br>
                <button class="action-btn secondary" type="submit">Send follow-up</button>
              </form>
            </div>
            """


def render_studio_session_row_html(
    session: Dict[str, Any],
    *,
    td_fn,
    render_action_fn,
) -> str:
    session_id = int(session.get("id") or 0)
    draft_count = int(session.get("draft_proposal_count") or 0)
    proposal_count = int(session.get("proposal_count") or 0)
    latest_summary = str(session.get("latest_message_summary") or session.get("summary") or "").strip()
    if len(latest_summary) > 180:
        latest_summary = latest_summary[:177].rstrip() + "..."
    return f"""
            <tr>
              <td>{td_fn(session.get('id'))}</td>
              <td>{td_fn(session.get('status') or 'unknown')}</td>
              <td>{td_fn(session.get('role_label') or session.get('role') or 'designer')}</td>
              <td>{td_fn(session.get('session_scope') or '')}</td>
              <td><div>{td_fn(session.get('title') or f'Studio session #{session_id}')}</div><div class="muted">{td_fn(session.get('summary') or '')}</div></td>
              <td><div>{td_fn(draft_count)} draft / {td_fn(proposal_count)} total</div><div class="muted">{td_fn(session.get('last_message_at') or '')}</div></td>
              <td><div>{td_fn(session.get('latest_message_label') or 'No messages yet')}</div><div class="muted">{td_fn(latest_summary or 'No message summary yet.')}</div></td>
              <td><div class="actions">{render_action_fn({'label': 'Preview', 'focus_id': f'studio-session-{session_id}', 'method': 'focus'})}{render_action_fn({'label': 'Open Studio', 'href': f"/studio?session={session_id}", 'method': 'get'})}</div></td>
            </tr>
            """


def render_studio_session_focus_html(
    session: Dict[str, Any],
    *,
    td_fn,
    render_action_fn,
) -> str:
    session_id = int(session.get("id") or 0)
    recent_messages = list(session.get("recent_message_lines") or [])
    active_run = dict(session.get("active_run") or {})
    recent_message_html = "".join(
        f"<li><strong>{td_fn(item.get('label'))}</strong> <span class=\"muted\">{td_fn(item.get('created_at'))}</span><pre>{html.escape(str(item.get('content') or ''))}</pre></li>"
        for item in recent_messages
    ) or "<li>No Studio messages yet.</li>"
    active_run_html = ""
    if active_run:
        active_run_html = (
            f"<p><strong>Active run:</strong> #{td_fn(active_run.get('id'))} · {td_fn(active_run.get('status'))} · {td_fn(active_run.get('model'))}</p>"
            f"<p><strong>Started:</strong> {td_fn(active_run.get('started_at'))}</p>"
            f"<p><strong>Log preview:</strong></p><pre>{html.escape(str(active_run.get('log_preview') or ''))}</pre>"
            f"<p><strong>Final preview:</strong></p><pre>{html.escape(str(active_run.get('final_preview') or ''))}</pre>"
        )
    return f"""
            <div id="studio-session-{session_id}" class="focus-template">
              <h3>{td_fn(session.get('title') or f'Studio session #{session_id}')}</h3>
              <p class="muted">{td_fn(session.get('summary') or 'No session summary yet.')}</p>
              <p><strong>Scope:</strong> {td_fn(session.get('session_scope') or '')}</p>
              <p><strong>Role:</strong> {td_fn(session.get('role_label') or session.get('role') or 'Designer')}</p>
              <p><strong>Status:</strong> {td_fn(session.get('status') or 'unknown')} · <strong>Updated:</strong> {td_fn(session.get('updated_at') or '')}</p>
              <p><strong>Draft proposals:</strong> {td_fn(session.get('draft_proposal_count') or 0)} of {td_fn(session.get('proposal_count') or 0)}</p>
              <p><strong>Recent session messages:</strong></p>
              <ul>{recent_message_html}</ul>
              {active_run_html}
              <div class="actions">
                {render_action_fn({'label': 'Open Studio', 'href': f"/studio?session={session_id}", 'method': 'get'})}
              </div>
              <form method="post" action="/api/admin/studio/sessions/{session_id}/message">
                <label>Follow-up message<br><textarea name="message" required placeholder="Tell Studio what to tighten, clarify, compare, or rewrite from admin."></textarea></label><br><br>
                <button class="action-btn secondary" type="submit">Send follow-up</button>
              </form>
            </div>
            """


def render_studio_publish_event_focus_html(event: Dict[str, Any], *, td_fn) -> str:
    target_lines = "".join(
        f"<li><strong>{td_fn(target.get('target_type'))}:{td_fn(target.get('target_id'))}</strong> · files {td_fn(target.get('file_count') or 0)} · dir {td_fn(target.get('published_dir') or '')} · feedback {td_fn(target.get('feedback_rel') or '')}<div class=\"muted\">{td_fn(target.get('current_outcome') or '')}</div></li>"
        for target in (event.get("published_targets") or [])
    ) or "<li>No published targets recorded.</li>"
    return f"""
            <div id="studio-publish-event-{td_fn(event.get('id'))}" class="focus-template">
              <h3>Studio publish event #{td_fn(event.get('id'))}</h3>
              <p class="muted">{td_fn(event.get('source_target_type'))}:{td_fn(event.get('source_target_id'))} · mode {td_fn(event.get('mode'))}</p>
              <p><strong>Proposal:</strong> #{td_fn(event.get('proposal_id'))} · <strong>Session:</strong> #{td_fn(event.get('session_id'))}</p>
              <p><strong>Created:</strong> {td_fn(event.get('created_at'))}</p>
              <p><strong>Current outcome:</strong> {td_fn(event.get('outcome_state') or 'unknown')} · {td_fn(event.get('outcome_summary') or '')}</p>
              <p><strong>Published targets:</strong></p>
              <ul>{target_lines}</ul>
            </div>
            """


def render_group_publish_event_focus_html(event: Dict[str, Any], *, td_fn) -> str:
    target_lines = "".join(
        f"<li><strong>{td_fn(target.get('target_type'))}:{td_fn(target.get('target_id'))}</strong> · files {td_fn(target.get('file_count') or 0)} · dir {td_fn(target.get('published_dir') or '')}<div class=\"muted\">{td_fn(target.get('current_outcome') or '')}</div></li>"
        for target in (event.get("published_targets") or [])
    ) or "<li>No published targets recorded.</li>"
    return f"""
            <div id="group-publish-event-{td_fn(event.get('id'))}" class="focus-template">
              <h3>Group publish event #{td_fn(event.get('id'))}</h3>
              <p class="muted">group {td_fn(event.get('group_id'))} · source {td_fn(event.get('source_scope_type'))}:{td_fn(event.get('source_scope_id'))}</p>
              <p><strong>Kind:</strong> {td_fn(event.get('source'))} · <strong>Created:</strong> {td_fn(event.get('created_at'))}</p>
              <p><strong>Current outcome:</strong> {td_fn(event.get('outcome_state') or 'unknown')} · {td_fn(event.get('outcome_summary') or '')}</p>
              <p><strong>Published targets:</strong></p>
              <ul>{target_lines}</ul>
            </div>
            """


def render_audit_task_focus_html(
    task: Dict[str, Any],
    *,
    td_fn,
    render_action_fn,
) -> str:
    task_id = int(task.get("id") or 0)
    return f"""
            <div id="audit-task-{task_id}" class="focus-template">
              <h3>{td_fn(task.get('title'))}</h3>
              <p class="muted">{td_fn(task.get('finding_key'))}</p>
              <p><strong>Scope:</strong> {td_fn(task.get('scope_type'))}:{td_fn(task.get('scope_id'))}</p>
              <pre>{html.escape(str(task.get('detail') or ''))}</pre>
              <div class="actions">
                {render_action_fn({'label': 'Approve', 'href': f"/api/admin/audit/tasks/{task_id}/approve", 'method': 'post'}) if str(task.get('status') or '') == 'open' else ''}
                {render_action_fn({'label': 'Publish', 'href': f"/api/admin/audit/tasks/{task_id}/publish", 'method': 'post'}) if str(task.get('status') or '') == 'approved' else ''}
                {render_action_fn({'label': 'Reject', 'href': f"/api/admin/audit/tasks/{task_id}/reject", 'method': 'post'})}
              </div>
            </div>
            """


def assemble_studio_session_views(
    sessions: List[Dict[str, Any]],
    *,
    snapshot_loader,
    message_limit: int = 4,
) -> List[Dict[str, Any]]:
    views: List[Dict[str, Any]] = []
    for session in sessions:
        item = dict(session)
        snapshot = snapshot_loader(item.get("id"), message_limit=message_limit)
        session_row = dict(snapshot.get("session") or {})
        if session_row:
            item.update(session_row)
        recent_messages = list(snapshot.get("recent_messages") or [])
        active_run = dict(snapshot.get("active_run") or {})
        item["role_label"] = studio_role_label(item.get("role"))
        item["session_scope"] = (
            f"{str(item.get('target_type') or 'project')}:{str(item.get('target_id') or item.get('project_id') or '').strip()}"
        )
        item["recent_message_lines"] = [
            {
                "label": f"{str(message.get('actor_type') or '').strip()}:{str(message.get('actor_name') or '').strip()}",
                "content": str(message.get("content") or "").strip(),
                "created_at": str(message.get("created_at") or "").strip(),
            }
            for message in recent_messages
        ]
        latest_message = item["recent_message_lines"][-1] if item["recent_message_lines"] else {}
        item["latest_message_label"] = str(latest_message.get("label") or "").strip()
        item["latest_message_summary"] = str(latest_message.get("content") or "").strip()
        item["active_run"] = active_run
        views.append(item)
    return views


def assemble_studio_proposal_views(
    proposals: List[Dict[str, Any]],
    *,
    snapshot_loader,
    publish_mode_actions_fn,
) -> List[Dict[str, Any]]:
    views: List[Dict[str, Any]] = []
    for proposal in proposals:
        item = dict(proposal)
        payload = dict(item.get("payload") or {})
        proposal_payload = dict(item.get("proposal") or {})
        control_decision = dict(proposal_payload.get("control_decision") or {})
        recommended_mode = (
            str(proposal_payload.get("recommended_publish_mode") or "publish_artifacts_and_feedback").strip()
            or "publish_artifacts_and_feedback"
        )
        session_snapshot = snapshot_loader(item.get("session_id"))
        session_row = dict(session_snapshot.get("session") or {})
        recent_messages = list(session_snapshot.get("recent_messages") or [])
        active_run = dict(session_snapshot.get("active_run") or {})
        files = list(proposal_payload.get("files") or item.get("files") or [])
        targets = list(item.get("targets") or [])
        item["payload"] = payload
        item["proposal"] = proposal_payload
        item["recommended_publish_mode"] = recommended_mode
        item["publish_mode_actions"] = publish_mode_actions_fn(int(item.get("id") or 0), recommended_mode)
        item["session"] = session_row
        item["recent_messages"] = recent_messages
        item["active_run"] = active_run
        item["files"] = files
        item["targets"] = targets
        item["target_lines"] = [
            f"{str(target.get('target_type') or '').strip()}:{str(target.get('target_id') or '').strip()}"
            for target in targets
            if isinstance(target, dict)
            and (str(target.get("target_type") or "").strip() or str(target.get("target_id") or "").strip())
        ] or [str(item.get("targets_summary") or "<single target proposal>").strip()]
        item["file_lines"] = [
            str(file_item.get("path") or "").strip()
            for file_item in files
            if isinstance(file_item, dict) and str(file_item.get("path") or "").strip()
        ] or ["No direct file artifacts listed"]
        item["recent_message_lines"] = [
            {
                "label": f"{str(message.get('actor_type') or '').strip()}:{str(message.get('actor_name') or '').strip()}",
                "content": str(message.get("content") or "").strip(),
                "created_at": str(message.get("created_at") or "").strip(),
            }
            for message in recent_messages
        ]
        item["session_scope"] = (
            f"{str(session_row.get('target_type') or item.get('target_type') or 'project')}:{str(session_row.get('target_id') or item.get('target_id') or item.get('project_id') or '').strip()}"
        )
        item["session_status"] = str(session_row.get("status") or "unknown")
        item["session_summary"] = str(session_row.get("summary") or "").strip()
        item["session_last_error"] = str(session_row.get("last_error") or "").strip()
        item["draft_dir"] = str(item.get("draft_dir") or "").strip()
        item["feedback_note"] = str(proposal_payload.get("feedback_note") or "").strip()
        item["control_decision"] = control_decision
        item["affected_canon_files"] = [
            str(value).strip()
            for value in (control_decision.get("affected_canon_files") or [])
            if str(value).strip()
        ]
        lane = str(control_decision.get("primary_lane") or "").strip()
        change_class = str(control_decision.get("change_class") or "").strip()
        item["control_decision_summary"] = " / ".join(part for part in [lane, change_class] if part)
        item["control_decision_reason"] = str(control_decision.get("reason") or "").strip()
        item["control_decision_exit_condition"] = str(control_decision.get("exit_condition") or "").strip()
        views.append(item)
    return views
