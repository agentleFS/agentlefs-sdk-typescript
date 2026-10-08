"""Validation shared by release workflows; failures precede Git/npm publication."""
import base64
import gzip
import hashlib
import json
import os
import re
import sys
from pathlib import Path

VERSION = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"


def validate(version, build=None, spec_sha256=None):
    if not re.fullmatch(VERSION, version):
        raise ValueError("Release must be stable X.Y.Z without leading zeros")
    if build is not None and not re.fullmatch(r"[0-9a-f]{40}", build):
        raise ValueError("Build must be the full released API commit SHA")

    if spec_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", spec_sha256):
        raise ValueError("Spec digest must be a SHA-256 hex digest")


def snapshot(digest, path):
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
        raise ValueError("Spec bytes differ from the released API snapshot")


def unpack(encoded, digest, path):
    validate("0.0.0", spec_sha256=digest)
    raw = gzip.decompress(base64.b64decode(encoded, validate=True))
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("Dispatched spec digest does not match its bytes")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def metadata(version, build, spec_sha256, path):
    validate(version, build, spec_sha256)
    recorded = json.loads(Path(path).read_text())
    if recorded != {"release": version, "build": build, "spec_sha256": spec_sha256}:
        raise ValueError("Existing SDK tag was generated for a different API release/build")
    return recorded


def check_integrity(tarball, published):
    digest = "sha512-" + base64.b64encode(hashlib.sha512(Path(tarball).read_bytes()).digest()).decode()
    if json.loads(Path(published).read_text()) != digest:
        raise ValueError("npm version already exists with different package bytes; refusing to replace it")


def publish_tag(version, tags):
    validate(version)
    latest = tags.get("latest")
    if latest is None:
        return "latest"
    validate(latest)
    numbers = lambda value: tuple(map(int, value.split(".")))
    return "latest" if numbers(version) >= numbers(latest) else "api-" + version


def main():
    command, *args = sys.argv[1:]
    if command == "validate":
        validate(*args)
    elif command == "metadata":
        metadata(*args)
    elif command == "write":
        version, build, spec_sha256, path = args
        validate(version, build, spec_sha256)
        Path(path).write_text(json.dumps({"release": version, "build": build, "spec_sha256": spec_sha256}, indent=2) + "\n")
    elif command == "integrity":
        check_integrity(*args)
    elif command == "snapshot":
        snapshot(*args)
    elif command == "publish-tag":
        version, path = args
        print(publish_tag(version, json.loads(Path(path).read_text())))
    elif command == "unpack":
        unpack(os.environ["SPEC_GZIP_BASE64"], os.environ["SPEC_SHA256"], "openapi/v1.yaml")
    else:
        raise ValueError("Unknown release contract command")


if __name__ == "__main__":
    main()
