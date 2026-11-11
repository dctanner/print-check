"""CLI with machine-readable reports and explicit executable-input consent."""

import argparse
from dataclasses import asdict
from importlib.resources import files
import json
import os
from pathlib import Path
import runpy
import shutil
import sys
import tempfile

from . import __version__, check
from .checks import RULES
from .config import context, profiles

SOLID_LIMITATIONS = [
    "Heuristic findings, not proof of printability or mechanical safety.",
    "Curved faces and wall thickness are sampled; local defects can be missed.",
    "build_volume may find another orientation while other rules use the requested up axis.",
    "Checks assume the lowest point is on the bed; they do not check absolute Z placement.",
    "No assembly collision/motion checks, slicing, thermal simulation, or load testing.",
]


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, scratch = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(scratch, path)
    finally:
        Path(scratch).unlink(missing_ok=True)


def install_skill(project):
    project = Path(project).expanduser().resolve()
    if not project.is_dir():
        raise ValueError(f"Project directory does not exist: {project}")
    destination = project / ".pi/skills/print-check/SKILL.md"
    resource = files("print_check").joinpath("skill/SKILL.md")
    if resource.is_file():
        content = resource.read_text(encoding="utf-8")
    else:
        # Editable installs use source paths, not wheel force-included resources.
        content = (Path(__file__).resolve().parents[2] / "skills/print-check/SKILL.md").read_text(encoding="utf-8")
    executable = shutil.which("print-check") or str(Path(sys.executable).with_name("print-check"))
    content += f"\n## Local installation\n\nCLI executable for this installation: `{executable}`.\n"
    # Do not silently clobber a different skill.
    if destination.exists() and "Standalone Print Check" not in destination.read_text():
        raise ValueError(f"Refusing to replace unrelated skill: {destination}")
    agent_file = project / "AGENTS.md"
    original = agent_file.read_text() if agent_file.exists() else ""
    begin, end = "<!-- print-check:start -->", "<!-- print-check:end -->"
    section = (
        f"{begin}\n## Print-check skill (default for CAD/printing work)\n\n"
        "Before creating, changing, exporting, or reviewing printable geometry, read\n"
        "`.pi/skills/print-check/SKILL.md` and follow it. Run the checker after geometry\n"
        "changes when STEP/BREP or build123d solids are available. STL/mesh inputs are\n"
        "unsupported: report the format blocker rather than claiming a check passed.\n"
        "Do not replace existing project validation or regenerate unrelated artifacts.\n"
        f"{end}"
    )
    if original.count(begin) != original.count(end) or original.count(begin) > 1:
        raise ValueError(f"Malformed print-check markers in {agent_file}")
    if begin in original:
        before, rest = original.split(begin, 1)
        _, after = rest.split(end, 1)
        updated = before + section + after
    else:
        updated = original.rstrip() + ("\n\n" if original.strip() else "") + section + "\n"
    atomic_text(destination, content)
    atomic_text(agent_file, updated)
    return {"skill": str(destination), "instructions": str(agent_file), "executable": executable}


def load_solid(path, allow_python=False):
    from build123d import Shape, import_brep, import_step

    suffix = path.suffix.lower()
    if suffix in {".step", ".stp"}:
        return import_step(str(path))
    if suffix in {".brep", ".brp"}:
        return import_brep(str(path))
    if suffix == ".py":
        if not allow_python:
            raise ValueError("Python files execute arbitrary code; inspect/trust the file, then use --allow-python")
        # Keep model stdout off JSON stdout.
        from contextlib import redirect_stdout
        with redirect_stdout(sys.stderr):
            namespace = runpy.run_path(str(path))
            build = namespace.get("build")
            shape = build() if callable(build) else namespace.get("part")
        if not isinstance(shape, Shape):
            raise ValueError("Python input must define build() returning a build123d Shape, or a Shape named part")
        return shape
    raise ValueError("Supported inputs: STEP, BREP, trusted Python build123d solids. STL/meshes are not supported.")


