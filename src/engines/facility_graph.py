"""
Digital Facility Graph Engine
==============================
Converts a BlueprintParseResult into a graph-structured Digital Twin.

Nodes  → rooms, systems (HVAC, electrical), equipment
Edges  → adjacent_to, connects_to, ventilated_by, powered_by

Backed by NetworkX in-process; Neo4j driver interface available
for production deployments (enable USE_NEO4J=true in .env).
"""
import logging
import math
from typing import List, Optional, Dict, Any, Tuple

import networkx as nx

from src.models.blueprint import BlueprintParseResult, DetectedRoom, RoomType, ObjectType
from src.models.facility import FacilityGraph, FacilityNode, FacilityEdge, EdgeType, NodeType

logger = logging.getLogger(__name__)

# Adjacency threshold: rooms whose bounding centroids are within this many
# pixels are considered "adjacent" when no explicit corridor link is found.
DEFAULT_ADJACENCY_THRESHOLD_PX = 80.0

# System node IDs
HVAC_SYSTEM_ID = "SYS-HVAC-MAIN"
ELECTRICAL_SYSTEM_ID = "SYS-ELEC-MAIN"
MEDICAL_GAS_SYSTEM_ID = "SYS-MEDGAS-MAIN"

# Room types that must be ventilated at high-ACH by a dedicated HVAC branch
HIGH_ACH_ROOM_TYPES = {RoomType.OPERATING_ROOM, RoomType.STERILE_CORE, RoomType.ICU}

# Room pairs that should be adjacent in a compliant layout
REQUIRED_ADJACENCIES = [
    (RoomType.OPERATING_ROOM, RoomType.STERILE_CORE),
    (RoomType.ICU, RoomType.NURSE_STATION),
]


