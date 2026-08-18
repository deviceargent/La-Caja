# Acceso de agentes a La Caja (MCP)

Decision de arquitectura (18/8/2026): como integran los agentes la memoria
de La Caja, y que transportes se soportan.

## Transportes MCP

El spec de MCP define exactamente dos transportes:

- **`stdio`** — LOCAL. El servidor corre como subproceso del agente
  (opencode, Claude Desktop, Cursor, VS Code...). Es la regla para uso en
  maquina propia: `pip install .` y una config de 3 lineas por agente.
- **Streamable HTTP** — REMOTO. POST JSON-RPC sobre HTTP, con respuesta
  JSON o stream SSE y sesion via `Mcp-Session-Id`. Es el UNICO standard
  para MCP remoto (el transporte `HTTP+SSE` separado fue absorbido por
  este en la revision del spec). Para acceso remoto autorizado, OAuth.

No existe otra regla que vigilar: local = stdio, remoto = streamable HTTP.

## Decision de despliegue

- La Caja NO mantiene un servidor MCP publico hosteado.
- `worker/` es un EJEMPLO de host despliegable (Cloudflare Workers, VPS,
  Deno Deploy, etc.) sobre el mismo servidor MCP (un juego de tools, dos
  transportes). Quien quiera acceso remoto despliega el ejemplo y lo
  protege con OAuth.
- La mecanica remota queda documentada aqui; el codigo del worker sirve
  de referencia de como hostear streamable HTTP.

## Patron de integracion para agentes

1. `pip install .` (proyecto instalable, entry point `la-caja-mcp`).
2. Config del agente apunta al comando local (stdio).
3. El agente usa las tools: `procesar_consulta` (ingesta),
   `consultar` (confianza observado/inferido), `contexto_primado`
   (inyeccion de contexto asociativo), `declarar_relacion`,
   `stats`.

## Backward/forward

- El codigo del servidor MCP (`mcp_server.py`) define las tools UNA vez
  y se sirve por ambos transportes (FastMCP `stdio` / `streamable_http`).
  No hay dos implementaciones que mantener en sincronia.
