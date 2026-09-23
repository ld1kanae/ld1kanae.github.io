import {buildRhythmGrid,GRID_PPQ as PPQ} from './rhythm-grid.js?v=20260923-grid-v29';

// Standard MIDI file type 0: channel 10 percussion, PPQ 480.
// Preview events stay on the audio timeline. Export uses score-grid ticks plus
// a tempo map so audible timing can follow the source without leaving notes
// between notation subdivisions.
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
  const grid=timing?.rhythmGrid||buildRhythmGrid(events,bpm,{...timing,numerator,denominator});
  const ticksPerBeat=PPQ*4/denominator;

  const packets=[];
  for(const t of grid.tempoMap||[]){
    const us=clamp(Math.round(Number(t.us)||60000000/bpm),1,0xffffff);
    packets.push({tick:Math.max(0,Math.round(Number(t.tick)||0)),order:0,data:[255,81,3,(us>>16)&255,(us>>8)&255,us&255]});
  }
  if(!packets.length){
    const us=Math.round(60000000/bpm);
    packets.push({tick:0,order:0,data:[255,81,3,(us>>16)&255,(us>>8)&255,us&255]});
  }
  packets.push({tick:0,order:0,data:[255,88,4,clamp(numerator,1,255),pow2Exp(denominator),24,8]});

  // A signature event is required at every change, not merely at tick zero.
  // beatIndex is measured from the first audio downbeat; barPad places pickup
  // material before that downbeat without changing the musical grid.
  let previous=numerator;
  for(const bar of timing?.bars||[]){
    if(!Number.isInteger(bar.beatIndex)||bar.beatIndex<0||!Number.isFinite(bar.numerator))continue;
    const next=clamp(Math.round(bar.numerator),1,255);
    if(next===previous)continue;
    const tick=Math.max(0,Math.round((bar.beatIndex+grid.barPad*numerator)*ticksPerBeat));
    packets.push({tick,order:0,data:[255,88,4,next,pow2Exp(bar.denominator||denominator),24,8]});
    previous=next;
  }

  const noteLength=Math.max(1,Math.round(PPQ/16));
  for(let i=0;i<(events||[]).length;i++){
    const e=events[i];
    const tick=Math.max(0,Math.round(grid.eventTicks?.[i]??0));
    const note=clamp(Math.round(Number(e.note)||0),0,127);
    const vel=clamp(Math.round(Number(e.velocity)||90),1,127);
    packets.push({tick,order:2,data:[0x99,note,vel]});
    packets.push({tick:tick+noteLength,order:1,data:[0x89,note,0]});
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
