from pathlib import Path
import importlib.util
import json
import sys


MODULE_PATH = Path("/docker/fleet/scripts/probe_magixai_api.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("probe_magixai_api", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def test_base_candidates_prefers_configured_base(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "env_value", lambda name: "https://beta.aimagicx.com/api" if name == "CHUMMER6_MAGIXAI_BASE_URL" else "")

    candidates = module.base_candidates()

    assert candidates[0] == "https://beta.aimagicx.com/api"
    assert "https://www.aimagicx.com/api/v1" in candidates


def test_base_candidates_falls_back_to_official_base_without_override(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "env_value", lambda _name: "")

    candidates = module.base_candidates()

    assert candidates[0] == module.MAGIXAI_OFFICIAL_API_BASE


def test_main_treats_contract_error_as_route_ready(monkeypatch, capsys) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "env_value", lambda name: "test-key" if name == "AI_MAGICX_API_KEY" else "")
    monkeypatch.setattr(module, "base_candidates", lambda: ["https://www.aimagicx.com/api/v1"])
    monkeypatch.setattr(module, "header_variants", lambda _api_key: [("authorization_bearer", {"Authorization": "Bearer test-key"})])
    monkeypatch.setattr(
        module,
        "request_specs",
        lambda _width, _height: [
            {
                "kind": "image_contract_probe",
                "method": "POST",
                "endpoint": module.MAGIXAI_IMAGE_ENDPOINT,
                "payload": {"model": "bad-model"},
            }
        ],
    )
    monkeypatch.setattr(
        module,
        "run_probe",
        lambda *_args, **_kwargs: {
            "status": 500,
            "content_type": "application/json",
            "allow": "",
            "body_preview": '{"error":"Invalid App Id"}',
        },
    )
    monkeypatch.setattr(sys, "argv", ["probe_magixai_api.py"])

    exit_code = module.main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert len(payload["route_ready_rows"]) == 1
    assert payload["route_ready_rows"][0]["kind"] == "image_contract_probe"
