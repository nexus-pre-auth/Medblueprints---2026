"""
Blueprint Ingestion Pipeline
==============================
Handles real-world file uploads before the CV engine runs.

Architects upload:  PDF · DWG · Revit export · scanned images

Pipeline:
  upload file
      ↓
  detect format (PDF / image / CAD)
      ↓
  normalize to image(s) — one per floor
      ↓
  OCR pass for room labels (Tesseract)
      ↓
  feed to CVBlueprintEngine
      ↓
  return BlueprintParseResult

Libraries:
  pypdf       — PDF text extraction + page-to-image
  Pillow      — image normalization
  pytesseract — OCR room labels from bitmap blueprints
  opencv      — image preprocessing for better OCR accuracy

DWG support requires ezdxf (optional, graceful fallback).
Revit support requires ifc-related parsing (future).
"""
import io
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageFilter, ImageEnhance
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import numpy as np
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = bool(pytesseract.get_tesseract_version())
except Exception:
    TESSERACT_AVAILABLE = False

try:
    import ezdxf
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False


SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}
SUPPORTED_FORMATS = SUPPORTED_IMAGE_EXTS | {".pdf", ".dwg", ".dxf"}

# DPI for rendering PDF pages to images (higher = more detail, slower)
PDF_RENDER_DPI = 200


class IngestionResult:
    """Output of the ingestion pipeline — ready for CVBlueprintEngine."""

    def __init__(self):
        # Use Any to avoid NameError when numpy/cv2 are not installed
        self.images: List[Any] = []                  # One per floor/page (np.ndarray when CV2 available)
        self.room_labels: List[Dict[str, str]] = []  # Per-floor OCR label maps
        self.floor_count: int = 0
        self.source_format: str = "unknown"
        self.warnings: List[str] = []
        self.metadata: Dict = {}

    def primary_image(self) -> Optional[Any]:
        return self.images[0] if self.images else None

    def primary_labels(self) -> Dict[str, str]:
        return self.room_labels[0] if self.room_labels else {}


