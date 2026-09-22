// Standard MIDI file type 0: channel 10 percussion, PPQ 480.
const PPQ=480;
const bytes32=x=>[(x>>>24)&255,(x>>>16)&255,(x>>>8)&255,x&255];
const vlq=x=>{const out=[x&127];while(x>>=7)out.unshift((x&127)|128);return out;};
export function midiFile(events,referenceBpm=null){
  const bpm=referenceBpm==null?120:referenceBpm;
  const micros=Math.round(60000000/bpm),ticksPerSecond=PPQ*1000000/micros;
  const packets=[{tick:0,order:0,data:[255,81,3,(micros>>>16)&255,(micros>>>8)&255,micros&255]}];
  for(const e of events){
    const tick=Math.max(0,Math.round(e.time*ticksPerSecond));
    packets.push({tick,order:2,data:[0x99,e.note,Math.max(1,Math.min(127,e.velocity||90))]});
    packets.push({tick:tick+Math.round(.07*ticksPerSecond),order:1,data:[0x89,e.note,0]});
  }
  packets.sort((a,b)=>a.tick-b.tick||a.order-b.order||a.data[1]-b.data[1]);
  const track=[];let prev=0;
  for(const e of packets){track.push(...vlq(e.tick-prev),...e.data);prev=e.tick;}
  track.push(0,255,47,0);
  return new Uint8Array([77,84,104,100,...bytes32(6),0,0,0,1,1,224,77,84,114,107,...bytes32(track.length),...track]);
}
