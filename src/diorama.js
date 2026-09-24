import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone } from 'three/addons/utils/SkeletonUtils.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const TAU=Math.PI*2;
const matCache=new Map();
function material(color,roughness=.85,metalness=0){const key=color+'|'+roughness+'|'+metalness;if(!matCache.has(key))matCache.set(key,new THREE.MeshStandardMaterial({color,roughness,metalness}));return matCache.get(key);}
function mesh(geo,mat,parent,x=0,y=0,z=0){const m=new THREE.Mesh(geo,mat);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;}
function box(parent,w,h,d,x,y,z,color){return mesh(new THREE.BoxGeometry(w,h,d),typeof color==='string'?material(color):color,parent,x,y,z);}
function cylinder(parent,r1,r2,h,x,y,z,color,segments=32){return mesh(new THREE.CylinderGeometry(r1,r2,h,segments),typeof color==='string'?material(color):color,parent,x,y,z);}
function torus(parent,r,t,x,y,z,color,arc=TAU){return mesh(new THREE.TorusGeometry(r,t,8,64,arc),typeof color==='string'?material(color):color,parent,x,y,z);}
function rng(seed){return()=>{seed|=0;seed=seed+0x6d2b79f5|0;let t=Math.imul(seed^seed>>>15,1|seed);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}

export async function createDiorama({canvas,worlds,onActive,onProgress}){
 const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:true,powerPreference:'high-performance'});
 renderer.setPixelRatio(Math.min(devicePixelRatio,1.65));renderer.setClearColor(0xf6f4ef,0);renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.1;
 const scene=new THREE.Scene();
 const wideCamera=new THREE.OrthographicCamera(-10,10,6,-6,.1,100);wideCamera.position.set(0,10.5,15);wideCamera.lookAt(0,.3,0);
 const focusCamera=new THREE.PerspectiveCamera(46,1,.1,100);focusCamera.position.set(0,4.4,10.5);focusCamera.lookAt(0,.85,3.3);
 let camera=focusCamera,overview=false;
 const pmrem=new THREE.PMREMGenerator(renderer);const room=new RoomEnvironment();scene.environment=pmrem.fromScene(room,.06).texture;scene.environmentIntensity=.43;room.dispose();pmrem.dispose();
 scene.add(new THREE.HemisphereLight(0xfff8e8,0x87959b,1.25));
 const sun=new THREE.DirectionalLight(0xfff4e6,2.25);sun.position.set(-5,12,8);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);Object.assign(sun.shadow.camera,{left:-10,right:10,top:10,bottom:-10,near:.5,far:35});sun.shadow.normalBias=.025;sun.shadow.bias=-.0002;sun.shadow.radius=4;scene.add(sun);
 const fill=new THREE.DirectionalLight(0xe2eeff,.6);fill.position.set(5,5,-6);scene.add(fill);
 const floor=mesh(new THREE.PlaneGeometry(100,100),new THREE.ShadowMaterial({opacity:.13}),scene,0,-.87,0);floor.rotation.x=-Math.PI/2;floor.castShadow=false;
 const root=new THREE.Group();scene.add(root);
 const N=worlds.length,step=TAU/N,R=6.2,half=step/2-.006;
 const loader=new GLTFLoader();const textureLoader=new THREE.TextureLoader();const assetCache=new Map();const characters=[];const moving=[];const groups=[];const failures=[];
 const stoneMap=textureLoader.load('assets/images/texture_stone.jpg');stoneMap.colorSpace=THREE.SRGBColorSpace;stoneMap.wrapS=stoneMap.wrapT=THREE.RepeatWrapping;stoneMap.repeat.set(.48,.48);stoneMap.anisotropy=4;
 function masonry(color){const m=material(color,.89);m.map=stoneMap;return m;}
 let completed=0;
 async function loadModel(key){if(assetCache.has(key))return assetCache.get(key);const promise=loader.loadAsync(`assets/models/${key}.glb`).then(g=>g.scene).catch(e=>{failures.push(key);console.warn('Model unavailable',key,e);return null;});assetCache.set(key,promise);return promise;}
 async function putAsset(parent,key,height,x,z,yaw=0,y=0,fit={}){
  const src=await loadModel(key);if(!src)return null;
  const ob=clone(src);ob.updateMatrixWorld(true);const bounds=new THREE.Box3().setFromObject(ob);const size=bounds.getSize(new THREE.Vector3());const center=bounds.getCenter(new THREE.Vector3());
  const s=Math.min(height/size.y,(fit.width||Infinity)/size.x,(fit.depth||Infinity)/size.z);const pivot=new THREE.Group();parent.add(pivot);ob.scale.multiplyScalar(s);ob.position.sub(new THREE.Vector3(center.x,bounds.min.y,center.z).multiplyScalar(s));pivot.add(ob);pivot.position.set(x,y,z);pivot.rotation.y=yaw;
  // A display pose is applied in world space so different bind-pose axes cannot leave T-poses.
  if(key.includes('player')||key.includes('boss')){
   pivot.updateWorldMatrix(true,true);const q=pivot.getWorldQuaternion(new THREE.Quaternion());
   const bones={};ob.traverse(b=>{if(b.isBone)bones[b.name]=b;});
   for(const [a,b,d]of[['L_Upperarm','L_Forearm',[.28,-.90,.22]],['R_Upperarm','R_Forearm',[-.28,-.90,.22]],['L_Forearm','L_Hand',[.12,-.72,.63]],['R_Forearm','R_Hand',[-.12,-.72,.63]]]){
    if(!bones[a]||!bones[b])continue;const bone=bones[a];pivot.updateWorldMatrix(true,true);
    const v=bones[b].getWorldPosition(new THREE.Vector3()).sub(bone.getWorldPosition(new THREE.Vector3())).normalize();
    const target=new THREE.Vector3(...d).normalize().applyQuaternion(q);const delta=new THREE.Quaternion().setFromUnitVectors(v,target);
    const world=bone.getWorldQuaternion(new THREE.Quaternion());const inv=bone.parent.getWorldQuaternion(new THREE.Quaternion()).invert();bone.quaternion.copy(inv.multiply(delta).multiply(world));
   }
   pivot.updateWorldMatrix(true,true);
  }
  ob.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;o.frustumCulled=false;const mats=Array.isArray(o.material)?o.material:[o.material];for(const m of mats){if(key==='cyberpunk_corner_shophouse')m.color.set('#9baac5');if(m.map)m.map.anisotropy=4;m.envMapIntensity=.5;}}});
  return pivot;
 }
 function wedgeShape(radius){const s=new THREE.Shape();s.moveTo(0,0);for(let i=0;i<=80;i++){const a=-half+2*half*i/80;s.lineTo(Math.sin(a)*radius,Math.cos(a)*radius);}s.lineTo(0,0);return s;}
 function terrainFor(world){
  const peak=(x,z,cx,cz,rx,rz)=>Math.exp(-(((x-cx)/rx)**2+((z-cz)/rz)**2));
  return(x,z)=>{
   const r=Math.hypot(x,z),angle=Math.abs(Math.atan2(x,z));
   const rim=THREE.MathUtils.smoothstep(R-r,0,.65)*THREE.MathUtils.smoothstep(half-angle,0,.15)*THREE.MathUtils.smoothstep(r,0,.8);
   let h=0;
   switch(world.miniature){
    case 'sakura':h=.53*peak(x,z,0,2.25,1.7,1.4)+.27*peak(x,z,-1.85,4.05,.8,1.0)+.18*peak(x,z,1.9,4.2,.8,1);break;
    case 'abyssal':h=.15*peak(x,z,0,2.8,1.6,1.2)+.11*peak(x,z,2.1,4.8,.7,.9);break;
    case 'neon':h=.25*peak(x,z,0,2.3,1.8,1.2)+.16*peak(x,z,1.65,4.0,.7,1.2);break;
    case 'cloister':h=.43*peak(x,z,0,2.25,1.8,1.5)+.21*peak(x,z,-1.8,4.1,.7,1.1);break;
    case 'desert':h=.30*peak(x,z,0,2.3,1.65,1.45)+.48*peak(x,z,2.15,4.75,.75,1.2)+.24*peak(x,z,-2.25,4.2,.75,1.05);break;
    case 'snow':h=.55*peak(x,z,0,2.35,1.7,1.5)+.37*peak(x,z,2.0,4.0,.8,1.3)+.18*peak(x,z,-2.0,3.85,.65,.9);break;
    default:h=.35*peak(x,z,0,2.5,1.8,1.4);
   }
   return rim*h;
  };
 }
 function terrainGeometry(height){
  const nr=48,na=40,positions=[],uvs=[],indices=[];
  for(let ir=0;ir<=nr;ir++)for(let ia=0;ia<=na;ia++){
   const r=R*ir/nr,a=-half+2*half*ia/na,x=Math.sin(a)*r,z=Math.cos(a)*r;
   positions.push(x,height(x,z),z);uvs.push(x/2.8,z/2.8);
  }
  for(let ir=0;ir<nr;ir++)for(let ia=0;ia<na;ia++){const a=ir*(na+1)+ia,b=a+1,c=a+na+1,d=c+1;indices.push(a,c,b,b,c,d);}
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.setAttribute('uv',new THREE.Float32BufferAttribute(uvs,2));geometry.setIndex(indices);geometry.computeVertexNormals();return geometry;
 }
 function wedge(parent,world){
  const s=wedgeShape(R);
  const body=new THREE.ExtrudeGeometry(s,{depth:.66,bevelEnabled:true,bevelSegments:3,steps:1,bevelSize:.045,bevelThickness:.045,curveSegments:64});
  const m=mesh(body,[material(world.edge),material(world.edge)],parent,0,-.055,0);m.rotation.x=Math.PI/2;
  const topGeo=terrainGeometry(parent.userData.terrain);
  const texture=textureLoader.load(`assets/images/texture_${world.texture}.jpg`);texture.wrapS=texture.wrapT=THREE.RepeatWrapping;texture.colorSpace=THREE.SRGBColorSpace;texture.anisotropy=4;
  const topmat=new THREE.MeshStandardMaterial({color:world.ground,map:texture,roughness:world.miniature==='neon'?.55:.96,side:THREE.DoubleSide});
  mesh(topGeo,topmat,parent,0,.012,0);
  // A narrow edge band gives all scenes a shared display base.
  const arc=new THREE.CatmullRomCurve3(Array.from({length:65},(_,i)=>{let a=-half+2*half*i/64;return new THREE.Vector3(R*Math.sin(a),-.57,R*Math.cos(a));}));
  mesh(new THREE.TubeGeometry(arc,64,.019,6,false),material('#e2d8c4',.5,.25),parent);
 }
 function pathTiles(g,color='#b5b2a2',seed=4,curve=0,tileMaterial=null){const random=rng(seed);for(let j=0;j<9;j++){const z=2.0+j*.43,cx=curve*Math.sin(j*.4);for(let i=-1;i<=1;i++){const t=box(g,.47,.055,.37,cx+i*.51,.04,z,tileMaterial||masonry(color));t.rotation.y=(random()-.5)*.065;}}}
 function stoneArch(parent,x,z,scale=1,color='#9a9d8b',yaw=0){
  const g=new THREE.Group();g.position.set(x,0,z);g.rotation.y=yaw;g.scale.setScalar(scale);parent.add(g);
  const stone=masonry(color);
  for(const side of [-1,1])for(let j=0;j<5;j++)box(g,.24,.235,.3,side*.56,.13+j*.24,0,stone);
  for(let j=0;j<13;j++){let a=j*Math.PI/12;let m=box(g,.2,.29,.34,Math.cos(a)*.56,1.07+Math.sin(a)*.56,0,stone);m.rotation.z=a-Math.PI/2;}
  for(const side of [-1,1]){box(g,.37,.12,.45,side*.56,.06,0,stone);box(g,.33,.09,.37,side*.56,.92,0,stone);}return g;
 }
 function column(parent,x,z,h,color){const m=masonry(color);cylinder(parent,.16,.2,h,x,h/2,z,m,24);for(const [y,r] of [[.07,.26],[h-.07,.24]])cylinder(parent,r,r,.13,x,y,z,m,24);}
 function rocks(parent,seed,color,count=14){const random=rng(seed);for(let i=0;i<count;i++){const angle=(random()-.5)*step*.85,r=3.2+random()*2.6;const x=Math.sin(angle)*r,z=Math.cos(angle)*r;if(Math.abs(x)<1.2)continue;const a=.08+random()*.17;const rock=mesh(new THREE.DodecahedronGeometry(a,1),masonry(color),parent,x,a*.45,z);rock.scale.set(1.3,.6,.95);rock.rotation.set(random(),random(),random());}}
 function shrubs(parent,seed,color,count=16){const random=rng(seed);for(let i=0;i<Math.ceil(count*.22);i++){const a=(random()-.5)*step*.86,r=3.2+random()*2.7,x=Math.sin(a)*r,z=Math.cos(a)*r;if(Math.abs(x)<1.1)continue;const ob=mesh(new THREE.SphereGeometry(.06+random()*.06,9,6),material(color),parent,x,.025,z);ob.scale.set(1.2,.45,1);}}
 function lantern(g,x,z){box(g,.13,.53,.13,x,.3,z,'#5e594d');box(g,.29,.08,.29,x,.6,z,'#69675a');box(g,.22,.19,.22,x,.69,z,new THREE.MeshStandardMaterial({color:'#eed4a3',emissive:'#f9bd65',emissiveIntensity:.35,roughness:.7}));let roof=cylinder(g,0,.25,.16,x,.86,z,'#5e6254',4);roof.rotation.y=Math.PI/4;}
 async function buildSakura(g){
  pathTiles(g,'#bcc1b1',10,.2);
  await Promise.all([putAsset(g,'vermilion_shrine_landmark',2.6,0,2.7,Math.PI),putAsset(g,'cherry_full_bloom',2.4,-2.1,3.8,.5),putAsset(g,'cherry_full_bloom',2.05,2.05,3.8,-.5)]);
  const gate=new THREE.Group();gate.position.z=3.7;gate.scale.setScalar(1.13);g.add(gate);
  const vermilion='#985040';for(const x of [-.84,.84]){box(gate,.12,1.35,.13,x,.73,0,vermilion);box(gate,.2,.1,.23,x,1.27,0,vermilion);}box(gate,2, .1,.2,0,1.47,0,'#493d34');box(gate,1.85,.09,.13,0,1.23,0,vermilion);
  lantern(g,-1.55,4.62);lantern(g,1.62,4.76);rocks(g,6,'#858f80',22);shrubs(g,7,'#677a48',30);
 }
 async function buildNeon(g){
  const dark='#273e51';pathTiles(g,'#526371',8,-.12);
  await Promise.all([putAsset(g,'cyberpunk_corner_shophouse',3.0,-.22,2.65,Math.PI*.86),putAsset(g,'cyberpunk_hover_interceptor',.56,-2.38,4.7,Math.PI*.2)]);
  for(const x of [-1.95,1.95]){box(g,.12,1.85,.12,x,.98,3.8,dark);const m=new THREE.MeshStandardMaterial({color:x<0?'#dc91d4':'#8edcdf',emissive:x<0?'#ce379c':'#25becd',emissiveIntensity:2});box(g,.07,1.22,.075,x,1.02,3.86,m);box(g,.4,.08,.15,x,1.85,3.8,dark);}
  for(let i=0;i<8;i++){box(g,.055,.015,.23,-.94,.085,3.0+i*.31,'#99b5b7');box(g,.055,.015,.23,.92,.085,3.0+i*.31,'#b5a55e');}
  for(const [x,c]of[[-1.5,0xc654cc],[1.45,0x34c5dd]]){const light=new THREE.PointLight(c,3,4,2);light.position.set(x,1.1,3.6);g.add(light);}
  const sign=new THREE.Group();g.add(sign);sign.position.set(.65,1.7,1.95);box(sign,.32,.9,.1,0,0,0,'#203047');for(let i=0;i<4;i++){box(sign,.18,.06,.025,0,.27-i*.18,.068,new THREE.MeshStandardMaterial({color:'#f6c2da',emissive:'#ff58bc',emissiveIntensity:2}));}
  function neonSign(label,width,height,x,y,z,color){const c=document.createElement('canvas');c.width=512;c.height=192;const ctx=c.getContext('2d');ctx.fillStyle='#121b32';ctx.fillRect(0,0,512,192);ctx.strokeStyle=color;ctx.lineWidth=9;ctx.strokeRect(8,8,496,176);ctx.font='bold 85px Arial';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle=color;ctx.fillText(label,256,101);const map=new THREE.CanvasTexture(c);map.colorSpace=THREE.SRGBColorSpace;const m=new THREE.MeshStandardMaterial({map,emissiveMap:map,emissive:'#ffffff',emissiveIntensity:1.3,roughness:.5});box(g,width+.04,height+.04,.1,x,y,z-.03,'#1c2940');mesh(new THREE.PlaneGeometry(width,height),m,g,x,y,z+.025);}
  neonSign('NOVA',1.6,.38,-.30,1.45,4.19,'#57e8e3');neonSign('08',.5,.36,.85,2.7,3.8,'#ee7bca');
 }
 async function buildCloister(g){
  pathTiles(g,'#c9bf9e',25,.13);
  const m='#c7b792';const dark='#85694d';const hall=new THREE.Group();hall.position.set(0,0,2.8);hall.scale.setScalar(1.3);g.add(hall);
  box(hall,2.05,1.15,.62,0,.63,-.1,masonry(m));for(let i=-1;i<=1;i++){const a=stoneArch(hall,i*.61,.29,.48,m);a.position.y=.15;box(hall,.32,.61,.018,i*.61,.51,.303,'#5b5c4b');}
  const roofGeo=new THREE.BufferGeometry();roofGeo.setAttribute('position',new THREE.Float32BufferAttribute([-1.16,0,-.48,1.16,0,-.48,-1.16,.46,0,1.16,.46,0,-1.16,0,.48,1.16,0,.48],3));roofGeo.setIndex([0,2,1,1,2,3,2,4,3,3,4,5,0,4,2,1,3,5]);roofGeo.computeVertexNormals();mesh(roofGeo,new THREE.MeshStandardMaterial({color:dark,roughness:.94,side:THREE.DoubleSide}),hall,0,1.23,-.08);
  for(let i=1;i<6;i++){for(const side of[-1,1]){const z=side*i*.079;box(hall,2.34,.018,.017,0,1.7-i*.076,z-.08,'#735944');}}
  box(hall,.46,1.95,.52,.73,1.02,-.08,masonry(m));const towerRoof=cylinder(hall,0,.44,.46,.73,2.18,-.08,dark,4);towerRoof.rotation.y=Math.PI/4;
  for(const x of [.63,.83])box(hall,.08,.37,.035,x,1.68,.191,'#5b5e4b');
  stoneArch(g,-1.65,3.8,.76,m,-.3);column(g,1.97,4.32,.66,m);lantern(g,-1.6,4.95);rocks(g,29,'#9d987e',15);shrubs(g,31,'#7c8655',38);
 }
 async function buildDesert(g){
  pathTiles(g,'#ccb98f',63,.24,new THREE.MeshStandardMaterial({color:'#cdbb97',roughness:.91,bumpMap:stoneMap,bumpScale:.014}));
  await Promise.all([
   putAsset(g,'sandstone_caravan_house',2.45,-.08,2.95,0,0,{width:3.2,depth:2.1}),
   putAsset(g,'mature_date_palm',2.75,-2.05,3.95,.22,0,{width:1.8,depth:1.8}),
   putAsset(g,'mature_date_palm',2.5,2.0,3.6,-.3,0,{width:1.7,depth:1.7}),
   putAsset(g,'caravan_merchant_stall',1.08,-2.05,4.93,Math.PI,0,{width:1.5,depth:.9})
  ]);
  stoneArch(g,1.66,3.35,.58,'#c1a87d',-.18);
  // A small woven canopy and stepped entrance tie the landmark into the court.
  const entry=new THREE.Group();entry.position.set(-.08,0,3.82);g.add(entry);
  for(let i=0;i<3;i++)box(entry,1.28-i*.12,.075,.2,0,.038+i*.07,-i*.18,masonry('#d1bd96'));
  const awningGeo=new THREE.BufferGeometry(),positions=[],indices=[];
  for(let i=0;i<=18;i++){
   const x=-1.08+i*.12;
   positions.push(x,1.62,-.34,x,1.46+.035*Math.cos(i*Math.PI),.14);
   if(i<18){const a=i*2;indices.push(a,a+1,a+2,a+1,a+3,a+2);}
  }
  awningGeo.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));awningGeo.setIndex(indices);awningGeo.computeVertexNormals();
  mesh(awningGeo,new THREE.MeshStandardMaterial({color:'#455477',roughness:.96,side:THREE.DoubleSide}),entry);
  for(const x of [-1.08,1.08])cylinder(entry,.018,.023,1.46,x,.73,.14,'#756044',10);
  rocks(g,66,'#bfa575',12);
 }
 async function buildSnow(g){
  await Promise.all([
   putAsset(g,'alpine_ranger_lodge',2.1,-.12,2.98,0,0,{width:3.15,depth:2.15}),
   putAsset(g,'alpine_watch_lookout',1.8,-1.9,3.65,Math.PI*.92,0,{width:1.15,depth:1.2}),
   putAsset(g,'snowy_alpine_spruce',2.75,2.15,3.93,.25,0,{width:1.85,depth:1.85}),
   putAsset(g,'snowy_alpine_spruce',1.7,-2.58,4.48,-.45,0,{width:1.12,depth:1.12})
  ]);
  const porch=new THREE.Group();porch.position.set(-.12,0,3.85);g.add(porch);
  for(let j=0;j<3;j++)box(porch,1.18,.075,.19,0,.035+j*.065,-j*.18,'#747777');
  const positions=[],indices=[],height=g.userData.terrain;
  for(let i=0;i<=40;i++){
   const t=i/40,z=3.68+2.25*t,x=-2.38+1.45*t+.12*Math.sin(t*Math.PI*2);
   for(const side of [-1,1]){const xx=x+side*(.15+.045*Math.sin(t*6));positions.push(xx,height(xx,z)+.032,z);}
   if(i<40){const a=i*2;indices.push(a,a+2,a+1,a+1,a+2,a+3);}
  }
  const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geo.setIndex(indices);geo.computeVertexNormals();
  const stream=mesh(geo,new THREE.MeshPhysicalMaterial({color:'#94bbcc',roughness:.34,metalness:.08,clearcoat:.25,side:THREE.DoubleSide}),g);stream.userData.keepLevel=true;
  const bridge=new THREE.Group();bridge.position.set(-1.77,.09,4.65);g.add(bridge);
  for(let i=0;i<9;i++)box(bridge,.12,.06,.60,-.52+i*.13,.045,0,'#777a76');
  for(const z of [-.25,.25])box(bridge,1.23,.08,.07,0,0,z,'#525d61');
  for(const x of [-1.4,1.4]){
   const lamp=new THREE.Group();lamp.position.set(x,0,4.35);g.add(lamp);
   box(lamp,.055,.72,.055,0,.36,0,'#4b5b60');box(lamp,.2,.04,.2,0,.8,0,'#4e5f66');
   box(lamp,.12,.18,.12,0,.69,0,new THREE.MeshStandardMaterial({color:'#f3c88b',emissive:'#edab59',emissiveIntensity:.55,roughness:.7}));
   const light=new THREE.PointLight('#ffce8f',.8,1.5,2);light.position.y=.71;lamp.add(light);
  }
  rocks(g,71,'#b2c2c8',13);
 }

 async function buildSunward(g){
  const pale=masonry('#d6cfb8'),trim=material('#e7dfc8'),blue=material('#426977'),roof=material('#ab7051');
  pathTiles(g,'#d2cbb8',81,.10);
  const house=new THREE.Group();house.position.set(-.12,0,2.94);g.add(house);
  box(house,2.64,1.48,.9,0,.81,0,pale);
  box(house,2.78,.10,1.0,0,1.56,0,trim);box(house,2.70,.065,.98,0,.79,0,trim);
  for(const x of [-1.02,-.51,0,.51,1.02]){
   for(const y of [.41,1.16]){
    box(house,.31,.43,.025,x,y,.462,material('#354347'));
    box(house,.38,.055,.075,x,y-.235,.485,trim);
    for(const side of [-1,1]){
     box(house,.09,.46,.045,x+side*.19,y,.485,blue);
     for(let k=0;k<6;k++)box(house,.095,.018,.018,x+side*.19,y-.17+k*.065,.515,material('#315564'));
    }
   }
  }
  // A tiled pitched roof carries the same terracotta/cobalt/ivory vocabulary.
  for(const side of [-1,1]){
   const panel=box(house,2.88,.055,.68,0,1.79,side*.25,roof);panel.rotation.x=side*.54;
   for(let i=0;i<27;i++){
    const roll=cylinder(house,.025,.025,.68,-1.36+i*.104,1.82,side*.25,roof,8);
    roll.rotation.x=Math.PI/2+side*.54;
   }
  }
  const ridge=cylinder(house,.045,.045,2.92,0,1.98,0,roof,12);ridge.rotation.z=Math.PI/2;
  for(const x of [-1.05,-.35,.35,1.05]){
   const arch=stoneArch(house,x,.69,.50,'#d1c7aa');arch.position.y=.04;
  }
  const arcade=new THREE.Group();arcade.position.set(-1.70,0,3.72);arcade.rotation.y=.25;g.add(arcade);
  stoneArch(arcade,0,0,.67,'#d1c7aa');
  await Promise.all([
   putAsset(g,'sunward_olive',2.30,1.98,3.30,-.25,0,{width:1.65,depth:1.65}),
   putAsset(g,'sunward_fountain',.74,-1.95,4.80,0,0,{width:.85,depth:.85}),
   putAsset(g,'sunward_flowers',.74,1.91,4.70,.2,0,{width:.75,depth:.75}),
   putAsset(g,'sunward_flowers',.55,-1.76,4.05,-.4,0,{width:.65,depth:.65})
  ]);
 }

 async function buildAbyssal(g){
  const frame=material('#334d58',.34,.72),hull=material('#6b919b',.43,.55),ivory=material('#d0d8cf',.44,.38),brass=material('#c79b55',.43,.55);
  const window=new THREE.MeshStandardMaterial({color:'#153e4b',metalness:.22,roughness:.19,emissive:'#216575',emissiveIntensity:.17});
  const cyan=new THREE.MeshStandardMaterial({color:'#a4e5e1',emissive:'#49a7b1',emissiveIntensity:.45,roughness:.35});
  // A compact pressure-shell pavilion illustrates the authored dry habitat.
  const station=new THREE.Group();station.position.set(0,.10,2.90);g.add(station);
  box(station,2.42,.18,1.20,0,.08,0,frame);
  box(station,2.26,.72,1.05,0,.50,0,hull);
  const vertices=[],indices=[];
  for(let j=0;j<=1;j++)for(let i=0;i<=40;i++){
   const a=-Math.PI/2+Math.PI*i/40;vertices.push(Math.sin(a)*1.13,.83+Math.cos(a)*.80,-.51+j*1.02);
  }
  for(let i=0;i<40;i++){const a=i,b=i+1,c=i+41,d=i+42;indices.push(a,c,b,b,c,d);}
  const shell=new THREE.BufferGeometry();shell.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));shell.setIndex(indices);shell.computeVertexNormals();
  const shellMat=hull.clone();shellMat.side=THREE.DoubleSide;mesh(shell,shellMat,station);
  for(const z of [-.55,-.18,.18,.55]){
   const points=Array.from({length:41},(_,i)=>{const a=-Math.PI/2+Math.PI*i/40;return new THREE.Vector3(Math.sin(a)*1.16,.83+Math.cos(a)*.83,z);});
   mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points),40,.045,8,false),ivory,station);
   for(const x of [-1.16,1.16])box(station,.085,.77,.10,x,.46,z,ivory);
  }
  box(station,2.18,.82,.055,0,.60,.558,ivory);
  torus(station,.45,.075,0,.66,.61,frame);torus(station,.45,.025,0,.66,.695,brass);
  const hatch=mesh(new THREE.CircleGeometry(.395,48),window,station,0,.66,.642);
  for(let k=0;k<12;k++){const a=k*Math.PI/6;mesh(new THREE.SphereGeometry(.026,8,6),brass,station,Math.cos(a)*.45,.66+Math.sin(a)*.45,.702);}
  for(const x of [-.79,.79]){torus(station,.16,.035,x,.68,.63,frame);mesh(new THREE.CircleGeometry(.136,32),window,station,x,.68,.65);box(station,.32,.045,.055,x,1.05,.64,cyan);}
  box(station,.30,.09,.18,0,1.80,-.13,frame);cylinder(station,.02,.026,.61,0,2.10,-.13,ivory,12);torus(station,.13,.025,0,2.32,-.13,brass);
  for(const x of [-.65,.65]){
   const pipe=cylinder(station,.044,.044,1.40,x,.14,.10,brass,12);pipe.rotation.x=Math.PI/2;
  }
  // Dry deck and restrained utility details, with exterior coral at the edges.
  for(let j=0;j<6;j++)for(let i=-1;i<=1;i++)box(g,.61,.12,.36,i*.64,.07,3.48+j*.40,material('#667a80',.46,.55));
  for(const x of [-1.04,1.04]){const rail=cylinder(g,.025,.025,2.35,x,.12,4.55,brass,12);rail.rotation.x=Math.PI/2;}
  rocks(g,71,'#607f84',18);
  await Promise.all([
   putAsset(g,'abyssal_subsea_survey_submersible',.80,-1.85,4.47,.60,.08,{width:1.10,depth:1.10}),
   putAsset(g,'abyssal_coral_outcrop',1.14,2.06,4.65,-.18,0,{width:1.20,depth:1.10}),
   putAsset(g,'abyssal_coral_outcrop',.72,-2.13,5.22,.60,0,{width:1.05,depth:.82}),
   putAsset(g,'abyssal_pressure_relay',1.34,-1.30,3.26,.28,0,{width:.62,depth:.68})
  ]);
 }
 const builders={abyssal:buildAbyssal,sunward:buildSunward,sakura:buildSakura,neon:buildNeon,cloister:buildCloister,desert:buildDesert,snow:buildSnow};
 for(let i=0;i<N;i++){
  const w=worlds[i],g=new THREE.Group();g.rotation.y=i*step;g.userData.terrain=terrainFor(w);root.add(g);groups.push(g);wedge(g,w);
 }
 // No giant world mesh is loaded: each scene has a small, explicitly chosen asset set.
 const tasks=worlds.map(async(w,i)=>{
  const g=groups[i];if(w.props){await Promise.all(w.props.map(p=>putAsset(g,p.model,p.height,p.x,p.z,p.yaw||0,p.y||0)));}else if(builders[w.miniature])await builders[w.miniature](g);
  const bossX=w.miniature==='neon'?1.28:.98,bossZ=w.miniature==='neon'?4.55:4.25;
  const player=await putAsset(g,w.player,1.02,-.96,5.05,Math.atan2(bossX+.96,bossZ-5.05),w.miniature==='abyssal'?.14:0);
  const boss=await putAsset(g,w.boss,2.12,bossX,bossZ,Math.atan2(-.96-bossX,5.05-bossZ),w.miniature==='abyssal'?.14:0);
  for(const object of g.children){if(!object.userData.keepLevel)object.position.y+=g.userData.terrain(object.position.x,object.position.z);}
  for(const obj of [player,boss])if(obj){const bones={};obj.traverse(b=>{if(b.isBone&&['Spine02','Head','L_Upperarm','R_Upperarm'].includes(b.name))bones[b.name]={bone:b,base:b.quaternion.clone()};});characters.push({object:obj,bones,seed:i*1.3+(obj===boss?.7:0)});}
  completed++;onProgress(completed/N);
 });
 const hub=cylinder(root,.13,.29,.29,0,.15,0,material('#c7b693',.5,.45),32);hub.castShadow=false;
 let disposed=false,ready=false,visible=true,paused=matchMedia('(prefers-reduced-motion: reduce)').matches,phase=0,origin=0,clock=0,last=performance.now(),selection=null,drag=null,lastActive=-1,frameCount=0;
 const cadence=6.8;
 const cycleEase=t=>t-.91*Math.sin(TAU*t)/TAU;
 function notify(){const index=((Math.round(phase)%N)+N)%N;if(index!==lastActive){lastActive=index;onActive(index);}}
 function select(index){let target=Math.round(phase/N)*N+index;if(target-phase>N/2)target-=N;if(phase-target>N/2)target+=N;selection={from:phase,to:target,start:performance.now(),duration:1100+Math.abs(target-phase)*190};}
 canvas.addEventListener('pointerdown',e=>{if(e.button!==0)return;drag={x:e.clientX,phase,y:e.clientY,moved:false};selection=null;canvas.setPointerCapture(e.pointerId);});
 canvas.addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-drag.x;if(Math.abs(dx)>5)drag.moved=true;phase=drag.phase-dx*.006;root.rotation.y=-phase*step;notify();});
 const release=()=>{if(!drag)return;drag=null;select(((Math.round(phase)%N)+N)%N);};canvas.addEventListener('pointerup',release);canvas.addEventListener('pointercancel',release);
 const observer=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;},{threshold:.03});observer.observe(canvas);
 function resize(){const w=canvas.clientWidth,h=canvas.clientHeight;renderer.setSize(w,h,false);const aspect=w/h;const vh=aspect<1.3?14.8:10.5;wideCamera.left=-vh*aspect/2;wideCamera.right=vh*aspect/2;wideCamera.top=vh/2;wideCamera.bottom=-vh/2;wideCamera.updateProjectionMatrix();focusCamera.aspect=aspect;focusCamera.fov=aspect<1.3?74:46;focusCamera.updateProjectionMatrix();}
 const resizeObserver=new ResizeObserver(resize);resizeObserver.observe(canvas);resize();
 const restQuat=new THREE.Quaternion();const axis=new THREE.Vector3(1,0,0);
 function tick(now){if(disposed)return;requestAnimationFrame(tick);const dt=Math.min((now-last)/1000,.05);last=now;if(!visible||document.hidden)return;
  if(!drag){if(selection){const t=Math.min(1,(now-selection.start)/selection.duration);const e=t*t*t*(10+t*(-15+6*t));phase=selection.from+(selection.to-selection.from)*e;if(t===1){origin=selection.to;clock=0;selection=null;}}
   else if(!paused&&ready){clock+=dt;const turns=clock/cadence;phase=origin+Math.floor(turns)+cycleEase(turns%1);}}
  root.rotation.y=-phase*step;notify();const t=now/1000;
  if(!paused){for(const c of characters){for(const [key,v]of Object.entries(c.bones)){const amp=key==='Spine02'?.011:key==='Head'?.012:.018;restQuat.setFromAxisAngle(axis,Math.sin(t*1.35+c.seed)*amp);v.bone.quaternion.copy(v.base).multiply(restQuat);}}
   for(const m of moving){if(m.kind==='instrument')m.object.rotation.y=t*.09;else m.object.material.opacity=.7+.12*Math.sin(t+m.offset);}}
  renderer.render(scene,camera);frameCount++;
 }
 requestAnimationFrame(tick);await Promise.allSettled(tasks);ready=true;clock=0;phase=0;origin=0;last=performance.now();notify();
 return {select,setPaused(value){paused=value;return paused;},get paused(){return paused;},setOverview(value){overview=value;camera=overview?wideCamera:focusCamera;},get overview(){return overview;},setView({y,z,targetY=.55,targetZ=2,fov=41}){focusCamera.position.set(0,y,z);focusCamera.lookAt(0,targetY,targetZ);focusCamera.fov=fov;focusCamera.updateProjectionMatrix();},reset(){select(0);},state(){return {phase,active:lastActive,paused,overview,loaded:completed,worlds:N,triangles:renderer.info.render.triangles,drawCalls:renderer.info.render.calls,frames:frameCount,failures};},dispose(){disposed=true;observer.disconnect();resizeObserver.disconnect();renderer.dispose();}};
}
