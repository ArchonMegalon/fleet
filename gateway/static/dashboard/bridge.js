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

  function renderOperators() {
    const operatorGrid = document.getElementById("operator-grid");
    if (!operatorGrid) return;
    clear(operatorGrid);
    const operators = (state.cockpit.operators || []).slice(0, 2);
    if (!operators.length) {
      operatorGrid.appendChild(el("div", "empty", "No named Codex lanes configured."));
      return;
    }
    operators.forEach((operator) => {
      const card = el("article", `operator-card state-${tone(operator.pressure_state)}`);
      const row = el("div", "signal-row");
      row.appendChild(el("span", `signal ${tone(operator.pressure_state)}`, operator.label || operator.alias));
      row.appendChild(el("span", "signal gray", operator.token_status || "ready"));
      card.appendChild(row);
      card.appendChild(el("h3", "", operator.label || operator.alias));
      card.appendChild(el("p", "muted", operator.current_summary || "No active slice right now."));

      const workList = el("div", "operator-work-list");
      if ((operator.current_work_items || []).length) {
        (operator.current_work_items || []).slice(0, 3).forEach((item) => {
          const workItem = el("div", "operator-work-item");
          workItem.appendChild(el("strong", "", item.project_id || "project"));
          workItem.appendChild(el("span", "muted", item.slice || item.phase || "working"));
          if (item.elapsed_human) {
            workItem.appendChild(el("span", "muted", item.elapsed_human));
          }
          workList.appendChild(workItem);
        });
      } else {
        const idle = el("div", "operator-work-item");
        idle.appendChild(el("strong", "", "No active project"));
        idle.appendChild(el("span", "muted", (operator.top_consumers || [])[0] || "Pool is available for reassignment."));
        workList.appendChild(idle);
      }
      card.appendChild(workList);

      const meta = el("div", "meta-row");
      meta.appendChild(el("span", "", `Pool left ${operator.pool_left || "unknown"}`));
      meta.appendChild(el("span", "", `Burn ${operator.burn_rate || "$0.000/day"}`));
      meta.appendChild(el("span", "", `ETA ${operator.projected_exhaustion || "unknown"}`));
      card.appendChild(meta);

      const meta2 = el("div", "meta-row");
      meta2.appendChild(el("span", "", `Account ${operator.alias || ""}`));
      meta2.appendChild(el("span", "", `${operator.occupied_runs || 0} engaged runs`));
      meta2.appendChild(el("span", "", (operator.allowed_models || []).join(", ") || "no models"));
      card.appendChild(meta2);

      if ((operator.top_consumers || []).length) {
        card.appendChild(el("p", "muted", (operator.top_consumers || []).join(" | ")));
      }

      card.addEventListener("mouseenter", (event) => showHover(event, operator.label || operator.alias || "Codex lane", [
        operator.current_summary || "",
        `Token status ${operator.token_status || "ready"}`,
        `Pool left ${operator.pool_left || "unknown"}`,
        `Burn ${operator.burn_rate || "$0.000/day"}`,
        `Projected exhaustion ${operator.projected_exhaustion || "unknown"}`,
        ...(operator.top_consumers || []).slice(0, 3),
      ]));
      card.addEventListener("mousemove", moveHover);
      card.addEventListener("mouseleave", hideHover);
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
      const card = el("article", "group-card");
      const signalRow = el("div", "signal-row");
      signalRow.appendChild(el("span", `signal ${tone(group.runway_risk)}`, group.runway_risk || group.status || "nominal"));
      signalRow.appendChild(el("span", "signal gray", `priority ${group.priority}`));
      card.appendChild(signalRow);
      card.appendChild(el("h3", "", group.group_id));
      card.appendChild(el("p", "muted", group.bottleneck || "No current bottleneck."));
      const meta = el("div", "meta-row");
      meta.appendChild(el("span", "", group.finish_outlook || "runway outlook unknown"));
      meta.appendChild(el("span", "", `${group.slot_share_percent || 0}% pool`));
      meta.appendChild(el("span", "", `${group.drain_share_percent || 0}% drain`));
      card.appendChild(meta);
      const meta2 = el("div", "meta-row");
      meta2.appendChild(el("span", "", `lifecycle ${group.lifecycle || "unknown"}`));
      meta2.appendChild(el("span", "", `phase ${group.status}`));
      meta2.appendChild(el("span", "", `${group.dispatch_member_count || 0} dispatch`));
      meta2.appendChild(el("span", "", `${group.remaining_slices} slices`));
      card.appendChild(meta2);
      const design = group.design_progress || {};
      const designEta = group.design_eta || {};
      const designBlock = el("div", "progress-stack");
      designBlock.appendChild(el("div", "progress-label", `Design completeness ${design.percent_complete || 0}% · ETA ${designEta.eta_human || design.eta_human || "unknown"} · ${designEta.confidence || design.eta_confidence || "low"}`));
      designBlock.appendChild(progressBar(design, false));
      designBlock.appendChild(el("div", "muted", design.summary || "No design summary available."));
      card.appendChild(designBlock);
      const actions = el("div", "action-row");
      addActionButton(actions, "Protect", () => postForm(`/api/admin/groups/${group.group_id}/protect`), false);
      addActionButton(actions, "Drain", () => postForm(`/api/admin/groups/${group.group_id}/drain`), false);
      addActionButton(actions, "Burst", () => postForm(`/api/admin/groups/${group.group_id}/burst`), false);
      addActionButton(actions, "Heal", () => postForm(`/api/admin/groups/${group.group_id}/heal-now`), true);
      addActionButton(actions, "Pause", () => postForm(`/api/admin/groups/${group.group_id}/pause`), false);
      addActionButton(actions, "Open", () => Promise.resolve(openGroupDrawer(group.group_id)), false);
      card.appendChild(actions);
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
      designSection.appendChild(el("p", "muted", `${progressSummary(design, false)} | ETA ${designEta.eta_human || design.eta_human || "unknown"} | ${designEta.confidence || design.eta_confidence || "low"} confidence`));
      designSection.appendChild(progressBar(design, false));
      designSection.appendChild(el("p", "muted", design.summary || "No design summary available."));
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
          const item = el("article", "mini-project-card");
          item.appendChild(el("h4", "", `${project.id} · ${project.runtime_status || "unknown"}`));
          item.appendChild(el("p", "muted", `${project.current_slice || "no active slice"} · ETA ${(project.design_eta || {}).eta_human || (project.design_progress || {}).eta_human || "unknown"}`));
          item.appendChild(el("p", "muted", progressSummary(project.design_progress || {}, false)));
          item.appendChild(progressBar(project.design_progress || {}, false));
          item.appendChild(el("p", "muted", (project.design_progress || {}).summary || project.stop_reason || ""));
          if ((project.design_progress || {}).main_blocker) {
            item.appendChild(el("p", "muted", `Blocker: ${(project.design_progress || {}).main_blocker}`));
          }
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
