/* Edge TTS 语音工作台 前端逻辑 */
const $ = (id) => document.getElementById(id);

const els = {
  text: $("textInput"), charCount: $("charCount"),
  importBtn: $("importBtn"), fileInput: $("fileInput"), clearBtn: $("clearBtn"),
  countrySel: $("countrySel"), voiceSel: $("voiceSel"), voiceHint: $("voiceHint"),
  previewBtn: $("previewBtn"),
  rate: $("rate"), volume: $("volume"), pitch: $("pitch"),
  rateVal: $("rateVal"), volumeVal: $("volumeVal"), pitchVal: $("pitchVal"),
  convertBtn: $("convertBtn"), progress: $("progress"), bar: document.querySelector(".progress .bar i"),
  progressText: $("progressText"),
  projectSel: $("projectSel"), newProjBtn: $("newProjBtn"), openBtn: $("openBtn"),
  storageBtn: $("storageBtn"),
  resultCard: $("resultCard"), player: $("player"), resultFile: $("resultFile"),
  fileList: $("fileList"), refreshBtn: $("refreshBtn"),
  toast: $("toast"),
  modal: $("modal"), projNameInput: $("projNameInput"), modalOk: $("modalOk"), modalCancel: $("modalCancel"),
  projDirInput: $("projDirInput"), projDirPick: $("projDirPick"),
  storageModal: $("storageModal"), storageTitle: $("storageTitle"), storageDesc: $("storageDesc"),
  storageInput: $("storageInput"), storagePick: $("storagePick"),
  storageOk: $("storageOk"), storageCancel: $("storageCancel"),
};

let voicesByLocale = {};   // locale -> voices[]
let converting = false;
let CFG = { projects_root: "", first_run: false };

/* ---------------- 工具 ---------------- */
function toast(msg, type = "") {
  els.toast.textContent = msg;
  els.toast.className = "toast " + type;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => els.toast.classList.add("hidden"), 2600);
}

const isGUI = () => !!(window.pywebview && window.pywebview.api);

async function pickFolder() {
  if (isGUI()) {
    try { return await window.pywebview.api.pick_folder(); } catch { return null; }
  }
  toast("浏览器模式不支持选择对话框，请手动输入路径", "err");
  return null;
}

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res;
}

