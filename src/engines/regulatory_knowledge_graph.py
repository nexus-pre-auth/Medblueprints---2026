"""
Regulatory Knowledge Graph
============================
Structures healthcare regulations as a queryable graph of rules.

Rule nodes connect to room_type nodes via constraint edges, enabling
the compliance engine to retrieve all applicable rules for any room
in a blueprint without doing a full table scan.

Vector search (FAISS + sentence-transformers) is used for semantic
retrieval of rules given a natural-language context string.

Architecture:
  RuleNode ──[applies_to]──► RoomTypeNode
  RuleNode ──[references]──► StandardNode (FGI, NFPA, …)
"""
import json
import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

import networkx as nx

from src.models.compliance import RegulatoryRule, ConstraintType, RuleSource

logger = logging.getLogger(__name__)

# Rule data lives in data/regulatory_rules/
RULES_DIR = Path(__file__).parent.parent.parent / "data" / "regulatory_rules"

# Optional: vector search libraries
try:
    import numpy as np
    import faiss
    from sentence_transformers import SentenceTransformer
    VECTOR_SEARCH_AVAILABLE = True
except ImportError:
    VECTOR_SEARCH_AVAILABLE = False


class RegulatoryKnowledgeGraph:
    """
    Loads all regulatory rules into a NetworkX graph and provides
    efficient retrieval by room type, constraint type, or semantic query.
    """

    def __init__(
        self,
        rules_dir: Optional[Path] = None,
        embeddings_model: str = "all-MiniLM-L6-v2",
        enable_vector_search: bool = True,
    ):
        self._graph = nx.DiGraph()
        self._rules: Dict[str, RegulatoryRule] = {}
        self._rules_by_room_type: Dict[str, List[RegulatoryRule]] = {}

        # Vector search
        self._vector_search_ready = False
        self._faiss_index = None
        self._rule_ids_ordered: List[str] = []
        self._embedder = None

        rules_dir = rules_dir or RULES_DIR
        self._load_rules_from_dir(rules_dir)
        self._build_graph()

        if enable_vector_search and VECTOR_SEARCH_AVAILABLE:
            self._build_vector_index(embeddings_model)

        logger.info(
            "RegulatoryKnowledgeGraph loaded: %d rules, %d room types",
            len(self._rules),
            len(self._rules_by_room_type),
        )

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_rules_from_dir(self, rules_dir: Path) -> None:
        if not rules_dir.exists():
            logger.warning("Rules directory not found: %s", rules_dir)
            return

        for json_file in rules_dir.glob("*.json"):
            try:
                raw = json.loads(json_file.read_text())
                for item in raw:
                    rule = RegulatoryRule(**item)
                    self._rules[rule.rule_id] = rule
                    self._rules_by_room_type.setdefault(rule.room_type, []).append(rule)
                logger.debug("Loaded %d rules from %s", len(raw), json_file.name)
            except Exception as exc:
                logger.error("Failed to load %s: %s", json_file, exc)

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self) -> None:
        """
        Graph structure:
          rule_id → room_type        (applies_to)
          rule_id → source_standard  (governed_by)
        """
        for rule in self._rules.values():
            # Rule node
            self._graph.add_node(
                rule.rule_id,
                node_class="rule",
                description=rule.description,
                constraint_type=rule.constraint_type.value,
                threshold_value=rule.threshold_value,
                threshold_unit=rule.threshold_unit,
                mandatory=rule.mandatory,
            )
            # Room type node
            rt_node = f"room_type:{rule.room_type}"
            if rt_node not in self._graph:
                self._graph.add_node(rt_node, node_class="room_type", label=rule.room_type)
            self._graph.add_edge(rule.rule_id, rt_node, relation="applies_to")

            # Standard node
            std_node = f"standard:{rule.source.value}"
            if std_node not in self._graph:
                self._graph.add_node(std_node, node_class="standard", label=rule.source.value)
            self._graph.add_edge(rule.rule_id, std_node, relation="governed_by")

            # Related room type (for adjacency rules)
            if rule.related_room_type:
                related_node = f"room_type:{rule.related_room_type}"
                if related_node not in self._graph:
                    self._graph.add_node(related_node, node_class="room_type", label=rule.related_room_type)
                self._graph.add_edge(rule.rule_id, related_node, relation="requires_relation_to")

    # ------------------------------------------------------------------
    # Vector index
    # ------------------------------------------------------------------

    def _build_vector_index(self, model_name: str) -> None:
        try:
            self._embedder = SentenceTransformer(model_name)
            descriptions = [r.description for r in self._rules.values()]
            self._rule_ids_ordered = list(self._rules.keys())
            embeddings = self._embedder.encode(descriptions, convert_to_numpy=True)
            embeddings = embeddings.astype("float32")
            faiss.normalize_L2(embeddings)

            dim = embeddings.shape[1]
            self._faiss_index = faiss.IndexFlatIP(dim)
            self._faiss_index.add(embeddings)
            self._vector_search_ready = True
            logger.info("FAISS vector index built (%d rules, dim=%d)", len(descriptions), dim)
        except Exception as exc:
            logger.warning("Vector search initialization failed: %s", exc)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get_rules_for_room_type(
        self,
        room_type: str,
        constraint_type: Optional[ConstraintType] = None,
    ) -> List[RegulatoryRule]:
        """Return all rules applicable to a room type, optionally filtered."""
        rules = self._rules_by_room_type.get(room_type, [])
        if constraint_type:
            rules = [r for r in rules if r.constraint_type == constraint_type]
        return rules

    def get_rule(self, rule_id: str) -> Optional[RegulatoryRule]:
        return self._rules.get(rule_id)

    def get_all_rules(self) -> List[RegulatoryRule]:
        return list(self._rules.values())

    def get_adjacency_rules(self, room_type: str) -> List[RegulatoryRule]:
        """Return all adjacency-required rules for a given room type."""
        return [
            r for r in self._rules_by_room_type.get(room_type, [])
            if r.constraint_type == ConstraintType.ADJACENCY_REQUIRED
        ]

    def semantic_search(self, query: str, top_k: int = 5) -> List[RegulatoryRule]:
        """
        Find the most semantically relevant rules for a natural-language query.
        Falls back to keyword matching if vector search is unavailable.
        """
        if self._vector_search_ready and self._faiss_index is not None:
            return self._vector_search(query, top_k)
        return self._keyword_search(query, top_k)

    def _vector_search(self, query: str, top_k: int) -> List[RegulatoryRule]:
        import numpy as np
        q_emb = self._embedder.encode([query], convert_to_numpy=True).astype("float32")
        faiss.normalize_L2(q_emb)
        distances, indices = self._faiss_index.search(q_emb, min(top_k, len(self._rules)))
        results = []
        for idx in indices[0]:
            if 0 <= idx < len(self._rule_ids_ordered):
                rule_id = self._rule_ids_ordered[idx]
                results.append(self._rules[rule_id])
        return results

    def _keyword_search(self, query: str, top_k: int) -> List[RegulatoryRule]:
        query_lower = query.lower()
        scored = []
        for rule in self._rules.values():
            score = sum(
                1 for word in query_lower.split()
                if word in rule.description.lower() or word in rule.room_type
            )
            if score > 0:
                scored.append((score, rule))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:top_k]]

    def graph_neighbors(self, node_id: str) -> List[str]:
        return list(self._graph.successors(node_id))

    def export_graph_json(self) -> Dict[str, Any]:
        """Export the rule graph as JSON (for visualization / Neo4j import)."""
        nodes = []
        for node_id, data in self._graph.nodes(data=True):
            nodes.append({"id": node_id, **data})
        edges = []
        for u, v, data in self._graph.edges(data=True):
            edges.append({"from": u, "to": v, **data})
        return {"nodes": nodes, "edges": edges}

    def stats(self) -> Dict[str, Any]:
        return {
            "total_rules": len(self._rules),
            "room_types_covered": list(self._rules_by_room_type.keys()),
            "sources": list({r.source.value for r in self._rules.values()}),
            "graph_nodes": self._graph.number_of_nodes(),
            "graph_edges": self._graph.number_of_edges(),
            "vector_search_enabled": self._vector_search_ready,
        }
