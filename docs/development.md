# Build and test

```sh
python -m unittest discover -s tests -v
python build.py
```

The build writes `dist/reqtable.pyz`.

## Formatting

Python is formatted with [ruff](https://docs.astral.sh/ruff/), configured in `ruff.toml`. Format before you commit:

```sh
ruff format .
```

CI runs `ruff format --check .` and fails the pull request if any file would change. It pins ruff `0.17.5`, so install the same version locally to get identical output (`pip install ruff==0.17.5`). Only formatting is enforced; lint rules are off.

## Releasing

`pyproject.toml` takes the package version from `__version__` in `reqtable/__init__.py`. To check the package locally:

```sh
uv build --out-dir /tmp/reqtable-dist
uv tool install /tmp/reqtable-dist/reqtable-*.whl
reqtable --version
```

To release, bump `__version__` in a pull request and merge it, then create a GitHub release whose tag is `v` plus the version (for example `v0.2.0`). The `publish` workflow builds the package and uploads it to PyPI. It fails if the tag and `__version__` disagree.

One-time PyPI setup (trusted publishing, so no token is stored):

1. Create a PyPI account with two-factor authentication.
2. On PyPI, open Your account → Publishing, and add a pending publisher: project `reqtable`, owner `patrick984`, repository `reqtable`, workflow `publish.yml`, environment `pypi`.
3. In the GitHub repository, open Settings → Environments and create an environment named `pypi`. Optionally require your approval for deployments.

After the first release, `uv tool install reqtable` works without the git URL.
