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
metadata as a snapshot commit, create `vX.Y.Z`, and explicitly dispatch
`release.yml` on that tag. A bot-created tag does not start a push workflow by itself.

The API repository needs `SDK_DISPATCH_TOKEN` with Actions write access to this
repository. Each tested snapshot is committed only under its `vX.Y.Z` tag;
`main` continues to hold the reviewed generator and workflow code. Per-version
queues let separate releases finish without overwriting main or cancelling one
another. The workflow needs contents and Actions write permissions; PR creation
permission is no longer needed. It never force pushes.

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
build. An existing matching tag resumes publication; mismatched build metadata
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
