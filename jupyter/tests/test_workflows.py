"""Packaging contracts for upstream-only publishing workflows."""

from pathlib import Path

import yaml


WORKFLOWS = Path(__file__).resolve().parents[2] / ".github/workflows"


def test_all_pages_and_release_jobs_are_upstream_only():
    workflow = yaml.safe_load((WORKFLOWS / "deploy-gh-pages.yml").read_text())
    assert workflow["permissions"] == {"contents": "read"}
    guard = "github.repository == 'freesurfer/freebrowse'"
    for name in ("build", "deploy", "release"):
        assert guard in workflow["jobs"][name]["if"]
    assert "github.ref == 'refs/heads/main'" in workflow["jobs"]["release"]["if"]
    assert workflow["jobs"]["build"]["permissions"] == {"contents": "read", "pages": "read"}
    assert workflow["jobs"]["deploy"]["permissions"] == {
        "contents": "read", "pages": "write", "id-token": "write"}
    assert workflow["jobs"]["release"]["permissions"] == {"contents": "write"}


def test_fork_validation_has_no_publishing_credentials():
    workflow = yaml.safe_load((WORKFLOWS / "jupyter-tests.yml").read_text())
    assert workflow["permissions"] == {"contents": "read"}
    assert all("permissions" not in job for job in workflow["jobs"].values())
