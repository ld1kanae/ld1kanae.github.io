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

  /* Load the smartphone result geometry after every legacy result stylesheet.
     Appending here guarantees the centering layer wins the cascade without
     disturbing PC result CSS. */
  if(!document.querySelector('link[data-dm-result-mobile-centering]')){
    const link=document.createElement('link');
    link.rel='stylesheet';
    link.href='css/result-mobile-centering-v2.css?v=20260902-title-up5px1';
    link.dataset.dmResultMobileCentering='1';
    document.head.appendChild(link);
  }

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

    /* The app is authored as a landscape stage and then rotated -90deg.
       Therefore the pre-rotation width is the visible viewport height and
       the pre-rotation height is the visible viewport width. */
    root.style.setProperty('--dm-mobile-stage-w',`${viewportH}px`);
    root.style.setProperty('--dm-mobile-stage-h',`${viewportW}px`);
    root.dataset.dmViewport=`${viewportW}x${viewportH}`;
  }

  function scheduleStageUpdate(){
    if(raf) cancelAnimationFrame(raf);
    raf=requestAnimationFrame(updateStageNow);
  }

  applySavedCorrection();
  scheduleStageUpdate();

  /* Keep the landscape-stage sizing responsive to the browser's visible
     viewport, but never enter the Fullscreen API automatically. Browser chrome
     remains under the user's control. */
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
