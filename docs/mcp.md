# MCP server (Claude)

How Claude drives PhotoEditor (Phase 7). The code is in `src/photoedit/mcp/`. The tools are thin: each one turns its
arguments into a core call and the result into structured output, an image or a short text, like the HTTP routes.

## Where it runs

Inside the `photoedit ui` server, at **`http://127.0.0.1:8765/mcp`** (MCP Streamable HTTP; decided 2026-10-15,
PLAN.md §0). The AI and the web UI share one set of services: the catalog, the caches, the job queue (one export at
a time) and, from P7.8, the change events the UI follows. So `photoedit ui` must be running when a Claude Code
session starts; otherwise Claude Code lists the server as failed until you start it and reconnect in `/mcp`.

## SDK notes (P7.2 spike, `mcp` 2.3.0)

- `FastMCP` from SDK 1.x is **`MCPServer`** in 2.x (`from mcp.server.mcpserver import MCPServer, Image`).
- **Mounting**: `server.streamable_http_app(streamable_http_path="/mcp", host=...)` returns a Starlette app with a
  single route; its routes are added to the FastAPI app **before** the UI's catch-all `GET /{path}` route (the MCP
  stream's `GET` would otherwise get the UI's HTML). The route isn't an `APIRoute`, so OpenAPI is unchanged.
  `server.session_manager.run()` must wrap the app's lifespan; a server's session manager runs once, so every app
  builds its own server.
- **Transport security**: for host `127.0.0.1`/`localhost`/`::1` the SDK checks the `Host` and `Origin` headers by
  default (allowed: those hosts on any port). A request from a web page on another origin gets **403**, so a page
  can't reach the tools through DNS rebinding. (A non-local `host` in the config turns the check off.)
- **Tools** are typed Python functions; the input schema comes from the signature (Pydantic `Field` ranges are
  in it), the description from the docstring. A function returning a Pydantic model gets an output schema and
  `structuredContent` (plus the same JSON as text). Returning `Image(data=..., format="jpeg")` gives an image block.
  Sync functions run in a worker thread, so blocking core calls don't stall the server.
- **Errors**: arguments that fail the input schema come back as a tool error (`isError: true`) with Pydantic's
  message. Inside a tool, only `ToolError` keeps its message; **any other exception reaches the model as just
  "Error executing tool …"**. So every tool goes through `_core_errors`, which turns the core's `NotFoundError`,
  `InvalidRequestError` (and `ConflictError`), `WriteNotAllowedError` and Pydantic `ValidationError` into
  `ToolError`s with their message.
- **Testing**: `mcp.Client(server)` connects in-process (no transport), `mcp.Client("http://…/mcp")` over HTTP.
  `tests/test_mcp_server.py` does both: the HTTP test runs the whole app under uvicorn on a free port.

## Tools

| Tool | What it does |
|---|---|
| `ping` | Version and the open folder's photo count. |
| `render_preview(photo_id, size=1024)` | The photo with its current edit as a JPEG (256–1600 px long edge). |

The rest of the tool list follows in P7.10–P7.13.
