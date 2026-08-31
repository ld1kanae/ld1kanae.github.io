(() => {
  const HOT_ZONE_PX = 50;
  const BUTTON_SIZE_PX = 50;

  const button = document.createElement('button');
  button.type = 'button';
  button.setAttribute('aria-label', 'Close DruMaster');
  button.textContent = '×';

  Object.assign(button.style, {
    position: 'fixed',
    top: '0',
    right: '0',
    width: `${BUTTON_SIZE_PX}px`,
    height: `${BUTTON_SIZE_PX}px`,
    padding: '0',
    margin: '0',
    border: '0',
    outline: '0',
    background: 'transparent',
    color: '#fff',
    fontFamily: 'Arial, Helvetica, sans-serif',
    fontSize: '40px',
    fontWeight: '300',
    lineHeight: `${BUTTON_SIZE_PX - 2}px`,
    textAlign: 'center',
    cursor: 'pointer',
    zIndex: '2147483647',
    opacity: '0',
    pointerEvents: 'none',
    transition: 'opacity 100ms linear',
    userSelect: 'none',
    WebkitUserSelect: 'none'
  });

  const setVisible = (visible) => {
    button.style.opacity = visible ? '1' : '0';
    button.style.pointerEvents = visible ? 'auto' : 'none';
  };

  document.addEventListener('mousemove', (event) => {
    setVisible(event.clientY >= 0 && event.clientY <= HOT_ZONE_PX);
  }, { passive: true });

  document.addEventListener('mouseleave', () => setVisible(false));

  button.addEventListener('click', async (event) => {
    event.preventDefault();
    event.stopPropagation();
    try {
      await window.__TAURI__?.core?.invoke('close_app');
    } catch (error) {
      console.error('Failed to close DruMaster window:', error);
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
    document.body.appendChild(button);
  }, { once: true });
})();
