"""
IconProcessor: einfacher Icon-Workflow mit Pillow.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


class IconProcessor:
    def _require_pillow(self):
        if Image is None:
            raise RuntimeError("Pillow ist nicht installiert. Bitte 'pip install pillow' ausfuehren.")

    def remove_background(self, image_path: str | Path):
        self._require_pillow()
        img = Image.open(image_path).convert("RGBA")
        px = img.getdata()
        new_data = []
        for r, g, b, a in px:
            if r > 245 and g > 245 and b > 245:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append((r, g, b, a))
        img.putdata(new_data)
        return img

    def resize_and_save(self, image, target_dir: str | Path, sizes: Iterable[int] = (256, 128, 64, 32, 16)):
        self._require_pillow()
        out = Path(target_dir)
        out.mkdir(parents=True, exist_ok=True)
        result_paths: list[Path] = []
        for s in sizes:
            resized = image.resize((int(s), int(s)), Image.LANCZOS)
            p = out / f"icon_{s}.png"
            resized.save(p, format="PNG")
            result_paths.append(p)
        return result_paths

    def create_ico_file(self, image, output_path: str | Path):
        self._require_pillow()
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        image.save(out, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
        return out

    def process_robot_icon(self, source_path: str | Path, output_dir: str | Path = "electron/assets"):
        img = self.remove_background(source_path)
        output = Path(output_dir)
        pngs = self.resize_and_save(img, output)
        ico = self.create_ico_file(img, output / "roboter_icon.ico")
        main_png = output / "roboter_icon.png"
        img.resize((256, 256)).save(main_png, format="PNG")
        return {
            "source": str(source_path),
            "main_png": str(main_png),
            "ico": str(ico),
            "generated_pngs": [str(p) for p in pngs],
        }
