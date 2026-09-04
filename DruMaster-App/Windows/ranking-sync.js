(() => {
  'use strict';

  const DB_NAME = 'drumaster-ranking';
  const DB_VERSION = 1;
  const STORE = 'plays';
  const ENDPOINT_KEY = 'drumasterRankingEndpoint';
  const DEFAULT_ENDPOINT = 'https://drumaster-ranking-api.aoka45utau.workers.dev';
  const PLAYER_ID_KEY = 'drumasterPlayerId';
  const PLAYER_NAME_KEY = 'drumasterPlayerName';
  const RETRY_MS = 30000;
  const DEFAULT_RANKING_VERSION = '1';

  let dbPromise;
  let lastCapturedSignature = '';
  let syncing = false;
  let chartHashPromise;

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

  function statusElement() {
    let el = document.getElementById('rankingSyncState');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'rankingSyncState';
    Object.assign(el.style, {
      position: 'fixed', right: '18px', bottom: '14px', zIndex: '2147483000',
      fontFamily: 'Arial, Helvetica, sans-serif', fontSize: '12px', fontWeight: '600',
      color: 'rgba(255,255,255,.76)', background: 'transparent', pointerEvents: 'none',
      letterSpacing: '.02em', textShadow: '0 1px 3px rgba(0,0,0,.7)'
    });
    document.body.appendChild(el);
    return el;
  }

  function setStatus(text) {
    statusElement().textContent = text || '';
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
      chartVersion: await chartVersion(), gameVersion: document.documentElement.dataset.gameVersion || 'pc-ranking-20260902',
      score, perfect, great, good, miss, noteCount: perfect + great + good + miss,
      maxCombo: numberFrom('#maxCombo') || null, playMode: detectMode(),
      autoPlay: false, noScore: false, playedAtClient: now, createdAtLocal: now,
      syncStatus: 'pending', retryCount: 0, lastAttemptAt: null, lastError: null, serverResult: null
    };

    if (play.noteCount < 1) return;
    await putPlay(play);
    setStatus('ランキング同期中…');
    syncAll().catch(console.error);
  }

  async function uploadPlay(play, base) {
    const response = await fetch(`${base}/v1/plays`, {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(play)
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json().catch(() => ({}));
    play.syncStatus = 'synced';
    play.lastAttemptAt = new Date().toISOString();
    play.lastError = null;
    play.serverResult = result;
    await putPlay(play);
    if (Number.isFinite(result.rank)) setStatus(`WORLD RANK #${result.rank}${result.totalPlayers ? ` / ${result.totalPlayers}` : ''}`);
    else setStatus('ランキング同期済み');
  }

  async function pushPending(base) {
    const queue = await pendingPlays();
    for (const play of queue) {
      try {
        play.lastAttemptAt = new Date().toISOString();
        await uploadPlay(play, base);
      } catch (error) {
        play.syncStatus = 'pending';
        play.retryCount = (play.retryCount || 0) + 1;
        play.lastAttemptAt = new Date().toISOString();
        play.lastError = String(error?.message || error);
        await putPlay(play);
        setStatus('ランキング未同期 · 自動再送します');
        throw error;
      }
    }
  }

  async function pullServerHistory(base) {
    const response = await fetch(`${base}/v1/players/${encodeURIComponent(playerId())}/plays`, { cache: 'no-store' });
    if (response.status === 404) return 0;
    if (!response.ok) throw new Error(`history HTTP ${response.status}`);
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
    return added;
  }

  async function syncAll() {
    const base = endpoint();
    if (!base || !navigator.onLine || syncing) return;
    syncing = true;
    try {
      await pushPending(base).catch(() => {});
      try {
        const added = await pullServerHistory(base);
        if (added > 0) setStatus(`ランキング同期済み · ${added}件取得`);
      } catch (error) {
        console.warn('Ranking history pull unavailable:', error);
      }
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

  function init() {
    statusElement();
    watchResult();
    syncAll().catch(console.error);
    addEventListener('online', () => syncAll().catch(console.error));
    setInterval(() => syncAll().catch(console.error), RETRY_MS);
    document.addEventListener('click', (event) => {
      if (event.target?.closest?.('#home,.home,[data-action="home"]')) syncAll().catch(console.error);
    }, true);
  }

  window.DruMasterRanking = {
    syncPending: syncAll,
    syncAll,
    setEndpoint(value) { localStorage.setItem(ENDPOINT_KEY, String(value || '').trim()); syncAll().catch(console.error); },
    getEndpoint: endpoint,
    setPlayerName(value) { localStorage.setItem(PLAYER_NAME_KEY, String(value || '').trim() || playerName()); },
    getPlayerName: playerName
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
