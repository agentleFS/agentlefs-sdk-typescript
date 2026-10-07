#!/usr/bin/env bun
// Write the generated SDK's package.json and tsconfig.json.
//
// ── WHY THIS SCRIPT EXISTS ───────────────────────────────────────────────────
// The Fern TypeScript generator should own these files, and it does emit them when it is
// given package metadata via a `config:` block in generators.yml. It cannot be, because on
// generator 3.88.0 ANY `config:` block makes generation silently write ZERO files while the
// CLI still prints "Wrote files" and exits 0. 3.88.0 is the newest tag published, so there
// is no version to upgrade to.
//
// Without a package.json the generated tree is not installable at all: no name, no version,
// no entry points. So this writes the minimum that makes it a real package, and nothing
// more, so that deleting this script is the whole of the cleanup once the generator bug is
// fixed.
//
// Run by `bun run generate`, so it is impossible to regenerate and forget it.
//
// ── WHAT IS DELIBERATELY NOT HERE ────────────────────────────────────────────
// No dependencies. The generated client imports nothing outside itself, verified by
// grepping every bare import specifier in the tree and finding none: it uses the platform
// fetch and no node builtins. A dependency block would be fiction, and fiction in a
// manifest becomes someone's install failure.

import { join } from "node:path";

const SDK_DIR = join(import.meta.dir, "..", "sdks", "typescript");

/**
 * The published version, from the environment so a release workflow owns it and this file
 * does not have to be edited to cut a release.
 *
 * 0.0.0-dev is a deliberate placeholder rather than 1.0.0: a local build should never
 * accidentally look like a real release, and npm treats a prerelease tag as not-latest.
 */
const version = process.env.SDK_VERSION ?? "0.0.0-dev";

const packageJson = {
  name: "@agentlefs/sdk",
  version,
  description: "Official TypeScript SDK for the agentleFS REST API.",
  license: "MIT",
  repository: {
    type: "git",
    url: "git+https://github.com/agentleFS/agentlefs-sdk-typescript.git",
  },
  homepage: "https://agentlefs.com",
  keywords: ["agentlefs", "sdk", "api-client", "openapi"],
  // Dual CJS/ESM, matching what the generated code is written for: source uses ESM with
  // explicit .js specifiers, which tsc emits correctly for both module systems.
  //
  // This makes Node treat every .js in the package as ESM, INCLUDING the CommonJS build that
  // `main` points at. dist/cjs therefore needs its own package.json declaring
  // {"type":"commonjs"} to opt that subtree back out; the `build` script below writes it.
  // Shipped 0.2.0 without it, and `require("@agentlefs/sdk")` died on "Cannot find module
  // './api/index.js'": Node parsed the CJS output as ESM, so its require() calls resolved as
  // bare ESM specifiers. ESM consumers were unaffected, which is why the tarball checks
  // (which only assert files exist) passed.
  type: "module",
  main: "./dist/cjs/index.js",
  module: "./dist/esm/index.js",
  types: "./dist/esm/index.d.ts",
  exports: {
    ".": {
      types: "./dist/esm/index.d.ts",
      import: "./dist/esm/index.js",
      require: "./dist/cjs/index.js",
    },
  },
  // Only build output and docs. Shipping the .ts sources would double the install size for
  // no benefit, since types come from the .d.ts files.
  files: ["dist", "README.md", "LICENSE"],
  scripts: {
    // The third step is load-bearing, not tidying: it stamps {"type":"commonjs"} into
    // dist/cjs so Node stops reading that subtree as ESM. It runs here rather than in
    // write-package-json.ts because dist/cjs does not exist until tsc creates it.
    build:
      "tsc -p tsconfig.esm.json && tsc -p tsconfig.cjs.json && node -e \"require('fs').writeFileSync('dist/cjs/package.json', JSON.stringify({type:'commonjs'}) + '\\n')\"",
  },
  devDependencies: {
    // @types/node is required, not optional: the generated error classes call
    // Error.captureStackTrace, which is a V8/Node API absent from the default lib. Without
    // it tsc emits output but reports TS2339 on every error class.
    "@types/node": "^22.0.0",
    typescript: "^5.7.0",
  },
  // The floor is set by native fetch, which the generated core relies on. Node 18 shipped
  // it unflagged; anything older would fail at runtime rather than at install.
  engines: {
    node: ">=18.0.0",
  },
  sideEffects: false,
} as const;

