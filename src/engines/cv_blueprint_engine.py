"""
Computer Vision Blueprint Engine
=================================
Parses blueprint images/PDFs into structured geometry.

Pipeline:
  Blueprint image
    → Edge detection (Canny)
    → Wall detection (Hough lines)
    → Room segmentation (contour analysis)
    → Object detection (template matching / rule-based)
    → Output: BlueprintParseResult

In production, YOLOv8 or Detectron2 models can replace the
rule-based room classifier.  This implementation provides the
full pipeline interface so model weights can be hot-swapped.
"""
import uuid
import math
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from src.models.blueprint import (
    BlueprintParseResult,
    DetectedRoom,
    DetectedObject,
    DetectedCorridor,
    Polygon,
    RoomType,
    ObjectType,
)

logger = logging.getLogger(__name__)

# Typical healthcare room area ranges (sq ft) for heuristic classification
ROOM_AREA_PROFILES: Dict[str, Dict[str, float]] = {
    "operating_room":  {"min": 400,  "max": 700,  "aspect_max": 1.8},
    "icu":             {"min": 200,  "max": 400,  "aspect_max": 2.0},
    "patient_room":    {"min": 120,  "max": 250,  "aspect_max": 2.5},
    "sterile_core":    {"min": 150,  "max": 500,  "aspect_max": 3.0},
    "nurse_station":   {"min": 80,   "max": 200,  "aspect_max": 4.0},
    "corridor":        {"min": 10,   "max": 300,  "aspect_max": 20.0},
    "waiting":         {"min": 200,  "max": 800,  "aspect_max": 3.0},
    "emergency":       {"min": 150,  "max": 500,  "aspect_max": 2.5},
    "laboratory":      {"min": 100,  "max": 400,  "aspect_max": 3.0},
    "imaging":         {"min": 150,  "max": 600,  "aspect_max": 2.0},
    "pharmacy":        {"min": 100,  "max": 300,  "aspect_max": 3.0},
    "mechanical":      {"min": 50,   "max": 500,  "aspect_max": 5.0},
}


def _polygon_area(contour) -> float:
    """OpenCV contour area in pixel^2."""
    return float(cv2.contourArea(contour))


def _bounding_aspect(contour) -> float:
    """Width/height aspect ratio of bounding rect."""
    x, y, w, h = cv2.boundingRect(contour)
    return w / max(h, 1)


def _contour_to_polygon(contour, approx_epsilon: float = 0.02) -> Polygon:
    """Simplify an OpenCV contour to a polygon."""
    peri = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, approx_epsilon * peri, True)
    points = [(float(pt[0][0]), float(pt[0][1])) for pt in approx]
    return Polygon(points=points)


def _classify_room(area_sqft: float, aspect: float, label_hint: str = "") -> RoomType:
    """
    Heuristic room type classifier.
    In production this is replaced by a trained YOLOv8 / Detectron2 model.
    """
    label_lower = label_hint.lower()

    keyword_map = {
        "or ": RoomType.OPERATING_ROOM,
        "operating": RoomType.OPERATING_ROOM,
        "icu": RoomType.ICU,
        "sterile": RoomType.STERILE_CORE,
        "nurse": RoomType.NURSE_STATION,
        "corridor": RoomType.CORRIDOR,
        "hall": RoomType.CORRIDOR,
        "wait": RoomType.WAITING,
        "emergency": RoomType.EMERGENCY,
        "er ": RoomType.EMERGENCY,
        "lab": RoomType.LABORATORY,
        "imaging": RoomType.IMAGING,
        "mri": RoomType.IMAGING,
        "ct ": RoomType.IMAGING,
        "pharmacy": RoomType.PHARMACY,
        "mechanical": RoomType.MECHANICAL,
        "utility": RoomType.UTILITY,
        "patient": RoomType.PATIENT_ROOM,
    }
    for kw, rt in keyword_map.items():
        if kw in label_lower:
            return rt

    # Area + aspect heuristics
    if aspect > 8 and area_sqft < 250:
        return RoomType.CORRIDOR
    if 380 <= area_sqft <= 650 and aspect < 1.9:
        return RoomType.OPERATING_ROOM
    if 150 <= area_sqft <= 380 and aspect < 2.1:
        return RoomType.ICU
    if 100 <= area_sqft <= 240 and aspect < 2.8:
        return RoomType.PATIENT_ROOM

    return RoomType.UNKNOWN


