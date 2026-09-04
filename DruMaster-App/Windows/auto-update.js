(() => {
  'use strict';

  const invoke = window.__TAURI__?.core?.invoke;
  if (!invoke) return;

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

  async function check() {
    try {
      const info = await invoke('check_for_update');
      if (!info?.updateAvailable) {
        hide();
        return;
      }
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
