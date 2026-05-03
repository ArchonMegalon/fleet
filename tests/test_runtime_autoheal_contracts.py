from __future__ import annotations

import unittest
from pathlib import Path


DOCKER_COMPOSE = Path("/docker/fleet/docker-compose.yml")
NGINX_CONF = Path("/docker/fleet/gateway/nginx.conf")
REBUILD_LOOP = Path("/docker/fleet/scripts/rebuild-loop.sh")
RUN_OODA_LOOP = Path("/docker/fleet/scripts/run_ooda_design_supervisor.sh")
RUN_FLEET_OODA_CODEX_TIMER = Path("/docker/fleet/scripts/run_fleet_ooda_codex_timer.sh")
RUNTIME_ENV_EXAMPLE = Path("/docker/fleet/runtime.env.example")
README = Path("/docker/fleet/README.md")
INTERNAL_AFFAIRS_WATCHDOG = Path("/home/tibor/codexea-internal-affairs-watchdog.sh")


class RuntimeAutoHealContractTests(unittest.TestCase):
    def test_controller_healthcheck_uses_dedicated_script(self) -> None:
        compose = DOCKER_COMPOSE.read_text(encoding="utf-8")
        self.assertIn("python /opt/codex-fleet/scripts/healthcheck_controller.py", compose)
        self.assertIn("FLEET_CONTROLLER_HEARTBEAT_PATH: /var/lib/codex-fleet/controller-heartbeat.json", compose)
        self.assertIn('FLEET_CONTROLLER_HEARTBEAT_MAX_AGE_SECONDS: "45"', compose)
        self.assertIn('FLEET_CONTROLLER_HEALTH_TIMEOUT_SECONDS: "10"', compose)
        self.assertIn('FLEET_CONTROLLER_HEALTH_ALLOW_HEARTBEAT_ONLY: "1"', compose)

    def test_auditor_healthcheck_uses_dedicated_script_and_run_budget(self) -> None:
        compose = DOCKER_COMPOSE.read_text(encoding="utf-8")
        self.assertIn("python /opt/codex-fleet/scripts/healthcheck_auditor.py", compose)
        self.assertIn('FLEET_AUDITOR_RUN_MAX_AGE_SECONDS: "900"', compose)
        self.assertIn('FLEET_AUDITOR_STARTUP_GRACE_SECONDS: "180"', compose)

    def test_design_supervisor_healthcheck_uses_dedicated_script(self) -> None:
        compose = DOCKER_COMPOSE.read_text(encoding="utf-8")
        self.assertIn("python /opt/codex-fleet/scripts/healthcheck_design_supervisor.py", compose)
        self.assertIn('CHUMMER_DESIGN_SUPERVISOR_HEALTH_MAX_AGE_SECONDS: "900"', compose)

    def test_gateway_health_is_static_and_not_proxied_to_controller(self) -> None:
        nginx = NGINX_CONF.read_text(encoding="utf-8")
        self.assertIn('location = /health {', nginx)
        self.assertIn('return 200 "ok";', nginx)
        health_block = nginx.split('location = /health {', 1)[1].split('}', 1)[0]
        self.assertNotIn("proxy_pass", health_block)

    def test_rebuilder_loop_declares_autoheal_controls(self) -> None:
        script = REBUILD_LOOP.read_text(encoding="utf-8")
        compose = DOCKER_COMPOSE.read_text(encoding="utf-8")
        self.assertIn('FLEET_REBUILD_COMPOSE_FILE: /docker/fleet/docker-compose.yml', compose)
        self.assertIn('FLEET_REBUILD_STATE_DIR: /docker/fleet/state/rebuilder', compose)
        self.assertIn('command: ["sh", "/docker/fleet/scripts/rebuild-loop.sh"]', compose)
        self.assertIn('test -f /docker/fleet/state/rebuilder/heartbeat.txt', compose)
        self.assertIn('default_workspace_root="/docker/fleet"', script)
        self.assertIn('compose_project_name="${FLEET_COMPOSE_PROJECT_NAME:-fleet}"', script)
        self.assertIn('docker compose -p "$compose_project_name" -f "$compose_file"', script)
        self.assertIn('autoheal_enabled="$(printf', script)
        self.assertIn(
            'autoheal_services="${FLEET_AUTOHEAL_SERVICES:-fleet-controller fleet-dashboard fleet-auditor fleet-design-supervisor}"',
            script,
        )
        self.assertIn('loop_once="$(printf', script)
        self.assertIn('autoheal_escalate_after_restarts="${FLEET_AUTOHEAL_ESCALATE_AFTER_RESTARTS:-3}"', script)
        self.assertIn('autoheal_event_log="$autoheal_state_dir/events.jsonl"', script)
        self.assertIn('external_proof_autoingest_enabled="$(printf', script)
        self.assertIn(
            'external_proof_commands_dir="${FLEET_EXTERNAL_PROOF_COMMANDS_DIR:-$workspace_root/.codex-studio/published/external-proof-commands}"',
            script,
        )
        self.assertIn(
            'external_proof_autoingest_status_file="$external_proof_autoingest_state_dir/status.json"',
            script,
        )
        self.assertIn('proof_shell="$(command -v bash 2>/dev/null || true)"', script)
        self.assertIn('if [ -z "$proof_shell" ] && [ -x /usr/bin/bash ]; then', script)
        self.assertIn('if [ -z "$proof_shell" ] && [ -x /bin/sh ]; then', script)
        self.assertIn('PATH="${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}" "$proof_shell" "$finalize_script"', script)
        self.assertIn('compose_cmd restart "$service"', script)
        self.assertIn("monitor_autoheal", script)
        self.assertIn("monitor_external_proof_autoingest", script)

    def test_dashboard_waits_for_healthy_upstreams_and_probes_root(self) -> None:
        compose = DOCKER_COMPOSE.read_text(encoding="utf-8")
        self.assertIn("fleet-controller:\n        condition: service_healthy", compose)
        self.assertIn("fleet-auditor:\n        condition: service_healthy", compose)
        self.assertIn("http://127.0.0.1:8090/health", compose)
        self.assertIn("http://127.0.0.1:8090/", compose)

    def test_ooda_launcher_keeps_root_state_following_current_alias(self) -> None:
        script = RUN_OODA_LOOP.read_text(encoding="utf-8")
        compose = DOCKER_COMPOSE.read_text(encoding="utf-8")
        self.assertIn('current_alias="${OODA_CURRENT_ALIAS:-current_${duration_label}}"', script)
        self.assertIn('ln -sfn "$(basename "$monitor_root")" "$current_link"', script)
        self.assertIn('ln -sfn "${current_alias}/state.json" "${state_root}/state.json"', script)
        self.assertIn("Path('/var/lib/codex-fleet/design_supervisor_ooda/current_8h/state.json')", compose)

    def test_fleet_ooda_timer_prompt_bounds_live_refresh_commands(self) -> None:
        script = RUN_FLEET_OODA_CODEX_TIMER.read_text(encoding="utf-8")
        self.assertIn('workspace_root="${FLEET_OODA_CODEXEA_WORKSPACE_ROOT:-${FLEET_OODA_CODEX_WORKSPACE_ROOT:-/docker/fleet}}"', script)
        self.assertIn('state_root="${FLEET_OODA_CODEXEA_STATE_ROOT:-${FLEET_OODA_CODEX_STATE_ROOT:-${workspace_root}/state/fleet_ooda_codex_timer}}"', script)
        self.assertIn('target_shards="${FLEET_OODA_CODEXEA_TARGET_SHARDS:-${FLEET_OODA_CODEX_TARGET_SHARDS:-20}}"', script)
        self.assertIn('timeout_seconds="${FLEET_OODA_CODEXEA_TIMEOUT_SECONDS:-${FLEET_OODA_CODEX_TIMEOUT_SECONDS:-1200}}"', script)
        self.assertIn('post_guard_timeout_seconds="${FLEET_OODA_CODEXEA_POST_GUARD_TIMEOUT_SECONDS:-${FLEET_OODA_CODEX_POST_GUARD_TIMEOUT_SECONDS:-120}}"', script)
        self.assertIn('service_budget_seconds="${FLEET_OODA_CODEXEA_SERVICE_BUDGET_SECONDS:-${FLEET_OODA_CODEX_SERVICE_BUDGET_SECONDS:-1380}}"', script)
        self.assertIn('fallback_minimum_window_seconds="${FLEET_OODA_CODEXEA_FALLBACK_MINIMUM_WINDOW_SECONDS:-${FLEET_OODA_CODEX_FALLBACK_MINIMUM_WINDOW_SECONDS:-180}}"', script)
        self.assertIn('codexea_bin="${FLEET_OODA_CODEXEA_BIN:-${FLEET_OODA_CODEX_BIN:-}}"', script)
        self.assertIn('codexea_model="${FLEET_OODA_CODEXEA_MODEL:-${FLEET_OODA_CODEX_MODEL:-}}"', script)
        self.assertIn('codexea_lane="${FLEET_OODA_CODEXEA_LANE:-core}"', script)
        self.assertIn('fallback_lane="${FLEET_OODA_CODEXEA_FALLBACK_LANE:-repair}"', script)
        self.assertIn('first_response_timeout_seconds="${FLEET_OODA_CODEXEA_FIRST_RESPONSE_TIMEOUT_SECONDS:-360}"', script)
        self.assertIn('You are CodexEA running an unattended 30-minute Fleet OODA maintenance slice.', script)
        self.assertIn("Keep Fleet workers and this scheduled operator pass on EA/codexea.", script)
        self.assertIn('Chosen timer metadata for this run is in:', script)
        self.assertIn('retrying with fallback lane=%s after primary lane=%s stalled', script)
        self.assertIn('service-budget-exhausted lane=%s remaining_total=%ss post_guard_timeout=%ss; terminating attempt', script)
        self.assertIn('skipping fallback lane=%s after primary lane=%s stalled because remaining service budget=%ss is below minimum retry window=%ss', script)
        self.assertIn('timeout 20s docker compose -f docker-compose.yml ps', script)
        self.assertIn('timeout 10s df -h / || true', script)
        self.assertIn('timeout 10s free -h || true', script)
        self.assertIn('Run scripts/fleet_ooda_keeper.py --once --target-active ${target_shards}', script)
        self.assertIn("Wrap status, live-refresh, guard, keeper, docker-log, and test commands in explicit timeouts", script)
        self.assertIn("timeout 90s scripts/chummer_design_supervisor.py status --json --live-refresh", script)
        self.assertIn('timeout "${post_guard_timeout_seconds}s" python3 scripts/fleet_ooda_timer_guard.py', script)

    def test_internal_affairs_watchdog_allows_audit_when_backlog_is_productive_only(self) -> None:
        script = INTERNAL_AFFAIRS_WATCHDOG.read_text(encoding="utf-8")
        self.assertIn("/docker/fleet/state/chummer_design_supervisor/status-live-refresh.materialized.json", script)
        self.assertIn('"healthy_enough_for_internal_affairs": healthy_enough_for_internal_affairs', script)
        self.assertIn('(remaining_open > 0 and productive >= 1 and active == productive)', script)
        self.assertIn('if [[ "${healthy_enough}" != "1" ]]; then', script)
        self.assertIn('fleet-health loop still owns active remediation; deferring internal-affairs patch cycle', script)
        self.assertNotIn('fleet-health loop still owns active remediation or backlog; deferring internal-affairs patch cycle', script)

    def test_runtime_env_and_readme_document_autoheal(self) -> None:
        env_example = RUNTIME_ENV_EXAMPLE.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        self.assertIn("FLEET_AUTOHEAL_ENABLED=true", env_example)
        self.assertIn(
            'FLEET_AUTOHEAL_SERVICES="fleet-controller fleet-dashboard fleet-auditor fleet-design-supervisor"',
            env_example,
        )
        self.assertIn("FLEET_EXTERNAL_PROOF_AUTOINGEST_ENABLED=true", env_example)
        self.assertIn("FLEET_EXTERNAL_PROOF_COMMANDS_DIR=/docker/fleet/.codex-studio/published/external-proof-commands", env_example)
        self.assertIn("FLEET_EXTERNAL_PROOF_AUTOINGEST_COOLDOWN_SECONDS=120", env_example)
        self.assertIn("FLEET_CONTROLLER_HEARTBEAT_MAX_AGE_SECONDS=45", env_example)
        self.assertIn("FLEET_AUDITOR_RUN_MAX_AGE_SECONDS=900", env_example)
        self.assertIn("FLEET_AUDITOR_STARTUP_GRACE_SECONDS=180", env_example)
        self.assertIn("FLEET_COMPOSE_PROJECT_NAME=fleet", env_example)
        self.assertIn("FLEET_AUTOHEAL_ESCALATE_AFTER_RESTARTS=3", env_example)
        self.assertIn("FLEET_AUTOHEAL_ESCALATE_WINDOW_SECONDS=1800", env_example)
        self.assertIn("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_OWNER_IDS=", env_example)
        self.assertIn("CHUMMER_DESIGN_SUPERVISOR_FOCUS_OWNER=", env_example)
        self.assertIn("CHUMMER_DESIGN_SUPERVISOR_WATCHDOG_SHARD=shard-7", env_example)
        self.assertIn("CHUMMER_DESIGN_SUPERVISOR_WATCHDOG_MAX_SILENT_SECONDS=240", env_example)
        self.assertIn("CHUMMER_DESIGN_SUPERVISOR_WATCHDOG_STARTUP_GRACE_SECONDS=1800", env_example)
        self.assertIn("bounded auto-heal", readme)
        self.assertIn("FLEET_AUTOHEAL_ENABLED=true", readme)
        self.assertIn(
            'FLEET_AUTOHEAL_SERVICES="fleet-controller fleet-dashboard fleet-auditor fleet-design-supervisor"',
            readme,
        )
        self.assertIn("FLEET_EXTERNAL_PROOF_AUTOINGEST_ENABLED=true", readme)
        self.assertIn("FLEET_EXTERNAL_PROOF_COMMANDS_DIR=/docker/fleet/.codex-studio/published/external-proof-commands", readme)
        self.assertIn("FLEET_EXTERNAL_PROOF_AUTOINGEST_COOLDOWN_SECONDS=120", readme)
        self.assertIn("FLEET_CONTROLLER_HEARTBEAT_MAX_AGE_SECONDS=45", readme)
        self.assertIn("FLEET_AUDITOR_RUN_MAX_AGE_SECONDS=900", readme)
        self.assertIn("FLEET_AUDITOR_STARTUP_GRACE_SECONDS=180", readme)
        self.assertIn("FLEET_COMPOSE_PROJECT_NAME=fleet", readme)
        self.assertIn("FLEET_AUTOHEAL_ESCALATE_AFTER_RESTARTS=3", readme)
        self.assertIn("CHUMMER_DESIGN_SUPERVISOR_WATCHDOG_SHARD=shard-7", readme)
        self.assertIn("CHUMMER_DESIGN_SUPERVISOR_WATCHDOG_MAX_SILENT_SECONDS=240", readme)
        self.assertIn("CHUMMER_DESIGN_SUPERVISOR_WATCHDOG_STARTUP_GRACE_SECONDS=1800", readme)
        self.assertIn("For EA / OneMinAI lanes, the supervisor now routes each shard dynamically", readme)


if __name__ == "__main__":
    unittest.main()
