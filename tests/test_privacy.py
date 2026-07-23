from pathlib import Path

from evidence_routing.privacy import scan_tracked_files


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_safe_example_configuration_passes(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "configs/local.example.yaml",
        "password_env: CER_CHEMICAL_NEO4J_PASSWORD\nroot_env: CER_CHEMICAL_PROJECT_ROOT\n",
    )
    assert scan_tracked_files(tmp_path, tracked_files=["configs/local.example.yaml"]) == []


def test_machine_local_path_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "notes.md", "root: C:\\Users\\researcher\\private-project\n")
    findings = scan_tracked_files(tmp_path, tracked_files=["notes.md"])
    assert [finding.rule for finding in findings] == ["absolute-path"]


def test_credential_assignment_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "settings.txt", "SERVICE_API_KEY=realistic-secret-value\n")
    findings = scan_tracked_files(tmp_path, tracked_files=["settings.txt"])
    assert [finding.rule for finding in findings] == ["possible-secret"]


def test_environment_variable_name_is_not_treated_as_a_secret(tmp_path: Path) -> None:
    _write(tmp_path, "settings.yaml", "password: CER_CHEMICAL_NEO4J_PASSWORD\n")
    assert scan_tracked_files(tmp_path, tracked_files=["settings.yaml"]) == []


def test_restricted_file_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "data/raw/source.txt", "restricted source\n")
    findings = scan_tracked_files(tmp_path, tracked_files=["data/raw/source.txt"])
    assert [finding.rule for finding in findings] == ["restricted-directory"]


def test_oversize_file_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "result.json", "123456")
    findings = scan_tracked_files(tmp_path, tracked_files=["result.json"], max_bytes=5)
    assert [finding.rule for finding in findings] == ["oversize-file"]
