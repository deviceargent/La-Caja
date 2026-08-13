import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const pkg = JSON.parse(await readFile(new URL("../package.json", import.meta.url)));
const wrangler = await readFile(new URL("../wrangler.jsonc", import.meta.url), "utf8");
const source = await readFile(new URL("../src/index.ts", import.meta.url), "utf8");

test("Cloudflare package uses MCP SDK v2", () => {
  assert.equal(pkg.dependencies["@modelcontextprotocol/server"], "2.0.0");
});

test("Worker declares a SQLite Durable Object", () => {
  assert.match(wrangler, /\"class_name\": \"CajaState\"/);
  assert.match(wrangler, /\"storage\": \"sqlite\"/);
});

test("all seven La Caja operations are registered", () => {
  for (const name of [
    "get_state",
    "get_entity",
    "search_context",
    "propose",
    "challenge",
    "update_entity",
    "publish_evidence",
  ]) {
    assert.match(source, new RegExp(`\\"${name}\\"`));
  }
});

test("remote endpoint requires bearer authentication", () => {
  assert.match(source, /Authorization/);
  assert.match(source, /Bearer/);
});
