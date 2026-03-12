#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
from textwrap import dedent


EA_ROOT = Path("/docker/EA")


def write(path: str, content: str) -> None:
    target = EA_ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    target = EA_ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected snippet missing in {path}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def regex_replace(path: str, pattern: str, repl: str) -> None:
    target = EA_ROOT / path
    text = target.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, repl, text, count=1, flags=re.MULTILINE | re.DOTALL)
    if count != 1:
        raise RuntimeError(f"expected regex match missing in {path}: {pattern}")
    target.write_text(updated, encoding="utf-8")


def append_if_missing(path: str, snippet: str) -> None:
    target = EA_ROOT / path
    text = target.read_text(encoding="utf-8")
    if snippet in text:
        return
    target.write_text(text + ("\n" if not text.endswith("\n") else "") + snippet, encoding="utf-8")


def patch_settings() -> None:
    write(
        "ea/app/settings.py",
        dedent(
            """\
            from __future__ import annotations

            import os
            import warnings
            from dataclasses import dataclass, replace


            def _to_int(raw: str, default: int) -> int:
                try:
                    return int(raw)
                except Exception:
                    return default


            @dataclass(frozen=True)
            class CoreSettings:
                app_name: str
                app_version: str
                role: str
                host: str
                port: int
                log_level: str
                tenant_id: str


            @dataclass(frozen=True)
            class RuntimeSettings:
                mode: str


            @dataclass(frozen=True)
            class StorageSettings:
                backend: str
                database_url: str
                artifacts_dir: str


            @dataclass(frozen=True)
            class AuthSettings:
                api_token: str
                default_principal_id: str

                @property
                def enabled(self) -> bool:
                    return bool(self.api_token.strip())


            @dataclass(frozen=True)
            class PolicySettings:
                max_rewrite_chars: int
                approval_required_chars: int
                approval_ttl_minutes: int


            @dataclass(frozen=True)
            class ChannelSettings:
                default_list_limit: int


            @dataclass(frozen=True)
            class RuntimeProfile:
                mode: str
                storage_backend: str
                durability: str
                auth_mode: str
                principal_source: str
                database_required: bool
                database_configured: bool
                source_backend: str

                @property
                def caller_principal_header_allowed(self) -> bool:
                    return self.auth_mode == "token"


            @dataclass(frozen=True)
            class Settings:
                core: CoreSettings
                runtime: RuntimeSettings
                storage: StorageSettings
                auth: AuthSettings
                policy: PolicySettings
                channels: ChannelSettings

                @property
                def app_name(self) -> str:
                    return self.core.app_name

                @property
                def app_version(self) -> str:
                    return self.core.app_version

                @property
                def role(self) -> str:
                    return self.core.role

                @property
                def host(self) -> str:
                    return self.core.host

                @property
                def port(self) -> int:
                    return self.core.port

                @property
                def log_level(self) -> str:
                    return self.core.log_level

                @property
                def tenant_id(self) -> str:
                    return self.core.tenant_id

                @property
                def runtime_mode(self) -> str:
                    return self.runtime.mode

                @property
                def storage_backend(self) -> str:
                    return self.storage.backend

                @property
                def database_url(self) -> str:
                    return self.storage.database_url

                @property
                def ledger_backend(self) -> str:
                    return self.storage.backend

                @property
                def storage_fallback_allowed(self) -> bool:
                    return not is_prod_mode(self.runtime.mode)


            def _runtime_mode(raw: str) -> str:
                mode = str(raw or "").strip().lower() or "dev"
                if mode not in {"dev", "test", "prod"}:
                    return "dev"
                return mode


            def is_prod_mode(raw: str | None) -> bool:
                return str(raw or "").strip().lower() == "prod"


            def resolve_runtime_profile(settings: Settings) -> RuntimeProfile:
                source_backend = str(settings.storage.backend or "auto").strip().lower() or "auto"
                if is_prod_mode(settings.runtime.mode):
                    return RuntimeProfile(
                        mode="prod",
                        storage_backend="postgres",
                        durability="durable",
                        auth_mode="token",
                        principal_source="authenticated_header",
                        database_required=True,
                        database_configured=bool(settings.database_url),
                        source_backend=source_backend,
                    )
                storage_backend = "postgres" if source_backend in {"postgres"} else "memory"
                durability = "durable" if storage_backend == "postgres" else "ephemeral"
                if source_backend == "auto" and settings.database_url:
                    storage_backend = "postgres"
                    durability = "durable"
                auth_mode = "token" if settings.auth.enabled else "anonymous_dev"
                principal_source = "authenticated_header" if settings.auth.enabled else "default_principal"
                return RuntimeProfile(
                    mode=settings.runtime.mode,
                    storage_backend=storage_backend,
                    durability=durability,
                    auth_mode=auth_mode,
                    principal_source=principal_source,
                    database_required=storage_backend == "postgres",
                    database_configured=bool(settings.database_url),
                    source_backend=source_backend,
                )


            def settings_with_storage_backend(settings: Settings, backend: str) -> Settings:
                normalized = str(backend or "").strip().lower() or "memory"
                return replace(settings, storage=replace(settings.storage, backend=normalized))


            def ensure_storage_fallback_allowed(
                settings: Settings,
                reason: str,
                exc: Exception | None = None,
            ) -> None:
                if settings.storage_fallback_allowed:
                    return
                if exc is not None:
                    message = str(exc)
                    if message.startswith("EA_RUNTIME_MODE=prod forbids memory fallback"):
                        raise exc
                message = f"EA_RUNTIME_MODE=prod forbids memory fallback({reason})"
                if exc is not None:
                    raise RuntimeError(message) from exc
                raise RuntimeError(message)


            def ensure_prod_api_token_configured(settings: Settings) -> None:
                if not is_prod_mode(settings.runtime.mode):
                    return
                if str(settings.auth.api_token or "").strip():
                    return
                raise RuntimeError("EA_RUNTIME_MODE=prod requires EA_API_TOKEN to be set")


            def validate_startup_settings(settings: Settings) -> RuntimeProfile:
                profile = resolve_runtime_profile(settings)
                ensure_prod_api_token_configured(settings)
                if is_prod_mode(settings.runtime.mode):
                    if profile.storage_backend != "postgres":
                        raise RuntimeError("EA_RUNTIME_MODE=prod requires a durable postgres runtime profile")
                    if not settings.database_url:
                        raise RuntimeError("EA_RUNTIME_MODE=prod requires DATABASE_URL")
                return profile


            def get_settings() -> Settings:
                app_name = (os.environ.get("EA_APP_NAME") or "ea-rewrite").strip() or "ea-rewrite"
                app_version = (os.environ.get("EA_APP_VERSION") or "0.3.0").strip() or "0.3.0"
                role = (os.environ.get("EA_ROLE") or "api").strip().lower() or "api"
                host = (os.environ.get("EA_HOST") or "0.0.0.0").strip() or "0.0.0.0"
                port = max(1, min(65535, _to_int(os.environ.get("EA_PORT") or "8090", 8090)))
                log_level = (os.environ.get("EA_LOG_LEVEL") or "INFO").strip().upper() or "INFO"
                tenant_id = (os.environ.get("EA_TENANT_ID") or "default").strip() or "default"
                runtime_mode = _runtime_mode(os.environ.get("EA_RUNTIME_MODE") or "dev")

                legacy_backend = (os.environ.get("EA_LEDGER_BACKEND") or "").strip().lower()
                configured_storage_backend = (os.environ.get("EA_STORAGE_BACKEND") or "").strip().lower()
                if legacy_backend and not configured_storage_backend:
                    warnings.warn(
                        "EA_LEDGER_BACKEND is deprecated; use EA_STORAGE_BACKEND instead.",
                        DeprecationWarning,
                        stacklevel=2,
                    )
                elif legacy_backend and configured_storage_backend:
                    warnings.warn(
                        "EA_LEDGER_BACKEND is deprecated and ignored when EA_STORAGE_BACKEND is set.",
                        DeprecationWarning,
                        stacklevel=2,
                    )
                storage_backend = (configured_storage_backend or legacy_backend or "auto").strip().lower() or "auto"
                database_url = (os.environ.get("DATABASE_URL") or "").strip()
                artifacts_dir = (os.environ.get("EA_ARTIFACTS_DIR") or "/tmp/ea_artifacts").strip() or "/tmp/ea_artifacts"

                api_token = (os.environ.get("EA_API_TOKEN") or "").strip()
                default_principal_id = (os.environ.get("EA_DEFAULT_PRINCIPAL_ID") or "local-user").strip() or "local-user"
                max_rewrite_chars = max(1, _to_int(os.environ.get("EA_MAX_REWRITE_CHARS") or "20000", 20000))
                approval_required_chars = max(1, _to_int(os.environ.get("EA_APPROVAL_THRESHOLD_CHARS") or "5000", 5000))
                approval_ttl_minutes = max(1, _to_int(os.environ.get("EA_APPROVAL_TTL_MINUTES") or "120", 120))
                default_list_limit = max(1, min(500, _to_int(os.environ.get("EA_CHANNEL_DEFAULT_LIMIT") or "50", 50)))

                settings = Settings(
                    core=CoreSettings(
                        app_name=app_name,
                        app_version=app_version,
                        role=role,
                        host=host,
                        port=port,
                        log_level=log_level,
                        tenant_id=tenant_id,
                    ),
                    runtime=RuntimeSettings(mode=runtime_mode),
                    storage=StorageSettings(
                        backend=storage_backend,
                        database_url=database_url,
                        artifacts_dir=artifacts_dir,
                    ),
                    auth=AuthSettings(api_token=api_token, default_principal_id=default_principal_id),
                    policy=PolicySettings(
                        max_rewrite_chars=max_rewrite_chars,
                        approval_required_chars=approval_required_chars,
                        approval_ttl_minutes=approval_ttl_minutes,
                    ),
                    channels=ChannelSettings(default_list_limit=default_list_limit),
                )
                validate_startup_settings(settings)
                return settings
            """
        ),
    )


