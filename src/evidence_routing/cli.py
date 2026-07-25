"""Command-line entry points for the evidence-routing Pilot."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import typer
import yaml
from pydantic import ValidationError

from evidence_routing.adapters.chemical import ChemicalSafetyAdapter
from evidence_routing.adapters.pharma import PharmaceuticalRegulatoryAdapter
from evidence_routing.chemical_corpus import (
    export_scope_candidates,
    freeze_scope_review,
    generate_chemical_corpus_fingerprint,
    write_json_atomic,
)
from evidence_routing.privacy import scan_tracked_files
from evidence_routing.reranking import QwenFrozenReranker
from evidence_routing.runner import run_all_paths
from evidence_routing.schemas import (
    SCHEMA_MODELS,
    ExperimentManifest,
    PathRun,
    QueryRecord,
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


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise typer.BadParameter(f"required environment variable is unset: {name}")
    return value


def _chemical_session(config: Path):
    """Resolve a Neo4j session from env-var names without exposing credentials."""
    payload = _load_yaml(config)
    try:
        neo4j = payload["projects"]["chemical"]["neo4j"]
        uri = _required_environment(neo4j["uri_env"])
        user = _required_environment(neo4j["user_env"])
        credential_value = _required_environment(neo4j["password_env"])
        database_name = neo4j.get("database_env")
        database = os.environ.get(database_name, "").strip() if database_name else ""
    except (KeyError, TypeError) as error:
        raise typer.BadParameter("chemical Neo4j configuration is incomplete") from error
    try:
        from neo4j import GraphDatabase
    except ImportError as error:
        raise typer.BadParameter("install project dependencies to use Neo4j") from error
    driver = GraphDatabase.driver(uri, auth=(user, credential_value))
    session = driver.session(**({"database": database} if database else {}))
    return driver, session


def _project_root(payload: dict[str, Any], project_name: str) -> Path:
    try:
        variable = str(payload["projects"][project_name]["root_env"])
    except (KeyError, TypeError) as error:
        raise typer.BadParameter(f"projects.{project_name}.root_env is required") from error
    return Path(_required_environment(variable)).resolve()


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


@app.command("chemical-fingerprint")
def chemical_fingerprint(
    config: Path = typer.Option(..., exists=True, dir_okay=False, readable=True),
    source_revision: str = typer.Option(..., help="Human-readable frozen database revision."),
    output: Path = typer.Option(..., dir_okay=False),
) -> None:
    """Stream a strong fingerprint of the read-only chemical Neo4j corpus."""
    driver, session = _chemical_session(config)
    try:
        manifest = generate_chemical_corpus_fingerprint(
            session,
            source_revision=source_revision,
        )
        write_json_atomic(output, manifest.to_payload())
    except Exception as error:
        typer.echo(f"chemical fingerprint failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    finally:
        session.close()
        driver.close()
    typer.echo(
        f"wrote fingerprint for {manifest.section_count} Sections "
        f"({manifest.corpus_hash})"
    )


@app.command("chemical-export-scope")
def chemical_export_scope(
    config: Path = typer.Option(..., exists=True, dir_okay=False, readable=True),
    scope_config: Path = typer.Option(..., exists=True, dir_okay=False, readable=True),
    output: Path = typer.Option(..., dir_okay=False),
) -> None:
    """Export keyword-screened standards for human inclusion/exclusion review."""
    rules = _load_yaml(scope_config)
    terms = rules.get("candidate_terms")
    if rules.get("schema_version") != "1.0" or not isinstance(terms, list):
        raise typer.BadParameter("scope config requires schema_version 1.0 and candidate_terms")
    driver, session = _chemical_session(config)
    try:
        summary = export_scope_candidates(session, terms=terms, output_path=output)
    except Exception as error:
        typer.echo(f"chemical scope export failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    finally:
        session.close()
        driver.close()
    typer.echo(
        f"exported {summary['candidate_count']} candidates "
        f"from {summary['inventory_count']} standards"
    )


@app.command("chemical-freeze-scope")
def chemical_freeze_scope(
    review: Path = typer.Option(..., exists=True, dir_okay=False, readable=True),
    fingerprint: Path = typer.Option(..., exists=True, dir_okay=False, readable=True),
    scope_config: Path = typer.Option(..., exists=True, dir_okay=False, readable=True),
    output: Path = typer.Option(..., dir_okay=False),
) -> None:
    """Validate completed human review and freeze the chemical allowlist."""
    try:
        fingerprint_payload = json.loads(fingerprint.read_text(encoding="utf-8"))
        rules = _load_yaml(scope_config)
        scope = freeze_scope_review(
            review,
            corpus_hash=str(fingerprint_payload["corpus_hash"]),
            terms=rules["candidate_terms"],
            output_path=output,
        )
    except (FileExistsError, KeyError, json.JSONDecodeError, TypeError, ValueError) as error:
        typer.echo(f"chemical scope freeze failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"froze {scope.included_standard_count} included standards")


@app.command("run-paths")
def run_paths(
    config: Path = typer.Option(..., exists=True, dir_okay=False, readable=True),
    query_path: Path = typer.Option(
        ...,
        "--query",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
    model_snapshot: Path = typer.Option(
        ...,
        exists=True,
        file_okay=False,
        readable=True,
    ),
    output: Path = typer.Option(..., dir_okay=False),
    reranker_config: Path = typer.Option(
        Path("configs/reranker-v1.yaml"),
        exists=True,
        dir_okay=False,
        readable=True,
    ),
    chemical_fingerprint: Path = typer.Option(
        Path("artifacts/private/chemical-corpus-fingerprint.json"),
        exists=False,
        dir_okay=False,
    ),
    device: str = typer.Option("cuda:0"),
) -> None:
    """Execute all six paths for one local query and write source-free records."""
    if output.exists():
        raise typer.BadParameter(f"refusing to overwrite existing output: {output}")
    payload = _load_yaml(config)
    try:
        query = QueryRecord.model_validate(
            json.loads(query_path.read_text(encoding="utf-8"))
        )
    except (json.JSONDecodeError, ValidationError) as error:
        raise typer.BadParameter(f"invalid query record: {error}") from error

    driver = None
    try:
        if query.domain.value == "chemical":
            if not chemical_fingerprint.is_file():
                raise typer.BadParameter(
                    f"chemical fingerprint does not exist: {chemical_fingerprint}"
                )
            fingerprint = json.loads(chemical_fingerprint.read_text(encoding="utf-8"))
            driver, session = _chemical_session(config)
            session.close()
            adapter = ChemicalSafetyAdapter(
                driver,
                database=os.environ.get(
                    payload["projects"]["chemical"]["neo4j"].get("database_env", ""),
                    "",
                )
                or None,
                corpus_hash=str(fingerprint["corpus_hash"]),
                source_revision=str(fingerprint["source_revision"]),
            )
        else:
            project = payload["projects"]["pharmaceutical"]
            root = _project_root(payload, "pharmaceutical")
            adapter = PharmaceuticalRegulatoryAdapter(
                root / str(project["corpus_relative_path"]),
                root / str(project["graph_relative_path"]),
                source_revision=str(project.get("source_revision", "pharma-pilot-v1")),
                expected_record_count=(
                    None
                    if project.get("expected_record_count") is None
                    else int(project["expected_record_count"])
                ),
            )
        reranker = QwenFrozenReranker(
            model_snapshot,
            config_path=reranker_config,
            device=device,
        )
        runs = run_all_paths(adapter, query, reranker)
        write_json_atomic(
            output,
            {
                "schema_version": "1.0",
                "question_id": query.question_id,
                "runs": [run.model_dump(mode="json") for run in runs],
            },
        )
    except (KeyError, TypeError, ValueError, RuntimeError) as error:
        typer.echo(f"run-paths failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    finally:
        if driver is not None:
            driver.close()
    completed = sum(run.status.value == "complete" for run in runs)
    typer.echo(f"wrote {len(runs)} path runs ({completed} complete)")


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
