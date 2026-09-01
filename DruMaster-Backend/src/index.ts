export interface Env {
  DB: D1Database;
}

type JsonRecord = Record<string, unknown>;

type PlayInput = {
  playId: string;
  playerId: string;
  displayName: string;
  songId: string;
  chartId: string;
  rankingVersion: string;
  chartVersion: string;
  gameVersion: string;
  score: number;
  perfect: number;
  great: number;
  good: number;
  miss: number;
  noteCount: number;
  maxCombo: number | null;
  playMode: string;
  autoPlay: boolean;
  noScore: boolean;
  playedAtClient: string;
};

const CORS_HEADERS = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET,POST,OPTIONS',
  'access-control-allow-headers': 'content-type',
  'access-control-max-age': '86400',
};

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      ...CORS_HEADERS,
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
    },
  });
}

function error(message: string, status = 400, details?: unknown): Response {
  return json({ ok: false, error: message, ...(details === undefined ? {} : { details }) }, status);
}

function isObject(value: unknown): value is JsonRecord {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function cleanString(value: unknown, name: string, maxLength: number, pattern?: RegExp): string {
  if (typeof value !== 'string') throw new Error(`${name} must be a string`);
  const out = value.trim();
  if (!out || out.length > maxLength) throw new Error(`${name} is invalid`);
  if (pattern && !pattern.test(out)) throw new Error(`${name} has invalid characters`);
  return out;
}

function cleanInt(value: unknown, name: string, min: number, max: number): number {
  if (!Number.isInteger(value) || (value as number) < min || (value as number) > max) {
    throw new Error(`${name} is invalid`);
  }
  return value as number;
}

function parsePlay(body: unknown): PlayInput {
  if (!isObject(body)) throw new Error('JSON object required');

  const idPattern = /^[A-Za-z0-9._:-]+$/;
  const playId = cleanString(body.playId, 'playId', 128, idPattern);
  const playerId = cleanString(body.playerId, 'playerId', 128, idPattern);
  const songId = cleanString(body.songId, 'songId', 80, idPattern);
  const chartId = cleanString(body.chartId, 'chartId', 80, idPattern);
  const rankingVersion = cleanString(body.rankingVersion, 'rankingVersion', 64, idPattern);
  const chartVersion = cleanString(body.chartVersion, 'chartVersion', 128);
  const gameVersion = cleanString(body.gameVersion, 'gameVersion', 128);
  const playMode = cleanString(body.playMode, 'playMode', 64, idPattern);

  let displayName = cleanString(body.displayName, 'displayName', 32)
    .replace(/[\u0000-\u001f\u007f]/g, '')
    .trim();
  if (!displayName) displayName = 'PLAYER';

  if (body.autoPlay !== false) throw new Error('AUTO PLAY scores are not ranked');
  if (body.noScore !== false) throw new Error('NO SCORE results are not ranked');
  if (/auto|no[-_ ]?score/i.test(playMode)) throw new Error('This play mode is not ranked');

  const score = cleanInt(body.score, 'score', 0, 1_000_000);
  const perfect = cleanInt(body.perfect, 'perfect', 0, 1_000_000);
  const great = cleanInt(body.great, 'great', 0, 1_000_000);
  const good = cleanInt(body.good, 'good', 0, 1_000_000);
  const miss = cleanInt(body.miss, 'miss', 0, 1_000_000);
  const noteCount = cleanInt(body.noteCount, 'noteCount', 1, 1_000_000);
  if (perfect + great + good + miss !== noteCount) throw new Error('noteCount does not match judgement counts');

  let maxCombo: number | null = null;
  if (body.maxCombo !== null && body.maxCombo !== undefined) {
    maxCombo = cleanInt(body.maxCombo, 'maxCombo', 0, noteCount);
  }

  const playedAtClient = cleanString(body.playedAtClient, 'playedAtClient', 64);
  const playedDate = new Date(playedAtClient);
  if (!Number.isFinite(playedDate.getTime())) throw new Error('playedAtClient is invalid');

  return {
    playId,
    playerId,
    displayName,
    songId,
    chartId,
    rankingVersion,
    chartVersion,
    gameVersion,
    score,
    perfect,
    great,
    good,
    miss,
    noteCount,
    maxCombo,
    playMode,
    autoPlay: false,
    noScore: false,
    playedAtClient: playedDate.toISOString(),
  };
}

async function getPlayerRank(
  db: D1Database,
  playerId: string,
  songId: string,
  chartId: string,
  rankingVersion: string,
) {
  const row = await db.prepare(`
    WITH candidate AS (
      SELECT
        play_id,
        player_id,
        display_name,
        score,
        played_at_client,
        received_at_server,
        ROW_NUMBER() OVER (
          PARTITION BY player_id
          ORDER BY score DESC, received_at_server ASC, play_id ASC
        ) AS player_best
      FROM plays
      WHERE song_id = ?1 AND chart_id = ?2 AND ranking_version = ?3
    ), best AS (
      SELECT * FROM candidate WHERE player_best = 1
    ), ranked AS (
      SELECT
        *,
        ROW_NUMBER() OVER (
          ORDER BY score DESC, received_at_server ASC, play_id ASC
        ) AS rank
      FROM best
    )
    SELECT
      play_id AS playId,
      player_id AS playerId,
      display_name AS displayName,
      score,
      played_at_client AS playedAtClient,
      received_at_server AS receivedAtServer,
      rank,
      (SELECT COUNT(*) FROM ranked) AS totalPlayers
    FROM ranked
    WHERE player_id = ?4
    LIMIT 1
  `).bind(songId, chartId, rankingVersion, playerId).first<Record<string, unknown>>();

  return row || null;
}

async function submitPlay(request: Request, env: Env): Promise<Response> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return error('Invalid JSON');
  }

  let play: PlayInput;
  try {
    play = parsePlay(body);
  } catch (cause) {
    return error(cause instanceof Error ? cause.message : 'Invalid play');
  }

  const existing = await env.DB.prepare(
    'SELECT play_id FROM plays WHERE play_id = ?1 LIMIT 1',
  ).bind(play.playId).first();

  if (existing) {
    const rank = await getPlayerRank(env.DB, play.playerId, play.songId, play.chartId, play.rankingVersion);
    return json({
      ok: true,
      accepted: true,
      duplicate: true,
      personalBest: rank?.playId === play.playId,
      ...(rank || {}),
    });
  }

  const receivedAtServer = new Date().toISOString();

  try {
    await env.DB.batch([
      env.DB.prepare(`
        INSERT INTO players(player_id, display_name, created_at, updated_at)
        VALUES(?1, ?2, ?3, ?3)
        ON CONFLICT(player_id) DO UPDATE SET
          display_name = excluded.display_name,
          updated_at = excluded.updated_at
      `).bind(play.playerId, play.displayName, receivedAtServer),
      env.DB.prepare(`
        INSERT INTO plays(
          play_id, player_id, display_name, song_id, chart_id, ranking_version,
          chart_version, game_version, score, perfect, great, good, miss,
          note_count, max_combo, play_mode, played_at_client, received_at_server
        ) VALUES(
          ?1, ?2, ?3, ?4, ?5, ?6,
          ?7, ?8, ?9, ?10, ?11, ?12, ?13,
          ?14, ?15, ?16, ?17, ?18
        )
      `).bind(
        play.playId,
        play.playerId,
        play.displayName,
        play.songId,
        play.chartId,
        play.rankingVersion,
        play.chartVersion,
        play.gameVersion,
        play.score,
        play.perfect,
        play.great,
        play.good,
        play.miss,
        play.noteCount,
        play.maxCombo,
        play.playMode,
        play.playedAtClient,
        receivedAtServer,
      ),
    ]);
  } catch (cause) {
    const message = cause instanceof Error ? cause.message : String(cause);
    if (/UNIQUE|constraint/i.test(message)) {
      const rank = await getPlayerRank(env.DB, play.playerId, play.songId, play.chartId, play.rankingVersion);
      return json({ ok: true, accepted: true, duplicate: true, ...(rank || {}) });
    }
    console.error('D1 submit failure', cause);
    return error('Database write failed', 500);
  }

  const rank = await getPlayerRank(env.DB, play.playerId, play.songId, play.chartId, play.rankingVersion);
  return json({
    ok: true,
    accepted: true,
    duplicate: false,
    personalBest: rank?.playId === play.playId,
    ...(rank || {}),
  }, 201);
}

