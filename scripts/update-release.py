"""Index the latest published stable release after verifying both WASM assets."""
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

REPO = "yongminari/zellij-rounded-bars"
ASSETS = ("rounded-tab-bar.wasm", "rounded-status-bar.wasm")


def version(tag):
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError(f"Not a stable version: {tag}")
    return tuple(map(int, tag[1:].split(".")))


def manifest(tag, directory):
    version(tag)
    checksums = dict(line.split()[::-1] for line in
                     (directory / "SHA256SUMS").read_text().splitlines())
    artifacts = {}
    for name in ASSETS:
        digest = hashlib.sha256((directory / name).read_bytes()).digest()
        if checksums.get(name) != digest.hex():
            raise ValueError(f"Checksum mismatch: {name}")
        artifacts[name] = "sha256-" + base64.b64encode(digest).decode()
    return {"version": tag[1:], "artifacts": artifacts}


def main():
    release = json.loads(subprocess.check_output(
        ["gh", "api", f"repos/{REPO}/releases/latest"], text=True))
    if release["draft"] or release["prerelease"]:
        raise ValueError("Latest release must be published and stable")
    tag = release["tag_name"]
    target = Path("release.json")
    if target.exists() and version(tag) < version("v" + json.loads(target.read_text())["version"]):
        raise ValueError("Refusing to downgrade the release index")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["gh", "release", "download", tag, "--repo", REPO,
                        "--dir", tmp, "--pattern", "*.wasm",
                        "--pattern", "SHA256SUMS"], check=True)
        result = manifest(tag, Path(tmp))
    target.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
