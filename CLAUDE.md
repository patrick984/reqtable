# reqtable

- Format Python with `ruff format .` before committing. CI runs `ruff format --check` and fails on unformatted files.
- Run the tests with `python -m unittest discover -s tests`. A bare `discover` misses tests that import each other.
- Work on a branch and open a pull request; `main` is protected.
