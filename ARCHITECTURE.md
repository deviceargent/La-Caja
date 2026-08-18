# La Caja — Architecture Working Contract

This document is an implementation boundary for the current specification.

## Source of truth

The canonical architecture remains in:

- `docs/La_Caja_v2.0.md`
- `docs/la_caja_v2.1_addendum_troncal.md`

This file does not replace those documents and must not silently resolve their open questions.

## Initial implementation principle

The first implementation should model the architecture as explicit, testable components rather than embedding an LLM inside every Box.

Core roles:

- **Super Index** — global meta-tag to node-location registry.
- **Access Pillar** — mediation endpoint for Super Index lookups.
- **Trunk / Branches** — routing topology.
- **Node** — query-emergent meta-tag cluster and connection endpoint.
- **Box** — local lookup/indexing/filtering/connection layer; no inference.

## Deliberately unresolved

The implementation must not silently decide:

- persistent versus query-scoped nodal cache;
- node-local versus neighborhood cache scope;
- exact intersection-density threshold;
- production transport or storage technology;
- how semantic/ontological tagging is produced beyond the documented boundary.

These are experiments, not hidden defaults.

## First engineering target

Build a minimal in-memory reference implementation capable of demonstrating:

1. meta-tag registration;
2. node creation from a tag-weight profile;
3. repeated-query node identity/relevance behavior;
4. local Box lookup;
5. Super Index-mediated discovery;
6. direct node-to-node connection after discovery;
7. query-relative relevance scoring;
8. explicit separation between routing/indexing and model inference.

No LLM dependency is required for this first layer.
