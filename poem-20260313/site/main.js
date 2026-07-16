/**
 * 每日一诗 — 按日期确定性选取；诗境面板展示出处、全诗、背景与解读。
 */

const EPOCH = Date.UTC(2020, 11, 23);
const STORY_SECTIONS = [
  { key: "source", label: "出处" },
  { key: "full_poem", label: "全诗" },
  { key: "background", label: "创作背景" },
  { key: "interpretation", label: "解读" },
  { key: "meaning", label: "意在何处" },
];

let currentPoem = null;

function pad(n) {
  return String(n).padStart(2, "0");
}

function formatDate(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function formatDateCN(d) {
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日`;
}

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

function parseLocalDate(dateStr) {
  const [y, m, day] = dateStr.split("-").map(Number);
  return new Date(y, m - 1, day);
}

function hasStory(story) {
  if (!story || typeof story !== "object") return false;
  return STORY_SECTIONS.some(({ key }) => story[key] && String(story[key]).trim());
}

async function loadPoems() {
  const res = await fetch("./poems.json", { cache: "no-cache" });
  if (!res.ok) throw new Error("无法加载诗库");
  const data = await res.json();
  return data.poems || [];
}

function showPoem(poem, when) {
  currentPoem = poem;
  const textEl = document.getElementById("poem-text");
  const dateEl = document.getElementById("poem-date");
  const storyBtn = document.getElementById("btn-story");

  dateEl.textContent = formatDateCN(when);
  textEl.textContent = poem.content || "（暂无）";

  const card = document.getElementById("poem-card");
  card.style.animation = "none";
  card.offsetHeight;
  card.style.animation = "";

  storyBtn.hidden = false;
  storyBtn.classList.toggle("story-entry--ready", hasStory(poem.story));
  storyBtn.querySelector(".story-entry-hint").textContent = hasStory(poem.story)
    ? "读出处 · 全诗 · 背景"
    : "故事整理中";
}

function renderStorySections(story) {
  const container = document.getElementById("story-sections");
  const empty = document.getElementById("story-empty");
  container.innerHTML = "";

  if (!hasStory(story)) {
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  STORY_SECTIONS.forEach(({ key, label }) => {
    const text = story[key];
    if (!text || !String(text).trim()) return;
    const section = document.createElement("section");
    section.className = "story-block";
    section.innerHTML = `<h3>${label}</h3>`;
    const body = document.createElement("p");
    body.className = key === "full_poem" ? "story-full-poem" : "story-block-text";
    body.textContent = text;
    section.appendChild(body);
    container.appendChild(section);
  });
}

function openStory() {
  if (!currentPoem) return;
  closeHistory();

  document.getElementById("story-poem-line").textContent = currentPoem.content || "";
  renderStorySections(currentPoem.story);

  const panel = document.getElementById("story-panel");
  panel.hidden = false;
  document.getElementById("story-scroll").scrollTop = 0;
  document.body.classList.add("panel-open");
}

function closeStory() {
  document.getElementById("story-panel").hidden = true;
  document.body.classList.remove("panel-open");
}

function buildHistory(poems, today) {
  const list = document.getElementById("history-list");
  list.innerHTML = "";
  const count = poems.length;
  const todayStr = formatDate(today);

  for (let back = 0; back < 45; back++) {
    const d = new Date(today);
    d.setDate(d.getDate() - back);
    const ds = formatDate(d);
    const poem = poems[indexForDate(ds, count)];
    const isToday = ds === todayStr;

    const li = document.createElement("li");
    li.innerHTML = `
      <div class="h-date">${formatDateCN(d)}${isToday ? " · 今日" : ""}${hasStory(poem.story) ? " · 有诗境" : ""}</div>
      <div class="h-text"></div>
    `;
    li.querySelector(".h-text").textContent = poem.content;
    li.addEventListener("click", () => {
      showPoem(poem, parseLocalDate(ds));
      closeHistory();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    list.appendChild(li);
  }
}

function openHistory() {
  closeStory();
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

  document.getElementById("btn-story").addEventListener("click", openStory);
  document.getElementById("btn-close-story").addEventListener("click", closeStory);
  document.getElementById("story-panel").addEventListener("click", (e) => {
    if (e.target.id === "story-panel") closeStory();
  });

  document.getElementById("btn-history").addEventListener("click", openHistory);
  document.getElementById("btn-close-history").addEventListener("click", closeHistory);
  document.getElementById("history-panel").addEventListener("click", (e) => {
    if (e.target.id === "history-panel") closeHistory();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeStory();
      closeHistory();
    }
  });
}

main();