def patch_container() -> None:
    write(
        "ea/app/container.py",
        dedent(
            """\
            from __future__ import annotations

            import logging
            from dataclasses import dataclass

            from app.repositories.artifacts import InMemoryArtifactRepository
            from app.repositories.connector_bindings import InMemoryConnectorBindingRepository
            from app.repositories.commitments import InMemoryCommitmentRepository
            from app.repositories.communication_policies import InMemoryCommunicationPolicyRepository
            from app.repositories.decision_windows import InMemoryDecisionWindowRepository
            from app.repositories.deadline_windows import InMemoryDeadlineWindowRepository
            from app.repositories.delivery_outbox import InMemoryDeliveryOutboxRepository
            from app.repositories.delivery_preferences import InMemoryDeliveryPreferenceRepository
            from app.repositories.entities import InMemoryEntityRepository
            from app.repositories.evidence_objects import InMemoryEvidenceObjectRepository
            from app.repositories.follow_ups import InMemoryFollowUpRepository
            from app.repositories.follow_up_rules import InMemoryFollowUpRuleRepository
            from app.repositories.interruption_budgets import InMemoryInterruptionBudgetRepository
            from app.repositories.authority_bindings import InMemoryAuthorityBindingRepository
            from app.repositories.memory_candidates import InMemoryMemoryCandidateRepository
            from app.repositories.memory_items import InMemoryMemoryItemRepository
            from app.repositories.observation import InMemoryObservationEventRepository
            from app.repositories.relationships import InMemoryRelationshipRepository
            from app.repositories.stakeholders import InMemoryStakeholderRepository
            from app.repositories.tool_registry import InMemoryToolRegistryRepository
            from app.services.channel_runtime import ChannelRuntimeService, build_channel_runtime
            from app.services.evidence_runtime import EvidenceRuntimeService, build_evidence_runtime
            from app.services.memory_runtime import MemoryRuntimeService, build_memory_runtime
            from app.services.orchestrator import RewriteOrchestrator, build_artifact_repo, build_default_orchestrator
            from app.services.planner import PlannerService
            from app.services.policy import PolicyDecisionService
            from app.services.provider_registry import ProviderRegistryService
            from app.services.skills import SkillCatalogService
            from app.services.task_contracts import TaskContractService, build_task_contract_service
            from app.services.tool_execution import ToolExecutionService
            from app.services.tool_runtime import ToolRuntimeService, build_tool_runtime
            from app.settings import (
                RuntimeProfile,
                Settings,
                ensure_prod_api_token_configured,
                get_settings,
                settings_with_storage_backend,
                validate_startup_settings,
            )


            class ReadinessService:
                def __init__(self, settings: Settings) -> None:
                    self._settings = settings

                def check(self) -> tuple[bool, str]:
                    try:
                        profile = validate_startup_settings(self._settings)
                    except RuntimeError as exc:
                        message = str(exc)
                        if "EA_API_TOKEN" in message:
                            return False, "prod_api_token_missing"
                        if "DATABASE_URL" in message:
                            return False, "database_url_missing"
                        return False, "startup_validation_failed"
                    if profile.storage_backend == "memory":
                        if str(self._settings.storage.backend or "").strip().lower() == "memory":
                            return True, "memory_ready"
                        return True, "auto_memory_ready"
                    if not self._settings.database_url:
                        return False, "database_url_missing"
                    return self._probe_database()

                def _probe_database(self) -> tuple[bool, str]:
                    try:
                        import psycopg
                    except Exception:
                        return False, "psycopg_missing"
                    try:
                        with psycopg.connect(self._settings.database_url, autocommit=True) as conn:
                            with conn.cursor() as cur:
                                cur.execute("SELECT 1")
                                _ = cur.fetchone()
                        return True, "postgres_ready"
                    except Exception as exc:
                        return False, f"postgres_unavailable:{exc.__class__.__name__}"


            @dataclass(frozen=True)
            class AppContainer:
                settings: Settings
                runtime_profile: RuntimeProfile
                orchestrator: RewriteOrchestrator
                channel_runtime: ChannelRuntimeService
                tool_runtime: ToolRuntimeService
                tool_execution: ToolExecutionService
                evidence_runtime: EvidenceRuntimeService
                memory_runtime: MemoryRuntimeService
                task_contracts: TaskContractService
                skills: SkillCatalogService
                planner: PlannerService
                provider_registry: ProviderRegistryService
                readiness: ReadinessService


            def _build_container_for_settings(settings: Settings, profile: RuntimeProfile) -> AppContainer:
                artifacts = build_artifact_repo(settings)
                task_contracts = build_task_contract_service(settings=settings)
                planner = PlannerService(task_contracts)
                skills = SkillCatalogService(task_contracts)
                channel_runtime = build_channel_runtime(settings=settings)
                memory_runtime = build_memory_runtime(settings=settings)
                evidence_runtime = build_evidence_runtime(settings=settings)
                tool_runtime = build_tool_runtime(settings=settings)
                tool_execution = ToolExecutionService(
                    tool_runtime=tool_runtime,
                    artifacts=artifacts,
                    channel_runtime=channel_runtime,
                    evidence_runtime=evidence_runtime,
                )
                orchestrator = build_default_orchestrator(
                    settings=settings,
                    artifacts=artifacts,
                    task_contracts=task_contracts,
                    planner=planner,
                    evidence_runtime=evidence_runtime,
                    memory_runtime=memory_runtime,
                    tool_execution=tool_execution,
                )
                return AppContainer(
                    settings=settings,
                    runtime_profile=profile,
                    orchestrator=orchestrator,
                    channel_runtime=channel_runtime,
                    tool_runtime=tool_runtime,
                    tool_execution=tool_execution,
                    evidence_runtime=evidence_runtime,
                    memory_runtime=memory_runtime,
                    task_contracts=task_contracts,
                    skills=skills,
                    planner=planner,
                    provider_registry=ProviderRegistryService(),
                    readiness=ReadinessService(settings),
                )


            def build_container(settings: Settings | None = None) -> AppContainer:
                configured = settings or get_settings()
                profile = validate_startup_settings(configured)
                ensure_prod_api_token_configured(configured)
                log = logging.getLogger("ea.container")
                if profile.storage_backend == "memory":
                    effective_settings = settings_with_storage_backend(configured, "memory")
                    memory_profile = validate_startup_settings(effective_settings)
                    return _build_container_for_settings(effective_settings, memory_profile)

                effective_settings = settings_with_storage_backend(configured, "postgres")
                postgres_profile = validate_startup_settings(effective_settings)
                try:
                    return _build_container_for_settings(effective_settings, postgres_profile)
                except Exception as exc:
                    if str(configured.storage.backend or "").strip().lower() == "auto" and configured.storage_fallback_allowed:
                        log.warning("postgres runtime profile unavailable, switching whole container to memory: %s", exc)
                        memory_settings = settings_with_storage_backend(configured, "memory")
                        memory_profile = validate_startup_settings(memory_settings)
                        return _build_container_for_settings(memory_settings, memory_profile)
                    raise
            """
        ),
    )


