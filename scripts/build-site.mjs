// Build classic scripts and lossless asset transports for opaque-origin sandboxes.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {gzipSync,gunzipSync} from 'node:zlib';
import {createRequire} from 'node:module';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const out=path.join(root,'assets/portable');
const manifestFile=path.join(root,'src/portable-manifest.json');
const sha=b=>createHash('sha256').update(b).digest('hex');
const writeChanged=async(file,data)=>{
  const bytes=Buffer.isBuffer(data)?data:Buffer.from(data);
  const old=await fs.readFile(file).catch(()=>null);
  if(!old?.equals(bytes))await fs.writeFile(file,bytes);
};
if(process.argv.includes('--verify')){
  const manifest=JSON.parse(await fs.readFile(manifestFile,'utf8'));
  for(const [name,entry] of Object.entries(manifest)){
    const script=await fs.readFile(path.join(root,entry.script),'utf8');
    // Parse the transport as data; never execute a generated asset script in Node.
    const match=script.match(/^globalThis\.__gameCrafterAsset\(("[^"\n]+"),\s*(\[[\s\S]*\])\.join\(""\)\);\s*$/);
    if(!match||JSON.parse(match[1])!==name)throw Error('Invalid asset envelope: '+name);
    const decoded=gunzipSync(Buffer.from(JSON.parse(match[2]).join(''),'base64'));
    const source=await fs.readFile(path.join(root,name));
    if(!decoded.equals(source)||decoded.length!==entry.bytes||sha(decoded)!==entry.sha256)throw Error('Asset mismatch: '+name);
  }
  console.log(`Verified ${Object.keys(manifest).length} lossless asset transports.`);
  process.exit(0);
}
await fs.mkdir(out,{recursive:true});
const modelNames=(await fs.readdir(path.join(root,'assets/models'))).filter(n=>n.endsWith('.glb')).map(n=>'assets/models/'+n);
const textureNames=(await fs.readdir(path.join(root,'assets/images'))).filter(n=>/^texture_.*\.jpg$/.test(n)).map(n=>'assets/images/'+n);
const decoderRoot='vendor/three/examples/jsm/libs/draco/gltf/';
const names=[...modelNames,...textureNames,...['draco_decoder.js','draco_wasm_wrapper.js','draco_decoder.wasm'].map(n=>decoderRoot+n)].sort();
const manifest={};
let total=0;
for(const name of names){
  const bytes=await fs.readFile(path.join(root,name));
  const hash=sha(bytes),script='assets/portable/'+sha(Buffer.from(name+'\0'+hash)).slice(0,24)+'.js';
  const packed=gzipSync(bytes,{level:6}).toString('base64');
  const chunks=packed.match(/.{1,65536}/g)||[];
  const envelope=`globalThis.__gameCrafterAsset(${JSON.stringify(name)},[\n${chunks.map(c=>JSON.stringify(c)).join(',\n')}\n].join(""));\n`;
  await writeChanged(path.join(root,script),envelope);
  manifest[name]={script,bytes:bytes.length,sha256:hash};total+=Buffer.byteLength(envelope);
}
await writeChanged(manifestFile,JSON.stringify(manifest,null,2)+'\n');
const require=createRequire(import.meta.url);
const esbuild=require('esbuild');
await esbuild.build({
  absWorkingDir:root,entryPoints:['src/site-entry.js'],outfile:'src/site.bundle.js',
  bundle:true,format:'iife',platform:'browser',target:['es2020'],minify:true,
  sourcemap:false,legalComments:'eof',logLevel:'warning',
  plugins:[{name:'bundled-three',setup(build){
    build.onResolve({filter:/^three$/},()=>({path:path.join(root,'vendor/three/build/three.module.js')}));
    build.onResolve({filter:/^three\/addons\//},args=>({path:path.join(root,'vendor/three/examples/jsm',args.path.slice('three/addons/'.length))}));
  }}]
});
console.log(`Built classic entry and ${names.length} portable assets (${(total/1048576).toFixed(1)} MiB).`);
