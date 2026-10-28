"""Local CLI report export and validation require no provider access."""

import json
import sys
from importlib.resources import files

import pytest

from uk_data_mcp import cli


def test_export_saved_workspace_produces_all_five_artifacts(tmp_path, monkeypatch, capsys):
    source = tmp_path / "workspace.json"
    report = json.loads(
        files("uk_data_mcp").joinpath("demo_desk_study.json").read_text(encoding="utf-8")
    )
    report["gaps"][0]["notes"] = "Review boundary against layout"
    source.write_text(json.dumps(report), encoding="utf-8")
    output = tmp_path / "export"
    monkeypatch.setattr(
        sys, "argv", ["uk-data-mcp", "report", "--input", str(source), "--output-dir", str(output)]
    )
    cli.main()
    result = json.loads(capsys.readouterr().out)
    assert len(result["files"]) == 5
    assert all((output / name).is_file() for name in result["files"])
    assert "Review boundary against layout" in (output / "desk-study.html").read_text(
        encoding="utf-8"
    )
    assert (
        json.loads((output / "desk-study.json").read_text(encoding="utf-8"))["evidence"]
        == report["evidence"]
    )


def test_invalid_study_inputs_fail_before_any_provider_call(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uk-data-mcp",
            "desk-study",
            "--latitude",
            "52.45",
            "--longitude",
            "-1.93",
            "--nation",
            "England",
            "--max-borehole-pages",
            "6",
        ],
    )
    with pytest.raises(SystemExit) as failure:
        cli.main()
    assert failure.value.code == 2
    assert "limit" in capsys.readouterr().err
