La Caja
A Graph-Based Contextual Memory Architecture for Large Language Models
Version 2.0  ·  Public Domain  ·  Free to implement and extend


Abstract
Current large language model (LLM) deployments handle inter-session memory through primitive mechanisms: raw text injection, lossy summarization, or hard truncation. These approaches treat context as a flat buffer rather than a navigable structure, resulting in high token overhead, loss of relational information, and inability to traverse prior states without contaminating the active context window.
This document describes La Caja, a graph-based memory architecture designed to address these limitations. La Caja organizes persistent knowledge into a weighted, hierarchical graph of query-emergent nodes, each managed by a lightweight indexing agent — the box (caja) — capable of preparing virtual context, routing inter-node queries, and strengthening connection weights through use. The system is designed for increasing efficiency over time, emergent connectivity, and relevance-weighted retrieval without backpropagation or decay mechanisms.

1. Problem Statement
Memory management in LLMs presents a structural tension: models are stateless between sessions, yet meaningful interaction often requires access to prior context. Current mitigation strategies include:
1. Injection: prepending prior conversation text into the active context. Cost is linear in context size; relational structure is lost.
1. Summarization: compressing prior sessions into natural language summaries. Lossy by design; introduces hallucination risk in the compression step.
1. Retrieval-Augmented Generation (RAG): embedding-based similarity search over stored chunks. Retrieves content, not structure; no mechanism for traversal or context priming.
None of these approaches support navigation — the ability to momentarily inhabit a prior context state, extract relevant information, and return to the active context without merging the two. La Caja is designed around navigation as a first-class operation.

2. Architecture Overview
La Caja can be understood as a directed, weighted graph with five structural layers:
1. Super Index (global meta-tag registry)
1. Access Pillars (index query endpoints)
1. Trunk and Branches (primary routing tree)
1. Nodes (query-emergent meta-tag clusters)
1. Boxes (node agents, filters, and inter-node connectors)
These layers are not independent services — they are roles within a single coherent system. The system fails to achieve efficiency if any layer is absent or decoupled from the others. This interdependence is the defining property of La Caja as a whole.
A key behavioral property: the system becomes more efficient over time, not more costly. As nodes accumulate direct inter-connections, the proportion of queries requiring Super Index consultation decreases. Routing progressively shifts from centralized lookup to distributed direct connection.

