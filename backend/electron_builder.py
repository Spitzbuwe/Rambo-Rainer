"""
ElectronBuilder: erzeugt Main/Preload/Package fuer Desktop-Apps.
"""
from __future__ import annotations

from typing import Any


class ElectronBuilder:
    def _cfg(self, spec: dict[str, Any] | None = None) -> dict[str, Any]:
        s = spec or {}
        return {
            "app_name": str(s.get("app_name") or "Rambo-Rainer"),
            "backend_port": int(s.get("backend_port") or 5002),
            "icon_png": str(s.get("icon_png") or "assets/roboter_icon.png"),
            "icon_ico": str(s.get("icon_ico") or "assets/roboter_icon.ico"),
        }

    def build_main_process(self, spec: dict[str, Any] | None = None) -> str:
        c = self._cfg(spec)
        return f"""const {{ app, BrowserWindow, ipcMain }} = require('electron');
const path = require('path');
const {{ spawn }} = require('child_process');

let mainWindow = null;
let backendProcess = null;
const backendPort = {c["backend_port"]};

function startBackend() {{
  const backendDir = path.join(__dirname, '..', 'rambo_builder_local', 'backend');
  backendProcess = spawn('python', ['main.py'], {{ cwd: backendDir, stdio: 'pipe' }});
}}

function createWindow() {{
  mainWindow = new BrowserWindow({{
    width: 1300,
    height: 900,
    icon: path.join(__dirname, '{c["icon_png"]}'),
    webPreferences: {{
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }}
  }});
  mainWindow.loadFile(path.join(__dirname, '..', 'rambo_ui', 'build', 'index.html'));
}}

app.whenReady().then(() => {{
  startBackend();
  createWindow();
}});

app.on('window-all-closed', () => {{
  if (backendProcess) backendProcess.kill();
  if (process.platform !== 'darwin') app.quit();
}});

ipcMain.handle('api-call', async (_event, endpoint, method, payload) => {{
  const response = await fetch(`http://127.0.0.1:${{backendPort}}${{endpoint}}`, {{
    method: method || 'GET',
    headers: {{ 'Content-Type': 'application/json' }},
    body: payload ? JSON.stringify(payload) : undefined
  }});
  return response.json();
}});
"""

    def build_preload(self, spec: dict[str, Any] | None = None) -> str:
        _ = self._cfg(spec)
        return """const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  apiCall: (endpoint, method = 'GET', data = null) =>
    ipcRenderer.invoke('api-call', endpoint, method, data),
  switchMode: (mode) => ipcRenderer.send('switch-mode', mode),
  getMode: () => ipcRenderer.invoke('get-mode'),
  onModeChanged: (cb) => ipcRenderer.on('mode-changed', (_e, mode) => cb(mode)),
});
"""

    def build_package_json(self, spec: dict[str, Any] | None = None) -> str:
        c = self._cfg(spec)
        return (
            "{\n"
            f'  "name": "{str(c["app_name"]).lower().replace(" ", "-")}",\n'
            '  "version": "1.0.0",\n'
            '  "main": "main.js",\n'
            '  "scripts": {\n'
            '    "build": "electron-builder --dir",\n'
            '    "start": "electron .",\n'
            '    "build:win": "electron-builder --win"\n'
            "  },\n"
            '  "devDependencies": {\n'
            '    "electron": "^31.0.0",\n'
            '    "electron-builder": "^24.0.0"\n'
            "  },\n"
            '  "build": {\n'
            '    "appId": "com.rambo.rainer",\n'
            f'    "productName": "{c["app_name"]}",\n'
            '    "win": {\n'
            f'      "icon": "{c["icon_ico"]}"\n'
            "    }\n"
            "  }\n"
            "}\n"
        )

    def build_complete_app(self, spec: dict[str, Any] | None = None) -> dict[str, str]:
        c = self._cfg(spec)
        return {
            "electron/main.js": self.build_main_process(c),
            "electron/preload.js": self.build_preload(c),
            "electron/package.json": self.build_package_json(c),
        }