def _euclidean(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.dist(a, b)


class FacilityGraphEngine:
    """
    Builds and queries the Digital Facility Graph.

    Usage:
        engine = FacilityGraphEngine()
        graph = engine.build(parse_result)
        adjacents = engine.get_adjacent_rooms(graph, "OR-001")
    """

    def __init__(self, adjacency_threshold_px: float = DEFAULT_ADJACENCY_THRESHOLD_PX):
        self.adjacency_threshold = adjacency_threshold_px

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, parse_result: BlueprintParseResult) -> FacilityGraph:
        """Convert a BlueprintParseResult into a FacilityGraph."""
        logger.info(
            "Building facility graph for project %s (%d rooms)",
            parse_result.project_id,
            len(parse_result.rooms),
        )

        nodes: List[FacilityNode] = []
        edges: List[FacilityEdge] = []

        # 1. Add system nodes
        nodes.extend(self._create_system_nodes())

        # 2. Add room nodes
        for room in parse_result.rooms:
            node = FacilityNode(
                id=room.id,
                node_type=NodeType.ROOM,
                label=room.label,
                properties={
                    "room_type": room.room_type.value,
                    "area_sqft": room.area_sqft,
                    "floor": room.floor,
                    "centroid_x": room.polygon.centroid[0],
                    "centroid_y": room.polygon.centroid[1],
                    **room.attributes,
                },
            )
            nodes.append(node)

        # 3. Add corridor nodes
        for corridor in parse_result.corridors:
            node = FacilityNode(
                id=corridor.id,
                node_type=NodeType.ZONE,
                label=f"Corridor {corridor.id}",
                properties={"width_ft": corridor.width_ft},
            )
            nodes.append(node)

        # 4. Add equipment nodes (from detected objects)
        for obj in parse_result.objects:
            if obj.object_type not in (ObjectType.DOOR,):  # skip doors — they become edges
                node = FacilityNode(
                    id=obj.id,
                    node_type=NodeType.EQUIPMENT,
                    label=obj.object_type.value.replace("_", " ").title(),
                    properties={"object_type": obj.object_type.value, "room_id": obj.room_id},
                )
                nodes.append(node)

        # 5. Build adjacency edges from spatial proximity
        edges.extend(self._build_adjacency_edges(parse_result))

        # 6. Connect corridors to rooms
        edges.extend(self._build_corridor_connections(parse_result))

        # 7. Connect high-ACH rooms to HVAC system
        edges.extend(self._build_system_edges(parse_result))

        # 8. Connect equipment to their host rooms
        edges.extend(self._build_equipment_edges(parse_result))

        graph = FacilityGraph(
            project_id=parse_result.project_id,
            nodes=nodes,
            edges=edges,
        )
        logger.info(
            "Facility graph built: %d nodes, %d edges",
            len(nodes),
            len(edges),
        )
        return graph

    # ------------------------------------------------------------------
    # Spatial adjacency
    # ------------------------------------------------------------------

    def _build_adjacency_edges(self, pr: BlueprintParseResult) -> List[FacilityEdge]:
        edges: List[FacilityEdge] = []
        rooms = pr.rooms
        for i, room_a in enumerate(rooms):
            for room_b in rooms[i + 1:]:
                dist = _euclidean(room_a.polygon.centroid, room_b.polygon.centroid)
                if dist <= self.adjacency_threshold:
                    edges.append(FacilityEdge(
                        from_node=room_a.id,
                        to_node=room_b.id,
                        edge_type=EdgeType.ADJACENT_TO,
                        properties={"distance_px": round(dist, 2)},
                    ))
        return edges

    def _build_corridor_connections(self, pr: BlueprintParseResult) -> List[FacilityEdge]:
        edges: List[FacilityEdge] = []
        for corridor in pr.corridors:
            for room_id in corridor.connects_rooms:
                edges.append(FacilityEdge(
                    from_node=room_id,
                    to_node=corridor.id,
                    edge_type=EdgeType.CONNECTS_TO,
                    properties={"via": "corridor"},
                ))
        return edges

    # ------------------------------------------------------------------
    # System connections
    # ------------------------------------------------------------------

    def _create_system_nodes(self) -> List[FacilityNode]:
        return [
            FacilityNode(id=HVAC_SYSTEM_ID, node_type=NodeType.SYSTEM, label="Main HVAC System"),
            FacilityNode(id=ELECTRICAL_SYSTEM_ID, node_type=NodeType.SYSTEM, label="Electrical Distribution"),
            FacilityNode(id=MEDICAL_GAS_SYSTEM_ID, node_type=NodeType.SYSTEM, label="Medical Gas Supply"),
        ]

    def _build_system_edges(self, pr: BlueprintParseResult) -> List[FacilityEdge]:
        edges: List[FacilityEdge] = []
        for room in pr.rooms:
            # HVAC ventilation
            edges.append(FacilityEdge(
                from_node=room.id,
                to_node=HVAC_SYSTEM_ID,
                edge_type=EdgeType.VENTILATED_BY,
                properties={"priority": "high" if room.room_type in HIGH_ACH_ROOM_TYPES else "standard"},
            ))
            # Electrical
            edges.append(FacilityEdge(
                from_node=room.id,
                to_node=ELECTRICAL_SYSTEM_ID,
                edge_type=EdgeType.POWERED_BY,
                properties={"redundant": room.room_type in {RoomType.OPERATING_ROOM, RoomType.ICU}},
            ))
            # Medical gas for clinical spaces
            if room.room_type in {RoomType.OPERATING_ROOM, RoomType.ICU, RoomType.EMERGENCY}:
                edges.append(FacilityEdge(
                    from_node=room.id,
                    to_node=MEDICAL_GAS_SYSTEM_ID,
                    edge_type=EdgeType.SERVED_BY,
                    properties={"gases": ["O2", "N2O", "vacuum"]},
                ))
        return edges

    def _build_equipment_edges(self, pr: BlueprintParseResult) -> List[FacilityEdge]:
        edges: List[FacilityEdge] = []
        for obj in pr.objects:
            if obj.room_id:
                edges.append(FacilityEdge(
                    from_node=obj.id,
                    to_node=obj.room_id,
                    edge_type=EdgeType.ACCESSED_BY,
                    properties={"object_type": obj.object_type.value},
                ))
        return edges

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def to_networkx(self, graph: FacilityGraph) -> nx.DiGraph:
        G = nx.DiGraph()
        for node in graph.nodes:
            G.add_node(node.id, **{"label": node.label, "node_type": node.node_type.value, **node.properties})
        for edge in graph.edges:
            G.add_edge(edge.from_node, edge.to_node, edge_type=edge.edge_type.value, **edge.properties)
        return G

    def get_adjacent_rooms(self, graph: FacilityGraph, room_id: str) -> List[str]:
        return graph.neighbors(room_id, EdgeType.ADJACENT_TO)

    def find_missing_required_adjacencies(
        self, graph: FacilityGraph, parse_result: BlueprintParseResult
    ) -> List[Tuple[RoomType, RoomType]]:
        """
        Return required (type_a, type_b) pairs that are NOT adjacent in this facility.
        """
        missing = []
        room_type_index: Dict[RoomType, List[str]] = {}
        for room in parse_result.rooms:
            room_type_index.setdefault(room.room_type, []).append(room.id)

        for type_a, type_b in REQUIRED_ADJACENCIES:
            rooms_a = room_type_index.get(type_a, [])
            rooms_b = room_type_index.get(type_b, [])
            if not rooms_a or not rooms_b:
                continue

            found = False
            for ra in rooms_a:
                for rb in rooms_b:
                    adj = self.get_adjacent_rooms(graph, ra)
                    if rb in adj:
                        found = True
                        break
                if found:
                    break
            if not found:
                missing.append((type_a, type_b))

        return missing

    def shortest_path(
        self, graph: FacilityGraph, from_id: str, to_id: str
    ) -> Optional[List[str]]:
        G = self.to_networkx(graph)
        try:
            return nx.shortest_path(G.to_undirected(), from_id, to_id)
        except nx.NetworkXNoPath:
            return None
