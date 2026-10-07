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

Production promotion in `agentleFS/proof-of-concept-2` waits for the deployed build
and dispatches `regenerate.yml` here with the release and commit. That workflow
regenerates, tests, compiles and opens a PR when the SDK changes. Review the public
API diff before merging; regeneration does not publish automatically.

The API repository needs `SDK_DISPATCH_TOKEN` with Actions write access to this
repository. In this repository's Settings → Actions → General, enable **Allow
GitHub Actions to create and approve pull requests**. The regeneration workflow
requests contents and pull-request write permissions.

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

After the regenerated SDK is merged and CI passes, push a `vX.Y.Z` tag on that
commit. `release.yml` derives the package version from the tag, checks the SDK
against production, runs tests, builds and verifies both CJS and ESM tarball entry
points, then publishes and creates a GitHub Release. For the catch-up release,
use `v0.4.0` after confirming it has not already been published.

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
