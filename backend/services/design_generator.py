# -*- coding: utf-8 -*-
"""SVG-/Design-Generierung für CorelDRAW-kompatible Vektordateien."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

_MM_TO_PX = 96.0 / 25.4


class DesignGenerator:
    """Erzeugt SVG (optional EPS) aus JSON-Templates."""

    def __init__(
        self,
        templates_path: str,
        output_dir: str | None = None,
        svgwrite_module: Any | None = None,
    ) -> None:
        self._svgwrite = svgwrite_module
        self.templates_path = os.path.abspath(templates_path)
        try:
            with open(self.templates_path, "r", encoding="utf-8") as f:
                self.templates = json.load(f)
        except Exception:
            self.templates = {"svg_templates": {}, "brand_colors": {}}
        base = os.path.dirname(self.templates_path)
        self.output_dir = os.path.abspath(output_dir or os.path.join(base, "output", "designs"))
        os.makedirs(self.output_dir, exist_ok=True)

    def _ensure_svgwrite(self):
        if self._svgwrite is not None:
            return self._svgwrite
        import svgwrite as sw

        self._svgwrite = sw
        return sw

    @staticmethod
    def mm_to_px(mm_val: float) -> float:
        return float(mm_val) * _MM_TO_PX

    @staticmethod
    def _substitute(text: str, variables: dict[str, Any]) -> str:
        if not text or not variables:
            return text
        out = text
        for key, raw in variables.items():
            val = "" if raw is None else str(raw)
            k = str(key).strip()
            out = out.replace(f"[{k}]", val)
            out = out.replace(f"[{k.upper()}]", val)
            out = out.replace(f"[{k.lower()}]", val)
            out = out.replace(f"[{k.capitalize()}]", val)
        return out

    def _scale_coord(self, val: float, unit: str) -> float:
        if unit == "mm":
            return self.mm_to_px(val)
        return float(val)

    def generate_svg_design(
        self,
        template_type: str,
        variables: dict[str, Any] | None = None,
        width: float | None = None,
        height: float | None = None,
        content: str | None = None,
        colors: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        variables = dict(variables or {})
        if content is not None:
            variables.setdefault("content", content)
            variables.setdefault("Content", content)

        tpl_root = self.templates.get("svg_templates") or {}
        template = tpl_root.get(template_type)
        if not template:
            return {"error": f"Template {template_type!r} not found"}

        unit = str(template.get("unit") or "px")
        tw = float(width if width is not None else template.get("width") or 100)
        th = float(height if height is not None else template.get("height") or 100)

        if unit == "mm":
            width_px = self.mm_to_px(tw)
            height_px = self.mm_to_px(th)
        else:
            width_px = tw
            height_px = th

        sw = self._ensure_svgwrite()

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{template_type}_{stamp}.svg"
        filepath = os.path.join(self.output_dir, filename)

        dwg = sw.Drawing(
            filepath,
            size=(f"{width_px}px", f"{height_px}px"),
            profile="tiny",
        )
        dwg.attribs["xmlns"] = "http://www.w3.org/2000/svg"
        dwg.attribs["viewBox"] = f"0 0 {width_px} {height_px}"

        color_map = colors if isinstance(colors, dict) else {}

        for element in template.get("elements") or []:
            if not isinstance(element, dict):
                continue
            et = element.get("type")
            fill = element.get("fill", "#000000")
            stroke = element.get("stroke", "none")
            if isinstance(colors, dict):
                ei = str(element.get("id") or "")
                if ei and ei in color_map:
                    fill = color_map[ei]
                elif "fill" in color_map and et == "rect":
                    fill = color_map.get("fill", fill)

            if et == "rect":
                x = self._scale_coord(float(element.get("x", 0)), unit)
                y = self._scale_coord(float(element.get("y", 0)), unit)
                w = self._scale_coord(float(element.get("width", 100)), unit)
                h = self._scale_coord(float(element.get("height", 100)), unit)
                kw: dict[str, Any] = {"insert": (x, y), "size": (w, h), "fill": fill}
                if stroke and stroke != "none":
                    kw["stroke"] = stroke
                    kw["stroke_width"] = 0.5
                dwg.add(dwg.rect(**kw))
            elif et == "circle":
                cx = self._scale_coord(float(element.get("cx", 0)), unit)
                cy = self._scale_coord(float(element.get("cy", 0)), unit)
                r = self._scale_coord(float(element.get("r", 50)), unit)
                ckw: dict[str, Any] = {"center": (cx, cy), "r": r, "fill": fill}
                if stroke and stroke != "none":
                    ckw["stroke"] = stroke
                    ckw["stroke_width"] = 0.5
                dwg.add(dwg.circle(**ckw))
            elif et == "text":
                raw_text = str(element.get("text", ""))
                text = self._substitute(raw_text, variables)
                x = self._scale_coord(float(element.get("x", 0)), unit)
                y = self._scale_coord(float(element.get("y", 0)), unit)
                fs = float(element.get("font_size", 12))
                ff = str(element.get("font_family", "Arial"))
                weight = str(element.get("font_weight", "normal"))
                t_kw: dict[str, Any] = {
                    "insert": (x, y),
                    "fill": fill,
                    "font_size": fs,
                    "font_family": ff,
                }
                if weight and weight.lower() != "normal":
                    t_kw["font_weight"] = weight
                dwg.add(dwg.text(text, **t_kw))

        dwg.save()

        result: dict[str, Any] = {
            "status": "success",
            "file": filename,
            "path": filepath,
            "format": "SVG",
        }

        eps_path = self._try_write_eps_placeholder(filepath, width_px, height_px)
        if eps_path:
            result["eps_file"] = os.path.basename(eps_path)
            result["eps_path"] = eps_path

        return result

    def _try_write_eps_placeholder(self, svg_path: str, w_px: float, h_px: float) -> str | None:
        """Minimal-EPS über ReportLab (best effort)."""
        base = os.path.splitext(svg_path)[0] + ".eps"
        try:
            from reportlab.graphics.shapes import Drawing as RLDrawing
            from reportlab.graphics import renderPS

            # ReportLab: Ursprung unten links — nur ein leichtes Bounding-Rechteck als EPS-Rahmen
            h_pts = max(72.0, min(h_px * 72.0 / 96.0, 2000.0))
            w_pts = max(72.0, min(w_px * 72.0 / 96.0, 2000.0))
            d = RLDrawing(w_pts, h_pts)
            renderPS.drawToFile(d, base)
            return base if os.path.isfile(base) else None
        except Exception:
            return None

    def generate_design_template(
        self,
        design_type: str,
        brand_style: str = "default",
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tpl_root = self.templates.get("svg_templates") or {}
        if design_type not in tpl_root:
            return {"error": f"Design {design_type!r} not found"}

        brands = self.templates.get("brand_colors") or {}
        brand = brands.get(brand_style) or brands.get("default") or {}
        merged = dict(variables or {})
        if isinstance(brand, dict):
            merged.setdefault("brand_primary", brand.get("primary", ""))
            merged.setdefault("brand_secondary", brand.get("secondary", ""))

        return self.generate_svg_design(design_type, variables=merged)

    def get_design_templates(self) -> dict[str, Any]:
        svg_tpl = self.templates.get("svg_templates") or {}
        brands = self.templates.get("brand_colors") or {}
        details = {}
        for name, data in svg_tpl.items():
            if isinstance(data, dict):
                details[name] = {
                    "full_name": data.get("name", name),
                    "width": data.get("width"),
                    "height": data.get("height"),
                    "unit": data.get("unit"),
                }
        return {
            "svg_templates": list(svg_tpl.keys()),
            "brand_colors": list(brands.keys()),
            "template_details": details,
        }
