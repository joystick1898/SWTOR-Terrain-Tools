# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep install ZIPs reproducible and free of fixtures, caches and developer files."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

spec = importlib.util.spec_from_file_location(
    "release_builder", Path(__file__).parents[1] / "scripts/build_release.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ReleaseTests(unittest.TestCase):
    def test_install_zip_contents_and_reproducibility(self):
        with tempfile.TemporaryDirectory() as folder:
            first = builder.build(Path(folder) / "first")
            second = builder.build(Path(folder) / "second")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with ZipFile(first) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(
                    set(archive.namelist()),
                    {
                        f"swtor_terrain_tools/{name}"
                        for name in (*builder.MODULES, "LICENSE", "CREDITS.md")
                    },
                )
                self.assertIn(
                    b"GNU GENERAL PUBLIC LICENSE",
                    archive.read("swtor_terrain_tools/LICENSE"),
                )


if __name__ == "__main__":
    unittest.main()
