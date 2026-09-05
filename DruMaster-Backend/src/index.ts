export interface Env { DB: D1Database }
type JsonRecord = Record<string, unknown>;
type PlayInput = {
  playId:string; playerId:string; displayName:string; songId:string; chartId:string;
  rankingVersion:string; chartVersion:string; gameVersion:string; score:number;
  perfect:number; great:number; good:number; miss:number; noteCount:number;
  maxCombo:number|null; playMode:string; autoPlay:boolean; noScore:boolean; playedAtClient:string;
};

const CORS_HEADERS={
  'access-control-allow-origin':'*',
  'access-control-allow-methods':'GET,POST,OPTIONS',
  'access-control-allow-headers':'content-type',
  'access-control-max-age':'86400',
};
const json=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status,headers:{...CORS_HEADERS,'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
const error=(message:string,status=400,details?:unknown)=>json({ok:false,error:message,...(details===undefined?{}:{details})},status);
const isObject=(v:unknown):v is JsonRecord=>!!v&&typeof v==='object'&&!Array.isArray(v);
function cleanString(v:unknown,name:string,max:number,pattern?:RegExp){if(typeof v!=='string')throw new Error(`${name} must be a string`);const s=v.trim();if(!s||s.length>max)throw new Error(`${name} is invalid`);if(pattern&&!pattern.test(s))throw new Error(`${name} has invalid characters`);return s}
function cleanInt(v:unknown,name:string,min:number,max:number){if(!Number.isInteger(v)||(v as number)<min||(v as number)>max)throw new Error(`${name} is invalid`);return v as number}
function parsePlay(body:unknown):PlayInput{
  if(!isObject(body))throw new Error('JSON object required');
  const id=/^[A-Za-z0-9._:-]+$/;
  const playId=cleanString(body.playId,'playId',128,id),playerId=cleanString(body.playerId,'playerId',128,id),songId=cleanString(body.songId,'songId',80,id),chartId=cleanString(body.chartId,'chartId',80,id),rankingVersion=cleanString(body.rankingVersion,'rankingVersion',64,id),chartVersion=cleanString(body.chartVersion,'chartVersion',128),gameVersion=cleanString(body.gameVersion,'gameVersion',128),playMode=cleanString(body.playMode,'playMode',64,id);
  const displayName=cleanString(body.displayName,'displayName',32).replace(/[\u0000-\u001f\u007f]/g,'').trim()||'PLAYER';
  if(body.autoPlay!==false)throw new Error('AUTO PLAY scores are not ranked');
  if(body.noScore!==false)throw new Error('NO SCORE results are not ranked');
  if(/auto|no[-_ ]?score/i.test(playMode))throw new Error('This play mode is not ranked');
  const score=cleanInt(body.score,'score',0,1_000_000),perfect=cleanInt(body.perfect,'perfect',0,1_000_000),great=cleanInt(body.great,'great',0,1_000_000),good=cleanInt(body.good,'good',0,1_000_000),miss=cleanInt(body.miss,'miss',0,1_000_000),noteCount=cleanInt(body.noteCount,'noteCount',1,1_000_000);
  if(perfect+great+good+miss!==noteCount)throw new Error('noteCount does not match judgement counts');
  let maxCombo:number|null=null;if(body.maxCombo!==null&&body.maxCombo!==undefined)maxCombo=cleanInt(body.maxCombo,'maxCombo',0,noteCount);
  const playedAtClient=cleanString(body.playedAtClient,'playedAtClient',64),d=new Date(playedAtClient);if(!Number.isFinite(d.getTime()))throw new Error('playedAtClient is invalid');
  return{playId,playerId,displayName,songId,chartId,rankingVersion,chartVersion,gameVersion,score,perfect,great,good,miss,noteCount,maxCombo,playMode,autoPlay:false,noScore:false,playedAtClient:d.toISOString()};
}
async function getPlayerRank(db:D1Database,playerId:string,songId:string,chartId:string,rankingVersion:string){
  const row=await db.prepare(`WITH candidate AS (SELECT play_id,player_id,display_name,score,played_at_client,received_at_server,ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY score DESC,received_at_server ASC,play_id ASC) AS player_best FROM plays WHERE song_id=?1 AND chart_id=?2 AND ranking_version=?3),best AS (SELECT * FROM candidate WHERE player_best=1),ranked AS (SELECT *,ROW_NUMBER() OVER (ORDER BY score DESC,received_at_server ASC,play_id ASC) AS rank FROM best) SELECT play_id AS playId,player_id AS playerId,display_name AS displayName,score,played_at_client AS playedAtClient,received_at_server AS receivedAtServer,rank,(SELECT COUNT(*) FROM ranked) AS totalPlayers FROM ranked WHERE player_id=?4 LIMIT 1`).bind(songId,chartId,rankingVersion,playerId).first<Record<string,unknown>>();return row||null;
}
async function submitPlay(request:Request,env:Env){
  let body:unknown;try{body=await request.json()}catch{return error('Invalid JSON')}
  let play:PlayInput;try{play=parsePlay(body)}catch(c){return error(c instanceof Error?c.message:'Invalid play')}
  const existing=await env.DB.prepare('SELECT play_id FROM plays WHERE play_id=?1 LIMIT 1').bind(play.playId).first();
  if(existing){const rank=await getPlayerRank(env.DB,play.playerId,play.songId,play.chartId,play.rankingVersion);return json({ok:true,accepted:true,duplicate:true,personalBest:rank?.playId===play.playId,...(rank||{})})}
  const receivedAtServer=new Date().toISOString();
  try{await env.DB.batch([
    env.DB.prepare(`INSERT INTO players(player_id,display_name,created_at,updated_at) VALUES(?1,?2,?3,?3) ON CONFLICT(player_id) DO UPDATE SET display_name=excluded.display_name,updated_at=excluded.updated_at`).bind(play.playerId,play.displayName,receivedAtServer),
    env.DB.prepare(`INSERT INTO plays(play_id,player_id,display_name,song_id,chart_id,ranking_version,chart_version,game_version,score,perfect,great,good,miss,note_count,max_combo,play_mode,played_at_client,received_at_server) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18)`).bind(play.playId,play.playerId,play.displayName,play.songId,play.chartId,play.rankingVersion,play.chartVersion,play.gameVersion,play.score,play.perfect,play.great,play.good,play.miss,play.noteCount,play.maxCombo,play.playMode,play.playedAtClient,receivedAtServer)
  ])}catch(c){const m=c instanceof Error?c.message:String(c);if(/UNIQUE|constraint/i.test(m)){const rank=await getPlayerRank(env.DB,play.playerId,play.songId,play.chartId,play.rankingVersion);return json({ok:true,accepted:true,duplicate:true,...(rank||{})})}console.error('D1 submit failure',c);return error('Database write failed',500)}
  const rank=await getPlayerRank(env.DB,play.playerId,play.songId,play.chartId,play.rankingVersion);return json({ok:true,accepted:true,duplicate:false,personalBest:rank?.playId===play.playId,...(rank||{})},201);
}

async function submitLegacyBest(request:Request,env:Env){
  let body:unknown;try{body=await request.json()}catch{return error('Invalid JSON')}
  if(!isObject(body))return error('JSON object required');
  const id=/^[A-Za-z0-9._:-]+$/;
  let playerId:string,displayName:string,songId:string,chartId:string,rankingVersion:string,score:number,legacySource='default';
  try{
    playerId=cleanString(body.playerId,'playerId',128,id);
    displayName=cleanString(body.displayName,'displayName',32).replace(/[\u0000-\u001f\u007f]/g,'').trim()||'PLAYER';
    songId=cleanString(body.songId,'songId',80,id);
    chartId=cleanString(body.chartId||'default','chartId',80,id);
    rankingVersion=cleanString(body.rankingVersion||'1','rankingVersion',64,id);
    score=cleanInt(body.score,'score',0,1_000_000);
    if(body.legacySource!==undefined)legacySource=cleanString(body.legacySource,'legacySource',64,id);
  }catch(c){return error(c instanceof Error?c.message:'Invalid legacy best')}
  const now=new Date().toISOString();
  const safe=(s:string)=>s.replace(/[^A-Za-z0-9._:-]/g,'_');
  const playId=legacySource==='default'
    ? `legacy:${safe(playerId)}:${safe(songId)}:${safe(chartId)}:${safe(rankingVersion)}`.slice(0,128)
    : `legacy2:${safe(playerId).slice(0,40)}:${safe(songId).slice(0,32)}:${safe(legacySource).slice(0,40)}`.slice(0,128);
  try{await env.DB.batch([
    env.DB.prepare(`INSERT INTO players(player_id,display_name,created_at,updated_at) VALUES(?1,?2,?3,?3) ON CONFLICT(player_id) DO UPDATE SET display_name=excluded.display_name,updated_at=excluded.updated_at`).bind(playerId,displayName,now),
    env.DB.prepare(`INSERT INTO plays(play_id,player_id,display_name,song_id,chart_id,ranking_version,chart_version,game_version,score,perfect,great,good,miss,note_count,max_combo,play_mode,played_at_client,received_at_server) VALUES(?1,?2,?3,?4,?5,?6,'legacy-best-only','legacy-import',?7,0,0,0,0,0,NULL,'legacy',?8,?8) ON CONFLICT(play_id) DO UPDATE SET score=MAX(score,excluded.score),display_name=excluded.display_name,received_at_server=excluded.received_at_server`).bind(playId,playerId,displayName,songId,chartId,rankingVersion,score,now)
  ])}catch(c){console.error('D1 legacy best failure',c);return error('Database write failed',500)}
  const rank=await getPlayerRank(env.DB,playerId,songId,chartId,rankingVersion);
  return json({ok:true,accepted:true,legacyBest:true,legacySource,playId,...(rank||{})},201);
}

async function leaderboard(url:URL,env:Env){
  const m=url.pathname.match(/^\/v1\/leaderboards\/([^/]+)\/([^/]+)$/);if(!m)return error('Not found',404);const id=/^[A-Za-z0-9._:-]+$/;let songId,chartId,rankingVersion;try{songId=cleanString(decodeURIComponent(m[1]),'songId',80,id);chartId=cleanString(decodeURIComponent(m[2]),'chartId',80,id);rankingVersion=cleanString(url.searchParams.get('rankingVersion')||'1','rankingVersion',64,id)}catch(c){return error(c instanceof Error?c.message:'Invalid request')}
  const limit=Math.min(100,Math.max(1,parseInt(url.searchParams.get('limit')||'50')||50)),offset=Math.max(0,parseInt(url.searchParams.get('offset')||'0')||0);
  const result=await env.DB.prepare(`WITH candidate AS (SELECT play_id,player_id,display_name,score,perfect,great,good,miss,max_combo,played_at_client,received_at_server,ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY score DESC,received_at_server ASC,play_id ASC) AS player_best FROM plays WHERE song_id=?1 AND chart_id=?2 AND ranking_version=?3),best AS (SELECT * FROM candidate WHERE player_best=1),ranked AS (SELECT *,ROW_NUMBER() OVER (ORDER BY score DESC,received_at_server ASC,play_id ASC) AS rank FROM best) SELECT rank,player_id AS playerId,display_name AS displayName,score,perfect,great,good,miss,max_combo AS maxCombo,played_at_client AS playedAtClient FROM ranked ORDER BY rank LIMIT ?4 OFFSET ?5`).bind(songId,chartId,rankingVersion,limit,offset).all();
  const count=await env.DB.prepare('SELECT COUNT(DISTINCT player_id) AS totalPlayers FROM plays WHERE song_id=?1 AND chart_id=?2 AND ranking_version=?3').bind(songId,chartId,rankingVersion).first<{totalPlayers:number}>();
  return json({ok:true,songId,chartId,rankingVersion,totalPlayers:Number(count?.totalPlayers||0),limit,offset,entries:result.results||[]});
}
async function playerBest(url:URL,env:Env){
  const m=url.pathname.match(/^\/v1\/players\/([^/]+)\/best$/);if(!m)return error('Not found',404);const id=/^[A-Za-z0-9._:-]+$/;let playerId,songId,chartId,rankingVersion;try{playerId=cleanString(decodeURIComponent(m[1]),'playerId',128,id);songId=cleanString(url.searchParams.get('songId'),'songId',80,id);chartId=cleanString(url.searchParams.get('chartId')||'default','chartId',80,id);rankingVersion=cleanString(url.searchParams.get('rankingVersion')||'1','rankingVersion',64,id)}catch(c){return error(c instanceof Error?c.message:'Invalid request')}
  const rank=await getPlayerRank(env.DB,playerId,songId,chartId,rankingVersion);if(!rank)return error('Player has no ranked play for this chart',404);return json({ok:true,songId,chartId,rankingVersion,...rank});
}
async function playerPlays(url:URL,env:Env){
  const m=url.pathname.match(/^\/v1\/players\/([^/]+)\/plays$/);if(!m)return error('Not found',404);const id=/^[A-Za-z0-9._:-]+$/;let playerId:string;try{playerId=cleanString(decodeURIComponent(m[1]),'playerId',128,id)}catch(c){return error(c instanceof Error?c.message:'Invalid request')}
  const limit=Math.min(5000,Math.max(1,parseInt(url.searchParams.get('limit')||'5000')||5000));
  const result=await env.DB.prepare(`SELECT play_id AS playId,player_id AS playerId,display_name AS displayName,song_id AS songId,chart_id AS chartId,ranking_version AS rankingVersion,chart_version AS chartVersion,game_version AS gameVersion,score,perfect,great,good,miss,note_count AS noteCount,max_combo AS maxCombo,play_mode AS playMode,played_at_client AS playedAtClient,received_at_server AS receivedAtServer FROM plays WHERE player_id=?1 ORDER BY received_at_server ASC,play_id ASC LIMIT ?2`).bind(playerId,limit).all();
  return json({ok:true,playerId,plays:result.results||[]});
}
export default{async fetch(request:Request,env:Env){if(request.method==='OPTIONS')return new Response(null,{status:204,headers:CORS_HEADERS});const url=new URL(request.url);try{
  if(request.method==='GET'&&url.pathname==='/health'){const probe=await env.DB.prepare('SELECT 1 AS ok').first();return json({ok:true,service:'drumaster-ranking-api',database:!!probe})}
  if(request.method==='POST'&&url.pathname==='/v1/plays')return await submitPlay(request,env);
  if(request.method==='POST'&&url.pathname==='/v1/legacy-best')return await submitLegacyBest(request,env);
  if(request.method==='GET'&&url.pathname.startsWith('/v1/leaderboards/'))return await leaderboard(url,env);
  if(request.method==='GET'&&/^\/v1\/players\/[^/]+\/best$/.test(url.pathname))return await playerBest(url,env);
  if(request.method==='GET'&&/^\/v1\/players\/[^/]+\/plays$/.test(url.pathname))return await playerPlays(url,env);
  return error('Not found',404);
}catch(c){console.error('Unhandled request failure',c);return error('Internal server error',500)}}};
