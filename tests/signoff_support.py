from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

CSV_TEXT = (
    "ID,Type,Name,Part of,Allocated to,Verified by,Compliance\n"
    "SYS-A,System,Product,,,,\n"
    "SYS-B,System,Other,,,,\n"
    "R1,,One,,SYS-A,,Not verified\n"
    "R2,,Two,,SYS-B,,Not verified\n"
)

TOOLS_PRESENT = bool(shutil.which("git") and shutil.which("ssh-keygen"))
EMAIL = "t@example.com"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def init_signing_repo(root: Path, keys: Path) -> Path:
    """A repo whose tags are signed with a fresh SSH key that its allowed-signers file trusts."""
    keys.mkdir(exist_ok=True)
    key = keys / "key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True, capture_output=True)
    allowed = keys / "allowed_signers"
    allowed.write_text(f"{EMAIL} {(keys / 'key.pub').read_text().strip()}\n", encoding="utf-8")
    git(root, "init", "-q")
    for name, value in (
        ("user.name", "Tester"), ("user.email", EMAIL), ("gpg.format", "ssh"), ("user.signingkey", str(key)),
        ("gpg.ssh.allowedSignersFile", str(allowed)), ("commit.gpgsign", "false"), ("tag.gpgsign", "false"),
    ):
        git(root, "config", name, value)
    return allowed
