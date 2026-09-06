(() => {
  'use strict';

  const invoke = window.__TAURI__?.core?.invoke;
  if (!invoke) return;

  const ATTEMPTED_BUILD_KEY = 'drumasterAutoUpdateAttemptedBuild';
  const ATTEMPTED_AT_KEY = 'drumasterAutoUpdateAttemptedAt';
  const RETRY_AFTER_MS = 6 * 60 * 60 * 1000;

  let overlay;
  let titleNode;
  let messageNode;
  let actionsNode;

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
      width: 'min(560px, calc(100vw - 48px))', padding: '32px 34px',
      border: '1px solid rgba(255,255,255,.18)', borderRadius: '18px',
      background: 'rgba(13,24,36,.98)', boxShadow: '0 24px 80px rgba(0,0,0,.5)',
      textAlign: 'center'
    });

    titleNode = document.createElement('div');
    Object.assign(titleNode.style, { fontSize: '22px', fontWeight: '700', marginBottom: '14px' });

    messageNode = document.createElement('div');
    Object.assign(messageNode.style, {
      fontSize: '14px', lineHeight: '1.8', opacity: '.86', whiteSpace: 'pre-line'
    });

    actionsNode = document.createElement('div');
    Object.assign(actionsNode.style, {
      display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '24px'
    });

    panel.append(titleNode, messageNode, actionsNode);
    overlay.appendChild(panel);
    document.body.appendChild(overlay);
    return overlay;
  }

  function makeButton(text, primary = false) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = text;
    Object.assign(button.style, {
      minWidth: '128px', minHeight: '42px', padding: '10px 18px',
      borderRadius: '10px', cursor: 'pointer', fontSize: '14px', fontWeight: '700',
      border: primary ? '1px solid rgba(184,218,255,.7)' : '1px solid rgba(255,255,255,.22)',
      color: '#fff',
      background: primary ? 'rgba(86,145,210,.5)' : 'rgba(255,255,255,.08)'
    });
    return button;
  }

  function hide() {
    if (overlay) overlay.style.display = 'none';
  }

  function showProgress(text) {
    ensureOverlay();
    titleNode.textContent = 'DruMaster を更新しています';
    messageNode.textContent = text;
    actionsNode.replaceChildren();
    overlay.style.display = 'flex';
  }

  function askForUpdate(info) {
    ensureOverlay();
    titleNode.textContent = '新しいバージョンがあります';
    messageNode.textContent = `現在: Build #${info.currentBuild}\n最新版: Build #${info.latestBuild}\n\n更新しますか？`;
    actionsNode.replaceChildren();

    const later = makeButton('後で');
    const update = makeButton('更新する', true);
    actionsNode.append(later, update);
    overlay.style.display = 'flex';
    update.focus();

    return new Promise(resolve => {
      const finish = value => {
        later.onclick = null;
        update.onclick = null;
        resolve(value);
      };
      later.onclick = () => finish(false);
      update.onclick = () => finish(true);
    });
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

      if (recentlyAttempted(info.latestBuild)) {
        hide();
        return;
      }

      const accepted = await askForUpdate(info);
      if (!accepted) {
        hide();
        return;
      }

      rememberAttempt(info.latestBuild);
      showProgress(`最新版（Build #${info.latestBuild}）をダウンロードしています。\n完了後、自動で再起動します。`);
      await invoke('install_update', {
        url: info.downloadUrl,
        assetName: info.assetName
      });
    } catch (error) {
      console.error('DruMaster auto update failed:', error);
      hide();
      alert(`更新に失敗しました。アプリはこのまま使用できます。\n\n${String(error?.message || error)}`);
    }
  }

  const start = () => setTimeout(check, 1800);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
