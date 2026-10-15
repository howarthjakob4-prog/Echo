'use strict';
const {app,BrowserWindow,ipcMain,dialog,shell,session}=require('electron');
const fs=require('node:fs/promises');const path=require('node:path');const {pathToFileURL}=require('node:url');
const {validateChat,modelNames}=require('./validation.cjs');
app.setName('Echo');app.setAppUserModelId('ProjectNovaStudio.Echo');
let window,activeController;
const page=pathToFileURL(path.join(__dirname,'ui','index.html')).href;
function checkSender(event){if(!window||event.sender!==window.webContents||event.senderFrame!==window.webContents.mainFrame||event.senderFrame.url!==page)throw new Error('Untrusted request.');}
function handler(name,fn){ipcMain.handle(name,async(event,arg)=>{checkSender(event);try{return await fn(arg);}catch(e){return {error:e.name==='AbortError'?'Generation stopped.':e.message||'Echo could not finish this action.'};}});}
async function listModels(){const r=await fetch('http://127.0.0.1:11434/api/tags',{redirect:'error',signal:AbortSignal.timeout(4000)});if(!r.ok)throw new Error('The local model service returned an error.');return modelNames(await r.json());}
handler('echo:models',async()=>{try{return {models:await listModels()};}catch{return {models:[],error:'No local AI service found. Start Ollama on this PC, install a model, then refresh.'};}});
handler('echo:chat',async(payload)=>{
 const p=validateChat(payload);if(activeController)throw new Error('Echo is already answering.');
 const available=await listModels();if(!available.includes(p.model))throw new Error('Choose an installed model in Connections.');
 activeController=new AbortController();const control=activeController;const timeout=setTimeout(()=>control.abort(),180000);
 try{
  const instructions=await fs.readFile(path.join(__dirname,'echo-instructions.md'),'utf8');
  const context='Desktop mode: you can only reply with text in this application. No file, shell, browser or editor tools are provided to this chat. Do not claim to have executed code, accessed a sandbox, or controlled Roblox Studio or Unreal Engine. Produce practical code and instructions.\nTarget engine: '+p.engine+'\nTask mode: '+p.mode+'\nUser project context:\n'+p.brief;
  const r=await fetch('http://127.0.0.1:11434/api/chat',{method:'POST',redirect:'error',headers:{'Content-Type':'application/json'},signal:control.signal,body:JSON.stringify({model:p.model,stream:false,messages:[{role:'system',content:instructions+'\n\n'+context},...p.messages]})});
  if(!r.ok)throw new Error('The local model could not answer. Check that it is loaded and your PC has enough memory.');
  const v=await r.json();if(typeof v.message?.content!=='string'||!v.message.content.trim())throw new Error('The model returned no text. Try another installed chat model.');
  return {message:v.message.content};
 }finally{clearTimeout(timeout);if(activeController===control)activeController=null;}
});
handler('echo:cancel',async()=>{activeController?.abort();return {ok:true};});
handler('echo:save',async p=>{if(!p||typeof p.name!=='string'||typeof p.text!=='string'||p.text.length>4000000)throw new Error('Invalid file.');const name=path.basename(p.name).replace(/[<>:"/\\|?*\x00-\x1f]/g,'_').slice(0,120)||'echo-export.txt';const d=await dialog.showSaveDialog(window,{title:'Save Echo file',defaultPath:path.join(app.getPath('documents'),name)});if(d.canceled||!d.filePath)return {canceled:true};await fs.writeFile(d.filePath,p.text,'utf8');return {ok:true};});
handler('echo:import',async()=>{const d=await dialog.showOpenDialog(window,{title:'Open a text or code file',properties:['openFile'],filters:[{name:'Code and notes',extensions:['txt','md','json','lua','luau','cpp','h','hpp','cs','js','ts','py']}]});if(d.canceled)return {canceled:true};const file=d.filePaths[0];if((await fs.stat(file)).size>2000000)throw new Error('Choose a file smaller than 2 MB.');return {name:path.basename(file),text:await fs.readFile(file,'utf8')};});
handler('echo:workspace',async()=>{const dir=path.join(app.getPath('documents'),'Echo Workspace');await fs.mkdir(dir,{recursive:true});const err=await shell.openPath(dir);if(err)throw new Error(err);return {ok:true};});
handler('echo:shortcut',async()=>{if(process.platform!=='win32')throw new Error('Desktop shortcuts are available in the Windows app.');const target=path.join(app.getPath('desktop'),'Echo.lnk');try{await fs.access(target);return {ok:true,message:'An Echo shortcut already exists on your desktop.'};}catch{}const ok=shell.writeShortcutLink(target,'create',{target:process.execPath,cwd:path.dirname(process.execPath),icon:path.join(__dirname,'assets','echo-icon.ico'),iconIndex:0,description:'Echo — your game development companion',appUserModelId:'ProjectNovaStudio.Echo'});if(!ok)throw new Error('Windows could not create the shortcut.');return {ok:true,message:'Echo shortcut added to your Windows desktop.'};});
handler('echo:help',async()=>{await shell.openExternal('https://ollama.com/download/windows');return {ok:true};});
function createWindow(){window=new BrowserWindow({width:1280,height:900,minWidth:800,minHeight:650,title:'Echo',backgroundColor:'#101211',icon:path.join(__dirname,'assets','echo-icon.png'),autoHideMenuBar:true,webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true,webviewTag:false,webSecurity:true}});window.webContents.setWindowOpenHandler(()=>({action:'deny'}));window.webContents.on('will-navigate',(event,url)=>{if(url!==page)event.preventDefault();});window.webContents.on('will-attach-webview',event=>event.preventDefault());window.loadFile(path.join(__dirname,'ui','index.html'));window.on('closed',()=>{activeController?.abort();window=null;});}
if(!app.requestSingleInstanceLock())app.quit();else{app.on('second-instance',()=>{if(window){if(window.isMinimized())window.restore();window.focus();}});app.whenReady().then(()=>{session.defaultSession.setPermissionRequestHandler((_w,_p,cb)=>cb(false));session.defaultSession.setPermissionCheckHandler(()=>false);createWindow();});app.on('window-all-closed',()=>app.quit());}
