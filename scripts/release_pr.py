"""Land a tested generated SDK through CI and a head-matched automatic PR merge."""
import json
import os
import subprocess
import sys
import time

from release_contract import validate

ARTIFACTS = ("sdks/", "openapi/v1.yaml", "sdk-release.json")


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def api(path, *args):
    return json.loads(run("gh", "api", path, *args))


def version_tuple(value):
    validate(value)
    return tuple(map(int, value.split(".")))


def ensure_forward(version, recorded, tags=()):
    latest = max((version_tuple(tag) for tag in tags), default=(0, 0, 0))
    if version_tuple(version) < latest or (recorded and version_tuple(version) < version_tuple(recorded["release"])):
        raise ValueError("This release would replace an equal or newer SDK on main; retry its existing tag instead")


def validate_pr(pr, branch, sha):
    if pr["base"]["ref"] != "main" or pr["head"]["ref"] != branch or pr["head"]["sha"] != sha:
        raise ValueError("Generated PR no longer points at the tested SDK commit; rerun regeneration")
    if pr["state"] == "closed" and not pr.get("merged"):
        raise ValueError("The generated PR was closed without merging; reopen it to retry")


def wait_until(fetch, done, timeout, label, sleep=time.sleep, clock=time.monotonic):
    deadline = clock() + timeout
    while True:
        value = fetch()
        if done(value):
            return value
        if clock() >= deadline:
            raise TimeoutError(f"Timed out waiting for {label}; rerun regeneration with the same release/build to resume")
        sleep(15)


def successful_ci(value):
    if value["status"] != "completed":
        return False
    if value["conclusion"] != "success":
        raise ValueError("Generated SDK CI failed; inspect its Actions run and rerun regeneration after fixing it")
    return True


def preflight(version, build, digest, ref="HEAD"):
    validate(version, build, digest)
    raw = subprocess.run(["git", "show", ref + ":sdk-release.json"], text=True, capture_output=True)
    recorded = json.loads(raw.stdout) if raw.returncode == 0 else None
    tags = run("git", "tag", "--list").splitlines()
    stable = []
    for tag in tags:
        try:
            validate(tag)
            stable.append(tag)
        except ValueError:
            pass
    ensure_forward(version, recorded, stable)
    if recorded and recorded["release"] == version and recorded != {"release": version, "build": build, "spec_sha256": digest}:
        raise ValueError("Main already records this SDK version with different API metadata")


def publish_pr(version, build, digest):
    validate(version, build, digest)
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = "generated/sdk-" + version
    sha = run("git", "rev-parse", "HEAD")
    prs = api(f"repos/{repo}/pulls?state=all&head={repo.split('/')[0]}:{branch}&base=main")
    if len(prs) > 1:
        raise ValueError("Multiple generated PRs use the release branch; resolve them before retrying")
    if prs:
        # List responses omit the merged boolean; read the individual PR for retries.
        pr = api(f"repos/{repo}/pulls/{prs[0]['number']}")
        existing_sha = pr["head"]["sha"]
        run("git", "fetch", "origin", existing_sha)
        # Generation may be repeated with a newer main parent; the tested artifact tree
        # must be identical before trusting an existing PR or merged snapshot.
        run("git", "diff", "--exit-code", existing_sha, sha, "--", *ARTIFACTS)
        sha = existing_sha
        validate_pr(pr, branch, sha)
    else:
        # A prior push can succeed before PR creation fails. Reuse only identical
        # tested artifacts; never force-push a release branch on a retry.
        remote = run("git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}")
        if remote:
            existing_sha = remote.split()[0]
            run("git", "fetch", "origin", existing_sha)
            run("git", "diff", "--exit-code", existing_sha, sha, "--", *ARTIFACTS)
            sha = existing_sha
        else:
            run("git", "push", "origin", f"HEAD:refs/heads/{branch}")
        pr = api(f"repos/{repo}/pulls", "--method", "POST", "-f", "base=main", "-f", f"head={branch}",
                 "-f", f"title=Release SDK {version}", "-f",
                 f"body=Update the generated SDK to API release {version} (build {build}). Generation, SDK tests, and packed CJS/ESM checks passed. CI is explicitly dispatched before automatic squash merge and publication.")
    number = pr["number"]
    if not pr.get("merged"):
        # GITHUB_TOKEN-created PRs do not emit a workflow-triggering pull_request event.
        baseline = api(f"repos/{repo}/actions/workflows/ci.yml/runs?event=workflow_dispatch&head_sha={sha}&per_page=100")
        seen = {item["id"] for item in baseline["workflow_runs"]}
        run("gh", "workflow", "run", "ci.yml", "--ref", branch)

        def dispatched_run():
            values = api(f"repos/{repo}/actions/workflows/ci.yml/runs?event=workflow_dispatch&head_sha={sha}&per_page=100")
            return next((item for item in values["workflow_runs"] if item["id"] not in seen and item["head_branch"] == branch and item["head_sha"] == sha), None)

        ci = wait_until(dispatched_run, lambda value: value is not None, 120, "the dispatched CI run")
        completed = wait_until(lambda: api(f"repos/{repo}/actions/runs/{ci['id']}"), successful_ci, 1800, "generated SDK CI")
        if completed["head_sha"] != sha:
            raise ValueError("Dispatched CI checked a different SDK commit; refusing automatic merge")
        jobs = api(f"repos/{repo}/actions/runs/{ci['id']}/jobs?per_page=100")["jobs"]
        expected = {"Committed SDK matches the spec", "Generated SDK compiles", "SDK tests"}
        passed = {job["name"] for job in jobs if job["conclusion"] == "success"}
        if not expected.issubset(passed):
            raise ValueError("Dispatched CI did not pass every required SDK job; refusing automatic merge")
        current = api(f"repos/{repo}/pulls/{number}")
        validate_pr(current, branch, sha)
        run("git", "fetch", "origin", "main", "--tags")
        preflight(version, build, digest, "origin/main")
        # Merge now after successful CI. Leaving an auto-merge request queued after a
        # timeout could let an old release land after a newer one.
        run("gh", "pr", "merge", str(number), "--repo", repo, "--squash", "--match-head-commit", sha)

        def merged_pr():
            current = api(f"repos/{repo}/pulls/{number}")
            validate_pr(current, branch, sha)
            return current

        pr = wait_until(merged_pr, lambda value: value.get("merged"), 900, "automatic PR merge")
    merged = pr["merge_commit_sha"]
    run("git", "fetch", "origin", "main", merged)
    run("git", "merge-base", "--is-ancestor", merged, "origin/main")
    # Tags must contain precisely the SDK tested above, even if main moved during CI.
    run("git", "diff", "--exit-code", sha, merged, "--", *ARTIFACTS)
    run("git", "tag", version, merged)
    run("git", "push", "origin", "refs/tags/" + version)
    with open(os.environ.get("GITHUB_STEP_SUMMARY", os.devnull), "a") as summary:
        summary.write(f"Merged generated SDK through {pr['html_url']} and tagged `{version}` at `{merged}`.\n")


if __name__ == "__main__":
    command, *args = sys.argv[1:]
    if command == "preflight":
        preflight(*args)
    elif command == "publish-pr":
        publish_pr(*args)
    else:
        raise ValueError("Unknown release PR command")
