import{build}from'vite';import fs from'node:fs/promises';import path from'node:path';import{fileURLToPath}from'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
await build({configFile:false,root,base:'./',build:{outDir:'ui',emptyOutDir:true,assetsInlineLimit:15000000,minify:true,rollupOptions:{input:path.join(root,'index.html')}}});
let html=await fs.readFile(path.join(root,'ui/index.html'),'utf8');
const js=html.match(/<script[^>]*src="([^\"]+)"[^>]*><\/script>/)?.[1];const css=html.match(/<link[^>]*href="([^\"]+\.css)"[^>]*>/)?.[1];if(!js||!css)throw Error('Missing bundled assets');
const code=await fs.readFile(path.join(root,'ui',js),'utf8');const styles=await fs.readFile(path.join(root,'ui',css),'utf8');
let single=html.replace(/<script[^>]*src="[^\"]+"[^>]*><\/script>/,()=>'<script type="module">'+code.replace(/<\/script/gi,'<\\/script')+'</script>').replace(/<link[^>]*href="[^\"]+\.css"[^>]*>/,()=>'<style>'+styles+'</style>');
single=single.replace("script-src 'self'","script-src 'self' 'unsafe-inline'");const out=path.resolve(root,'../outputs');await fs.mkdir(out,{recursive:true});await fs.writeFile(path.join(out,'Echo-Offline.html'),single);