def patch_dependencies() -> None:
    write(
        "ea/app/api/dependencies.py",
        dedent(
            """\
            from __future__ import annotations

            from dataclasses import dataclass

            from fastapi import Depends, HTTPException, Request

            from app.container import AppContainer
            from app.settings import is_prod_mode


            def get_container(request: Request) -> AppContainer:
                container = getattr(request.app.state, "container", None)
                if container is None:
                    raise RuntimeError("application container is not initialized")
                return container


            def _extract_token(request: Request) -> str:
                header = str(request.headers.get("authorization") or "").strip()
                if header.lower().startswith("bearer "):
                    return header[7:].strip()
                return str(request.headers.get("x-api-token") or "").strip()


            def _configured_api_token(container: AppContainer) -> str:
                return str(container.settings.auth.api_token or "").strip()


            def _is_prod_mode(container: AppContainer) -> bool:
                return is_prod_mode(container.settings.runtime.mode)


            def _resolved_principal_id(request: Request, *, container: AppContainer) -> str:
                expected = _configured_api_token(container)
                if expected:
                    principal_id = str(request.headers.get("x-ea-principal-id") or "").strip()
                    if principal_id:
                        return principal_id
                if _is_prod_mode(container):
                    return ""
                return str(container.settings.auth.default_principal_id or "").strip() or "local-user"


            def require_request_auth(
                request: Request,
                container: AppContainer = Depends(get_container),
            ) -> None:
                if _is_prod_mode(container) and not _configured_api_token(container):
                    raise HTTPException(status_code=401, detail="auth_required")
                expected = _configured_api_token(container)
                if not expected:
                    return
                provided = _extract_token(request)
                if provided == expected:
                    return
                raise HTTPException(status_code=401, detail="auth_required")


            @dataclass(frozen=True)
            class RequestContext:
                principal_id: str
                authenticated: bool


            def get_request_context(
                request: Request,
                container: AppContainer = Depends(get_container),
            ) -> RequestContext:
                if _is_prod_mode(container) and not _configured_api_token(container):
                    raise HTTPException(status_code=401, detail="auth_required")
                authenticated = False
                expected = _configured_api_token(container)
                if expected:
                    provided = _extract_token(request)
                    if provided != expected:
                        raise HTTPException(status_code=401, detail="auth_required")
                    authenticated = True
                elif _is_prod_mode(container):
                    raise HTTPException(status_code=401, detail="principal_required")

                principal_id = _resolved_principal_id(request, container=container)
                if not principal_id and _is_prod_mode(container):
                    raise HTTPException(status_code=401, detail="principal_required")
                if not principal_id:
                    raise HTTPException(status_code=401, detail="principal_required")
                return RequestContext(principal_id=principal_id, authenticated=authenticated)


            def resolve_principal_id(requested_principal_id: str | None, context: RequestContext) -> str:
                requested = str(requested_principal_id or "").strip()
                if requested and requested != context.principal_id:
                    raise HTTPException(status_code=403, detail="principal_scope_mismatch")
                return context.principal_id
            """
        ),
    )


def patch_app_factory() -> None:
    write(
        "ea/app/api/app.py",
        dedent(
            """\
            from __future__ import annotations

            from fastapi import Depends, FastAPI

            from app.api.dependencies import require_request_auth
            from app.api.errors import install_error_handlers
            from app.api.threadpool_compat import inline_sync_handlers_enabled, install_inline_threadpool_compat
            from app.container import build_container
            from app.settings import get_settings, validate_startup_settings


            def create_app() -> FastAPI:
                s = get_settings()
                validate_startup_settings(s)
                if inline_sync_handlers_enabled():
                    install_inline_threadpool_compat()
                from app.api.routes.channels import router as channels_router
                from app.api.routes.connectors import router as connectors_router
                from app.api.routes.delivery import router as delivery_router
                from app.api.routes.evidence import router as evidence_router
                from app.api.routes.health import router as health_router
                from app.api.routes.human import router as human_router
                from app.api.routes.memory import router as memory_router
                from app.api.routes.observations import router as observations_router
                from app.api.routes.plans import router as plans_router
                from app.api.routes.policy import router as policy_router
                from app.api.routes.rewrite import router as rewrite_router
                from app.api.routes.skills import router as skills_router
                from app.api.routes.task_contracts import router as task_contracts_router
                from app.api.routes.tools import router as tools_router

                app = FastAPI(title=s.app_name, version=s.app_version)
                install_error_handlers(app)
                app.state.container = build_container(settings=s)
                app.include_router(health_router)
                auth_dependency = [Depends(require_request_auth)]
                app.include_router(channels_router, dependencies=auth_dependency)
                app.include_router(human_router, dependencies=auth_dependency)
                app.include_router(memory_router, dependencies=auth_dependency)
                app.include_router(evidence_router, dependencies=auth_dependency)
                app.include_router(observations_router, dependencies=auth_dependency)
                app.include_router(delivery_router, dependencies=auth_dependency)
                app.include_router(connectors_router, dependencies=auth_dependency)
                app.include_router(policy_router, dependencies=auth_dependency)
                app.include_router(plans_router, dependencies=auth_dependency)
                app.include_router(rewrite_router, dependencies=auth_dependency)
                app.include_router(skills_router, dependencies=auth_dependency)
                app.include_router(task_contracts_router, dependencies=auth_dependency)
                app.include_router(tools_router, dependencies=auth_dependency)
                return app
            """
        ),
    )


def patch_task_contracts() -> None:
    write(
        "ea/app/services/task_contracts.py",
        dedent(
            """\
            from __future__ import annotations

            import logging
            from typing import Any

            from app.domain.models import (
                IntentSpecV3,
                TaskContract,
                TaskContractRuntimePolicy,
                TaskContractSkillCatalogPolicy,
                now_utc_iso,
                parse_task_contract_runtime_policy,
            )
            from app.repositories.task_contracts import InMemoryTaskContractRepository, TaskContractRepository
            from app.repositories.task_contracts_postgres import PostgresTaskContractRepository
            from app.settings import Settings, ensure_storage_fallback_allowed, get_settings


            def serialize_task_contract_runtime_policy(policy: TaskContractRuntimePolicy) -> dict[str, Any]:
                metadata: dict[str, Any] = {
                    "class": str(policy.budget_class or "low"),
                    "workflow_template": str(policy.workflow_template or "rewrite"),
                    "browseract_timeout_budget_seconds": int(policy.browseract_timeout_budget_seconds),
                    "post_artifact_packs": list(policy.post_artifact_packs or ()),
                    "artifact_failure_strategy": policy.artifact_retry.failure_strategy,
                    "artifact_max_attempts": int(policy.artifact_retry.max_attempts),
                    "artifact_retry_backoff_seconds": int(policy.artifact_retry.retry_backoff_seconds),
                    "dispatch_failure_strategy": policy.dispatch_retry.failure_strategy,
                    "dispatch_max_attempts": int(policy.dispatch_retry.max_attempts),
                    "dispatch_retry_backoff_seconds": int(policy.dispatch_retry.retry_backoff_seconds),
                    "browseract_failure_strategy": policy.browseract_retry.failure_strategy,
                    "browseract_max_attempts": int(policy.browseract_retry.max_attempts),
                    "browseract_retry_backoff_seconds": int(policy.browseract_retry.retry_backoff_seconds),
                    "human_review_role": str(policy.human_review.role or ""),
                    "human_review_task_type": str(policy.human_review.task_type or ""),
                    "human_review_brief": str(policy.human_review.brief or ""),
                    "human_review_priority": str(policy.human_review.priority or ""),
                    "human_review_sla_minutes": int(policy.human_review.sla_minutes),
                    "human_review_auto_assign_if_unique": bool(policy.human_review.auto_assign_if_unique),
                    "human_review_desired_output_json": dict(policy.human_review.desired_output_json or {}),
                    "human_review_authority_required": str(policy.human_review.authority_required or ""),
                    "human_review_why_human": str(policy.human_review.why_human or ""),
                    "human_review_quality_rubric_json": dict(policy.human_review.quality_rubric_json or {}),
                    "memory_candidate_category": str(policy.memory_candidate.category or ""),
                    "memory_candidate_sensitivity": str(policy.memory_candidate.sensitivity or ""),
                    "memory_candidate_confidence": float(policy.memory_candidate.confidence),
                    "artifact_output_template": str(policy.artifact_output.template or ""),
                    "evidence_pack_confidence": float(policy.artifact_output.default_confidence),
                    "skill_catalog_json": {
                        "skill_key": str(policy.skill_catalog.skill_key or ""),
                        "name": str(policy.skill_catalog.name or ""),
                        "description": str(policy.skill_catalog.description or ""),
                        "memory_reads": list(policy.skill_catalog.memory_reads or ()),
                        "memory_writes": list(policy.skill_catalog.memory_writes or ()),
                        "tags": list(policy.skill_catalog.tags or ()),
                        "input_schema_json": dict(policy.skill_catalog.input_schema_json or {}),
                        "output_schema_json": dict(policy.skill_catalog.output_schema_json or {}),
                        "authority_profile_json": dict(policy.skill_catalog.authority_profile_json or {}),
                        "model_policy_json": dict(policy.skill_catalog.model_policy_json or {}),
                        "provider_hints_json": dict(policy.skill_catalog.provider_hints_json or {}),
                        "tool_policy_json": dict(policy.skill_catalog.tool_policy_json or {}),
                        "human_policy_json": dict(policy.skill_catalog.human_policy_json or {}),
                        "evaluation_cases_json": [dict(value) for value in policy.skill_catalog.evaluation_cases_json],
                    },
                }
                if str(policy.pre_artifact_tool_name or "").strip():
                    metadata["pre_artifact_tool_name"] = str(policy.pre_artifact_tool_name).strip()
                return metadata


            class TaskContractService:
                def __init__(self, repo: TaskContractRepository) -> None:
                    self._repo = repo

                def _require_principal_id(self, principal_id: str) -> str:
                    resolved = str(principal_id or "").strip()
                    if resolved:
                        return resolved
                    raise ValueError("principal_id_required")

                def upsert_contract(
                    self,
                    *,
                    task_key: str,
                    deliverable_type: str,
                    default_risk_class: str,
                    default_approval_class: str,
                    allowed_tools: tuple[str, ...] = (),
                    evidence_requirements: tuple[str, ...] = (),
                    memory_write_policy: str = "reviewed_only",
                    budget_policy_json: dict[str, object] | None = None,
                    runtime_policy: TaskContractRuntimePolicy | None = None,
                ) -> TaskContract:
                    policy_payload = dict(budget_policy_json or {})
                    if runtime_policy is not None:
                        policy_payload.update(serialize_task_contract_runtime_policy(runtime_policy))
                    row = TaskContract(
                        task_key=str(task_key or "").strip(),
                        deliverable_type=str(deliverable_type or ""),
                        default_risk_class=str(default_risk_class or "low"),
                        default_approval_class=str(default_approval_class or "none"),
                        allowed_tools=tuple(str(v) for v in allowed_tools),
                        evidence_requirements=tuple(str(v) for v in evidence_requirements),
                        memory_write_policy=str(memory_write_policy or "reviewed_only"),
                        budget_policy_json=policy_payload,
                        updated_at=now_utc_iso(),
                    )
                    return self._repo.upsert(row)

                def get_contract(self, task_key: str) -> TaskContract | None:
                    return self._repo.get(task_key)

                def list_contracts(self, limit: int = 100) -> list[TaskContract]:
                    return self._repo.list_all(limit=limit)

                def contract_or_default(self, task_key: str) -> TaskContract:
                    found = self._repo.get(task_key)
                    if found:
                        return found
                    if task_key == "rewrite_text":
                        return TaskContract(
                            task_key="rewrite_text",
                            deliverable_type="rewrite_note",
                            default_risk_class="low",
                            default_approval_class="none",
                            allowed_tools=("artifact_repository",),
                            evidence_requirements=(),
                            memory_write_policy="reviewed_only",
                            budget_policy_json={"class": "low"},
                            updated_at=now_utc_iso(),
                        )
                    return TaskContract(
                        task_key=task_key,
                        deliverable_type="generic_artifact",
                        default_risk_class="low",
                        default_approval_class="none",
                        allowed_tools=(),
                        evidence_requirements=(),
                        memory_write_policy="reviewed_only",
                        budget_policy_json={"class": "low"},
                        updated_at=now_utc_iso(),
                    )

                def compile_rewrite_intent(
                    self,
                    principal_id: str,
                    *,
                    goal: str = "rewrite supplied text into an artifact",
                ) -> IntentSpecV3:
                    contract = self.contract_or_default("rewrite_text")
                    budget_class = str(contract.runtime_policy().budget_class or "low")
                    return IntentSpecV3(
                        principal_id=self._require_principal_id(principal_id),
                        goal=str(goal or "rewrite supplied text into an artifact"),
                        task_type=contract.task_key,
                        deliverable_type=contract.deliverable_type,
                        risk_class=contract.default_risk_class,
                        approval_class=contract.default_approval_class,
                        budget_class=budget_class,
                        allowed_tools=contract.allowed_tools,
                        evidence_requirements=contract.evidence_requirements,
                        desired_artifact=contract.deliverable_type,
                        memory_write_policy=contract.memory_write_policy,
                    )


            def _backend_mode(settings: Settings) -> str:
                return str(settings.storage.backend or "auto").strip().lower()


            def build_task_contract_repo(settings: Settings) -> TaskContractRepository:
                backend = _backend_mode(settings)
                log = logging.getLogger("ea.task_contracts")
                if backend == "memory":
                    ensure_storage_fallback_allowed(settings, "task contracts configured for memory")
                    return InMemoryTaskContractRepository()
                if backend == "postgres":
                    if not settings.database_url:
                        raise RuntimeError("EA_STORAGE_BACKEND=postgres requires DATABASE_URL")
                    return PostgresTaskContractRepository(settings.database_url)
                if settings.database_url:
                    try:
                        return PostgresTaskContractRepository(settings.database_url)
                    except Exception as exc:
                        ensure_storage_fallback_allowed(settings, "task contracts auto fallback", exc)
                        log.warning("postgres task-contract backend unavailable in auto mode; falling back to memory: %s", exc)
                ensure_storage_fallback_allowed(settings, "task contracts auto backend without DATABASE_URL")
                return InMemoryTaskContractRepository()


            def build_task_contract_service(settings: Settings | None = None) -> TaskContractService:
                resolved = settings or get_settings()
                return TaskContractService(build_task_contract_repo(resolved))
            """
        ),
    )


