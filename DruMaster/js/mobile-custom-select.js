"use strict";

(()=>{
  const mobileQuery=matchMedia("(hover:none) and (pointer:coarse) and (max-width:900px)");
  if(!mobileQuery.matches)return;

  const enhanced=new WeakMap();
  let opened=null;

  function close(entry=opened){
    if(!entry)return;
    entry.root.classList.remove("open","open-up");
    entry.trigger.setAttribute("aria-expanded","false");
    entry.menu.hidden=true;
    if(opened===entry)opened=null;
  }

  function sync(entry){
    const option=entry.select.options[entry.select.selectedIndex];
    entry.value.textContent=option?.textContent||"";
    [...entry.menu.children].forEach((node,i)=>{
      const selected=i===entry.select.selectedIndex;
      node.classList.toggle("selected",selected);
      node.setAttribute("aria-selected",selected?"true":"false");
      node.disabled=!!entry.select.options[i]?.disabled;
    });
  }

  function positionMenu(entry){
    entry.root.classList.remove("open-up");
    const setup=entry.root.closest(".setup"),card=entry.root.closest(".song-card");
    if(!setup)return;
    const rootBottom=(card||entry.root).offsetTop+(card||entry.root).offsetHeight,
          approxMenuHeight=Math.min(180,Math.max(48,entry.select.options.length*46+8));
    if(rootBottom+approxMenuHeight+10>setup.clientHeight)entry.root.classList.add("open-up");
  }

  function open(entry){
    if(opened&&opened!==entry)close(opened);
    sync(entry);
    entry.menu.hidden=false;
    entry.root.classList.add("open");
    entry.trigger.setAttribute("aria-expanded","true");
    positionMenu(entry);
    opened=entry;
  }

  function enhance(select){
    if(!select||enhanced.has(select))return;

    const root=document.createElement("div");
    root.className="mobile-custom-select"+(select.id==="songSelect"?" song-custom-select":" mode-custom-select");

    const trigger=document.createElement("button");
    trigger.type="button";
    trigger.className="mobile-custom-select-trigger";
    trigger.setAttribute("aria-haspopup","listbox");
    trigger.setAttribute("aria-expanded","false");

    const value=document.createElement("span");
    value.className="mobile-custom-select-value";
    /* Do not use <i> here: .option i is the legacy toggle-switch knob selector. */
    const arrow=document.createElement("span");
    arrow.className="mobile-custom-select-arrow";
    arrow.setAttribute("aria-hidden","true");
    trigger.append(value,arrow);

    const menu=document.createElement("div");
    menu.className="mobile-custom-select-menu";
    menu.setAttribute("role","listbox");
    menu.hidden=true;

    [...select.options].forEach((option,index)=>{
      const item=document.createElement("button");
      item.type="button";
      item.className="mobile-custom-select-option";
      item.setAttribute("role","option");
      item.textContent=option.textContent;
      item.disabled=option.disabled;
      item.addEventListener("pointerdown",e=>e.stopPropagation());
      item.addEventListener("click",()=>{
        if(option.disabled)return;
        select.selectedIndex=index;
        select.value=option.value;
        sync(entry);
        close(entry);
        select.dispatchEvent(new Event("change",{bubbles:true}));
      });
      menu.appendChild(item);
    });

    select.classList.add("mobile-native-select-hidden");
    select.insertAdjacentElement("afterend",root);
    root.append(trigger,menu);

    const entry={select,root,trigger,value,menu};
    enhanced.set(select,entry);
    sync(entry);

    trigger.addEventListener("pointerdown",e=>e.stopPropagation());
    trigger.addEventListener("click",e=>{
      e.preventDefault();
      e.stopPropagation();
      root.classList.contains("open")?close(entry):open(entry);
    });
    select.addEventListener("change",()=>sync(entry));
  }

  function install(){
    enhance(document.querySelector("#songSelect"));
    enhance(document.querySelector("#performanceModeSelect"));
  }

  install();
  new MutationObserver(install).observe(document.body,{childList:true,subtree:true});
  addEventListener("pointerdown",()=>close(),{passive:true});
  addEventListener("resize",()=>close(),{passive:true});
})();
