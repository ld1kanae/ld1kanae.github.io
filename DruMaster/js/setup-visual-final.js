(()=>{
  const setup=document.querySelector('#setup');
  if(!setup)return;

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
})();