def patch_skills() -> None:
    write(
        "ea/app/services/skills.py",
        dedent(
            """\
            from __future__ import annotations

            from typing import Any

            from app.domain.models import (
                SkillContract,
                TaskContract,
                TaskContractRuntimePolicy,
                TaskContractSkillCatalogPolicy,
                parse_task_contract_runtime_policy,
            )
            from app.services.task_contracts import TaskContractService


            def _collect_string_values(value: object) -> tuple[str, ...]:
                if isinstance(value, str):
                    normalized = str(value or "").strip()
                    return (normalized,) if normalized else ()
                if isinstance(value, dict):
                    collected: list[str] = []
                    for nested in value.values():
                        collected.extend(_collect_string_values(nested))
                    return tuple(collected)
                if isinstance(value, (list, tuple, set)):
                    collected: list[str] = []
                    for nested in value:
                        collected.extend(_collect_string_values(nested))
                    return tuple(collected)
                return ()


            def _title_from_key(value: str) -> str:
                parts = [part for part in str(value or "").replace("-", "_").split("_") if part]
                if not parts:
                    return "Unnamed Skill"
                return " ".join(part.capitalize() for part in parts)


            class SkillCatalogService:
                def __init__(self, task_contracts: TaskContractService) -> None:
                    self._task_contracts = task_contracts

                def _skill_meta(self, contract: TaskContract) -> TaskContractSkillCatalogPolicy:
                    return contract.runtime_policy().skill_catalog

                def _workflow_template(self, contract: TaskContract) -> str:
                    return str(contract.runtime_policy().workflow_template or "rewrite").strip() or "rewrite"

                def _derive_input_schema(self, contract: TaskContract) -> dict[str, Any]:
                    policy = contract.runtime_policy()
                    workflow_template = self._workflow_template(contract)
                    pre_artifact_tool_name = str(policy.pre_artifact_tool_name or "").strip()
                    if workflow_template == "browseract_extract_then_artifact" or (
                        workflow_template == "tool_then_artifact"
                        and pre_artifact_tool_name in {"browseract.extract_account_facts", "browseract.extract_account_inventory"}
                    ):
                        required = ["binding_id", "service_name"]
                        if pre_artifact_tool_name == "browseract.extract_account_inventory":
                            required = ["binding_id"]
                        return {
                            "type": "object",
                            "properties": {
                                "binding_id": {"type": "string"},
                                "service_name": {"type": "string"},
                                "service_names": {"type": "array", "items": {"type": "string"}},
                                "requested_fields": {"type": "array", "items": {"type": "string"}},
                                "run_url": {"type": "string"},
                                "instructions": {"type": "string"},
                                "account_hints_json": {"type": "object"},
                            },
                            "required": required,
                        }
                    return {
                        "type": "object",
                        "properties": {
                            "source_text": {"type": "string"},
                        },
                        "required": ["source_text"],
                    }

                def _derive_output_schema(self, contract: TaskContract) -> dict[str, Any]:
                    return {
                        "type": "object",
                        "properties": {
                            "deliverable_type": {"const": contract.deliverable_type},
                            "artifact_kind": {"type": "string"},
                        },
                        "required": ["deliverable_type"],
                    }

                def _derive_memory_writes(self, contract: TaskContract) -> tuple[str, ...]:
                    if str(contract.memory_write_policy or "none").strip() == "none":
                        return ()
                    category = str(contract.runtime_policy().memory_candidate.category or "").strip()
                    if category:
                        return (category,)
                    return (contract.memory_write_policy,)

                def _derive_human_policy(self, contract: TaskContract) -> dict[str, Any]:
                    human_review = contract.runtime_policy().human_review
                    if not str(human_review.role or "").strip():
                        return {}
                    return {
                        "role_required": str(human_review.role or "").strip(),
                        "task_type": str(human_review.task_type or "").strip(),
                        "priority": str(human_review.priority or "").strip(),
                        "sla_minutes": int(human_review.sla_minutes),
                        "authority_required": str(human_review.authority_required or "").strip(),
                    }

                def contract_to_skill(self, contract: TaskContract) -> SkillContract:
                    meta = self._skill_meta(contract)
                    workflow_template = self._workflow_template(contract)
                    skill_key = str(meta.skill_key or contract.task_key).strip() or contract.task_key
                    input_schema_json = dict(meta.input_schema_json or {}) or self._derive_input_schema(contract)
                    output_schema_json = dict(meta.output_schema_json or {}) or self._derive_output_schema(contract)
                    authority_profile_json = dict(meta.authority_profile_json or {}) or {
                        "default_approval_class": contract.default_approval_class,
                        "workflow_template": workflow_template,
                    }
                    provider_hints_json = dict(meta.provider_hints_json or {})
                    tool_policy_json = dict(meta.tool_policy_json or {}) or {
                        "allowed_tools": list(contract.allowed_tools),
                    }
                    human_policy_json = dict(meta.human_policy_json or {}) or self._derive_human_policy(contract)
                    return SkillContract(
                        skill_key=skill_key,
                        task_key=contract.task_key,
                        name=str(meta.name or _title_from_key(skill_key)).strip() or _title_from_key(skill_key),
                        description=str(meta.description or f"Skill wrapper for task contract `{contract.task_key}`.").strip(),
                        deliverable_type=contract.deliverable_type,
                        default_risk_class=contract.default_risk_class,
                        default_approval_class=contract.default_approval_class,
                        workflow_template=workflow_template,
                        allowed_tools=tuple(contract.allowed_tools or ()),
                        evidence_requirements=tuple(contract.evidence_requirements or ()),
                        memory_write_policy=contract.memory_write_policy,
                        memory_reads=tuple(meta.memory_reads or ()) or tuple(contract.evidence_requirements or ()),
                        memory_writes=tuple(meta.memory_writes or ()) or self._derive_memory_writes(contract),
                        tags=tuple(meta.tags or ()) or (workflow_template, contract.deliverable_type),
                        input_schema_json=input_schema_json,
                        output_schema_json=output_schema_json,
                        authority_profile_json=authority_profile_json,
                        model_policy_json=dict(meta.model_policy_json or {}),
                        provider_hints_json=provider_hints_json,
                        tool_policy_json=tool_policy_json,
                        human_policy_json=human_policy_json,
                        evaluation_cases_json=tuple(dict(value) for value in meta.evaluation_cases_json),
                        updated_at=contract.updated_at,
                    )

                def upsert_skill(
                    self,
                    *,
                    skill_key: str,
                    task_key: str = "",
                    name: str,
                    description: str = "",
                    deliverable_type: str,
                    default_risk_class: str = "low",
                    default_approval_class: str = "none",
                    workflow_template: str = "rewrite",
                    allowed_tools: tuple[str, ...] = (),
                    evidence_requirements: tuple[str, ...] = (),
                    memory_write_policy: str = "reviewed_only",
                    memory_reads: tuple[str, ...] = (),
                    memory_writes: tuple[str, ...] = (),
                    tags: tuple[str, ...] = (),
                    input_schema_json: dict[str, Any] | None = None,
                    output_schema_json: dict[str, Any] | None = None,
                    authority_profile_json: dict[str, Any] | None = None,
                    model_policy_json: dict[str, Any] | None = None,
                    provider_hints_json: dict[str, Any] | None = None,
                    tool_policy_json: dict[str, Any] | None = None,
                    human_policy_json: dict[str, Any] | None = None,
                    evaluation_cases_json: tuple[dict[str, Any], ...] = (),
                    budget_policy_json: dict[str, Any] | None = None,
                ) -> SkillContract:
                    resolved_task_key = str(task_key or skill_key).strip() or str(skill_key or "").strip()
                    base_policy = parse_task_contract_runtime_policy(dict(budget_policy_json or {}))
                    runtime_policy = TaskContractRuntimePolicy(
                        budget_class=base_policy.budget_class,
                        workflow_template=str(workflow_template or "rewrite").strip() or "rewrite",
                        pre_artifact_tool_name=base_policy.pre_artifact_tool_name,
                        browseract_timeout_budget_seconds=base_policy.browseract_timeout_budget_seconds,
                        post_artifact_packs=base_policy.post_artifact_packs,
                        artifact_retry=base_policy.artifact_retry,
                        dispatch_retry=base_policy.dispatch_retry,
                        browseract_retry=base_policy.browseract_retry,
                        human_review=base_policy.human_review,
                        memory_candidate=base_policy.memory_candidate,
                        artifact_output=base_policy.artifact_output,
                        skill_catalog=TaskContractSkillCatalogPolicy(
                            skill_key=str(skill_key or resolved_task_key).strip() or resolved_task_key,
                            name=str(name or "").strip(),
                            description=str(description or "").strip(),
                            memory_reads=tuple(memory_reads),
                            memory_writes=tuple(memory_writes),
                            tags=tuple(tags),
                            input_schema_json=dict(input_schema_json or {}),
                            output_schema_json=dict(output_schema_json or {}),
                            authority_profile_json=dict(authority_profile_json or {}),
                            model_policy_json=dict(model_policy_json or {}),
                            provider_hints_json=dict(provider_hints_json or {}),
                            tool_policy_json=dict(tool_policy_json or {}),
                            human_policy_json=dict(human_policy_json or {}),
                            evaluation_cases_json=tuple(dict(value) for value in evaluation_cases_json),
                        ),
                    )
                    contract = self._task_contracts.upsert_contract(
                        task_key=resolved_task_key,
                        deliverable_type=deliverable_type,
                        default_risk_class=default_risk_class,
                        default_approval_class=default_approval_class,
                        allowed_tools=allowed_tools,
                        evidence_requirements=evidence_requirements,
                        memory_write_policy=memory_write_policy,
                        budget_policy_json=budget_policy_json,
                        runtime_policy=runtime_policy,
                    )
                    return self.contract_to_skill(contract)

                def get_skill(self, skill_key: str) -> SkillContract | None:
                    resolved = str(skill_key or "").strip()
                    if not resolved:
                        return None
                    direct = self._task_contracts.get_contract(resolved)
                    if direct is not None:
                        return self.contract_to_skill(direct)
                    for contract in self._task_contracts.list_contracts(limit=500):
                        if self.contract_to_skill(contract).skill_key == resolved:
                            return self.contract_to_skill(contract)
                    return None

                def list_skills(self, limit: int = 100, provider_hint: str = ""):
                    normalized_provider_hint = str(provider_hint or "").strip().lower()
                    fetch_limit = 500 if normalized_provider_hint else limit
                    rows = [self.contract_to_skill(contract) for contract in self._task_contracts.list_contracts(limit=fetch_limit)]
                    if normalized_provider_hint:
                        rows = [
                            row
                            for row in rows
                            if any(
                                normalized_provider_hint in candidate.lower()
                                for candidate in _collect_string_values(row.provider_hints_json)
                            )
                        ]
                    return rows[:limit]
            """
        ),
    )


