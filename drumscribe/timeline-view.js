export function createTimelineViewport({canvas,zoom,scroll,zoomOut,scrollOut,fitButton,getDuration,onChange=()=>{}}){
  let pxPerSec=260,viewStart=0,fitted=true,internal=false;
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const width=()=>Math.max(1,canvas.getBoundingClientRect().width||canvas.clientWidth||1);
  const duration=()=>Math.max(0,Number(getDuration?.())||0);
  const fitPx=()=>duration()>0?width()/duration():260;
  const minPx=()=>Math.max(.25,Math.min(3000,fitPx()));
  const maxPx=()=>Math.max(minPx(),Number(zoom?.max)||3000);
  const visibleDuration=()=>duration()>0?Math.min(duration(),width()/Math.max(.01,pxPerSec)):0;
  const maxView=()=>Math.max(0,duration()-visibleDuration());
  function updateUi(){
    internal=true;
    try{
      if(zoom){zoom.min=String(minPx());zoom.value=String(pxPerSec);}
      if(zoomOut)zoomOut.textContent=fitted?'全体':Math.round(pxPerSec)+' px/s';
      if(scroll){scroll.disabled=maxView()<=1e-6;scroll.value=maxView()?String(Math.round(viewStart/maxView()*1000)):'0';}
      if(scrollOut)scrollOut.textContent=viewStart.toFixed(3)+'s';
    }finally{internal=false}
  }
  function emit(){updateUi();onChange();}
  function setStart(value){viewStart=clamp(Number(value)||0,0,maxView());fitted=Math.abs(pxPerSec-fitPx())<.01&&viewStart<.001;emit();}
  function setZoom(value,anchorX=width()/2){
    const oldVisible=visibleDuration(),ratio=clamp(anchorX/width(),0,1),anchorTime=viewStart+ratio*oldVisible;
    pxPerSec=clamp(Number(value)||pxPerSec,minPx(),maxPx());fitted=Math.abs(pxPerSec-fitPx())<.01;
    const nextVisible=visibleDuration();viewStart=clamp(anchorTime-ratio*nextVisible,0,maxView());emit();
  }
  function resetFit(){pxPerSec=fitPx();viewStart=0;fitted=true;emit();}
  function reset(){pxPerSec=260;viewStart=0;fitted=true;updateUi();onChange();}
  function metrics(){return {pxPerSec,start:viewStart,visible:visibleDuration(),end:viewStart+visibleDuration(),maxStart:maxView(),duration:duration(),width:width(),fitted};}
  function timeToX(t){return (Number(t)-viewStart)*pxPerSec}
  function xToTime(x){return clamp(viewStart+Number(x)/Math.max(.01,pxPerSec),0,duration())}
  function ensureVisible(t){
    t=Number(t)||0;const span=visibleDuration();
    if(!span)return;
    if(t<viewStart||t>viewStart+span){viewStart=clamp(t-span*.25,0,maxView());fitted=false;emit();}
  }
  function focusRange(start,end){
    const d=duration();if(!d)return;
    let a=clamp(Number(start)||0,0,d),b=clamp(Number(end)||0,0,d);if(b<a)[a,b]=[b,a];
    const span=Math.max(.15,b-a),targetPx=clamp(width()/(span*1.35),minPx(),maxPx()),center=(a+b)/2;
    pxPerSec=targetPx;fitted=false;viewStart=clamp(center-visibleDuration()/2,0,maxView());emit();
  }
  zoom?.addEventListener('input',e=>{if(!internal)setZoom(Number(e.target.value),width()/2)});
  scroll?.addEventListener('input',e=>{if(!internal)setStart(maxView()*Number(e.target.value)/1000)});
  fitButton?.addEventListener('click',resetFit);
  canvas.addEventListener('wheel',e=>{
    if(duration()<=0)return;
    e.preventDefault();e.stopPropagation();
    const raw=Math.abs(e.deltaY)>=Math.abs(e.deltaX)?e.deltaY:e.deltaX;
    const unit=e.deltaMode===1?16:e.deltaMode===2?width():1;
    const wheelPixels=raw*unit;
    if(e.ctrlKey||e.metaKey){
      const factor=Math.exp(-wheelPixels*.0018),r=canvas.getBoundingClientRect();
      setZoom(pxPerSec*factor,clamp(e.clientX-r.left,0,r.width));
    }else setStart(viewStart+wheelPixels/Math.max(.01,pxPerSec));
  },{passive:false});
  addEventListener('resize',()=>{if(fitted)resetFit();else{viewStart=clamp(viewStart,0,maxView());emit();}});
  updateUi();
  return {resetFit,reset,clamp:()=>{if(fitted)resetFit();else{viewStart=clamp(viewStart,0,maxView());emit();}},metrics,timeToX,xToTime,setStart,setZoom,ensureVisible,focusRange};
}
