import json
from pathlib import Path
import subprocess
import sys

from build123d import Box, Pos, export_brep, export_step
import pytest

from print_check import check
from print_check.checks import Context, RULES
from print_check.cli import install_skill, main
from print_check.config import context


@pytest.fixture
def cube(tmp_path):
    path = tmp_path / "cube.step"
    export_step(Box(20, 20, 20), str(path))
    return path


def test_all_thirteen_rules_preserved():
    assert set(RULES) == {
        "solids", "overhang", "floating", "hole_ceiling", "min_wall", "sliver",
        "concave_cosmetic", "bed_bevel", "warp_risk", "pin", "stability",
        "projection_ratio", "build_volume",
    }


def test_step_json(cube, capsys):
    assert main(["check", str(cube), "--printer", "bambu_a1_mini", "--format", "json"]) == 0
    result = json.loads(capsys.readouterr().out)["results"][0]
    assert result["status"] == "pass"
    assert result["context"]["bed"] == [180, 180, 180]
    assert len(result["rules_run"]) == 13
    assert result["stats"]["solids"] == 1


def test_brep(tmp_path, capsys):
    path = tmp_path / "part.brep"
    export_brep(Box(10, 10, 10), str(path))
    assert main(["check", str(path)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_fail_exit_and_never(tmp_path, capsys):
    path = tmp_path / "overhang.step"
    export_step(Box(6, 6, 20) + Pos(0, 0, 12) * Box(30, 30, 4), str(path))
    assert main(["check", str(path), "--format", "json"]) == 1
    assert json.loads(capsys.readouterr().out)["results"][0]["status"] == "fail"
    assert main(["check", str(path), "--fail-on", "never"]) == 0


def test_warning_policy(tmp_path, capsys):
    path = tmp_path / "wall.step"
    export_step(Box(0.5, 20, 20), str(path))
    assert main(["check", str(path), "--only", "min_wall"]) == 0
    assert "WARN" in capsys.readouterr().out
    assert main(["check", str(path), "--only", "min_wall", "--fail-on", "warn"]) == 1


def test_mesh_rejected(tmp_path, capsys):
    path = tmp_path / "part.stl"
    path.write_text("solid not-supported\nendsolid\n")
    assert main(["check", str(path), "--format", "json", "--fail-on", "never"]) == 2
    assert "not supported" in json.loads(capsys.readouterr().out)["results"][0]["error"]


def test_missing_input_does_not_hide_other_results(cube, capsys):
    assert main(["check", "missing.step", str(cube), "--format", "json"]) == 2
    assert [r["status"] for r in json.loads(capsys.readouterr().out)["results"]] == ["error", "pass"]


def test_python_requires_explicit_consent(tmp_path, capsys):
    path = tmp_path / "part.py"
    path.write_text('from build123d import Box\nprint("model log")\npart = Box(10, 10, 10)\n')
    assert main(["check", str(path), "--format", "json"]) == 2
    assert "--allow-python" in json.loads(capsys.readouterr().out)["results"][0]["error"]
    assert main(["check", str(path), "--allow-python", "--format", "json"]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["results"][0]["status"] == "pass"
    assert "model log" in output.err


def test_python_build_function(tmp_path, capsys):
    path = tmp_path / "part.py"
    path.write_text("from build123d import Box\ndef build():\n    return Box(10, 10, 10)\n")
    assert main(["check", str(path), "--allow-python"]) == 0


@pytest.mark.parametrize("extra", [
    ["--up", "0", "0", "0"], ["--bed", "0", "180", "180"],
    ["--min-wall", "nan"], ["--min-wall", "-1"], ["--printer", "typo"],
    ["--material", "unknown"], ["--only", "typo"],
])
def test_bad_settings_never_pass(cube, extra, capsys):
    assert main(["check", str(cube), *extra]) == 2


def test_explicit_config_and_overrides(tmp_path):
    config = tmp_path / "settings.toml"
    config.write_text('printer = "bambu_a1_mini"\n[context]\nmin_wall = 1.5\nmaterial = "PETG"\n')
    ctx = context(config, overrides={"min_wall": 2.0})
    assert ctx.bed == (180, 180, 180)
    assert ctx.material == "petg"
    assert ctx.min_wall == 2.0


def test_unknown_config_key(tmp_path):
    path = tmp_path / "bad.toml"
    path.write_text("[context]\nmin_wal = 1\n")
    with pytest.raises(ValueError, match="Unknown settings"):
        context(path)


def test_output_and_overwrite_guard(cube, tmp_path, capsys):
    output = tmp_path / "report.json"
    assert main(["check", str(cube), "--format", "json", "--output", str(output)]) == 0
    assert json.loads(output.read_text())["exit_code"] == 0
    original = cube.read_bytes()
    assert main(["check", str(cube), "--output", str(cube)]) == 2
    assert cube.read_bytes() == original


def test_install_preserves_instructions_and_is_idempotent(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Existing instructions\nKeep these.\n")
    result = install_skill(tmp_path)
    first = agents.read_text()
    install_skill(tmp_path)
    assert agents.read_text() == first
    assert "Keep these." in first
    assert first.count("<!-- print-check:start -->") == 1
    skill = Path(result["skill"]).read_text()
    assert "name: print-check" in skill
    assert "Local installation" in skill


def test_install_refuses_unrelated_skill(tmp_path):
    path = tmp_path / ".pi/skills/print-check/SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("Someone else's skill")
    with pytest.raises(ValueError, match="unrelated"):
        install_skill(tmp_path)
    assert not (tmp_path / "AGENTS.md").exists()


def test_api_context_validation():
    with pytest.raises(ValueError, match="nonzero"):
        check(Box(10, 10, 10), Context(up=(0, 0, 0)))


def test_api_unknown_rule_rejected():
    with pytest.raises(ValueError, match="Unknown rules"):
        check(Box(10, 10, 10), only={"typo"})


def test_empty_solid_retains_upstream_finding():
    shape = Box(10, 10, 10) - Box(20, 20, 20)
    findings = check(shape)
    assert len(findings) == 1
    assert findings[0].rule == "solids"
    assert findings[0].value == 0


def test_rule_implementations_match_pinned_upstream_hashes():
    import ast
    import hashlib
    from print_check import checks

    source = Path(checks.__file__).read_text()
    expected = json.loads(Path(__file__).with_name("upstream-rule-hashes.json").read_text())
    actual = {
        node.name: hashlib.sha256(ast.get_source_segment(source, node).encode()).hexdigest()
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name in expected
    }
    assert len(actual) == 13
    assert actual == expected


def test_module_entrypoint():
    result = subprocess.run([sys.executable, "-m", "print_check.cli", "--version"],
                            capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == "0.1.0"
