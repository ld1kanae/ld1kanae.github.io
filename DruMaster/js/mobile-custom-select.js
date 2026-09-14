"use strict";

(()=>{
  /* Use the same DOM-based selector on desktop as well. Native Windows/Chromium
     dropdowns keep the OS accent color for the selected row and ignore CSS. */
  const enhanced=new WeakMap(),
        mobileQuery=typeof matchMedia==="function"?matchMedia("(hover:none) and (pointer:coarse) and (max-width:900px)"):null;
  let opened=null;

  function close(entry=opened){
    if(!entry)return;
    entry.root.classList.remove("open","open-up");
    entry.host?.classList.remove("mobile-select-host-open");
    entry.trigger.setAttribute("aria-expanded","false");
    entry.menu.hidden=true;
    if(opened===entry)opened=null;
  }

  function sync(entry){
    const option=entry.select.options[entry.select.selectedIndex];
    entry.value.textContent=option?.textContent||"";
    [...entry.menu.children].forEach(node=>{
      const index=Number(node.dataset.optionIndex);
      const source=entry.select.options[index];
      const selected=index===entry.select.selectedIndex;
      node.classList.toggle("selected",selected);
      node.setAttribute("aria-selected",selected?"true":"false");
      node.disabled=!!source?.disabled;
      node.hidden=!!source?.hidden;
    });
  }

  function topWithin(node,ancestor){
    let top=0,el=node;
    while(el&&el!==ancestor){
      top+=el.offsetTop||0;
      el=el.offsetParent;
    }
    if(el===ancestor)return top;
    const nr=node.getBoundingClientRect(),ar=ancestor.getBoundingClientRect();
    return nr.top-ar.top;
  }

  function positionMenu(entry){
    entry.root.classList.remove("open-up");
    const setup=entry.root.closest(".setup");
    if(!setup)return;

    /* Measure in the setup stage rather than against the selector's nearest
       positioned parent. The song selector is nested inside .song-card, so a
       bare offsetTop understated the available room and could choose a clipped
       direction on the forced-landscape phone layout. */
    const rootTop=topWithin(entry.root,setup),
          rootBottom=rootTop+entry.root.offsetHeight,
          spaceAbove=Math.max(0,rootTop-8),
          spaceBelow=Math.max(0,setup.clientHeight-rootBottom-8),
          naturalHeight=Math.min(180,Math.max(48,entry.menu.scrollHeight||0)),
          forceSongUp=entry.select.id==="songSelect"&&!!mobileQuery?.matches,
          openUp=forceSongUp||(spaceBelow<naturalHeight&&spaceAbove>spaceBelow);

    if(openUp)entry.root.classList.add("open-up");

    const available=openUp?spaceAbove:spaceBelow;
    entry.menu.style.maxHeight=`${Math.max(48,Math.min(180,available||180))}px`;

    /* Performance mode's first item is "通常". Always open at the top so it
       remains immediately selectable even when the menu has to scroll. */
    if(entry.select.id==="performanceModeSelect")entry.menu.scrollTop=0;
  }

  function open(entry){
    if(opened&&opened!==entry)close(opened);
    sync(entry);
    entry.menu.hidden=false;
    entry.root.classList.add("open");
    entry.host?.classList.add("mobile-select-host-open");
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
      if(option.hidden)return;
      const item=document.createElement("button");
      item.type="button";
      item.className="mobile-custom-select-option";
      item.dataset.optionIndex=String(index);
      item.setAttribute("role","option");

      const label=document.createElement("span");
      label.className="mobile-custom-select-option-label";
      label.textContent=option.textContent;
      item.appendChild(label);

      if(select.id==="performanceModeSelect"&&option.value==="pad"){
        const mic=document.createElement("span");
        mic.className="mobile-custom-select-mic";
        mic.setAttribute("aria-hidden","true");
        mic.innerHTML='<svg viewBox="0 0 24 24"><rect x="8.5" y="2.5" width="7" height="11" rx="3.5"/><path d="M5.5 10.5v.7a6.5 6.5 0 0 0 13 0v-.7M12 17.7V21M8.5 21h7"/></svg>';
        item.appendChild(mic);
      }

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

    const entry={select,root,trigger,value,menu,host:root.closest(".song-card,.options")};
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
