"""
TemplateLibrary: zentrale Vorlagen fuer generierte Dateien.
"""
from __future__ import annotations


class TemplateLibrary:
    REACT_COMPONENT_TEMPLATE = """import React from 'react';

export default function {component_name}() {{
  return (
    <section>
      <h2>{component_name}</h2>
    </section>
  );
}}
"""

    ELECTRON_MAIN_TEMPLATE = """const { app, BrowserWindow } = require('electron');
const path = require('path');

function createWindow() {{
  const win = new BrowserWindow({{
    width: 1200,
    height: 800,
    webPreferences: {{ preload: path.join(__dirname, 'preload.js') }}
  }});
  win.loadFile('{start_file}');
}}

app.whenReady().then(createWindow);
"""

    ELECTRON_PRELOAD_TEMPLATE = """const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('electronAPI', {{
  apiCall: (endpoint, method, data) => ipcRenderer.invoke('api-call', endpoint, method, data)
}});
"""

    ELECTRON_PACKAGE_JSON_TEMPLATE = """{{
  "name": "{app_name}",
  "version": "1.0.0",
  "main": "main.js",
  "scripts": {{
    "start": "electron .",
    "build:win": "electron-builder --win"
  }}
}}
"""

    PYTHON_SCRIPT_TEMPLATE = '''"""
{description}
"""

def main():
    print("{message}")

if __name__ == "__main__":
    main()
'''

    _MAP = {
        "react_component": REACT_COMPONENT_TEMPLATE,
        "electron_main": ELECTRON_MAIN_TEMPLATE,
        "electron_preload": ELECTRON_PRELOAD_TEMPLATE,
        "electron_package_json": ELECTRON_PACKAGE_JSON_TEMPLATE,
        "python_script": PYTHON_SCRIPT_TEMPLATE,
    }

    @classmethod
    def get_template(cls, template_type: str) -> str:
        return cls._MAP.get(str(template_type or "").lower(), "")

    @classmethod
    def fill_template(cls, template_type: str, **kwargs) -> str:
        template = cls.get_template(template_type)
        if not template:
            return ""
        try:
            return template.format(**kwargs)
        except Exception:
            return template
