import fnmatch
from typing import Any, Dict, List


def normalize_scope_path(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/").strip("/")


def scope_claim_conflicts(left_type: str, left_value: str, right_type: str, right_value: str) -> bool:
    lt = str(left_type or "").strip().lower()
    rt = str(right_type or "").strip().lower()
    lv = normalize_scope_path(left_value)
    rv = normalize_scope_path(right_value)
    if not (lt and rt and lv and rv):
        return False
    if lt == "build_root" or rt == "build_root":
        return lv == rv
    if lt == "surface" and rt == "surface":
        return lv == rv
    if lt == "path" and rt == "path":
        if any(token in lv for token in "*?[") or any(token in rv for token in "*?["):
            return fnmatch.fnmatch(lv, rv) or fnmatch.fnmatch(rv, lv)
        return lv == rv or lv.startswith(rv + "/") or rv.startswith(lv + "/")
    return False


def compile_package_scope_claims(package: Dict[str, Any]) -> List[Dict[str, str]]:
    package_id = str(package.get("package_id") or "").strip()
    project_id = str(package.get("project_id") or "").strip()
    claims: List[Dict[str, str]] = []
    allowed_paths = [normalize_scope_path(item) for item in package.get("allowed_paths") or [] if normalize_scope_path(item)]
    owned_surfaces = [str(item).strip() for item in package.get("owned_surfaces") or [] if str(item).strip()]
    horizon_surface = str(package.get("horizon_surface") or "").strip()
    for path in allowed_paths:
        namespaced_path = f"{project_id}/{path}" if project_id else path
        claims.append(
            {
                "package_id": package_id,
                "project_id": project_id,
                "claim_type": "path",
                "claim_value": namespaced_path,
                "scope_key": f"path:{namespaced_path}",
            }
        )
    for surface in owned_surfaces:
        claims.append(
            {
                "package_id": package_id,
                "project_id": project_id,
                "claim_type": "surface",
                "claim_value": surface,
                "scope_key": f"surface:{surface}",
            }
        )
    if horizon_surface:
        claims.append(
            {
                "package_id": package_id,
                "project_id": project_id,
                "claim_type": "surface",
                "claim_value": horizon_surface,
                "scope_key": f"surface:{horizon_surface}",
            }
        )
    if not claims:
        claims.append(
            {
                "package_id": package_id,
                "project_id": project_id,
                "claim_type": "build_root",
                "claim_value": project_id,
                "scope_key": f"build_root:{project_id}",
            }
        )
    return claims
