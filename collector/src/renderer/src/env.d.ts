/// <reference types="vite/client" />

import type { CollectorAPI } from '../../preload/index'

declare global {
  interface Window {
    collector: CollectorAPI
    electron: {
      ipcRenderer: import('electron').IpcRenderer
    }
  }
}
