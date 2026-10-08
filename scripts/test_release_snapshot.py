"""Run the publication guard against real commit graphs, including the review's bypass."""
import subprocess
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).with_name("check-release-snapshot.sh").resolve()
WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/release.yml"


class ReleaseSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Release test")
        self.git("config", "user.email", "release-test@example.com")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", "/dev/null")
        self.commit(".github/workflows/release.yml", "trusted workflow")
        self.base = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.base)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True,
                                       stderr=subprocess.DEVNULL).strip()

    def commit(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        self.git("add", "--", path)
        self.git("commit", "-m", "Test snapshot")

    def check(self):
        return subprocess.run(["bash", str(GUARD)], cwd=self.root, text=True,
                              capture_output=True, check=False)

    def test_valid_generated_snapshot_is_allowed(self):
        for path in ["sdks/typescript/index.ts", "openapi/v1.yaml", "sdk-release.json"]:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("generated snapshot")
        self.git("add", ".")
        self.git("commit", "-m", "Generate release snapshot")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_merge_cannot_hide_workflow_changes_from_the_second_parent(self):
        self.git("checkout", "-b", "other", self.base)
        self.commit(".github/workflows/release.yml", "untrusted publishing workflow")
        self.git("checkout", "main")
        self.commit("sdks/typescript/index.ts", "generated SDK")
        self.git("update-ref", "refs/remotes/origin/main", self.git("rev-parse", "HEAD"))
        self.git("merge", "--no-ff", "other", "-m", "Merge hidden workflow")
        # Both parts of the old guard pass, reproducing the reported omission.
        self.git("merge-base", "--is-ancestor", "HEAD^", "origin/main")
        self.assertEqual(self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"), "")
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly one parent", result.stdout)

    def test_root_commit_cannot_be_a_generated_snapshot(self):
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly one parent", result.stdout)

    def test_single_parent_snapshot_cannot_change_publishing_code(self):
        for path in [".github/workflows/release.yml", "scripts/release_contract.py"]:
            with self.subTest(path=path):
                self.git("reset", "--hard", self.base)
                self.commit(path, "untrusted source")
                result = self.check()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(path, result.stdout)

    def test_parent_outside_main_cannot_publish_even_if_snapshot_files_are_allowed(self):
        self.commit("README.md", "off-main source")
        self.commit("sdks/typescript/index.ts", "generated SDK")
        self.assertNotEqual(self.check().returncode, 0)

    def test_rename_out_of_the_allowlist_is_rejected(self):
        self.commit("sdks/typescript/index.ts", "generated SDK")
        self.git("update-ref", "refs/remotes/origin/main", self.git("rev-parse", "HEAD"))
        (self.root / "scripts").mkdir()
        self.git("mv", "sdks/typescript/index.ts", "scripts/publish.ts")
        self.git("commit", "-m", "Rename into publishing code")
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("scripts/publish.ts", result.stdout)

    def test_release_workflow_invokes_the_guard_before_reading_snapshot_metadata(self):
        workflow = WORKFLOW.read_text()
        self.assertLess(workflow.index("bash scripts/check-release-snapshot.sh"),
                        workflow.index("recorded_build="))
        self.assertLess(workflow.index("bash scripts/check-release-snapshot.sh"),
                        workflow.index("python3 scripts/release_contract.py validate"))


if __name__ == "__main__":
    unittest.main()