async function leaderboard(url: URL, env: Env): Promise<Response> {
  const match = url.pathname.match(/^\/v1\/leaderboards\/([^/]+)\/([^/]+)$/);
  if (!match) return error('Not found', 404);

  let songId: string;
  let chartId: string;
  let rankingVersion: string;
  try {
    songId = cleanString(decodeURIComponent(match[1]), 'songId', 80, /^[A-Za-z0-9._:-]+$/);
    chartId = cleanString(decodeURIComponent(match[2]), 'chartId', 80, /^[A-Za-z0-9._:-]+$/);
    rankingVersion = cleanString(url.searchParams.get('rankingVersion') || '1', 'rankingVersion', 64, /^[A-Za-z0-9._:-]+$/);
  } catch (cause) {
    return error(cause instanceof Error ? cause.message : 'Invalid request');
  }

  const limit = Math.min(100, Math.max(1, Number.parseInt(url.searchParams.get('limit') || '50', 10) || 50));
  const offset = Math.max(0, Number.parseInt(url.searchParams.get('offset') || '0', 10) || 0);

  const result = await env.DB.prepare(`
    WITH candidate AS (
      SELECT
        play_id,
        player_id,
        display_name,
        score,
        perfect,
        great,
        good,
        miss,
        max_combo,
        played_at_client,
        received_at_server,
        ROW_NUMBER() OVER (
          PARTITION BY player_id
          ORDER BY score DESC, received_at_server ASC, play_id ASC
        ) AS player_best
      FROM plays
      WHERE song_id = ?1 AND chart_id = ?2 AND ranking_version = ?3
    ), best AS (
      SELECT * FROM candidate WHERE player_best = 1
    ), ranked AS (
      SELECT
        *,
        ROW_NUMBER() OVER (
          ORDER BY score DESC, received_at_server ASC, play_id ASC
        ) AS rank
      FROM best
    )
    SELECT
      rank,
      player_id AS playerId,
      display_name AS displayName,
      score,
      perfect,
      great,
      good,
      miss,
      max_combo AS maxCombo,
      played_at_client AS playedAtClient
    FROM ranked
    ORDER BY rank
    LIMIT ?4 OFFSET ?5
  `).bind(songId, chartId, rankingVersion, limit, offset).all();

  const count = await env.DB.prepare(`
    SELECT COUNT(DISTINCT player_id) AS totalPlayers
    FROM plays
    WHERE song_id = ?1 AND chart_id = ?2 AND ranking_version = ?3
  `).bind(songId, chartId, rankingVersion).first<{ totalPlayers: number }>();

  return json({
    ok: true,
    songId,
    chartId,
    rankingVersion,
    totalPlayers: Number(count?.totalPlayers || 0),
    limit,
    offset,
    entries: result.results || [],
  });
}

