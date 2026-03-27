from __future__ import annotations

import unittest
from pathlib import Path


DOCKER_COMPOSE = Path("/docker/fleet/docker-compose.yml")
NGINX_CONF = Path("/docker/fleet/gateway/nginx.conf")
REBUILD_LOOP = Path("/docker/fleet/scripts/rebuild-loop.sh")
RUNTIME_ENV_EXAMPLE = Path("/docker/fleet/runtime.env.example")
README = Path("/docker/fleet/README.md")


class RuntimeAutoHealContractTests(unittest.TestCase):
    def test_controller_healthcheck_uses_dedicated_script(self) -> None:
        compose = DOCKER_COMPOSE.read_text(encoding="utf-8")
        self.assertIn("python /opt/codex-fleet/scripts/healthcheck_controller.py", compose)
        self.assertIn("FLEET_CONTROLLER_HEARTBEAT_PATH: /var/lib/codex-fleet/controller-heartbeat.json", compose)
        self.assertIn('FLEET_CONTROLLER_HEARTBEAT_MAX_AGE_SECONDS: "45"', compose)

    def test_gateway_health_is_static_and_not_proxied_to_controller(self) -> None:
        nginx = NGINX_CONF.read_text(encoding="utf-8")
        self.assertIn('location = /health {', nginx)
        self.assertIn('return 200 "ok";', nginx)
        health_block = nginx.split('location = /health {', 1)[1].split('}', 1)[0]
        self.assertNotIn("proxy_pass", health_block)

    def test_rebuilder_loop_declares_autoheal_controls(self) -> None:
        script = REBUILD_LOOP.read_text(encoding="utf-8")
        self.assertIn('compose_project_name="${FLEET_COMPOSE_PROJECT_NAME:-fleet}"', script)
        self.assertIn('docker compose -p "$compose_project_name" -f "$compose_file"', script)
        self.assertIn('autoheal_enabled="$(printf', script)
        self.assertIn('autoheal_services="${FLEET_AUTOHEAL_SERVICES:-fleet-controller fleet-dashboard}"', script)
        self.assertIn('loop_once="$(printf', script)
        self.assertIn('autoheal_escalate_after_restarts="${FLEET_AUTOHEAL_ESCALATE_AFTER_RESTARTS:-3}"', script)
        self.assertIn('autoheal_event_log="$autoheal_state_dir/events.jsonl"', script)
        self.assertIn('compose_cmd restart "$service"', script)
        self.assertIn("monitor_autoheal", script)

    def test_runtime_env_and_readme_document_autoheal(self) -> None:
        env_example = RUNTIME_ENV_EXAMPLE.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        self.assertIn("FLEET_AUTOHEAL_ENABLED=true", env_example)
        self.assertIn("FLEET_AUTOHEAL_SERVICES=", env_example)
        self.assertIn("FLEET_CONTROLLER_HEARTBEAT_MAX_AGE_SECONDS=45", env_example)
        self.assertIn("FLEET_COMPOSE_PROJECT_NAME=fleet", env_example)
        self.assertIn("FLEET_AUTOHEAL_ESCALATE_AFTER_RESTARTS=3", env_example)
        self.assertIn("FLEET_AUTOHEAL_ESCALATE_WINDOW_SECONDS=1800", env_example)
        self.assertIn("bounded auto-heal", readme)
        self.assertIn("FLEET_AUTOHEAL_ENABLED=true", readme)
        self.assertIn("FLEET_CONTROLLER_HEARTBEAT_MAX_AGE_SECONDS=45", readme)
        self.assertIn("FLEET_COMPOSE_PROJECT_NAME=fleet", readme)
        self.assertIn("FLEET_AUTOHEAL_ESCALATE_AFTER_RESTARTS=3", readme)


if __name__ == "__main__":
    unittest.main()
