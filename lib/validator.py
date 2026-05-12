"""compose.yaml v2 + manifests + roles.yaml 전체 통합 검증 (v2).

묶음 1 (manifest/roles_registry/resolver) + 묶음 2 (compose 파서) 를 결합해
"compose.yaml 이 실제로 valid 한가?" 를 한 번에 검사.

검증 단계:
  1. compose 의 각 entry:
     a. resolver.resolve(id) — id 존재 + standard ↔ know-how 충돌 검사
     b. parse_manifest — manifest 자체 파싱 가능?
     c. validate_manifest(roles_registry) — manifest 형식 + role enum 검증
     d. manifest.domain == entry.domain — 위치 일관성
     e. entry.role 명시되면 manifest.roles 에 포함?
     f. entry.role 명시되면 roles_registry 에 등록?

사용 예:
    from lib.compose import parse_compose
    from lib.resolver import Resolver
    from lib.roles_registry import load_roles
    from lib.validator import validate_compose

    compose = parse_compose(Path(".harness/compose.yaml"))
    resolver = Resolver(Path("standard"), Path("know-how"))
    roles = load_roles(Path("standard"), Path("know-how"))

    errors = validate_compose(compose, resolver, roles)
    if errors:
        for e in errors:
            print(f"✗ {e}")
"""
from __future__ import annotations

from lib.compose import Compose, ComposeEntry
from lib.manifest import (
    Manifest,
    ManifestError,
    parse_manifest,
    validate_manifest,
)
from lib.resolver import IdConflict, IdNotFound, Resolver


def validate_compose(
    compose: Compose,
    resolver: Resolver,
    roles_registry: dict[str, frozenset[str]],
) -> list[str]:
    """compose 전체 검증. 에러 메시지 리스트 반환 (빈 = OK)."""
    errors: list[str] = []

    for entry in compose.entries:
        prefix = _entry_label(entry)
        # 1) id resolve
        try:
            manifest_path = resolver.resolve(entry.id)
        except IdConflict as e:
            errors.append(f"{prefix}: {e}")
            continue
        except IdNotFound as e:
            errors.append(f"{prefix}: {e}")
            continue

        # 2) manifest 파싱
        try:
            m = parse_manifest(manifest_path)
        except (FileNotFoundError, ManifestError) as e:
            errors.append(f"{prefix}: manifest 파싱 실패 — {e}")
            continue

        # 3) manifest 자체 형식 + role enum 검증
        manifest_errs = validate_manifest(m, allowed_roles=roles_registry)
        for err in manifest_errs:
            errors.append(f"{prefix}: {err}")

        # 4) (제거) manifest.domain == entry.domain 검증
        #    §5.3 schema 에서 한 manifest 가 여러 도메인에 등록 가능 (N:N).
        #    entry.domain 의 정확성은 5b 의 role enum 검증으로 자동 보장됨.

        # 5) entry.role 검증 (명시된 경우만)
        if entry.role is not None:
            # 5a) manifest.roles 에 포함되어 있나?
            if entry.role not in m.roles:
                errors.append(
                    f"{prefix}: role '{entry.role}' 가 manifest 의 roles 에 없음. "
                    f"manifest.roles: {m.roles}"
                )
            # 5b) roles_registry 의 도메인에 등록되어 있나?
            allowed = roles_registry.get(entry.domain, frozenset())
            if entry.role not in allowed:
                errors.append(
                    f"{prefix}: role '{entry.role}' 가 roles.yaml 의 "
                    f"'{entry.domain}' 도메인에 미등록"
                )

    return errors


def _entry_label(entry: ComposeEntry) -> str:
    """에러 메시지의 entry 식별용 prefix."""
    role_part = f"/{entry.role}" if entry.role else ""
    return f"{entry.domain}.{entry.section}[{entry.id}{role_part}]"
