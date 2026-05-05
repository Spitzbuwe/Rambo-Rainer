from pathlib import Path
import tempfile

from main import build_written_result_detail


def test_build_written_result_detail_includes_content_for_text_file():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "analyse.md"
        p.write_text("# Analyse\n\n- Punkt A\n- Punkt B\n", encoding="utf-8")
        detail = build_written_result_detail(p, "data/auto/analyse.md")
        assert "Hier ist was ich gefunden habe:" in detail
        assert "Punkt A" in detail
        assert "data/auto/analyse.md" in detail


def test_build_written_result_detail_skips_binary_like_extensions():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "image.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n")
        detail = build_written_result_detail(p, "data/auto/image.png")
        assert detail == ""
