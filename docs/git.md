# Use as a Git diff tool

The included `examples/reqtable-git-diff` wrapper generates an offline HTML comparison and opens it with the platform's default browser. Point `REQTABLE_PYZ` at the built zipapp and set the unique ID column if it is not `ID`:

```sh
REQTABLE_PYZ="$PWD/dist/reqtable.pyz" REQTABLE_ID_COLUMN=ID \
  examples/reqtable-git-diff old-requirements.csv new-requirements.csv
```

To register it as a repository-local Git difftool:

```sh
git config diff.tool reqtable
git config difftool.reqtable.cmd \
  'REQTABLE_PYZ="$PWD/dist/reqtable.pyz" REQTABLE_ID_COLUMN=ID examples/reqtable-git-diff "$LOCAL" "$REMOTE"'
git config difftool.prompt false
git difftool --tool=reqtable REVISION_A REVISION_B -- path/to/requirements.csv
```

The wrapper accepts `REQTABLE_CONFIG=/path/to/config.json`. CLI values in the wrapper override matching JSON settings. Git may provide `/dev/null` for a newly added or deleted file; generate a snapshot for that case or compare two commits in which the CSV exists.

## Compare against a git checkpoint

Skip the manual export: `--old` also accepts `git:REV`, where `REV` is any tag, branch, or commit. The old file is read from git, so the working-tree `--new` CSV is compared with its own committed version at that revision:

```sh
python -m reqtable --old git:v1.0 --new requirements.csv --id-column ID -o changes-since-v1.0.html
```

If the file lived elsewhere at that revision, name the path with `git:REV:PATH`:

```sh
python -m reqtable --old git:v1.0:docs/old-requirements.csv --new requirements.csv --id-column ID -o changes.html
```

The report labels the old side like `requirements.csv @ v1.0 (abc1234)`. This form runs `git` as an external command, so `git` must be on `PATH`, and the CSV must be inside a git repository. Git's line-ending and attribute filters apply, so the result matches a checkout of that revision. It works with `--document-mode develop` too.
