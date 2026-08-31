"use strict";

(()=>{
  const proto=globalThis.Element?.prototype;
  const nativeAnimate=proto?.animate;
  if(typeof nativeAnimate!=="function"||globalThis.DruMasterPerfAnimationPool)return;

  const slots=new WeakMap();
  const stats={created:0,reused:0,recreated:0,eligibleCalls:0};

  function purposeFor(el){
    if(!(el instanceof Element))return null;
    if(el.id==="kickFx")return "kick";
    if(el.id==="score")return "score";
    if(el.classList?.contains("lane-hit-glow"))return "lane-hit-glow";
    if(el.classList?.contains("mobile-tap-hit-fx"))return "mobile-tap";
    if(el.classList?.contains("dm-reusable-hit-fx"))return "kit-hit";
    return null;
  }

  function create(el,purpose,keyframes,options){
    const animation=nativeAnimate.call(el,keyframes,options);
    slots.set(el,{purpose,animation});
    stats.created++;
    return animation;
  }

  proto.animate=function(keyframes,options){
    const purpose=purposeFor(this);
    if(!purpose)return nativeAnimate.call(this,keyframes,options);
    stats.eligibleCalls++;

    const slot=slots.get(this);
    if(!slot||slot.purpose!==purpose||!slot.animation){
      return create(this,purpose,keyframes,options);
    }

    const animation=slot.animation;
    try{
      if(animation.effect?.setKeyframes)animation.effect.setKeyframes(keyframes);
      if(animation.effect?.updateTiming){
        if(typeof options==="number")animation.effect.updateTiming({duration:options});
        else if(options&&typeof options==="object")animation.effect.updateTiming(options);
      }
      animation.cancel();
      animation.currentTime=0;
      animation.play();
      stats.reused++;
      return animation;
    }catch(error){
      try{animation.cancel()}catch{}
      slots.delete(this);
      stats.recreated++;
      return create(this,purpose,keyframes,options);
    }
  };

  globalThis.DruMasterPerfAnimationPool={
    version:"20260901-pass7",
    stats,
    nativeAnimate
  };
})();
