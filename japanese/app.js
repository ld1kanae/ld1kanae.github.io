(() => {
  'use strict';

  const STORAGE_KEY = 'japanese-shower-state-v1';
  const GITHUB_TOKEN_KEY = 'japanese-shower-github-token-v1';
  const GITHUB_REPOSITORY = 'ld1kanae/ld1kanae.github.io';
  const GITHUB_SAVE_PATH = 'japanese/save_data.json';
  const GITHUB_API_URL = `https://api.github.com/repos/${GITHUB_REPOSITORY}/contents/${GITHUB_SAVE_PATH}`;
  const STATUS_LABELS = { known: '知ってる', unknown: '知らない', uninterested: '興味ない' };
  const FILTER_LABELS = { favorite: 'お気に入り', known: '知ってる', unknown: '知らない', uninterested: '興味ない' };
  const defaults = {
    schemaVersion: 1,
    settings: { showMeaning: true, font: 'gothic', theme: 'light' },
    items: {},
    session: null
  };

  let state = loadState();
  let vocabulary = [];
  let vocabularyById = new Map();
  let currentReviewFilter = null;
  let toastTimer = null;
  let swipeLocked = false;

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (!saved || saved.schemaVersion !== 1) return structuredClone(defaults);
      return {
        ...structuredClone(defaults),
        ...saved,
        settings: { ...defaults.settings, ...(saved.settings || {}) },
        items: saved.items || {}
      };
    } catch {
      return structuredClone(defaults);
    }
  }

  function saveState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function itemState(id) {
    if (!state.items[id]) state.items[id] = { status: null, favorite: false, updatedAt: null };
    return state.items[id];
  }

  async function loadVocabulary() {
    const all = [];
    const ids = new Set();
    for (let number = 1; number <= 999; number += 1) {
      const filename = `data/vocabulary_${String(number).padStart(3, '0')}.txt`;
      const response = await fetch(filename, { cache: 'no-cache' });
      if (response.status === 404) break;
      if (!response.ok) throw new Error(`${filename} を読み込めませんでした。`);
      let entries;
      try { entries = JSON.parse(await response.text()); }
      catch { throw new Error(`${filename} の形式が正しくありません。`); }
      if (!Array.isArray(entries)) throw new Error(`${filename} は配列形式で記載してください。`);
      entries.forEach((entry, index) => {
        for (const key of ['id', 'phrase', 'reading', 'meaning', 'example']) {
          if (!entry[key] || typeof entry[key] !== 'string') throw new Error(`${filename} ${index + 1}件目の ${key} が不足しています。`);
        }
        if (ids.has(entry.id)) throw new Error(`語彙ID ${entry.id} が重複しています。`);
        ids.add(entry.id);
        all.push({
          category: '慣用句',
          ...entry,
          genres: Array.isArray(entry.genres) ? entry.genres.filter(Boolean) : [entry.category || 'その他'],
          similar: Array.isArray(entry.similar) ? entry.similar.filter(Boolean) : []
        });
      });
    }
    if (!all.length) throw new Error('語彙ファイルが見つかりませんでした。');
    return all;
  }

  function showView(name) {
    $$('.view').forEach((view) => view.classList.toggle('is-active', view.id === `${name}-view`));
    document.body.dataset.view = name;
    window.scrollTo({ top: 0, behavior: 'instant' });
  }

  function applyAppearance() {
    document.documentElement.dataset.theme = state.settings.theme;
    document.documentElement.dataset.font = state.settings.font;
    $('meta[name="theme-color"]').content = state.settings.theme === 'dark' ? '#0d1925' : '#245d9e';
  }

  function counts() {
    const result = { favorite: 0, known: 0, unknown: 0, uninterested: 0, unclassified: 0 };
    vocabulary.forEach((word) => {
      const saved = state.items[word.id];
      if (saved?.favorite) result.favorite += 1;
      if (saved?.status) result[saved.status] += 1;
      else result.unclassified += 1;
    });
    return result;
  }

  function renderHome() {
    if (state.session && (!Array.isArray(state.session.order) || state.session.index >= state.session.order.length)) {
      state.session = null;
      saveState();
    }
    const totals = counts();
    Object.entries(totals).forEach(([key, value]) => $$(`[data-count="${key}"]`).forEach((node) => { node.textContent = value; }));
    $('#total-count').textContent = vocabulary.length;
    const validSession = Boolean(
      state.session &&
      Array.isArray(state.session.order) &&
      Number.isInteger(state.session.index) &&
      state.session.index >= 0 &&
      state.session.index < state.session.order.length &&
      vocabularyById.has(state.session.order[state.session.index])
    );
    if (state.session && !validSession) {
      state.session = null;
      saveState();
    }
    $('#resume-panel').hidden = !validSession;
    $('#random-subtitle').textContent = validSession ? '途中データを終えて、新しく始める' : '全体から重複なしで出題';
    if (validSession) {
      $('#resume-progress').textContent = `${state.session.index + 1} / ${state.session.order.length}　${state.session.label}`;
    }
    showView('home');
  }

  function shuffled(items) {
    const copy = [...items];
    for (let i = copy.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [copy[i], copy[j]] = [copy[j], copy[i]];
    }
    return copy;
  }

  function wordsForPool(pool) {
    if (pool === 'all') return vocabulary.filter((word) => itemState(word.id).status !== 'uninterested');
    if (pool === 'favorite') return vocabulary.filter((word) => itemState(word.id).favorite);
    if (pool.startsWith('genre:')) {
      const genre = pool.slice(6);
      return vocabulary.filter((word) => word.genres.includes(genre));
    }
    return vocabulary.filter((word) => itemState(word.id).status === pool);
  }

  function poolLabel(pool) {
    if (pool.startsWith('genre:')) return `${pool.slice(6)}から出題`;
    return pool === 'all' ? 'ランダム出題' : `${FILTER_LABELS[pool]}から出題`;
  }

  function startSession(pool = 'all', force = false) {
    const hasActiveSession = state.session && Array.isArray(state.session.order) && state.session.index < state.session.order.length;
    if (!force && hasActiveSession) {
      const proceed = confirm('途中の出題を終了し、新しい順番で始めますか？');
      if (!proceed) return;
    }
    const words = wordsForPool(pool);
    if (!words.length) {
      showToast('出題できることばがありません');
      return;
    }
    state.session = {
      pool,
      label: poolLabel(pool),
      order: shuffled(words.map((word) => word.id)),
      index: 0,
      revealed: {},
      startedAt: new Date().toISOString()
    };
    saveState();
    renderQuiz();
  }

  function currentWord() {
    if (!state.session || !Array.isArray(state.session.order) || !Number.isInteger(state.session.index)) return null;
    while (state.session.index < state.session.order.length && !vocabularyById.has(state.session.order[state.session.index])) {
      state.session.index += 1;
    }
    return vocabularyById.get(state.session.order[state.session.index]) || null;
  }

  function renderQuiz() {
    const word = currentWord();
    if (!word) {
      state.session = null;
      saveState();
      startSession('all', true);
      return;
    }
    const saved = itemState(word.id);
    $('#quiz-mode-label').textContent = state.session.label;
    $('#quiz-progress').textContent = `${state.session.index + 1} / ${state.session.order.length}`;
    $('#word-category').textContent = word.category || '慣用句';
    $('#word-phrase').textContent = word.phrase;
    $('#word-reading').textContent = word.reading;
    $('#word-meaning').textContent = word.meaning;
    $('#word-example').textContent = word.example;
    const similarBox = $('#word-similar-box');
    const similarList = $('#word-similar');
    similarBox.hidden = word.similar.length === 0;
    similarList.replaceChildren(...word.similar.map((phrase) => {
      const span = document.createElement('span');
      span.textContent = phrase;
      return span;
    }));
    updateFavoriteButton($('#favorite-button'), saved.favorite);
    $$('.classification button').forEach((button) => {
      const active = saved.status === button.dataset.status;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    const revealed = state.settings.showMeaning || Boolean(state.session.revealed[word.id]);
    $('#word-explanation').hidden = !revealed;
    $('#reveal-button').hidden = revealed;
    $('#previous-button').disabled = state.session.index === 0;
    $('#next-button').textContent = state.session.index === state.session.order.length - 1 ? '完了 →' : '次へ →';
    saveState();
    showView('quiz');
  }

  function moveSession(amount) {
    if (!state.session) return;
    const nextIndex = state.session.index + amount;
    if (nextIndex < 0) return;
    if (nextIndex >= state.session.order.length) {
      state.session.index = state.session.order.length;
      saveState();
      renderComplete();
      return;
    }
    state.session.index = nextIndex;
    saveState();
    renderQuiz();
  }

  function renderComplete() {
    if (!state.session) return renderHome();
    $('#complete-message').textContent = `${state.session.order.length}語を眺めました。覚えていなくても、それで大丈夫です。`;
    showView('complete');
  }

  function finishSession() {
    state.session = null;
    saveState();
    renderHome();
  }

  function updateFavoriteButton(button, active) {
    button.textContent = active ? '★' : '☆';
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', String(active));
    button.setAttribute('aria-label', active ? 'お気に入りから外す' : 'お気に入りに追加');
  }

  function setCurrentStatus(status) {
    const word = currentWord();
    if (!word) return;
    const saved = itemState(word.id);
    saved.status = saved.status === status ? null : status;
    saved.updatedAt = new Date().toISOString();
    saveState();
    renderQuiz();
  }

  function classifyCurrentAndMove(status) {
    const word = currentWord();
    if (!word || !state.session) return;
    const saved = itemState(word.id);
    saved.status = status;
    saved.updatedAt = new Date().toISOString();
    moveSession(1);
  }

  function bindQuizSwipe() {
    const card = $('.word-card');
    let gesture = null;

    const resetCard = () => {
      card.style.removeProperty('transform');
      card.style.removeProperty('transition');
      delete card.dataset.swipeDirection;
    };

    card.addEventListener('pointerdown', (event) => {
      if (event.pointerType !== 'touch' || swipeLocked) return;
      if (!$('#quiz-view').classList.contains('is-active')) return;
      if (!matchMedia('(max-width: 768px)').matches) return;
      if (event.target.closest('button')) return;
      gesture = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        dx: 0,
        dy: 0
      };
      card.setPointerCapture?.(event.pointerId);
    });

    card.addEventListener('pointermove', (event) => {
      if (!gesture || gesture.pointerId !== event.pointerId) return;
      gesture.dx = event.clientX - gesture.startX;
      gesture.dy = event.clientY - gesture.startY;
      if (Math.abs(gesture.dx) < 10 || Math.abs(gesture.dx) <= Math.abs(gesture.dy) * 1.15) return;
      event.preventDefault();
      const limitedX = Math.max(-120, Math.min(120, gesture.dx));
      card.style.transition = 'none';
      card.style.transform = `translateX(${limitedX}px) rotate(${limitedX / 45}deg)`;
      card.dataset.swipeDirection = gesture.dx < 0 ? 'known' : 'unknown';
    });

    const finishSwipe = (event) => {
      if (!gesture || gesture.pointerId !== event.pointerId) return;
      const { dx, dy } = gesture;
      gesture = null;
      const threshold = Math.max(64, card.clientWidth * 0.18);
      const isHorizontal = Math.abs(dx) >= threshold && Math.abs(dx) > Math.abs(dy) * 1.25;
      if (!isHorizontal) {
        card.style.transition = 'transform .16s ease';
        card.style.transform = 'translateX(0) rotate(0)';
        delete card.dataset.swipeDirection;
        setTimeout(resetCard, 170);
        return;
      }

      swipeLocked = true;
      const status = dx < 0 ? 'known' : 'unknown';
      card.style.transition = 'transform .12s ease, opacity .12s ease';
      card.style.transform = `translateX(${dx < 0 ? '-110%' : '110%'}) rotate(${dx < 0 ? -7 : 7}deg)`;
      card.style.opacity = '.2';
      setTimeout(() => {
        resetCard();
        card.style.removeProperty('opacity');
        classifyCurrentAndMove(status);
        swipeLocked = false;
      }, 120);
    };

    card.addEventListener('pointerup', finishSwipe);
    card.addEventListener('pointercancel', (event) => {
      if (!gesture || gesture.pointerId !== event.pointerId) return;
      gesture = null;
      resetCard();
    });
  }

  function toggleCurrentFavorite() {
    const word = currentWord();
    if (!word) return;
    const saved = itemState(word.id);
    saved.favorite = !saved.favorite;
    saved.updatedAt = new Date().toISOString();
    saveState();
    renderQuiz();
  }

  function reviewWords(filter) {
    if (filter === 'favorite') return vocabulary.filter((word) => itemState(word.id).favorite);
    if (filter.startsWith('genre:')) {
      const genre = filter.slice(6);
      return vocabulary.filter((word) => word.genres.includes(genre));
    }
    return vocabulary.filter((word) => itemState(word.id).status === filter);
  }

  function renderReview(filter = currentReviewFilter) {
    currentReviewFilter = filter;
    $('#review-title').textContent = filter.startsWith('genre:') ? filter.slice(6) : FILTER_LABELS[filter];
    $('#review-search').value = '';
    renderReviewList();
    showView('review');
  }

  function renderReviewList() {
    const query = $('#review-search').value.trim().toLocaleLowerCase('ja');
    const all = reviewWords(currentReviewFilter);
    const words = all.filter((word) => [word.phrase, word.reading, word.meaning, word.example, ...word.similar].some((value) => value.toLocaleLowerCase('ja').includes(query)));
    $('#review-result-count').textContent = query ? `${all.length}件中 ${words.length}件` : `${all.length}件`;
    $('#review-empty').hidden = words.length > 0;
    $('#review-random-button').disabled = all.length === 0;
    const list = $('#review-list');
    list.replaceChildren(...words.map(createReviewItem));
  }

  function createReviewItem(word) {
    const saved = itemState(word.id);
    const article = document.createElement('article');
    article.className = 'review-item';
    const favorite = document.createElement('button');
    favorite.className = 'favorite-button';
    favorite.type = 'button';
    updateFavoriteButton(favorite, saved.favorite);
    favorite.addEventListener('click', () => {
      saved.favorite = !saved.favorite;
      saved.updatedAt = new Date().toISOString();
      saveState();
      if (currentReviewFilter === 'favorite') renderReviewList();
      else updateFavoriteButton(favorite, saved.favorite);
    });
    const title = document.createElement('h2'); title.textContent = word.phrase;
    const reading = document.createElement('p'); reading.className = 'review-reading'; reading.textContent = word.reading;
    const meaning = document.createElement('p'); meaning.className = 'review-meaning'; meaning.textContent = word.meaning;
    const example = document.createElement('p'); example.className = 'review-example'; example.textContent = `例：${word.example}`;
    const similar = document.createElement('p'); similar.className = 'review-similar';
    similar.textContent = word.similar.length ? `近い表現：${word.similar.join('・')}` : '';
    const controls = document.createElement('div'); controls.className = 'review-item-controls';
    Object.entries(STATUS_LABELS).forEach(([status, label]) => {
      const button = document.createElement('button');
      button.type = 'button'; button.textContent = label;
      button.classList.toggle('is-active', saved.status === status);
      button.addEventListener('click', () => {
        saved.status = saved.status === status ? null : status;
        saved.updatedAt = new Date().toISOString();
        saveState();
        renderReviewList();
      });
      controls.append(button);
    });
    article.append(favorite, title, reading, meaning, example, similar, controls);
    return article;
  }

  function renderGenres() {
    const counts = new Map();
    vocabulary.forEach((word) => word.genres.forEach((genre) => counts.set(genre, (counts.get(genre) || 0) + 1)));
    const grid = $('#genre-grid');
    grid.replaceChildren(...[...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'ja')).map(([genre, count]) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'genre-card';
      const title = document.createElement('strong'); title.textContent = genre;
      const small = document.createElement('small'); small.textContent = `${count}表現`;
      button.append(title, small);
      button.addEventListener('click', () => renderReview(`genre:${genre}`));
      return button;
    }));
    showView('genres');
  }

  function renderSettings() {
    $$('.segmented-control button').forEach((button) => {
      const setting = button.dataset.setting;
      const expected = setting === 'showMeaning' ? String(state.settings[setting]) : state.settings[setting];
      const active = button.dataset.value === expected;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-checked', String(active));
    });
    showView('settings');
  }

  function renderBackup() {
    const token = localStorage.getItem(GITHUB_TOKEN_KEY) || '';
    $('#github-token-input').value = token;
    setGithubStatus(token ? 'この端末には保存用トークンが設定されています。' : 'GitHubからの読み込みはすぐ使えます。保存するにはトークンを設定してください。');
    showView('backup');
  }

  function setGithubStatus(message, kind = '') {
    const node = $('#github-backup-status');
    node.textContent = message;
    node.classList.toggle('is-error', kind === 'error');
    node.classList.toggle('is-success', kind === 'success');
  }

  function encodeBase64(text) {
    const bytes = new TextEncoder().encode(text);
    let binary = '';
    for (let index = 0; index < bytes.length; index += 0x8000) {
      binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
    }
    return btoa(binary);
  }

  function decodeBase64(value) {
    const binary = atob(value.replace(/\n/g, ''));
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    return new TextDecoder().decode(bytes);
  }

  async function githubRequest(options = {}) {
    const token = options.token || '';
    const method = options.method || 'GET';
    const url = method === 'GET' ? `${GITHUB_API_URL}?ref=main&t=${Date.now()}` : GITHUB_API_URL;
    const response = await fetch(url, {
      method,
      headers: {
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.body ? { 'Content-Type': 'application/json' } : {})
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      cache: 'no-store'
    });
    let result = null;
    try { result = await response.json(); } catch { /* GitHub returned no JSON. */ }
    if (!response.ok) {
      const detail = result?.message ? `（${result.message}）` : '';
      throw new Error(`GitHubとの通信に失敗しました：${response.status}${detail}`);
    }
    return result;
  }

  async function saveToGithub() {
    const token = $('#github-token-input').value.trim() || localStorage.getItem(GITHUB_TOKEN_KEY) || '';
    if (!token) {
      setGithubStatus('先に保存用トークンを入力してください。', 'error');
      $('#github-token-input').focus();
      return;
    }
    localStorage.setItem(GITHUB_TOKEN_KEY, token);
    $('#github-save-button').disabled = true;
    setGithubStatus('GitHubの現在データを確認しています……');
    try {
      let currentSha = null;
      try { currentSha = (await githubRequest({ token })).sha || null; }
      catch (error) {
        if (!error.message.includes('404')) throw error;
      }
      const payload = {
        ...state,
        app: '使える日本語を勝手に浴びる',
        savedAt: new Date().toISOString()
      };
      const body = {
        message: `Update Japanese learning data (${new Date().toLocaleString('ja-JP')})`,
        content: encodeBase64(JSON.stringify(payload, null, 2)),
        branch: 'main',
        ...(currentSha ? { sha: currentSha } : {})
      };
      await githubRequest({ method: 'PUT', token, body });
      setGithubStatus(`GitHubに保存しました：${new Date().toLocaleString('ja-JP')}`, 'success');
      showToast('GitHubに保存しました');
    } catch (error) {
      setGithubStatus(error.message, 'error');
    } finally {
      $('#github-save-button').disabled = false;
    }
  }

  async function loadFromGithub() {
    $('#github-load-button').disabled = true;
    setGithubStatus('GitHubから読み込んでいます……');
    try {
      const remote = await githubRequest();
      const imported = JSON.parse(decodeBase64(remote.content));
      if (imported.schemaVersion !== 1 || typeof imported.items !== 'object') throw new Error('GitHub上のセーブデータ形式が正しくありません。');
      if (!confirm('この端末の学習状況を、GitHub上のセーブデータで置き換えますか？')) {
        setGithubStatus('読み込みを取り消しました。');
        return;
      }
      state = {
        ...structuredClone(defaults),
        ...imported,
        settings: { ...defaults.settings, ...(imported.settings || {}) },
        items: imported.items || {}
      };
      saveState();
      applyAppearance();
      setGithubStatus(`GitHubから読み込みました：${new Date().toLocaleString('ja-JP')}`, 'success');
      showToast('GitHubから読み込みました');
    } catch (error) {
      setGithubStatus(error.message, 'error');
    } finally {
      $('#github-load-button').disabled = false;
    }
  }

  function saveGithubToken() {
    const token = $('#github-token-input').value.trim();
    if (!token) {
      setGithubStatus('保存するトークンを入力してください。', 'error');
      return;
    }
    localStorage.setItem(GITHUB_TOKEN_KEY, token);
    setGithubStatus('この端末にトークンを記憶しました。', 'success');
  }

  function clearGithubToken() {
    localStorage.removeItem(GITHUB_TOKEN_KEY);
    $('#github-token-input').value = '';
    setGithubStatus('この端末からトークンを削除しました。', 'success');
  }

  function updateSetting(setting, value) {
    state.settings[setting] = setting === 'showMeaning' ? value === 'true' : value;
    saveState();
    applyAppearance();
    renderSettings();
  }

  function exportData() {
    const payload = { ...state, exportedAt: new Date().toISOString(), app: '使える日本語を勝手に浴びる' };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `japanese-shower-backup-${new Date().toISOString().slice(0, 10)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    showToast('データを書き出しました');
  }

  async function importData(file) {
    if (!file) return;
    try {
      const imported = JSON.parse(await file.text());
      if (imported.schemaVersion !== 1 || typeof imported.items !== 'object') throw new Error();
      if (!confirm('現在の学習データを、読み込んだデータで置き換えますか？')) return;
      state = {
        ...structuredClone(defaults),
        ...imported,
        settings: { ...defaults.settings, ...(imported.settings || {}) },
        items: imported.items || {}
      };
      saveState();
      applyAppearance();
      renderSettings();
      showToast('データを読み込みました');
    } catch {
      alert('このファイルは読み込めませんでした。');
    } finally {
      $('#import-input').value = '';
    }
  }

  function resetData() {
    if (!confirm('分類・お気に入り・設定・途中位置をすべて初期化しますか？\nこの操作は取り消せません。')) return;
    state = structuredClone(defaults);
    saveState();
    applyAppearance();
    renderSettings();
    showToast('すべて初期化しました');
  }

  function showToast(message) {
    const toast = $('#toast');
    toast.textContent = message;
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 1800);
  }

  function bindEvents() {
    bindQuizSwipe();
    $('#home-button').addEventListener('click', renderHome);
    $('#settings-shortcut').addEventListener('click', renderSettings);
    $('#settings-button').addEventListener('click', renderSettings);
    $('#genres-button').addEventListener('click', renderGenres);
    $('#backup-button').addEventListener('click', renderBackup);
    $$('.go-home').forEach((button) => button.addEventListener('click', renderHome));
    $('#resume-button').addEventListener('click', () => {
      const resumable = state.session && Array.isArray(state.session.order) && Number.isInteger(state.session.index) && vocabularyById.has(state.session.order[state.session.index]);
      if (resumable) renderQuiz();
      else {
        state.session = null;
        saveState();
        startSession('all', true);
      }
    });
    $('#random-button').addEventListener('click', () => startSession('all'));
    $$('.review-link').forEach((button) => button.addEventListener('click', () => renderReview(button.dataset.filter)));
    $('#quiz-exit').addEventListener('click', renderHome);
    $('#previous-button').addEventListener('click', () => moveSession(-1));
    $('#next-button').addEventListener('click', () => moveSession(1));
    $('#favorite-button').addEventListener('click', toggleCurrentFavorite);
    $('#reveal-button').addEventListener('click', () => {
      const word = currentWord();
      if (!word) return;
      state.session.revealed[word.id] = true;
      saveState();
      renderQuiz();
    });
    $$('.classification button').forEach((button) => button.addEventListener('click', () => setCurrentStatus(button.dataset.status)));
    $('#reshuffle-button').addEventListener('click', () => {
      const pool = state.session?.pool || 'all';
      state.session = null;
      startSession(pool, true);
    });
    $('#review-search').addEventListener('input', renderReviewList);
    $('#review-random-button').addEventListener('click', () => startSession(currentReviewFilter));
    $$('.segmented-control button').forEach((button) => button.addEventListener('click', () => updateSetting(button.dataset.setting, button.dataset.value)));
    $('#export-button').addEventListener('click', exportData);
    $('#import-input').addEventListener('change', (event) => importData(event.target.files[0]));
    $('#reset-button').addEventListener('click', resetData);
    $('#github-save-button').addEventListener('click', saveToGithub);
    $('#github-load-button').addEventListener('click', loadFromGithub);
    $('#github-token-save').addEventListener('click', saveGithubToken);
    $('#github-token-clear').addEventListener('click', clearGithubToken);

    document.addEventListener('keydown', (event) => {
      if (!$('#quiz-view').classList.contains('is-active')) return;
      if (/INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) return;
      if (event.key === 'ArrowLeft') moveSession(-1);
      if (event.key === 'ArrowRight') moveSession(1);
      if (event.key.toLowerCase() === 'f') toggleCurrentFavorite();
      if (event.key === '1') setCurrentStatus('known');
      if (event.key === '2') setCurrentStatus('unknown');
      if (event.key === '3') setCurrentStatus('uninterested');
      if (event.key === ' ' && !$('#reveal-button').hidden) {
        event.preventDefault();
        $('#reveal-button').click();
      }
    });
  }

  async function init() {
    applyAppearance();
    bindEvents();
    try {
      vocabulary = await loadVocabulary();
      vocabularyById = new Map(vocabulary.map((word) => [word.id, word]));
      renderHome();
    } catch (error) {
      $('#error-message').textContent = error.message || '時間を置いて、もう一度お試しください。';
      showView('error');
    }
  }

  init();
})();
