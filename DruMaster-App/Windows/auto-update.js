(() => {
  'use strict';

  const invoke = window.__TAURI__?.core?.invoke;
  if (!invoke) return;

  const ATTEMPTED_BUILD_KEY = 'drumasterAutoUpdateAttemptedBuild';
  const ATTEMPTED_AT_KEY = 'drumasterAutoUpdateAttemptedAt';
  const RETRY_AFTER_MS = 6 * 60 * 60 * 1000;

  let overlay;
  let message;

  function ensureOverlay() {
    if (overlay) return overlay;
    overlay = document.createElement('div');
    overlay.id = 'drumasterAutoUpdateOverlay';
    Object.assign(overlay.style, {
      position: 'fixed', inset: '0', zIndex: '2147483600',
      display: 'none', alignItems: 'center', justifyContent: 'center',
      background: 'rgba(3, 8, 14, .82)', backdropFilter: 'blur(10px)',
      WebkitBackdropFilter: 'blur(10px)', color: '#fff',
      fontFamily: 'Arial, Helvetica, sans-serif'
    });
    const panel = document.createElement('div');
    Object.assign(panel.style, {
      width: 'min(560px, calc(100vw - 48px))', padding: '34px 36px',
      border: '1px solid rgba(255,255,255,.18)', borderRadius: '18px',
      background: 'rgba(13,24,36,.96)', boxShadow: '0 24px 80px rgba(0,0,0,.45)',
      textAlign: 'center'
    });
    const title = document.createElement('div');
    title.textContent = 'DruMaster を更新しています';
    Object.assign(title.style, { fontSize: '24px', fontWeight: '700', marginBottom: '14px' });
    message = document.createElement('div');
    message.textContent = '最新版を確認しています…';
    Object.assign(message.style, { fontSize: '14px', lineHeight: '1.7', opacity: '.8' });
    panel.append(title, message);
    overlay.appendChild(panel);
    document.body.appendChild(overlay);
    return overlay;
  }

  function show(text) {
    ensureOverlay();
    message.textContent = text;
    overlay.style.display = 'flex';
  }

  function hide() {
    if (overlay) overlay.style.display = 'none';
  }

  function recentlyAttempted(build) {
    const attemptedBuild = Number(localStorage.getItem(ATTEMPTED_BUILD_KEY) || 0);
    const attemptedAt = Number(localStorage.getItem(ATTEMPTED_AT_KEY) || 0);
    return attemptedBuild === Number(build) && Date.now() - attemptedAt < RETRY_AFTER_MS;
  }

  function rememberAttempt(build) {
    localStorage.setItem(ATTEMPTED_BUILD_KEY, String(build));
    localStorage.setItem(ATTEMPTED_AT_KEY, String(Date.now()));
  }

  function clearAttemptIfCurrent(currentBuild) {
    const attemptedBuild = Number(localStorage.getItem(ATTEMPTED_BUILD_KEY) || 0);
    if (attemptedBuild > 0 && Number(currentBuild) >= attemptedBuild) {
      localStorage.removeItem(ATTEMPTED_BUILD_KEY);
      localStorage.removeItem(ATTEMPTED_AT_KEY);
    }
  }

  async function check() {
    try {
      const info = await invoke('check_for_update');
      clearAttemptIfCurrent(info?.currentBuild);
      if (!info?.updateAvailable) {
        hide();
        return;
      }

      /* If an installer failed or was cancelled, never trap the user in an
         update -> exit -> relaunch -> update loop. Leave the app playable and
         retry the same build only after a cooldown. A newer build is still
         allowed immediately. */
      if (recentlyAttempted(info.latestBuild)) {
        hide();
        return;
      }

      rememberAttempt(info.latestBuild);
      show(`最新版（Build #${info.latestBuild}）をダウンロードしています。完了後、自動で再起動します。`);
      await invoke('install_update', {
        url: info.downloadUrl,
        assetName: info.assetName
      });
    } catch (error) {
      console.error('DruMaster auto update failed:', error);
      hide();
    }
  }

  const start = () => setTimeout(check, 1800);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
