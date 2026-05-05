const { app, BrowserWindow, session } = require("electron");

app.commandLine.appendSwitch("enable-speech-dispatcher");
app.commandLine.appendSwitch("autoplay-policy", "no-user-gesture-required");
app.commandLine.appendSwitch("use-fake-ui-for-media-stream", "false");

function createWindow() {
  const win = new BrowserWindow({
    width: 1600,
    height: 950,
    minWidth: 1200,
    minHeight: 800,
    backgroundColor: "#040816",
    title: "Matze AI Desktop",
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.loadURL("http://localhost:5173");
}

app.whenReady().then(() => {
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    if (permission === "media" || permission === "microphone") {
      callback(true);
      return;
    }
    callback(false);
  });

  session.defaultSession.setDisplayMediaRequestHandler((request, callback) => {
    callback({ video: null, audio: "loopback" });
  });

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});