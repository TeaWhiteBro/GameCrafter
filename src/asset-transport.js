import {Texture} from 'three';
import {DRACOLoader} from 'three/addons/loaders/DRACOLoader.js';
import manifest from './portable-manifest.json';

// Anonymous project-page hosts may isolate the document with an opaque origin.
// Use permitted classic-script delivery for public assets in that environment.
// No credentials, external asset host, or changes to the host sandbox are needed.
export const opaqueOrigin=globalThis.origin==='null';
const jobs=new Map(),queue=[];
let active=0;
const MAX_CONCURRENT=3;

globalThis.__gameCrafterAsset=(key,payload)=>{
  const job=jobs.get(key);
  if(job&&!job.received){job.received=true;job.payload=payload;}
};

async function unpack(job){
  if(!job.received)throw Error('Asset response was incomplete: '+job.key);
  const text=atob(job.payload);job.payload=null;
  const compressed=new Uint8Array(text.length);
  for(let i=0;i<text.length;i++)compressed[i]=text.charCodeAt(i);
  if(typeof DecompressionStream==='undefined')throw Error('This browser cannot decompress the 3D assets. Please use a current browser.');
  const stream=new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'));
  const bytes=await new Response(stream).arrayBuffer();
  if(bytes.byteLength!==job.entry.bytes)throw Error('Asset length mismatch: '+job.key);
  if(globalThis.crypto?.subtle){
    const digest=await crypto.subtle.digest('SHA-256',bytes);
    const hash=Array.from(new Uint8Array(digest),x=>x.toString(16).padStart(2,'0')).join('');
    if(hash!==job.entry.sha256)throw Error('Asset integrity mismatch: '+job.key);
  }
  return bytes;
}

function drain(){
  while(active<MAX_CONCURRENT&&queue.length){
    const job=queue.shift();active++;
    const script=document.createElement('script');script.async=true;
    let settled=false;
    const finish=(error,bytes)=>{
      if(settled)return;settled=true;clearTimeout(timer);script.remove();
      job.payload=null;jobs.delete(job.key);active--;drain();
      if(error)job.reject(error);else job.resolve(bytes);
    };
    const timer=setTimeout(()=>finish(Error('Asset download timed out: '+job.key)),180000);
    script.onload=()=>unpack(job).then(bytes=>finish(null,bytes),finish);
    script.onerror=()=>finish(Error('Asset could not load: '+job.key));
    // crossorigin or SRI here would require the CORS header this host omits.
    script.src=job.entry.script;document.head.append(script);
  }
}

export function readPortable(key){
  const existing=jobs.get(key);if(existing)return existing.promise;
  const entry=manifest[key];
  if(!entry)return Promise.reject(Error('Unregistered display asset: '+key));
  const job={key,entry,received:false,payload:null};
  job.promise=new Promise((resolve,reject)=>Object.assign(job,{resolve,reject}));
  jobs.set(key,job);queue.push(job);drain();return job.promise;
}

export function loadGltf(loader,path){
  return opaqueOrigin?readPortable(path).then(bytes=>loader.parseAsync(bytes,'')):loader.loadAsync(path);
}

export function loadTexture(loader,path,onError=console.warn){
  if(!opaqueOrigin)return loader.load(path,undefined,undefined,onError);
  const texture=new Texture();
  readPortable(path).then(bytes=>{
    const url=URL.createObjectURL(new Blob([bytes],{type:'image/jpeg'}));
    const image=new Image();
    image.onload=()=>{texture.image=image;texture.needsUpdate=true;URL.revokeObjectURL(url);};
    image.onerror=()=>{URL.revokeObjectURL(url);onError(Error('Texture decoding failed: '+path));};
    image.src=url;
  }).catch(onError);
  return texture;
}

export class CompatibleDRACOLoader extends DRACOLoader{
  _loadLibrary(file,type){
    if(!opaqueOrigin)return super._loadLibrary(file,type);
    return readPortable(this.decoderPath+file).then(bytes=>type==='text'?new TextDecoder().decode(bytes):bytes);
  }
}