def patch_planner() -> None:
    target = EA_ROOT / "ea/app/services/planner.py"
    text = target.read_text(encoding="utf-8")
    marker = "\n    def _build_artifact_then_memory_candidate_steps("
    start = text.find(marker)
    replacement_prefix = "\n"
    if start < 0:
        marker = "\n        def _build_artifact_then_memory_candidate_steps("
        start = text.find(marker)
        replacement_prefix = "\n"
    if start < 0:
        raise RuntimeError("planner function marker missing")
    next_marker = "\n    def _build_artifact_then_dispatch_then_memory_candidate_steps("
    end = text.find(next_marker, start)
    if end < 0:
        raise RuntimeError("planner function end marker missing")
    new = (
        "    def _build_artifact_then_memory_candidate_steps(\n"
        "        self,\n"
        "        intent: IntentSpecV3,\n"
        "        *,\n"
        "        contract: TaskContract,\n"
        "        pack_keys: tuple[str, ...] | None = None,\n"
        "    ) -> tuple[PlanStepSpec, ...]:\n"
        "        prepare_output_keys, prepare_desired_output_json = self._prepare_step_artifact_envelope(contract)\n"
        "        prepare_step = self._build_prepare_step(\n"
        "            output_keys=prepare_output_keys,\n"
        "            desired_output_json=prepare_desired_output_json,\n"
        "        )\n"
        "        policy_step = self._build_policy_step(\n"
        "            depends_on=(\"step_input_prepare\",),\n"
        "            additional_passthrough_keys=self._artifact_envelope_input_keys(contract),\n"
        "        )\n"
        "        artifact_step = self._build_artifact_save_step(\n"
        "            intent,\n"
        "            contract=contract,\n"
        "            depends_on=(\"step_policy_evaluate\",),\n"
        "            approval_required=False,\n"
        "            additional_input_keys=self._artifact_envelope_input_keys(contract),\n"
        "        )\n"
        "        packs = pack_keys or self._resolve_post_artifact_packs(contract, fallback=(\"memory_candidate\",))\n"
        "        steps: list[PlanStepSpec] = [prepare_step, policy_step, artifact_step]\n"
        "        memory_depends_on = [\"step_artifact_save\", \"step_policy_evaluate\"]\n"
        "        additional_input_keys: tuple[str, ...] = self._artifact_evidence_output_keys(contract)\n"
        "        if \"dispatch\" in packs:\n"
        "            steps.append(self._build_dispatch_step(contract=contract, depends_on=(\"step_policy_evaluate\",)))\n"
        "            memory_depends_on.append(\"step_connector_dispatch\")\n"
        "            additional_input_keys = (\n"
        "                \"delivery_id\",\n"
        "                \"status\",\n"
        "                \"binding_id\",\n"
        "                \"channel\",\n"
        "                \"recipient\",\n"
        "                *self._artifact_evidence_output_keys(contract),\n"
        "            )\n"
        "        steps.append(\n"
        "            self._build_memory_candidate_step(\n"
        "                intent,\n"
        "                contract=contract,\n"
        "                depends_on=tuple(memory_depends_on),\n"
        "                additional_input_keys=additional_input_keys,\n"
        "            )\n"
        "        )\n"
        "        return tuple(steps)\n"
    )
    target.write_text(text[:start] + replacement_prefix + new + text[end:], encoding="utf-8")


