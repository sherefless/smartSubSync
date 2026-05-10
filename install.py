#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def run(command: list[str]) -> None:
    print("+ " + " ".join(command))
    subprocess.run(command, check=True)


def mpv_config_dir() -> Path:
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise RuntimeError("APPDATA is not set; cannot find mpv config directory.")
        return Path(appdata) / "mpv"
    return Path.home() / ".config" / "mpv"


def venv_python(venv_dir: Path) -> Path:
    if sys.platform.startswith("win"):
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def install_project(python_path: Path) -> None:
    run(
        [
            str(python_path),
            "-m",
            "pip",
            "install",
            "--no-build-isolation",
            "-e",
            str(PROJECT_ROOT),
        ]
    )


def create_venv(venv_dir: Path, *, skip_dependencies: bool) -> Path:
    python_path = venv_python(venv_dir)
    if not python_path.exists():
        print(f"Creating virtual environment: {venv_dir}")
        venv.EnvBuilder(with_pip=True).create(venv_dir)

    if not skip_dependencies:
        run(
            [
                str(python_path),
                "-m",
                "pip",
                "install",
                "--upgrade",
                "pip",
                "setuptools",
                "wheel",
            ]
        )
        run(
            [
                str(python_path),
                "-m",
                "pip",
                "install",
                "torch",
                "--index-url",
                "https://download.pytorch.org/whl/cpu",
            ]
        )
        run([str(python_path), "-m", "pip", "install", "silero-vad", "numpy"])

    install_project(python_path)

    return python_path


def venv_command(venv_dir: Path) -> Path:
    if sys.platform.startswith("win"):
        return venv_dir / "Scripts" / "smartsubsync.exe"
    return venv_dir / "bin" / "smartsubsync"


def upsert_config_value(content: str, key: str, value: str) -> str:
    lines: list[str] = []
    found = False
    for line in content.splitlines():
        if line.startswith(f"{key}="):
            lines.append(f"{key}={value}")
            found = True
        else:
            lines.append(line)
    if not found:
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def read_config_values(content: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def render_config(config_target: Path, template_path: Path, *, command_path: Path) -> str:
    template = template_path.read_text(encoding="utf-8")
    if not config_target.exists():
        return upsert_config_value(template, "command", str(command_path))

    values = read_config_values(config_target.read_text(encoding="utf-8", errors="replace"))
    template_keys = set(read_config_values(template))
    content = template
    for key, value in values.items():
        if key == "command" or key not in template_keys:
            continue
        content = upsert_config_value(content, key, value)
    return upsert_config_value(content, "command", str(command_path))


def install_mpv_files(*, command_path: Path) -> None:
    config_dir = mpv_config_dir()
    scripts_dir = config_dir / "scripts"
    opts_dir = config_dir / "script-opts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    opts_dir.mkdir(parents=True, exist_ok=True)

    lua_source = PROJECT_ROOT / "mpv" / "smartsubsync.lua"
    lua_target = scripts_dir / "smartsubsync.lua"
    if not lua_target.exists() or lua_source.resolve() != lua_target.resolve():
        shutil.copy2(lua_source, lua_target)

    config_source = PROJECT_ROOT / "mpv" / "script-opts" / "smartsubsync.conf"
    config_target = opts_dir / "smartsubsync.conf"
    config_target.write_text(
        render_config(config_target, config_source, command_path=command_path),
        encoding="utf-8",
    )

    print()
    print("Installed smartSubSync for mpv.")
    print(f"Lua script: {lua_target}")
    print(f"Config:     {config_target}")
    print(f"Command:    {command_path}")
    print(f"Check:      {command_path} doctor")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install smartSubSync for mpv.")
    parser.add_argument(
        "--venv",
        default=str(PROJECT_ROOT / ".venv"),
        help="Virtual environment path. Defaults to .venv inside the project.",
    )
    parser.add_argument(
        "--skip-dependencies",
        action="store_true",
        help="Skip third-party dependency installs; still installs smartSubSync itself.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    venv_dir = Path(args.venv).resolve()
    create_venv(venv_dir, skip_dependencies=args.skip_dependencies)
    install_mpv_files(command_path=venv_command(venv_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