3. Component Specification
3.1 Super Index
The Super Index is the global registry of the system. It does not store node content — it stores meta-tag-to-location bindings. Each entry maps a meta-tag identifier to one or more node coordinates within the graph.
New meta-tags are ingested with minimal overhead: assignment of a serial identifier, a coordinate, and insertion into a sorted structure. The ordering scheme — alphabetic, hash-based, or otherwise — is an implementation detail optimized for lookup speed. Semantic organization is not required at this layer.
Key properties:
1. Singleton: one Super Index per system instance.
1. Location-only: stores coordinates, never content.
1. Decreasing load over time: as nodes form direct connections, queries bypass the Super Index entirely. The index is consulted primarily for new nodes and new meta-tags, both of which are structurally infrequent — language and concepts do not expand arbitrarily.
1. Write operations occur only during consolidation after node processing periods. Read operations are the dominant access pattern.
3.2 Access Pillars
Access Pillars are lightweight query endpoints positioned at the periphery of the system topology. Their sole function is to mediate between individual node boxes and the Super Index, preventing direct high-frequency access to the central trunk.
The number of Access Pillars is initially fixed but scales with query throughput. Because their operation is limited to tag-based query routing — no content storage, no semantic processing — their footprint remains small regardless of system scale.
Latency note: each query carries its own lifecycle. The system does not optimize for minimum response time at the cost of connection richness. Latency is a controlled variable, not a failure mode.
3.3 Trunk and Branch Structure
The primary routing tree consists of a central trunk and a set of primary branches representing major thematic domains. Branch weight increases with traversal frequency through kinetic reinforcement — paths strengthen proportionally to use, without explicit weight update mechanisms.
Nodes are not appended externally to the tree. They emerge from within it, growing outward from established branch points. This inside-out generation ensures that new nodes inherit topological context from their origin and are immediately reachable through existing branch paths.
3.4 Nodes
Nodes are not pre-defined knowledge containers. They are the structural precipitate of queries: each node is generated by a unique combination of meta-tag weights produced by a box during query processing. Node identity is query identity.
This has two important consequences:
1. Topical specificity emerges naturally. No enforcement mechanism is required — a node's scope is defined by the query that created it.
1. Redundancy is self-eliminating. If a subsequent query produces an identical meta-tag weight profile, the existing node gains relevance weight rather than generating a duplicate.
Nodes begin with minimal connections and grow through use. A node created for a low-profile entity at any point in time starts with few associated meta-tags and weak connections. As queries accumulate additional associations, the node's density and connection weight increase accordingly. Historical weight does not suppress new nodes — retrieval priority is determined by match quality against the incoming query, not by absolute accumulated weight.
3.4.1 Node overlap and virtual intersection
When two nodes share a subset of meta-tags without being identical, they form a partial overlap — a Venn-diagram relationship. This overlap is not materialized as a separate structural entity at the index level. It is registered by both boxes as a bidirectional connection. The overlapping region can be treated as a virtual intersection: both nodes remain independent, but queries that match the shared tag subset may activate both.
When the shared subset is sufficiently dense, the boxes may instruct their respective nodes to generate a third, emergent node representing the intersection explicitly. This emergent node is a full node: it has its own box, its own index, and grows independently through subsequent queries.
3.4.2 Hierarchical origin without fixed hierarchy
Nodes inherit topological position from their origin branch. A node generated under a broad domain branch (e.g., philosophy) begins as a structural descendant of that domain. However, this inheritance is positional, not weight-based. Through accumulated queries and associations, a descendant node can surpass its ancestor in connection density and retrieval priority. The graph is not a fixed taxonomy — it is a dynamic topology shaped by use.
3.5 The Box
The box is the agent layer of each node. It is simultaneously the node's internal indexing assistant and its interface to the rest of the system. The name La Caja refers to the system as a whole precisely because the box is the component without which no other layer achieves its function.
3.5.1 Ontological filtering
Not all terms in a query carry semantic weight sufficient to justify node connection. Functional language elements — prepositions, conjunctions, articles, minor symbols — are registered by the box but not transmitted to the node as connection candidates. Only terms with autonomous ontological weight — entities, concepts, proper names, domain terms — are forwarded.
This filter is static. The category of weight-less terms is structurally stable: functional language elements do not acquire ontological weight over time. A symbol or particle that lacks topic-level meaning at system initialization will not acquire it through use. Terms that gain new meaning do so as new named entities, which are indexed independently from their inception.
3.5.2 Local indexing and non-volatile cache
As information is processed into a node, the box indexes it with meta-tags. This cost is paid once and consolidated into the local index. The box maintains a non-volatile cache of previously resolved connections and query patterns. Subsequent queries against known patterns are resolved locally without Super Index consultation — analogous to DNS name resolution caching.
The box index is bounded: it grows as a lookup structure, not as a content store. It cannot and does not substitute for the node's full connection graph.
3.5.3 Context priming
Before full content retrieval occurs, the box prepares a virtual context: activating relevant connection pathways without loading content. The computational cost of this operation is bounded by the grammatical weight analysis of the incoming query — a syntactic-level operation with negligible overhead. No semantic processing occurs at this stage.
3.5.4 Inter-node negotiation and connection formation
When a box detects that an incoming query carries meta-tags associated with a remote node, it initiates a negotiation protocol:
1. The local box queries the Super Index via an Access Pillar for the coordinates of the remote node.
1. The local box contacts the remote box and exchanges index summaries.
1. Both boxes identify coincident meta-tags and assess overlap weight.
1. If overlap is sufficient, each box instructs its node to form a direct connection with the other.
1. The remote box confirms the connection to the Super Index. If the Super Index records a prior registration of the same connection by another box, the remote box consolidates it into its local cache. If not, no action is taken.
Once a direct connection exists between two nodes, subsequent queries that activate both can route between them without Super Index involvement. The system progressively replaces index-mediated routing with direct node-to-node routing.
3.5.5 Query weight analysis and conversation agenda
Incoming queries carry an implicit weight distribution across their meta-tags, derived through grammatical analysis at the syntactic level. The box uses this distribution to determine which connections to prime and in what priority order.
Once a query has been indexed and its tag weights resolved, the interaction acquires an independent agenda: a structured set of topics and connection priorities that can be carried across node traversals along primary branches. This allows multi-node interactions to maintain coherent context without re-resolving the Super Index at each traversal step.
3.5.6 Relevance ranking
The box maintains a count of queries directed at its node and can consult the Super Index for comparative query counts across related nodes. Retrieval priority within a query is determined not by absolute accumulated weight but by coincidence density between the query's meta-tag profile and the node's index. A recently created node with high tag-match specificity will outrank a historically dense node with low match specificity for that query. Historical weight and current relevance are independent dimensions.

4. Emergent Intersection Nodes
When two non-adjacent nodes exchange index summaries and identify a sufficiently dense shared meta-tag subset, their boxes may cooperatively generate a third node representing the intersection. This emergent node:
1. Is a full structural node with its own box, index, and connection capacity.
1. Is initialized with the shared meta-tag subset as its founding index.
1. Grows independently through subsequent queries that match its profile.
1. Does not require either parent node to be aware of the other's full index — only the shared subset is exchanged.
This mechanism replaces the concept of pre-defined pool structures. There are no shortcut paths added to the graph — there are only new nodes that emerge where query patterns justify them. The graph topology is entirely query-driven.
The distinction between primary branches and emergent intersection nodes mirrors the distinction between major transit infrastructure and locally known routes. Both are necessary; neither is redundant. Primary branches handle volume and predictability; emergent nodes handle specificity and cross-domain convergence.

