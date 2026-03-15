"""
Regulatory Design Graph Store
================================
Combines the Digital Facility Graph with compliance outcomes to build
a persistent, queryable graph of every project's design decisions.

This is the data structure that makes MedBlueprints hard to replicate:
each project's rooms, adjacencies, violations, and approval outcomes
are stored as interconnected nodes — forming a living knowledge graph.

Backend:
  - NetworkX (in-memory, dev / small deployments)
  - Neo4j (production — enable USE_NEO4J=true in .env)

Graph schema:
  (:Room {id, type, area_sqft, ...}) -[:ADJACENT_TO]→ (:Room)
  (:Room) -[:VIOLATES]→ (:Rule {rule_id, source, description})
  (:Room) -[:COMPLIES_WITH]→ (:Rule)
  (:Project {id, facility_type, ...}) -[:CONTAINS]→ (:Room)
  (:Project) -[:HAS_OUTCOME]→ (:Outcome {result, cost, days})
"""
import json
import logging
from typing import List, Optional, Dict, Any, Tuple

import networkx as nx

from src.core.config import settings
from src.models.facility import FacilityGraph, FacilityEdge, FacilityNode, EdgeType
from src.models.compliance import ComplianceReport, ViolationSeverity
from src.models.blueprint import BlueprintParseResult

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False


