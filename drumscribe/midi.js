// Standard MIDI file type 0: channel 10 percussion, PPQ 480.
// Preview events stay on the audio timeline. Export can independently align
// the MIDI grid so detected bar heads land exactly on MIDI measure boundaries.
const PPQ=480;
const bytes32=x=>[(x>>>24)&255,(x>>>16)&255,(x>>>8)&255,x&255];
const vlq=x=>{const out=[x&127];while(x>>=7)out.unshift((x&127)|128);return out;};
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const pow2Exp=n=>{
  n=Math.max(1,Math.round(n));
  let e=0,v=1;
  while(v<n&&e<7){v*=2;e++;}
  return e;
};

export function midiFile(events,bpm=120,timing={}){
  bpm=Number.isFinite(bpm)&&bpm>=30&&bpm<=300?bpm:120;
  const numerator=Number.isFinite(timing?.numerator)?Math.max(1,Math.round(timing.numerator)):4;
  const denominator=Number.isFinite(timing?.denominator)?Math.max(1,Math.round(timing.denominator)):4;
  const beatSec=60/bpm*4/denominator;
  const barSec=beatSec*numerator;
  const rawPhase=Number(timing?.barPhaseSec);
  const hasPhase=Number.isFinite(rawPhase)&&barSec>0;
  const phase=hasPhase?((rawPhase%barSec)+barSec)%barSec:0;
  const align=timing?.alignToBar!==false&&hasPhase;

  // Keep events that occur before the first detected downbeat by placing them
  // in a pickup measure. Whole-measure padding never changes grid alignment.
  let barPad=0;
  if(align&&events?.length){
    let minMusical=Infinity;
    for(const e of events)minMusical=Math.min(minMusical,Number(e.time)-phase);
    if(Number.isFinite(minMusical)&&minMusical<0)barPad=Math.ceil(-minMusical/barSec);
  }
  const exportOffsetSec=align?barPad*barSec-phase:0;

  const ticksPerSecond=PPQ*bpm/60;
  const tempo=Math.round(60000000/bpm);
  const packets=[
    {tick:0,order:0,data:[255,81,3,(tempo>>16)&255,(tempo>>8)&255,tempo&255]},
    // FF 58: numerator, log2(denominator), MIDI clocks/metronome, 32nd notes/quarter.
    {tick:0,order:0,data:[255,88,4,clamp(numerator,1,255),pow2Exp(denominator),24,8]},
  ];

  // A signature event is required at every change, not merely at tick zero.
  // beatIndex is measured from the first audio downbeat; exportOffsetSec puts
  // that downbeat at a MIDI bar boundary, including a complete pickup bar.
  let previous=numerator;
  for(const bar of timing?.bars||[]){
    if(!Number.isInteger(bar.beatIndex)||bar.beatIndex<0||!Number.isFinite(bar.numerator))continue;
    const next=clamp(Math.round(bar.numerator),1,255);
    if(next===previous)continue;
    const tick=Math.max(0,Math.round((bar.beatIndex*60/bpm+barPad*barSec)*ticksPerSecond));
    packets.push({tick,order:0,data:[255,88,4,next,pow2Exp(bar.denominator||4),24,8]});
    previous=next;
  }

  for(const e of events||[]){
    const musicalTime=Math.max(0,Number(e.time)+exportOffsetSec);
    const tick=Math.max(0,Math.round(musicalTime*ticksPerSecond));
    const note=clamp(Math.round(Number(e.note)||0),0,127);
    const vel=clamp(Math.round(Number(e.velocity)||90),1,127);
    packets.push({tick,order:2,data:[0x99,note,vel]});
    packets.push({tick:tick+Math.max(1,Math.round(.07*ticksPerSecond)),order:1,data:[0x89,note,0]});
  }

  packets.sort((a,b)=>a.tick-b.tick||a.order-b.order||((a.data[1]||0)-(b.data[1]||0)));
  const track=[];let prev=0;
  for(const e of packets){track.push(...vlq(e.tick-prev),...e.data);prev=e.tick;}
  track.push(0,255,47,0);
  return new Uint8Array([77,84,104,100,...bytes32(6),0,0,0,1,1,224,77,84,114,107,...bytes32(track.length),...track]);
}

export function midiExportTiming(bpm=120,timing={}){
  bpm=Number.isFinite(bpm)&&bpm>=30&&bpm<=300?bpm:120;
  const numerator=Number.isFinite(timing?.numerator)?Math.max(1,Math.round(timing.numerator)):4;
  const denominator=Number.isFinite(timing?.denominator)?Math.max(1,Math.round(timing.denominator)):4;
  const beatSec=60/bpm*4/denominator;
  const barSec=beatSec*numerator;
  const rawPhase=Number(timing?.barPhaseSec);
  const phase=Number.isFinite(rawPhase)&&barSec>0?((rawPhase%barSec)+barSec)%barSec:0;
  return {bpm,numerator,denominator,beatSec,barSec,barPhaseSec:phase};
}
