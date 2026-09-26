import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {loadGltf,CompatibleDRACOLoader} from './asset-transport.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';

// One lazy renderer serves all result scenes. No frame loop runs off screen.
export function createPanorama({canvas,poster,status,loadButton,resetButton}) {
 let renderer,scene,camera,controls,model,displayBounds,fitSize={width:50,height:50},selection,token=0,visible=false,disposed=false,loading=false;
 const draco=new CompatibleDRACOLoader().setDecoderPath('vendor/three/examples/jsm/libs/draco/gltf/');draco.setWorkerLimit(2);
 const loader=new GLTFLoader().setDRACOLoader(draco),center=new THREE.Vector3();
 function render(){if(renderer&&visible&&!disposed)renderer.render(scene,camera);}
 function init(){
  if(renderer)return;
  renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false,powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.setClearColor(0xeceee8);renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.98;renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  scene=new THREE.Scene();scene.add(new THREE.HemisphereLight(0xfff5e4,0x718a83,1.25));
  const key=new THREE.DirectionalLight(0xfff5e8,2.5);key.position.set(-30,65,40);key.castShadow=true;key.shadow.mapSize.set(2048,2048);Object.assign(key.shadow.camera,{left:-40,right:40,top:40,bottom:-40,near:1,far:160});key.shadow.normalBias=.025;key.shadow.bias=-.00015;scene.add(key);
  const fill=new THREE.DirectionalLight(0xc9e2ff,.65);fill.position.set(20,10,-12);scene.add(fill);
  camera=new THREE.OrthographicCamera(-30,30,25,-25,.05,500);
  controls=new OrbitControls(camera,canvas);controls.enableDamping=false;controls.minZoom=.5;controls.maxZoom=8;controls.maxPolarAngle=Math.PI*.48;controls.screenSpacePanning=true;
  controls.addEventListener('change',render);resize();
 }
 function resize(){if(!renderer)return;const w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;renderer.setSize(w,h,false);const aspect=w/h,span=Math.max(fitSize.height,fitSize.width/aspect)*1.12;camera.left=-span*aspect/2;camera.right=span*aspect/2;camera.top=span/2;camera.bottom=-span/2;camera.updateProjectionMatrix();render();}
 function reset(){
  if(!camera||!displayBounds)return;camera.zoom=1;const direction=new THREE.Vector3(19,34,25).normalize();camera.position.copy(center).addScaledVector(direction,100);camera.lookAt(center);camera.updateMatrixWorld(true);
  // Fit projected geometry, not empty corners of a loose world-axis box.
  const projected=new THREE.Box3(),point=new THREE.Vector3(),matrix=new THREE.Matrix4();
  model.traverse(o=>{const positions=o.geometry?.attributes.position;if(!positions||!o.visible)return;matrix.multiplyMatrices(camera.matrixWorldInverse,o.matrixWorld);for(let i=0;i<positions.count;i++){point.fromBufferAttribute(positions,i).applyMatrix4(matrix);projected.expandByPoint(point);}});
  fitSize={width:projected.max.x-projected.min.x,height:projected.max.y-projected.min.y};
  const shift=new THREE.Vector3((projected.min.x+projected.max.x)/2,(projected.min.y+projected.max.y)/2,0).applyQuaternion(camera.quaternion),target=center.clone().add(shift);camera.position.add(shift);
  controls.target.copy(target);controls.update();resize();render();
 }
 function release(root){const geo=new Set(),mat=new Set(),tex=new Set();root.traverse(o=>{if(o.geometry)geo.add(o.geometry);for(const m of (Array.isArray(o.material)?o.material:[o.material]))if(m){mat.add(m);for(const v of Object.values(m))if(v?.isTexture)tex.add(v);}});geo.forEach(x=>x.dispose());mat.forEach(x=>x.dispose());tex.forEach(x=>x.dispose());}
 function clear(){if(!model)return;scene.remove(model);release(model);model=null;}
 async function load(){
  if(!selection?.url||loading)return;const current=++token,requested=selection;loading=true;loadButton.hidden=true;status.textContent='Loading the authored scene…';
  try{
   init();const g=await loadGltf(loader,requested.url);if(current!==token||disposed){release(g.scene);return;}
   clear();model=g.scene;model.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});model.updateMatrixWorld(true);const box=new THREE.Box3().setFromObject(model),size=box.getSize(new THREE.Vector3()),c=box.getCenter(new THREE.Vector3());
   const scale=46/Math.max(size.x,size.z);model.scale.multiplyScalar(scale);model.position.sub(new THREE.Vector3(c.x,box.min.y,c.z).multiplyScalar(scale));scene.add(model);
   model.updateMatrixWorld(true);displayBounds=new THREE.Box3().setFromObject(model);displayBounds.getCenter(center);poster.hidden=true;canvas.hidden=false;resetButton.hidden=false;status.textContent='Drag to orbit · Scroll or pinch to zoom · Right-drag to pan';
   canvas.setAttribute('aria-label',`Interactive miniature of ${requested.name}`);reset();resize();
  }catch(error){if(current!==token||disposed)return;console.error('Scene miniature failed',error);status.textContent='The miniature could not load. Try again.';loadButton.textContent='Retry 3D miniature';loadButton.hidden=false;}
  finally{if(current===token)loading=false;}
 }
 loadButton.addEventListener('click',load);resetButton.addEventListener('click',reset);
 canvas.addEventListener('keydown',e=>{if(e.key==='Home'){e.preventDefault();reset();}if(['+','=','-'].includes(e.key)&&camera){e.preventDefault();camera.zoom=THREE.MathUtils.clamp(camera.zoom*(e.key==='-'?.89:1.12),.5,8);camera.updateProjectionMatrix();render();}});
 const resizeObserver=new ResizeObserver(resize);resizeObserver.observe(canvas.parentElement);
 const observer=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible)render();},{threshold:.05});observer.observe(canvas.parentElement);
 return {
  select({url,name,preview}){token++;loading=false;selection={url,name,preview};clear();canvas.hidden=true;poster.hidden=false;poster.src=preview;poster.alt=`${name} overview`;loadButton.hidden=!url;loadButton.textContent='Explore 3D miniature';resetButton.hidden=true;status.textContent='Rotate and inspect the full authored map';},
  state(){return {case:selection?.name,loaded:Boolean(model),loading,triangles:renderer?.info.render.triangles||0,drawCalls:renderer?.info.render.calls||0,camera:camera?.position.toArray(),zoom:camera?.zoom,visible};},
  dispose(){disposed=true;token++;clear();controls?.dispose();draco.dispose();renderer?.dispose();observer.disconnect();resizeObserver.disconnect();}
 };
}
