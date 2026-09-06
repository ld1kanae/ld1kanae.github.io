(() => {
  'use strict';

  if (globalThis.DruMasterRanking) return;

  const DB_NAME = 'drumaster-ranking';
  const DB_VERSION = 2;
  const STORE = 'plays';
  const ENDPOINT_KEY = 'drumasterRankingEndpoint';
  const PLAYER_ID_KEY = 'drumasterPlayerId';
  const PLAYER_NAME_KEY = 'drumasterPlayerName';
  const LINKED_PLAYER_IDS_KEY = 'drumasterRankingLinkedPlayerIds';
  const MERGED_STATE_KEY = 'drumasterRankingMergedState';
  const CURSOR_KEY_PREFIX = 'drumasterRankingCursorV2:';
  const LOCAL_MIGRATION_KEY = 'drumasterRankingLocalHistoryMergedV1';
  const DEFAULT_ENDPOINT = 'https://drumaster-ranking-api.aoka45utau.workers.dev';
  const DEFAULT_RANKING_VERSION = '1';
  const REQUEST_TIMEOUT_MS = 12000;
  const DELTA_PAGE_SIZE = 500;
  const MAX_DELTA_PAGES = 100;

  let dbPromise;
  let syncing = false;
  let syncQueued = false;
  let lastSyncState = null;
  let captureBusy = false;
  let capturedForVisibleResult = false;

  const uuid = () => crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`;

  function endpoint() {
    return (localStorage.getItem(ENDPOINT_KEY) || DEFAULT_ENDPOINT).trim().replace(/\/$/, '');
  }

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

  function linkedPlayerIds() {
    try {
      const value = JSON.parse(localStorage.getItem(LINKED_PLAYER_IDS_KEY) || '[]');
      return Array.isArray(value)
        ? value.filter(v => typeof v === 'string' && /^[A-Za-z0-9._:-]{8,128}$/.test(v))
        : [];
    } catch {
      return [];
    }
  }

  function setLinkedPlayerIds(values) {
    const current = playerId();
    const clean = [...new Set(values)]
      .filter(v => typeof v === 'string' && v !== current && /^[A-Za-z0-9._:-]{8,128}$/.test(v));
    localStorage.setItem(LINKED_PLAYER_IDS_KEY, JSON.stringify(clean));
    return clean;
  }

  function syncPlayerIds() {
    return [...new Set([playerId(), ...linkedPlayerIds()])];
  }

  function cursorKey(id) {
    return `${CURSOR_KEY_PREFIX}${id}`;
  }

  function getCursor(id) {
    return localStorage.getItem(cursorKey(id)) || '';
  }

  function setCursor(id, cursor) {
    if (cursor) localStorage.setItem(cursorKey(id), cursor);
  }

  function resetCursor(id) {
    localStorage.removeItem(cursorKey(id));
  }

  function openDb() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        let store;
        if (!db.objectStoreNames.contains(STORE)) {
          store = db.createObjectStore(STORE, { keyPath: 'playId' });
        } else {
          store = req.transaction.objectStore(STORE);
        }
        if (!store.indexNames.contains('syncStatus')) store.createIndex('syncStatus', 'syncStatus', { unique: false });
        if (!store.indexNames.contains('playedAtClient')) store.createIndex('playedAtClient', 'playedAtClient', { unique: false });
        if (!store.indexNames.contains('songId')) store.createIndex('songId', 'songId', { unique: false });
        if (!store.indexNames.contains('playerId')) store.createIndex('playerId', 'playerId', { unique: false });
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

  async function migrateDetachedLocalHistory() {
    if (localStorage.getItem(LOCAL_MIGRATION_KEY) === '1') return 0;
    try {
      if (typeof indexedDB.databases === 'function') {
        const names = (await indexedDB.databases()).map(x => x?.name).filter(Boolean);
        if (!names.includes('drumaster-local-history')) {
          localStorage.setItem(LOCAL_MIGRATION_KEY, '1');
          return 0;
        }
      }

      const oldDb = await new Promise((resolve, reject) => {
        const req = indexedDB.open('drumaster-local-history');
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      });
      if (!oldDb.objectStoreNames.contains('plays')) {
        oldDb.close();
        localStorage.setItem(LOCAL_MIGRATION_KEY, '1');
        return 0;
      }
      const oldPlays = await new Promise((resolve, reject) => {
        const tx = oldDb.transaction('plays', 'readonly');
        const req = tx.objectStore('plays').getAll();
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => reject(req.error);
      });
      oldDb.close();

      const existing = new Set((await allPlays()).map(p => String(p?.playId || '')).filter(Boolean));
      let migrated = 0;
      for (const source of oldPlays) {
        if (!source || source.autoPlay || source.noScore) continue;
        const noteCount = Number(source.noteCount || 0);
        if (!source.playId || noteCount < 1 || existing.has(String(source.playId))) continue;
        const play = {
          ...source,
          playerId: source.playerId || playerId(),
          displayName: source.displayName || playerName(),
          chartId: source.chartId || 'default',
          rankingVersion: source.rankingVersion || DEFAULT_RANKING_VERSION,
          chartVersion: source.chartVersion || 'local-history-migration',
          gameVersion: source.gameVersion || 'local-history-migration',
          playMode: source.playMode || 'normal',
          autoPlay: false,
          noScore: false,
          syncStatus: source.syncStatus === 'synced' && source.playerId ? 'synced' : 'pending',
          retryCount: Number(source.retryCount || 0),
          lastAttemptAt: source.lastAttemptAt || null,
          lastError: source.lastError || null,
          serverResult: source.serverResult || { migratedFromDetachedLocalHistory: true }
        };
        await putPlay(play);
        existing.add(String(play.playId));
        migrated++;
      }
      localStorage.setItem(LOCAL_MIGRATION_KEY, '1');
      return migrated;
    } catch (error) {
      console.warn('Detached local history migration skipped:', error);
      return 0;
    }
  }

  async function linkToPlayerId(rawTarget) {
    const target = String(rawTarget || '').trim();
    if (!/^[A-Za-z0-9._:-]{8,128}$/.test(target)) throw new Error('同期コードの形式が正しくありません');

    const current = playerId();
    if (target === current) return { changed: false, playerId: current, aliases: linkedPlayerIds(), migrated: 0 };

    const sourceIds = [...new Set([current, ...linkedPlayerIds()])];
    localStorage.setItem(PLAYER_ID_KEY, target);
    const aliases = setLinkedPlayerIds(sourceIds);
    resetCursor(target);
    await rebuildMergedState();
    await syncAll('link');
    return { changed: true, playerId: target, aliases, migrated: 0 };
  }

  async function openSyncPrompt() {
    if (globalThis.DruMasterOfflinePlayback?.isLocked?.()) return;
    const current = playerId();
    const value = prompt(
      `端末同期コード\n\n現在のコード:\n${current}\n\n別の端末と同じスコア履歴を使う場合は、その端末のコードを入力してください。\nこのコードのままOKを押すとクリップボードへコピーします。`,
      current
    );
    if (value === null) return;
    const target = value.trim();
    if (!target) return;
    if (target === current) {
      try {
        await navigator.clipboard?.writeText(current);
        setStatus('端末同期コードをコピーしました');
      } catch {
        setStatus(`端末同期コード: ${current}`);
      }
      return;
    }
    setStatus('端末スコアを統合中…');
    try {
      await linkToPlayerId(target);
      setStatus('端末同期完了');
    } catch (error) {
      setStatus(`端末同期失敗 · ${String(error?.message || error).slice(0, 80)}`);
      alert(String(error?.message || error));
    }
  }

  function statusElement() {
    let el = document.getElementById('rankingSyncState');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'rankingSyncState';
    el.title = 'クリックして端末同期コードを確認・入力';
    Object.assign(el.style, {
      position: 'fixed', right: '18px', bottom: '14px', zIndex: '2147483000',
      fontFamily: 'Arial, Helvetica, sans-serif', fontSize: '12px', fontWeight: '600',
      color: 'rgba(255,255,255,.88)', background: 'rgba(0,0,0,.24)', pointerEvents: 'auto',
      cursor: 'pointer', userSelect: 'none', padding: '5px 8px', borderRadius: '6px',
      letterSpacing: '.02em', textShadow: '0 1px 3px rgba(0,0,0,.7)'
    });
    el.addEventListener('click', () => openSyncPrompt().catch(console.error));
    document.body.appendChild(el);
    return el;
  }

  function setStatus(text) {
    const el = statusElement();
    el.style.display = globalThis.DruMasterOfflinePlayback?.isLocked?.() ? 'none' : '';
    el.textContent = text || '';
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

  function currentSongId() {
    return globalThis.DruMasterSongs?.current?.id
      || document.querySelector('#songSelect')?.value
      || document.body?.dataset.songId
      || document.documentElement.dataset.songId
      || localStorage.getItem('drumasterSongId')
      || localStorage.getItem('drumusterSongId')
      || 'nanairo';
  }

  function numberFrom(selector) {
    const raw = document.querySelector(selector)?.textContent || '';
    const match = raw.replace(/,/g, '').match(/-?\d+/);
    return match ? Number(match[0]) : 0;
  }

  function detectMode() {
    return document.querySelector('#playMode')?.value
      || document.querySelector('#performanceModeSelect')?.value
      || document.querySelector('[name="playMode"]:checked')?.value
      || document.body?.dataset.playMode
      || 'normal';
  }

  function isRankableResult() {
    const result = document.querySelector('#result');
    if (!result || result.classList.contains('hidden')) return false;
    const finalText = document.querySelector('#finalScore')?.textContent?.trim() || '';
    const auto = result.classList.contains('autoplay')
      || document.body?.classList.contains('autoplay')
      || document.querySelector('#autoToggle')?.checked
      || /AUTO/i.test(finalText);
    const noScore = result.classList.contains('no-score') || document.body?.classList.contains('no-score');
    return !auto && !noScore;
  }

  async function rebuildMergedState() {
    const plays = await allPlays();
    const bestByBoard = {};
    for (const play of plays) {
      if (!play || play.autoPlay || play.noScore) continue;
      const key = `${play.songId || 'unknown'}::${play.chartId || 'default'}::${play.rankingVersion || DEFAULT_RANKING_VERSION}`;
      if (!bestByBoard[key] || Number(play.score || 0) > Number(bestByBoard[key].score || 0)) {
        bestByBoard[key] = {
          playId: play.playId, songId: play.songId, chartId: play.chartId || 'default',
          rankingVersion: play.rankingVersion || DEFAULT_RANKING_VERSION,
          score: Number(play.score || 0), perfect: Number(play.perfect || 0), great: Number(play.great || 0),
          good: Number(play.good || 0), miss: Number(play.miss || 0),
          maxCombo: play.maxCombo == null ? null : Number(play.maxCombo), playedAtClient: play.playedAtClient || null
        };
      }
    }
    const merged = {
      playerId: playerId(), linkedPlayerIds: linkedPlayerIds(), displayName: playerName(),
      totalPlays: plays.length, pendingPlays: plays.filter(p => p?.syncStatus === 'pending').length,
      bestByBoard, updatedAt: new Date().toISOString()
    };
    localStorage.setItem(MERGED_STATE_KEY, JSON.stringify(merged));
    dispatchEvent(new CustomEvent('drumaster-ranking-synced', { detail: merged }));
    return merged;
  }

  async function captureResult() {
    if (captureBusy || capturedForVisibleResult || !isRankableResult()) return null;
    captureBusy = true;
    try {
      const score = numberFrom('#finalScore');
      const perfect = numberFrom('#perfectCount');
      const great = numberFrom('#greatCount');
      const good = numberFrom('#goodCount');
      const miss = numberFrom('#missCount');
      const noteCount = perfect + great + good + miss;
      if (noteCount < 1) return null;

      capturedForVisibleResult = true;
      const now = new Date().toISOString();
      const play = {
        playId: uuid(), playerId: playerId(), displayName: playerName(), songId: currentSongId(),
        chartId: document.body?.dataset.chartId || 'default',
        rankingVersion: document.body?.dataset.rankingVersion || DEFAULT_RANKING_VERSION,
        chartVersion: document.body?.dataset.chartVersion || document.documentElement.dataset.chartVersion || 'unknown',
        gameVersion: document.documentElement.dataset.gameVersion || 'shared-ranking-20260907-local-first',
        score, perfect, great, good, miss, noteCount, maxCombo: numberFrom('#maxCombo') || null,
        playMode: detectMode(), autoPlay: false, noScore: false,
        playedAtClient: now, createdAtLocal: now, syncStatus: 'pending', retryCount: 0,
        lastAttemptAt: null, lastError: null, serverResult: null
      };

      await putPlay(play);
      await rebuildMergedState();
      dispatchEvent(new CustomEvent('drumaster-local-play-saved', { detail: play }));
      setStatus('スコアをローカル保存済み · 同期中…');
      syncAll('result').catch(console.error);
      return play;
    } finally {
      captureBusy = false;
    }
  }

  async function uploadPlay(play, base) {
    const response = await fetchWithTimeout(`${base}/v1/plays`, {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(play), cache: 'no-store'
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
    if (result?.receivedAtServer) play.receivedAtServer = result.receivedAtServer;
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
        const result = await uploadPlay(play, base);
        uploaded++;
        if (Number.isFinite(result?.rank)) lastRank = result;
      } catch (error) {
        failed++;
        play.syncStatus = 'pending';
        play.retryCount = Number(play.retryCount || 0) + 1;
        play.lastAttemptAt = new Date().toISOString();
        play.lastError = String(error?.message || error);
        await putPlay(play);
      }
    }
    return { queued: queue.length, uploaded, failed, lastRank };
  }

  async function pullServerDelta(base) {
    const existing = new Map((await allPlays()).map(play => [String(play?.playId || ''), play]).filter(([id]) => id));
    let remoteCount = 0;
    let added = 0;
    let updated = 0;

    for (const id of syncPlayerIds()) {
      let cursor = getCursor(id);
      for (let page = 0; page < MAX_DELTA_PAGES; page++) {
        const response = await fetchWithTimeout(
          `${base}/v1/players/${encodeURIComponent(id)}/plays?cursor=${encodeURIComponent(cursor)}&limit=${DELTA_PAGE_SIZE}`,
          { cache: 'no-store', headers: { accept: 'application/json' } }
        );
        if (response.status === 404) break;
        if (!response.ok) throw new Error(`history HTTP ${response.status}`);
        const payload = await response.json();
        const rows = Array.isArray(payload?.plays) ? payload.plays : [];
        remoteCount += rows.length;

        for (const remote of rows) {
          if (!remote?.playId) continue;
          const key = String(remote.playId);
          const local = existing.get(key);
          if (local) {
            const merged = {
              ...local, ...remote, autoPlay: false, noScore: false, syncStatus: 'synced',
              retryCount: 0, lastAttemptAt: new Date().toISOString(), lastError: null,
              serverResult: { ...(local.serverResult || {}), importedFromServer: true }
            };
            await putPlay(merged);
            existing.set(key, merged);
            updated++;
          } else {
            const imported = {
              ...remote, autoPlay: false, noScore: false,
              createdAtLocal: remote.playedAtClient || remote.receivedAtServer || new Date().toISOString(),
              syncStatus: 'synced', retryCount: 0, lastAttemptAt: new Date().toISOString(), lastError: null,
              serverResult: { importedFromServer: true }
            };
            await putPlay(imported);
            existing.set(key, imported);
            added++;
          }
        }

        if (typeof payload?.nextCursor !== 'string') break;
        if (payload.nextCursor) {
          cursor = payload.nextCursor;
          setCursor(id, cursor);
        }
        if (!payload.hasMore) break;
      }
    }
    return { remoteCount, added, updated, playerIds: syncPlayerIds() };
  }

  async function syncAll(reason = 'manual') {
    if (globalThis.DruMasterOfflinePlayback?.isLocked?.()) return lastSyncState;
    if (syncing) {
      syncQueued = true;
      return lastSyncState;
    }
    const base = endpoint();
    if (!base) return lastSyncState;
    syncing = true;
    syncQueued = false;
    setStatus('ランキング同期中…');
    const startedAt = new Date().toISOString();
    try {
      if (navigator.onLine === false) {
        const merged = await rebuildMergedState();
        lastSyncState = { ok: false, offline: true, reason, startedAt, completedAt: new Date().toISOString(), merged };
        setStatus(`ローカル保存済み · 未同期 ${merged.pendingPlays}件`);
        return lastSyncState;
      }

      const pushed = await pushPending(base);
      let pulled = { remoteCount: 0, added: 0, updated: 0, playerIds: syncPlayerIds() };
      let pullError = null;
      try {
        pulled = await pullServerDelta(base);
      } catch (error) {
        pullError = error;
      }
      const merged = await rebuildMergedState();
      const ok = pushed.failed === 0 && !pullError;
      lastSyncState = {
        ok, reason, startedAt, completedAt: new Date().toISOString(), pushed, pulled, merged,
        ...(pullError ? { error: String(pullError?.message || pullError) } : {})
      };

      if (pushed.failed) setStatus(`ローカル保存済み · 未送信 ${pushed.failed}件`);
      else if (pullError) setStatus(`送信済み · 差分取得失敗 ${String(pullError?.message || pullError).slice(0, 50)}`);
      else if (pushed.lastRank) setStatus(`WORLD RANK #${pushed.lastRank.rank}${pushed.lastRank.totalPlayers ? ` / ${pushed.lastRank.totalPlayers}` : ''} · ${merged.totalPlays}件`);
      else setStatus(`ランキング同期済み · ${merged.totalPlays}件${pulled.added ? `（+${pulled.added}）` : ''}`);
      return lastSyncState;
    } catch (error) {
      const merged = await rebuildMergedState().catch(() => null);
      lastSyncState = { ok: false, reason, startedAt, completedAt: new Date().toISOString(), error: String(error?.message || error), merged };
      setStatus(`ローカル保持中 · 同期失敗 ${String(error?.message || error).slice(0, 50)}`);
      return lastSyncState;
    } finally {
      syncing = false;
      if (syncQueued && !globalThis.DruMasterOfflinePlayback?.isLocked?.()) {
        syncQueued = false;
        queueMicrotask(() => syncAll('queued').catch(console.error));
      }
    }
  }

  function scheduleCapture() {
    requestAnimationFrame(() => setTimeout(() => captureResult().catch(console.error), 0));
  }

  function watchResult() {
    const result = document.querySelector('#result');
    if (!result) return;
    const observer = new MutationObserver(() => {
      if (result.classList.contains('hidden')) {
        capturedForVisibleResult = false;
        return;
      }
      scheduleCapture();
    });
    observer.observe(result, { attributes: true, attributeFilter: ['class'] });
    addEventListener('drumaster-result-finalized', scheduleCapture);
    if (!result.classList.contains('hidden')) scheduleCapture();
  }

  async function init() {
    statusElement();
    watchResult();
    const migrated = await migrateDetachedLocalHistory();
    await rebuildMergedState().catch(console.warn);
    if (migrated) setStatus(`ローカル履歴 ${migrated}件を統合 · 同期中…`);
    syncAll('startup').catch(console.error);
  }

  globalThis.DruMasterRanking = {
    syncPending: () => syncAll('manual'),
    syncAll,
    forceHistorySync() {
      for (const id of syncPlayerIds()) resetCursor(id);
      return syncAll('full-resync');
    },
    getLocalPlays: allPlays,
    getSyncState: () => lastSyncState,
    getMergedState() {
      try { return JSON.parse(localStorage.getItem(MERGED_STATE_KEY) || 'null'); }
      catch { return null; }
    },
    getPlayerId: playerId,
    getLinkedPlayerIds: linkedPlayerIds,
    getSyncCode: playerId,
    linkSyncCode: linkToPlayerId,
    showSyncCodeDialog: openSyncPrompt,
    getPlayerName: playerName,
    setPlayerName(value) {
      localStorage.setItem(PLAYER_NAME_KEY, String(value || '').trim() || playerName());
      rebuildMergedState().catch(console.error);
    },
    getEndpoint: endpoint,
    setEndpoint(value) {
      localStorage.setItem(ENDPOINT_KEY, String(value || '').trim());
      syncAll('endpoint-change').catch(console.error);
    },
    captureResult
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
