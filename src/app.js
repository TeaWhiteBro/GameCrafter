import {worlds,discWorlds} from './worlds.js';
import {createPanorama} from './panorama.js';
import {createDiorama} from './diorama.js';
const $=s=>document.querySelector(s);
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;document.body.dataset.reducedMotion=reduced;
const requestedCase=new URLSearchParams(location.search).get('scene');
let diorama=null,resultCase=worlds.find(w=>w.id===requestedCase)||worlds[0],activity='exploration',media={};
const baseModalityNote=$('.modality-note').textContent;
const worldSelector=$('#world-selector');
const panorama=createPanorama({canvas:$('#panorama-canvas'),poster:$('#panorama-poster'),status:$('#panorama-status'),loadButton:$('#panorama-load'),resetButton:$('#panorama-reset')});
window.worldCrafterPanorama=panorama;
discWorlds.forEach((w,i)=>{
 const button=document.createElement('button');button.type='button';button.role='tab';button.style.setProperty('--case-color',w.color);button.innerHTML=`<i></i>${w.short}`;button.setAttribute('aria-selected',String(i===0));button.classList.toggle('active',i===0);button.addEventListener('click',()=>diorama?.select(i));worldSelector.append(button);
});
worlds.forEach((w,i)=>{
 const tab=document.createElement('button');tab.type='button';tab.role='tab';tab.textContent=w.short;tab.classList.toggle('active',i===0);tab.setAttribute('aria-selected',String(i===0));tab.addEventListener('click',()=>renderResults(w));$('#result-tabs').append(tab);
});
function setActive(i){const w=discWorlds[i];$('#world-index').textContent=`${String(i+1).padStart(2,'0')} / ${String(discWorlds.length).padStart(2,'0')}`;$('#world-name').textContent=w.name;$('#world-description').textContent=w.description;[...worldSelector.children].forEach((b,j)=>{b.classList.toggle('active',i===j);b.setAttribute('aria-selected',String(i===j));});}
const canvas=$('#world-canvas');
createDiorama({canvas,worlds:discWorlds,onActive:setActive,onProgress:p=>{$('#loading-label').textContent=`Preparing the worlds · ${Math.round(p*100)}%`;}}).then(d=>{diorama=d;const requestedIndex=discWorlds.findIndex(w=>w.id===requestedCase);if(requestedIndex>=0)d.select(requestedIndex);$('#loading').classList.add('done');updatePause();window.worldCrafter={state:()=>d.state(),select:i=>d.select(i),view:v=>d.setView(v),overview:v=>d.setOverview(v),pause:v=>{d.setPaused(v);updatePause();},worlds:discWorlds.map(w=>w.id)};}).catch(error=>{console.error('Diorama initialization failed',error);$('#loading').classList.add('done');$('#webgl-fallback').hidden=false;});
function updatePause(){const paused=diorama?.paused;$('#spin-toggle').textContent=paused?'▶':'Ⅱ';$('#spin-toggle').setAttribute('aria-label',paused?'Resume rotation':'Pause rotation');}
$('#spin-toggle').addEventListener('click',()=>{if(diorama)diorama.setPaused(!diorama.paused);updatePause();});$('#reset-view').addEventListener('click',()=>diorama?.reset());
$('#view-toggle').addEventListener('click',()=>{if(!diorama)return;diorama.setOverview(!diorama.overview);$('#view-toggle').textContent=diorama.overview?'Focus view':'Overview';$('#view-toggle').setAttribute('aria-label',diorama.overview?'Return to the close perspective view':`Show all ${discWorlds.length} sectors from above`);});
worldSelector.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();let i=[...worldSelector.children].indexOf(document.activeElement);i=e.key==='Home'?0:e.key==='End'?discWorlds.length-1:(i+(e.key==='ArrowRight'?1:-1)+discWorlds.length)%discWorlds.length;worldSelector.children[i].focus();diorama?.select(i);});

const details=[
 ['A shared world specification','The design agent turns intent into a GameSpec: player and Boss roles, a visual direction, a combat space, and a connected exploration map. Map planning defines destinations, branching routes, scale, and collision clearances before scene construction.'],
 ['Assets with a purpose','The asset agent decides what requires a distinctive generated mesh and what should be built parametrically. gpt-image-2 develops visual references; Tripo generates characters and selected buildings or plants. Source receipts preserve provenance and support interrupted jobs.'],
 ['Geometry and characters','Blender prepares meshes, checks unwanted surface bridges and anatomy, preserves or creates rigs, and validates deformation. The scene agent constructs terrain, roads, architecture, and a corresponding structural whitebox.'],
 ['A coherent playable world','Unreal Engine integrates the scene and characters, retargets motion, and handles lighting, PBR materials, collision, exploration, and Boss combat. The same game supports first-person, third-person, and isometric cameras.'],
 ['Review the actual result','Visual review examines current scene renders. Playtests check movement, facing, contact, and camera behavior. Capture checks validate frame pairing, projection, depth, labels, and the structural whitebox. Failures return to the responsible stage for a bounded repair and recheck.']
];
function setStep(i){[...$('#workflow-steps').querySelectorAll('button')].forEach((b,j)=>{b.classList.toggle('active',i===j);b.setAttribute('aria-pressed',String(i===j));});$('#step-detail').innerHTML=`<h3>${details[i][0]}</h3><p>${details[i][1]}</p>`;}
$('#workflow-steps').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>setStep(Number(b.dataset.step))));setStep(0);

