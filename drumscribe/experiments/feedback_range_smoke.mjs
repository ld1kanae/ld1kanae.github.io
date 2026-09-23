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
  status:document.querySelector('#reviewStatus')?.textContent
}));
console.log('STATE',JSON.stringify(state));
console.log('ERRORS',JSON.stringify(errors));

if(state.popoverHidden!==false) throw new Error('review popover did not open');
if(!state.apiSelection || !(state.apiSelection.end>state.apiSelection.start)) throw new Error('review selection was not created');
if(!state.range || state.range.includes('未選択')) throw new Error('selection label was not updated');
if(errors.length) throw new Error(errors.join(' | '));

await browser.close();
