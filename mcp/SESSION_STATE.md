# La Caja MCP — Session State

## Current branch

`mcp-deliberation-mvp`

## What has been implemented

- Minimal MCP server under `mcp/`.
- SQLite-backed entities and immutable deliberation events.
- Seven initial operations: `get_state`, `get_entity`, `search_context`, `propose`, `challenge`, `update_entity`, `publish_evidence`.
- Entity existence checks and SQLite foreign-key enforcement.
- `get_state` returns the complete event history rather than silently truncating at 50 events.
- `search_context` searches entity metadata and event content.
- Status transitions preserve their history.
- Initial protocol tests under `mcp/tests/test_protocol.py`.
- GitHub Actions workflow added at `.github/workflows/mcp-tests.yml` to install the package and run the protocol tests on pushes to this branch and on pull requests.

## Deliberately NOT implemented yet

- Provider-specific OAuth / authentication for ChatGPT and Claude.
- Public HTTPS deployment / remote MCP transport.
- Final epistemic model (consensus, conditional agreement, candidates, incompatibility).
- Automatic consensus logic.
- Full La Caja architecture.
- Vector search or semantic retrieval.
- Production persistence/deployment concerns beyond the local SQLite MVP.

These are intentionally deferred. Do not silently treat them as solved.

## Current adversarial test targets

1. Proposal can be created and retrieved.
2. Unknown-entity challenge must not create an orphan event.
3. Status transitions preserve proposal/challenge/status history.
4. Invalid statuses are rejected.
5. Search must find event content.
6. State retrieval must not silently drop older events.
7. Next: verify CI execution and use failures as the next source of design corrections.

## Notes for the next agent/session

This project is being developed as an adversarial/collaborative research workspace between independent LLM agents. The server should preserve disagreement and provenance rather than deciding truth. Agents may bring external evidence and proposals between sessions. The architecture is expected to emerge incrementally from actual use.

Last update: added the GitHub Actions CI workflow and recorded the current implementation/deferred work here.