const tsconfigBase = {
  compilerOptions: {
    target: "ES2022",
    // DOM.Iterable is required, not cosmetic: the generated fetcher calls
    // Headers.entries(), which only exists in the iterable DOM lib. Without it tsc reports
    // TS2339 on every header-copying site.
    lib: ["ES2022", "DOM", "DOM.Iterable"],
    // Node types for Error.captureStackTrace in the generated error classes.
    types: ["node"],
    moduleResolution: "node",
    strict: true,
    // The generated code writes `export * as X from "./y.js"`, so the emitted JS must keep
    // those specifiers verbatim rather than rewriting them.
    esModuleInterop: true,
    skipLibCheck: true,
    declaration: true,
    sourceMap: true,
    rootDir: ".",
  },
  include: ["**/*.ts"],
  exclude: ["node_modules", "dist", "**/*.test.ts"],
};

const tsconfigEsm = {
  ...tsconfigBase,
  compilerOptions: { ...tsconfigBase.compilerOptions, module: "ES2022", outDir: "./dist/esm" },
};

const tsconfigCjs = {
  ...tsconfigBase,
  compilerOptions: {
    ...tsconfigBase.compilerOptions,
    module: "CommonJS",
    outDir: "./dist/cjs",
    // CJS output needs its own declaration set, or the two builds fight over .d.ts files.
    declaration: true,
  },
};

const readme = `# @agentlefs/sdk

Official TypeScript SDK for the [agentleFS](https://agentlefs.com) REST API.

> Generated from agentleFS's OpenAPI spec. Do not edit by hand: see the
> [SDK repository](https://github.com/agentleFS/agentlefs-sdk-typescript) for how it is
> produced.

## Install

\`\`\`bash
npm install @agentlefs/sdk
\`\`\`

## Usage

\`\`\`ts
import { AgentlefsApiClient } from "@agentlefs/sdk";

const client = new AgentlefsApiClient({ token: process.env.AGENTLEFS_API_KEY! });

// List what your key can reach
const folders = await client.folders.listFolders();

// Read a document
const doc = await client.documents.retrieveDocument({
  location: "handbook/onboarding/day-one.md",
});
\`\`\`

API keys are minted in the agentleFS console: **Access**, open a principal, **Tokens**,
**Mint**, with *enable for the REST API* ticked. Keys are long-lived and do not expire;
revoke them in the console when they should stop working.

## A 404 does not mean you got the path wrong

If your key is not permitted to read something, the API returns \`404\` with exactly the
response it would give for something that does not exist. The two are byte-identical, on
purpose: if they differed, any key holder could map content they cannot read by watching
which paths answer differently.

So there is no \`403\` on this API and no error meaning "forbidden". A surprising \`404\` is a
question about **grants**, not about your path.

## Writing safely

Two headers exist so a retry or a race cannot cost you data, and the SDK surfaces both:

- **Creating** takes an idempotency key, so a retry after a network failure cannot produce a
  duplicate document.
- **Updating and deleting** take the \`ETag\` from a read, so a concurrent edit is refused
  rather than silently overwritten.

## Reference

- Full API reference: [\`docs/api.md\`](https://github.com/agentleFS/agentlefs-sdk-typescript)
- Machine-readable contract: <https://agentlefs.com/v1/openapi.yaml>

## License

MIT
`;

await Bun.write(join(SDK_DIR, "package.json"), JSON.stringify(packageJson, null, 2) + "\n");
await Bun.write(join(SDK_DIR, "tsconfig.esm.json"), JSON.stringify(tsconfigEsm, null, 2) + "\n");
await Bun.write(join(SDK_DIR, "tsconfig.cjs.json"), JSON.stringify(tsconfigCjs, null, 2) + "\n");
await Bun.write(join(SDK_DIR, "README.md"), readme);

// The published package must carry the licence it claims.
const license = await Bun.file(join(import.meta.dir, "..", "LICENSE")).text();
await Bun.write(join(SDK_DIR, "LICENSE"), license);

console.log(`wrote package.json (@agentlefs/sdk@${version}), tsconfigs, README, LICENSE`);
