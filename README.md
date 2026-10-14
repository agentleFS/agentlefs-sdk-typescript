# agentleFS TypeScript SDK

Official TypeScript client for the [agentleFS REST API](https://agentlefs.com).

```sh
npm install @agentlefs/sdk
```

See [the package README](sdks/typescript/README.md) for usage. Fern generates the
client from the OpenAPI contract production serves at
https://agentlefs.com/v1/openapi.yaml. Change the API contract or generator config
instead of editing generated client files.

## Regeneration and release

Production promotion in `agentleFS/proof-of-concept-2` verifies exhaustive release
CI and creates the final stable `X.Y.Z` API tag and published release. It dispatches
`regenerate.yml` here with the final release, build SHA and immutable OpenAPI
snapshot from that commit. The SDK version exactly matches the API version, including
releases whose API contract is unchanged.

Regeneration verifies the snapshot digest, generates from those exact bytes and runs SDK
tests, builds, and loads the packed package through CJS and ESM. Only after those
checks pass does it commit the generated SDK, OpenAPI snapshot and release
metadata to a `generated/sdk-X.Y.Z` branch and automatically open a PR into `main`.
The workflow explicitly dispatches CI for that exact commit, waits for all three
SDK jobs to pass, and performs a head-matched squash merge automatically. It verifies
that the merged commit contains exactly the tested generated files, tags that
commit `X.Y.Z`, and explicitly dispatches `release.yml`. Explicit dispatch avoids
manual workflow approvals for bot-created PRs and starts publication for bot-created tags. No routine manual PR or
merge step is required; failures or conflicting branch rules need intervention.

The API repository needs `SDK_DISPATCH_TOKEN` with Actions write access to this
repository. Enable **Allow GitHub Actions to create and approve pull requests**
in this repository's Actions settings; organization policy must also allow it. The regeneration workflow needs contents,
Actions and pull-request write permissions. It never force pushes. A shared queue
serializes updates to `main`, and release metadata plus existing stable tags prevent
older releases from replacing a newer SDK. Matching historical release tags can
still resume publication without modifying `main`.

The automation waits for the explicitly dispatched CI run before requesting merge.
Existing branch protection still applies. If additional required checks or reviews
block the bot, the merge fails and the PR remains available to retry; configure those rules
for the release bot before relying on unattended releases. A workflow-dispatch CI
run does not substitute for every kind of pull-request-required check.

Before publishing, configure the trusted publisher for `@agentlefs/sdk` in npm:

| Field | Value |
| --- | --- |
| Organization or user | `agentleFS` |
| Repository | `agentlefs-sdk-typescript` |
| Workflow filename | `release.yml` |
| Environment | Leave blank |

Update the old `ContextHubApps` publisher in npm; changing package links alone
does not change npm's authentication configuration. The release job uses OIDC
and needs no npm token.

`release.yml` tests and packages the committed SDK snapshot, publishes via npm
OIDC and creates a GitHub Release with the tested tarball. It does not regenerate
from a moving live spec. A real publish requires a stable SDK tag with a trusted
`main` parent and matching committed API release/build/spec-digest metadata.
Branch dispatches can only dry run.

To retry a failed publication, rerun regeneration with the same API release and
build. An existing generated PR is reused, including a PR already merged before
a tagging failure. An existing matching tag resumes publication; mismatched build metadata
fails. An existing npm version is accepted only if its package integrity matches
the newly tested tarball. npm writes use a shared queue that retains up to 100
pending releases. If an older release finishes late, it publishes under `api-X.Y.Z` without moving npm's `latest`
tag backwards. Check the **Release** run for the final npm result; the
regeneration run confirms only that publication was dispatched.

To validate packaging without publishing, dispatch `release.yml` with
`dry_run=true` on the branch to release. A dry run checks the build and tarball;
it does not verify npm's trusted-publisher configuration.

## Local checks

With Bun 1.3.11 and Fern CLI 5.98.3 installed:

```sh
bun run generate
bun run test
cd sdks/typescript
npm install --no-package-lock
npm run build
```

MIT licensed.
