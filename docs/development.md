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
