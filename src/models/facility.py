"""
Facility graph models — the digital twin of the facility.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class EdgeType(str, Enum):
    ADJACENT_TO = "adjacent_to"
    CONNECTS_TO = "connects_to"
    VENTILATED_BY = "ventilated_by"
    POWERED_BY = "powered_by"
    SERVED_BY = "served_by"
    ACCESSED_BY = "accessed_by"


class NodeType(str, Enum):
    ROOM = "room"
    SYSTEM = "system"
    EQUIPMENT = "equipment"
    ZONE = "zone"


class FacilityNode(BaseModel):
    id: str
    node_type: NodeType
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class FacilityEdge(BaseModel):
    from_node: str
    to_node: str
    edge_type: EdgeType
    properties: Dict[str, Any] = Field(default_factory=dict)


class FacilityGraph(BaseModel):
    """Digital representation of an entire facility."""
    project_id: str
    nodes: List[FacilityNode] = Field(default_factory=list)
    edges: List[FacilityEdge] = Field(default_factory=list)

    def get_node(self, node_id: str) -> Optional[FacilityNode]:
        return next((n for n in self.nodes if n.id == node_id), None)

    def neighbors(self, node_id: str, edge_type: Optional[EdgeType] = None) -> List[str]:
        edges = [e for e in self.edges if e.from_node == node_id or e.to_node == node_id]
        if edge_type:
            edges = [e for e in edges if e.edge_type == edge_type]
        result = []
        for e in edges:
            neighbor = e.to_node if e.from_node == node_id else e.from_node
            result.append(neighbor)
        return result
