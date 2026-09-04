(() => {
  'use strict';

  const DB_NAME = 'drumaster-ranking';
  const DB_VERSION = 1;
  const STORE = 'plays';
  const ENDPOINT_KEY = 'drumasterRankingEndpoint';
  const DEFAULT_ENDPOINT = 'https://drumaster-ranking-api.aoka45utau.workers.dev';
  const PLAYER_ID_KEY = 'drumasterPlayerId';
  const PLAYER_NAME_KEY = 'drumasterPlayerName';
  const MERGED_STATE_KEY = 'drumasterRankingMergedState';
  const RETRY_MS = 30000;
  const REQUEST_TIMEOUT_MS = 12000;
  const DEFAULT_RANKING_VERSION = '1';

  let dbPromise;
  let lastCapturedSignature = '';
  let syncing = false;
  let chartHashPromise;
  let lastSyncState = null;

  const uuid = () => crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`;

  function playerId() {
    let value = localStorage.getItem(PLAYER_ID_KEY);
    if (!value) {
      value = uuid();
      localStorage.setItem(PLAYER_ID_KEY, value);
    }
    return value;
  }

  function playerName() {
    let value = localStorage.getItem(PLAYER_NAME_KEY);
    if (!value) {
      value = `PLAYER-${playerId().replace(/-/g, '').slice(-6).toUpperCase()}`;
      localStorage.setItem(PLAYER_NAME_KEY, value);
    }
    return value;
  }

  function endpoint() {
    return (localStorage.getItem(ENDPOINT_KEY) || DEFAULT_ENDPOINT).trim().replace(/\/$/, '');
  }

  function openDb() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORE)) {
          const store = db.createObjectStore(STORE, { keyPath: 'playId' });
          store.createIndex('syncStatus', 'syncStatus', { unique: false });
          store.createIndex('playedAtClient', 'playedAtClient', { unique: false });
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    return dbPromise;
  }

  async function putPlay(play) {
    const db = await openDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.objectStore(STORE).put(play);
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  }

  async function getPlay(playId) {
    const db = await openDb();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly');
      const req = tx.objectStore(STORE).get(playId);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
    });
  }

  async function allPlays() {
    const db = await openDb();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly');
      const req = tx.objectStore(STORE).getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
  }

  async function pendingPlays() {
    const db = await openDb();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly');
      const idx = tx.objectStore(STORE).index('syncStatus');
      const req = idx.getAll('pending');
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
  }

  async function recoverPlayerIdFromLocalHistory() {
    if (localStorage.getItem(PLAYER_ID_KEY)) return;
    try {
      const plays = await allPlays();
      const recovered = plays.find(p => typeof p?.playerId === 'string' && p.playerId.trim())?.playerId?.trim();
      if (recovered) localStorage.setItem(PLAYER_ID_KEY, recovered);
    } catch (error) {
      console.warn('Ranking player identity recovery failed:', error);
    }
  }

  function statusElement() {
    let el = document.getElementById('rankingSyncState');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'rankingSyncState';
    Object.assign(el.style, {
      position: 'fixed', right: '18px', bottom: '14px', zIndex: '2147483000',
      fontFamily: 'Arial, Helvetica, sans-serif', fontSize: '12px', fontWeight: '600',
      color: 'rgba(255,255,255,.88)', background: 'rgba(0,0,0,.24)', pointerEvents: 'none',
      padding: '5px 8px', borderRadius: '6px', letterSpacing: '.02em',
      textShadow: '0 1px 3px rgba(0,0,0,.7)'
    });
    document.body.appendChild(el);
    return el;
  }

  function setStatus(text) {
    statusElement().textContent = text || '';
  }

  async function fetchWithTimeout(url, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      return await fetch(url, { ...options, signal: controller.signal });
    } finally {
      clearTimeout(timer);
    }
  }

  async function sha256(buffer) {
    if (!crypto?.subtle) return null;
    const digest = await crypto.subtle.digest('SHA-256', buffer);
    return [...new Uint8Array(digest)].map(v => v.toString(16).padStart(2, '0')).join('');
  }

  function currentSongId() {
    return document.documentElement.dataset.songId
      || document.body?.dataset.songId
      || localStorage.getItem('drumasterSongId')
      || localStorage.getItem('drumusterSongId')
      || 'nanairo';
  }

  async function chartVersion() {
    if (chartHashPromise) return chartHashPromise;
    chartHashPromise = (async () => {
      const candidates = [
        document.documentElement.dataset.chartPath,
        document.body?.dataset.chartPath,
        `songs/${currentSongId()}/chart.mid`
      ].filter(Boolean);
      for (const path of candidates) {
        try {
          const response = await fetch(path, { cache: 'no-store' });
          if (!response.ok) continue;
          const hash = await sha256(await response.arrayBuffer());
          if (hash) return hash;
        } catch {}
      }
      return 'unknown';
    })();
    return chartHashPromise;
  }

  function numberFrom(selector) {
    const raw = document.querySelector(selector)?.textContent || '';
    const match = raw.replace(/,/g, '').match(/-?\d+/);
    return match ? Number(match[0]) : 0;
  }

  function detectMode() {
    return document.querySelector('#playMode')?.value
      || document.querySelector('[name="playMode"]:checked')?.value
      || document.body?.dataset.playMode
      || 'normal';
  }

  async function rebuildMergedState() {
    const plays = await allPlays();
    const bestByBoard = {};
    for (const play of plays) {
      if (!play || play.autoPlay || play.noScore) continue;
      const key = `${play.songId || 'unknown'}::${play.chartId || 'default'}::${play.rankingVersion || DEFAULT_RANKING_VERSION}`;
      const current = bestByBoard[key];
      if (!current || Number(play.score || 0) > Number(current.score || 0)) {
        bestByBoard[key] = {
          playId: play.playId,
          songId: play.songId,
          chartId: play.chartId || 'default',
          rankingVersion: play.rankingVersion || DEFAULT_RANKING_VERSION,
          score: Number(play.score || 0),
          perfect: Number(play.perfect || 0),
          great: Number(play.great || 0),
          good: Number(play.good || 0),
          miss: Number(play.miss || 0),
          maxCombo: play.maxCombo == null ? null : Number(play.maxCombo),
          playedAtClient: play.playedAtClient || null
        };
      }
    }
    const merged = {
      playerId: playerId(),
      displayName: playerName(),
      totalPlays: plays.length,
      pendingPlays: plays.filter(p => p?.syncStatus === 'pending').length,
      bestByBoard,
      updatedAt: new Date().toISOString()
    };
    localStorage.setItem(MERGED_STATE_KEY, JSON.stringify(merged));
    window.dispatchEvent(new CustomEvent('drumaster-ranking-synced', { detail: merged }));
    return merged;
  }

  async function captureResult() {
    const result = document.querySelector('#result');
    if (!result || result.classList.contains('hidden')) return;

    const finalText = document.querySelector('#finalScore')?.textContent?.trim() || '';
    const autoplay = result.classList.contains('autoplay') || /AUTO/i.test(finalText);
    const noScore = result.classList.contains('no-score') || document.body?.classList.contains('no-score');
    if (autoplay || noScore) {
      setStatus('ランキング対象外');
      return;
    }

    const score = numberFrom('#finalScore');
    const perfect = numberFrom('#perfectCount');
    const great = numberFrom('#greatCount');
    const good = numberFrom('#goodCount');
    const miss = numberFrom('#missCount');
    const signature = `${currentSongId()}:${score}:${perfect}:${great}:${good}:${miss}:${Date.now() >> 10}`;
    if (signature === lastCapturedSignature) return;
    lastCapturedSignature = signature;

    const now = new Date().toISOString();
    const play = {
      playId: uuid(), playerId: playerId(), displayName: playerName(),
      songId: currentSongId(), chartId: document.body?.dataset.chartId || 'default',
      rankingVersion: document.body?.dataset.rankingVersion || DEFAULT_RANKING_VERSION,
      chartVersion: await chartVersion(), gameVersion: document.documentElement.dataset.gameVersion || 'pc-ranking-20260905',
      score, perfect, great, good, miss, noteCount: perfect + great + good + miss,
      maxCombo: numberFrom('#maxCombo') || null, playMode: detectMode(),
      autoPlay: false, noScore: false, playedAtClient: now, createdAtLocal: now,
      syncStatus: 'pending', retryCount: 0, lastAttemptAt: null, lastError: null, serverResult: null
    };

    if (play.noteCount < 1) return;
    await putPlay(play);
    await rebuildMergedState();
    setStatus('スコア保存済み · オンライン同期中…');
    syncAll().catch(console.error);
  }

  async function uploadPlay(play, base) {
    const response = await fetchWithTimeout(`${base}/v1/plays`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(play),
      cache: 'no-store'
    });
    if (!response.ok) {
      const text = await response.text().catch(() => '');
      throw new Error(`upload HTTP ${response.status}${text ? `: ${text.slice(0, 160)}` : ''}`);
    }
    const result = await response.json().catch(() => ({}));
    play.syncStatus = 'synced';
    play.lastAttemptAt = new Date().toISOString();
    play.lastError = null;
    play.serverResult = result;
    await putPlay(play);
    return result;
  }

  async function pushPending(base) {
    const queue = await pendingPlays();
    let uploaded = 0;
    let failed = 0;
    let lastRank = null;
    for (const play of queue) {
      try {
        play.lastAttemptAt = new Date().toISOString();
        const result = await uploadPlay(play, base);
        uploaded++;
        if (Number.isFinite(result?.rank)) lastRank = result;
      } catch (error) {
        failed++;
        play.syncStatus = 'pending';
        play.retryCount = (play.retryCount || 0) + 1;
        play.lastAttemptAt = new Date().toISOString();
        play.lastError = String(error?.message || error);
        await putPlay(play);
        console.warn('Ranking upload failed:', error);
      }
    }
    return { queued: queue.length, uploaded, failed, lastRank };
  }

  async function pullServerHistory(base) {
    const response = await fetchWithTimeout(`${base}/v1/players/${encodeURIComponent(playerId())}/plays?limit=5000`, {
      cache: 'no-store',
      headers: { 'accept': 'application/json' }
    });
    if (response.status === 404) return { remoteCount: 0, added: 0 };
    if (!response.ok) {
      const text = await response.text().catch(() => '');
      throw new Error(`history HTTP ${response.status}${text ? `: ${text.slice(0, 160)}` : ''}`);
    }
    const payload = await response.json();
    const plays = Array.isArray(payload?.plays) ? payload.plays : [];
    let added = 0;
    for (const remote of plays) {
      if (!remote?.playId) continue;
      if (await getPlay(remote.playId)) continue;
      await putPlay({
        ...remote,
        playerId: remote.playerId || playerId(),
        displayName: remote.displayName || playerName(),
        autoPlay: false,
        noScore: false,
        createdAtLocal: remote.createdAtLocal || remote.playedAtClient || remote.receivedAtServer || new Date().toISOString(),
        syncStatus: 'synced',
        retryCount: 0,
        lastAttemptAt: new Date().toISOString(),
        lastError: null,
        serverResult: { importedFromServer: true }
      });
      added++;
    }
    return { remoteCount: plays.length, added };
  }

  async function syncAll() {
    const base = endpoint();
    if (!base || syncing) return lastSyncState;
    syncing = true;
    setStatus('ランキング同期中…');
    const startedAt = new Date().toISOString();
    try {
      await recoverPlayerIdFromLocalHistory();
      const pushed = await pushPending(base);
      const pulled = await pullServerHistory(base);
      const merged = await rebuildMergedState();
      lastSyncState = {
        ok: pushed.failed === 0,
        startedAt,
        completedAt: new Date().toISOString(),
        playerId: playerId(),
        pushed,
        pulled,
        merged
      };

      if (pushed.failed > 0) {
        setStatus(`同期一部失敗 · ${pushed.failed}件を自動再送`);
      } else if (pushed.lastRank) {
        const r = pushed.lastRank;
        setStatus(`WORLD RANK #${r.rank}${r.totalPlayers ? ` / ${r.totalPlayers}` : ''} · 同期済み ${merged.totalPlays}件`);
      } else {
        setStatus(`ランキング同期済み · ${merged.totalPlays}件${pulled.added ? `（オンラインから${pulled.added}件追加）` : ''}`);
      }
      return lastSyncState;
    } catch (error) {
      lastSyncState = {
        ok: false,
        startedAt,
        completedAt: new Date().toISOString(),
        playerId: localStorage.getItem(PLAYER_ID_KEY) || null,
        error: String(error?.message || error)
      };
      console.warn('Ranking sync failed:', error);
      setStatus(`ランキング同期失敗 · ${String(error?.message || error).slice(0, 80)}`);
      return lastSyncState;
    } finally {
      syncing = false;
    }
  }

  function watchResult() {
    const result = document.querySelector('#result');
    if (!result) return;
    const observer = new MutationObserver(() => captureResult().catch(console.error));
    observer.observe(result, { attributes: true, attributeFilter: ['class'] });
    captureResult().catch(console.error);
  }

  async function init() {
    statusElement();
    setStatus('ランキング同期を確認中…');
    await recoverPlayerIdFromLocalHistory();
    watchResult();
    await rebuildMergedState().catch(console.warn);
    syncAll().catch(console.error);
    addEventListener('online', () => syncAll().catch(console.error));
    addEventListener('focus', () => syncAll().catch(console.error));
    setInterval(() => syncAll().catch(console.error), RETRY_MS);
    document.addEventListener('click', (event) => {
      if (event.target?.closest?.('#home,.home,[data-action="home"]')) syncAll().catch(console.error);
    }, true);
  }

  window.DruMasterRanking = {
    syncPending: syncAll,
    syncAll,
    getSyncState: () => lastSyncState,
    getMergedState() {
      try { return JSON.parse(localStorage.getItem(MERGED_STATE_KEY) || 'null'); }
      catch { return null; }
    },
    getPlayerId: playerId,
    setEndpoint(value) {
      localStorage.setItem(ENDPOINT_KEY, String(value || '').trim());
      syncAll().catch(console.error);
    },
    getEndpoint: endpoint,
    setPlayerName(value) {
      localStorage.setItem(PLAYER_NAME_KEY, String(value || '').trim() || playerName());
      rebuildMergedState().catch(console.error);
    },
    getPlayerName: playerName
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