def patch_ltd_inventory_api() -> None:
    write(
        "ea/app/services/ltd_inventory_api.py",
        dedent(
            """\
            from __future__ import annotations

            from typing import Any


            def build_inventory_execute_payload(
                *,
                binding_id: str,
                service_names: tuple[str, ...],
                requested_fields: tuple[str, ...],
                skill_key: str = "ltd_inventory_refresh",
                goal: str = "refresh LTD inventory facts",
                instructions: str = "",
                run_url: str = "",
            ) -> dict[str, object]:
                if not str(binding_id or "").strip():
                    raise ValueError("binding_id_required")
                normalized_services = tuple(str(value or "").strip() for value in service_names if str(value or "").strip())
                if not normalized_services:
                    raise ValueError("service_names_required")
                normalized_fields = tuple(str(value or "").strip() for value in requested_fields if str(value or "").strip())
                if not normalized_fields:
                    normalized_fields = ("tier", "account_email", "status")
                payload: dict[str, object] = {
                    "skill_key": str(skill_key or "").strip() or "ltd_inventory_refresh",
                    "goal": str(goal or "").strip() or "refresh LTD inventory facts",
                    "input_json": {
                        "binding_id": str(binding_id or "").strip(),
                        "service_names": list(normalized_services),
                        "requested_fields": list(normalized_fields),
                    },
                }
                normalized_instructions = str(instructions or "").strip()
                if normalized_instructions:
                    payload["input_json"]["instructions"] = normalized_instructions
                normalized_run_url = str(run_url or "").strip()
                if normalized_run_url:
                    payload["input_json"]["run_url"] = normalized_run_url
                return payload


            def _extract_inventory_payload(value: Any) -> dict[str, Any] | None:
                if not isinstance(value, dict):
                    return None
                direct = value.get("services_json")
                if isinstance(direct, list):
                    return dict(value)
                structured = value.get("structured_output_json")
                if isinstance(structured, dict):
                    nested = structured.get("services_json")
                    if isinstance(nested, list):
                        return dict(structured)
                for key in ("output_json", "result_json", "result", "payload_json", "artifact_json"):
                    nested = _extract_inventory_payload(value.get(key))
                    if nested is not None:
                        return nested
                return None


            def extract_inventory_output_json(execute_response_json: dict[str, Any]) -> dict[str, Any]:
                extracted = _extract_inventory_payload(execute_response_json)
                if extracted is not None:
                    return extracted
                status = str(execute_response_json.get("status") or "").strip()
                next_action = str(execute_response_json.get("next_action") or "").strip()
                if status and next_action:
                    raise ValueError(f"inventory_refresh_not_immediate:{status}")
                raise ValueError("inventory_payload_not_found")
            """
        ),
    )


def patch_ltd_inventory_markdown() -> None:
    write(
        "ea/app/services/ltd_inventory_markdown.py",
        dedent(
            """\
            from __future__ import annotations

            from typing import Any


            DISCOVERY_TRACKING_HEADING = "## Discovery Tracking"


            def _normalize_service_name(value: object) -> str:
                return str(value or "").strip().strip("`")


            def _inventory_services_json(inventory_output_json: dict[str, Any]) -> list[dict[str, Any]]:
                direct = inventory_output_json.get("services_json")
                if isinstance(direct, list):
                    return [dict(row) for row in direct if isinstance(row, dict)]
                structured = inventory_output_json.get("structured_output_json")
                if isinstance(structured, dict):
                    nested = structured.get("services_json")
                    if isinstance(nested, list):
                        return [dict(row) for row in nested if isinstance(row, dict)]
                return []


            def _notes_for_service_row(row: dict[str, Any]) -> str:
                notes: list[str] = []
                plan_tier = str(row.get("plan_tier") or "").strip()
                if plan_tier:
                    notes.append(f"Plan/Tier: {plan_tier}")
                facts_json = dict(row.get("facts_json") or {})
                status = str(facts_json.get("status") or row.get("status") or "").strip()
                if status:
                    notes.append(f"Status: {status}")
                missing_fields = [
                    str(value or "").strip()
                    for value in (row.get("missing_fields") or [])
                    if str(value or "").strip()
                ]
                if missing_fields:
                    notes.append(f"Missing fields: {', '.join(missing_fields)}")
                live_discovery_error = str(row.get("live_discovery_error") or "").strip()
                if live_discovery_error:
                    notes.append(f"Live discovery error: {live_discovery_error}")
                if not notes:
                    notes.append("BrowserAct inventory refresh updated this row.")
                return "; ".join(notes)


            def build_discovery_updates(inventory_output_json: dict[str, Any]) -> dict[str, list[str]]:
                updates: dict[str, list[str]] = {}
                for row in _inventory_services_json(inventory_output_json):
                    service_name = _normalize_service_name(row.get("service_name"))
                    if not service_name:
                        continue
                    updates[service_name.lower()] = [
                        f"`{service_name}`",
                        str(row.get("account_email") or "").strip(),
                        f"`{str(row.get('discovery_status') or '').strip()}`" if str(row.get("discovery_status") or "").strip() else "",
                        f"`{str(row.get('verification_source') or '').strip()}`" if str(row.get("verification_source") or "").strip() else "",
                        str(row.get("last_verified_at") or "").strip(),
                        _notes_for_service_row(row),
                    ]
                return updates


            def _parse_table_row(line: str) -> list[str] | None:
                stripped = line.strip()
                if not stripped.startswith("|") or not stripped.endswith("|"):
                    return None
                parts = [part.strip() for part in stripped.strip("|").split("|")]
                if len(parts) < 6:
                    return None
                return parts[:6]


            def _format_row(parts: list[str]) -> str:
                return "| " + " | ".join(parts[:6]) + " |"


            def update_discovery_tracking_table(markdown_text: str, inventory_output_json: dict[str, Any]) -> str:
                lines = markdown_text.splitlines()
                try:
                    heading_index = next(
                        index
                        for index, value in enumerate(lines)
                        if value.strip() == DISCOVERY_TRACKING_HEADING
                    )
                except StopIteration as exc:
                    raise ValueError("discovery_tracking_heading_not_found") from exc

                try:
                    table_start = next(
                        index
                        for index in range(heading_index + 1, len(lines))
                        if lines[index].strip().startswith("|")
                    )
                except StopIteration as exc:
                    raise ValueError("discovery_tracking_table_not_found") from exc

                table_end = table_start
                while table_end < len(lines) and lines[table_end].strip().startswith("|"):
                    table_end += 1

                if table_end - table_start < 2:
                    raise ValueError("discovery_tracking_table_invalid")

                header_line = lines[table_start]
                separator_line = lines[table_start + 1]
                updates = build_discovery_updates(inventory_output_json)
                existing_service_keys: set[str] = set()
                rebuilt_rows: list[str] = []
                for line in lines[table_start + 2 : table_end]:
                    parts = _parse_table_row(line)
                    if parts is None:
                        rebuilt_rows.append(line)
                        continue
                    service_name = _normalize_service_name(parts[0])
                    if service_name:
                        existing_service_keys.add(service_name.lower())
                    update = updates.get(service_name.lower())
                    if update is None:
                        rebuilt_rows.append(line)
                        continue
                    rebuilt_rows.append(_format_row(update))

                for row in _inventory_services_json(inventory_output_json):
                    service_name = _normalize_service_name(row.get("service_name"))
                    if not service_name or service_name.lower() in existing_service_keys:
                        continue
                    update = updates.get(service_name.lower())
                    if update is not None:
                        rebuilt_rows.append(_format_row(update))

                updated_lines = (
                    lines[:table_start]
                    + [header_line, separator_line]
                    + rebuilt_rows
                    + lines[table_end:]
                )
                return "\\n".join(updated_lines) + ("\\n" if markdown_text.endswith("\\n") else "")
            """
        ),
    )


