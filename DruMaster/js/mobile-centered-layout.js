(()=>{
  const root=document.documentElement;
  const params=new URLSearchParams(location.search);
  const legacy=params.get('layout')==='legacy';
  if(legacy){
    root.classList.remove('dm-layout-centered');
    root.classList.add('dm-layout-legacy');
    return;
  }

  root.classList.add('dm-layout-centered');

  const mobileQuery=matchMedia('(hover:none) and (pointer:coarse) and (max-width:900px)');
  const correctionKey='dm-mobile-center-correction-v1';
  let raf=0;
  let fullscreenTried=false;

  function clampNumber(value,min,max){
    const n=Number(value);
    if(!Number.isFinite(n)) return 0;
    return Math.max(min,Math.min(max,n));
  }

  function applySavedCorrection(){
    let data=null;
    try{data=JSON.parse(localStorage.getItem(correctionKey)||'null')}catch(_){data=null}
    const x=clampNumber(data&&data.xPx,-80,80);
    const y=clampNumber(data&&data.yPx,-60,60);
    root.style.setProperty('--dm-mobile-center-correction-x',`${x}px`);
    root.style.setProperty('--dm-mobile-center-correction-y',`${y}px`);
  }

  function updateStageNow(){
    raf=0;
    if(!mobileQuery.matches) return;
    const vv=window.visualViewport;
    const viewportW=Math.max(1,Math.round(vv?vv.width:window.innerWidth));
    const viewportH=Math.max(1,Math.round(vv?vv.height:window.innerHeight));

    /* The app is authored as a landscape stage and then rotated -90deg.
       Therefore the pre-rotation width is the visible viewport height and
       the pre-rotation height is the visible viewport width. */
    root.style.setProperty('--dm-mobile-stage-w',`${viewportH}px`);
    root.style.setProperty('--dm-mobile-stage-h',`${viewportW}px`);
    root.dataset.dmViewport=`${viewportW}x${viewportH}`;
    root.dataset.dmFullscreen=document.fullscreenElement||document.webkitFullscreenElement?'1':'0';
  }

  function scheduleStageUpdate(){
    if(raf) cancelAnimationFrame(raf);
    raf=requestAnimationFrame(updateStageNow);
  }

  async function requestMobileFullscreen(){
    if(fullscreenTried||!mobileQuery.matches) return;
    if(document.fullscreenElement||document.webkitFullscreenElement){
      fullscreenTried=true;
      scheduleStageUpdate();
      return;
    }
    fullscreenTried=true;
    const target=document.documentElement;
    try{
      if(target.requestFullscreen){
        try{await target.requestFullscreen({navigationUI:'hide'})}
        catch(_){await target.requestFullscreen()}
      }else if(target.webkitRequestFullscreen){
        target.webkitRequestFullscreen();
      }
    }catch(_){
      /* Fullscreen is optional. VisualViewport centering still works when the
         browser rejects or does not implement the request. */
    }finally{
      scheduleStageUpdate();
      setTimeout(scheduleStageUpdate,120);
      setTimeout(scheduleStageUpdate,420);
    }
  }

  applySavedCorrection();
  scheduleStageUpdate();

  /* Use the click event rather than pointerdown so the original target has
     already been resolved before the viewport can change. */
  document.addEventListener('click',requestMobileFullscreen,{capture:true});

  window.addEventListener('resize',scheduleStageUpdate,{passive:true});
  window.addEventListener('orientationchange',scheduleStageUpdate,{passive:true});
  document.addEventListener('fullscreenchange',scheduleStageUpdate);
  document.addEventListener('webkitfullscreenchange',scheduleStageUpdate);
  if(window.visualViewport){
    window.visualViewport.addEventListener('resize',scheduleStageUpdate,{passive:true});
    window.visualViewport.addEventListener('scroll',scheduleStageUpdate,{passive:true});
  }

  window.addEventListener('storage',event=>{
    if(event.key===correctionKey) applySavedCorrection();
  });
})();
