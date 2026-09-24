const dialog=document.querySelector('#method-dialog');
const surface=document.querySelector('#method-zoom-surface');
const image=document.querySelector('#method-full-image');
const level=document.querySelector('#method-zoom-level');
let zoom=1,fitWidth=1,drag=null;
function fit(){
 fitWidth=Math.max(100,Math.min(surface.clientWidth-40,(surface.clientHeight-40)*16/9));
 zoom=1;image.style.width=`${fitWidth}px`;level.textContent='100%';surface.scrollTo(0,0);
}
function scale(factor){
 const oldWidth=fitWidth*zoom,oldLeft=surface.scrollLeft,oldTop=surface.scrollTop;
 zoom=Math.max(1,Math.min(8,zoom*factor));const width=fitWidth*zoom;
 image.style.width=`${width}px`;level.textContent=`${Math.round(zoom*100)}%`;
 const ratio=width/oldWidth;
 surface.scrollLeft=(oldLeft+surface.clientWidth/2)*ratio-surface.clientWidth/2;
 surface.scrollTop=(oldTop+surface.clientHeight/2)*ratio-surface.clientHeight/2;
}
document.querySelector('#method-figure-open').addEventListener('click',()=>{dialog.showModal();requestAnimationFrame(fit);});
document.querySelector('#method-close').addEventListener('click',()=>dialog.close());
document.querySelector('#method-fit').addEventListener('click',fit);
document.querySelector('#method-zoom-in').addEventListener('click',()=>scale(1.5));
document.querySelector('#method-zoom-out').addEventListener('click',()=>scale(1/1.5));
dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close();});
dialog.addEventListener('keydown',e=>{
 if(['+','=','-','Home'].includes(e.key)){e.preventDefault();if(e.key==='Home')fit();else scale(e.key==='-'?1/1.5:1.5);}
});
surface.addEventListener('pointerdown',e=>{
 if(e.button!==0||e.pointerType!=='mouse')return;
 e.preventDefault();drag={x:e.clientX,y:e.clientY,left:surface.scrollLeft,top:surface.scrollTop};surface.setPointerCapture(e.pointerId);
});
surface.addEventListener('pointermove',e=>{if(!drag)return;surface.scrollLeft=drag.left+drag.x-e.clientX;surface.scrollTop=drag.top+drag.y-e.clientY;});
for(const type of ['pointerup','pointercancel','lostpointercapture'])surface.addEventListener(type,()=>{drag=null;});
image.addEventListener('dragstart',e=>e.preventDefault());
window.addEventListener('resize',()=>{if(dialog.open)fit();});
