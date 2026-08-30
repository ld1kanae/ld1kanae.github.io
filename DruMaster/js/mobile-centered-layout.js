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
    const browserLandscape=viewportW>viewportH;

    /* DruMaster is authored as a landscape stage. When the browser remains in
       portrait we rotate that stage ourselves, as before. If Android/iOS auto
       rotation changes the browser viewport to landscape, stop applying the
       extra -90deg transform and use the viewport directly. The visible game
       orientation therefore stays the same whether device auto-rotate is on or
       off; only the browser chrome itself remains under OS control. */
    if(browserLandscape){
      root.classList.add('dm-browser-landscape');
      root.style.setProperty('--dm-mobile-stage-w',`${viewportW}px`);
      root.style.setProperty('--dm-mobile-stage-h',`${viewportH}px`);
    }else{
      root.classList.remove('dm-browser-landscape');
      root.style.setProperty('--dm-mobile-stage-w',`${viewportH}px`);
      root.style.setProperty('--dm-mobile-stage-h',`${viewportW}px`);
    }
    root.dataset.dmViewport=`${viewportW}x${viewportH}`;
    root.dataset.dmBrowserOrientation=browserLandscape?'landscape':'portrait';
  }

  function scheduleStageUpdate(){
    if(raf) cancelAnimationFrame(raf);
    raf=requestAnimationFrame(updateStageNow);
  }

  applySavedCorrection();
  scheduleStageUpdate();

  /* Keep the visible game orientation stable across browser/device rotation,
     without requesting Fullscreen or native Screen Orientation lock. */
  window.addEventListener('resize',scheduleStageUpdate,{passive:true});
  window.addEventListener('orientationchange',scheduleStageUpdate,{passive:true});
  if(window.visualViewport){
    window.visualViewport.addEventListener('resize',scheduleStageUpdate,{passive:true});
    window.visualViewport.addEventListener('scroll',scheduleStageUpdate,{passive:true});
  }

  window.addEventListener('storage',event=>{
    if(event.key===correctionKey) applySavedCorrection();
  });
})();
