# blender-addon-dev-template

A minimal, production-ready template for creating Blender add-ons.

## 📁 Project Structure

```bash
.
├─ BlenderGeminiAgent/        # Blender add-on source
│  ├─ __init__.py
│  ├─ blender_manifest.toml
│  ├─ *.py
│  └─ prefs.py
├─ tools/
│  └─ build_addon_zip.py     # Creates an installable ZIP
├─ tests/
│  ├─ unit/                  # Pure Python tests
│  └─ blender/               # Blender integration test
├─ .github/
│  └─ workflows/
│     └─ ci.yml              # Lint + test + zip build
├─ pyproject.toml            # uv-based dev environment
└─ README.md
```

### TEST

Separate tests into Blender-dependent and pure logic parts.
To enable testing of the logic layer, defer importing any modules that rely on bpy or its stubs.

The tests under tests/blender are executed within a Blender environment.
For example, on macOS you can run them with the following command:

```bash
/Applications/Blender.app/Contents/MacOS/Blender \
  --background --factory-startup --python tests/blender/test_in_blender.py
```

The tests under `tests/unit` can be executed independently of Blender.
Just like typical Python tests, you can run them, like:

```bash
uv run pytest
```

### CI

In CI, run linting, execute Pytest, and generate a ZIP file that can be installed in Blender.

Blender is not included in the CI workflow because running Blender itself on GitHub Actions requires heavy setup, varies
by platform, and provides little benefit for this template.
Logic tests run without Blender are sufficient, and actual Blender execution should be validated locally.
(Depending on project requirements, adding Blender execution to CI may still be appropriate.)

### LICENSE

Add-ons
are [recommended](https://docs.blender.org/manual/en/latest/advanced/extensions/licenses.html) to be licensed under GPL
v3 or later.
This repository provides an example of publishing a Blender add-on under a compatible license, GPL v3 or later, using
the SPDX format.

### INIT

(This is a temporary method, and we plan to make it possible to obtain the template directly from the Git remote in the
future. #1 )

Initialize a new project from this template by copying files and replacing all occurrences of `BlenderGeminiAgent` with
your add-on name.

```bash
# create ./my_cool_addon/ from the current template
uv run python [path/to/tools/init_from_template.py] my_cool_addon --template [path/to/this/dir] --outdir [path/to/output/dir]
```

- Dry-run (no write):

```bash
uv run python [path/to/tools/init_from_template.py] my_cool_addon --template [path/to/this/dir] --outdir [path/to/output/dir] --dry-run
```

This generates `./my_cool_addon/` with directory names, file names, and file contents updated from `BlenderGeminiAgent`
to your specified name. 
