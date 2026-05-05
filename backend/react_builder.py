"""
ReactBuilder: generiert React-Komponenten und einfache App-Strukturen.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ReactSpec:
    app_name: str = "RainerApp"
    component_name: str = "GeneratedComponent"
    include_state: bool = True
    include_effect: bool = False
    include_api_call: bool = False
    include_form: bool = False
    include_validation: bool = False
    endpoint: str = "/api/health"


class ReactBuilder:
    def _normalize(self, spec: dict[str, Any] | None) -> ReactSpec:
        s = spec or {}
        return ReactSpec(
            app_name=str(s.get("app_name") or "RainerApp"),
            component_name=str(s.get("component_name") or "GeneratedComponent"),
            include_state=bool(s.get("include_state", True)),
            include_effect=bool(s.get("include_effect", False)),
            include_api_call=bool(s.get("include_api_call", False)),
            include_form=bool(s.get("include_form", False)),
            include_validation=bool(s.get("include_validation", False)),
            endpoint=str(s.get("endpoint") or "/api/health"),
        )

    def build_component(self, spec: dict[str, Any] | None = None) -> str:
        cfg = self._normalize(spec)
        imports = ["import React"]
        hooks = []
        if cfg.include_state:
            hooks.append("useState")
        if cfg.include_effect:
            hooks.append("useEffect")
        if hooks:
            imports[0] += ", { " + ", ".join(hooks) + " }"
        imports[0] += " from 'react';"

        state_block = "  const [value, setValue] = useState('');\n" if cfg.include_state else ""
        effect_block = ""
        if cfg.include_effect:
            effect_block = (
                "  useEffect(() => {\n"
                "    // Initialisierung beim Mount\n"
                "  }, []);\n"
            )
        api_block = ""
        if cfg.include_api_call:
            api_block = (
                "  async function loadData() {\n"
                f"    const response = await fetch('{cfg.endpoint}');\n"
                "    const data = await response.json();\n"
                "    console.log(data);\n"
                "  }\n"
            )
        form_block = ""
        if cfg.include_form:
            validator = "return true;"
            if cfg.include_validation:
                validator = "return String(value || '').trim().length >= 3;"
            form_block = (
                "  function isValid() {\n"
                f"    {validator}\n"
                "  }\n\n"
                "  function onSubmit(e) {\n"
                "    e.preventDefault();\n"
                "    if (!isValid()) return;\n"
                "    console.log('submitted', value);\n"
                "  }\n"
            )

        jsx_form = ""
        if cfg.include_form:
            jsx_form = (
                "      <form onSubmit={onSubmit}>\n"
                "        <input value={value} onChange={(e) => setValue(e.target.value)} placeholder=\"Eingabe\" />\n"
                "        <button type=\"submit\">Speichern</button>\n"
                "      </form>\n"
            )

        jsx_button = "      <button onClick={loadData}>API laden</button>\n" if cfg.include_api_call else ""

        return (
            "\n".join(imports)
            + "\n\n"
            + f"export default function {cfg.component_name}() {{\n"
            + state_block
            + effect_block
            + api_block
            + form_block
            + "  return (\n"
            + "    <section>\n"
            + f"      <h2>{cfg.component_name}</h2>\n"
            + jsx_form
            + jsx_button
            + "    </section>\n"
            + "  );\n"
            + "}\n"
        )

    def build_app_structure(self, spec: dict[str, Any] | None = None) -> dict[str, str]:
        cfg = self._normalize(spec)
        component_code = self.build_component(spec)
        component_file = f"src/components/{cfg.component_name}.jsx"
        app_code = (
            "import React from 'react';\n"
            f"import {cfg.component_name} from './components/{cfg.component_name}';\n\n"
            "export default function App() {\n"
            "  return (\n"
            "    <main>\n"
            f"      <h1>{cfg.app_name}</h1>\n"
            f"      <{cfg.component_name} />\n"
            "    </main>\n"
            "  );\n"
            "}\n"
        )
        index_code = (
            "import React from 'react';\n"
            "import { createRoot } from 'react-dom/client';\n"
            "import App from './App';\n\n"
            "createRoot(document.getElementById('root')).render(<App />);\n"
        )
        return {
            "package.json": (
                '{\n'
                f'  "name": "{cfg.app_name.lower()}",\n'
                '  "private": true,\n'
                '  "scripts": { "dev": "vite", "build": "vite build" },\n'
                '  "dependencies": { "react": "^18.0.0", "react-dom": "^18.0.0" }\n'
                '}\n'
            ),
            "src/App.jsx": app_code,
            component_file: component_code,
            "src/main.jsx": index_code,
            "index.html": "<!doctype html><html><body><div id='root'></div><script type='module' src='/src/main.jsx'></script></body></html>\n",
        }