5. Kinetic Reinforcement and Relevance
La Caja does not use gradient-based learning, explicit weight updates, or decay mechanisms. Reinforcement is kinetic: structural weights increase as a direct consequence of traversal. No learning signal is required. No maintenance pass is needed to prevent relevance drift.
Relevance drift — the risk that historically dense nodes suppress newer, more contextually appropriate nodes — does not occur in La Caja because retrieval priority is query-relative, not globally ranked. A node's accumulated weight does not grant it priority over a node with higher tag-match specificity for the active query. The two dimensions are independent.
New nodes are not disadvantaged at birth. By the time a new node is created, its parent branch already exists and carries weight. The new node is immediately reachable through existing topology and begins accumulating connections from its first query.
Reinforcement summary:
1. Node connection density: increases with query frequency and inter-box negotiation outcomes.
1. Branch weight: increases with traversal frequency.
1. Emergent node generation: triggered by inter-box negotiation when shared meta-tag density crosses operational threshold.
1. No decay mechanism is specified. Decay policy is left to implementation. The architecture does not require it for correctness.

6. Context Isolation
A central design objective of La Caja is navigation without contamination: the ability to traverse a prior context state and return to the active context without the two states merging.
This property is structurally supported by the inter-box negotiation mechanism. Before any traversal occurs, boxes exchange index summaries and assess coincidence weight. Communication is only established between nodes with high tag-match overlap. A node from an unrelated domain does not enter the active context because the box filter prevents the connection from forming in the first place.
The risk of inference-level state leakage — where the underlying model retains associative activations from a traversed node — is a property of the model, not of La Caja. However, La Caja's pre-traversal filtering mitigates this risk structurally: traversal only occurs to nodes with demonstrated relevance to the active query. Speculative traversal does not occur.

7. Formal Properties
7.1 Scalability
1. Super Index: scales with the number of distinct meta-tags, not with node content volume. Meta-tag space is bounded — language and concepts do not expand arbitrarily. Index consolidation is a batch operation with decreasing frequency as the system matures.
1. Access Pillars: scale with query throughput. Stateless with respect to content; horizontal scaling is straightforward.
1. Nodes: scale independently. Node connection density growth does not affect system-wide index performance.
1. Boxes: fixed overhead per node. No cross-box state is maintained outside of registered connections. Load decreases as direct node connections replace index-mediated routing.
7.2 Separation of concerns
1. Super Index: meta-tag-to-location registry.
1. Access Pillars: index query mediation.
1. Trunk / Branches: topological routing structure.
1. Nodes: query-emergent meta-tag clusters and connection endpoints.
1. Boxes: ontological filtering, local indexing, caching, priming, inter-node negotiation, and relevance ranking.
No component requires knowledge of the full system to perform its function.
7.3 Efficiency trajectory
The system is designed to become more efficient over time, not less. At initialization, most routing passes through the Super Index. As nodes accumulate direct connections, an increasing proportion of queries are resolved through direct node-to-node routing. The Super Index load decreases monotonically relative to total query volume as the system matures.
7.4 Complexity characteristics
1. Super Index lookup: O(log n), where n is the number of distinct meta-tags.
1. Box query resolution (cached): O(1) for previously resolved patterns.
1. Box query resolution (uncached): O(log n) via Access Pillar.
1. Inter-box negotiation: O(k) where k is the size of the exchanged index summaries.
1. Direct node-to-node routing (established connection): O(1).
1. Kinetic reinforcement: O(1) per traversal.

8. Glossary
Node  —  A query-emergent meta-tag cluster. Generated by a unique combination of meta-tag weights. Grows through accumulated queries and inter-box negotiation.
Box (Caja)  —  The agent layer of a node. Responsible for ontological filtering, local indexing, non-volatile caching, context priming, inter-node negotiation, connection formation, and relevance ranking.
Super Index  —  The global meta-tag registry. Maps tag identifiers to node coordinates. Does not store content. Load decreases as direct node connections proliferate.
Access Pillar  —  A lightweight query endpoint mediating between node boxes and the Super Index.
Trunk  —  The central routing axis of the primary branch tree.
Branch  —  A primary thematic routing path. Weight increases with traversal frequency through kinetic reinforcement.
Emergent intersection node  —  A node generated cooperatively by two boxes when their shared meta-tag subset reaches sufficient density. A full structural node, not a shortcut.
Meta-tag  —  A structured label assigned to information during indexing. The atomic unit of the Super Index. Ontologically weighted terms only — functional language elements are filtered.
Ontological filter  —  The box mechanism that distinguishes semantically weighted terms from functional language elements. Static; does not require updates over system lifetime.
Kinetic reinforcement  —  Weight increase through traversal, without explicit learning signal or optimization objective.
Context priming  —  Activation of connection pathways prior to full content retrieval. Syntactic-level operation; negligible computational cost.
Conversation agenda  —  The structured topic and priority set carried by a query across multi-node traversals, derived from initial box weight analysis.
Virtual context  —  A primed but unloaded state — pathways activated, content not yet retrieved.
Virtual intersection  —  The implicit shared region between two overlapping nodes, registered as a bidirectional connection in both boxes without requiring a dedicated structural node.

La Caja · Version 2.0 · Public Domain
This document may be freely copied, implemented, extended, or cited without restriction.