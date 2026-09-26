import os
import uuid

from PIL import Image

from config import config

CELL_SIZE = 400
PADDING = 20
BG_COLOR = (255, 255, 255)


def build_collage(photo_paths: list[str]) -> str | None:
    """Возвращает путь к коллажу (относительно static/), либо None."""
    if not photo_paths:
        return None

    n = len(photo_paths)
    cols = min(n, 3)
    rows = (n + cols - 1) // cols

    canvas_w = cols * CELL_SIZE + (cols + 1) * PADDING
    canvas_h = rows * CELL_SIZE + (rows + 1) * PADDING
    canvas = Image.new("RGB", (canvas_w, canvas_h), BG_COLOR)

    for idx, path in enumerate(photo_paths):
        try:
            img = Image.open(path).convert("RGB")
        except FileNotFoundError:
            continue
        img.thumbnail((CELL_SIZE, CELL_SIZE))
        col = idx % cols
        row = idx // cols
        x = PADDING + col * (CELL_SIZE + PADDING) + (CELL_SIZE - img.width) // 2
        y = PADDING + row * (CELL_SIZE + PADDING) + (CELL_SIZE - img.height) // 2
        canvas.paste(img, (x, y))

    os.makedirs(config.collages_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    out_path = os.path.join(config.collages_dir, filename)
    canvas.save(out_path, quality=90)
    return out_path
