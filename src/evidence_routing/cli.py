"""Command-line entry points for the evidence-routing Pilot."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
import yaml

from evidence_routing.privacy import scan_tracked_files

app = typer.Typer(no_args_is_help=True, add_completion=False)

_REQUIRED_PROJECTS = {"chemical", "pharmaceutical"}
_PHASE_GATED_COMMANDS = {
    "validate-data": 2,
    "run-paths": 4,
    "export-annotation": 5,
    "import-annotation": 5,
    "fit-router": 6,
    "evaluate": 7,
    "go-no-go": 7,
}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise typer.BadParameter(f"configuration file does not exist: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise typer.BadParameter("configuration root must be a mapping")
    return payload


@app.command("validate-config")
def validate_config(
    config: Path = typer.Option(..., exists=True, dir_okay=False, readable=True),
) -> None:
    """Validate the safe local configuration contract without resolving secrets."""
    payload = _load_yaml(config)
    if payload.get("schema_version") != "1.0":
        raise typer.BadParameter("schema_version must equal '1.0'")
    projects = payload.get("projects")
    if not isinstance(projects, dict):
        raise typer.BadParameter("projects must be a mapping")
    missing = sorted(_REQUIRED_PROJECTS - set(projects))
    if missing:
        raise typer.BadParameter(f"missing project entries: {', '.join(missing)}")
    for name in sorted(_REQUIRED_PROJECTS):
        project = projects[name]
        if not isinstance(project, dict) or not project.get("root_env"):
            raise typer.BadParameter(f"projects.{name}.root_env is required")
    typer.echo("configuration contract is valid")


@app.command("privacy-scan")
def privacy_scan(root: Path = typer.Option(Path("."), file_okay=False)) -> None:
    """Scan tracked files for restricted paths, data, and likely credentials."""
    findings = scan_tracked_files(root.resolve())
    for finding in findings:
        typer.echo(f"{finding.path}: {finding.rule}: {finding.message}", err=True)
    if findings:
        raise typer.Exit(code=1)
    typer.echo("privacy scan passed")


def _phase_gate(command: str) -> None:
    phase = _PHASE_GATED_COMMANDS[command]
    typer.echo(f"{command} becomes operational in implementation phase {phase}", err=True)
    raise typer.Exit(code=2)


def _make_phase_command(command: str):
    def phase_command() -> None:
        _phase_gate(command)

    return phase_command


for _command_name in _PHASE_GATED_COMMANDS:
    app.command(_command_name)(_make_phase_command(_command_name))


if __name__ == "__main__":
    app()