class BlueprintIngestionPipeline:
    """
    Normalizes any blueprint file format into CV-ready images
    with OCR-extracted room labels.
    """

    def __init__(
        self,
        max_image_dimension: int = 4096,
        ocr_enabled: bool = True,
        enhance_contrast: bool = True,
    ):
        self.max_dim = max_image_dimension
        self.ocr_enabled = ocr_enabled and TESSERACT_AVAILABLE
        self.enhance_contrast = enhance_contrast
        logger.info(
            "BlueprintIngestionPipeline ready (OCR=%s, DWG=%s, PDF=%s)",
            self.ocr_enabled,
            EZDXF_AVAILABLE,
            PYPDF_AVAILABLE,
        )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def ingest(
        self,
        file_bytes: bytes,
        filename: str,
        project_id: Optional[str] = None,
    ) -> IngestionResult:
        """
        Main entry point.  Accepts raw file bytes + filename.
        Returns an IngestionResult containing normalized images and OCR labels.
        """
        result = IngestionResult()
        result.metadata["project_id"] = project_id or str(uuid.uuid4())[:12]
        result.metadata["original_filename"] = filename

        ext = Path(filename).suffix.lower()
        result.source_format = ext

        if not CV2_AVAILABLE or not PIL_AVAILABLE:
            result.warnings.append("OpenCV/Pillow not available — using empty image fallback")
            return result

        if ext in SUPPORTED_IMAGE_EXTS:
            images = self._load_image(file_bytes)
        elif ext == ".pdf":
            images = self._load_pdf(file_bytes, result)
        elif ext in (".dwg", ".dxf"):
            images = self._load_dwg(file_bytes, filename, result)
        else:
            result.warnings.append(f"Unsupported format '{ext}'. Supported: {sorted(SUPPORTED_FORMATS)}")
            return result

        if not images:
            result.warnings.append("No images could be extracted from the file")
            return result

        for img in images:
            normalized = self._normalize_image(img)
            result.images.append(normalized)

            if self.ocr_enabled:
                labels = self._extract_room_labels(normalized)
            else:
                labels = {}
            result.room_labels.append(labels)

        result.floor_count = len(result.images)
        logger.info(
            "Ingested '%s': %d floor(s), %d OCR labels (first floor)",
            filename,
            result.floor_count,
            len(result.primary_labels()),
        )
        return result

    # ------------------------------------------------------------------
    # Format loaders
    # ------------------------------------------------------------------

    def _load_image(self, file_bytes: bytes) -> List[np.ndarray]:
        arr = np.frombuffer(file_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            logger.warning("cv2.imdecode failed on image bytes")
            return []
        return [img]

    def _load_pdf(self, file_bytes: bytes, result: IngestionResult) -> List[np.ndarray]:
        if not PYPDF_AVAILABLE:
            result.warnings.append("pypdf not installed — cannot parse PDF blueprints")
            return []

        images: List[np.ndarray] = []
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            result.metadata["pdf_pages"] = len(reader.pages)

            # Attempt to extract embedded images from each page
            for page_num, page in enumerate(reader.pages):
                page_images = self._extract_images_from_pdf_page(page)
                if page_images:
                    images.extend(page_images)
                else:
                    # No embedded images — try to render page as image via pypdf
                    # pypdf doesn't render; fall back to text extraction + synthetic image
                    text = page.extract_text() or ""
                    if text.strip():
                        result.metadata[f"page_{page_num}_text"] = text[:500]
                    result.warnings.append(
                        f"Page {page_num + 1}: no raster image found. "
                        "For best results, provide a rasterized PDF or PNG export."
                    )
        except Exception as exc:
            result.warnings.append(f"PDF parsing error: {exc}")

        return images

    @staticmethod
    def _extract_images_from_pdf_page(page) -> List[np.ndarray]:
        """Extract raster images embedded in a pypdf page object."""
        images = []
        try:
            resources = page.get("/Resources")
            if resources is None:
                return []
            xobjects = resources.get("/XObject")
            if xobjects is None:
                return []
            for name in xobjects:
                obj = xobjects[name]
                if obj.get("/Subtype") == "/Image":
                    data = obj.get_data()
                    if data:
                        arr = np.frombuffer(data, dtype=np.uint8)
                        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        if img is not None:
                            images.append(img)
        except Exception:
            pass
        return images

    def _load_dwg(
        self, file_bytes: bytes, filename: str, result: IngestionResult
    ) -> List[np.ndarray]:
        """
        Parse DWG/DXF files using ezdxf.
        Renders all LINE and LWPOLYLINE entities to a raster image.
        """
        if not EZDXF_AVAILABLE:
            result.warnings.append("ezdxf not installed — cannot parse DWG/DXF files")
            return []

        ext = Path(filename).suffix.lower()
        if ext == ".dwg":
            result.warnings.append("DWG format requires conversion to DXF first (use ODA or LibreCAD)")
            return []

        try:
            doc = ezdxf.read(io.BytesIO(file_bytes))
            msp = doc.modelspace()
            return [self._render_dxf_to_image(msp)]
        except Exception as exc:
            result.warnings.append(f"DXF parse error: {exc}")
            return []

    @staticmethod
    def _render_dxf_to_image(msp, size: int = 2048) -> np.ndarray:
        """Rasterize a DXF modelspace to an OpenCV image."""
        import numpy as np

        # Collect all points to determine bounds
        all_pts: List[Tuple[float, float]] = []
        for entity in msp:
            if entity.dxftype() == "LINE":
                all_pts.append((entity.dxf.start.x, entity.dxf.start.y))
                all_pts.append((entity.dxf.end.x, entity.dxf.end.y))
            elif entity.dxftype() == "LWPOLYLINE":
                all_pts.extend(entity.get_points("xy"))

        if not all_pts:
            return np.ones((size, size, 3), dtype=np.uint8) * 240

        xs = [p[0] for p in all_pts]
        ys = [p[1] for p in all_pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(max_x - min_x, 1)
        span_y = max(max_y - min_y, 1)

        img = np.ones((size, size, 3), dtype=np.uint8) * 255

        def to_px(x, y):
            px = int((x - min_x) / span_x * (size - 40)) + 20
            py = size - int((y - min_y) / span_y * (size - 40)) - 20
            return px, py

        for entity in msp:
            if entity.dxftype() == "LINE":
                p1 = to_px(entity.dxf.start.x, entity.dxf.start.y)
                p2 = to_px(entity.dxf.end.x, entity.dxf.end.y)
                cv2.line(img, p1, p2, (50, 50, 50), 2)
            elif entity.dxftype() == "LWPOLYLINE":
                pts = list(entity.get_points("xy"))
                for i in range(len(pts) - 1):
                    p1 = to_px(pts[i][0], pts[i][1])
                    p2 = to_px(pts[i + 1][0], pts[i + 1][1])
                    cv2.line(img, p1, p2, (50, 50, 50), 2)

        return img

    # ------------------------------------------------------------------
    # Image normalization
    # ------------------------------------------------------------------

    def _normalize_image(self, img: np.ndarray) -> np.ndarray:
        """
        Normalize image for optimal CV processing:
        - Resize to max_dim (preserving aspect ratio)
        - Convert to consistent color space
        - Optional contrast enhancement
        """
        h, w = img.shape[:2]

        # Resize if too large
        if max(h, w) > self.max_dim:
            scale = self.max_dim / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # Ensure BGR (3-channel)
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        if self.enhance_contrast:
            img = self._enhance_for_cv(img)

        return img

    @staticmethod
    def _enhance_for_cv(img: np.ndarray) -> np.ndarray:
        """
        Enhance blueprint image contrast for better wall/room detection.
        Blueprint-specific: boost dark lines on light background.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced_gray = clahe.apply(gray)

        # Sharpen edges
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        sharpened = cv2.filter2D(enhanced_gray, -1, kernel)

        # Reconstruct BGR with enhanced channel
        enhanced = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)
        return enhanced

    # ------------------------------------------------------------------
    # OCR room label extraction
    # ------------------------------------------------------------------

    def _extract_room_labels(self, img: np.ndarray) -> Dict[str, str]:
        """
        Use Tesseract OCR to extract room labels from blueprint.
        Returns dict: "centroid_x,centroid_y" → "label text"

        Blueprint-specific preprocessing:
        - Threshold to isolate text
        - Remove thin lines (walls) that confuse OCR
        """
        if not TESSERACT_AVAILABLE:
            return {}

        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Threshold: white background, black text
            _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

            # Remove horizontal/vertical lines (walls)
            h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
            h_lines = cv2.morphologyEx(cv2.bitwise_not(binary), cv2.MORPH_OPEN, h_kernel)
            v_lines = cv2.morphologyEx(cv2.bitwise_not(binary), cv2.MORPH_OPEN, v_kernel)
            lines_mask = cv2.bitwise_or(h_lines, v_lines)
            text_only = cv2.bitwise_or(binary, lines_mask)

            # Tesseract data extraction with bounding boxes
            pil_img = Image.fromarray(text_only)
            data = pytesseract.image_to_data(
                pil_img,
                output_type=pytesseract.Output.DICT,
                config="--psm 11 --oem 3",
            )

            labels: Dict[str, str] = {}
            n = len(data["text"])
            for i in range(n):
                text = data["text"][i].strip()
                try:
                    conf = float(data["conf"][i])
                except (ValueError, TypeError):
                    continue
                if not text or conf < 40 or len(text) < 2:
                    continue

                # Filter out pure numbers (room numbers keep, single chars skip)
                if len(text) == 1 and not text.isdigit():
                    continue

                x = data["left"][i] + data["width"][i] // 2
                y = data["top"][i] + data["height"][i] // 2
                key = f"{x},{y}"
                labels[key] = text

            # Merge nearby labels into multi-word room names
            labels = self._merge_nearby_labels(labels, proximity=60)

            logger.debug("OCR extracted %d room labels", len(labels))
            return labels

        except Exception as exc:
            logger.warning("OCR failed: %s", exc)
            return {}

    @staticmethod
    def _merge_nearby_labels(
        labels: Dict[str, str], proximity: float = 60
    ) -> Dict[str, str]:
        """Merge adjacent OCR words into room label phrases."""
        import math
        points = []
        for key, text in labels.items():
            try:
                x, y = map(float, key.split(","))
                points.append({"x": x, "y": y, "text": text, "merged": False})
            except ValueError:
                continue

        merged: Dict[str, str] = {}
        for i, p in enumerate(points):
            if p["merged"]:
                continue
            words = [p["text"]]
            cx, cy = p["x"], p["y"]
            for j, q in enumerate(points):
                if i == j or q["merged"]:
                    continue
                dist = math.dist((p["x"], p["y"]), (q["x"], q["y"]))
                if dist < proximity and abs(p["y"] - q["y"]) < 20:
                    words.append(q["text"])
                    q["merged"] = True
            merged[f"{cx:.0f},{cy:.0f}"] = " ".join(words)

        return merged

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def get_supported_formats() -> List[str]:
        return sorted(SUPPORTED_FORMATS)

    @staticmethod
    def is_supported(filename: str) -> bool:
        return Path(filename).suffix.lower() in SUPPORTED_FORMATS
