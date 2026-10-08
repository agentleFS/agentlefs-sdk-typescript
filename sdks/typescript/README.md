# @agentlefs/sdk

Official TypeScript SDK for the [agentleFS](https://agentlefs.com) REST API.

> Generated from agentleFS's OpenAPI spec. Do not edit by hand: see the
> [SDK repository](https://github.com/agentleFS/agentlefs-sdk-typescript) for how it is
> produced.

## Install

```bash
npm install @agentlefs/sdk
```

## Usage

```ts
import { AgentlefsApiClient } from "@agentlefs/sdk";

const client = new AgentlefsApiClient({ token: process.env.AGENTLEFS_API_KEY! });

// List what your key can reach
const folders = await client.folders.listFolders();

// Read a document
const doc = await client.documents.retrieveDocument({
  location: "handbook/onboarding/day-one.md",
});
```

API keys are minted in the agentleFS console: **Access**, open a principal, **Tokens**,
**Mint**, with *enable for the REST API* ticked. Keys are long-lived and do not expire;
revoke them in the console when they should stop working.

## A 404 does not mean you got the path wrong

If your key is not permitted to read something, the API returns `404` with exactly the
response it would give for something that does not exist. The two are byte-identical, on
purpose: if they differed, any key holder could map content they cannot read by watching
which paths answer differently.

So there is no `403` on this API and no error meaning "forbidden". A surprising `404` is a
question about **grants**, not about your path.

## Writing safely

Two headers exist so a retry or a race cannot cost you data, and the SDK surfaces both:

- **Creating** takes an idempotency key, so a retry after a network failure cannot produce a
  duplicate document.
- **Updating and deleting** take the `ETag` from a read, so a concurrent edit is refused
  rather than silently overwritten.

## Reference

- Full API reference: [`docs/api.md`](https://github.com/agentleFS/agentlefs-sdk-typescript)
- Machine-readable contract: <https://agentlefs.com/v1/openapi.yaml>

## License

MIT
