"use strict";
(()=>{
  const root=document.querySelector("#editorWrap");
  if(!root)return;

  const defaults={
    igWidth:"10",
    igCore:"1",
    igShoulder:"0.21",
    igTail:"0.04",
    igShoulderStop:"18",
    igTailStop:"64",
    igBlur:"3",
    haloY:"0",
    haloHeight:"22",
    haloBlur:"12",
    haloOpacity:"0.51",
    haloExpand:"0",
    spectralAngle:"90"
  };

  for(const [id,value] of Object.entries(defaults)){
    const el=root.querySelector(`#${id}`);
    if(!el)continue;
    el.value=value;
    el.dispatchEvent(new Event("input",{bubbles:true}));
  }
})();