def inspect(path, ctx, args):
    available = tuple(RULES)
    only = args.only.split(",") if args.only else None
    if only is not None:
        only = [value.strip() for value in only]
        unknown = set(only) - set(available)
        if unknown:
            raise ValueError(f"Unavailable rules: {', '.join(sorted(unknown))}")
    shape = load_solid(path, args.allow_python)
    findings = check(shape, ctx, only)
    stats = {"solids": len(shape.solids()), "extents_mm": list(shape.bounding_box().size)}
    executed = list(only or available)
    return {
        "path": str(path), "mode": "solid", "status": "fail" if any(f.severity == "fail" for f in findings)
        else "warn" if findings else "pass",
        "rules_run": executed, "context": asdict(ctx), "stats": stats,
        "findings": [{**asdict(f), "label": f.label, "plain": f.said} for f in findings],
        "limitations": SOLID_LIMITATIONS,
    }


def parser():
    p = argparse.ArgumentParser(prog="print-check", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check", help="Check print parts; coordinates must be in mm")
    c.add_argument("files", nargs="+", type=Path)
    c.add_argument("--printer", help="Shipped printer profile; list with printers")
    c.add_argument("--config", type=Path, help="Explicit TOML configuration (never auto-loaded)")
    c.add_argument("--bed", nargs=3, type=float, metavar=("X", "Y", "Z"))
    c.add_argument("--up", nargs=3, type=float, metavar=("X", "Y", "Z"))
    c.add_argument("--forward", nargs=3, type=float, metavar=("X", "Y", "Z"))
    c.add_argument("--min-wall", type=float)
    c.add_argument("--material")
    c.add_argument("--only", help="Comma-separated rule identifiers")
    c.add_argument("--allow-python", action="store_true", help="Allow arbitrary code execution from trusted .py input")
    c.add_argument("--format", choices=["text", "json"], default="text")
    c.add_argument("--output", type=Path, help="Write report atomically (instead of stdout)")
    c.add_argument("--fail-on", choices=["fail", "warn", "never"], default="fail")
    sub.add_parser("printers", help="List bundled printer profiles")
    sub.add_parser("rules", help="List the 13 solid rule identifiers")
    s = sub.add_parser("install-skill", help="Install project-local Pi/Jelly skill and default AGENTS.md instruction")
    s.add_argument("--project", type=Path, default=Path.cwd())
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "printers":
            print(json.dumps(profiles(), indent=2))
            return 0
        if args.command == "rules":
            print(json.dumps({"solid": list(RULES)}, indent=2))
            return 0
        if args.command == "install-skill":
            print(json.dumps(install_skill(args.project), indent=2))
            return 0
        # Refuse accidental destruction of inputs/config, including symlink aliases.
        if args.output and args.output.resolve() in {p.resolve() for p in [*args.files, *([args.config] if args.config else [])]}:
            raise ValueError("--output must not overwrite an input or configuration file")
        ctx = context(args.config, args.printer, {
            name: getattr(args, name) for name in ("bed", "up", "forward", "min_wall", "material")
        })
        results = []
        for path in args.files:
            try:
                results.append(inspect(path, ctx, args))
            except Exception as exc:
                results.append({"path": str(path), "status": "error", "error": str(exc)})
        errors = any(r["status"] == "error" for r in results)
        failed = args.fail_on != "never" and any(
            r["status"] == "fail" or (args.fail_on == "warn" and r["status"] == "warn")
            for r in results
        )
        code = 2 if errors else 1 if failed else 0
        report = {"schema_version": 1, "tool_version": __version__,
                  "exit_code": code, "results": results}
        if args.format == "json":
            output = json.dumps(report, indent=2, allow_nan=False) + "\n"
        else:
            chunks = []
            for r in results:
                chunks.append(f"{r['path']}: {r['status'].upper()} ({r.get('mode', 'input error')})")
                if "error" in r:
                    chunks.append(f"  {r['error']}")
                else:
                    chunks += [f"  {f['severity']:4} {f['rule']}: {f['message']}" for f in r["findings"]]
                    chunks.append(f"  Coverage: {len(r['rules_run'])} rules; " + r["limitations"][0])
            output = "\n".join(chunks) + "\n"
        if args.output:
            atomic_text(args.output, output)
        else:
            print(output, end="")
        return code
    except Exception as exc:
        print(f"print-check: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
