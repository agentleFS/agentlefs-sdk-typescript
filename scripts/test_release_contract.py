import base64
import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from release_contract import validate, metadata, check_integrity, snapshot, publish_tag, unpack


class ReleaseContractTests(unittest.TestCase):
    def test_only_final_semver_and_full_build(self):
        validate("1.20.300", "a" * 40)
        for version in ("v1.2.3", "1.2.3-rc.1", "1.2.3+meta", "01.2.3", "1.02.3", "1.2", "x.2.3", "1.2.3\n"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                validate(version)
        for build in ("", "abc123", "A" * 40):
            with self.subTest(build=build), self.assertRaises(ValueError):
                validate("1.2.3", build)

    def test_existing_tag_must_belong_to_the_same_api_release(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "sdk-release.json"
            path.write_text(json.dumps({"release": "1.2.3", "build": "a" * 40, "spec_sha256": "c" * 64}))
            metadata("1.2.3", "a" * 40, "c" * 64, path)
            with self.assertRaises(ValueError):
                metadata("1.2.3", "b" * 40, "c" * 64, path)
            with self.assertRaises(ValueError):
                metadata("1.2.4", "a" * 40, "c" * 64, path)

    def test_delayed_version_cannot_move_latest_backwards(self):
        self.assertEqual(publish_tag("1.10.0", {"latest": "1.9.0"}), "latest")
        self.assertEqual(publish_tag("1.9.0", {"latest": "1.10.0"}), "api-1.9.0")
        self.assertEqual(publish_tag("1.10.0", {"latest": "1.10.0"}), "latest")
        self.assertEqual(publish_tag("1.0.0", {}), "latest")

    def test_dispatch_payload_preserves_exact_released_spec(self):
        with tempfile.TemporaryDirectory() as root:
            raw = b"openapi: 3.1.0\ninfo: {version: 1.2.3}\n"
            encoded = base64.b64encode(gzip.compress(raw)).decode()
            digest = hashlib.sha256(raw).hexdigest()
            path = Path(root) / "openapi/v1.yaml"
            unpack(encoded, digest, path)
            self.assertEqual(path.read_bytes(), raw)
            with self.assertRaises(ValueError):
                unpack(encoded, "0" * 64, path)
            self.assertEqual(path.read_bytes(), raw)

    def test_snapshot_must_match_released_digest(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "v1.yaml"
            path.write_bytes(b"released spec")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            snapshot(digest, path)
            path.write_bytes(b"newer production spec")
            with self.assertRaises(ValueError):
                snapshot(digest, path)

    def test_retry_requires_identical_registry_artifact(self):
        with tempfile.TemporaryDirectory() as root:
            tarball, published = Path(root) / "sdk.tgz", Path(root) / "npm.json"
            tarball.write_bytes(b"tested SDK artifact")
            digest = "sha512-" + base64.b64encode(hashlib.sha512(tarball.read_bytes()).digest()).decode()
            published.write_text(json.dumps(digest))
            check_integrity(tarball, published)
            tarball.write_bytes(b"different SDK artifact")
            with self.assertRaises(ValueError):
                check_integrity(tarball, published)


if __name__ == "__main__":
    unittest.main()
