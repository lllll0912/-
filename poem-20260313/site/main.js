/**
 * 每日一诗 — 按日期确定性选取同一首，全球同日同句。
 */

const EPOCH = Date.UTC(2020, 11, 23); // 与诗库起始大致对齐

function pad(n) {
  return String(n).padStart(2, "0");
}

function formatDate(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function formatDateCN(d) {
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日`;
}

/** 将 YYYY-MM-DD 映射为稳定整数哈希 */
function dateHash(dateStr) {
  let h = 2166136261;
  for (let i = 0; i < dateStr.length; i++) {
    h ^= dateStr.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function indexForDate(dateStr, count) {
  if (!count) return 0;
  return dateHash(dateStr) % count;
}

function daysBetweenUTC(a, b) {
  return Math.floor((a - b) / 86400000);
}

function dateFromOffset(offsetDays) {
  const t = EPOCH + offsetDays * 86400000;
  const d = new Date(t);
  return new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
}

function parseLocalDate(dateStr) {
  const [y, m, day] = dateStr.split("-").map(Number);
  return new Date(y, m - 1, day);
}

async function loadPoems() {
  const res = await fetch("./poems.json", { cache: "no-cache" });
  if (!res.ok) throw new Error("无法加载诗库");
  const data = await res.json();
  return data.poems || [];
}

function showPoem(poem, when) {
  const textEl = document.getElementById("poem-text");
  const dateEl = document.getElementById("poem-date");
  const storyWrap = document.getElementById("poem-story");
  const storyBody = document.getElementById("poem-story-body");

  dateEl.textContent = formatDateCN(when);
  textEl.textContent = poem.content || "（暂无）";

  // 重触发淡入
  const card = document.getElementById("poem-card");
  card.style.animation = "none";
  // eslint-disable-next-line no-unused-expressions
  card.offsetHeight;
  card.style.animation = "";

  if (poem.story && String(poem.story).trim()) {
    storyBody.textContent = poem.story;
    storyWrap.hidden = false;
  } else {
    storyWrap.hidden = true;
    storyBody.textContent = "";
  }
}

function buildHistory(poems, today) {
  const list = document.getElementById("history-list");
  list.innerHTML = "";
  const count = poems.length;
  const todayStr = formatDate(today);
  const todayOffset = daysBetweenUTC(
    Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()),
    EPOCH
  );

  const items = [];
  for (let back = 0; back < 45 && back <= todayOffset + 365; back++) {
    const d = new Date(today);
    d.setDate(d.getDate() - back);
    const ds = formatDate(d);
    const idx = indexForDate(ds, count);
    items.push({ date: d, dateStr: ds, poem: poems[idx], isToday: ds === todayStr });
  }

  items.forEach(({ date, dateStr, poem, isToday }) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="h-date">${formatDateCN(date)}${isToday ? " · 今日" : ""}</div>
      <div class="h-text"></div>
    `;
    li.querySelector(".h-text").textContent = poem.content;
    li.addEventListener("click", () => {
      showPoem(poem, parseLocalDate(dateStr));
      closeHistory();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    list.appendChild(li);
  });
}

function openHistory() {
  const panel = document.getElementById("history-panel");
  const btn = document.getElementById("btn-history");
  panel.hidden = false;
  btn.setAttribute("aria-expanded", "true");
}

function closeHistory() {
  const panel = document.getElementById("history-panel");
  const btn = document.getElementById("btn-history");
  panel.hidden = true;
  btn.setAttribute("aria-expanded", "false");
}

async function main() {
  const today = new Date();
  const todayLocal = new Date(today.getFullYear(), today.getMonth(), today.getDate());

  try {
    const poems = await loadPoems();
    if (!poems.length) {
      document.getElementById("poem-text").textContent = "诗库为空";
      return;
    }
    const todayStr = formatDate(todayLocal);
    const poem = poems[indexForDate(todayStr, poems.length)];
    showPoem(poem, todayLocal);
    buildHistory(poems, todayLocal);
  } catch (err) {
    console.error(err);
    document.getElementById("poem-text").textContent = "加载失败，请稍后刷新";
    document.getElementById("poem-date").textContent = "";
  }

  document.getElementById("btn-history").addEventListener("click", openHistory);
  document.getElementById("btn-close-history").addEventListener("click", closeHistory);
  document.getElementById("history-panel").addEventListener("click", (e) => {
    if (e.target.id === "history-panel") closeHistory();
  });
}

main();
