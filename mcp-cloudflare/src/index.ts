import { McpServer } from "@modelcontextprotocol/server";
import { createMcpHandler } from "agents/mcp/server";
import { z } from "zod";

export interface Env {
  CAJA_STATE: DurableObjectNamespace<CajaState>;
  CHATGPT_TOKEN?: string;
  CLAUDE_TOKEN?: string;
  HUMAN_TOKEN?: string;
}

type Actor = "chatgpt" | "claude" | "human";
type EventKind = "proposal" | "challenge" | "status_change" | "evidence";
type Status = "candidate" | "disputed" | "conditional" | "consensus" | "rejected" | "superseded" | "unresolved";

const ACTORS: Actor[] = ["chatgpt", "claude", "human"];
const STATUSES: Status[] = [
  "candidate",
  "disputed",
  "conditional",
  "consensus",
  "rejected",
  "superseded",
  "unresolved",
];

function actorFromToken(request: Request, env: Env): Actor | null {
  const value = request.headers.get("authorization");
  if (!value?.startsWith("Bearer ")) return null;
  const token = value.slice("Bearer ".length);
  if (env.CHATGPT_TOKEN && token === env.CHATGPT_TOKEN) return "chatgpt";
  if (env.CLAUDE_TOKEN && token === env.CLAUDE_TOKEN) return "claude";
  if (env.HUMAN_TOKEN && token === env.HUMAN_TOKEN) return "human";
  return null;
}

function authError(): Response {
  return new Response("Unauthorized", {
    status: 401,
    headers: { "WWW-Authenticate": "Bearer" },
  });
}

function state(env: Env): DurableObjectStub<CajaState> {
  return env.CAJA_STATE.get(env.CAJA_STATE.idFromName("default-workspace"));
}

