(() => {
  'use strict';

  function currentSongId() {
    return globalThis.DruMasterSongs?.current?.id
      || document.querySelector('#songSelect')?.value
      || document.body?.dataset.songId
      || document.documentElement.dataset.songId
      || localStorage.getItem('drumasterSongId')
      || localStorage.getItem('drumusterSongId')
      || 'nanairo';
  }

  function currentChartId() {
    return document.body?.dataset.chartId || 'default';
  }

  function currentRankingVersion() {
    return document.body?.dataset.rankingVersion || '1';
  }

  function applyMergedBest(merged) {
    const entries = Object.values(merged?.bestByBoard || {});
    if (!entries.length) return;

    const songId = currentSongId();
    const chartId = currentChartId();
    const rankingVersion = currentRankingVersion();

    let matches = entries.filter(entry =>
      entry?.songId === songId
      && (entry.chartId || 'default') === chartId
      && (entry.rankingVersion || '1') === rankingVersion
    );

    if (!matches.length) {
      matches = entries.filter(entry =>
        entry?.songId === songId
        && (entry.rankingVersion || '1') === rankingVersion
      );
    }

    const historyBest = matches.reduce((best, entry) => Math.max(best, Number(entry?.score || 0)), 0);
    if (!historyBest) return;

    const compatibilityBest = Number(localStorage.getItem('drumusterBest') || 0);
    const best = Math.max(compatibilityBest, historyBest);
    localStorage.setItem('drumusterBest', String(best));

    const bestScore = document.querySelector('#bestScore');
    if (bestScore) bestScore.textContent = String(best).padStart(6, '0');
  }

  addEventListener('drumaster-ranking-synced', event => applyMergedBest(event.detail));

  function applyCurrentState() {
    try {
      applyMergedBest(globalThis.DruMasterRanking?.getMergedState?.());
    } catch (error) {
      console.warn('Unable to project local ranking best into game UI:', error);
    }
  }

  function loadOnce(src, key) {
    if (document.querySelector(`script[data-${key}]`)) return;
    const script = document.createElement('script');
    script.src = src;
    script.setAttribute(`data-${key}`, '1');
    script.onerror = error => console.error(`DruMaster ${key} loader failed`, error);
    document.head.appendChild(script);
  }

  function blockDetachedLocalHistoryLoader() {
    if (document.querySelector('script[data-dm-local-play-history]')) return;
    const marker = document.createElement('script');
    marker.type = 'application/json';
    marker.setAttribute('data-dm-local-play-history', 'disabled-unified-store');
    document.head.appendChild(marker);
  }

  function loadRankingExtensions() {
    blockDetachedLocalHistoryLoader();
    loadOnce('js/legacy-score-migration.js?v=20260906-legacy3', 'dm-legacy-best-migration');
    loadOnce('js/ranking-result-cloud.js?v=20260907-unified1', 'dm-ranking-result-cloud');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      applyCurrentState();
      loadRankingExtensions();
    }, { once: true });
  } else {
    applyCurrentState();
    loadRankingExtensions();
  }
})();