class RegulatoryDesignGraphStore:
    """
    Persists the regulatory design graph.

    The in-memory NetworkX graph accumulates across all projects in a
    single server session.  Call export_gexf() to persist to disk.
    For production, enable Neo4j via USE_NEO4J=true.
    """

    def __init__(self):
        self._G = nx.MultiDiGraph()
        self._neo4j_driver = None

        if settings.use_neo4j and NEO4J_AVAILABLE:
            try:
                self._neo4j_driver = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password),
                )
                logger.info("Connected to Neo4j at %s", settings.neo4j_uri)
            except Exception as exc:
                logger.warning("Neo4j connection failed: %s — using in-memory graph", exc)

        logger.info("RegulatoryDesignGraphStore initialized (neo4j=%s)", self._neo4j_driver is not None)

    # ------------------------------------------------------------------
    # Ingest a project
    # ------------------------------------------------------------------

    def ingest_project(
        self,
        parse_result: BlueprintParseResult,
        facility_graph: FacilityGraph,
        compliance_report: ComplianceReport,
        approval_result: Optional[str] = None,
        facility_type: str = "hospital",
    ) -> None:
        """
        Add a complete project to the graph store.
        """
        project_id = parse_result.project_id

        # Project node
        self._G.add_node(
            f"project:{project_id}",
            node_class="project",
            facility_type=facility_type,
            total_rooms=len(parse_result.rooms),
            total_area_sqft=parse_result.total_area_sqft or 0,
        )

        # Room nodes + violation edges
        result_by_room = {r.room_id: r for r in compliance_report.room_results}

        for room in parse_result.rooms:
            room_node_id = f"room:{project_id}:{room.id}"
            self._G.add_node(
                room_node_id,
                node_class="room",
                room_type=room.room_type.value,
                area_sqft=room.area_sqft or 0,
                label=room.label,
                project_id=project_id,
            )

            # Project → Room
            self._G.add_edge(
                f"project:{project_id}", room_node_id,
                relation="CONTAINS",
            )

            result = result_by_room.get(room.id)
            if result:
                for violation in result.violations:
                    rule_node_id = f"rule:{violation.rule_id}"
                    if rule_node_id not in self._G:
                        self._G.add_node(
                            rule_node_id,
                            node_class="rule",
                            rule_id=violation.rule_id,
                            source=violation.source.value,
                            description=violation.description,
                        )
                    self._G.add_edge(
                        room_node_id, rule_node_id,
                        relation="VIOLATES",
                        severity=violation.severity.value,
                        actual_value=violation.actual_value,
                        required_value=violation.required_value,
                        cost_usd=violation.estimated_correction_cost_usd or 0,
                    )

                for passed_rule_id in result.passed_rules:
                    rule_node_id = f"rule:{passed_rule_id}"
                    if rule_node_id not in self._G:
                        self._G.add_node(rule_node_id, node_class="rule", rule_id=passed_rule_id)
                    self._G.add_edge(room_node_id, rule_node_id, relation="COMPLIES_WITH")

        # Adjacency edges from facility graph
        for edge in facility_graph.edges:
            if edge.edge_type == EdgeType.ADJACENT_TO:
                n_a = f"room:{project_id}:{edge.from_node}"
                n_b = f"room:{project_id}:{edge.to_node}"
                if n_a in self._G and n_b in self._G:
                    self._G.add_edge(n_a, n_b, relation="ADJACENT_TO")

        # Outcome node
        if approval_result:
            outcome_node_id = f"outcome:{project_id}"
            self._G.add_node(
                outcome_node_id,
                node_class="outcome",
                result=approval_result,
                critical_violations=compliance_report.critical_violations,
                total_correction_cost=compliance_report.estimated_total_correction_cost_usd,
            )
            self._G.add_edge(f"project:{project_id}", outcome_node_id, relation="HAS_OUTCOME")

        logger.debug("Ingested project %s into design graph (%d nodes)", project_id, self._G.number_of_nodes())

        # Mirror to Neo4j if available
        if self._neo4j_driver:
            self._neo4j_ingest(project_id, parse_result, compliance_report, approval_result)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def most_common_violations(
        self, room_type: Optional[str] = None, top_k: int = 10
    ) -> List[Tuple[str, int]]:
        """Return the most frequently violated rules across all ingested projects."""
        violation_counts: Dict[str, int] = {}
        for u, v, data in self._G.edges(data=True):
            if data.get("relation") == "VIOLATES":
                u_data = self._G.nodes.get(u, {})
                if room_type and u_data.get("room_type") != room_type:
                    continue
                rule_id = v.replace("rule:", "")
                violation_counts[rule_id] = violation_counts.get(rule_id, 0) + 1
        sorted_items = sorted(violation_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:top_k]

    def approval_rate_by_violation_count(self) -> Dict[str, float]:
        """
        Compute approval rates binned by critical violation count.
        Answers: "How many critical violations before rejection becomes likely?"
        """
        bins: Dict[int, List[bool]] = {}
        for project_node, data in self._G.nodes(data=True):
            if data.get("node_class") != "project":
                continue
            project_id = project_node.replace("project:", "")
            outcome_node = f"outcome:{project_id}"
            if outcome_node not in self._G:
                continue
            outcome = self._G.nodes[outcome_node]
            critical = outcome.get("critical_violations", 0)
            approved = outcome.get("result") == "approved"
            bins.setdefault(critical, []).append(approved)

        return {
            f"critical_{k}": round(sum(v) / len(v) * 100, 1)
            for k, v in sorted(bins.items())
        }

    def similar_projects(
        self,
        room_types: List[str],
        top_k: int = 5,
    ) -> List[str]:
        """
        Find existing projects in the graph with similar room type distributions.
        Uses Jaccard similarity on room type sets.
        """
        query_set = set(room_types)
        scores: List[Tuple[float, str]] = []

        project_room_types: Dict[str, set] = {}
        for n, data in self._G.nodes(data=True):
            if data.get("node_class") == "room":
                pid = data.get("project_id", "")
                rt = data.get("room_type", "")
                project_room_types.setdefault(pid, set()).add(rt)

        for pid, rts in project_room_types.items():
            intersection = len(query_set & rts)
            union = len(query_set | rts)
            jaccard = intersection / max(union, 1)
            scores.append((jaccard, pid))

        scores.sort(reverse=True)
        return [pid for _, pid in scores[:top_k]]

    def graph_stats(self) -> Dict[str, Any]:
        project_count = sum(1 for _, d in self._G.nodes(data=True) if d.get("node_class") == "project")
        room_count = sum(1 for _, d in self._G.nodes(data=True) if d.get("node_class") == "room")
        rule_count = sum(1 for _, d in self._G.nodes(data=True) if d.get("node_class") == "rule")
        violation_edges = sum(1 for _, _, d in self._G.edges(data=True) if d.get("relation") == "VIOLATES")

        return {
            "total_nodes": self._G.number_of_nodes(),
            "total_edges": self._G.number_of_edges(),
            "projects": project_count,
            "rooms": room_count,
            "rules": rule_count,
            "violation_relationships": violation_edges,
            "neo4j_connected": self._neo4j_driver is not None,
        }

    def export_gexf(self, path: str) -> None:
        """Export the full graph as GEXF (compatible with Gephi and Neo4j import)."""
        nx.write_gexf(self._G, path)
        logger.info("Exported design graph to %s", path)

    # ------------------------------------------------------------------
    # Neo4j mirroring
    # ------------------------------------------------------------------

    def _neo4j_ingest(
        self,
        project_id: str,
        parse_result: BlueprintParseResult,
        report: ComplianceReport,
        approval_result: Optional[str],
    ) -> None:
        if not self._neo4j_driver:
            return
        try:
            with self._neo4j_driver.session() as session:
                # Upsert Project node
                session.run(
                    "MERGE (p:Project {id: $id}) SET p.facility_type = $ft, p.total_rooms = $tr",
                    id=project_id,
                    ft="hospital",
                    tr=len(parse_result.rooms),
                )
                for room in parse_result.rooms:
                    session.run(
                        """
                        MERGE (r:Room {id: $rid})
                        SET r.room_type = $rt, r.area_sqft = $area, r.label = $label
                        WITH r
                        MATCH (p:Project {id: $pid})
                        MERGE (p)-[:CONTAINS]->(r)
                        """,
                        rid=f"{project_id}:{room.id}",
                        rt=room.room_type.value,
                        area=room.area_sqft or 0,
                        label=room.label,
                        pid=project_id,
                    )
                if approval_result:
                    session.run(
                        """
                        MATCH (p:Project {id: $pid})
                        MERGE (o:Outcome {project_id: $pid})
                        SET o.result = $result
                        MERGE (p)-[:HAS_OUTCOME]->(o)
                        """,
                        pid=project_id,
                        result=approval_result,
                    )
        except Exception as exc:
            logger.warning("Neo4j ingest failed for project %s: %s", project_id, exc)