function text(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

function createServer(env: Env, actor: Actor) {
  const server = new McpServer({
    name: "La Caja",
    version: "0.2.0",
  });

  server.registerTool(
    "get_state",
    {
      description: "Return the complete research state and immutable deliberation history.",
      inputSchema: {},
    },
    async () => ({
      content: [{ type: "text", text: text(await state(env).execute({ op: "get_state" })) }],
    }),
  );

  server.registerTool(
    "get_entity",
    {
      description: "Return one entity and its complete deliberation history.",
      inputSchema: { entity_id: z.string() },
    },
    async ({ entity_id }) => ({
      content: [{ type: "text", text: text(await state(env).execute({ op: "get_entity", entity_id })) }],
    }),
  );

  server.registerTool(
    "search_context",
    {
      description: "Search entity metadata and deliberation event content.",
      inputSchema: { query: z.string(), limit: z.number().int().min(1).max(100).optional() },
    },
    async ({ query, limit }) => ({
      content: [{ type: "text", text: text(await state(env).execute({ op: "search_context", query, limit: limit ?? 20 })) }],
    }),
  );

  server.registerTool(
    "propose",
    {
      description: "Create a candidate proposal and preserve its originating argument.",
      inputSchema: { title: z.string(), content: z.string(), entity_type: z.string().optional() },
    },
    async ({ title, content, entity_type }) => ({
      content: [{ type: "text", text: text(await state(env).execute({ op: "propose", title, content, entity_type: entity_type ?? "proposal", actor })) }],
    }),
  );

  server.registerTool(
    "challenge",
    {
      description: "Record an adversarial objection without deleting prior reasoning.",
      inputSchema: { entity_id: z.string(), content: z.string(), targets: z.array(z.string()).optional() },
    },
    async ({ entity_id, content, targets }) => ({
      content: [{ type: "text", text: text(await state(env).execute({ op: "challenge", entity_id, content, targets: targets ?? [], actor })) }],
    }),
  );

  server.registerTool(
    "update_entity",
    {
      description: "Change an entity status while preserving the reason as an immutable event.",
      inputSchema: { entity_id: z.string(), status: z.enum(STATUSES), content: z.string() },
    },
    async ({ entity_id, status, content }) => ({
      content: [{ type: "text", text: text(await state(env).execute({ op: "update_entity", entity_id, status, content, actor })) }],
    }),
  );

  server.registerTool(
    "publish_evidence",
    {
      description: "Attach externally researched evidence to an entity.",
      inputSchema: { entity_id: z.string(), source: z.string(), claim: z.string(), notes: z.string().optional() },
    },
    async ({ entity_id, source, claim, notes }) => ({
      content: [{ type: "text", text: text(await state(env).execute({ op: "publish_evidence", entity_id, source, claim, notes: notes ?? "", actor })) }],
    }),
  );

  return server;
}

export class CajaState extends DurableObject<Env> {
  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    this.ctx.storage.sql.exec(`
      CREATE TABLE IF NOT EXISTS entities (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      )
    `);
    this.ctx.storage.sql.exec(`
      CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        entity_id TEXT NOT NULL,
        actor TEXT NOT NULL,
        kind TEXT NOT NULL,
        content TEXT NOT NULL,
        metadata TEXT NOT NULL,
        created_at TEXT NOT NULL
      )
    `);
  }

  async execute(command: Record<string, unknown>): Promise<Record<string, unknown>> {
    const op = command.op;
    const now = new Date().toISOString();

    if (op === "get_state") {
      return {
        entities: this.ctx.storage.sql.exec("SELECT * FROM entities ORDER BY updated_at DESC").toArray(),
        events: this.ctx.storage.sql.exec("SELECT * FROM events ORDER BY created_at ASC").toArray(),
      };
    }

    if (op === "get_entity") {
      const entityId = String(command.entity_id ?? "");
      const entity = this.ctx.storage.sql.exec("SELECT * FROM entities WHERE id = ?", entityId).toArray();
      const history = this.ctx.storage.sql.exec("SELECT * FROM events WHERE entity_id = ? ORDER BY created_at ASC", entityId).toArray();
      if (!entity.length) return { error: "entity_not_found", entity_id: entityId };
      return { entity: entity[0], history };
    }

    if (op === "search_context") {
      const query = String(command.query ?? "");
      const limit = Math.min(Math.max(Number(command.limit ?? 20), 1), 100);
      const pattern = `%${query}%`;
      return {
        query,
        entities: this.ctx.storage.sql.exec(
          "SELECT * FROM entities WHERE title LIKE ? OR type LIKE ? ORDER BY updated_at DESC LIMIT ?",
          pattern, pattern, limit,
        ).toArray(),
        events: this.ctx.storage.sql.exec(
          "SELECT * FROM events WHERE content LIKE ? OR kind LIKE ? OR actor LIKE ? ORDER BY created_at DESC LIMIT ?",
          pattern, pattern, pattern, limit,
        ).toArray(),
      };
    }

    if (op === "propose") {
      const id = crypto.randomUUID();
      const type = String(command.entity_type ?? "proposal");
      const title = String(command.title ?? "");
      const content = String(command.content ?? "");
      const actor = String(command.actor ?? "unknown");
      this.ctx.storage.sql.exec(
        "INSERT INTO entities (id,type,title,status,created_at,updated_at) VALUES (?,?,?,?,?,?)",
        id, type, title, "candidate", now, now,
      );
      const event = this.insertEvent(id, actor, "proposal", content, "{}");
      return { entity: { id, type, title, status: "candidate" }, event };
    }

    const entityId = String(command.entity_id ?? "");
    const exists = this.ctx.storage.sql.exec("SELECT id FROM entities WHERE id = ?", entityId).toArray();
    if (!exists.length) return { error: "entity_not_found", entity_id: entityId };

    if (op === "challenge") {
      return this.insertEvent(
        entityId,
        String(command.actor ?? "unknown"),
        "challenge",
        String(command.content ?? ""),
        JSON.stringify({ targets: Array.isArray(command.targets) ? command.targets : [] }),
      );
    }

    if (op === "update_entity") {
      const status = String(command.status ?? "");
      if (!STATUSES.includes(status as Status)) return { error: "invalid_status", allowed: STATUSES };
      this.ctx.storage.sql.exec("UPDATE entities SET status = ?, updated_at = ? WHERE id = ?", status, now, entityId);
      return this.insertEvent(
        entityId,
        String(command.actor ?? "unknown"),
        "status_change",
        String(command.content ?? ""),
        JSON.stringify({ status }),
      );
    }

    if (op === "publish_evidence") {
      return this.insertEvent(
        entityId,
        String(command.actor ?? "unknown"),
        "evidence",
        String(command.claim ?? ""),
        JSON.stringify({ source: String(command.source ?? ""), notes: String(command.notes ?? "") }),
      );
    }

    return { error: "unknown_operation", operation: op };
  }

  private insertEvent(entityId: string, actor: string, kind: EventKind, content: string, metadata: string) {
    const id = crypto.randomUUID();
    const createdAt = new Date().toISOString();
    this.ctx.storage.sql.exec(
      "INSERT INTO events (id,entity_id,actor,kind,content,metadata,created_at) VALUES (?,?,?,?,?,?,?)",
      id, entityId, actor, kind, content, metadata, createdAt,
    );
    this.ctx.storage.sql.exec("UPDATE entities SET updated_at = ? WHERE id = ?", createdAt, entityId);
    return { id, entity_id: entityId, actor, kind, content, metadata, created_at: createdAt };
  }
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext) {
    if (new URL(request.url).pathname === "/health") {
      return Response.json({ ok: true, service: "la-caja-mcp" });
    }

    const actor = actorFromToken(request, env);
    if (!actor || !ACTORS.includes(actor)) return authError();

    return createMcpHandler(() => createServer(env, actor))(request, env, ctx);
  },
} satisfies ExportedHandler<Env>;
