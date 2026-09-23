// Audio-derived downbeats can support a 3/4 passage when the fixed 4/4
// grid systematically disagrees. The score and guard mirror experiment v22.
const GROUP={36:'kick',38:'snare',42:'hat',44:'pedal_hat',45:'tom',49:'crash',51:'ride'};
const CFG={penalty3:.46,switch:.62,head:1,pattern:.55,runBonus:.16};

export function inferBars(events,bpm,phase,duration,downbeats=[]){
  const beat=60/bpm;
  const n=Math.max(8,Math.ceil((duration-phase)/beat)+4);
  const f=Array.from({length:n},()=>({kick:0,snare:0,hat:0,pedal_hat:0,tom:0,crash:0,ride:0,head:0}));
  for(const e of events){
    const g=GROUP[e.note],i=Math.round((e.time-phase)/beat);
    if(!g||i<0||i>=n)continue;
    const d=Math.abs(e.time-phase-i*beat);
    if(d>.2*beat)continue;
    const v=(e.velocity||90)/127*Math.exp(-.5*(d/(.1*beat))**2);
    f[i][g]=Math.max(f[i][g],v);
  }
  for(let i=0;i<n;i++){
    const x=f[i];
    x.head=1.35*x.kick+2.35*x.crash+.55*x.tom+.18*x.ride-.62*x.snare;
    if(i)x.head+=.32*f[i-1].tom+.18*f[i-1].snare;
  }
  const downs=downbeats.filter(Number.isFinite).sort((a,b)=>a-b);
  const residual=downs.map(t=>Math.abs(t-(phase+Math.round((t-phase)/(4*beat))*4*beat))/beat).sort((a,b)=>a-b);
  const variable=downs.length>0&&residual[Math.floor(residual.length/2)]>=.5;
  // Walk the sorted downbeats once; evaluating every bar against every
  // downbeat would grow quadratically on long recordings.
  const support=Array(n).fill(0);let k=0;
  for(let i=0;i<n;i++){
    const t=phase+i*beat;
    while(k+1<downs.length&&Math.abs(downs[k+1]-t)<Math.abs(downs[k]-t))k++;
    if(downs.length)support[i]=Math.exp(-.5*((downs[k]-t)/(.16*beat))**2);
  }
  const dp=Array.from({length:n},()=>new Map());
  dp[0].set(0,{score:0,previous:null});
  for(let i=0;i<n;i++)for(const [last,state] of dp[i])for(const L of (variable?[4,3]:[4])){
    const j=i+L;if(j>=n)continue;
    const x=f[i],interior=Array.from({length:L-1},(_,q)=>f[i+q+1].head).reduce((a,b)=>a+b,0)/(L-1);
    const patt=L===4?.52*(f[i+1].snare+f[i+3].snare)+.28*f[i+2].kick+.15*x.kick-.22*(x.snare+f[i+2].snare):
      .42*Math.max(f[i+1].snare,f[i+2].snare)+.16*x.kick-.24*x.snare;
    let score=state.score+x.head+.4*support[i]+CFG.pattern*patt+.35*(x.head-interior)-(L===3?CFG.penalty3:0);
    if(state.previous)score+=last===L?CFG.runBonus:-CFG.switch;
    if(downs.length)score+=.14*support[j];
    if(!dp[j].has(L)||score>dp[j].get(L).score)dp[j].set(L,{score,previous:{index:i,last}});
  }
  const target=Math.max(0,Math.floor((duration-phase)/beat));
  const ends=[];
  for(let i=Math.max(0,target-6);i<n;i++)for(const [last,state] of dp[i])ends.push({index:i,last,...state});
  ends.sort((a,b)=>Math.abs(a.index-target)-Math.abs(b.index-target)||b.score-a.score);
  const path=[];let cur=ends[0];
  while(cur?.previous){
    path.push({time:phase+cur.previous.index*beat,beatIndex:cur.previous.index,numerator:cur.last,denominator:4});
    const {index,last}=cur.previous;
    cur={...dp[index].get(last),last};
  }
  path.reverse();
  return {bars:path.filter(b=>b.time>=0&&b.time<=duration),variableMeterEnabled:variable,externalDownbeats:downs.length};
}

export function parseBeatThis(text){
  return text.split(/\r?\n/).map(line=>line.trim().split(/\s+/)).filter(parts=>parts.length>=2&&Number(parts[1])===1).map(parts=>Number(parts[0])).filter(Number.isFinite);
}
