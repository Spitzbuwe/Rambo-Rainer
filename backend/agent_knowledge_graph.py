"""
Wissensgraph aus Dateien — Importkanten, Abfragen, Export fuer UI.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.,\s]+))\s*",
    re.MULTILINE,
)


class KnowledgeGraphEngine:
    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or ".").resolve()
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []
        self._edge_set: set[tuple[str, str, str]] = set()

    def scan_files(self, globs: tuple[str, ...] = ("**/*.py", "**/*.js", "**/*.ts")) -> list[str]:
        found: list[str] = []
        for g in globs:
            for p in self.project_root.glob(g):
                if p.is_file() and ".git" not in p.parts:
                    try:
                        rel = str(p.relative_to(self.project_root)).replace("\\", "/")
                    except ValueError:
                        rel = str(p)
                    found.append(rel)
        return sorted(set(found))

    def build_graph(self, globs: tuple[str, ...] = ("**/*.py",)) -> dict[str, Any]:
        self.nodes.clear()
        self.edges.clear()
        self._edge_set.clear()
        for rel in self.scan_files(globs):
            path = (self.project_root / Path(rel)).resolve()
            if not path.is_file():
                continue
            self.nodes[rel] = {"id": rel, "label": Path(rel).name, "type": "file"}
            if path.suffix.lower() == ".py":
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for mod in self._parse_imports(text):
                    tgt = self._resolve_module_edge(rel, mod)
                    self._add_edge(rel, tgt, "imports")

        return {"nodes": len(self.nodes), "edges": len(self.edges)}

    @staticmethod
    def _parse_imports(text: str) -> list[str]:
        mods: list[str] = []
        for m in _IMPORT_RE.finditer(text):
            a, b = m.group(1), m.group(2)
            if a:
                mods.append(a.split(".")[0])
            elif b:
                for part in b.split(","):
                    name = part.strip().split()[0].split(".")[0]
                    if name and name not in ("import",):
                        mods.append(name)
        return list(dict.fromkeys(mods))

    def _resolve_module_edge(self, source_rel: str, mod: str) -> str:
        cand = self.project_root / f"{mod}.py"
        if cand.is_file():
            try:
                return str(cand.relative_to(self.project_root)).replace("\\", "/")
            except ValueError:
                pass
        pkg = self.project_root / mod / "__init__.py"
        if pkg.is_file():
            try:
                return str(pkg.parent.relative_to(self.project_root)).replace("\\", "/") + "/__init__.py"
            except ValueError:
                pass
        return f":external:{mod}"

    def _add_edge(self, src: str, tgt: str, kind: str) -> None:
        key = (src, tgt, kind)
        if key in self._edge_set:
            return
        self._edge_set.add(key)
        self.edges.append({"source": src, "target": tgt, "type": kind})
        if tgt.startswith(":external:"):
            eid = tgt
            if eid not in self.nodes:
                self.nodes[eid] = {"id": eid, "label": tgt.split(":")[-1], "type": "external"}

    def dynamic_graph_updates(
        self,
        add_nodes: list[dict[str, Any]] | None = None,
        add_edges: list[dict[str, str]] | None = None,
        remove_edges: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        for n in add_nodes or []:
            nid = str(n.get("id", ""))
            if nid:
                self.nodes[nid] = n
        for e in add_edges or []:
            self._add_edge(str(e["source"]), str(e["target"]), str(e.get("type", "dynamic")))
        for a, b in remove_edges or []:
            self.edges = [x for x in self.edges if not (x["source"] == a and x["target"] == b)]
        return {"nodes": len(self.nodes), "edges": len(self.edges)}

    def graph_queries(self, node_id: str, mode: str = "neighbors") -> dict[str, Any]:
        if mode == "neighbors":
            outs = [e for e in self.edges if e["source"] == node_id]
            ins = [e for e in self.edges if e["target"] == node_id]
            return {"node": node_id, "outgoing": outs, "incoming": ins}
        if mode == "degree":
            deg_out = sum(1 for e in self.edges if e["source"] == node_id)
            deg_in = sum(1 for e in self.edges if e["target"] == node_id)
            return {"node": node_id, "out_degree": deg_out, "in_degree": deg_in}
        return {"error": "unknown_mode", "node": node_id}

    def visualization_export(self) -> dict[str, Any]:
        return {
            "format": "cytoscape-json-lite",
            "nodes": [{"data": {"id": k, "label": v.get("label", k)}} for k, v in self.nodes.items()],
            "edges": [
                {"data": {"id": f"{e['source']}->{e['target']}", "source": e["source"], "target": e["target"]}}
                for e in self.edges
            ],
        }

    def _reverse_dependent_files(self, rel_path: str) -> set[str]:
        rel_path = rel_path.strip().replace("\\", "/")
        affected: set[str] = set()
        stack = [rel_path]
        while stack:
            cur = stack.pop()
            for e in self.edges:
                if e["target"] == cur and e["source"] not in affected:
                    if not str(e["source"]).startswith(":"):
                        affected.add(e["source"])
                        stack.append(e["source"])
        return affected

    def impact_analysis(self, file_or_symbol: str) -> dict[str, Any]:
        key = file_or_symbol.strip().replace("\\", "/")
        if "::" in key:
            fp, sym = key.split("::", 1)
            fp, sym = fp.strip(), sym.strip()
            base = sorted(self._reverse_dependent_files(fp))
            if not sym:
                return {"changed": key, "file": fp, "symbol": "", "reverse_dependents": base}
            hits: list[str] = []
            for n in base:
                p = self.project_root / n
                if not p.is_file():
                    continue
                try:
                    body = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if sym in body:
                    hits.append(n)
            return {
                "changed": key,
                "file": fp,
                "symbol": sym,
                "reverse_dependents": hits if hits else base,
            }
        return {
            "changed": key,
            "reverse_dependents": sorted(self._reverse_dependent_files(key)),
        }

    def health(self) -> dict[str, Any]:
        return {"module": "agent_knowledge_graph", "class": "KnowledgeGraphEngine", "ok": True}

    def describe(self) -> str:
        return "KnowledgeGraphEngine"


def get_instance(project_root: Path | str | None = None) -> KnowledgeGraphEngine:
    return KnowledgeGraphEngine(project_root)


__all__ = ["KnowledgeGraphEngine", "get_instance"]
