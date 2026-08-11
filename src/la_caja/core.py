"""Small, dependency-free reference primitives for La Caja.

This module intentionally models routing/indexing mechanics only. It does not
perform semantic inference and does not choose the unresolved cache policy.
"""

from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Optional, Set, Tuple

TagProfile = Tuple[Tuple[str, float], ...]


def canonical_profile(tags: Mapping[str, float]) -> TagProfile:
    """Return a deterministic representation of a query/tag weight profile."""
    return tuple(sorted((str(tag), float(weight)) for tag, weight in tags.items()))


@dataclass
class Box:
    """Local resolver/index owned by a node; it performs no inference."""

    node_id: str
    index: Dict[str, float] = field(default_factory=dict)
    known_connections: Set[str] = field(default_factory=set)

    def index_tags(self, tags: Mapping[str, float]) -> None:
        for tag, weight in tags.items():
            self.index[tag] = max(self.index.get(tag, 0.0), float(weight))

    def overlap(self, tags: Mapping[str, float]) -> float:
        """Simple weighted coincidence score for the reference implementation."""
        return sum(min(float(weight), self.index.get(tag, 0.0)) for tag, weight in tags.items())

    def connect(self, node_id: str) -> None:
        if node_id != self.node_id:
            self.known_connections.add(node_id)


@dataclass
class Node:
    """Query-emergent cluster identified by its canonical tag profile."""

    node_id: str
    profile: TagProfile
    relevance_weight: int = 1
    box: Box = field(init=False)

    def __post_init__(self) -> None:
        self.box = Box(self.node_id)
        self.box.index_tags(dict(self.profile))


class SuperIndex:
    """Global registry mapping meta-tags/profiles to node locations."""

    def __init__(self) -> None:
        self._nodes: Dict[str, Node] = {}
        self._profile_to_node: Dict[TagProfile, str] = {}
        self._tag_to_nodes: Dict[str, Set[str]] = {}
        self._counter = 0

    @property
    def nodes(self) -> Mapping[str, Node]:
        return self._nodes

    def register(self, tags: Mapping[str, float]) -> Node:
        profile = canonical_profile(tags)
        existing_id = self._profile_to_node.get(profile)
        if existing_id is not None:
            node = self._nodes[existing_id]
            node.relevance_weight += 1
            return node

        self._counter += 1
        node_id = f"node-{self._counter:04d}"
        node = Node(node_id=node_id, profile=profile)
        self._nodes[node_id] = node
        self._profile_to_node[profile] = node_id
        for tag, _ in profile:
            self._tag_to_nodes.setdefault(tag, set()).add(node_id)
        return node

    def lookup(self, tags: Iterable[str]) -> Set[str]:
        result: Set[str] = set()
        for tag in tags:
            result.update(self._tag_to_nodes.get(tag, set()))
        return result

    def rank(self, tags: Mapping[str, float]) -> list[tuple[str, float]]:
        """Rank nodes by current query coincidence, not historical weight."""
        ranked = [(node.node_id, node.box.overlap(tags)) for node in self._nodes.values()]
        ranked.sort(key=lambda item: (-item[1], item[0]))
        return ranked

    def connect(self, left: str, right: str) -> None:
        self._nodes[left].box.connect(right)
        self._nodes[right].box.connect(left)
