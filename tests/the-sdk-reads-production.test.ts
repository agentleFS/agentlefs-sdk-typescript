/* The SDK as published talks to production, unmocked. Health needs no credential, so it always
   runs; EXPECT_BUILD (the commit a release promoted) makes it prove the regeneration read the
   release it was asked for, not the one before. AGENTLEFS_TOKEN, when set, adds an
   authenticated read. AGENTLEFS_BASE_URL points it at another deployment. */
import { test, expect } from "bun:test";
import { AgentlefsApiClient } from "../sdks/typescript/index.ts";

const baseUrl = process.env.AGENTLEFS_BASE_URL || undefined;
const token = process.env.AGENTLEFS_TOKEN || undefined;
const expectBuild = process.env.EXPECT_BUILD || undefined;

test("production answers health through the SDK", async () => {
  const client = new AgentlefsApiClient({ baseUrl });
  const health = (await client.service.checkHealth()) as { status?: string; build?: string };
  expect(health.status).toBe("ok");
  if (expectBuild) expect(health.build).toBe(expectBuild);
});

test.skipIf(!token)("an authenticated read succeeds with AGENTLEFS_TOKEN", async () => {
  const client = new AgentlefsApiClient({ baseUrl, token });
  const folders = await client.folders.listFolders({ limit: 1 });
  expect(folders).toBeDefined();
});