def patch_provider_registry() -> None:
    write(
        "ea/app/services/provider_registry.py",
        dedent(
            """\
            from __future__ import annotations

            from dataclasses import dataclass

            from app.domain.models import SkillContract


            def _collect_strings(value: object) -> tuple[str, ...]:
                if isinstance(value, str):
                    normalized = str(value or "").strip()
                    return (normalized,) if normalized else ()
                if isinstance(value, dict):
                    collected: list[str] = []
                    for nested in value.values():
                        collected.extend(_collect_strings(nested))
                    return tuple(collected)
                if isinstance(value, (list, tuple, set)):
                    collected: list[str] = []
                    for nested in value:
                        collected.extend(_collect_strings(nested))
                    return tuple(collected)
                return ()


            @dataclass(frozen=True)
            class ProviderCapability:
                provider_key: str
                capability_key: str
                tool_name: str
                executable: bool = True


            @dataclass(frozen=True)
            class ProviderBinding:
                provider_key: str
                display_name: str
                executable: bool
                capabilities: tuple[ProviderCapability, ...]
                source: str = "runtime"


            class ProviderRegistryService:
                def __init__(self) -> None:
                    self._bindings = (
                        ProviderBinding(
                            provider_key="artifact_repository",
                            display_name="Artifact Repository",
                            executable=True,
                            capabilities=(
                                ProviderCapability(
                                    provider_key="artifact_repository",
                                    capability_key="artifact_save",
                                    tool_name="artifact_repository",
                                ),
                            ),
                        ),
                        ProviderBinding(
                            provider_key="browseract",
                            display_name="BrowserAct",
                            executable=True,
                            capabilities=(
                                ProviderCapability(
                                    provider_key="browseract",
                                    capability_key="account_facts",
                                    tool_name="browseract.extract_account_facts",
                                ),
                                ProviderCapability(
                                    provider_key="browseract",
                                    capability_key="account_inventory",
                                    tool_name="browseract.extract_account_inventory",
                                ),
                            ),
                        ),
                        ProviderBinding(
                            provider_key="connector_dispatch",
                            display_name="Connector Dispatch",
                            executable=True,
                            capabilities=(
                                ProviderCapability(
                                    provider_key="connector_dispatch",
                                    capability_key="dispatch",
                                    tool_name="connector.dispatch",
                                ),
                            ),
                        ),
                    )

                def list_bindings(self) -> tuple[ProviderBinding, ...]:
                    return self._bindings

                def bindings_for_skill(self, skill: SkillContract) -> tuple[ProviderBinding, ...]:
                    hints = {value.strip().lower() for value in _collect_strings(skill.provider_hints_json) if value.strip()}
                    allowed_tools = {str(value or "").strip() for value in skill.allowed_tools if str(value or "").strip()}
                    matched: list[ProviderBinding] = []
                    for binding in self._bindings:
                        capability_tools = {cap.tool_name for cap in binding.capabilities}
                        if binding.provider_key in hints or capability_tools.intersection(allowed_tools):
                            matched.append(binding)
                    return tuple(matched)
            """
        ),
    )


def patch_architecture_map() -> None:
    write(
        "ARCHITECTURE_MAP.md",
        dedent(
            """\
            # Architecture Map

            ## Runtime Entry Points

            - API app factory: `ea/app/api/app.py`
            - ASGI app export: `ea/app/main.py`
            - Process runner / role switch: `ea/app/runner.py`

            ## Runtime Profile

            - Settings shape: `ea/app/settings.py`
            - Startup validation + runtime profile resolution: `ea/app/settings.py`
            - Container composition + single-profile bootstrap: `ea/app/container.py`

            ## API Surface

            - Health: `GET /health`
            - Channels: `/v1/channels/*`
            - Connectors: `/v1/connectors/*`
            - Delivery: `/v1/delivery/*`
            - Evidence: `/v1/evidence/*`
            - Human tasks: `/v1/human/*`
            - Memory: `/v1/memory/*`
            - Observations: `/v1/observations/*`
            - Plans: `/v1/plans/*`
            - Policy: `/v1/policy/*`
            - Rewrite: `/v1/rewrite/*`
            - Skills: `/v1/skills/*`
            - Task contracts: `/v1/task-contracts/*`
            - Tools: `/v1/tools/*`
            - Route roots: `ea/app/api/routes/`

            ## Core Domain Models

            - Intent + execution: `IntentSpecV3`, `ExecutionSession`, `ExecutionEvent`
            - Policy: `PolicyDecision`, `PolicyDecisionRecord`
            - Memory: `MemoryCandidate`, `MemoryItem`
            - Semantic context: `Entity`, `RelationshipEdge`
            - Commitment context: `Commitment`
            - Governance context: `AuthorityBinding`
            - Delivery context: `DeliveryPreference`
            - Follow-up context: `FollowUp`
            - Deadline context: `DeadlineWindow`
            - Stakeholder context: `Stakeholder`
            - Decision context: `DecisionWindow`
            - Communication context: `CommunicationPolicy`
            - Follow-up rule context: `FollowUpRule`
            - Interruption budget context: `InterruptionBudget`
            - Channel runtime: `ObservationEvent`, `DeliveryOutboxItem`
            - File: `ea/app/domain/models.py`

            ## Services

            - Orchestration kernel: `ea/app/services/orchestrator.py`
            - Planner: `ea/app/services/planner.py`
            - Policy engine: `ea/app/services/policy.py`
            - Task contract storage + serialization: `ea/app/services/task_contracts.py`
            - Skill catalog: `ea/app/services/skills.py`
            - Provider registry: `ea/app/services/provider_registry.py`
            - Tool execution: `ea/app/services/tool_execution.py`
            - Channel runtime: `ea/app/services/channel_runtime.py`
            - Evidence runtime: `ea/app/services/evidence_runtime.py`
            - Memory runtime: `ea/app/services/memory_runtime.py`
            - LTD inventory helpers: `ea/app/services/ltd_inventory_api.py`, `ea/app/services/ltd_inventory_markdown.py`

            ## Repositories

            - Artifacts: in-memory + postgres
            - Task contracts: in-memory + postgres
            - Observation events: in-memory + postgres
            - Delivery outbox: in-memory + postgres
            - Memory candidates/items: in-memory + postgres
            - Entities/relationships/commitments: in-memory + postgres
            - Governance/delivery/follow-up windows: in-memory + postgres
            - Tool registry + connector bindings: in-memory + postgres
            - Repository roots: `ea/app/repositories/`

            ## Operator Tooling

            - Deploy: `scripts/deploy.sh`
            - DB bootstrap: `scripts/db_bootstrap.sh`
            - DB status: `scripts/db_status.sh`
            - DB retention: `scripts/db_retention.sh`
            - DB size: `scripts/db_size.sh`
            - API smoke: `scripts/smoke_api.sh`
            - Postgres smoke: `scripts/smoke_postgres.sh`
            - LTD refresh: `scripts/refresh_ltds_via_api.py`, `scripts/refresh_ltds_from_inventory.py`
            - Support bundle: `scripts/support_bundle.sh`
            - CI workflow: `.github/workflows/smoke-runtime.yml`
            """
        ),
    )


def patch_dockerfiles() -> None:
    dockerfile = dedent(
        """\
        FROM python:3.12-slim

        ENV PYTHONDONTWRITEBYTECODE=1 \\
            PYTHONUNBUFFERED=1

        RUN apt-get update && apt-get install -y --no-install-recommends \\
            ca-certificates curl && \\
            rm -rf /var/lib/apt/lists/* && \\
            adduser --system --uid 10001 --group ea

        WORKDIR /app
        COPY ea/requirements.txt .
        RUN pip install --no-cache-dir -r requirements.txt
        COPY ea/app ./app
        RUN chown -R ea:ea /app

        USER ea
        HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \\
          CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health', timeout=3)" >/dev/null || exit 1

        CMD ["python", "-m", "app.runner"]
        """
    )
    write("Dockerfile", dockerfile)
    write("ea/Dockerfile", dockerfile)


