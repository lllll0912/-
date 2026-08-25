/**
 * 把服务器上的最新备份写入用户绑定的本机 backup 文件夹。
 * 依赖 File System Access API（Chrome / Edge）；需 HTTPS 或 localhost。
 */
(function () {
  var DB_NAME = "bill-local-backup-v1";
  var STORE = "handles";
  var KEY = "backupDir";

  function supportsFs() {
    return typeof window.showDirectoryPicker === "function";
  }

  function openDb() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = function () {
        var db = req.result;
        if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE);
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function idbGet(db, key) {
    return new Promise(function (resolve, reject) {
      var tx = db.transaction(STORE, "readonly");
      var req = tx.objectStore(STORE).get(key);
      req.onsuccess = function () { resolve(req.result || null); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function idbSet(db, key, value) {
    return new Promise(function (resolve, reject) {
      var tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).put(value, key);
      tx.oncomplete = function () { resolve(); };
      tx.onerror = function () { reject(tx.error); };
    });
  }

  function idbDel(db, key) {
    return new Promise(function (resolve, reject) {
      var tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).delete(key);
      tx.oncomplete = function () { resolve(); };
      tx.onerror = function () { reject(tx.error); };
    });
  }

  function toast(msg, ok) {
    var el = document.getElementById("local-backup-toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "local-backup-toast";
      el.style.cssText =
        "position:fixed;right:16px;bottom:16px;z-index:9999;max-width:360px;" +
        "padding:10px 14px;border-radius:10px;font-size:13px;box-shadow:0 8px 24px rgba(0,0,0,.18);" +
        "background:#0f172a;color:#fff;";
      document.body.appendChild(el);
    }
    el.style.background = ok === false ? "#9f1239" : "#0f172a";
    el.textContent = msg;
    el.style.display = "block";
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.style.display = "none"; }, 4500);
  }

  function setStatus(bound) {
    var st = document.getElementById("local-backup-status");
    if (st) st.textContent = bound ? "已绑定本机 backup" : "未绑定";
    var btn = document.getElementById("bind-local-backup");
    if (btn) btn.textContent = bound ? "更换本机 backup" : "绑定本机 backup";
  }

  async function getHandle() {
    var db = await openDb();
    return idbGet(db, KEY);
  }

  async function saveHandle(handle) {
    var db = await openDb();
    await idbSet(db, KEY, handle);
    setStatus(true);
  }

  async function clearHandle() {
    var db = await openDb();
    await idbDel(db, KEY);
    setStatus(false);
  }

  async function ensurePermission(handle, interactive) {
    var opts = { mode: "readwrite" };
    try {
      if ((await handle.queryPermission(opts)) === "granted") return true;
      if (!interactive) return false;
      return (await handle.requestPermission(opts)) === "granted";
    } catch (e) {
      return false;
    }
  }

  async function bindFolder() {
    if (!supportsFs()) {
      toast("当前浏览器不支持绑定文件夹，请用 Chrome/Edge，或点「导出备份 zip」", false);
      return null;
    }
    try {
      var handle = await window.showDirectoryPicker({
        mode: "readwrite",
        id: "bill-project-backup",
      });
      await saveHandle(handle);
      toast("已绑定：之后备份会直接写入该文件夹");
      return handle;
    } catch (e) {
      if (e && e.name === "AbortError") return null;
      toast("绑定失败：" + (e && e.message ? e.message : e), false);
      return null;
    }
  }

  async function writeFiles(dirHandle, files) {
    // 保留历史备份：同名则覆盖，不删其它 records_backup_*
    for (var i = 0; i < files.length; i++) {
      var f = files[i];
      var res = await fetch(f.url, { credentials: "same-origin" });
      if (!res.ok) throw new Error("下载失败：" + f.name);
      var buf = await res.arrayBuffer();
      var fh = await dirHandle.getFileHandle(f.name, { create: true });
      var w = await fh.createWritable();
      await w.write(buf);
      await w.close();
    }
  }

  async function syncLatest(opts) {
    opts = opts || {};
    var interactive = !!opts.interactive;
    var handle = await getHandle();
    if (!handle) {
      if (interactive) {
        handle = await bindFolder();
        if (!handle) {
          if (opts.fallbackZip) window.location.href = opts.fallbackZip;
          return false;
        }
      } else {
        showNeedBind(opts.fallbackZip);
        return false;
      }
    }
    if (!(await ensurePermission(handle, interactive))) {
      if (!interactive) {
        showNeedClick(opts.fallbackZip);
        return false;
      }
      toast("未获得写入权限", false);
      return false;
    }
    try {
      var metaRes = await fetch("/api/backup/latest", { credentials: "same-origin" });
      if (!metaRes.ok) throw new Error("无法读取最新备份列表");
      var meta = await metaRes.json();
      if (!meta.files || !meta.files.length) throw new Error("服务器上没有可同步的备份文件");
      await writeFiles(handle, meta.files);
      toast("已写入本机 backup（" + meta.files.length + " 个文件）");
      hideBanner();
      return true;
    } catch (e) {
      toast("同步失败：" + (e && e.message ? e.message : e), false);
      return false;
    }
  }

  function hideBanner() {
    var b = document.getElementById("local-backup-banner");
    if (b) b.remove();
  }

  function showBanner(html) {
    hideBanner();
    var b = document.createElement("div");
    b.id = "local-backup-banner";
    b.className = "flash success";
    b.style.cssText = "display:flex;flex-wrap:wrap;gap:8px;align-items:center;";
    b.innerHTML = html;
    var main = document.querySelector("main.container");
    if (main) main.insertBefore(b, main.firstChild);
    else document.body.insertBefore(b, document.body.firstChild);
  }

  function showNeedBind(fallbackZip) {
    var zip = fallbackZip || "/download/backup.zip?raw=1";
    showBanner(
      '<span>请先绑定本机项目的 <b>backup</b> 文件夹，之后会自动写入，无需整理下载路径。</span>' +
      '<button type="button" class="btn-secondary" id="lb-bind-now">绑定本机 backup</button>' +
      '<a class="btn-secondary" href="' + zip + '">仍下载 zip</a>'
    );
    var btn = document.getElementById("lb-bind-now");
    if (btn) {
      btn.addEventListener("click", function () {
        syncLatest({ interactive: true, fallbackZip: zip });
      });
    }
  }

  function showNeedClick(fallbackZip) {
    var zip = fallbackZip || "/download/backup.zip?raw=1";
    showBanner(
      '<span>浏览器需要你点一下，才能写入已绑定的 backup 文件夹。</span>' +
      '<button type="button" id="lb-sync-now">写入本机 backup</button>' +
      '<a class="btn-secondary" href="' + zip + '">改下 zip</a>'
    );
    var btn = document.getElementById("lb-sync-now");
    if (btn) {
      btn.addEventListener("click", function () {
        syncLatest({ interactive: true, fallbackZip: zip });
      });
    }
  }

  async function refreshStatus() {
    if (!supportsFs()) {
      setStatus(false);
      var st = document.getElementById("local-backup-status");
      if (st) st.textContent = "浏览器不支持绑定";
      return;
    }
    try {
      var h = await getHandle();
      setStatus(!!h);
    } catch (e) {
      setStatus(false);
    }
  }

  function init() {
    refreshStatus();
    var bindBtn = document.getElementById("bind-local-backup");
    if (bindBtn) {
      bindBtn.addEventListener("click", function () {
        bindFolder();
      });
    }
    var exportBtn = document.getElementById("export-local-backup");
    if (exportBtn) {
      exportBtn.addEventListener("click", function (e) {
        e.preventDefault();
        // 先让服务器生成最新备份，再同步到绑定目录
        window.location.href = exportBtn.getAttribute("href") || "/download/backup.zip";
      });
    }
    if (window.__SYNC_LOCAL_BACKUP) {
      syncLatest({
        interactive: false,
        fallbackZip: "/download/backup.zip?raw=1",
      });
    }
  }

  window.LocalBackup = {
    bindFolder: bindFolder,
    syncLatest: syncLatest,
    clearHandle: clearHandle,
    supportsFs: supportsFs,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
