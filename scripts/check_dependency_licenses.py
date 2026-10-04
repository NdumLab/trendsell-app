#!/usr/bin/env python3
"""Validate locked dependency licenses and maintain the auditable license report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
LOCK_PATHS = (
    Path("backend/requirements.lock"),
    Path("backend/requirements-dev.lock"),
    Path("frontend/package-lock.json"),
)
PERMISSIVE_LICENSES = {
    "0BSD",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "MIT",
    "PSF-2.0",
}
APPROVED_EXCEPTIONS = {"LGPL-3.0-only", "MPL-2.0"}
CLASSIFIER_LICENSES = {
    "OSI Approved :: BSD License": "BSD-3-Clause",
    "OSI Approved :: MIT License": "MIT",
}
NODE_LICENSE_OVERRIDES = {
    "@rolldown/binding-android-arm-eabi": "MIT",
    "@rolldown/binding-android-arm64": "MIT",
    "@rolldown/binding-darwin-arm64": "MIT",
    "@rolldown/binding-darwin-x64": "MIT",
    "@rolldown/binding-freebsd-x64": "MIT",
    "@rolldown/binding-linux-arm-gnueabihf": "MIT",
    "@rolldown/binding-linux-arm64-gnu": "MIT",
    "@rolldown/binding-linux-arm64-musl": "MIT",
    "@rolldown/binding-linux-ppc64-gnu": "MIT",
    "@rolldown/binding-linux-s390x-gnu": "MIT",
    "@rolldown/binding-openharmony-arm64": "MIT",
    "@rolldown/binding-win32-arm64-msvc": "MIT",
    "@rolldown/binding-win32-x64-msvc": "MIT",
    "fsevents": "MIT",
    "lightningcss-android-arm64": "MPL-2.0",
    "lightningcss-darwin-arm64": "MPL-2.0",
    "lightningcss-darwin-x64": "MPL-2.0",
    "lightningcss-freebsd-x64": "MPL-2.0",
    "lightningcss-linux-arm-gnueabihf": "MPL-2.0",
    "lightningcss-linux-arm64-gnu": "MPL-2.0",
    "lightningcss-linux-arm64-musl": "MPL-2.0",
    "lightningcss-win32-arm64-msvc": "MPL-2.0",
    "lightningcss-win32-x64-msvc": "MPL-2.0",
}


@dataclass(frozen=True, order=True)
class Dependency:
    ecosystem: str
    scope: str
    name: str
    version: str
    license_expression: str

    @property
    def disposition(self) -> str:
        identifiers = license_identifiers(self.license_expression)
        if "LGPL-3.0-only" in identifiers:
            return "Approved server exception"
        if "MPL-2.0" in identifiers:
            return "Approved build-only exception"
        return "Approved permissive"


def normalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def pinned_requirements(path: Path) -> dict[str, tuple[str, str]]:
    requirements: dict[str, tuple[str, str]] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.count("==") != 1:
            raise ValueError(f"{path}: dependency is not exactly pinned: {line}")
        name, version = line.split("==", 1)
        requirements[normalize_name(name)] = (name, version)
    return requirements


def python_license(distribution: metadata.Distribution) -> str:
    expression = (distribution.metadata.get("License-Expression") or "").strip()
    if expression:
        return expression
    legacy = (distribution.metadata.get("License") or "").strip()
    if legacy in PERMISSIVE_LICENSES | APPROVED_EXCEPTIONS:
        return legacy
    for classifier in distribution.metadata.get_all("Classifier") or []:
        prefix = "License :: "
        if classifier.startswith(prefix):
            mapped = CLASSIFIER_LICENSES.get(classifier.removeprefix(prefix))
            if mapped:
                return mapped
    return ""


def python_dependencies() -> list[Dependency]:
    runtime = pinned_requirements(REPOSITORY / "backend/requirements.lock")
    development = pinned_requirements(REPOSITORY / "backend/requirements-dev.lock")
    dependencies: list[Dependency] = []
    for normalized, (locked_name, locked_version) in sorted(development.items()):
        try:
            distribution = metadata.distribution(locked_name)
        except metadata.PackageNotFoundError as error:
            raise ValueError(f"locked Python package is not installed: {locked_name}") from error
        if distribution.version != locked_version:
            raise ValueError(
                f"installed Python package does not match the lock: {locked_name} "
                f"{distribution.version} != {locked_version}"
            )
        dependencies.append(
            Dependency(
                "Python",
                "runtime" if normalized in runtime else "development",
                distribution.metadata["Name"],
                distribution.version,
                python_license(distribution),
            )
        )
    missing_from_development = sorted(set(runtime) - set(development))
    if missing_from_development:
        raise ValueError(
            "runtime Python dependencies are absent from the development lock: "
            + ", ".join(missing_from_development)
        )
    return dependencies


def node_package_name(lock_path: str, package: dict[str, object]) -> str:
    declared = package.get("name")
    if isinstance(declared, str) and declared:
        return declared
    return lock_path.rsplit("node_modules/", 1)[-1]


def node_license(name: str, lock_path: str, package: dict[str, object]) -> str:
    installed_manifest = REPOSITORY / "frontend" / lock_path / "package.json"
    if installed_manifest.is_file():
        manifest = json.loads(installed_manifest.read_text())
        expression = manifest.get("license")
        if isinstance(expression, str) and expression.strip():
            return expression.strip()
    expression = package.get("license")
    if isinstance(expression, str) and expression.strip():
        return expression.strip()
    return NODE_LICENSE_OVERRIDES.get(name, "")


def node_dependencies() -> list[Dependency]:
    lock = json.loads((REPOSITORY / "frontend/package-lock.json").read_text())
    if lock.get("lockfileVersion") != 3:
        raise ValueError("frontend/package-lock.json must use lockfileVersion 3")
    dependencies: list[Dependency] = []
    for lock_path, package in sorted(lock.get("packages", {}).items()):
        if not lock_path or "node_modules/" not in lock_path:
            continue
        if not isinstance(package, dict):
            raise ValueError(f"invalid package-lock entry: {lock_path}")
        name = node_package_name(lock_path, package)
        version = package.get("version")
        if not isinstance(version, str) or not version:
            raise ValueError(f"package-lock entry has no version: {lock_path}")
        installed_manifest = REPOSITORY / "frontend" / lock_path / "package.json"
        if installed_manifest.is_file():
            installed = json.loads(installed_manifest.read_text())
            if installed.get("version") != version:
                raise ValueError(
                    f"installed npm package does not match the lock: {name} "
                    f"{installed.get('version')} != {version}"
                )
        dependencies.append(
            Dependency(
                "npm",
                "development" if package.get("dev") is True else "runtime",
                name,
                version,
                node_license(name, lock_path, package),
            )
        )
    return dependencies


def license_identifiers(expression: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9.-]*", expression)
        if token not in {"AND", "OR", "WITH"}
    }


def validate(dependencies: list[Dependency]) -> None:
    errors: list[str] = []
    approved = PERMISSIVE_LICENSES | APPROVED_EXCEPTIONS
    for dependency in dependencies:
        identifiers = license_identifiers(dependency.license_expression)
        if not dependency.license_expression or not identifiers:
            errors.append(f"{dependency.ecosystem} {dependency.name}@{dependency.version}: missing license")
            continue
        unknown = identifiers - approved
        if unknown:
            errors.append(
                f"{dependency.ecosystem} {dependency.name}@{dependency.version}: "
                f"unapproved license expression {dependency.license_expression}"
            )
        if "LGPL-3.0-only" in identifiers and not (
            dependency.ecosystem == "Python"
            and dependency.name in {"psycopg", "psycopg-binary"}
        ):
            errors.append(
                f"{dependency.ecosystem} {dependency.name}@{dependency.version}: "
                "LGPL exception is limited to the unmodified server database driver"
            )
        if "MPL-2.0" in identifiers and dependency.scope != "development":
            errors.append(
                f"{dependency.ecosystem} {dependency.name}@{dependency.version}: "
                "MPL exception is limited to build/test dependencies"
            )
    if errors:
        raise ValueError("dependency license policy failed:\n" + "\n".join(f"- {error}" for error in errors))


def lock_hashes() -> list[tuple[str, str]]:
    return [
        (str(path), hashlib.sha256((REPOSITORY / path).read_bytes()).hexdigest())
        for path in LOCK_PATHS
    ]


def render_report(dependencies: list[Dependency]) -> str:
    rows = sorted(dependencies)
    counts: dict[tuple[str, str], int] = {}
    for dependency in rows:
        key = (dependency.ecosystem, dependency.scope)
        counts[key] = counts.get(key, 0) + 1

    lines = [
        "# Dependency license disposition",
        "",
        "This inventory is generated from the exact Python and npm lockfiles by",
        "`scripts/check_dependency_licenses.py`. CI fails when an installed version differs from a",
        "lock, the report is stale, a license is missing, or a dependency falls outside the policy.",
        "It is an engineering compatibility decision for this release, not jurisdiction-specific",
        "legal advice.",
        "",
        "## Decision",
        "",
        f"**PASS — {len(rows)} direct and transitive packages have an approved disposition.**",
        "",
        "- Permissive licenses approved: 0BSD, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC,",
        "  MIT and PSF-2.0.",
        "- LGPL-3.0-only is approved only for the unmodified `psycopg` server driver packages.",
        "  They are separately installed from the lock, are not linked into the browser, and must",
        "  retain upstream notices plus users' replacement/modification rights.",
        "- MPL-2.0 is approved only for the `lightningcss` build tool and its optional platform",
        "  packages. Those packages are not shipped in the release artifact; their generated CSS is.",
        "- A new, missing, strong-copyleft, source-available or otherwise unapproved license blocks CI",
        "  until an accountable reviewer records a new disposition.",
        "- Copyright, license and NOTICE material supplied by dependencies must remain intact wherever",
        "  dependency code is redistributed. This inventory must ship with the release artifact.",
        "",
        "## Locked inputs",
        "",
        "| Lockfile | SHA-256 |",
        "| --- | --- |",
    ]
    lines.extend(f"| `{path}` | `{digest}` |" for path, digest in lock_hashes())
    lines.extend(["", "## Inventory summary", "", "| Ecosystem | Scope | Packages |", "| --- | --- | ---: |"])
    for key in sorted(counts):
        lines.append(f"| {key[0]} | {key[1]} | {counts[key]} |")
    lines.extend(
        [
            "",
            "## Exact inventory",
            "",
            "| Ecosystem | Scope | Package | Version | License | Disposition |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for dependency in rows:
        lines.append(
            f"| {dependency.ecosystem} | {dependency.scope} | `{dependency.name}` | "
            f"`{dependency.version}` | {dependency.license_expression} | "
            f"{dependency.disposition} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--write-report", type=Path)
    output.add_argument("--check-report", type=Path)
    arguments = parser.parse_args()
    try:
        dependencies = python_dependencies() + node_dependencies()
        validate(dependencies)
        report = render_report(dependencies)
        if arguments.write_report:
            arguments.write_report.write_text(report)
        elif arguments.check_report:
            if not arguments.check_report.is_file() or arguments.check_report.read_text() != report:
                raise ValueError(
                    f"license report is stale; regenerate with --write-report {arguments.check_report}"
                )
        print(f"Dependency license policy passed for {len(dependencies)} locked packages.")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
