"""
Blueprint data models — the raw geometry extracted by the CV engine.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum


class RoomType(str, Enum):
    OPERATING_ROOM = "operating_room"
    ICU = "icu"
    EMERGENCY = "emergency"
    STERILE_CORE = "sterile_core"
    NURSE_STATION = "nurse_station"
    PATIENT_ROOM = "patient_room"
    CORRIDOR = "corridor"
    MECHANICAL = "mechanical"
    UTILITY = "utility"
    WAITING = "waiting"
    PHARMACY = "pharmacy"
    LABORATORY = "laboratory"
    IMAGING = "imaging"
    UNKNOWN = "unknown"


class ObjectType(str, Enum):
    DOOR = "door"
    WINDOW = "window"
    HVAC_VENT = "hvac_vent"
    ELEVATOR = "elevator"
    STAIRWELL = "stairwell"
    SINK = "sink"
    MEDICAL_GAS = "medical_gas"
    ELECTRICAL_PANEL = "electrical_panel"
    SPRINKLER = "sprinkler"


class Point(BaseModel):
    x: float
    y: float


class Polygon(BaseModel):
    points: List[Tuple[float, float]]

    @property
    def area(self) -> float:
        """Shoelace formula for polygon area in square units."""
        pts = self.points
        n = len(pts)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += pts[i][0] * pts[j][1]
            area -= pts[j][0] * pts[i][1]
        return abs(area) / 2.0

    @property
    def centroid(self) -> Tuple[float, float]:
        pts = self.points
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        return (cx, cy)


class DetectedRoom(BaseModel):
    id: str
    label: str
    room_type: RoomType
    polygon: Polygon
    area_sqft: Optional[float] = None
    floor: int = 1
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    attributes: Dict[str, Any] = Field(default_factory=dict)


class DetectedObject(BaseModel):
    id: str
    object_type: ObjectType
    location: Tuple[float, float]
    room_id: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    attributes: Dict[str, Any] = Field(default_factory=dict)


class DetectedCorridor(BaseModel):
    id: str
    polygon: Polygon
    width_ft: Optional[float] = None
    connects_rooms: List[str] = Field(default_factory=list)


class BlueprintParseResult(BaseModel):
    """Output of the Computer Vision Blueprint Engine."""
    project_id: str
    source_filename: str
    image_width: int
    image_height: int
    scale_ft_per_pixel: float = Field(default=0.1, description="Feet per pixel at detected scale")
    rooms: List[DetectedRoom] = Field(default_factory=list)
    objects: List[DetectedObject] = Field(default_factory=list)
    corridors: List[DetectedCorridor] = Field(default_factory=list)
    floors: int = 1
    total_area_sqft: Optional[float] = None
    parse_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def room_by_id(self, room_id: str) -> Optional[DetectedRoom]:
        return next((r for r in self.rooms if r.id == room_id), None)

    def objects_in_room(self, room_id: str) -> List[DetectedObject]:
        return [o for o in self.objects if o.room_id == room_id]
