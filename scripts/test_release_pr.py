import unittest
from unittest.mock import patch

import release_pr


class ReleasePrTests(unittest.TestCase):
    def test_downgrade_checks_history_even_before_main_has_metadata(self):
        with self.assertRaisesRegex(ValueError, "newer SDK"):
            release_pr.ensure_forward("0.5.3", None, ["0.5.4"])
        release_pr.ensure_forward("0.5.5", None, ["0.5.4"])

    def test_same_version_can_resume_an_already_merged_pr(self):
        release_pr.ensure_forward("0.5.4", {"release": "0.5.4"}, ["0.5.4"])

    def test_newer_main_cannot_be_replaced(self):
        with self.assertRaises(ValueError):
            release_pr.ensure_forward("0.5.4", {"release": "0.5.5"})

    def test_changed_pr_head_is_rejected(self):
        pr = {"base": {"ref": "main"}, "head": {"ref": "generated/sdk-0.5.4", "sha": "changed"}, "state": "open"}
        with self.assertRaisesRegex(ValueError, "tested SDK commit"):
            release_pr.validate_pr(pr, "generated/sdk-0.5.4", "tested")

    def test_closed_pr_requires_reopening(self):
        pr = {"base": {"ref": "main"}, "head": {"ref": "generated/sdk-0.5.4", "sha": "tested"}, "state": "closed", "merged": False}
        with self.assertRaisesRegex(ValueError, "reopen"):
            release_pr.validate_pr(pr, "generated/sdk-0.5.4", "tested")

    def test_failed_or_cancelled_ci_cannot_allow_merge(self):
        for conclusion in ("failure", "cancelled", "skipped", "timed_out"):
            with self.assertRaises(ValueError):
                release_pr.successful_ci({"status": "completed", "conclusion": conclusion})
        self.assertFalse(release_pr.successful_ci({"status": "in_progress"}))
        self.assertTrue(release_pr.successful_ci({"status": "completed", "conclusion": "success"}))

    def test_timeout_explains_same_release_retry(self):
        with self.assertRaisesRegex(TimeoutError, "same release/build"):
            release_pr.wait_until(lambda: None, bool, 1, "CI", sleep=lambda _: None, clock=iter([0, 2]).__next__)

    def test_merged_pr_retry_tags_the_verified_merge_not_new_generation(self):
        tested, merged = "a" * 40, "b" * 40
        pr = {"number": 7, "base": {"ref": "main"}, "head": {"ref": "generated/sdk-0.5.4", "sha": tested}, "state": "closed", "merged": True, "merge_commit_sha": merged, "html_url": "https://example.com/pr/7"}
        calls = []
        def command(*args):
            calls.append(args)
            return "c" * 40 if args[:3] == ("git", "rev-parse", "HEAD") else ""
        with patch.dict("os.environ", {"GITHUB_REPOSITORY": "agentleFS/sdk"}), patch.object(release_pr, "run", side_effect=command), patch.object(release_pr, "api", side_effect=[[{"number": 7}], pr]):
            release_pr.publish_pr("0.5.4", "d" * 40, "e" * 64)
        self.assertIn(("git", "tag", "0.5.4", merged), calls)
        self.assertIn(("git", "diff", "--exit-code", tested, merged, "--", *release_pr.ARTIFACTS), calls)
        self.assertFalse(any(call[:3] == ("gh", "workflow", "run") for call in calls))

    def test_changed_merged_artifacts_prevent_tag(self):
        import subprocess
        tested, merged = "a" * 40, "b" * 40
        pr = {"number": 7, "base": {"ref": "main"}, "head": {"ref": "generated/sdk-0.5.4", "sha": tested}, "state": "closed", "merged": True, "merge_commit_sha": merged}
        calls = []
        def command(*args):
            calls.append(args)
            if args[:5] == ("git", "diff", "--exit-code", tested, merged):
                raise subprocess.CalledProcessError(1, args)
            return "c" * 40 if args[:3] == ("git", "rev-parse", "HEAD") else ""
        with patch.dict("os.environ", {"GITHUB_REPOSITORY": "agentleFS/sdk"}), patch.object(release_pr, "run", side_effect=command), patch.object(release_pr, "api", side_effect=[[{"number": 7}], pr]):
            with self.assertRaises(subprocess.CalledProcessError):
                release_pr.publish_pr("0.5.4", "d" * 40, "e" * 64)
        self.assertFalse(any(call[:2] == ("git", "tag") for call in calls))


    def test_new_pr_only_merges_after_exact_dispatched_ci_passes(self):
        self.exercise_new_pr("success", complete_jobs=True)

    def test_failed_ci_prevents_merge_and_tag(self):
        self.exercise_new_pr("failure", complete_jobs=True)

    def test_skipped_required_job_prevents_merge_and_tag(self):
        self.exercise_new_pr("success", complete_jobs=False)

    def test_orphan_generated_branch_is_reused_without_force_push(self):
        self.exercise_new_pr("success", complete_jobs=True, orphan=True)

    def exercise_new_pr(self, conclusion, complete_jobs, orphan=False):
        sha, merged = "a" * 40, "b" * 40
        branch = "generated/sdk-0.5.4"
        pr = {"number": 8, "base": {"ref": "main"}, "head": {"ref": branch, "sha": sha}, "state": "open", "merged": False, "html_url": "https://example.com/pr/8"}
        events = []
        runs_reads = 0
        merged_requested = False
        def command(*args):
            nonlocal merged_requested
            events.append(args)
            if args[:3] == ("gh", "pr", "merge"):
                merged_requested = True
            if args[:2] == ("git", "ls-remote") and orphan:
                return sha + "\trefs/heads/" + branch
            return ("c" * 40 if orphan else sha) if args[:3] == ("git", "rev-parse", "HEAD") else ""
        def request(path, *args):
            nonlocal runs_reads
            events.append(("api", path))
            if "/pulls?" in path:
                return []
            if path.endswith("/pulls"):
                return pr
            if path.endswith("/pulls/8"):
                return dict(pr, merged=merged_requested, state="closed" if merged_requested else "open", merge_commit_sha=merged)
            if "/workflows/ci.yml/runs?" in path:
                runs_reads += 1
                return {"workflow_runs": [] if runs_reads == 1 else [{"id": 42, "head_branch": branch, "head_sha": sha}]}
            if path.endswith("/runs/42"):
                return {"status": "completed", "conclusion": conclusion, "head_sha": sha}
            if "/runs/42/jobs" in path:
                names = ["Committed SDK matches the spec", "Generated SDK compiles", "SDK tests"]
                return {"jobs": [{"name": name, "conclusion": "success" if complete_jobs or name != "SDK tests" else "skipped"} for name in names]}
            raise AssertionError(path)
        with patch.dict("os.environ", {"GITHUB_REPOSITORY": "agentleFS/sdk"}), patch.object(release_pr, "run", side_effect=command), patch.object(release_pr, "api", side_effect=request), patch.object(release_pr, "preflight") as forward:
            if conclusion != "success" or not complete_jobs:
                with self.assertRaises(ValueError):
                    release_pr.publish_pr("0.5.4", "d" * 40, "e" * 64)
                self.assertFalse(merged_requested)
                self.assertFalse(any(event[:2] == ("git", "tag") for event in events))
            else:
                release_pr.publish_pr("0.5.4", "d" * 40, "e" * 64)
                merge = ("gh", "pr", "merge", "8", "--repo", "agentleFS/sdk", "--squash", "--match-head-commit", sha)
                jobs = next(event for event in events if event[0] == "api" and "/runs/42/jobs" in event[1])
                self.assertLess(events.index(jobs), events.index(merge))
                forward.assert_called_once_with("0.5.4", "d" * 40, "e" * 64, "origin/main")
                self.assertIn(("git", "tag", "0.5.4", merged), events)
                if orphan:
                    self.assertIn(("git", "diff", "--exit-code", sha, "c" * 40, "--", *release_pr.ARTIFACTS), events)
                    self.assertFalse(any(event[:3] == ("git", "push", "origin") and "HEAD:" in event[3] for event in events))


if __name__ == "__main__":
    unittest.main()
