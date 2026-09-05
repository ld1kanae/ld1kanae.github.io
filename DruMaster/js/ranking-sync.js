(() => {
  'use strict';

  if (globalThis.DruMasterRanking) return;

  const DB_NAME = 'drumaster-ranking';
  const DB_VERSION = 1;
  const STORE = 'plays';
  const ENDPOINT_KEY = 'drumasterRankingEndpoint';
  const PLAYER_ID_KEY = 'drumasterPlayerId';
  const PLAYER_NAME_KEY = 'drumasterPlayerName';
  const LINKED_PLAYER_IDS_KEY = 'drumasterRankingLinkedPlayerIds';
  const MERGED_STATE_KEY = 'drumasterRankingMergedState';
  const DEFAULT_ENDPOINT = 'https://drumaster-ranking-api.aoka45utau.workers.dev';
  const DEFAULT_RANKING_VERSION = '1';
  const RETRY_MS = 30000;
  const REQUEST_TIMEOUT_MS = 12000;

  let dbPromise;
  let syncing = false;
  let lastSyncState = null;
  let lastCapturedKey = '';

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

  async function migrateLocalHistoryToCanonical(targetId, sourceIds) {
    const sourceSet = new Set(sourceIds.filter(v => v && v !== targetId));
    if (!sourceSet.size) return 0;
    const plays = await allPlays();
    let migrated = 0;

    for (const original of plays) {
      if (!original || !sourceSet.has(original.playerId)) continue;
      if (original.linkedToPlayerId === targetId) continue;

      original.linkedToPlayerId = targetId;
      await putPlay(original);

      const clone = {
        ...original,
        playId: uuid(),
        playerId: targetId,
        displayName: playerName(),
        syncStatus: 'pending',
        retryCount: 0,
        lastAttemptAt: null,
        lastError: null,
        serverResult: {
          migratedFromPlayId: original.playId,
          migratedFromPlayerId: original.playerId
        }
      };
      delete clone.linkedToPlayerId;
      await putPlay(clone);
      migrated++;
    }
    return migrated;
  }

  async function linkToPlayerId(rawTarget) {
    const target = String(rawTarget || '').trim();
    if (!/^[A-Za-z0-9._:-]{8,128}$/.test(target)) {
      throw new Error('同期コードの形式が正しくありません');
    }

    const current = playerId();
    if (target === current) {
      return { changed: false, playerId: current, aliases: linkedPlayerIds(), migrated: 0 };
    }

    const previousAliases = linkedPlayerIds();
    const sourceIds = [...new Set([current, ...previousAliases])];

    localStorage.setItem(PLAYER_ID_KEY, target);
    const aliases = setLinkedPlayerIds(sourceIds);
    const migrated = await migrateLocalHistoryToCanonical(target, sourceIds);

    await rebuildMergedState();
    await syncAll();

    return { changed: true, playerId: target, aliases, migrated };
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
      const result = await linkToPlayerId(target);
      setStatus(`端末同期完了 · ${result.migrated}件を統合`);
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
      cursor: 'pointer', userSelect: 'none',
      padding: '5px 8px', borderRadius: '6px', letterSpacing: '.02em',
      textShadow: '0 1px 3px rgba(0,0,0,.7)'
    });
    el.addEventListener('click', () => openSyncPrompt().catch(console.error));
    document.body.appendChild(el);
    return el;
  }

  function setStatus(text) {
    const el = statusElement();
    const locked = globalThis.DruMasterOfflinePlayback?.isLocked?.();
    el.style.display = locked ? 'none' : '';
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
    return document.documentElement.dataset.songId
      || document.body?.dataset.songId
      || localStorage.getItem('drumasterSongId')
      || localStorage.getItem('drumusterSongId')
      || document.querySelector('#songSelect')?.value
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
      linkedPlayerIds: linkedPlayerIds(),
      displayName: playerName(),
      totalPlays: plays.length,
      pendingPlays: plays.filter(p => p?.syncStatus === 'pending').length,
      bestByBoard,
      updatedAt: new Date().toISOString()
    };
    localStorage.setItem(MERGED_STATE_KEY, JSON.stringify(merged));
    dispatchEvent(new CustomEvent('drumaster-ranking-synced', { detail: merged }));
    return merged;
  }

  async function captureResult() {
    if (!isRankableResult()) return;

    const score = numberFrom('#finalScore');
    const perfect = numberFrom('#perfectCount');
    const great = numberFrom('#greatCount');
    const good = numberFrom('#goodCount');
    const miss = numberFrom('#missCount');
    const noteCount = perfect + great + good + miss;
    if (noteCount < 1) return;

    const key = `${currentSongId()}:${score}:${perfect}:${great}:${good}:${miss}`;
    if (key === lastCapturedKey) return;
    lastCapturedKey = key;

    const now = new Date().toISOString();
    const play = {
      playId: uuid(),
      playerId: playerId(),
      displayName: playerName(),
      songId: currentSongId(),
      chartId: document.body?.dataset.chartId || 'default',
      rankingVersion: document.body?.dataset.rankingVersion || DEFAULT_RANKING_VERSION,
      chartVersion: document.body?.dataset.chartVersion || document.documentElement.dataset.chartVersion || 'unknown',
      gameVersion: document.documentElement.dataset.gameVersion || 'shared-ranking-20260905',
      score,
      perfect,
      great,
      good,
      miss,
      noteCount,
      maxCombo: numberFrom('#maxCombo') || null,
      playMode: detectMode(),
      autoPlay: false,
      noScore: false,
      playedAtClient: now,
      createdAtLocal: now,
      syncStatus: 'pending',
      retryCount: 0,
      lastAttemptAt: null,
      lastError: null,
      serverResult: null
    };

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
      }
    }
    return { queued: queue.length, uploaded, failed, lastRank };
  }

  async function pullServerHistory(base) {
    let remoteCount = 0;
    let added = 0;

    for (const id of syncPlayerIds()) {
      const response = await fetchWithTimeout(`${base}/v1/players/${encodeURIComponent(id)}/plays?limit=5000`, {
        cache: 'no-store',
        headers: { accept: 'application/json' }
      });
      if (response.status === 404) continue;
      if (!response.ok) throw new Error(`history HTTP ${response.status}`);

      const payload = await response.json();
      const plays = Array.isArray(payload?.plays) ? payload.plays : [];
      remoteCount += plays.length;

      for (const remote of plays) {
        if (!remote?.playId || await getPlay(remote.playId)) continue;
        await putPlay({
          ...remote,
          autoPlay: false,
          noScore: false,
          createdAtLocal: remote.playedAtClient || remote.receivedAtServer || new Date().toISOString(),
          syncStatus: 'synced',
          retryCount: 0,
          lastAttemptAt: new Date().toISOString(),
          lastError: null,
          serverResult: { importedFromServer: true }
        });
        added++;
      }
    }

    return { remoteCount, added, playerIds: syncPlayerIds() };
  }

  async function syncAll() {
    if (syncing) return lastSyncState;
    const base = endpoint();
    if (!base) return lastSyncState;
    syncing = true;
    setStatus('ランキング同期中…');
    const startedAt = new Date().toISOString();
    try {
      const pushed = await pushPending(base);
      const pulled = await pullServerHistory(base);
      const merged = await rebuildMergedState();
      lastSyncState = { ok: pushed.failed === 0, startedAt, completedAt: new Date().toISOString(), pushed, pulled, merged };
      if (pushed.failed) setStatus(`同期一部失敗 · ${pushed.failed}件を自動再送`);
      else if (pushed.lastRank) setStatus(`WORLD RANK #${pushed.lastRank.rank}${pushed.lastRank.totalPlayers ? ` / ${pushed.lastRank.totalPlayers}` : ''}`);
      else setStatus(`ランキング同期済み · ${merged.totalPlays}件${pulled.added ? `（クラウドから${pulled.added}件追加）` : ''}`);
      return lastSyncState;
    } catch (error) {
      lastSyncState = { ok: false, startedAt, completedAt: new Date().toISOString(), error: String(error?.message || error) };
      if (!globalThis.DruMasterOfflinePlayback?.isLocked?.()) setStatus(`ランキング同期失敗 · ${String(error?.message || error).slice(0, 80)}`);
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
    watchResult();
    await rebuildMergedState().catch(console.warn);
    syncAll().catch(console.error);
    addEventListener('online', () => syncAll().catch(console.error));
    addEventListener('focus', () => syncAll().catch(console.error));
    setInterval(() => syncAll().catch(console.error), RETRY_MS);
  }

  globalThis.DruMasterRanking = {
    syncPending: syncAll,
    syncAll,
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
      syncAll().catch(console.error);
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