async function playerBest(url: URL, env: Env): Promise<Response> {
  const match = url.pathname.match(/^\/v1\/players\/([^/]+)\/best$/);
  if (!match) return error('Not found', 404);

  const idPattern = /^[A-Za-z0-9._:-]+$/;
  let playerId: string;
  let songId: string;
  let chartId: string;
  let rankingVersion: string;
  try {
    playerId = cleanString(decodeURIComponent(match[1]), 'playerId', 128, idPattern);
    songId = cleanString(url.searchParams.get('songId'), 'songId', 80, idPattern);
    chartId = cleanString(url.searchParams.get('chartId') || 'default', 'chartId', 80, idPattern);
    rankingVersion = cleanString(url.searchParams.get('rankingVersion') || '1', 'rankingVersion', 64, idPattern);
  } catch (cause) {
    return error(cause instanceof Error ? cause.message : 'Invalid request');
  }

  const rank = await getPlayerRank(env.DB, playerId, songId, chartId, rankingVersion);
  if (!rank) return error('Player has no ranked play for this chart', 404);
  return json({ ok: true, songId, chartId, rankingVersion, ...rank });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS_HEADERS });

    const url = new URL(request.url);

    try {
      if (request.method === 'GET' && url.pathname === '/health') {
        const probe = await env.DB.prepare('SELECT 1 AS ok').first();
        return json({ ok: true, service: 'drumaster-ranking-api', database: !!probe });
      }

      if (request.method === 'POST' && url.pathname === '/v1/plays') {
        return await submitPlay(request, env);
      }

      if (request.method === 'GET' && url.pathname.startsWith('/v1/leaderboards/')) {
        return await leaderboard(url, env);
      }

      if (request.method === 'GET' && /^\/v1\/players\/[^/]+\/best$/.test(url.pathname)) {
        return await playerBest(url, env);
      }

      return error('Not found', 404);
    } catch (cause) {
      console.error('Unhandled request failure', cause);
      return error('Internal server error', 500);
    }
  },
};
