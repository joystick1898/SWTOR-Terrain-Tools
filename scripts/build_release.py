# SPDX-License-Identifier: GPL-3.0-or-later
"""Build an installable ZIP from an explicit file list, without importing bpy."""

import argparse
import ast
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("__init__.py", "core.py", "details.py")


def version(root=ROOT):
    """Read literal Blender metadata without executing add-on imports."""
    tree = ast.parse((root / "swtor_terrain_tools/__init__.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "bl_info"
            for target in node.targets
        ):
            return ".".join(map(str, ast.literal_eval(node.value)["version"]))
    raise ValueError("Missing bl_info version")


def build(output, root=ROOT):
    """Write runtime modules and legal notices with repeatable ZIP metadata."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / f"swtor_terrain_tools_{version(root)}.zip"
    entries = [(root / "swtor_terrain_tools" / name, name) for name in MODULES]
    entries.append((root / "LICENSE", "LICENSE"))
    entries.append((root / "CREDITS.md", "CREDITS.md"))
    with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
        for path, name in entries:
            info = ZipInfo(f"swtor_terrain_tools/{name}", (1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    archive_path.with_suffix(".zip.sha256").write_text(
        f"{digest}  {archive_path.name}\n", encoding="ascii"
    )
    return archive_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    print(build(parser.parse_args().output))