def patch_tests() -> None:
    write(
        "tests/test_runtime_profile.py",
        dedent(
            """\
            from __future__ import annotations

            import os

            import pytest

            from app.api.dependencies import RequestContext, resolve_principal_id
            from app.domain.models import TaskContract, now_utc_iso
            from app.repositories.task_contracts import InMemoryTaskContractRepository
            from app.services.provider_registry import ProviderRegistryService
            from app.services.skills import SkillCatalogService
            from app.settings import (
                get_settings,
                resolve_runtime_profile,
                validate_startup_settings,
            )
            from app.services.task_contracts import TaskContractService


            def _clear_env() -> None:
                for key in (
                    "EA_RUNTIME_MODE",
                    "EA_STORAGE_BACKEND",
                    "EA_LEDGER_BACKEND",
                    "DATABASE_URL",
                    "EA_API_TOKEN",
                    "EA_DEFAULT_PRINCIPAL_ID",
                ):
                    os.environ.pop(key, None)


            def test_runtime_profile_auto_without_database_prefers_memory() -> None:
                _clear_env()
                settings = get_settings()
                profile = resolve_runtime_profile(settings)
                assert profile.storage_backend == "memory"
                assert profile.durability == "ephemeral"


            def test_runtime_profile_auto_with_database_prefers_postgres() -> None:
                _clear_env()
                os.environ["DATABASE_URL"] = "postgresql://example.invalid/ea"
                settings = get_settings()
                profile = resolve_runtime_profile(settings)
                assert profile.storage_backend == "postgres"
                assert profile.durability == "durable"


            def test_prod_requires_database_url() -> None:
                _clear_env()
                os.environ["EA_RUNTIME_MODE"] = "prod"
                os.environ["EA_API_TOKEN"] = "secret-token"
                with pytest.raises(RuntimeError, match="DATABASE_URL"):
                    validate_startup_settings(get_settings())


            def test_resolve_principal_id_rejects_foreign_requested_principal() -> None:
                context = RequestContext(principal_id="exec-1", authenticated=False)
                with pytest.raises(Exception):
                    resolve_principal_id("exec-2", context)


            def test_provider_registry_exposes_executable_browseract_binding() -> None:
                registry = ProviderRegistryService()
                contract = TaskContract(
                    task_key="inventory",
                    deliverable_type="inventory",
                    default_risk_class="low",
                    default_approval_class="none",
                    allowed_tools=("browseract.extract_account_inventory",),
                    evidence_requirements=(),
                    memory_write_policy="none",
                    budget_policy_json={"class": "low"},
                    updated_at=now_utc_iso(),
                )
                bindings = registry.bindings_for_skill(
                    SkillCatalogService(TaskContractService(InMemoryTaskContractRepository())).contract_to_skill(contract)
                )
                assert any(binding.provider_key == "browseract" and binding.executable for binding in bindings)
            """
        ),
    )
    write(
        "tests/test_planner_edge_cases.py",
        dedent(
            """\
            from __future__ import annotations

            from app.repositories.task_contracts import InMemoryTaskContractRepository
            from app.services.planner import PlannerService
            from app.services.task_contracts import TaskContractService


            def test_artifact_then_memory_candidate_keeps_dispatch_pack_when_requested() -> None:
                contracts = TaskContractService(InMemoryTaskContractRepository())
                contracts.upsert_contract(
                    task_key="artifact_memory_dispatch",
                    deliverable_type="rewrite_note",
                    default_risk_class="low",
                    default_approval_class="none",
                    allowed_tools=("artifact_repository", "connector.dispatch"),
                    memory_write_policy="reviewed_only",
                    budget_policy_json={
                        "class": "low",
                        "workflow_template": "artifact_then_memory_candidate",
                        "post_artifact_packs": ["dispatch", "memory_candidate"],
                    },
                )
                planner = PlannerService(contracts)
                _, plan = planner.build_plan(
                    task_key="artifact_memory_dispatch",
                    principal_id="exec-1",
                    goal="exercise edge case",
                )
                step_keys = [step.step_key for step in plan.steps]
                assert step_keys == [
                    "step_input_prepare",
                    "step_policy_evaluate",
                    "step_artifact_save",
                    "step_connector_dispatch",
                    "step_memory_candidate_stage",
                ]
            """
        ),
    )
    write(
        "tests/test_provider_registry.py",
        dedent(
            """\
            from __future__ import annotations

            from app.domain.models import SkillContract
            from app.services.provider_registry import ProviderRegistryService


            def test_provider_registry_matches_allowed_tools_and_provider_hints() -> None:
                registry = ProviderRegistryService()
                skill = SkillContract(
                    skill_key="inventory_refresh",
                    task_key="inventory_refresh",
                    name="Inventory Refresh",
                    description="refresh inventory",
                    deliverable_type="inventory",
                    default_risk_class="low",
                    default_approval_class="none",
                    workflow_template="tool_then_artifact",
                    allowed_tools=("browseract.extract_account_inventory", "artifact_repository"),
                    evidence_requirements=(),
                    memory_write_policy="none",
                    memory_reads=(),
                    memory_writes=(),
                    tags=("inventory",),
                    input_schema_json={},
                    output_schema_json={},
                    authority_profile_json={},
                    model_policy_json={},
                    provider_hints_json={"preferred": ["browseract"]},
                    tool_policy_json={},
                    human_policy_json={},
                    evaluation_cases_json=(),
                    updated_at="2026-03-12T00:00:00Z",
                )
                bindings = registry.bindings_for_skill(skill)
                keys = {binding.provider_key for binding in bindings}
                assert "browseract" in keys
                assert "artifact_repository" in keys
            """
        ),
    )
    write(
        "tests/test_ltd_inventory_markdown.py",
        dedent(
            """\
            from __future__ import annotations

            import json
            import subprocess
            import sys
            from pathlib import Path

            from app.services.ltd_inventory_markdown import (
                build_discovery_updates,
                update_discovery_tracking_table,
            )


            ROOT = Path(__file__).resolve().parents[1]


            def test_update_discovery_tracking_table_updates_known_rows_and_appends_new_services() -> None:
                markdown = \"\"\"# LTDs

            ## Discovery Tracking

            | Service | Account / Email | Discovery Status | Verification Source | Last Verified | Notes |
            |---|---|---|---|---|---|
            | `BrowserAct` |  | `runtime_ready` | `browseract.extract_account_inventory` |  | waiting |
            | `Teable` |  | `missing` | `manual_inventory` |  | stale |
            | `Vizologi` |  | `missing` | `manual_inventory` |  | keep me |

            ## Attention Items
            \"\"\"
                inventory_output_json = {
                    "services_json": [
                        {
                            "service_name": "BrowserAct",
                            "account_email": "ops@example.com",
                            "discovery_status": "complete",
                            "verification_source": "browseract_live",
                            "last_verified_at": "2026-03-07T12:00:00Z",
                            "plan_tier": "Tier 3",
                            "facts_json": {"status": "activated"},
                            "missing_fields": [],
                        },
                        {
                            "service_name": "Teable",
                            "account_email": "ops@teable.example",
                            "discovery_status": "complete",
                            "verification_source": "connector_metadata",
                            "last_verified_at": "2026-03-07T12:01:00Z",
                            "plan_tier": "License Tier 4",
                            "facts_json": {"status": "activated"},
                            "missing_fields": [],
                        },
                        {
                            "service_name": "UnknownService",
                            "account_email": "",
                            "discovery_status": "missing",
                            "verification_source": "missing",
                            "last_verified_at": "2026-03-07T12:02:00Z",
                            "missing_fields": ["tier", "account_email"],
                        },
                    ]
                }

                updated = update_discovery_tracking_table(markdown, inventory_output_json)

                assert "| `BrowserAct` | ops@example.com | `complete` | `browseract_live` | 2026-03-07T12:00:00Z | Plan/Tier: Tier 3; Status: activated |" in updated
                assert "| `Teable` | ops@teable.example | `complete` | `connector_metadata` | 2026-03-07T12:01:00Z | Plan/Tier: License Tier 4; Status: activated |" in updated
                assert "| `Vizologi` |  | `missing` | `manual_inventory` |  | keep me |" in updated
                assert "| `UnknownService` |  | `missing` | `missing` | 2026-03-07T12:02:00Z | Missing fields: tier, account_email |" in updated


            def test_build_discovery_updates_accepts_artifact_envelope_shape() -> None:
                updates = build_discovery_updates(
                    {
                        "structured_output_json": {
                            "services_json": [
                                {
                                    "service_name": "BrowserAct",
                                    "account_email": "ops@example.com",
                                    "discovery_status": "complete",
                                    "verification_source": "connector_metadata",
                                    "last_verified_at": "2026-03-07T12:00:00Z",
                                    "plan_tier": "Tier 3",
                                    "facts_json": {"status": "activated"},
                                    "missing_fields": [],
                                    "live_discovery_error": "",
                                }
                            ]
                        }
                    }
                )

                assert updates["browseract"] == [
                    "`BrowserAct`",
                    "ops@example.com",
                    "`complete`",
                    "`connector_metadata`",
                    "2026-03-07T12:00:00Z",
                    "Plan/Tier: Tier 3; Status: activated",
                ]


            def test_refresh_ltds_script_can_write_updated_markdown(tmp_path: Path) -> None:
                markdown_path = tmp_path / "LTDs.md"
                markdown_path.write_text(
                    \"\"\"# LTDs

            ## Discovery Tracking

            | Service | Account / Email | Discovery Status | Verification Source | Last Verified | Notes |
            |---|---|---|---|---|---|
            | `BrowserAct` |  | `runtime_ready` | `browseract.extract_account_inventory` |  | waiting |

            ## Attention Items
            \"\"\",
                    encoding="utf-8",
                )
                inventory_path = tmp_path / "inventory.json"
                inventory_path.write_text(
                    json.dumps(
                        {
                            "services_json": [
                                {
                                    "service_name": "BrowserAct",
                                    "account_email": "ops@example.com",
                                    "discovery_status": "complete",
                                    "verification_source": "browseract_live",
                                    "last_verified_at": "2026-03-07T12:00:00Z",
                                    "plan_tier": "Tier 3",
                                    "facts_json": {"status": "activated"},
                                    "missing_fields": [],
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )

                completed = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts/refresh_ltds_from_inventory.py"),
                        "--input",
                        str(inventory_path),
                        "--markdown",
                        str(markdown_path),
                        "--write",
                    ],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                assert completed.returncode == 0, completed.stderr
                updated = markdown_path.read_text(encoding="utf-8")
                assert "ops@example.com" in updated
                assert "Plan/Tier: Tier 3; Status: activated" in updated
            """
        ),
    )
    append_if_missing(
        "tests/test_ltd_inventory_api.py",
        dedent(
            """\


            def test_extract_inventory_output_json_accepts_nested_output_json() -> None:
                payload = extract_inventory_output_json(
                    {
                        "status": "completed",
                        "next_action": "download_artifact",
                        "output_json": {
                            "services_json": [
                                {
                                    "service_name": "MarkupGo",
                                    "account_email": "ops@example.com",
                                }
                            ]
                        },
                    }
                )

                assert payload["services_json"][0]["service_name"] == "MarkupGo"
            """
        ),
    )


def main() -> None:
    patch_settings()
    patch_container()
    patch_dependencies()
    patch_app_factory()
    patch_task_contracts()
    patch_skills()
    patch_planner()
    patch_ltd_inventory_api()
    patch_ltd_inventory_markdown()
    patch_provider_registry()
    patch_architecture_map()
    patch_dockerfiles()
    patch_tests()


if __name__ == "__main__":
    main()
