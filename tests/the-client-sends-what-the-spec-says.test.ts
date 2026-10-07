/* The generated client puts each call on the wire the way the spec says: path, method, query
   and the bearer token, and no token on the one public route. Run offline through the
   client's own `fetch` option, so a regeneration that changes a request's shape fails here
   by name instead of in a user's code. */
import { test, expect } from "bun:test";
import { AgentlefsApiClient } from "../sdks/typescript/index.ts";

type Seen = { method: string; url: URL; auth: string | null };

function recorder(body: unknown = {}) {
  const seen: Seen[] = [];
  const fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const headers = new Headers(init?.headers);
    seen.push({ method: init?.method ?? "GET", url: new URL(String(input)), auth: headers.get("authorization") });
    return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
  };
  return { seen, fetch: fetch as typeof globalThis.fetch };
}

test("search is GET /v1/search with the query and the bearer token", async () => {
  const r = recorder({ hits: [] });
  const client = new AgentlefsApiClient({ token: "afs_test", fetch: r.fetch, maxRetries: 0 });
  await client.search({ q: "runbook", limit: 3 });
  expect(r.seen).toHaveLength(1);
  expect(r.seen[0].method).toBe("GET");
  expect(r.seen[0].url.origin + r.seen[0].url.pathname).toBe("https://agentlefs.com/v1/search");
  expect(r.seen[0].url.searchParams.get("q")).toBe("runbook");
  expect(r.seen[0].url.searchParams.get("limit")).toBe("3");
  expect(r.seen[0].auth).toBe("Bearer afs_test");
});

test("listing folders is GET /v1/folders with the bearer token", async () => {
  const r = recorder({ folders: [] });
  const client = new AgentlefsApiClient({ token: "afs_test", fetch: r.fetch, maxRetries: 0 });
  await client.folders.listFolders();
  expect(r.seen.map((s) => `${s.method} ${s.url.pathname}`)).toEqual(["GET /v1/folders"]);
  expect(r.seen[0].auth).toBe("Bearer afs_test");
});

test("baseUrl replaces production, so the client can point at another deployment", async () => {
  const r = recorder({ status: "ok" });
  const client = new AgentlefsApiClient({ baseUrl: "https://dev.agentlefs.com", fetch: r.fetch, maxRetries: 0 });
  await client.service.checkHealth();
  expect(r.seen[0].url.href).toBe("https://dev.agentlefs.com/v1/health");
});

test("health is public: it sends no token, even when the client holds one", async () => {
  const r = recorder({ status: "ok" });
  const client = new AgentlefsApiClient({ token: "afs_test", fetch: r.fetch, maxRetries: 0 });
  const health = await client.service.checkHealth();
  expect(health.status).toBe("ok");
  expect(r.seen[0].auth).toBeNull();
});

test("an authenticated call without a token is refused before anything is sent", async () => {
  const r = recorder();
  const client = new AgentlefsApiClient({ fetch: r.fetch, maxRetries: 0 });
  // HttpResponsePromise is a thenable that expect().rejects does not unwrap, so catch it here.
  const error = await client.search({ q: "x" }).then(() => null, (e: Error) => e);
  expect(error?.message).toContain("token");
  expect(r.seen).toHaveLength(0);
});