function fmtSize(n) {
  return n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.round(n / 1024) + " KB";
}
function fmtTime(ts) {
  const d = new Date(ts * 1000);
  const p = (x) => String(x).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

/* ---------------- 音色 ---------------- */
async function loadVoices() {
  try {
    const data = await (await api("/api/voices")).json();
    voicesByLocale = {};
    for (const c of data) voicesByLocale[c.locale] = c.voices;
    els.countrySel.innerHTML = data
      .map((c) => `<option value="${c.locale}">${c.country}（${c.voices.length}）</option>`)
      .join("");
    onCountryChange();
  } catch (e) {
    els.countrySel.innerHTML = `<option value="">音色加载失败：${e.message}</option>`;
  }
}

function onCountryChange() {
  const locale = els.countrySel.value;
  const voices = voicesByLocale[locale] || [];
  els.voiceSel.innerHTML = voices
    .map((v) => `<option value="${v.name}">${v.display} · ${v.gender}声</option>`)
    .join("");
  els.voiceSel.disabled = voices.length === 0;
  els.previewBtn.disabled = voices.length === 0;
  updateHint();
}

function updateHint() {
  const v = els.voiceSel.value;
  if (!v) { els.voiceHint.textContent = ""; return; }
  const info = (voicesByLocale[els.countrySel.value] || []).find((o) => o.name === v);
  els.voiceHint.textContent = `当前音色：${info ? info.display : v}`;
}

async function preview() {
  const voice = els.voiceSel.value;
  if (!voice) return;
  els.previewBtn.disabled = true;
  const old = els.previewBtn.textContent;
  els.previewBtn.textContent = "试听生成中…";
  try {
    const res = await api(`/api/preview?voice=${encodeURIComponent(voice)}`);
    const blob = await res.blob();
    els.player.src = URL.createObjectURL(blob);
    els.resultCard.classList.remove("hidden");
    await els.player.play().catch(() => {});
  } catch (e) {
    toast("试听失败：" + e.message, "err");
  } finally {
    els.previewBtn.disabled = false;
    els.previewBtn.textContent = old;
  }
}

/* ---------------- 工程 ---------------- */
async function loadConfig() {
  CFG = await (await api("/api/config")).json();
}

async function loadProjects(keep) {
  const list = await (await api("/api/projects")).json();
  const cur = keep || els.projectSel.value;
  els.projectSel.innerHTML = list
    .map((p) => `<option value="${p.name}" title="${p.path}">${p.name}${p.external ? " 〔外部〕" : ""}</option>`)
    .join("");
  if (cur && list.some((p) => p.name === cur)) els.projectSel.value = cur;
  loadFiles();
}

async function loadFiles() {
  const proj = els.projectSel.value;
  if (!proj) { els.fileList.innerHTML = ""; return; }
  try {
    const files = await (await api(`/api/files?project=${encodeURIComponent(proj)}`)).json();
    if (!files.length) {
      els.fileList.innerHTML = `<li class="empty">暂无文件，转换的语音会自动保存到这里</li>`;
      return;
    }
    els.fileList.innerHTML = files.map((f) => `
      <li data-name="${f.name}">
        <span class="fname" title="${f.name}">${f.name}</span>
        <span class="fsize">${fmtSize(f.size)}<br>${fmtTime(f.mtime)}</span>
        <button class="icon-btn play" title="播放">▶</button>
        <a class="icon-btn" href="/api/audio?project=${encodeURIComponent(proj)}&file=${encodeURIComponent(f.name)}" download="${f.name}" title="保存">⬇</a>
        <button class="icon-btn del" title="删除">🗑</button>
      </li>`).join("");
  } catch (e) {
    els.fileList.innerHTML = `<li class="empty">加载失败</li>`;
  }
}

els.fileList.addEventListener("click", async (e) => {
  const li = e.target.closest("li[data-name]");
  if (!li) return;
  const name = li.dataset.name;
  const proj = encodeURIComponent(els.projectSel.value);
  if (e.target.classList.contains("play")) {
    els.player.src = `/api/audio?project=${proj}&file=${encodeURIComponent(name)}`;
    els.resultCard.classList.remove("hidden");
    els.resultFile.textContent = `${els.projectSel.value} / ${name}`;
    els.player.play().catch(() => {});
  } else if (e.target.classList.contains("del")) {
    if (!confirm(`确定删除 ${name}？`)) return;
    try {
      await api(`/api/file?project=${proj}&file=${encodeURIComponent(name)}`, { method: "DELETE" });
      loadFiles();
      toast("已删除", "ok");
    } catch (err) { toast("删除失败：" + err.message, "err"); }
  }
});

/* ---------------- 转换 ---------------- */
async function convert() {
  if (converting) return;
  const text = els.text.value.trim();
  const voice = els.voiceSel.value;
  const project = els.projectSel.value;
  if (!text) { toast("请先输入文本", "err"); return; }
  if (!voice) { toast("请先选择音色", "err"); return; }
  if (!project) { toast("请先选择或创建工程", "err"); return; }

  converting = true;
  els.convertBtn.disabled = true;
  els.progress.classList.remove("hidden");
  setProgress(0, 0);
  try {
    const body = {
      text, voice, project,
      rate: +els.rate.value, volume: +els.volume.value, pitch: +els.pitch.value,
    };
    const { task_id } = await (await api("/api/synthesize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })).json();

    // 轮询进度
    let status;
    while (true) {
      await new Promise((r) => setTimeout(r, 600));
      status = await (await api(`/api/progress/${task_id}`)).json();
      setProgress(status.done, status.total);
      if (status.status !== "running") break;
    }
    if (status.status === "error") throw new Error(status.error);

    toast(`转换完成，已保存到工程「${project}」`, "ok");
    els.player.src = `/api/audio?project=${encodeURIComponent(project)}&file=${encodeURIComponent(status.file)}`;
    els.resultCard.classList.remove("hidden");
    els.resultFile.textContent = `${project} / ${status.file}`;
    loadFiles();
  } catch (e) {
    toast("转换失败：" + e.message, "err");
  } finally {
    converting = false;
    els.convertBtn.disabled = false;
    setTimeout(() => els.progress.classList.add("hidden"), 800);
  }
}

function setProgress(done, total) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  els.bar.style.width = pct + "%";
  els.progressText.textContent = total
    ? `合成中 ${done}/${total} 段（${pct}%）`
    : "连接微软服务…";
}

/* ---------------- 事件绑定 ---------------- */
els.countrySel.addEventListener("change", onCountryChange);
els.voiceSel.addEventListener("change", updateHint);
els.previewBtn.addEventListener("click", preview);
els.convertBtn.addEventListener("click", convert);

els.text.addEventListener("input", () => {
  els.charCount.textContent = `${els.text.value.length} 字`;
  els.convertBtn.disabled = !els.text.value.trim() || !els.voiceSel.value;
});

els.rate.addEventListener("input", () => (els.rateVal.textContent = `${+els.rate.value}%`));
els.volume.addEventListener("input", () => (els.volumeVal.textContent = `${+els.volume.value}%`));
els.pitch.addEventListener("input", () => (els.pitchVal.textContent = `${+els.pitch.value}Hz`));

els.importBtn.addEventListener("click", () => els.fileInput.click());
els.fileInput.addEventListener("change", () => {
  const f = els.fileInput.files[0];
  if (!f) return;
  const reader = new FileReader();
  reader.onload = () => {
    els.text.value = reader.result;
    els.text.dispatchEvent(new Event("input"));
    toast(`已导入 ${f.name}（${els.text.value.length} 字）`, "ok");
  };
  reader.readAsText(f, "utf-8");
  els.fileInput.value = "";
});
els.clearBtn.addEventListener("click", () => {
  els.text.value = "";
  els.text.dispatchEvent(new Event("input"));
});

els.projectSel.addEventListener("change", () => {
  loadFiles();
  els.resultFile.textContent = "";
});

els.openBtn.addEventListener("click", async () => {
  try {
    await api(`/api/open-folder?project=${encodeURIComponent(els.projectSel.value)}`, { method: "POST" });
  } catch (e) { toast("打开失败：" + e.message, "err"); }
});

els.refreshBtn.addEventListener("click", loadFiles);

/* 新建工程 modal */
els.newProjBtn.addEventListener("click", () => {
  els.modal.classList.remove("hidden");
  els.projNameInput.value = "";
  els.projDirInput.value = "";
  els.projDirInput.placeholder = `留空则使用默认位置（${CFG.projects_root}）`;
  els.projNameInput.focus();
});
els.modalCancel.addEventListener("click", () => els.modal.classList.add("hidden"));
els.projNameInput.addEventListener("keydown", (e) => e.key === "Enter" && els.modalOk.click());
els.projDirPick.addEventListener("click", async () => {
  const d = await pickFolder();
  if (d) els.projDirInput.value = d;
});
els.modalOk.addEventListener("click", async () => {
  const name = els.projNameInput.value.trim();
  if (!name) return;
  try {
    await api("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, dir: els.projDirInput.value.trim() || null }),
    });
    els.modal.classList.add("hidden");
    await loadProjects(name);
    toast(`工程「${name}」已创建`, "ok");
  } catch (e) { toast(e.message, "err"); }
});

/* 存储位置设置 (首次启动 / 手动修改) */
function openStorageModal(firstRun) {
  els.storageTitle.textContent = firstRun ? "选择语音保存位置" : "修改默认存储位置";
  els.storageDesc.textContent = firstRun
    ? "欢迎使用！请选择工程与语音文件的默认保存位置，之后可随时更改。"
    : "更改后新建工程将默认保存到新位置，已有工程不受影响。";
  els.storageInput.value = CFG.projects_root;
  els.storageCancel.classList.toggle("hidden", firstRun);
  els.storageModal.classList.remove("hidden");
  els.storageInput.focus();
}
els.storageBtn.addEventListener("click", () => openStorageModal(false));
els.storagePick.addEventListener("click", async () => {
  const d = await pickFolder();
  if (d) els.storageInput.value = d;
});
els.storageCancel.addEventListener("click", () => els.storageModal.classList.add("hidden"));
els.storageInput.addEventListener("keydown", (e) => e.key === "Enter" && els.storageOk.click());
els.storageOk.addEventListener("click", async () => {
  const v = els.storageInput.value.trim();
  if (!v) { toast("请选择或输入存储位置", "err"); return; }
  try {
    CFG = await (await api("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ projects_root: v, first_run: false }),
    })).json();
    els.storageModal.classList.add("hidden");
    await loadProjects();
    toast("存储位置已更新", "ok");
  } catch (e) { toast(e.message, "err"); }
});

/* ---------------- 初始化 ---------------- */
(async () => {
  await loadConfig();
  if (CFG.first_run) openStorageModal(true);
  loadVoices();
  await loadProjects();
  els.text.dispatchEvent(new Event("input"));
})();
