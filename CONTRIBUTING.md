# Contributing

Use Python 3.11 or 3.12 for the portable tests and Blender 4.1.1 for the Blender check. Install development dependencies in a virtual environment if desired:

```
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m black --check swtor_terrain_tools tests scripts
blender --background --factory-startup --python-exit-code 1 --python tests/blender_smoke.py
```

See [the development guide](docs/DEVELOPMENT.md) before changing format readers or generated-data ownership. Keep PRs focused and describe the user-visible problem, the change and the checks performed. For behavior changes, add a regression that would fail without the change. Do not add tests that merely restate an implementation detail.

Use Black with the configuration in `pyproject.toml`. Explain non-obvious coordinate conversions, binary offsets, thresholds and resource-lifecycle decisions. Distinguish measured game behavior from empirical approximations. Preserve property names and deterministic behavior unless a migration is included.

Do not commit original game files, extracted assets, generated scenes, proprietary textures or local filesystem paths. Prefer tiny synthetic fixtures assembled in the tests. Discuss real-data reproduction by room name and instance ID, and arrange any permitted private sharing separately. Never upload a full resources directory to an issue.

Contributions to this repository are under GPL-3.0-or-later. Retain attribution/license notices when incorporating third-party code and identify its source and license in the PR. AI-assisted contributions should be reviewed and tested to the same standard as other changes.

The GitHub workflow runs portable checks and produces an installation ZIP as a workflow artifact. It does not run Blender or publish releases automatically. Run the Blender smoke test before tagging a release.
