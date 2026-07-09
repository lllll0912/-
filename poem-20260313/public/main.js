const API_BASE = '';

function getOrCreateUserId() {
  let id = localStorage.getItem('poems_user_id');
  if (!id) {
    id = 'web-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem('poems_user_id', id);
  }
  return id;
}

const userId = getOrCreateUserId();

const todayDateEl = document.getElementById('today-date');
const todayContentEl = document.getElementById('today-content');
const todayMetaEl = document.getElementById('today-meta');
const favoriteStatusEl = document.getElementById('favorite-status');
const btnFavorite = document.getElementById('btn-favorite');
const favoriteTextEl = document.getElementById('favorite-text');
const btnToggleHistory = document.getElementById('btn-toggle-history');
const historyCard = document.getElementById('history-card');
const listTitleEl = document.getElementById('list-title');
const listContainerEl = document.getElementById('list-container');
const tabHistory = document.getElementById('tab-history');
const tabFavorites = document.getElementById('tab-favorites');

let todayPoem = null;
let todayIsFavorite = false;

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json'
    },
    ...options
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

async function loadToday() {
  todayContentEl.textContent = '正在获取今日推荐...';
  try {
    const data = await fetchJSON(`${API_BASE}/api/today`);
    todayPoem = data;
    todayContentEl.textContent = data.content || '（无内容）';
    const dateStr = data.done_date ? new Date(data.done_date).toLocaleDateString('zh-CN') : '日期未知';
    todayDateEl.textContent = `日期：${dateStr}`;
    todayMetaEl.textContent = data.poem_date ? `原始日期：${data.poem_date}` : '';

    await refreshFavoriteState();
  } catch (e) {
    console.error(e);
    todayContentEl.textContent = '获取失败，请稍后重试';
    todayDateEl.textContent = '';
  }
}

async function refreshFavoriteState() {
  if (!todayPoem) return;
  try {
    const favorites = await fetchJSON(`${API_BASE}/api/favorites?userId=${encodeURIComponent(userId)}`);
    const ids = new Set(favorites.map((f) => f.id));
    todayIsFavorite = ids.has(todayPoem.id);
    updateFavoriteButton();
  } catch (e) {
    console.error(e);
  }
}

function updateFavoriteButton() {
  if (todayIsFavorite) {
    favoriteTextEl.textContent = '已收藏';
    favoriteStatusEl.textContent = '❤ 已收藏';
    favoriteStatusEl.style.color = '#f97316';
  } else {
    favoriteTextEl.textContent = '收藏';
    favoriteStatusEl.textContent = '';
  }
}

btnFavorite.addEventListener('click', async () => {
  if (!todayPoem) return;
  try {
    if (todayIsFavorite) {
      await fetchJSON(`${API_BASE}/api/favorites`, {
        method: 'DELETE',
        body: JSON.stringify({ userId, poemId: todayPoem.id })
      });
      todayIsFavorite = false;
    } else {
      await fetchJSON(`${API_BASE}/api/favorites`, {
        method: 'POST',
        body: JSON.stringify({ userId, poemId: todayPoem.id })
      });
      todayIsFavorite = true;
    }
    updateFavoriteButton();
  } catch (e) {
    console.error(e);
    alert('操作失败，请稍后重试');
  }
});

btnToggleHistory.addEventListener('click', () => {
  if (historyCard.style.display === 'none') {
    historyCard.style.display = 'block';
    loadHistory();
  } else {
    historyCard.style.display = 'none';
  }
});

tabHistory.addEventListener('click', () => {
  tabHistory.classList.add('tab-active');
  tabFavorites.classList.remove('tab-active');
  listTitleEl.textContent = '最近推送';
  loadHistory();
});

tabFavorites.addEventListener('click', () => {
  tabFavorites.classList.add('tab-active');
  tabHistory.classList.remove('tab-active');
  listTitleEl.textContent = '我的收藏';
  loadFavorites();
});

async function loadHistory() {
  listContainerEl.innerHTML = '<div class="empty-text">加载中...</div>';
  try {
    const data = await fetchJSON(`${API_BASE}/api/history?page=1&pageSize=50`);
    if (!data.length) {
      listContainerEl.innerHTML = '<div class="empty-text">暂无历史推送</div>';
      return;
    }
    renderList(data, false);
  } catch (e) {
    console.error(e);
    listContainerEl.innerHTML = '<div class="empty-text">加载失败</div>';
  }
}

async function loadFavorites() {
  listContainerEl.innerHTML = '<div class="empty-text">加载中...</div>';
  try {
    const data = await fetchJSON(`${API_BASE}/api/favorites?userId=${encodeURIComponent(userId)}`);
    if (!data.length) {
      listContainerEl.innerHTML = '<div class="empty-text">你还没有收藏的诗句</div>';
      return;
    }
    renderList(data, true);
  } catch (e) {
    console.error(e);
    listContainerEl.innerHTML = '<div class="empty-text">加载失败</div>';
  }
}

function renderList(list, isFavoriteList) {
  listContainerEl.innerHTML = '';
  list.forEach((item) => {
    const div = document.createElement('div');
    div.className = 'history-item';
    const dateStr = item.done_date ? new Date(item.done_date).toLocaleDateString('zh-CN') : '日期未知';
    div.innerHTML = `
      <div class="history-line1">${item.content || '（无内容）'}</div>
      <div class="history-line2">
        <span>推送日期：${dateStr}</span>
        ${isFavoriteList ? '<span class="favorite-tag">❤ 收藏</span>' : ''}
      </div>
    `;
    listContainerEl.appendChild(div);
  });
}

loadToday();

