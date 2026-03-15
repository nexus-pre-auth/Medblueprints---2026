"""
Sample Blueprint Generator
============================
Draws a realistic hospital floor plan as a PNG that the CV engine
can actually process — walls, rooms, corridors, labels.

Output: data/sample_blueprints/sample_hospital_floor.png

Run:
  python scripts/generate_sample_blueprint.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import cv2
    import numpy as np
except ImportError:
    print("OpenCV not installed. Run: pip install opencv-python-headless numpy")
    sys.exit(1)

OUTPUT_PATH = Path("data/sample_blueprints/sample_hospital_floor.png")

# Canvas: 1200 x 900 pixels, white background
W, H = 1200, 900
WALL_COLOR = (30, 30, 30)       # near-black walls
BG_COLOR = (245, 245, 245)      # off-white background
LABEL_COLOR = (60, 60, 60)
DOOR_COLOR = (120, 120, 200)
DIM_COLOR = (150, 150, 150)
WALL_THICKNESS = 6
INNER_WALL = 4

# Each room: (label, x1, y1, x2, y2, fill_color_BGR)
ROOMS = [
    # Operating suite
    ("OR 101",        50,  50, 280, 260, (230, 245, 255)),
    ("OR 102",       285,  50, 515, 260, (230, 245, 255)),
    ("Sterile Core",  50, 265, 515, 390, (220, 255, 220)),

    # ICU cluster
    ("ICU Bay 1",    530,  50, 710, 200, (255, 240, 220)),
    ("ICU Bay 2",    715,  50, 895, 200, (255, 240, 220)),
    ("ICU Bay 3",    530, 205, 710, 355, (255, 240, 220)),
    ("ICU Bay 4",    715, 205, 895, 355, (255, 240, 220)),
    ("Nurse Station A", 900, 50, 1150, 200, (245, 220, 255)),

    # ED / Emergency
    ("ED Trauma 1",   50, 430, 240, 580, (255, 230, 230)),
    ("ED Trauma 2",  245, 430, 435, 580, (255, 230, 230)),
    ("ED Waiting",   440, 430, 720, 580, (240, 240, 255)),

    # Imaging
    ("MRI Suite",    730, 430, 960, 580, (240, 255, 250)),
    ("CT Scanner",   965, 430, 1150, 580, (240, 255, 250)),

    # Support
    ("Pharmacy",      50, 620, 280, 840, (255, 255, 220)),
    ("Lab",          285, 620, 515, 840, (220, 255, 255)),
    ("Nurse Station B", 520, 620, 730, 840, (245, 220, 255)),
    ("Mechanical",   735, 620, 900, 840, (210, 210, 210)),
    ("Utility",      905, 620, 1150, 840, (215, 215, 215)),
]

# Corridors: horizontal and vertical spines
CORRIDORS = [
    # Main horizontal corridor connecting OR suite and ICU
    (50,  395, 1150, 428),
    # Main horizontal corridor connecting ED and imaging
    (50,  585, 1150, 618),
    # Vertical spine
    (520,  50,  528, 840),
    (900,  50,  910, 618),
]

# Doors: (x, y, horizontal=True/False)
DOORS = [
    (165, 390, True),   # OR 101 → corridor
    (400, 390, True),   # OR 102 → corridor
    (282, 265, False),  # Between ORs
    (620, 395, True),   # ICU Bay 1/2 → corridor
    (800, 395, True),   # ICU Bay 3/4 → corridor
    (1025, 395, True),  # Nurse station A → corridor
    (140, 585, True),   # ED Trauma 1 → corridor
    (340, 585, True),   # ED Trauma 2 → corridor
    (580, 585, True),   # ED Waiting → corridor
    (845, 585, True),   # MRI → corridor
    (1057, 585, True),  # CT → corridor
    (165, 618, True),   # Pharmacy → corridor
    (400, 618, True),   # Lab → corridor
    (625, 618, True),   # Nurse B → corridor
    (817, 618, True),   # Mechanical → corridor
]

FONT = cv2.FONT_HERSHEY_SIMPLEX


def draw_blueprint():
    img = np.full((H, W, 3), BG_COLOR, dtype=np.uint8)

    # Draw corridor fills first
    for (x1, y1, x2, y2) in CORRIDORS:
        cv2.rectangle(img, (x1, y1), (x2, y2), (200, 210, 200), -1)

    # Draw room fills and borders
    for label, x1, y1, x2, y2, fill in ROOMS:
        cv2.rectangle(img, (x1, y1), (x2, y2), fill, -1)
        cv2.rectangle(img, (x1, y1), (x2, y2), WALL_COLOR, WALL_THICKNESS)

    # Draw corridor outlines
    for (x1, y1, x2, y2) in CORRIDORS:
        cv2.rectangle(img, (x1, y1), (x2, y2), (100, 120, 100), 2)

    # Draw doors as small arcs/gaps in walls
    for (dx, dy, horiz) in DOORS:
        door_w = 30
        door_color_bg = BG_COLOR
        if horiz:
            # Gap in horizontal wall
            cv2.rectangle(img, (dx - door_w//2, dy - 4), (dx + door_w//2, dy + 4), (200, 200, 200), -1)
            cv2.line(img, (dx - door_w//2, dy - 8), (dx - door_w//2, dy + 8), DOOR_COLOR, 2)
            cv2.line(img, (dx + door_w//2, dy - 8), (dx + door_w//2, dy + 8), DOOR_COLOR, 2)
            # Door swing arc hint
            cv2.ellipse(img, (dx - door_w//2, dy), (door_w, door_w), 0, -30, 30, DOOR_COLOR, 1)
        else:
            cv2.rectangle(img, (dx - 4, dy - door_w//2), (dx + 4, dy + door_w//2), (200, 200, 200), -1)
            cv2.line(img, (dx - 8, dy - door_w//2), (dx + 8, dy - door_w//2), DOOR_COLOR, 2)
            cv2.line(img, (dx - 8, dy + door_w//2), (dx + 8, dy + door_w//2), DOOR_COLOR, 2)
            cv2.ellipse(img, (dx, dy - door_w//2), (door_w, door_w), 90, -30, 30, DOOR_COLOR, 1)

    # Draw room labels
    for label, x1, y1, x2, y2, _ in ROOMS:
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        room_w = x2 - x1
        room_h = y2 - y1

        # Scale font to room size
        font_scale = max(0.28, min(0.55, room_w / 420))
        thickness = 1

        # Multi-line if label is long
        words = label.split()
        if len(words) > 2 and room_h > 80:
            line1 = " ".join(words[:2])
            line2 = " ".join(words[2:])
            (tw1, th1), _ = cv2.getTextSize(line1, FONT, font_scale, thickness)
            (tw2, th2), _ = cv2.getTextSize(line2, FONT, font_scale, thickness)
            cv2.putText(img, line1, (cx - tw1//2, cy - th1//2 - 2), FONT, font_scale, LABEL_COLOR, thickness, cv2.LINE_AA)
            cv2.putText(img, line2, (cx - tw2//2, cy + th2//2 + 4), FONT, font_scale, LABEL_COLOR, thickness, cv2.LINE_AA)
        else:
            (tw, th), _ = cv2.getTextSize(label, FONT, font_scale, thickness)
            cv2.putText(img, label, (cx - tw//2, cy + th//2), FONT, font_scale, LABEL_COLOR, thickness, cv2.LINE_AA)

    # Add corridor labels
    cv2.putText(img, "Main Surgical Corridor", (530, 415), FONT, 0.32, (80, 100, 80), 1, cv2.LINE_AA)
    cv2.putText(img, "Emergency/Imaging Corridor", (530, 608), FONT, 0.32, (80, 100, 80), 1, cv2.LINE_AA)

    # Dimension lines (look like a real blueprint)
    _draw_dimension(img, 50, 20, 515, 20, "OR Suite  465 ft")
    _draw_dimension(img, 530, 20, 895, 20, "ICU Cluster  365 ft")
    _draw_dimension(img, 20, 50, 20, 390, "3 floors")

    # Title block
    cv2.rectangle(img, (0, H - 55), (W, H), (220, 220, 220), -1)
    cv2.line(img, (0, H - 55), (W, H - 55), WALL_COLOR, 2)
    cv2.putText(img, "MEDBLUEPRINTS SAMPLE — General Hospital, 2nd Floor — Scale 1:100",
                (20, H - 28), FONT, 0.45, (40, 40, 40), 1, cv2.LINE_AA)
    cv2.putText(img, "PRELIMINARY — FOR COMPLIANCE REVIEW ONLY",
                (20, H - 10), FONT, 0.35, (150, 50, 50), 1, cv2.LINE_AA)

    return img


def _draw_dimension(img, x1, y1, x2, y2, label):
    cv2.line(img, (x1, y1), (x2, y2), DIM_COLOR, 1)
    cv2.line(img, (x1, y1 - 5), (x1, y1 + 5), DIM_COLOR, 1)
    cv2.line(img, (x2, y2 - 5), (x2, y2 + 5), DIM_COLOR, 1)
    mx, my = (x1 + x2) // 2, (y1 + y2) // 2
    (tw, th), _ = cv2.getTextSize(label, FONT, 0.3, 1)
    cv2.putText(img, label, (mx - tw//2, my - 4), FONT, 0.3, DIM_COLOR, 1, cv2.LINE_AA)


if __name__ == "__main__":
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    img = draw_blueprint()
    cv2.imwrite(str(OUTPUT_PATH), img)
    print(f"Sample blueprint saved: {OUTPUT_PATH}")
    print(f"  Size: {img.shape[1]}x{img.shape[0]} px")
    print(f"  Rooms drawn: {len(ROOMS)}")
    print(f"  Corridors: {len(CORRIDORS)}")
    print(f"  Doors: {len(DOORS)}")
    print()
    print("Test with:")
    print(f"  curl -s -X POST http://localhost:8000/api/v1/jobs/analyze \\")
    print(f"    -F 'file=@{OUTPUT_PATH}' \\")
    print(f"    -F 'facility_type=hospital' | python -m json.tool")
