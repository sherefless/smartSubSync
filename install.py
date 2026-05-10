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


def create_venv(venv_dir: Path, *, skip_dependencies: bool) -> Path:
    python_path = venv_python(venv_dir)
    if not python_path.exists():
        print(f"Creating virtual environment: {venv_dir}")
        venv.EnvBuilder(with_pip=True).create(venv_dir)

    if not skip_dependencies:
        run([str(python_path), "-m", "pip", "install", "--upgrade", "pip"])
        run(
            [
                str(python_path),
                "-m",
                "pip",
                "install",
                "torch",
                "torchaudio",
                "--index-url",
                "https://download.pytorch.org/whl/cpu",
            ]
        )
        run([str(python_path), "-m", "pip", "install", "silero-vad", "numpy"])

    return python_path


def render_config(template_path: Path, *, python_path: Path, helper_path: Path) -> str:
    content = template_path.read_text(encoding="utf-8")
    lines: list[str] = []
    for line in content.splitlines():
        if line.startswith("python="):
            lines.append(f"python={python_path}")
        elif line.startswith("helper_path="):
            lines.append(f"helper_path={helper_path}")
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


def install_mpv_files(*, python_path: Path) -> None:
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
        render_config(
            config_source,
            python_path=python_path,
            helper_path=PROJECT_ROOT / "smartsubsync_cli.py",
        ),
        encoding="utf-8",
    )

    print()
    print("Installed smartSubSync for mpv.")
    print(f"Lua script: {lua_target}")
    print(f"Config:     {config_target}")
    print(f"Python:     {python_path}")


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
        help="Only install mpv files and write config paths.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    python_path = create_venv(Path(args.venv).resolve(), skip_dependencies=args.skip_dependencies)
    install_mpv_files(python_path=python_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
