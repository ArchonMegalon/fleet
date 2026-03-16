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
  const hoverCard = document.getElementById("hover-card");
  const recommendedAction = document.getElementById("recommended-action");

  let state = null;

  const showLoadError = (message) => {
    if (recommendedAction) {
      recommendedAction.textContent = message;
    }
  };

  const redirectToLogin = (loginUrl) => {
    window.location.href = loginUrl || "/admin/login?next=/dashboard/";
  };

  const incidentRequiresOperator = (item) => {
    const context = item && typeof item.context === "object" && item.context ? item.context : {};
    if (Object.prototype.hasOwnProperty.call(context, "operator_required")) {
      return Boolean(context.operator_required);
    }
    if (Object.prototype.hasOwnProperty.call(context, "can_resolve")) {
      return !Boolean(context.can_resolve);
    }
    return ["blocked_unresolved", "review_failed"].includes(String(item.incident_kind || ""));
  };

  const tone = (value) => {
    const clean = String(value || "").toLowerCase();
    if (["critical", "high", "red", "danger"].includes(clean)) return "red";
    if (["yellow", "warn", "medium", "tight", "healing", "queue_refilling", "review_fix", "elevated"].includes(clean)) return "yellow";
    if (["green", "good", "active", "nominal", "running"].includes(clean)) return "green";
    return "gray";
  };

  const tokenTone = (value) => {
    const clean = String(value || "").toLowerCase();
    if (!clean || clean === "ready") return "green";
    if (clean.includes("stale") || clean.includes("denied") || clean.includes("invalid") || clean.includes("error")) return "red";
    if (clean.includes("cooldown") || clean.includes("disabled") || clean.includes("draining") || clean.includes("paused")) return "yellow";
    return tone(clean);
  };

  const confidenceTone = (value) => {
    const clean = String(value || "").toLowerCase();
    if (clean === "high") return "green";
    if (clean === "medium") return "yellow";
    if (clean === "low") return "gray";
    return tone(clean);
  };

  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  const clear = (node) => {
    while (node.firstChild) node.removeChild(node.firstChild);
  };

  const describeResetWindow = (item) => {
    if (!item || typeof item !== "object") return "";
    const label = String(item.label || "").trim();
    const human = String(item.human || "").trim();
    return [label, human].filter(Boolean).join(" ");
  };

  const moveHover = (event) => {
    if (!hoverCard || hoverCard.hidden) return;
    const x = Math.min(window.innerWidth - hoverCard.offsetWidth - 16, (event.clientX || 0) + 18);
    const y = Math.min(window.innerHeight - hoverCard.offsetHeight - 16, (event.clientY || 0) + 18);
    hoverCard.style.left = `${Math.max(12, x)}px`;
    hoverCard.style.top = `${Math.max(12, y)}px`;
  };

  const showHover = (event, title, lines) => {
    if (!hoverCard) return;
    clear(hoverCard);
    hoverCard.appendChild(el("h3", "", title));
    const list = el("ul", "");
    (lines || []).filter(Boolean).slice(0, 5).forEach((line) => list.appendChild(el("li", "", line)));
    if (list.childNodes.length) {
      hoverCard.appendChild(list);
    }
    hoverCard.hidden = false;
    moveHover(event);
  };

  const hideHover = () => {
    if (!hoverCard) return;
    hoverCard.hidden = true;
  };

  const postForm = async (url, fields) => {
    const body = new URLSearchParams();
    Object.entries(fields || {}).forEach(([key, value]) => body.append(key, String(value)));
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    });
    if (!response.ok && response.status !== 303) {
      throw new Error(`POST ${url} failed with ${response.status}`);
    }
    await loadStatus();
  };

  const addActionButton = (row, label, handler, primary) => {
    const button = el("button", primary ? "primary" : "", label);
    button.type = "button";
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await handler();
      } finally {
        button.disabled = false;
      }
    });
    row.appendChild(button);
  };

  const progressSummary = (progress, delivery) => {
    const source = progress && typeof progress === "object" ? progress : {};
    const grayKey = delivery ? "percent_unstarted" : "percent_unmaterialized";
    const grayLabel = delivery ? "unstarted" : "unmaterialized";
    return `${source.percent_complete || 0}% done · ${source.percent_inflight || 0}% inflight · ${source.percent_blocked || 0}% blocked · ${source[grayKey] || 0}% ${grayLabel}`;
  };

  const summaryButton = (className) => {
    const button = el("button", className);
    button.type = "button";
    return button;
  };

  const summaryChip = (label, value, chipTone) => {
    const chip = el("span", `summary-chip state-${chipTone || "gray"}`);
    chip.appendChild(el("span", "summary-chip-label", label));
    chip.appendChild(el("strong", "", value));
    return chip;
  };

  const operatorPoolTone = (operator) => {
    const pressure = tone(operator && operator.pressure_state);
    if (pressure !== "gray") return pressure;
    const match = String((operator && operator.pool_left) || "").match(/(\d+)\s+slot/);
    if (!match) return "gray";
    const slotsLeft = Number(match[1] || 0);
    if (slotsLeft <= 0) return "red";
    if (slotsLeft === 1) return "yellow";
    return "green";
  };

  const operatorPrimaryWork = (operator) => {
    const items = (operator && operator.current_work_items) || [];
    if (items.length) {
      return items
        .slice(0, 2)
        .map((item) => {
          const projectId = String(item.project_id || "").trim();
          const phase = String(item.phase || "").trim().replace(/_/g, " ");
          return projectId && phase ? `${projectId} (${phase})` : projectId || phase || "working";
        })
        .join(" · ");
    }
    return operator && operator.current_summary ? operator.current_summary : "Idle · waiting on next runnable slice.";
  };

  const projectHeadline = (project) => {
    const designEta = (project && project.design_eta) || {};
    const designProgress = (project && project.design_progress) || {};
    if (designRegistryMissing(designProgress, designEta)) {
      return "Design registry missing";
    }
    return `Design ${designProgress.percent_complete || 0}% · Configured Queue ETA ${designEta.eta_human || designProgress.eta_human || "unknown"}`;
  };

  const designRegistryMissing = (progress, eta) => {
    const source = progress && typeof progress === "object" ? progress : {};
    const etaSource = eta && typeof eta === "object" ? eta : {};
    const blocker = String(source.main_blocker || "").toLowerCase();
    const summary = String(source.summary || "").toLowerCase();
    const reason = String(etaSource.eta_unavailable_reason || ((source.eta || {}).eta_unavailable_reason) || "").toLowerCase();
    return blocker === "design registry missing" || summary === "design registry missing" || reason === "no_design_registry";
  };

  const designProgressHeadline = (progress, eta) => {
    const source = progress && typeof progress === "object" ? progress : {};
    const etaSource = eta && typeof eta === "object" ? eta : {};
    if (designRegistryMissing(source, etaSource)) {
      return "Design registry missing";
    }
    return `${progressSummary(source, false)} | Configured Queue ETA ${etaSource.eta_human || source.eta_human || "unknown"} | ${etaSource.confidence || source.eta_confidence || "low"} confidence`;
  };

  const progressBar = (progress, delivery) => {
    const source = progress && typeof progress === "object" ? progress : {};
    const grayKey = delivery ? "percent_unstarted" : "percent_unmaterialized";
    const bar = el("div", "progress-bar");
    [
      ["progress-complete", source.percent_complete || 0],
      ["progress-inflight", source.percent_inflight || 0],
      ["progress-blocked", source.percent_blocked || 0],
      ["progress-unmaterialized", source[grayKey] || 0],
    ].forEach(([className, width]) => {
      const segment = el("span", `progress-segment ${className}`);
      segment.style.width = `${Math.max(0, Number(width) || 0)}%`;
      bar.appendChild(segment);
    });
    return bar;
  };

  const openDrawer = (eyebrow, title, bodyBuilder) => {
    if (!drawer || !drawerBody || !drawerTitle || !drawerEyebrow || !drawerBackdrop) return;
    drawerEyebrow.textContent = eyebrow;
    drawerTitle.textContent = title;
    clear(drawerBody);
    bodyBuilder(drawerBody);
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

  async function loadStatus() {
    const response = await fetch("/api/cockpit/status", {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (response.redirected && response.url && response.url.includes("/admin/login")) {
      redirectToLogin(response.url);
      return;
    }
    if (response.status === 401) {
      let loginUrl = "";
      try {
        const payload = await response.json();
        loginUrl = payload && payload.login;
      } catch (_error) {
        loginUrl = "";
      }
      redirectToLogin(loginUrl);
      return;
    }
    if (!response.ok) {
      throw new Error(`status fetch failed with ${response.status}`);
    }
    const contentType = String(response.headers.get("content-type") || "");
    if (!contentType.includes("application/json")) {
      throw new Error("cockpit returned a non-JSON response");
    }
    state = await response.json();
    render();
    window.__fleetBridgeReady = true;
  }

  async function loadSimulation(groupId, action) {
    const response = await fetch(`/api/cockpit/simulation?group_id=${encodeURIComponent(groupId)}&action=${encodeURIComponent(action)}`, {
      credentials: "same-origin",
    });
    if (!response.ok) {
      throw new Error(`simulation fetch failed with ${response.status}`);
    }
    return response.json();
  }

  function renderHeader() {
    const summary = state.cockpit.summary || {};
    document.getElementById("recommended-action").textContent = summary.recommended_action || "No urgent action right now.";
    document.getElementById("posture-state").textContent = summary.scheduler_posture || "unknown";
    document.getElementById("auto-heal-state").textContent = summary.auto_heal_enabled ? "enabled" : "paused";
    const resets = Array.isArray(summary.next_reset_windows) ? summary.next_reset_windows : [];
    document.getElementById("next-reset").textContent = resets.map(describeResetWindow).filter(Boolean).slice(0, 2).join(" / ") || "no reset window";
  }

  function openOperatorDrawer(operator) {
    openDrawer("Operator", operator.label || operator.alias || "Codex lane", (body) => {
      const summary = el("div", "drawer-section");
      summary.appendChild(el("p", "", operator.current_summary || "Ready for next slice."));
      summary.appendChild(
        el(
          "p",
          "muted",
          `Lane ${operator.lane_label || operator.configured_lane || "unknown"} | authority ${operator.lane_authority || "unknown"} | profile ${operator.lane_worker_profile || "unknown"}`,
        ),
      );
      summary.appendChild(
        el(
          "p",
          "muted",
          `Token ${operator.token_status || "ready"} | allowance ${operator.pool_left || "unknown"} | pool ETA ${operator.projected_exhaustion || "unknown"}`,
        ),
      );
      summary.appendChild(
        el(
          "p",
          "muted",
          `Pressure ${operator.pressure_state || "unknown"} | engaged ${operator.occupied_runs || 0} | active ${operator.active_runs || 0} | burn ${operator.burn_rate || "unknown"}`,
        ),
      );
      body.appendChild(summary);

      const workSection = el("div", "drawer-section");
      workSection.appendChild(el("h3", "", "Current work"));
      const workList = el("div", "drawer-list-grid");
      const workItems = (operator.current_work_items || []).slice(0, 4);
      if (!workItems.length) {
        workList.appendChild(el("div", "empty", "No active project on this lane."));
      } else {
        workItems.forEach((item) => {
          const card = el("article", "mini-project-card");
          card.appendChild(el("h4", "", item.project_id || "project"));
          card.appendChild(el("p", "muted", `${item.phase || "working"} · ${item.slice || "slice unknown"}`));
          if (item.elapsed_human) {
            card.appendChild(el("p", "muted", `elapsed ${item.elapsed_human}`));
          }
          workList.appendChild(card);
        });
      }
      workSection.appendChild(workList);
      body.appendChild(workSection);

      const accountSection = el("div", "drawer-section");
      accountSection.appendChild(el("h3", "", "Account details"));
      accountSection.appendChild(el("p", "muted", `Account ${operator.alias || "unknown"}`));
      accountSection.appendChild(el("p", "muted", `Runtime model ${operator.lane_runtime_model || "unknown"} | providers ${(operator.provider_hints || []).join(", ") || "unknown"}`));
      accountSection.appendChild(el("p", "muted", `Allowed models ${(operator.allowed_models || []).join(", ") || "none"}`));
      accountSection.appendChild(el("p", "muted", `Top consumers ${(operator.top_consumers || []).join(" | ") || "none"}`));
      body.appendChild(accountSection);
    });
  }

  function openProjectDrawer(project, groupId) {
    openDrawer("Project", project.id || "project", (body) => {
      const activeBackend = String(project.active_run_account_backend || "").trim();
      const activeIdentity = String(project.active_run_account_identity || "").trim();
      const activeBrain = String(project.active_run_brain || "").trim();
      const lastBackend = String(project.last_run_account_backend || "").trim();
      const lastIdentity = String(project.last_run_account_identity || "").trim();
      const lastBrain = String(project.last_run_brain || "").trim();
      const useActive = activeBackend && activeBackend !== "not active";
      const backendSource = useActive ? activeBackend : lastBackend;
      const backendIdentity = useActive ? activeIdentity : lastIdentity;
      const brainSource = useActive ? activeBrain : lastBrain;
      const sourceLabel = useActive ? "active run" : "last run";
      const backendLine = backendSource && backendSource !== "not active"
        ? `${backendSource}${backendIdentity ? ` (${backendIdentity})` : ""} · ${sourceLabel}`
        : "none";
      const brainLine = brainSource && brainSource !== "not active" ? `${brainSource} · ${sourceLabel}` : "none";

      const summary = el("div", "drawer-section");
      summary.appendChild(
        el(
          "p",
          "",
          `${project.runtime_status || "unknown"} · ${project.current_slice || "no active slice"} · group ${groupId || "unassigned"}`,
        ),
      );
      summary.appendChild(
        el(
          "p",
          "muted",
          `Backend ${backendLine} | brain ${brainLine}`,
        ),
      );
      summary.appendChild(
        el(
          "p",
          "muted",
          `Review ${project.review_status || "unknown"} | next ${project.next_action || "none"} | stop ${project.stop_reason || "none"}`,
        ),
      );
      summary.appendChild(
        el(
          "p",
          "muted",
          `Task ${project.task_difficulty || "auto"} / ${project.task_risk_level || "auto"} | lanes ${(project.allowed_lanes || []).join(", ") || "none"} | reviewer ${project.required_reviewer_lane || "core"}`,
        ),
      );
      summary.appendChild(
        el(
          "p",
          "muted",
          `Tasks ${project.approved_audit_task_count || 0} approved / ${project.open_audit_task_count || 0} open | blocker ${(project.design_progress || {}).main_blocker || "none"}`,
        ),
      );
      body.appendChild(summary);

      const deliverySection = el("div", "drawer-section");
      deliverySection.appendChild(el("h3", "", "Delivery progress"));
      deliverySection.appendChild(el("p", "muted", progressSummary(project.delivery_progress || {}, true)));
      deliverySection.appendChild(progressBar(project.delivery_progress || {}, true));
      body.appendChild(deliverySection);

      const design = project.design_progress || {};
      const designEta = project.design_eta || {};
      const designSection = el("div", "drawer-section");
      designSection.appendChild(el("h3", "", "Design completeness"));
      designSection.appendChild(el("p", "muted", designProgressHeadline(design, designEta)));
      if (!designRegistryMissing(design, designEta)) {
        designSection.appendChild(progressBar(design, false));
      }
      designSection.appendChild(el("p", "muted", design.summary || "No design summary available."));
      if (designEta.eta_basis) {
        designSection.appendChild(el("p", "muted", `ETA basis: ${designEta.eta_basis}`));
      }
      body.appendChild(designSection);
    });
  }

  function renderOperators() {
    const operatorGrid = document.getElementById("operator-grid");
    if (!operatorGrid) return;
    clear(operatorGrid);
    const operators = (state.cockpit.operators || []).slice(0, 3);
    if (!operators.length) {
      const lanes = Object.entries((state.lanes||{})).map(([k,v]) => k + ":" + ((v||{}).authority||"")) .join(", ");
      operatorGrid.appendChild(el("div", "empty", lanes ? ("Lanes: " + lanes) : "No lanes configured. Defaults: EA Easy(run), EA Repair(run), EA Core(approve_merge), Jury(audit)."));
      return;
    }
    operators.forEach((operator) => {
      const card = summaryButton(`operator-card compact-card state-${tone(operator.pressure_state)}`);
      const head = el("div", "summary-head");
      const title = el("div", "summary-title");
      title.appendChild(el("h3", "", operator.label || operator.alias));
      title.appendChild(el("div", "summary-main", operatorPrimaryWork(operator)));
      head.appendChild(title);
      const chips = el("div", "summary-chips");
      chips.appendChild(summaryChip("token", operator.token_status || "ready", tokenTone(operator.token_status)));
      chips.appendChild(summaryChip("allowance", operator.pool_left || "unknown", operatorPoolTone(operator)));
      chips.appendChild(summaryChip("Configured Queue ETA", operator.projected_exhaustion || "unknown", confidenceTone(operator.pressure_state)));
      head.appendChild(chips);
      card.appendChild(head);

      card.addEventListener("mouseenter", (event) => showHover(event, operator.label || operator.alias || "Codex lane", [
        operatorPrimaryWork(operator),
        `Lane ${(operator.lane_label || operator.configured_lane || "unknown")} / ${(operator.lane_authority || "unknown")}`,
        `Token status ${operator.token_status || "ready"}`,
        `Pool ${operator.pool_left || "unknown"}`,
        `Burn ${operator.burn_rate || "$0.000/day"}`,
        `Pool ETA ${operator.projected_exhaustion || "unknown"}`,
        ...(operator.top_consumers || []).slice(0, 3),
      ]));
      card.addEventListener("mousemove", moveHover);
      card.addEventListener("mouseleave", hideHover);
      card.addEventListener("click", () => openOperatorDrawer(operator));
      operatorGrid.appendChild(card);
    });
  }

  function renderLamps() {
    const lampGrid = document.getElementById("lamp-grid");
    clear(lampGrid);
    (state.cockpit.lamps || []).slice(0, 6).forEach((lamp) => {
      const card = el("button", `lamp state-${tone(lamp.state)}`);
      card.type = "button";
      card.title = `${lamp.detail || ""}${lamp.auto_action ? ` | ${lamp.auto_action}` : ""}`;
      card.appendChild(el("div", "lamp-label", lamp.label));
      card.appendChild(el("div", "lamp-value", String(lamp.count || 0)));
      card.appendChild(el("div", "lamp-detail", lamp.detail || ""));
      card.addEventListener("mouseenter", (event) => showHover(event, lamp.label || "Lamp", [
        lamp.detail || "",
        lamp.auto_action ? `Auto-action: ${lamp.auto_action}` : "",
        lamp.eta_hint ? `ETA: ${lamp.eta_hint}` : "",
        ...(lamp.summary_lines || []),
      ]));
      card.addEventListener("mousemove", moveHover);
      card.addEventListener("mouseleave", hideHover);
      card.addEventListener("click", () => openLampDrawer(lamp));
      lampGrid.appendChild(card);
    });
  }

  function renderIncidents() {
    const incidentRail = document.getElementById("incident-rail");
    clear(incidentRail);
    const incidents = (state.incidents || []).filter(incidentRequiresOperator).slice(0, 6);
    if (!incidents.length) {
      incidentRail.appendChild(el("div", "empty", "No red incidents right now."));
      return;
    }
    incidents.forEach((incident) => {
      const card = el("article", `incident-card state-${tone(incident.severity)}`);
      const chips = el("div", "signal-row");
      chips.appendChild(el("span", `signal ${tone(incident.severity)}`, incident.severity || "high"));
      chips.appendChild(el("span", "signal gray", incident.incident_kind || "incident"));
      chips.appendChild(el("span", "signal gray", `${incident.scope_type}:${incident.scope_id}`));
      card.appendChild(chips);
      card.appendChild(el("h3", "", incident.title || "Incident"));
      card.appendChild(el("p", "muted", incident.summary || ""));
      const actions = el("div", "action-row");
      addActionButton(actions, "Open context", () => Promise.resolve(openIncidentDrawer(incident)), false);
      addActionButton(actions, "Auto-resolve", () => postForm(`/api/admin/incidents/${incident.id}/auto-resolve`), true);
      addActionButton(actions, "Ack", () => postForm(`/api/admin/incidents/${incident.id}/ack`), false);
      addActionButton(actions, "Escalate", () => postForm(`/api/admin/incidents/${incident.id}/escalate`), false);
      card.appendChild(actions);
      card.addEventListener("mouseenter", (event) => showHover(event, incident.title || "Incident", [
        incident.summary || "",
        `${incident.scope_type || "scope"}:${incident.scope_id || ""}`,
        incident.incident_kind || "",
      ]));
      card.addEventListener("mousemove", moveHover);
      card.addEventListener("mouseleave", hideHover);
      incidentRail.appendChild(card);
    });
  }

  function renderGroups() {
    const groupGrid = document.getElementById("group-grid");
    clear(groupGrid);
    const groups = ((state.cockpit.runway || {}).groups || []).slice(0, 6);
    if (!groups.length) {
      groupGrid.appendChild(el("div", "empty", "No groups configured."));
      return;
    }
    groups.forEach((group) => {
      const statusGroup = (state.groups || []).find((item) => item.id === group.group_id) || {};
      const design = statusGroup.design_progress || group.design_progress || {};
      const designEta = statusGroup.design_eta || group.design_eta || {};
      const delivery = statusGroup.delivery_progress || {};
      const registryMissing = designRegistryMissing(design, designEta);
      const card = summaryButton(`group-card compact-card state-${tone(group.runway_risk || statusGroup.pressure_state)}`);
      const head = el("div", "summary-head");
      const title = el("div", "summary-title");
      title.appendChild(el("div", "eyebrow", `${statusGroup.phase || group.status || "unknown"} · ${group.remaining_slices || 0} left`));
      title.appendChild(el("h3", "", group.group_id));
      title.appendChild(el("div", "summary-main", registryMissing ? "Design registry missing" : (design.summary || group.bottleneck || "No current bottleneck.")));
      head.appendChild(title);
      const chips = el("div", "summary-chips");
      chips.appendChild(summaryChip("delivery", `${delivery.percent_complete || 0}%`, tone(statusGroup.phase || group.status)));
      chips.appendChild(summaryChip("design", registryMissing ? "n/a" : `${design.percent_complete || 0}%`, confidenceTone(designEta.confidence || design.eta_confidence)));
      chips.appendChild(summaryChip("Configured Queue ETA", designEta.eta_human || design.eta_human || "unknown", confidenceTone(designEta.confidence || design.eta_confidence)));
      head.appendChild(chips);
      card.appendChild(head);
      if (!registryMissing) {
        card.appendChild(progressBar(design, false));
      }
      const groupSummaryBits = [];
      if (group.eligible_parallel_slots || group.eligible_parallel_slots === 0) {
        groupSummaryBits.push(`${group.eligible_parallel_slots || 0} slots`);
      }
      if (group.slot_share_percent || group.slot_share_percent === 0) {
        groupSummaryBits.push(`${group.slot_share_percent || 0}% pool`);
      }
      if (!registryMissing && design.main_blocker) {
        groupSummaryBits.push(`blocker ${String(design.main_blocker).replace(/_/g, " ")}`);
      } else if (group.bottleneck) {
        groupSummaryBits.push(group.bottleneck);
      }
      if (groupSummaryBits.length) {
        card.appendChild(el("div", "summary-caption", groupSummaryBits.join(" · ")));
      }
      card.addEventListener("mouseenter", (event) => showHover(event, group.group_id, [
        group.bottleneck || "",
        group.finish_outlook || "",
        `status ${group.status || "unknown"}`,
        `${group.slot_share_percent || 0}% of fleet slots`,
        `${group.drain_share_percent || 0}% recent drain`,
        `${group.remaining_slices || 0} slices remaining`,
        `${group.eligible_parallel_slots || 0} eligible slots`,
        `${group.dispatch_member_count || 0} dispatch / ${group.scaffold_member_count || 0} scaffold / ${group.signoff_only_member_count || 0} signoff-only`,
        `${group.compile_attention_count || 0} compile attention`,
      ]));
      card.addEventListener("mousemove", moveHover);
      card.addEventListener("mouseleave", hideHover);
      card.addEventListener("click", () => openGroupDrawer(group.group_id));
      groupGrid.appendChild(card);
    });
  }

  function renderPools() {
    const poolList = document.getElementById("pool-list");
    clear(poolList);
    const pools = ((state.cockpit.runway || {}).accounts || []).slice(0, 4);
    if (!pools.length) {
      poolList.appendChild(el("div", "empty", "No pressured pools right now."));
      return;
    }
    pools.forEach((pool) => {
      const card = el("article", "pool-card");
      const row = el("div", "signal-row");
      row.appendChild(el("span", `signal ${tone(pool.pressure_state)}`, pool.alias));
      row.appendChild(el("span", "signal gray", pool.pressure_state || "ready"));
      card.appendChild(row);
      card.appendChild(el("h3", "", `${pool.burn_rate || "unknown burn"} | ${pool.projected_exhaustion || "unknown exhaustion"}`));
      card.appendChild(el("p", "muted", (pool.top_consumers || []).join(" | ") || "No recent top consumers."));
      const actions = el("div", "action-row");
      addActionButton(actions, "Drain", () => postForm(`/api/admin/accounts/${pool.alias}/state`, { state: "draining" }), false);
      addActionButton(actions, "Resume", () => postForm(`/api/admin/accounts/${pool.alias}/state`, { state: "ready" }), false);
      addActionButton(actions, "Disable", () => postForm(`/api/admin/accounts/${pool.alias}/state`, { state: "disabled" }), false);
      addActionButton(actions, "Validate", () => postForm(`/api/admin/accounts/${pool.alias}/validate`), true);
      card.appendChild(actions);
      card.addEventListener("mouseenter", (event) => showHover(event, pool.alias, [
        `pressure ${pool.pressure_state || "unknown"}`,
        pool.burn_rate || "",
        pool.projected_exhaustion ? `exhaustion ${pool.projected_exhaustion}` : "",
        ...(pool.top_consumers || []).slice(0, 3),
      ]));
      card.addEventListener("mousemove", moveHover);
      card.addEventListener("mouseleave", hideHover);
      poolList.appendChild(card);
    });
  }

  function renderBottomStrips() {
    const workers = state.cockpit.workers || [];
    const active = document.getElementById("active-slices");
    clear(active);
    const activeWorkers = workers.filter((worker) => ["coding", "verifying"].includes(String(worker.phase || ""))).slice(0, 6);
    if (!activeWorkers.length) {
      active.appendChild(el("div", "empty", "No active coding slices."));
    } else {
      activeWorkers.forEach((worker) => {
        const chip = el("div", "mini-chip");
        chip.appendChild(el("strong", "", worker.project_id));
        chip.appendChild(el("span", "muted", worker.current_slice || worker.phase || ""));
        const backend = String(worker.account_backend || "").trim();
        const identity = String(worker.account_identity || "").trim();
        const brain = String(worker.brain || "").trim();
        const backendLabel = [backend && backend !== "not active" ? backend : "backend", identity].filter(Boolean).join(" ");
        chip.appendChild(el("span", "muted", backendLabel || "no backend"));
        chip.appendChild(el("span", "muted", brain || "no brain"));
        active.appendChild(chip);
      });
    }

    const reviewGate = document.getElementById("review-gate");
    clear(reviewGate);
    const reviews = ((state.ops_summary || {}).prs_waiting_for_review || []).slice(0, 6);
    if (!reviews.length) {
      reviewGate.appendChild(el("div", "empty", "No review waits."));
    } else {
      reviews.forEach((project) => {
        const chip = el("div", "mini-chip");
        chip.appendChild(el("strong", "", project.id));
        chip.appendChild(
          el(
            "span",
            "muted",
            ((project.review_eta || {}).summary) || (project.pull_request || {}).review_status || "review",
          ),
        );
        reviewGate.appendChild(chip);
      });
    }

    const healerActivity = document.getElementById("healer-activity");
    clear(healerActivity);
    const healerGroups = (state.groups || []).filter((group) => ["audit_requested", "audit_required", "proposed_tasks"].includes(String(group.status || "")));
    const healerProjects = (state.projects || []).filter((project) => ["healing", "queue_refilling", "review_fix"].includes(String(project.runtime_status || "")));
    const items = healerGroups.map((group) => ({ label: group.id, detail: group.status })).concat(
      healerProjects.map((project) => {
        const compileStatus = (((project.compile_health || {}).status) || "");
        return {
          label: project.id,
          detail: [project.runtime_status, compileStatus && !["ready", "not_required"].includes(String(compileStatus)) ? `compile ${compileStatus}` : ""]
            .filter(Boolean)
            .join(" · "),
        };
      }),
    ).slice(0, 6);
    if (!items.length) {
      healerActivity.appendChild(el("div", "empty", "No healer-owned activity."));
    } else {
      items.forEach((item) => {
        const chip = el("div", "mini-chip");
        chip.appendChild(el("strong", "", item.label));
        chip.appendChild(el("span", "muted", item.detail));
        healerActivity.appendChild(chip);
      });
    }
  }

  function openLampDrawer(lamp) {
    openDrawer("Lamp", lamp.label || "Lamp", (body) => {
      const autoHealPolicies = (((state.config || {}).policies || {}).auto_heal || {});
      const summary = el("div", "drawer-section");
      summary.appendChild(el("p", "", lamp.detail || "No detail recorded."));
      if (lamp.auto_action) {
        summary.appendChild(el("p", "muted", `Auto-action: ${lamp.auto_action}`));
      }
      body.appendChild(summary);

      const affected = el("div", "drawer-section");
      affected.appendChild(el("h3", "", "Affected scopes"));
      const list = el("ul", "drawer-list");
      (lamp.summary_lines || []).forEach((item) => list.appendChild(el("li", "", item)));
      if (!list.childNodes.length) {
        list.appendChild(el("li", "", "No affected scopes right now."));
      }
      affected.appendChild(list);
      body.appendChild(affected);

      if (lamp.category) {
        const playbooks = autoHealPolicies.playbooks || {};
        const playbook = Object.prototype.hasOwnProperty.call(playbooks, lamp.category) ? playbooks[lamp.category] : null;
        if (playbook) {
          const section = el("div", "drawer-section");
          section.appendChild(el("h3", "", "Healing playbook"));
          const steps = el("ul", "drawer-list");
          (playbook.deterministic_steps || []).forEach((step) => steps.appendChild(el("li", "", step)));
          if (!steps.childNodes.length) {
            steps.appendChild(el("li", "", "No deterministic steps configured."));
          }
          section.appendChild(steps);
          const meta = [];
          meta.push(`LLM fallback: ${playbook.llm_fallback ? "enabled" : "disabled"}`);
          meta.push(`Verify: ${playbook.verify_required ? "required" : "optional"}`);
          meta.push(`Max attempts: ${playbook.max_attempts !== undefined && playbook.max_attempts !== null ? playbook.max_attempts : "n/a"}`);
          section.appendChild(el("p", "muted", meta.join(" | ")));
          body.appendChild(section);
        }
        const controls = el("div", "drawer-section");
        controls.appendChild(el("h3", "", "Policy controls"));
        const row = el("div", "action-row");
        addActionButton(row, "Auto-resolve now", () => postForm(`/api/admin/policies/auto-heal/category/${lamp.category}/resolve-now`), true);
        addActionButton(row, "Always auto-resolve this category", () => postForm(`/api/admin/policies/auto-heal/category/${lamp.category}`, { enabled: "1" }), false);
        controls.appendChild(row);

        const form = el("form", "drawer-form");
        form.addEventListener("submit", async (event) => {
          event.preventDefault();
          const attempts = form.querySelector("input").value || "0";
          await postForm(`/api/admin/policies/auto-heal/escalation/${lamp.category}`, { attempts });
        });
        form.appendChild(el("label", "", "Escalate after failed healer attempts"));
        const input = document.createElement("input");
        input.type = "number";
        input.min = "0";
        const escalationThresholds = autoHealPolicies.escalation_thresholds || {};
        input.value = String(Object.prototype.hasOwnProperty.call(escalationThresholds, lamp.category) ? escalationThresholds[lamp.category] : 0);
        form.appendChild(input);
        const submit = el("button", "", "Save threshold");
        submit.type = "submit";
        form.appendChild(submit);
        controls.appendChild(form);
        body.appendChild(controls);
      }
    });
  }

  async function openGroupDrawer(groupId) {
    const runwayGroup = ((state.cockpit.runway || {}).groups || []).find((group) => group.group_id === groupId) || {};
    const statusGroup = (state.groups || []).find((group) => group.id === groupId) || {};
    const simulations = await Promise.all(["protect", "drain", "burst"].map((action) => loadSimulation(groupId, action)));

    openDrawer("Group", groupId, (body) => {
      const summary = el("div", "drawer-section");
      summary.appendChild(el("p", "", runwayGroup.bottleneck || statusGroup.dispatch_basis || "No current bottleneck."));
      summary.appendChild(el("p", "muted", `Phase ${statusGroup.phase || runwayGroup.status || "unknown"} | pressure ${statusGroup.pressure_state || runwayGroup.runway_risk || "unknown"}`));
      summary.appendChild(
        el(
          "p",
          "muted",
          `Lifecycle ${statusGroup.lifecycle || runwayGroup.lifecycle || "unknown"} | dispatch ${statusGroup.dispatch_member_count || runwayGroup.dispatch_member_count || 0} | scaffold ${statusGroup.scaffold_member_count || runwayGroup.scaffold_member_count || 0} | signoff-only ${statusGroup.signoff_only_member_count || runwayGroup.signoff_only_member_count || 0} | compile attention ${statusGroup.compile_attention_count || runwayGroup.compile_attention_count || 0}`,
        ),
      );
      const delivery = statusGroup.delivery_progress || {};
      const design = statusGroup.design_progress || runwayGroup.design_progress || {};
      const designEta = statusGroup.design_eta || runwayGroup.design_eta || {};
      const deliverySection = el("div", "drawer-section");
      deliverySection.appendChild(el("h3", "", "Delivery progress"));
      deliverySection.appendChild(el("p", "muted", progressSummary(delivery, true)));
      deliverySection.appendChild(progressBar(delivery, true));
      summary.appendChild(deliverySection);
      const designSection = el("div", "drawer-section");
      designSection.appendChild(el("h3", "", "Design completeness"));
      designSection.appendChild(el("p", "muted", designProgressHeadline(design, designEta)));
      if (!designRegistryMissing(design, designEta)) {
        designSection.appendChild(progressBar(design, false));
      }
      designSection.appendChild(el("p", "muted", design.summary || "No design summary available."));
      if (designEta.eta_basis) {
        designSection.appendChild(el("p", "muted", `ETA basis: ${designEta.eta_basis}`));
      }
      if (design.main_blocker) {
        designSection.appendChild(el("p", "muted", `Top blocker: ${design.main_blocker}`));
      }
      summary.appendChild(designSection);
      body.appendChild(summary);

      const actions = el("div", "drawer-section");
      actions.appendChild(el("h3", "", "Bridge actions"));
      const row = el("div", "action-row");
      addActionButton(row, "Protect", () => postForm(`/api/admin/groups/${groupId}/protect`), false);
      addActionButton(row, "Drain", () => postForm(`/api/admin/groups/${groupId}/drain`), false);
      addActionButton(row, "Burst", () => postForm(`/api/admin/groups/${groupId}/burst`), false);
      addActionButton(row, "Heal now", () => postForm(`/api/admin/groups/${groupId}/heal-now`), true);
      addActionButton(row, "Pause", () => postForm(`/api/admin/groups/${groupId}/pause`), false);
      actions.appendChild(row);
      body.appendChild(actions);

      const sims = el("div", "drawer-section");
      sims.appendChild(el("h3", "", "Captain simulation"));
      simulations.forEach((simulation) => {
        const block = el("div", "drawer-section");
        block.appendChild(el("p", "", `${simulation.action}: ${simulation.notes}`));
        const list = el("ul", "drawer-list");
        (simulation.shed_candidates || []).slice(0, 3).forEach((item) => list.appendChild(el("li", "", `Likely shed: ${item}`)));
        (simulation.beneficiary_groups || []).slice(0, 3).forEach((item) => list.appendChild(el("li", "", `Likely beneficiary: ${item}`)));
        if (!list.childNodes.length) {
          list.appendChild(el("li", "", "No major secondary effects predicted."));
        }
        block.appendChild(list);
        sims.appendChild(block);
      });
      body.appendChild(sims);

      const memberSection = el("div", "drawer-section");
      memberSection.appendChild(el("h3", "", "Member projects"));
      const memberList = el("div", "drawer-list-grid");
      const members = (state.projects || []).filter((project) => Array.isArray(project.group_ids) && project.group_ids.includes(groupId));
      if (!members.length) {
        memberList.appendChild(el("div", "empty", "No member projects available in cockpit payload."));
      } else {
        members.forEach((project) => {
          const item = summaryButton("mini-project-card compact-card");
          const chips = el("div", "summary-chips");
          chips.appendChild(summaryChip("status", project.runtime_status || "unknown", tone(project.runtime_status)));
          chips.appendChild(summaryChip("design", designRegistryMissing(project.design_progress || {}, project.design_eta || {}) ? "n/a" : `${(project.design_progress || {}).percent_complete || 0}%`, confidenceTone((project.design_eta || {}).confidence || (project.design_progress || {}).eta_confidence)));
          chips.appendChild(summaryChip("Configured Queue ETA", (project.design_eta || {}).eta_human || (project.design_progress || {}).eta_human || "unknown", confidenceTone((project.design_eta || {}).confidence || (project.design_progress || {}).eta_confidence)));
          item.appendChild(chips);
          item.appendChild(el("h4", "", project.id || "project"));
          item.appendChild(el("p", "muted", projectHeadline(project)));
          if (!designRegistryMissing(project.design_progress || {}, project.design_eta || {})) {
            item.appendChild(progressBar(project.design_progress || {}, false));
          }
          item.appendChild(el("p", "muted", designRegistryMissing(project.design_progress || {}, project.design_eta || {}) ? "Design registry missing" : ((project.design_progress || {}).summary || project.next_action || project.stop_reason || "")));
          item.addEventListener("click", () => openProjectDrawer(project, groupId));
          memberList.appendChild(item);
        });
      }
      memberSection.appendChild(memberList);
      body.appendChild(memberSection);
    });
  }

  function openIncidentDrawer(incident) {
    openDrawer("Incident", incident.title || "Incident", (body) => {
      const summary = el("div", "drawer-section");
      summary.appendChild(el("p", "", incident.summary || "No summary recorded."));
      summary.appendChild(el("p", "muted", `${incident.incident_kind || "incident"} | ${incident.scope_type}:${incident.scope_id}`));
      body.appendChild(summary);

      const actions = el("div", "drawer-section");
      actions.appendChild(el("h3", "", "Incident actions"));
      const row = el("div", "action-row");
      addActionButton(row, "Auto-resolve now", () => postForm(`/api/admin/incidents/${incident.id}/auto-resolve`), true);
      addActionButton(row, "Ack", () => postForm(`/api/admin/incidents/${incident.id}/ack`), false);
      addActionButton(row, "Escalate", () => postForm(`/api/admin/incidents/${incident.id}/escalate`), false);
      const category = (() => {
        const kind = String(incident.incident_kind || "").toLowerCase();
        if (["review_failed", "review_lane_stalled", "pr_checks_failed"].includes(kind)) return "review";
        if (kind === "blocked_unresolved") return "capacity";
        return "";
      })();
      if (category) {
        addActionButton(row, "Always auto-resolve this class", () => postForm(`/api/admin/policies/auto-heal/category/${category}`, { enabled: "1" }), false);
      }
      actions.appendChild(row);
      body.appendChild(actions);

      const evidence = el("div", "drawer-section");
      evidence.appendChild(el("h3", "", "Context"));
      const pre = el("pre", "");
      pre.textContent = JSON.stringify(incident.context || {}, null, 2);
      evidence.appendChild(pre);
      body.appendChild(evidence);
    });
  }

  function render() {
    renderOperators();
    renderHeader();
    renderLamps();
    renderIncidents();
    renderGroups();
    renderPools();
    renderBottomStrips();
  }

  window.addEventListener("error", (event) => {
    showLoadError(`Bridge load failed: ${event.message || "script error"}`);
  });

  loadStatus().catch((error) => {
    showLoadError(`Bridge load failed: ${error.message}`);
  });
  window.setInterval(() => {
    loadStatus().catch(() => {});
  }, 15000);
})();
