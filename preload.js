// ============================================
// MediScan AI — Preload Script
// Provides secure IPC bridge between main & renderer
// ============================================
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // --- File Operations ---
  openFileDialog: () => ipcRenderer.invoke('open-file-dialog'),
  openFolderDialog: () => ipcRenderer.invoke('open-folder-dialog'),
  saveDialog: (defaultName) => ipcRenderer.invoke('save-dialog', defaultName),
  readFile: (filePath) => ipcRenderer.invoke('read-file', filePath),

  // --- App Info ---
  getAppInfo: () => ipcRenderer.invoke('get-app-info'),

  // --- Python Backend ---
  runPython: (scriptName, args) => ipcRenderer.invoke('run-python', scriptName, args),

  // --- File Save ---
  saveFile: (filePath, base64Data) => ipcRenderer.invoke('save-file', filePath, base64Data),

  // --- Python Dependency Check ---
  checkPythonDeps: () => ipcRenderer.invoke('check-python-deps'),

  // --- Config Sync ---
  readConfig: () => ipcRenderer.invoke('read-config'),
  writeConfig: (data) => ipcRenderer.invoke('write-config', data),

  // --- Model Archive (per patient) ---
  listPatientModels: (patientId) => ipcRenderer.invoke('list-patient-models', patientId),
  archiveModel: (patientId, modelName, sourceWeightPath, meta) => ipcRenderer.invoke('archive-model', patientId, modelName, sourceWeightPath, meta),

  // --- Window Controls ---
  minimizeWindow: () => ipcRenderer.send('minimize-window'),
  maximizeWindow: () => ipcRenderer.send('maximize-window'),
  closeWindow: () => ipcRenderer.send('close-window'),

  // --- Event Listeners (Main → Renderer) ---
  on: (channel, callback) => {
    const validChannels = [
      'files-opened',
      'folder-opened',
      'dataset-export',
      'navigate',
      'action',
      'open-settings',
      'python-output',
    ];
    if (validChannels.includes(channel)) {
      const subscription = (_event, ...args) => callback(...args);
      ipcRenderer.on(channel, subscription);
      // Return cleanup function
      return () => ipcRenderer.removeListener(channel, subscription);
    }
  },
});