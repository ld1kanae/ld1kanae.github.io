"use strict";

(()=>{
  const chart=globalThis.DruMusterChart;
  const canvas=document.querySelector("#chart");
  const wrap=document.querySelector("#chartWrap");
  if(!chart||!canvas||!wrap||typeof chart.draw!=="function")return;

  const LABELS=["CYMBAL","HI-HAT / RIDE / OTHER","SNARE / TOMS"];
  const isMobile=()=>chart.isMobileLayout?chart.isMobileLayout():!!globalThis.matchMedia?.("(hover:none) and (pointer:coarse) and (max-width:900px)")?.matches;

  function geometry(){
    const h=canvas.clientHeight,
          kickH=Math.max(16,h*.12),
          mainH=h-kickH,
          laneH=mainH/3,
          labelFont=Math.max(9,laneH*.13);
    return {h,kickH,mainH,laneH,labelFont};
  }

  /* The original renderer places the three main labels at laneTop + 6px.
     On mobile, repaint only the label strip and put each label on the exact
     vertical centreline of its lane. KICK is already centre-based, but repaint
     it too so every lane uses the same baseline rule. */
  const originalDraw=chart.draw;
  chart.draw=function(args){
    const result=originalDraw(args);
    if(!isMobile())return result;

    const {ctx}=args,{kickH,mainH,laneH,labelFont}=geometry();
    ctx.save();
    ctx.font=`700 ${labelFont}px system-ui,sans-serif`;
    const maxLabelW=Math.max(...LABELS.map(t=>ctx.measureText(t).width),ctx.measureText("KICK · AUTO").width);
    const stripW=Math.ceil(maxLabelW+15);

    for(let i=0;i<3;i++){
      ctx.fillStyle=i%2===0?"#0d1520":"#0a121c";
      ctx.fillRect(0,laneH*i,stripW,laneH);
      if(i>0){
        ctx.strokeStyle="#53677d";
        ctx.lineWidth=1.2;
        ctx.beginPath();
        ctx.moveTo(0,laneH*i+.5);
        ctx.lineTo(stripW,laneH*i+.5);
        ctx.stroke();
      }
    }

    ctx.fillStyle="#090e15";
    ctx.fillRect(0,mainH,stripW,kickH);
    ctx.strokeStyle="#5b6d82";
    ctx.lineWidth=1.2;
    ctx.beginPath();
    ctx.moveTo(0,mainH+.5);
    ctx.lineTo(stripW,mainH+.5);
    ctx.stroke();

    ctx.font=`700 ${labelFont}px system-ui,sans-serif`;
    ctx.textAlign="left";
    ctx.textBaseline="middle";
    ctx.fillStyle="#8b97a6";
    for(let i=0;i<3;i++)ctx.fillText(LABELS[i],7,laneH*(i+.5));
    ctx.fillStyle="#687483";
    ctx.fillText("KICK · AUTO",7,mainH+kickH/2);
    ctx.restore();
    return result;
  };

  /* Normal mobile judgement text uses the exact same lane centrelines.
     Inline top values from judgement-lane-fix.js are overridden after each
     effect placement. Hidden header judgement has no data-lane and is ignored. */
  function syncJudgements(){
    if(!isMobile())return;
    const {laneH}=geometry();
    wrap.querySelectorAll(".lane-judge-fx[data-lane]").forEach(node=>{
      const lane=Number(node.dataset.lane);
      if(!Number.isInteger(lane)||lane<0||lane>2)return;
      const top=`${laneH*(lane+.5)}px`;
      if(node.style.getPropertyValue("top")!==top||node.style.getPropertyPriority("top")!=="important"){
        node.style.setProperty("top",top,"important");
      }
      node.style.setProperty("transform","translate(0,-50%)","important");
    });
  }

  const style=document.createElement("style");
  style.textContent=`
    @media (hover:none) and (pointer:coarse) and (max-width:900px){
      .lane-judge-fx[data-lane] .lane-judge-text{
        font-size:9px!important;
      }
      .lane-judge-fx[data-lane].play .lane-judge-text{
        animation:laneJudgeTextMobileCentered .50s cubic-bezier(.16,.84,.24,1)!important;
      }
    }
    @keyframes laneJudgeTextMobileCentered{
      0%{opacity:0;transform:scaleX(var(--judge-x)) scale(.48)}
      4.8%{opacity:1;transform:scaleX(var(--judge-x)) scale(1.14)}
      10%{transform:scaleX(var(--judge-x)) scale(.98)}
      15.2%{transform:scaleX(var(--judge-x)) scale(1)}
      100%{opacity:.35;transform:scaleX(var(--judge-x)) scale(1)}
    }
  `;
  document.head.appendChild(style);

  const observer=new MutationObserver(()=>requestAnimationFrame(syncJudgements));
  observer.observe(wrap,{subtree:true,childList:true,attributes:true,attributeFilter:["style","class"]});
  new ResizeObserver(()=>requestAnimationFrame(syncJudgements)).observe(wrap);
  addEventListener("resize",()=>requestAnimationFrame(syncJudgements),{passive:true});
  requestAnimationFrame(syncJudgements);
})();
