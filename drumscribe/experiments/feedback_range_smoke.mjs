import { chromium } from 'playwright';

const browser=await chromium.launch({headless:true,args:['--autoplay-policy=no-user-gesture-required']});
const page=await browser.newPage({viewport:{width:1280,height:900}});
const errors=[];
page.on('console',msg=>{ if(msg.type()==='error') errors.push('console: '+msg.text()); });
page.on('pageerror',err=>errors.push('pageerror: '+String(err)));

const url=process.env.DRUMSCRIBE_FEEDBACK_URL||'https://ld1kanae.github.io/drumscribe/feedback.html';
console.log('URL',url);
await page.goto(url,{waitUntil:'domcontentloaded',timeout:60000});

await page.selectOption('#example','nanairo');
await page.waitForFunction(()=>!document.querySelector('#analyze')?.disabled,{},{timeout:60000});
console.log('FILE',await page.locator('#fileName').textContent());
await page.click('#analyze');
await page.waitForFunction(()=>!document.querySelector('#result')?.hidden,{},{timeout:180000});
await page.waitForFunction(()=>window.DrumScribeTimeline?.getDuration?.()>0,{},{timeout:30000});
console.log('RESULT',await page.locator('#resultSummary').textContent());

const canvas=page.locator('#timeline');
await canvas.scrollIntoViewIfNeeded();
const box=await canvas.boundingBox();
if(!box) throw new Error('timeline has no bounding box');
const y=box.y+box.height*0.45;
const x1=box.x+box.width*0.25;
const x2=box.x+box.width*0.48;

await page.mouse.move(x1,y);
await page.mouse.down();
await page.mouse.move(x2,y,{steps:12});
await page.mouse.up();
await page.waitForTimeout(300);

const state=await page.evaluate(()=>({
  popoverHidden:document.querySelector('#reviewPopover')?.hidden,
  range:document.querySelector('#selectionRange')?.textContent,
  hint:document.querySelector('#selectionHint')?.textContent,
  apiSelection:window.DrumScribeTimeline?.getSelection?.(),
  duration:window.DrumScribeTimeline?.getDuration?.(),
  status:document.querySelector('#reviewStatus')?.textContent,
  beatTimes:window.DrumScribeTimeline?.getBeatTimes?.()||[]
}));
console.log('STATE',JSON.stringify(state));
console.log('ERRORS',JSON.stringify(errors));

if(state.popoverHidden!==false) throw new Error('review popover did not open');
if(!state.apiSelection || !(state.apiSelection.end>state.apiSelection.start)) throw new Error('review selection was not created');
if(!state.range || state.range.includes('未選択')) throw new Error('selection label was not updated');
if(String(state.hint||'').includes('拍')) throw new Error('review range is still beat-snapped');
const nearestBeatDistance=value=>Math.min(...state.beatTimes.map(t=>Math.abs(t-value)));
if(state.beatTimes.length>2 && nearestBeatDistance(state.apiSelection.start)<.002 && nearestBeatDistance(state.apiSelection.end)<.002){
  throw new Error('both review edges still align to beat grid');
}

await page.click('#clearSelection');
await canvas.scrollIntoViewIfNeeded();
const seekBox=await canvas.boundingBox();
if(!seekBox) throw new Error('timeline lost its bounding box');
const clickX=seekBox.x+seekBox.width*.37,clickY=seekBox.y+seekBox.height*.45;
const rawClickTime=await page.evaluate(x=>window.DrumScribeTimeline.clientXToTime(x),clickX);
const expectedBeat=await page.evaluate(t=>window.DrumScribeTimeline.snapTimeToBeat(t),rawClickTime);
await page.mouse.click(clickX,clickY);
await page.waitForTimeout(100);
const snappedTime=await page.evaluate(()=>window.DrumScribeTimeline.getCurrentTime());
console.log('SEEK_SNAP',JSON.stringify({rawClickTime,expectedBeat,snappedTime}));
if(Math.abs(snappedTime-expectedBeat)>.003) throw new Error('manual timeline seek did not snap to beat');

await page.evaluate(({x1,x2,y})=>{
  const canvas=document.querySelector('#timeline');
  const mk=(x)=>new Touch({identifier:7,target:canvas,clientX:x,clientY:y,screenX:x,screenY:y,pageX:x,pageY:y,radiusX:1,radiusY:1,force:.5});
  const a=mk(x1),b=mk(x2);
  canvas.dispatchEvent(new TouchEvent('touchstart',{touches:[a],targetTouches:[a],changedTouches:[a],bubbles:true,cancelable:true}));
  window.dispatchEvent(new TouchEvent('touchmove',{touches:[b],targetTouches:[b],changedTouches:[b],bubbles:true,cancelable:true}));
  window.dispatchEvent(new TouchEvent('touchend',{touches:[],targetTouches:[],changedTouches:[b],bubbles:true,cancelable:true}));
},{x1:seekBox.x+seekBox.width*.58,x2:seekBox.x+seekBox.width*.72,y:seekBox.y+seekBox.height*.45});
await page.waitForTimeout(100);
const touchState=await page.evaluate(()=>({popoverHidden:document.querySelector('#reviewPopover')?.hidden,selection:window.DrumScribeTimeline?.getSelection?.()}));
console.log('TOUCH_STATE',JSON.stringify(touchState));
if(touchState.popoverHidden!==false||!touchState.selection||!(touchState.selection.end>touchState.selection.start)) throw new Error('touch range selection failed');

if(errors.length) throw new Error(errors.join(' | '));

await browser.close();
