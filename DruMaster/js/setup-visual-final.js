(()=>{
  const setup=document.querySelector('#setup');
  if(!setup)return;

  /* Load the approved SVG asset as text and insert it directly into the DOM.
     This avoids the external-SVG <img> rendering issue while preserving the
     user's finished SVG exactly, including its mask/slit edits. */
  const brand=setup.querySelector('.brand');
  if(brand){
    fetch('assets/DruMaster.svg?v=20260828-mainlogoinline1',{cache:'no-store'})
      .then(res=>{
        if(!res.ok)throw new Error(`logo ${res.status}`);
        return res.text();
      })
      .then(svgText=>{
        const doc=new DOMParser().parseFromString(svgText,'image/svg+xml');
        const svg=doc.documentElement;
        if(!svg||svg.nodeName.toLowerCase()!=='svg'||doc.querySelector('parsererror'))throw new Error('invalid logo svg');
        svg.removeAttribute('width');
        svg.removeAttribute('height');
        svg.setAttribute('role','img');
        svg.setAttribute('aria-label','DruMaster');
        svg.setAttribute('preserveAspectRatio','xMidYMid meet');
        brand.replaceChildren(document.importNode(svg,true));
      })
      .catch(err=>console.error('DruMaster logo load failed',err));
  }

  if(!setup.querySelector('.setup-moving-lights')){
    const field=document.createElement('div');
    field.className='setup-moving-lights';
    field.setAttribute('aria-hidden','true');
    field.innerHTML='<i class="setup-light setup-light-cyan"></i><i class="setup-light setup-light-blue"></i><i class="setup-light setup-light-violet"></i>';
    setup.prepend(field);
  }

  const updateRange=(input)=>{
    const min=Number(input.min||0);
    const max=Number(input.max||100);
    const value=Number(input.value||min);
    const pct=max===min?0:Math.max(0,Math.min(100,(value-min)/(max-min)*100));
    input.style.setProperty('--setup-range-progress',`${pct}%`);
    input.style.setProperty('--setup-range-mid',`${pct*.52}%`);
  };

  const ranges=setup.querySelectorAll('.tempo-box input[type="range"],.volume-box input[type="range"]');
  ranges.forEach(input=>{
    updateRange(input);
    input.addEventListener('input',()=>updateRange(input),{passive:true});
    input.addEventListener('change',()=>updateRange(input),{passive:true});
  });

  /* Toggle ON animation mirrors the approved PC button-hover animation.
     It runs once when switched ON; production must not replay it on a timer. */
  const reduced=matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
  const SETTINGS={
    rimRun1:{opacity:.3,speedPercent:150,fadeInMs:1300,fadeOutMs:2500,delayMs:0,base:1000,start:0,travel:-100},
    rimRun2:{opacity:.3,speedPercent:150,fadeInMs:1300,fadeOutMs:2500,delayMs:0,base:1000,start:-50,travel:-100},
    faceSheen:{opacity:.7,speedPercent:120,fadeInMs:1000,fadeOutMs:1000,delayMs:-150,base:720},
    faceFlash:{opacity:.25,speedPercent:100,fadeInMs:1000,fadeOutMs:400,delayMs:-150,base:660}
  };

  const activeAnimations=new WeakMap();

  function timing(s){
    const duration=Math.max(80,s.base*(100/Math.max(1,s.speedPercent)));
    let fi=Math.max(0,s.fadeInMs),fo=Math.max(0,s.fadeOutMs);
    const maxFade=duration*.9;
    if(fi+fo>maxFade){
      const k=maxFade/(fi+fo||1);
      fi*=k;
      fo*=k;
    }
    return {duration,inOff:fi/duration,outOff:1-fo/duration};
  }

  function strokeSpec(s){
    const t=timing(s),start=s.start,end=s.start+s.travel,max=s.opacity;
    const at=p=>start+(end-start)*p;
    return {duration:t.duration,frames:[
      {opacity:0,strokeDashoffset:start,offset:0},
      {opacity:max,strokeDashoffset:at(t.inOff),offset:t.inOff},
      {opacity:max,strokeDashoffset:at(t.outOff),offset:t.outOff},
      {opacity:0,strokeDashoffset:end,offset:1}
    ]};
  }

  function moveSpec(s,from,to){
    const t=timing(s),max=s.opacity;
    const at=p=>from+(to-from)*p;
    return {duration:t.duration,frames:[
      {opacity:0,left:`${from}%`,offset:0},
      {opacity:max,left:`${at(t.inOff)}%`,offset:t.inOff},
      {opacity:max,left:`${at(t.outOff)}%`,offset:t.outOff},
      {opacity:0,left:`${to}%`,offset:1}
    ]};
  }

  function fadeSpec(s){
    const t=timing(s),max=s.opacity;
    return {duration:t.duration,frames:[
      {opacity:0,offset:0},
      {opacity:max,offset:t.inOff},
      {opacity:max,offset:t.outOff},
      {opacity:0,offset:1}
    ]};
  }

  function makeRim(){
    const ns='http://www.w3.org/2000/svg';
    const svg=document.createElementNS(ns,'svg');
    svg.classList.add('setup-toggle-rim-svg');
    svg.setAttribute('preserveAspectRatio','none');
    svg.setAttribute('aria-hidden','true');
    for(const cls of ['setup-toggle-rim-run setup-toggle-rim-1','setup-toggle-rim-run setup-toggle-rim-2']){
      const r=document.createElementNS(ns,'rect');
      r.setAttribute('pathLength','100');
      r.setAttribute('class',cls);
      svg.appendChild(r);
    }
    return svg;
  }

  function syncRim(track){
    const svg=track.querySelector(':scope > .setup-toggle-rim-svg');
    if(!svg)return;
    const box=track.getBoundingClientRect();
    if(box.width<2||box.height<2)return;
    const inset=.5;
    const rx=Math.max(0,(box.height-inset*2)/2);
    svg.setAttribute('viewBox',`0 0 ${box.width} ${box.height}`);
    for(const r of svg.querySelectorAll('rect')){
      r.setAttribute('x',String(inset));
      r.setAttribute('y',String(inset));
      r.setAttribute('width',String(Math.max(0,box.width-inset*2)));
      r.setAttribute('height',String(Math.max(0,box.height-inset*2)));
      r.setAttribute('rx',String(rx));
    }
  }

  function addLayers(track){
    if(track.dataset.setupToggleFx==='1')return;
    track.dataset.setupToggleFx='1';
    const sheen=document.createElement('span');
    sheen.className='setup-toggle-face-sheen';
    sheen.setAttribute('aria-hidden','true');
    const flash=document.createElement('span');
    flash.className='setup-toggle-face-flash';
    flash.setAttribute('aria-hidden','true');
    track.appendChild(flash);
    track.appendChild(sheen);
    track.appendChild(makeRim());
    syncRim(track);
    if('ResizeObserver' in window)new ResizeObserver(()=>syncRim(track)).observe(track);
  }

  function stopAnimations(input){
    for(const a of activeAnimations.get(input)||[]){try{a.cancel()}catch{}}
    activeAnimations.delete(input);
  }

  function play(input,track){
    if(reduced||!input.checked)return;
    syncRim(track);
    stopAnimations(input);
    const running=[];
    const run=(el,s,spec)=>{
      if(!el)return;
      const a=el.animate(spec.frames,{duration:spec.duration,delay:s.delayMs,easing:'linear',fill:'both'});
      running.push(a);
    };
    run(track.querySelector('.setup-toggle-rim-1'),SETTINGS.rimRun1,strokeSpec(SETTINGS.rimRun1));
    run(track.querySelector('.setup-toggle-rim-2'),SETTINGS.rimRun2,strokeSpec(SETTINGS.rimRun2));
    run(track.querySelector('.setup-toggle-face-sheen'),SETTINGS.faceSheen,moveSpec(SETTINGS.faceSheen,-58,122));
    run(track.querySelector('.setup-toggle-face-flash'),SETTINGS.faceFlash,fadeSpec(SETTINGS.faceFlash));
    activeAnimations.set(input,running);
  }

  function syncToggle(input){
    const track=input.nextElementSibling;
    if(!track||track.tagName!=='I')return;
    addLayers(track);
    stopAnimations(input);
    if(!input.checked||reduced)return;
    play(input,track);
  }

  setup.querySelectorAll('.option input[type="checkbox"]').forEach(input=>{
    syncToggle(input);
    input.addEventListener('change',()=>syncToggle(input));
  });
})();
