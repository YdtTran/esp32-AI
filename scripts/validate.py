"""Dependency-free host foundation checks; no device or live-service validation."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
MODULES = {"firmware", "thingsboard", "models"}
SKIP = {".git", ".venv", "venv", "__pycache__", "build", "dist",
        "managed_components", "weights", "cache", "data", ".idea", ".vscode"}


def validate_registry(data: object, root: Path) -> None:
    """Validate repository interface metadata, not a wire schema."""
    if not isinstance(data, dict) or set(data) != {"format_version", "interfaces"}:
        raise ValueError("Registry requires format_version and interfaces")
    if type(data["format_version"]) is not int or data["format_version"] != 1:
        raise ValueError("Unsupported registry format_version")
    if not isinstance(data["interfaces"], list):
        raise ValueError("Registry interfaces must be a list")
    seen = set()
    root = root.resolve()
    for entry in data["interfaces"]:
        fields = {"id", "version", "specification", "producers", "consumers"}
        if not isinstance(entry, dict) or set(entry) != fields:
            raise ValueError("Interface requires id/version/specification/producers/consumers")
        if not isinstance(entry["id"], str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", entry["id"]):
            raise ValueError("Interface id must be kebab-case")
        if not isinstance(entry["version"], str) or not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", entry["version"]):
            raise ValueError("Interface version must be MAJOR.MINOR.PATCH")
        key = (entry["id"], entry["version"])
        if key in seen:
            raise ValueError(f"Duplicate interface version: {key}")
        seen.add(key)
        for side in ("producers", "consumers"):
            owners = entry[side]
            if (not isinstance(owners, list) or not owners
                    or any(not isinstance(owner, str) or owner not in MODULES for owner in owners)
                    or len(set(owners)) != len(owners)):
                raise ValueError(f"{side} must list unique known module owners")
        reference = entry["specification"]
        if not isinstance(reference, str) or not reference or "\\" in reference:
            raise ValueError("Specification must be a repository-relative POSIX path")
        relative = Path(reference)
        target = (root / relative).resolve()
        if relative.is_absolute() or not target.is_relative_to(root / "contracts"):
            raise ValueError("Specification must stay within contracts/")
        if not target.is_file():
            raise ValueError(f"Missing specification: {reference}")


def source_files():
    for directory, directories, files in os.walk(ROOT):
        directories[:] = [name for name in directories
                          if name not in SKIP and not name.startswith("build-")
                          and not name.endswith(".egg-info")]
        for name in sorted(files):
            # Real local env files and machine-specific settings are not source.
            if (name == ".env" or (name.startswith(".env.") and name != ".env.example")
                    or name.endswith(".local.toml") or name in {"settings.local.json", "CLAUDE.local.md"}):
                continue
            yield Path(directory) / name


def check_files() -> None:
    required = ["AGENTS.md", "CLAUDE.md", ".env.example", ".gitignore",
                "contracts/registry.json", "docs/architecture.md", "docs/development.md",
                "docs/decisions.md", "scripts/activate-idf.ps1",
                "firmware/CMakeLists.txt", "firmware/main/CMakeLists.txt",
                "firmware/main/app_main.c", "firmware/sdkconfig.defaults",
                "models/pyproject.toml", "models/src/iot_models/__init__.py",
                "infrastructure/compose.yaml", "infrastructure/Dockerfile",
                ".github/workflows/validate.yml", ".codex/config.toml"]
    required += [f"{module}/AGENTS.md" for module in MODULES | {"contracts", "tests", "infrastructure"}]
    for name in required:
        if not (ROOT / name).is_file() or not (ROOT / name).stat().st_size:
            raise ValueError(f"Missing or empty foundation file: {name}")
    for path in source_files():
        if path.suffix == ".json":
            json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix == ".toml":
            with path.open("rb") as stream:
                tomllib.load(stream)
        elif path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        elif path.suffix == ".md":
            for link in re.findall(r"\[[^\]]+\]\(([^\s)]+)\)", path.read_text(encoding="utf-8")):
                if ":" in link or link.startswith("#"):
                    continue
                target = path.parent / unquote(link.split("#", 1)[0])
                if not target.exists():
                    raise ValueError(f"Broken local link in {path.relative_to(ROOT)}: {link}")
    validate_registry(json.loads((ROOT / "contracts/registry.json").read_text(encoding="utf-8")), ROOT)


def check_agents() -> None:
    config_path = ROOT / ".codex/config.toml"
    with config_path.open("rb") as stream:
        config = tomllib.load(stream)
    if set(config) != {"agents"}:
        raise ValueError("Bootstrap Codex config should declare only role layers")
    for name, role in config["agents"].items():
        if set(role) != {"description", "config_file"}:
            raise ValueError(f"Unsupported bootstrap Codex role fields: {name}")
        role_path = (config_path.parent / role["config_file"]).resolve()
        if not role_path.is_relative_to(ROOT / ".codex/agents"):
            raise ValueError(f"Role layer outside .codex/agents: {name}")
        with role_path.open("rb") as stream:
            layer = tomllib.load(stream)
        if set(layer) != {"developer_instructions"} or not layer["developer_instructions"].strip():
            raise ValueError(f"Invalid bootstrap role layer: {name}")
    expected = {"firmware-engineer", "thingsboard-engineer", "ai-engineer", "integration-reviewer"}
    found = set()
    for path in (ROOT / ".claude/agents").glob("*.md"):
        parts = path.read_text(encoding="utf-8").split("---", 2)
        if len(parts) != 3 or parts[0].strip() or not parts[2].strip():
            raise ValueError(f"Invalid Claude agent frontmatter/body: {path.name}")
        # The intentionally small frontmatter uses simple scalar YAML only.
        values = dict(line.split(": ", 1) for line in parts[1].strip().splitlines())
        if set(values) != {"name", "description", "model"} or values["model"] != "inherit":
            raise ValueError(f"Unsupported bootstrap Claude agent fields: {path.name}")
        if values["name"] != path.stem or values["name"] in found:
            raise ValueError(f"Invalid or duplicate Claude agent name: {path.name}")
        found.add(values["name"])
    if found != expected:
        raise ValueError("Expected the four project Claude subagents")
    if "@AGENTS.md" not in (ROOT / "CLAUDE.md").read_text(encoding="utf-8"):
        raise ValueError("CLAUDE.md must import canonical guidance")


def main() -> int:
    try:
        check_files()
        check_agents()
        print("PASS: foundation files, syntax, local links, registry and role configuration", flush=True)
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join([str(ROOT / "models/src"), str(ROOT / "scripts")])
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        for suite in ("models/tests", "tests/integration"):
            subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", suite, "-v"],
                           cwd=ROOT, env=environment, check=True)
        print("PASS: host test suites. Firmware, live services and hardware are not checked.")
        return 0
    except (OSError, ValueError, SyntaxError, subprocess.CalledProcessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