function enlarge(src,caption){$('#dialog-image').src=src;$('#dialog-image').alt=caption;$('#dialog-caption').textContent=caption;$('#image-dialog').showModal();}
$('#close-dialog').onclick=()=>$('#image-dialog').close();$('#image-dialog').addEventListener('click',e=>{if(e.target===$('#image-dialog'))$('#image-dialog').close();});
function imageFigure(src,label){const figure=document.createElement('figure'),img=document.createElement('img');img.src=src;img.alt=label;img.loading='lazy';img.tabIndex=0;img.addEventListener('click',()=>enlarge(src,label));img.addEventListener('keydown',e=>{if(e.key==='Enter')enlarge(src,label);});const caption=document.createElement('figcaption');caption.textContent=label;figure.append(img,caption);return figure;}
function setMainMedia(prefix,record,poster){
 const video=$(`#${prefix}-video`),img=$(`#${prefix}-poster`),wrap=video.parentElement;
 video.pause();video.onplay=null;video.removeAttribute('src');video.load();img.classList.remove('gone');img.src=poster;video.poster=poster;
 let play=wrap.querySelector('.media-play');
 if(!play){play=document.createElement('button');play.type='button';play.className='media-play';wrap.append(play);}
 play.hidden=!record?.rgb;play.textContent=`▶  Play ${prefix==='explore'?'exploration':'Boss combat'}`;
 if(record?.rgb){
  video.src=record.rgb;video.onplay=()=>{img.classList.add('gone');play.hidden=true;};
  const start=()=>{play.textContent='Loading…';video.play().catch(()=>{play.hidden=false;play.textContent='▶  Retry playback';});};
  play.onclick=start;img.onclick=start;
 }else{play.onclick=null;img.onclick=()=>enlarge(poster,`${resultCase.name} ${prefix}`);}
}
function renderResults(w){resultCase=w;const data=media[w.id]||{};document.querySelectorAll('#result-tabs button').forEach((b,i)=>{const active=worlds[i].id===w.id;b.classList.toggle('active',active);b.setAttribute('aria-selected',String(active));});$('#result-style').textContent=w.style;$('#result-title').textContent=w.name;$('#result-prompt').textContent=`“${w.prompt}”`;
 document.querySelectorAll('#results video').forEach(v=>v.pause());
 const legacy=Boolean(data.legacy);$('#legacy-result').hidden=!legacy;$('#gameplay-layout').hidden=legacy;$('#gameplay-layout').style.display=legacy?'none':'';const legacyVideo=$('#legacy-video');if(legacy){legacyVideo.src=data.legacy;legacyVideo.poster=data.preview;$('#activity-switch').hidden=true;activity='combat';}else{legacyVideo.removeAttribute('src');legacyVideo.load();$('#activity-switch').hidden=false;setMainMedia('explore',data.sessions?.exploration_third,data.gameplayPosters?.exploration||data.sessions?.exploration_third?.poster||data.preview);setMainMedia('combat',data.sessions?.combat_third,data.gameplayPosters?.combat||data.sessions?.combat_third?.poster||data.preview);}
 panorama.select({url:data.miniature?.model,name:w.name,preview:data.preview});
 $('.modality-note').textContent=baseModalityNote+(data.captureNote?' '+data.captureNote:'');
 renderCameras();renderModalities();
}
function renderCameras(){const data=media[resultCase.id]||{};const container=$('#camera-grid');container.replaceChildren();for(const [key,label]of[['first','First person'],['third','Third person'],['isometric','2.5D / Isometric']]){const session=`${activity}_${key}`,src=data.cameras?.[session]||data.sessions?.[session]?.poster||data.preview;if(src)container.append(imageFigure(src,label));}$('#activity-switch').querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.activity===activity));}
function renderModalities(){const data=media[resultCase.id]||{},container=$('#modalities-grid');container.replaceChildren();for(const [key,label]of[['rgb','RGB'],['depth','Depth'],['skeleton','Skeleton'],['semantics','Semantics'],['whitebox','Whitebox']]){const src=(data.alignedByActivity?.[activity]||data.aligned)?.[key];if(src)container.append(imageFigure(src,label));}container.hidden=!container.children.length;}
$('#activity-switch').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{activity=b.dataset.activity;renderCameras();renderModalities();}));
fetch('src/media.json').then(r=>{if(!r.ok)throw new Error('Media manifest not found');return r.json();}).then(m=>{media=m;renderResults(resultCase);}).catch(e=>{console.error(e);$('#result-prompt').textContent='The media manifest could not be loaded. Start this page with the included local server.';});
const videoObserver=new IntersectionObserver(entries=>entries.forEach(entry=>{const video=entry.target;if(!entry.isIntersecting)video.pause();}),{threshold:.15});document.querySelectorAll('video').forEach(v=>videoObserver.observe(v));
document.addEventListener('visibilitychange',()=>{if(document.hidden)document.querySelectorAll('video').forEach(v=>v.pause());});