def _detect_objects_in_room(image_gray, room_contour) -> List[DetectedObject]:
    """
    Detect objects (doors, vents, sinks) within a room contour via
    simple morphological analysis.  In production, a YOLO head handles this.
    """
    objects: List[DetectedObject] = []
    mask = np.zeros_like(image_gray)
    cv2.drawContours(mask, [room_contour], -1, 255, -1)

    # Small bright rectangles near the room boundary → doors
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    eroded = cv2.erode(mask, kernel, iterations=3)
    boundary_mask = cv2.subtract(mask, eroded)
    blurred = cv2.GaussianBlur(image_gray, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY)
    door_candidate = cv2.bitwise_and(thresh, boundary_mask)
    door_contours, _ = cv2.findContours(door_candidate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for c in door_contours:
        a = cv2.contourArea(c)
        if 20 < a < 500:
            M = cv2.moments(c)
            if M["m00"] > 0:
                cx = M["m10"] / M["m00"]
                cy = M["m01"] / M["m00"]
                objects.append(DetectedObject(
                    id=str(uuid.uuid4())[:8],
                    object_type=ObjectType.DOOR,
                    location=(cx, cy),
                    confidence=0.6,
                ))

    return objects


class CVBlueprintEngine:
    """
    Computer Vision Blueprint Engine.

    Accepts a blueprint image (path or numpy array) and returns
    a fully parsed BlueprintParseResult with rooms, corridors,
    and detected objects.
    """

    def __init__(
        self,
        scale_ft_per_pixel: float = 0.1,
        min_room_area_pixels: int = 500,
        use_ml_classifier: bool = False,
    ):
        if not CV2_AVAILABLE:
            raise ImportError("opencv-python-headless is required for CVBlueprintEngine")
        self.scale = scale_ft_per_pixel
        self.min_room_area = min_room_area_pixels
        self.use_ml_classifier = use_ml_classifier
        logger.info("CVBlueprintEngine initialized (scale=%.3f ft/px)", scale_ft_per_pixel)

    def parse_image(
        self,
        image_path: Optional[str] = None,
        image_array: Optional[np.ndarray] = None,
        project_id: Optional[str] = None,
        filename: str = "blueprint.png",
        room_labels: Optional[Dict[str, str]] = None,
    ) -> BlueprintParseResult:
        """
        Main entry point.  Provide either image_path or image_array.

        room_labels: optional dict mapping approximate centroid coords (as
                     "x,y" strings) to room label text, from OCR pre-processing.
        """
        if project_id is None:
            project_id = str(uuid.uuid4())[:12]
        room_labels = room_labels or {}

        # Load image
        if image_array is not None:
            img = image_array
        elif image_path:
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError(f"Could not load image: {image_path}")
        else:
            raise ValueError("Provide image_path or image_array")

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

        # Step 1: Edge detection
        edges = self._detect_edges(gray)

        # Step 2: Wall detection via morphological operations
        wall_mask = self._detect_walls(edges, gray)

        # Step 3: Room segmentation
        rooms, corridors = self._segment_rooms(
            wall_mask, gray, room_labels, project_id
        )

        # Step 4: Object detection within rooms
        all_objects: List[DetectedObject] = []
        for room in rooms:
            # Build a synthetic contour from polygon for object detection
            pts = np.array(room.polygon.points, dtype=np.int32)
            contour = pts.reshape((-1, 1, 2))
            objs = _detect_objects_in_room(gray, contour)
            for obj in objs:
                obj.room_id = room.id
            all_objects.extend(objs)

        total_area = sum(r.area_sqft or 0.0 for r in rooms if r.room_type != RoomType.CORRIDOR)

        return BlueprintParseResult(
            project_id=project_id,
            source_filename=filename,
            image_width=w,
            image_height=h,
            scale_ft_per_pixel=self.scale,
            rooms=rooms,
            objects=all_objects,
            corridors=corridors,
            total_area_sqft=total_area,
            parse_confidence=self._estimate_parse_confidence(rooms),
        )

    # ------------------------------------------------------------------
    # Internal pipeline steps
    # ------------------------------------------------------------------

    def _detect_edges(self, gray: np.ndarray) -> np.ndarray:
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, threshold1=50, threshold2=150)
        # Dilate to close small gaps in walls
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=2)
        return edges

    def _detect_walls(self, edges: np.ndarray, gray: np.ndarray) -> np.ndarray:
        """
        Combine edge map with horizontal/vertical line detection to produce
        a binary wall mask that is then inverted to give room interiors.
        """
        h, w = edges.shape

        # Hough line detection for dominant wall directions
        lines = cv2.HoughLinesP(
            edges, rho=1, theta=np.pi / 180, threshold=80,
            minLineLength=30, maxLineGap=10
        )
        line_mask = np.zeros_like(edges)
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(line_mask, (x1, y1), (x2, y2), 255, 2)

        combined = cv2.bitwise_or(edges, line_mask)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        wall_mask = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=3)
        return wall_mask

    def _segment_rooms(
        self,
        wall_mask: np.ndarray,
        gray: np.ndarray,
        room_labels: Dict[str, str],
        project_id: str,
    ) -> Tuple[List[DetectedRoom], List[DetectedCorridor]]:
        """
        Flood-fill the inverse of the wall mask to find enclosed spaces (rooms).
        """
        inverted = cv2.bitwise_not(wall_mask)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        cleaned = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, kernel, iterations=2)

        contours, hierarchy = cv2.findContours(
            cleaned, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
        )

        rooms: List[DetectedRoom] = []
        corridors: List[DetectedCorridor] = []
        room_counter = 1

        for i, contour in enumerate(contours):
            area_px = _polygon_area(contour)
            if area_px < self.min_room_area:
                continue

            area_sqft = area_px * (self.scale ** 2)
            aspect = _bounding_aspect(contour)
            polygon = _contour_to_polygon(contour)
            centroid = polygon.centroid

            # Try to find a label from OCR hints
            label_hint = self._find_label_for_centroid(centroid, room_labels)
            room_type = _classify_room(area_sqft, aspect, label_hint)

            if room_type == RoomType.CORRIDOR or (aspect > 8 and area_sqft < 250):
                x, y, cw, ch = cv2.boundingRect(contour)
                width_ft = min(cw, ch) * self.scale
                corridors.append(DetectedCorridor(
                    id=f"COR-{project_id}-{room_counter:03d}",
                    polygon=polygon,
                    width_ft=width_ft,
                ))
            else:
                room_id = f"ROOM-{project_id}-{room_counter:03d}"
                display_label = label_hint if label_hint else f"{room_type.value.replace('_', ' ').title()} {room_counter:03d}"
                rooms.append(DetectedRoom(
                    id=room_id,
                    label=display_label,
                    room_type=room_type,
                    polygon=polygon,
                    area_sqft=round(area_sqft, 1),
                    confidence=0.82 if label_hint else 0.65,
                ))

            room_counter += 1

        return rooms, corridors

    @staticmethod
    def _find_label_for_centroid(
        centroid: Tuple[float, float],
        room_labels: Dict[str, str],
        tolerance: float = 50.0,
    ) -> str:
        for key, label in room_labels.items():
            try:
                kx, ky = map(float, key.split(","))
                if math.dist((centroid[0], centroid[1]), (kx, ky)) < tolerance:
                    return label
            except (ValueError, TypeError):
                continue
        return ""

    @staticmethod
    def _estimate_parse_confidence(rooms: List[DetectedRoom]) -> float:
        if not rooms:
            return 0.0
        avg = sum(r.confidence for r in rooms) / len(rooms)
        return round(avg, 3)

    # ------------------------------------------------------------------
    # Convenience: parse a synthetic/demo blueprint without a real image
    # ------------------------------------------------------------------

    @classmethod
    def create_demo_parse_result(cls, project_id: str) -> BlueprintParseResult:
        """
        Generate a realistic demo BlueprintParseResult for development
        and testing without requiring a real blueprint image.
        """
        rooms = [
            DetectedRoom(
                id=f"OR-{project_id}-001",
                label="OR 101",
                room_type=RoomType.OPERATING_ROOM,
                polygon=Polygon(points=[(12, 10), (52, 10), (52, 50), (12, 50)]),
                area_sqft=450.0,
                confidence=0.92,
                attributes={"ventilation_ach": 18, "pressurization": "positive"},
            ),
            DetectedRoom(
                id=f"OR-{project_id}-002",
                label="OR 102",
                room_type=RoomType.OPERATING_ROOM,
                polygon=Polygon(points=[(55, 10), (95, 10), (95, 50), (55, 50)]),
                area_sqft=480.0,
                confidence=0.91,
                attributes={"ventilation_ach": 22, "pressurization": "positive"},
            ),
            DetectedRoom(
                id=f"SC-{project_id}-001",
                label="Sterile Core",
                room_type=RoomType.STERILE_CORE,
                polygon=Polygon(points=[(12, 52), (95, 52), (95, 80), (12, 80)]),
                area_sqft=320.0,
                confidence=0.88,
                attributes={"pressurization": "positive"},
            ),
            DetectedRoom(
                id=f"ICU-{project_id}-001",
                label="ICU Bay 1",
                room_type=RoomType.ICU,
                polygon=Polygon(points=[(100, 10), (140, 10), (140, 42), (100, 42)]),
                area_sqft=200.0,
                confidence=0.85,
                attributes={"ventilation_ach": 6},
            ),
            DetectedRoom(
                id=f"NS-{project_id}-001",
                label="Nurse Station A",
                room_type=RoomType.NURSE_STATION,
                polygon=Polygon(points=[(100, 45), (140, 45), (140, 70), (100, 70)]),
                area_sqft=150.0,
                confidence=0.87,
                attributes={},
            ),
        ]
        corridors = [
            DetectedCorridor(
                id=f"COR-{project_id}-001",
                polygon=Polygon(points=[(0, 82), (150, 82), (150, 95), (0, 95)]),
                width_ft=7.5,
                connects_rooms=[r.id for r in rooms],
            )
        ]
        objects = [
            DetectedObject(
                id="door-001",
                object_type=ObjectType.DOOR,
                location=(32.0, 50.0),
                room_id=f"OR-{project_id}-001",
                confidence=0.9,
            ),
            DetectedObject(
                id="vent-001",
                object_type=ObjectType.HVAC_VENT,
                location=(32.0, 15.0),
                room_id=f"OR-{project_id}-001",
                confidence=0.85,
            ),
        ]
        return BlueprintParseResult(
            project_id=project_id,
            source_filename="demo_hospital_floor.png",
            image_width=200,
            image_height=150,
            scale_ft_per_pixel=1.0,
            rooms=rooms,
            objects=objects,
            corridors=corridors,
            total_area_sqft=sum(r.area_sqft or 0 for r in rooms),
            parse_confidence=0.88,
        )
