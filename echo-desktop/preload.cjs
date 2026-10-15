const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('echoDesktop',Object.freeze({
 models:()=>ipcRenderer.invoke('echo:models'),
 chat:(payload)=>ipcRenderer.invoke('echo:chat',payload),
 cancel:()=>ipcRenderer.invoke('echo:cancel'),
 save:(name,text)=>ipcRenderer.invoke('echo:save',{name,text}),
 importFile:()=>ipcRenderer.invoke('echo:import'),
 shortcut:()=>ipcRenderer.invoke('echo:shortcut'),
 workspace:()=>ipcRenderer.invoke('echo:workspace'),
 help:()=>ipcRenderer.invoke('echo:help')
}));
