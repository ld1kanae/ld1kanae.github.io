(()=>{
  const brand=document.querySelector('#setup .brand');
  if(!brand)return;

  const bg=getComputedStyle(brand).backgroundImage||'';
  const m=bg.match(/^url\(["']?(data:image\/png;base64,[^"')]+)["']?\)$/);
  if(!m)return;

  const img=document.createElement('img');
  img.src=m[1];
  img.alt='DruMaster';
  img.className='setup-main-logo-img';
  img.draggable=false;

  brand.replaceChildren(img);
  brand.style.setProperty('background-image','none','important');
  brand.style.setProperty('display','flex','important');
  brand.style.setProperty('align-items','center','important');
  brand.style.setProperty('justify-content','center','important');

  img.style.setProperty('display','block','important');
  img.style.setProperty('width','100%','important');
  img.style.setProperty('height','100%','important');
  img.style.setProperty('object-fit','contain','important');
  img.style.setProperty('object-position','center','important');
  img.style.setProperty('pointer-events','none','important');
})();
