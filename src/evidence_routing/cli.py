"""Command-line entry points for the evidence-routing Pilot."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
import yaml
from pydantic import ValidationError

from evidence_routing.privacy import scan_tracked_files
from evidence_routing.schemas import (
    SCHEMA_MODELS,
    ExperimentManifest,
    PathRun,
    QuestionAnnotationBundle,
)
from evidence_routing.validation import (
    DatasetValidationError,
    validate_annotation_bundle,
    validate_manifest,
    validate_path_run,
)

app = typer.Typer(no_args_is_help=True, add_completion=False)

_REQUIRED_PROJECTS = {"chemical", "pharmaceutical"}
_PHASE_GATED_COMMANDS = {
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


@app.command("validate-data")
def validate_data(
    model_name: str = typer.Option(..., "--model"),
    input_path: Path = typer.Option(..., "--input", exists=True, dir_okay=False, readable=True),
) -> None:
    """Validate one JSON record against a public Pilot data contract."""
    model = SCHEMA_MODELS.get(model_name)
    if model is None:
        choices = ", ".join(sorted(SCHEMA_MODELS))
        raise typer.BadParameter(f"unknown model {model_name!r}; choose one of: {choices}")
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        record = model.model_validate(payload)
        if isinstance(record, PathRun):
            validate_path_run(record)
        elif isinstance(record, QuestionAnnotationBundle):
            validate_annotation_bundle(record)
        elif isinstance(record, ExperimentManifest):
            validate_manifest(record)
    except (json.JSONDecodeError, ValidationError, DatasetValidationError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"{model_name} is valid")


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
