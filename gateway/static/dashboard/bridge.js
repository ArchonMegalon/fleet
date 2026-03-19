(function () {
  if (typeof window.__fleetBridgeMarkAssetLoaded === "function") {
    window.__fleetBridgeMarkAssetLoaded();
  }
  window.__fleetBridgeBooted = true;
  window.__fleetBridgeReady = false;

  const drawer = document.getElementById("drawer");
  const drawerBody = document.getElementById("drawer-body");
  const drawerTitle = document.getElementById("drawer-title");
  const drawerEyebrow = document.getElementById("drawer-eyebrow");
  const drawerBackdrop = document.getElementById("drawer-backdrop");
  const closeButton = document.getElementById("drawer-close");
  const REFRESH_INTERVAL_MS = 15000;

  const stateNodes = {
    headline: document.getElementById("mission-headline"),
    currentSliceTitle: document.getElementById("current-slice-title"),
    currentSliceMeta: document.getElementById("current-slice-meta"),
    nextTransitionTitle: document.getElementById("next-transition-title"),
    nextTransitionMeta: document.getElementById("next-transition-meta"),
    missionRunway: document.getElementById("mission-runway"),
    missionRunwayMeta: document.getElementById("mission-runway-meta"),
    stopCondition: document.getElementById("stop-condition"),
    stopConditionMeta: document.getElementById("stop-condition-meta"),
    truthFreshness: document.getElementById("truth-freshness"),
    truthFreshnessMeta: document.getElementById("truth-freshness-meta"),
    loopPolicy: document.getElementById("loop-policy"),
    loopTimeline: document.getElementById("loop-timeline"),
    loopCurrent: document.getElementById("loop-current"),
    loopNext: document.getElementById("loop-next"),
    loopHorizon: document.getElementById("loop-horizon"),
    groupGrid: document.getElementById("group-grid"),
    workerGrid: document.getElementById("worker-grid"),
    reviewGrid: document.getElementById("review-grid"),
    healerGrid: document.getElementById("healer-grid"),
    laneGrid: document.getElementById("lane-grid"),
    providerCreditCard: document.getElementById("provider-credit-card"),
    blockerGrid: document.getElementById("blocker-grid"),
    blockerPriority: document.getElementById("blocker-priority"),
  };

  let state = null;
  let loadInFlight = null;

  const surfaceState = () => ((state && state.public_status) || state || {});

  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  const clear = (node) => {
    if (!node) return;
    while (node.firstChild) node.removeChild(node.firstChild);
  };

  const setText = (node, value) => {
    if (node) node.textContent = value;
  };

  const first = (...values) => {
    for (const value of values) {
      if (value !== null && value !== undefined) {
        const clean = String(value).trim();
        if (clean) return clean;
      }
    }
    return "";
  };

  const redirectToLogin = (loginUrl) => {
    window.location.href = loginUrl || "/admin/login?next=/dashboard/";
  };

  const tone = (value) => {
    const clean = String(value || "").trim().toLowerCase();
    if (["critical", "high", "danger", "red", "blocked", "stale"].includes(clean)) return "danger";
    if (["warn", "warning", "yellow", "pending", "attention", "constrained", "fallback_ready"].includes(clean)) return "warn";
    if (["good", "green", "ready", "current", "enabled", "dispatchable", "done"].includes(clean)) return "good";
    return "muted";
  };

  const chip = (value, variant) => {
    const node = el("span", `chip tone-${variant || tone(value)}`);
    node.textContent = value || "unknown";
    return node;
  };

  const projectById = (projectId) => {
    return ((surfaceState().projects) || []).find((project) => String(project.id || "") === String(projectId || "")) || null;
  };

  const groupById = (groupId) => {
    return ((surfaceState().groups) || []).find((group) => String(group.id || "") === String(groupId || "")) || null;
  };

  const openDrawer = (eyebrow, title, renderBody) => {
    if (!drawer || !drawerBody || !drawerTitle || !drawerEyebrow || !drawerBackdrop) return;
    drawerEyebrow.textContent = eyebrow;
    drawerTitle.textContent = title;
    clear(drawerBody);
    renderBody(drawerBody);
    drawer.classList.add("open");
    drawer.setAttribute("aria-hidden", "false");
    drawerBackdrop.hidden = false;
  };

  const closeDrawer = () => {
    if (!drawer || !drawerBackdrop) return;
    drawer.classList.remove("open");
    drawer.setAttribute("aria-hidden", "true");
    drawerBackdrop.hidden = true;
  };

  if (closeButton) closeButton.addEventListener("click", closeDrawer);
  if (drawerBackdrop) drawerBackdrop.addEventListener("click", closeDrawer);

  const renderKeyValue = (parent, label, value) => {
    const row = el("div", "drawer-row");
    row.appendChild(el("strong", "", `${label}: `));
    row.appendChild(el("span", "", value || "unknown"));
    parent.appendChild(row);
  };

  const appendPreviewSection = (parent, item, options) => {
    const logPreview = first(item && item.log_preview);
    const finalPreview = first(item && item.final_preview);
    if (!logPreview && !finalPreview) return;
    const section = el("div", "drawer-section");
    const summaryBits = [first(item && item.preview_label, "Run preview")];
    if (first(item && item.brain)) summaryBits.push(first(item.brain));
    if (first(item && item.backend)) summaryBits.push(first(item.backend));
    if (first(item && item.when)) summaryBits.push(first(item.when));
    if (first(item && item.run_id)) summaryBits.push(`run ${first(item.run_id)}`);
    section.appendChild(el("div", "detail-kicker", summaryBits.filter(Boolean).join(" · ")));
    const grid = el("div", "drawer-preview-grid");
    const logPanel = el("div", "drawer-preview-panel");
    logPanel.appendChild(el("div", "detail-kicker", "Log Tail"));
    logPanel.appendChild(el("pre", "", logPreview || options.logEmpty));
    grid.appendChild(logPanel);
    const finalPanel = el("div", "drawer-preview-panel");
    finalPanel.appendChild(el("div", "detail-kicker", "Latest Final"));
    finalPanel.appendChild(el("pre", "", finalPreview || options.finalEmpty));
    grid.appendChild(finalPanel);
    section.appendChild(grid);
    parent.appendChild(section);
  };

  const openProjectDrawer = (projectId) => {
    const project = projectById(projectId);
    if (!project) return;
    openDrawer("Current Slice", project.current_slice || project.id || "Project", (body) => {
      const summary = el("div", "drawer-section");
      const readiness = project.readiness || {};
      renderKeyValue(summary, "Project", project.id || "unknown");
      renderKeyValue(summary, "Runtime", project.runtime_status || "unknown");
      renderKeyValue(summary, "Readiness", first(readiness.label, readiness.stage, "unknown"));
      renderKeyValue(summary, "Next gate", first(readiness.next_label, readiness.next_stage, readiness.terminal_stage, "unknown"));
      renderKeyValue(summary, "Final claim", readiness.final_claim_allowed ? "allowed" : "not yet");
      renderKeyValue(summary, "Lane", first(project.selected_lane, "unknown"));
      renderKeyValue(summary, "Reviewer", first(project.next_reviewer_lane, project.required_reviewer_lane, "n/a"));
      renderKeyValue(summary, "Landing lane", first(project.task_landing_lane, project.task_final_reviewer_lane, "n/a"));
      renderKeyValue(summary, "Workflow", first(project.task_workflow_kind, "default"));
      renderKeyValue(summary, "Review round", `${project.review_rounds_used || 0} / ${project.task_max_review_rounds || 0}`);
      renderKeyValue(summary, "Rounds remaining", String(Math.max(0, Number(project.task_max_review_rounds || 0) - Number(project.review_rounds_used || 0))));
      renderKeyValue(summary, "Next reviewer", first(project.next_reviewer_lane, project.required_reviewer_lane, "n/a"));
      renderKeyValue(summary, "Credit burn", project.task_allow_credit_burn ? "allowed" : "disabled");
      renderKeyValue(summary, "Paid fast lane", project.task_allow_paid_fast_lane ? "allowed" : "disabled");
      renderKeyValue(summary, "Core rescue", project.task_allow_core_rescue ? "enabled" : "disabled");
      renderKeyValue(summary, "Runway", first(project.sustainable_runway, "unknown"));
      renderKeyValue(summary, "Decision", first(project.decision_meta_summary, "No routing detail recorded."));
      renderKeyValue(summary, "Readiness basis", first(readiness.summary, "No readiness summary recorded."));
      body.appendChild(summary);
    });
  };

  const openGroupDrawer = (groupCard) => {
    const group = groupById(groupCard.group_id);
    openDrawer("Mission Group", groupCard.group_id || "group", (body) => {
      const summary = el("div", "drawer-section");
      const deploymentReadiness = (group && group.deployment_readiness) || {};
      renderKeyValue(summary, "Objective", first(groupCard.current_objective, "No current objective recorded."));
      renderKeyValue(summary, "Current slice", first(groupCard.current_slice, "Queue not materialized"));
      renderKeyValue(summary, "Dispatchability", first(groupCard.dispatchability, "unknown"));
      renderKeyValue(summary, "Milestone ETA", first(groupCard.next_milestone_eta, "unknown"));
      renderKeyValue(summary, "Program ETA", first(groupCard.program_eta, "unknown"));
      renderKeyValue(summary, "Design truth", first(groupCard.design_truth_freshness, "unknown"));
      renderKeyValue(summary, "Blockers", String(groupCard.blocker_count || 0));
      renderKeyValue(summary, "Review debt", String(groupCard.review_debt || 0));
      if (group) {
        renderKeyValue(summary, "Phase", first(group.phase, "unknown"));
        renderKeyValue(summary, "Pressure", first(group.pressure_state, "unknown"));
        renderKeyValue(summary, "Dispatch basis", first(group.dispatch_basis, "No dispatch basis recorded."));
        renderKeyValue(summary, "Promotion readiness", first(deploymentReadiness.summary, "No promotion-readiness summary recorded."));
      }
      body.appendChild(summary);
    });
  };

  const openWorkerDrawer = (worker) => {
    openDrawer("Worker Posture", first(worker.project_id, worker.current_slice, "worker"), (body) => {
      const summary = el("div", "drawer-section");
      renderKeyValue(summary, "Project", first(worker.project_id, "unknown"));
      renderKeyValue(summary, "Run", first(worker.run_id, "unknown"));
      renderKeyValue(summary, "Phase", first(worker.phase, "unknown"));
      renderKeyValue(summary, "Status", first(worker.status, "unknown"));
      renderKeyValue(summary, "Current slice", first(worker.current_slice, "No current slice recorded."));
      renderKeyValue(summary, "Lane", first(worker.lane, "unknown"));
      renderKeyValue(summary, "Profile", first(worker.profile, "unknown"));
      renderKeyValue(summary, "Provider", first(worker.provider, "unknown"));
      renderKeyValue(summary, "Backend", first(worker.backend, "unknown"));
      renderKeyValue(summary, "Brain", first(worker.brain, "unknown"));
      renderKeyValue(summary, "Capacity state", first(worker.capacity_state, "unknown"));
      renderKeyValue(summary, "Slots", `${first(worker.ready_slots, "0")} / ${first(worker.configured_slots, "0")}`);
      renderKeyValue(summary, "Slot owners", (worker.slot_owners || []).length ? worker.slot_owners.join(", ") : "none");
      renderKeyValue(summary, "Elapsed", first(worker.elapsed_human, "unknown"));
      renderKeyValue(summary, "Finished", first(worker.finished_at, "active"));
      body.appendChild(summary);
      appendPreviewSection(body, worker, {
        logEmpty: "No live log preview yet.",
        finalEmpty: "No final message written yet.",
      });
    });
  };

  const openReviewDrawer = (item) => {
    openDrawer("Review Gate", first(item.title, item.project_id, "review item"), (body) => {
      const summary = el("div", "drawer-section");
      renderKeyValue(summary, "Kind", first(item.kind, "review"));
      renderKeyValue(summary, "Status", first(item.status, "unknown"));
      renderKeyValue(summary, "Project", first(item.project_id, "n/a"));
      renderKeyValue(summary, "Detail", first(item.detail, "No review detail recorded."));
      body.appendChild(summary);
      appendPreviewSection(body, item, {
        logEmpty: "No recent log tail recorded for this review gate.",
        finalEmpty: "No final message recorded for this review gate.",
      });
    });
  };

  const openHealerDrawer = (item) => {
    openDrawer("Healer Activity", first(item.label, item.project_id, "healer item"), (body) => {
      const summary = el("div", "drawer-section");
      renderKeyValue(summary, "Label", first(item.label, "unknown"));
      renderKeyValue(summary, "Status", first(item.status, "unknown"));
      renderKeyValue(summary, "Project", first(item.project_id, "n/a"));
      renderKeyValue(summary, "Detail", first(item.detail, "No healer detail recorded."));
      body.appendChild(summary);
      appendPreviewSection(body, item, {
        logEmpty: "No healer log tail recorded yet.",
        finalEmpty: "No healer final message recorded yet.",
      });
    });
  };

  const openLaneDrawer = (lane) => {
    openDrawer("Lane Runway", lane.lane || "lane", (body) => {
      const summary = el("div", "drawer-section");
      renderKeyValue(summary, "Lane", first(lane.lane, "unknown"));
      renderKeyValue(summary, "Profile", first(lane.profile, "unknown"));
      renderKeyValue(summary, "Provider", first(lane.provider, "unknown"));
      renderKeyValue(summary, "Backend", first(lane.backend, "unknown"));
      renderKeyValue(summary, "Brain", first(lane.brain, lane.model, "unknown"));
      renderKeyValue(summary, "Model", first(lane.model, "unknown"));
      renderKeyValue(summary, "State", first(lane.state, "unknown"));
      renderKeyValue(summary, "Allowance", first(lane.remaining_text, "unknown"));
      renderKeyValue(summary, "Runway", first(lane.sustainable_runway, lane.hot_runway, "unknown"));
      renderKeyValue(summary, "Slots", `${first(lane.ready_slots, "0")} / ${first(lane.configured_slots, "0")}`);
      renderKeyValue(summary, "Slot owners", (lane.slot_owners || []).length ? lane.slot_owners.join(", ") : "none");
      renderKeyValue(summary, "Mission enabled", lane.mission_enabled ? "yes" : "no");
      renderKeyValue(summary, "Policy enabled", lane.policy_enabled ? "yes" : "no");
      renderKeyValue(summary, "Policy reason", first(lane.policy_reason, "mission-ready"));
      renderKeyValue(summary, "Critical path", lane.critical_path ? "yes" : "no");
      body.appendChild(summary);
    });
  };

  const openBlockerDrawer = (scope, detail, board) => {
    openDrawer("Blocker", scope || "blocker", (body) => {
      const summary = el("div", "drawer-section");
      renderKeyValue(summary, "Scope", scope || "unknown");
      renderKeyValue(summary, "Detail", detail || "none");
      renderKeyValue(summary, "Stop condition", first((board.blockers || {}).stop_sentence, "Forever on trend."));
      body.appendChild(summary);
    });
  };

  const openProviderCreditDrawer = (credit) => {
    openDrawer("Billing Truth", first(credit.provider, "1min"), (body) => {
      const summary = el("div", "drawer-section");
      renderKeyValue(summary, "Provider", first(credit.provider, "1min"));
      renderKeyValue(summary, "Free credits", `${first(credit.free_credits, "unknown")} / ${first(credit.max_credits, "unknown")}`);
      renderKeyValue(summary, "Remaining", first(credit.remaining_percent_total, "unknown"));
      renderKeyValue(summary, "Next top-up", first(credit.next_topup_at, "unknown"));
      renderKeyValue(summary, "Top-up amount", first(credit.topup_amount, "unknown"));
      renderKeyValue(summary, "Hours until top-up", first(credit.hours_until_next_topup, "unknown"));
      renderKeyValue(summary, "No top-up runway", first(credit.hours_remaining_at_current_pace_no_topup, "unknown"));
      renderKeyValue(
        summary,
        "Runway incl. next top-up",
        `${first(credit.hours_remaining_including_next_topup_at_current_pace, "unknown")}h / ${first(credit.days_remaining_including_next_topup_at_7d_avg, "unknown")}d`,
      );
      renderKeyValue(summary, "Depletes before top-up", credit.depletes_before_next_topup ? "yes" : "no");
      renderKeyValue(summary, "Basis quality", first(credit.basis_quality, "unknown"));
      renderKeyValue(summary, "Basis summary", first(credit.basis_summary, "unknown"));
      renderKeyValue(
        summary,
        "Coverage",
        `${first(credit.slot_count_with_billing_snapshot, "0")} billing slots / ${first(credit.slot_count_with_member_reconciliation, "0")} member snapshots`,
      );
      body.appendChild(summary);
    });
  };

  const renderDetailCard = (container, label, title, lines, onClick) => {
    clear(container);
    const card = el("button", "detail-card");
    card.type = "button";
    card.appendChild(el("div", "detail-kicker", label));
    card.appendChild(el("h3", "", title || "unknown"));
    (lines || []).filter(Boolean).forEach((line) => card.appendChild(el("p", "detail-line", line)));
    if (typeof onClick === "function") {
      card.addEventListener("click", onClick);
    }
    container.appendChild(card);
  };

  const renderHero = (board) => {
    const current = board.current_slice || {};
    const next = board.next_transition || {};
    const capacity = board.capacity || {};
    const blockers = board.blockers || {};
    const freshness = board.truth_freshness || {};
    const loop = board.execution_loop || {};

    setText(stateNodes.headline, board.headline || "Loading current mission...");
    setText(stateNodes.currentSliceTitle, current.title || "Idle");
    setText(
      stateNodes.currentSliceMeta,
      `${first(current.stage, "Idle")} · ${first(loop.round_label, "r0 / r0")} · next reviewer ${first(loop.next_reviewer_lane, "n/a")} · landing ${first(loop.landing_lane, "n/a")}`,
    );
    setText(stateNodes.nextTransitionTitle, next.title || "No next transition");
    setText(
      stateNodes.nextTransitionMeta,
      `${first(next.lane, "unknown")} · ${first(next.confidence, "unknown")} · ${first(next.prerequisites, "none")}`,
    );
    setText(stateNodes.missionRunway, first(capacity.mission_runway, "unknown"));
    setText(
      stateNodes.missionRunwayMeta,
      `critical path ${first(capacity.critical_path_lane, "unknown")} · pool ${first(capacity.pool_runway, "unknown")}`,
    );
    setText(stateNodes.stopCondition, first(blockers.stop_sentence, "Forever on trend."));
    setText(stateNodes.stopConditionMeta, first((blockers.items || [])[0] && (blockers.items || [])[0].detail, "none"));
    setText(stateNodes.truthFreshness, first(freshness.state, "unknown"));
    setText(
      stateNodes.truthFreshnessMeta,
      `${first(freshness.generated_at, "unknown")} · compile attention ${freshness.compile_attention_count || 0} · warnings ${freshness.config_warning_count || 0}`,
    );
  };

  const renderExecutionLoop = (board) => {
    const loop = board.execution_loop || {};
    const current = board.current_slice || {};
    const next = board.next_transition || {};
    const horizon = board.mission_horizon || {};
    const reviewTelemetry = loop.telemetry_review_loop || {};
    const workerTelemetry = loop.telemetry_worker_utilization || {};
    const accepted = reviewTelemetry.accepted_on_round_counts || {};

    clear(stateNodes.loopPolicy);
    stateNodes.loopPolicy.appendChild(chip(loop.current_stage_label || "Idle", tone(loop.current_stage_label)));
    stateNodes.loopPolicy.appendChild(chip(loop.round_label || "r0 / r0", "muted"));
    stateNodes.loopPolicy.appendChild(chip(`${String(loop.rounds_remaining || 0)} rounds left`, "muted"));
    stateNodes.loopPolicy.appendChild(chip(loop.allow_credit_burn ? "credit burn allowed" : "credit burn disabled", loop.allow_credit_burn ? "warn" : "good"));
    stateNodes.loopPolicy.appendChild(chip(loop.allow_core_rescue ? "core rescue enabled" : "core rescue disabled", loop.allow_core_rescue ? "warn" : "good"));
    stateNodes.loopPolicy.appendChild(chip(`landing ${first(loop.landing_lane, "n/a")}`, "muted"));
    if (Object.keys(accepted).length) {
      stateNodes.loopPolicy.appendChild(chip(`accept r1/r2/r3 ${accepted["1"] || 0}/${accepted["2"] || 0}/${accepted["3"] || 0}`, "muted"));
    }
    if (reviewTelemetry.shadow_assist_rate !== undefined) {
      stateNodes.loopPolicy.appendChild(chip(`shadow assist ${Math.round(Number(reviewTelemetry.shadow_assist_rate || 0) * 100)}%`, "muted"));
    }

    clear(stateNodes.loopTimeline);
    (loop.timeline || []).forEach((item) => {
      const node = el("div", `timeline-step state-${tone(item.state)}`);
      node.appendChild(el("div", "timeline-step-label", item.label || item.id || "step"));
      node.appendChild(chip(item.state || "pending", tone(item.state)));
      stateNodes.loopTimeline.appendChild(node);
    });

    renderDetailCard(
      stateNodes.loopCurrent,
      "Current Slice",
      current.title || "Idle",
      [
        `${first(loop.current_stage_label, "Idle")} · ${first(loop.round_label, "r0 / r0")}`,
        `${String(loop.rounds_remaining || 0)} rounds left · ${first(loop.next_reviewer_summary, "No reviewer is pending.")}`,
        `${first(current.lane, "unknown")} · ${first(current.provider, "none")} · ${first(current.brain, "none")}`,
        `ETA ${first(current.eta, "unknown")} · review ahead ${first(current.review_ahead, "no")}`,
        first(loop.policy_summary, "No cheap-loop policy recorded."),
        Object.keys(accepted).length ? `Accepted r1/r2/r3 ${accepted["1"] || 0}/${accepted["2"] || 0}/${accepted["3"] || 0} · core rescue ${(Number(reviewTelemetry.core_rescue_rate || 0) * 100).toFixed(0)}%` : "",
      ],
      () => openProjectDrawer(loop.project_id),
    );

    renderDetailCard(
      stateNodes.loopNext,
      "Next Transition",
      next.title || "No next transition",
      [
        `${first(next.lane, "unknown")} · ${first(next.confidence, "unknown")}`,
        `Prerequisites: ${first(next.prerequisites, "none")}`,
        `Reason: ${first(next.reason, "No queue reason recorded.")}`,
        `Next reviewer ${first(loop.next_reviewer_lane, "n/a")} · landing ${first(loop.landing_lane, "n/a")}`,
      ],
      () => openBlockerDrawer("next transition", next.reason || next.prerequisites || "none", board),
    );

    renderDetailCard(
      stateNodes.loopHorizon,
      "Mission Horizon",
      first(horizon.milestone_title, "unknown"),
      [
        `Milestone ETA ${first(horizon.milestone_eta, "unknown")}`,
        `Vision p50 ${first(horizon.vision_eta_p50, "unknown")} · p90 ${first(horizon.vision_eta_p90, "unknown")}`,
        `Confidence ${first(horizon.confidence, "unknown")}`,
        workerTelemetry.groundwork_shadow_busy_percent !== undefined
          ? `Busy primary/shadow/jury ${first(workerTelemetry.groundwork_primary_busy_percent, 0)}% / ${first(workerTelemetry.groundwork_shadow_busy_percent, 0)}% / ${first(workerTelemetry.jury_busy_percent, 0)}%`
          : "",
        first((board.truth_freshness || {}).summary, "No truth-freshness summary available."),
      ],
      () => openBlockerDrawer("mission horizon", first(horizon.vision_eta_p50, "unknown"), board),
    );
  };

  const renderGroups = (board) => {
    clear(stateNodes.groupGrid);
    const groups = board.group_cards || [];
    if (!groups.length) {
      stateNodes.groupGrid.appendChild(el("div", "empty-state", "No mission groups are available."));
      return;
    }
    groups.forEach((group) => {
      const card = el("button", `group-card state-${tone(group.dispatchability)}`);
      card.type = "button";
      card.appendChild(el("div", "card-kicker", `${group.group_id || "group"} · ${group.dispatchability || "unknown"}`));
      card.appendChild(el("h3", "", group.current_objective || "No current objective recorded."));
      card.appendChild(el("p", "card-line", `Current slice ${group.current_slice || "Queue not materialized"}`));
      card.appendChild(el("p", "card-line", `Milestone ${group.next_milestone_eta || "unknown"} · Program ${group.program_eta || "unknown"}`));
      card.appendChild(el("p", "card-line", `Truth ${group.design_truth_freshness || "unknown"} · Review debt ${group.review_debt || 0}`));
      card.appendChild(el("p", "card-line muted", `Blockers ${group.blocker_count || 0} · ${group.status || "unknown"} / ${group.phase || "unknown"}`));
      card.addEventListener("click", () => openGroupDrawer(group));
      stateNodes.groupGrid.appendChild(card);
    });
  };

  const renderWorkers = (board) => {
    clear(stateNodes.workerGrid);
    const posture = board.worker_posture || {};
    const active = (posture.active || []).map((worker) => ({ ...worker, posture_kind: "active" }));
    const recent = (posture.recent || []).map((worker) => ({ ...worker, posture_kind: "recent" }));
    const workers = [...active, ...recent];
    if (!workers.length) {
      stateNodes.workerGrid.appendChild(el("div", "empty-state", "No active or recent worker posture is available."));
      return;
    }
    workers.slice(0, 6).forEach((worker) => {
      const card = el("button", `detail-card state-${tone(worker.capacity_state || worker.status)}`);
      card.type = "button";
      card.appendChild(el("div", "detail-kicker", `${worker.posture_kind || "worker"} · ${worker.project_id || "project"}`));
      card.appendChild(el("h3", "", first(worker.current_slice, worker.project_id, "No current slice recorded.")));
      const chipRow = el("div", "chip-row");
      chipRow.appendChild(chip(first(worker.capacity_state, "unknown"), tone(worker.capacity_state)));
      chipRow.appendChild(chip(`${first(worker.ready_slots, "0")}/${first(worker.configured_slots, "0")} slots`, "muted"));
      chipRow.appendChild(chip(first(worker.phase, worker.status, worker.posture_kind || "worker"), worker.posture_kind === "active" ? "good" : "muted"));
      card.appendChild(chipRow);
      card.appendChild(el("p", "card-line", `${first(worker.lane, "unknown")} · ${first(worker.provider, "unknown")} · ${first(worker.backend, "unknown")}`));
      card.appendChild(el("p", "card-line", `${first(worker.profile, "unknown")} · ${first(worker.brain, "unknown")}`));
      card.appendChild(
        el(
          "p",
          "card-line muted",
          `${first(worker.elapsed_human, worker.finished_at, "unknown")} · owners ${((worker.slot_owners || []).join(", ")) || "none"}`,
        ),
      );
      card.addEventListener("click", () => openWorkerDrawer(worker));
      stateNodes.workerGrid.appendChild(card);
    });
  };

  const renderReviewGate = (board) => {
    clear(stateNodes.reviewGrid);
    const items = board.review_gate || [];
    if (!items.length) {
      stateNodes.reviewGrid.appendChild(el("div", "empty-state", "No review waits are active right now."));
      return;
    }
    items.slice(0, 4).forEach((item) => {
      const card = el("button", `detail-card state-${tone(item.status || item.kind)}`);
      card.type = "button";
      card.appendChild(el("div", "detail-kicker", `${first(item.kind, "review")} · ${first(item.project_id, "shared queue")}`));
      card.appendChild(el("h3", "", first(item.title, "Review item")));
      const chipRow = el("div", "chip-row");
      chipRow.appendChild(chip(first(item.status, item.kind, "review"), tone(item.status || item.kind)));
      if (first(item.preview_label)) chipRow.appendChild(chip(first(item.preview_label), "muted"));
      card.appendChild(chipRow);
      card.appendChild(el("p", "card-line", first(item.detail, "No review detail recorded.")));
      const previewMeta = [first(item.brain), first(item.backend), first(item.when)];
      if (previewMeta.some(Boolean)) {
        card.appendChild(el("p", "card-line muted", previewMeta.filter(Boolean).join(" · ")));
      }
      card.addEventListener("click", () => openReviewDrawer(item));
      stateNodes.reviewGrid.appendChild(card);
    });
  };

  const renderHealer = (board) => {
    clear(stateNodes.healerGrid);
    const items = board.healer_activity || [];
    if (!items.length) {
      stateNodes.healerGrid.appendChild(el("div", "empty-state", "No healer-owned activity right now."));
      return;
    }
    items.slice(0, 5).forEach((item) => {
      const card = el("button", `detail-card state-${tone(item.status)}`);
      card.type = "button";
      card.appendChild(el("div", "detail-kicker", `${first(item.label, "healer")} · ${first(item.status, "active")}`));
      card.appendChild(el("h3", "", first(item.detail, "Healer activity")));
      const chipRow = el("div", "chip-row");
      chipRow.appendChild(chip(first(item.status, "healing"), tone(item.status)));
      if (first(item.preview_label)) chipRow.appendChild(chip(first(item.preview_label), "muted"));
      card.appendChild(chipRow);
      const previewMeta = [first(item.brain), first(item.backend), first(item.when)];
      if (previewMeta.some(Boolean)) {
        card.appendChild(el("p", "card-line muted", previewMeta.filter(Boolean).join(" · ")));
      }
      card.addEventListener("click", () => openHealerDrawer(item));
      stateNodes.healerGrid.appendChild(card);
    });
  };

  const renderLanes = (board) => {
    clear(stateNodes.laneGrid);
    const lanes = board.lane_runway || [];
    if (!lanes.length) {
      stateNodes.laneGrid.appendChild(el("div", "empty-state", "No lane runway telemetry is available."));
      return;
    }
    lanes.forEach((lane) => {
      const card = el("button", `lane-card state-${tone(lane.state)}`);
      card.type = "button";
      const head = el("div", "lane-head");
      head.appendChild(el("strong", "", lane.lane || "lane"));
      const chipRow = el("div", "chip-row");
      chipRow.appendChild(chip(lane.remaining_text || "unknown", tone(lane.state)));
      chipRow.appendChild(chip(lane.policy_enabled ? "policy on" : "policy off", lane.policy_enabled ? "good" : "warn"));
      chipRow.appendChild(chip(lane.mission_enabled ? "mission on" : "mission off", lane.mission_enabled ? "good" : "muted"));
      if (lane.critical_path) chipRow.appendChild(chip("critical path", "warn"));
      head.appendChild(chipRow);
      card.appendChild(head);
      card.appendChild(el("p", "card-line", `${lane.provider || "unknown"} · ${lane.backend || "unknown"} · ${lane.brain || lane.model || "unknown"}`));
      card.appendChild(
        el(
          "p",
          "card-line",
          `${lane.sustainable_runway || lane.hot_runway || "unknown"} · slots ${first(lane.ready_slots, "0")}/${first(lane.configured_slots, "0")} · mission ${lane.mission_enabled ? "yes" : "no"} · policy ${lane.policy_enabled ? "yes" : "no"}`,
        ),
      );
      card.appendChild(el("p", "card-line muted", lane.policy_reason || "mission-ready"));
      card.addEventListener("click", () => openLaneDrawer(lane));
      stateNodes.laneGrid.appendChild(card);
    });
  };

  const renderProviderCredit = (board) => {
    clear(stateNodes.providerCreditCard);
    const credit = board.provider_credit_card || {};
    if (!credit || !Object.keys(credit).length) {
      stateNodes.providerCreditCard.appendChild(el("div", "empty-state", "No billing-backed credit telemetry is available."));
      return;
    }
    const basisTone =
      credit.basis_quality === "actual"
        ? "good"
        : credit.basis_quality === "mixed"
          ? "warn"
          : "danger";
    const card = el("button", "detail-card provider-credit-card");
    card.type = "button";
    card.appendChild(el("div", "detail-kicker", `${first(credit.provider, "1min")} billing truth`));
    card.appendChild(el("h3", "", `${first(credit.remaining_percent_total, "unknown")} remaining`));
    const chipRow = el("div", "chip-row");
    chipRow.appendChild(chip(first(credit.basis_quality, "unknown"), basisTone));
    chipRow.appendChild(chip(`${first(credit.slot_count_with_billing_snapshot, "0")} billing`, "muted"));
    chipRow.appendChild(chip(`${first(credit.slot_count_with_member_reconciliation, "0")} members`, "muted"));
    card.appendChild(chipRow);
    card.appendChild(
      el(
        "p",
        "card-line",
        `${first(credit.free_credits, "unknown")} / ${first(credit.max_credits, "unknown")} credits · top-up ${first(credit.next_topup_at, "unknown")}`,
      ),
    );
    card.appendChild(
      el(
        "p",
        "card-line",
        `No top-up ${first(credit.hours_remaining_at_current_pace_no_topup, "unknown")}h · incl. top-up ${first(credit.hours_remaining_including_next_topup_at_current_pace, "unknown")}h`,
      ),
    );
    card.appendChild(
      el(
        "p",
        "card-line muted",
        `7d avg ${first(credit.days_remaining_including_next_topup_at_7d_avg, "unknown")}d · depletes first ${credit.depletes_before_next_topup ? "yes" : "no"} · ${first(credit.basis_summary, "unknown")}`,
      ),
    );
    card.addEventListener("click", () => openProviderCreditDrawer(credit));
    stateNodes.providerCreditCard.appendChild(card);
  };

  const renderBlockers = (board) => {
    clear(stateNodes.blockerGrid);
    clear(stateNodes.blockerPriority);
    const blockers = board.blockers || {};
    const items = blockers.items || [];
    if (!items.length) {
      stateNodes.blockerGrid.appendChild(el("div", "empty-state", "No blockers are recorded."));
    } else {
      items.forEach((item) => {
        const card = el("button", "blocker-card");
        card.type = "button";
        card.appendChild(el("div", "card-kicker", item.scope || "blocker"));
        card.appendChild(el("h3", "", item.detail || "none"));
        card.addEventListener("click", () => openBlockerDrawer(item.scope, item.detail, board));
        stateNodes.blockerGrid.appendChild(card);
      });
    }

    const stopCard = el("article", "priority-card stop-card");
    stopCard.appendChild(el("div", "card-kicker", "Stop Condition"));
    stopCard.appendChild(el("h3", "", blockers.stop_sentence || "Forever on trend."));
    stateNodes.blockerPriority.appendChild(stopCard);

    (blockers.priority || []).slice(0, 4).forEach((item) => {
      const card = el("article", "priority-card");
      card.appendChild(el("div", "card-kicker", item.scope || "attention"));
      card.appendChild(el("h3", "", item.title || "attention"));
      card.appendChild(el("p", "card-line", item.detail || "No detail recorded."));
      stateNodes.blockerPriority.appendChild(card);
    });
  };

  const render = () => {
    const surface = surfaceState();
    if (!surface || !Object.keys(surface).length) return;
    const board = surface.mission_board || {};
    renderHero(board);
    renderExecutionLoop(board);
    renderGroups(board);
    renderWorkers(board);
    renderReviewGate(board);
    renderHealer(board);
    renderLanes(board);
    renderProviderCredit(board);
    renderBlockers(board);
  };

  async function loadStatus() {
    if (loadInFlight) return loadInFlight;
    loadInFlight = (async () => {
      const response = await fetch("/api/public/status", {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        throw new Error(`status fetch failed with ${response.status}`);
      }
      const contentType = String(response.headers.get("content-type") || "");
      if (!contentType.includes("application/json")) {
        throw new Error("status endpoint returned a non-JSON response");
      }
      state = await response.json();
      render();
      window.__fleetBridgeReady = true;
    })();
    try {
      await loadInFlight;
    } finally {
      loadInFlight = null;
    }
  }

  loadStatus().catch((error) => {
    setText(stateNodes.headline, `Mission Board failed to load: ${String(error && error.message || error)}`);
  });

  window.setInterval(() => {
    if (document.visibilityState === "hidden") return;
    loadStatus().catch((error) => {
      console.error("Mission Board background refresh failed", error);
    });
  }, REFRESH_INTERVAL_MS);

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      loadStatus().catch((error) => {
        console.error("Mission Board visibility refresh failed", error);
      });
    }
  });
})();
