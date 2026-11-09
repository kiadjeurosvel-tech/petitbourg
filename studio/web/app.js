'use strict';
/* Mon Studio — interface web. Aucune dépendance externe, aucun secret côté navigateur :
   seul un jeton de session (à durée limitée) est conservé sur l'appareil. */

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const LS = {
  get(k, d = null) { try { const v = localStorage.getItem('studio.' + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('studio.' + k, JSON.stringify(v)); } catch { /* stockage indisponible */ } },
  del(k) { try { localStorage.removeItem('studio.' + k); } catch { /* */ } },
};
const ON_PAGES = /\.github\.io$/.test(location.hostname) || location.protocol === 'file:';
const S = { api: ON_PAGES ? (LS.get('api') || '') : '', token: LS.get('token'), sys: null, jobs: [], timer: null, view: null, interpTimer: null };

const ICON = {
  play: '<svg viewBox="0 0 24 24"><path d="M7 4l13 8-13 8z"/></svg>',
  dl: '<svg viewBox="0 0 24 24"><path d="M12 3v12M6 11l6 6 6-6M4 21h16"/></svg>',
  plus: '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>',
  wand: '<svg viewBox="0 0 24 24"><path d="M4 20L16 8M14 4v3M18 6h3M19 10v3M12 2h0"/></svg>',
  next: '<svg viewBox="0 0 24 24"><path d="M5 12h12M13 6l6 6-6 6"/></svg>',
  edit: '<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg>',
  redo: '<svg viewBox="0 0 24 24"><path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/></svg>',
  ep: '<svg viewBox="0 0 24 24"><path d="M4 6h16v12H4zM9 10l5 2-5 2z"/></svg>',
  save: '<svg viewBox="0 0 24 24"><path d="M5 4h11l3 3v13H5zM8 4v5h7V4M8 20v-6h8v6"/></svg>',
  x: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>',
};
const STAGE_UNIT = { 'images': 'images', 'scènes': 'scènes', 'personnages': 'personnages', '%': '%' };
const EXAMPLES = [
  'Crée une animation 3D de deux personnages qui se disputent dans un restaurant.',
  'Crée un épisode de 2 minutes avec les personnages de mon histoire précédente.',
  "Continue automatiquement l'histoire précédente.",
  'Crée une animation cinématographique avec une caméra dynamique.',
  'Reprends la scène 4 et améliore les expressions faciales.',
  'Génère une histoire mystérieuse en 3D au format vertical 9:16.',
];
const EDIT_EXAMPLES = ['Le personnage doit être plus expressif.', 'La caméra doit se déplacer vers la gauche.', 'Ralentis le mouvement de cette scène.',
  "Change uniquement l'arrière-plan.", 'Conserve exactement le même personnage.', 'Mets cette scène de nuit, éclairage dramatique.'];

// ------------------------------------------------------------------ utilitaires
function toast(msg, kind = '') {
  const t = document.createElement('div');
  t.className = 'toast ' + kind; t.textContent = msg;
  $('#toasts').append(t);
  setTimeout(() => t.remove(), kind === 'err' ? 7000 : 4000);
}
const fmtDur = (s) => s == null ? '' : (s >= 60 ? `${Math.floor(s / 60)} min ${String(Math.round(s % 60)).padStart(2, '0')}` : `${Math.round(s)} s`);
const fmtEta = (s) => s == null ? '' : s < 60 ? `≈ ${Math.max(1, Math.round(s))} s restantes` : s < 3600 ? `≈ ${Math.round(s / 60)} min restantes` : `≈ ${(s / 3600).toFixed(1)} h restantes`;
const fmtDate = (t) => t ? new Date(t * 1000).toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
const mediaUrl = (u) => u ? (u.startsWith('http') ? u : S.api + u) : '';
const STATUS = { queued: 'En attente', running: 'En cours', cancelling: 'Annulation…', done: 'Terminé', error: 'Erreur', cancelled: 'Annulé' };

async function api(path, { method = 'GET', body } = {}) {
  let r;
  try {
    r = await fetch(S.api + path, {
      method, headers: { ...(S.token ? { Authorization: 'Bearer ' + S.token } : {}), ...(body ? { 'Content-Type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined, cache: 'no-store',
    });
  } catch {
    setEngine(false);
    throw new Error("Le moteur ne répond pas. Vérifiez que votre ordinateur est allumé et que le studio est lancé (ordinateur éteint : mode cloud GitHub, voir Réglages).");
  }
  if (r.status === 401 && !path.startsWith('/api/auth/login')) { logout(); throw new Error('Session expirée, reconnectez-vous.'); }
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('json') ? await r.json() : await r.text();
  if (!r.ok) throw new Error((data && data.detail) || `Erreur ${r.status}`);
  return data;
}

function setEngine(on, text) {
  const p = $('#engine-pill');
  p.className = 'engine ' + (on ? 'on' : 'off');
  p.querySelector('span').textContent = text || (on ? 'Moteur en ligne' : 'Moteur hors ligne');
}

// ------------------------------------------------------------------ connexion
function showLogin(msg) {
  $('#app').hidden = true; $('#login').hidden = false;
  $('#api-field').hidden = !ON_PAGES;
  if (ON_PAGES) $('#login-api').value = S.api;
  $('#login-err').textContent = msg || '';
  setTimeout(() => (ON_PAGES && !S.api ? $('#login-api') : $('#login-pw')).focus(), 50);
}
function logout() {
  S.token = null; LS.del('token'); clearTimeout(S.timer); showLogin();
}
$('#login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('#login-err').textContent = '';
  if (ON_PAGES) {
    let u = $('#login-api').value.trim().replace(/\/+$/, '');
    if (!/^https:\/\//.test(u) && !/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(u)) {
      $('#login-err').textContent = "L'adresse doit commencer par https:// (connexion chiffrée)."; return;
    }
    S.api = u; LS.set('api', u);
  }
  try {
    const r = await api('/api/auth/login', { method: 'POST', body: { password: $('#login-pw').value } });
    S.token = r.token; LS.set('token', r.token); $('#login-pw').value = '';
    start();
  } catch (err) { $('#login-err').textContent = err.message; }
});

// ------------------------------------------------------------------ démarrage / routage
async function start() {
  if (!S.token || (ON_PAGES && !S.api)) return showLogin();
  $('#login').hidden = true; $('#app').hidden = false;
  try {
    S.sys = await api('/api/system');
    setEngine(true, `En ligne · ${S.sys.renderer === 'blender' ? 'Blender' : 'aperçu 2D'} · ${S.sys.tts_selected}`);
  } catch (err) { if (!S.token) return; setEngine(false); toast(err.message, 'err'); }
  route();
  pollJobs();
}
window.addEventListener('hashchange', route);

function route() {
  if (!S.token) return;
  const h = location.hash.replace(/^#\/?/, '') || 'studio';
  const [name, a, b] = h.split('/');
  $$('#nav a').forEach((l) => l.classList.toggle('on', l.dataset.nav === (['episode', 'histoire'].includes(name) ? 'bibliotheque' : name)));
  S.view = name;
  const v = $('#view');
  v.style.animation = 'none'; void v.offsetWidth; v.style.animation = '';
  const views = { studio: viewStudio, production: viewProduction, bibliotheque: () => viewLibrary(a || 'videos', b), episode: () => viewEpisode(+a), histoire: () => viewStory(+a), reglages: viewSettings };
  (views[name] || viewStudio)().catch((err) => { v.innerHTML = `<div class="empty">${esc(err.message)}</div>`; });
  window.scrollTo(0, 0);
}

// ------------------------------------------------------------------ suivi des tâches (temps réel)
async function pollJobs() {
  clearTimeout(S.timer);
  if (!S.token) return;
  let delay = 5000;
  try {
    S.jobs = await api('/api/jobs?active=1');
    const active = S.jobs.filter((j) => ['queued', 'running', 'cancelling'].includes(j.status));
    const b = $('#badge-jobs'); b.hidden = !active.length; b.textContent = active.length;
    if (active.length) delay = 1200;
    setEngine(true, S.sys ? `En ligne · ${S.sys.renderer === 'blender' ? 'Blender' : 'aperçu 2D'} · ${S.sys.tts_selected}` : undefined);
    if (S.view === 'production') renderJobs($('#jobs-active'), active, true);
    if (S.view === 'studio' && $('#studio-jobs')) renderJobs($('#studio-jobs'), S.jobs.slice(-2).reverse(), false);
    for (const j of S.jobs) {
      const prev = S.known?.[j.id];
      if (prev && prev !== j.status && ['done', 'error'].includes(j.status)) {
        toast(j.status === 'done' ? `Terminé : ${j.title}` : `Échec : ${j.error || j.title}`, j.status === 'done' ? 'ok' : 'err');
        if (S.view === 'episode' && j.episode_id === S.episodeId) viewEpisode(S.episodeId, true);
      }
    }
    S.known = Object.fromEntries(S.jobs.map((j) => [j.id, j.status]));
  } catch { delay = 8000; }
  S.timer = setTimeout(pollJobs, delay);
}

function stageHtml(st) {
  const known = st.total != null && st.total > 0;
  const pct = known ? Math.min(100, Math.round((st.done / st.total) * 100)) : 0;
  let meta = '';
  if (st.status === 'running' && known) meta = st.unit === '%' ? `${pct} %` : `${st.done} / ${st.total} ${esc(STAGE_UNIT[st.unit] || st.unit || '')}`;
  if (st.status === 'done' && st.started && st.finished) meta = `${(st.finished - st.started).toFixed(1)} s`;
  if (st.status === 'skipped') meta = 'non nécessaire';
  const eta = st.status === 'running' && st.eta != null ? ` · ${fmtEta(st.eta)}` : '';
  const ic = { done: '✓', error: '!', skipped: '–', cancelled: '–' }[st.status] || '';
  return `<div class="stage ${esc(st.status)}"><span class="ic">${ic}</span><span class="lbl">${esc(st.label)}</span><span class="meta">${meta}${eta}</span>
    ${st.status === 'running' ? `<div class="bar ${known ? '' : 'indet'}"><i style="width:${pct}%"></i></div>` : ''}
    ${st.detail ? `<div class="det">${esc(st.detail)}</div>` : ''}</div>`;
}

function jobHtml(j, full) {
  const stages = (j.stages || []).filter((s) => full || s.status !== 'pending' || j.status === 'queued');
  const actions = [];
  if (['queued', 'running'].includes(j.status)) actions.push(`<button class="btn small ghost danger" data-cancel="${j.id}">${ICON.x}Annuler</button>`);
  if (['error', 'cancelled'].includes(j.status)) actions.push(`<button class="btn small" data-retry="${j.id}">${ICON.redo}Relancer</button>`);
  if (j.status === 'done' && j.episode_id) actions.push(`<a class="btn small primary" href="#/episode/${j.episode_id}">${ICON.play}Voir le résultat</a>`);
  if (full) actions.push(`<button class="btn small ghost" data-log="${j.id}">Journal</button>`);
  return `<div class="card job" data-job="${j.id}">
    <div class="job-head"><div><div class="job-title">${esc(j.title)}</div>
      <div class="small muted">#${j.id} · ${fmtDate(j.created)}${j.queue_position ? ` · position ${j.queue_position} dans la file` : ''}</div></div>
      <span class="status ${esc(j.status)}">${STATUS[j.status] || esc(j.status)}</span></div>
    ${j.error ? `<div class="notice" style="border-color:var(--err);margin-bottom:10px">${esc(j.error)}</div>` : ''}
    <div class="stages">${stages.map(stageHtml).join('')}</div>
    <div class="row" style="margin-top:12px">${actions.join('')}</div>
    <div class="log" hidden></div></div>`;
}

function renderJobs(el, jobs, full) {
  if (!el) return;
  if (!jobs.length) { el.innerHTML = full ? '<div class="empty">Aucune production en cours. Lancez-en une depuis le Studio.</div>' : ''; return; }
  const openLogs = new Set($$('.log:not([hidden])', el).map((l) => l.closest('[data-job]').dataset.job));
  el.innerHTML = jobs.map((j) => jobHtml(j, full)).join('');
  openLogs.forEach((id) => showLog(+id, el));
}
async function showLog(id, root = document) {
  const box = $(`[data-job="${id}"] .log`, root); if (!box) return;
  const j = await api(`/api/jobs/${id}?log=1`);
  box.hidden = false; box.textContent = j.log || '(journal vide)'; box.scrollTop = box.scrollHeight;
}
document.addEventListener('click', async (e) => {
  const t = e.target.closest('[data-cancel],[data-retry],[data-log]');
  if (!t) return;
  try {
    if (t.dataset.cancel) { await api(`/api/jobs/${t.dataset.cancel}/cancel`, { method: 'POST' }); toast('Annulation demandée.'); }
    if (t.dataset.retry) { await api(`/api/jobs/${t.dataset.retry}/retry`, { method: 'POST' }); toast('Production relancée.', 'ok'); }
    if (t.dataset.log) { const box = $(`[data-job="${t.dataset.log}"] .log`); if (box && !box.hidden) box.hidden = true; else await showLog(+t.dataset.log); return; }
    pollJobs();
  } catch (err) { toast(err.message, 'err'); }
});

// ------------------------------------------------------------------ STUDIO (centre de commande)
async function viewStudio() {
  const sys = S.sys || {};
  const opt = sys.options || { styles: {}, formats: ['9:16', '16:9', '1:1'], qualities: ['brouillon', 'standard', 'final'] };
  const draft = LS.get('draft', {});
  const [projects, stories] = await Promise.all([api('/api/projects'), api('/api/stories')]);
  const v = $('#view');
  v.innerHTML = `
  <div class="head"><div><h1>Centre de commande</h1><p class="muted">Décrivez la vidéo. Le moteur s'occupe du reste — sur votre machine.</p></div>
    <div class="row"><a class="btn ghost" href="#/production">Voir la production</a></div></div>
  <div class="grid two">
    <div class="stack">
      <div class="card stack">
        <div class="opts" style="grid-template-columns:repeat(2,minmax(0,1fr))">
          <label class="field"><span>Projet</span><select id="f-project"><option value="">— Nouveau projet —</option>
            ${projects.map((p) => `<option value="${p.id}">${esc(p.name)}</option>`).join('')}</select></label>
          <label class="field"><span>Histoire (pour continuer / modifier)</span><select id="f-story"><option value="">— Dernière histoire / nouvelle —</option></select></label>
        </div>
        <label class="field"><span>Votre demande</span>
          <textarea id="f-text" class="prompt" placeholder="Ex. : Crée une animation 3D de deux personnages qui se disputent dans un restaurant, 45 secondes, format vertical.">${esc(draft.text || '')}</textarea></label>
        <div class="chips">${EXAMPLES.map((x) => `<button class="chip" data-ex="${esc(x)}">${esc(x)}</button>`).join('')}</div>
        <div class="opts">
          <label class="field"><span>Style</span><select id="f-style"><option value="">Selon le texte</option>
            ${Object.entries(opt.styles).map(([k, l]) => `<option value="${k}">${esc(l)}</option>`).join('')}</select></label>
          <label class="field"><span>Durée</span><select id="f-duration"><option value="">Selon le texte</option>
            ${[[15, '15 s'], [30, '30 s'], [45, '45 s'], [60, '1 min'], [90, '1 min 30'], [120, '2 min'], [180, '3 min'], [300, '5 min']].map(([k, l]) => `<option value="${k}">${l}</option>`).join('')}</select></label>
          <div class="field"><span>Format</span><div class="seg" id="f-format">${['', '9:16', '16:9', '1:1'].map((f) => `<button type="button" data-v="${f}">${f || 'Auto'}</button>`).join('')}</div></div>
          <div class="field"><span>Qualité</span><div class="seg" id="f-quality">${[['brouillon', 'Brouillon'], ['standard', 'Standard'], ['final', 'Final']].map(([k, l]) => `<button type="button" data-v="${k}">${l}</button>`).join('')}</div></div>
        </div>
        <div class="row between">
          <label class="check"><input type="checkbox" id="f-subs" checked> Sous-titres incrustés</label>
          <button class="btn primary big" id="go">${ICON.wand}Générer</button>
        </div>
      </div>
      <div class="card stack">
        <h3>Commandes</h3>
        <div class="cmds">
          <button class="btn" data-cmd="create">${ICON.plus}Créer une vidéo</button>
          <button class="btn" data-cmd="continue">${ICON.next}Continuer une histoire</button>
          <button class="btn" data-cmd="edit_scene">${ICON.edit}Modifier une scène</button>
          <button class="btn" data-cmd="regenerate_scene">${ICON.redo}Régénérer une scène</button>
          <button class="btn" data-cmd="new_episode">${ICON.ep}Générer un nouvel épisode</button>
          <button class="btn" id="save-project">${ICON.save}Enregistrer le projet</button>
        </div>
        <div class="row small muted" id="scene-row" hidden>
          <label class="field" style="flex:1"><span>Épisode</span><select id="f-episode"></select></label>
          <label class="field" style="width:130px"><span>Scène</span><select id="f-scene"><option value="">Toutes / selon le texte</option></select></label>
        </div>
      </div>
    </div>
    <div class="stack">
      ${phoneCardHtml()}
      <div class="card understood" id="interp"><h3>Ce que le moteur a compris</h3><p class="muted small">Commencez à écrire : l'interprétation s'affiche ici avant de lancer quoi que ce soit.</p></div>
      <div id="studio-jobs" class="stack"></div>
    </div>
  </div>`;

  const segVal = (id) => $(`#${id} button.on`)?.dataset.v || '';
  const setSeg = (id, val) => $$(`#${id} button`).forEach((b) => b.classList.toggle('on', b.dataset.v === val));
  setSeg('f-format', draft.format ?? ''); setSeg('f-quality', draft.quality || sys.default_quality || 'standard');
  $$('.seg').forEach((seg) => seg.addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) { setSeg(seg.id, b.dataset.v); saveDraft(); interpret(); } }));
  if (draft.style) $('#f-style').value = draft.style;
  if (draft.duration) $('#f-duration').value = draft.duration;
  if (draft.project_id) $('#f-project').value = draft.project_id;

  const fillStories = () => {
    const pid = +$('#f-project').value;
    const list = stories.filter((s) => !pid || s.project_id === pid);
    $('#f-story').innerHTML = '<option value="">— Dernière histoire / nouvelle —</option>' + list.map((s) => `<option value="${s.id}">${esc(s.title)} (${s.n_episodes} ép.)</option>`).join('');
    if (draft.story_id && list.some((s) => s.id === draft.story_id)) $('#f-story').value = draft.story_id;
  };
  fillStories();
  const fillEpisodes = async () => {
    const sid = $('#f-story').value;
    const eps = await api('/api/episodes' + (sid ? `?story_id=${sid}` : ''));
    $('#f-episode').innerHTML = eps.filter((e) => e.current_version).map((e) => `<option value="${e.id}">${esc(e.story_title)} — ép. ${e.number} : ${esc(e.title)}</option>`).join('') || '<option value="">Aucun épisode terminé</option>';
    await fillScenes();
  };
  const fillScenes = async () => {
    const id = $('#f-episode').value;
    $('#f-scene').innerHTML = '<option value="">Toutes / selon le texte</option>';
    if (!id) return;
    const ep = await api(`/api/episodes/${id}`);
    $('#f-scene').innerHTML += (ep.scenes || []).map((s) => `<option value="${s.n}">Scène ${s.n}</option>`).join('');
  };
  $('#f-project').addEventListener('change', () => { fillStories(); saveDraft(); interpret(); });
  $('#f-story').addEventListener('change', () => { saveDraft(); if (!$('#scene-row').hidden) fillEpisodes(); interpret(); });
  $('#f-episode').addEventListener('change', () => { fillScenes(); interpret(); });
  $('#f-scene').addEventListener('change', interpret);

  const params = (command) => ({
    command, text: $('#f-text').value.trim(), project_id: +$('#f-project').value || null, story_id: +$('#f-story').value || null,
    episode_id: !$('#scene-row').hidden ? (+$('#f-episode').value || null) : null,
    scene: !$('#scene-row').hidden && $('#f-scene').value ? +$('#f-scene').value : null,
    style: $('#f-style').value || null, duration: +$('#f-duration').value || null, format: segVal('f-format') || null,
    quality: segVal('f-quality') || null, subtitles: $('#f-subs').checked,
  });
  function saveDraft() {
    const p = params('auto');
    LS.set('draft', { text: p.text, style: p.style, duration: p.duration, format: p.format, quality: p.quality, project_id: p.project_id, story_id: p.story_id });
  }
  async function interpret(command) {
    clearTimeout(S.interpTimer);
    S.interpTimer = setTimeout(async () => {
      const p = params(command || S.mode || 'auto');
      const box = $('#interp');
      if (!p.text && !['continue', 'new_episode', 'regenerate_scene'].includes(p.command)) {
        box.innerHTML = '<h3>Ce que le moteur a compris</h3><p class="muted small">Commencez à écrire : l\'interprétation s\'affiche ici avant de lancer quoi que ce soit.</p>'; return;
      }
      try {
        const r = await api('/api/interpret', { method: 'POST', body: p });
        box.innerHTML = interpHtml(r);
        if (['edit_scene', 'regenerate_scene'].includes(r.command) && $('#scene-row').hidden) { $('#scene-row').hidden = false; fillEpisodes(); }
      } catch (err) { box.innerHTML = `<h3>Ce que le moteur a compris</h3><div class="notice">${esc(err.message)}</div>`; }
    }, 350);
  }
  $('#f-text').addEventListener('input', () => { saveDraft(); interpret(); });
  ['f-style', 'f-duration'].forEach((id) => $('#' + id).addEventListener('change', () => { saveDraft(); interpret(); }));
  $$('[data-ex]').forEach((b) => b.addEventListener('click', () => { $('#f-text').value = b.dataset.ex; saveDraft(); S.mode = 'auto'; interpret(); $('#f-text').focus(); }));

  async function launch(command) {
    const p = params(command);
    const btns = $$('#go, [data-cmd]'); btns.forEach((b) => (b.disabled = true));
    try {
      const r = await api('/api/produce', { method: 'POST', body: p });
      toast(`Production lancée : ${r.resolved.label}`, 'ok');
      if (r.resolved.warnings?.length) r.resolved.warnings.forEach((w) => toast(w));
      pollJobs();
    } catch (err) { toast(err.message, 'err'); } finally { btns.forEach((b) => (b.disabled = false)); }
  }
  $('#go').addEventListener('click', () => launch(S.mode && S.mode !== 'auto' ? S.mode : 'auto'));
  $$('[data-cmd]').forEach((b) => b.addEventListener('click', () => {
    const c = b.dataset.cmd;
    if (['edit_scene', 'regenerate_scene'].includes(c)) {
      S.mode = c; $('#scene-row').hidden = false; fillEpisodes(); interpret(c);
      $$('[data-cmd]').forEach((x) => x.classList.toggle('primary', x === b));
      toast(c === 'edit_scene' ? 'Choisissez l\'épisode et la scène, décrivez la modification, puis « Générer ».' : 'Choisissez la scène puis « Générer » pour une nouvelle prise.');
      return;
    }
    S.mode = 'auto'; $$('[data-cmd]').forEach((x) => x.classList.remove('primary'));
    launch(c);
  }));
  $('#save-project').addEventListener('click', async () => {
    const p = params('auto');
    const cur = projects.find((x) => x.id === p.project_id);
    const name = prompt('Nom du projet :', cur ? cur.name : (p.text.slice(0, 40) || 'Nouveau projet'));
    if (!name) return;
    try {
      const saved = await api('/api/projects', { method: 'POST', body: { id: cur?.id, name, draft: { text: p.text, style: p.style, duration: p.duration, format: p.format, quality: p.quality } } });
      toast(`Projet « ${saved.name} » enregistré.`, 'ok');
      LS.set('draft', { ...LS.get('draft', {}), project_id: saved.id });
      viewStudio();
    } catch (err) { toast(err.message, 'err'); }
  });
  loadQr();
  if ((draft.text || '').trim()) interpret();
  renderJobs($('#studio-jobs'), S.jobs.slice(-2).reverse(), false);
}

// ------------------------------------------------------------------ accès téléphone (QR code)
function phoneCardHtml() {
  const u = S.sys && S.sys.phone_url;
  if (!u || location.hostname.endsWith('.ts.net')) return '';
  return `<div class="card stack phone"><h3>Sur votre téléphone</h3>
    <div class="row" style="align-items:flex-start;flex-wrap:nowrap"><img id="qr" alt="QR code" width="128" height="128">
    <div class="small stack" style="gap:6px"><span>1. Installez l'app <b>Tailscale</b> sur le téléphone et connectez-vous avec le même compte.</span>
    <span>2. Scannez ce code avec l'appareil photo.</span><span class="mono" style="overflow-wrap:anywhere">${esc(u)}</span></div></div></div>`;
}
async function loadQr() {
  const img = $('#qr'); if (!img || !S.sys?.phone_url) return;
  try {
    const r = await fetch(S.api + '/api/qr?u=' + encodeURIComponent(S.sys.phone_url), { headers: { Authorization: 'Bearer ' + S.token } });
    if (r.ok) img.src = URL.createObjectURL(await r.blob());
  } catch { /* QR facultatif */ }
}

function interpHtml(r) {
  const p = r.parsed || {};
  const rows = [['Action', `<span class="tag accent">${esc(r.label)}</span>`]];
  if (['create', 'continue', 'new_episode'].includes(r.command)) {
    rows.push(['Durée visée', fmtDur(r.duration)], ['Format', r.format], ['Style', (S.sys?.options?.styles || {})[r.style] || r.style], ['Qualité', r.quality]);
    if (p.genre) rows.push(['Genre', p.genre]);
    if (p.set) rows.push(['Lieu', (S.sys?.options?.sets || {})[p.set] || p.set]);
    if (p.n_characters) rows.push(['Personnages', p.n_characters]);
    if (p.names?.length) rows.push(['Noms', p.names.join(', ')]);
    if (p.topic) rows.push(['Sujet', p.topic]);
    if (p.camera_dynamic) rows.push(['Caméra', 'dynamique']);
    if (r.story_title) rows.push(['Histoire', r.story_title]);
  }
  let extra = '';
  if (r.edit) {
    rows.push(['Scène(s)', r.edit.scenes.join(', ')]);
    extra += `<div class="stack small">${r.edit.understood.map((u) => `<div>✓ ${esc(u)}</div>`).join('')}</div>`;
    if (r.plan) {
      const redo = r.plan.scenes.filter((s) => !s.visual_cached).map((s) => s.n);
      const keep = r.plan.scenes.filter((s) => s.visual_cached).map((s) => s.n);
      extra += `<div class="plan">${redo.length ? `<span class="tag accent">À régénérer : ${redo.map((n) => 'scène ' + n).join(', ')}</span>` : '<span class="tag">Rien à régénérer</span>'}
        ${keep.length ? `<span class="tag ok">Réutilisé tel quel : ${keep.join(', ')}</span>` : ''}</div>`;
    }
  }
  return `<h3>Ce que le moteur a compris</h3><dl class="kv">${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${typeof v === 'string' && v.startsWith('<span') ? v : esc(v)}</dd>`).join('')}</dl>${extra}
    ${(r.warnings || []).map((w) => `<div class="notice">${esc(w)}</div>`).join('')}`;
}

// ------------------------------------------------------------------ PRODUCTION
async function viewProduction() {
  const all = await api('/api/jobs?limit=25');
  const active = all.filter((j) => ['queued', 'running', 'cancelling'].includes(j.status));
  const past = all.filter((j) => !['queued', 'running', 'cancelling'].includes(j.status));
  $('#view').innerHTML = `<div class="head"><div><h1>Suivi de production</h1><p class="muted">Progression réelle mesurée par le moteur (images écrites, temps encodé). Aucune estimation inventée.</p></div></div>
    <div id="jobs-active" class="stack"></div>
    <h2 style="margin:28px 0 12px">Historique</h2><div id="jobs-past" class="stack"></div>`;
  renderJobs($('#jobs-active'), active, true);
  $('#jobs-past').innerHTML = past.length ? past.map((j) => jobHtml(j, false)).join('') : '<div class="empty">Aucun historique.</div>';
}

// ------------------------------------------------------------------ BIBLIOTHÈQUE
async function viewLibrary(tab, sub) {
  const tabs = [['videos', 'Vidéos'], ['episodes', 'Épisodes'], ['histoires', 'Histoires'], ['personnages', 'Personnages'], ['scenes', 'Scènes'], ['projets', 'Projets']];
  const v = $('#view');
  v.innerHTML = `<div class="head"><div><h1>Bibliothèque</h1><p class="muted">Projets, histoires, personnages, épisodes et vidéos — tout est stocké sur votre ordinateur.</p></div></div>
    <nav class="tabs">${tabs.map(([k, l]) => `<a href="#/bibliotheque/${k}" class="${k === tab ? 'on' : ''}">${l}</a>`).join('')}</nav><div id="lib"></div>`;
  const el = $('#lib');
  if (tab === 'videos') {
    const st = sub || 'terminees';
    const subs = [['terminees', 'Terminées'], ['en_cours', 'En cours'], ['anciennes', 'Anciennes versions']];
    const rows = await api(`/api/library/videos?state=${st}`);
    el.innerHTML = `<div class="seg" style="max-width:460px;margin-bottom:16px">${subs.map(([k, l]) => `<button data-sub="${k}" class="${k === st ? 'on' : ''}">${l}</button>`).join('')}</div>
      <div id="vids"></div>`;
    $$('[data-sub]', el).forEach((b) => b.addEventListener('click', () => (location.hash = `#/bibliotheque/videos/${b.dataset.sub}`)));
    if (st === 'en_cours') { $('#vids').className = 'stack'; renderJobs($('#vids'), rows, true); return; }
    $('#vids').className = 'grid cards';
    $('#vids').innerHTML = rows.length ? rows.map((r) => `<a class="tile" href="#/episode/${r.episode_id}">
        <div class="thumb" style="background-image:url('${esc(mediaUrl(r.thumb_url))}')">${r.duration ? `<span class="dur">${fmtDur(r.duration)}</span>` : ''}</div>
        <div class="body"><span class="t">${esc(r.title)}</span><span class="small muted">${esc(r.story_title)} · ép. ${r.ep_number} · v${r.number}</span>
        <span class="small faint">${esc(r.note || '')}</span></div></a>`).join('') : '<div class="empty">Aucune vidéo ici pour l\'instant.</div>';
  } else if (tab === 'episodes') {
    const eps = await api('/api/episodes');
    el.innerHTML = eps.length ? `<div class="grid cards">${eps.map(epTile).join('')}</div>` : '<div class="empty">Aucun épisode.</div>';
  } else if (tab === 'histoires') {
    const ss = await api('/api/stories');
    el.innerHTML = ss.length ? `<div class="grid cards">${ss.map((s) => `<a class="tile" href="#/histoire/${s.id}"><div class="body">
      <span class="t">${esc(s.title)}</span><span class="small muted">${esc(s.project_name)} · ${s.n_episodes} épisode(s)</span>
      <span class="small faint">${esc((s.memory && s.memory.ending) || '')}</span></div></a>`).join('')}</div>` : '<div class="empty">Aucune histoire.</div>';
  } else if (tab === 'personnages') {
    const cs = await api('/api/characters');
    el.innerHTML = cs.length ? `<div class="grid cards">${cs.map(charTile).join('')}</div>` : '<div class="empty">Aucun personnage.</div>';
  } else if (tab === 'scenes') {
    const eps = (await api('/api/episodes')).filter((e) => e.current_version);
    el.innerHTML = eps.length ? `<label class="field" style="max-width:520px;margin-bottom:16px"><span>Épisode</span><select id="sc-ep">${eps.map((e) => `<option value="${e.id}">${esc(e.story_title)} — ép. ${e.number} : ${esc(e.title)}</option>`).join('')}</select></label><div id="sc-list" class="grid cards"></div>` : '<div class="empty">Aucune scène.</div>';
    const load = async () => {
      const ep = await api(`/api/episodes/${$('#sc-ep').value}`);
      $('#sc-list').innerHTML = (ep.scenes || []).map((s) => `<div class="tile">${s.clip_url ? `<video class="thumb" style="width:100%" preload="metadata" controls playsinline src="${esc(mediaUrl(s.clip_url))}"></video>` : '<div class="thumb">—</div>'}
        <div class="body"><span class="t">Scène ${s.n}</span><span class="small muted">${esc(s.summary)}</span>
        <a class="small" href="#/episode/${ep.id}">Modifier dans l'épisode →</a></div></div>`).join('');
    };
    if (eps.length) { $('#sc-ep').addEventListener('change', load); load(); }
  } else if (tab === 'projets') {
    const ps = await api('/api/projects');
    el.innerHTML = ps.length ? `<div class="grid cards">${ps.map((p) => `<div class="tile"><div class="body stack">
      <span class="t">${esc(p.name)}</span><span class="small muted">${p.n_stories} histoire(s) · ${p.n_episodes} épisode(s) · modifié ${fmtDate(p.updated)}</span>
      ${p.draft && p.draft.text ? `<span class="small faint">Brouillon : ${esc(p.draft.text.slice(0, 120))}</span>` : ''}
      <div class="row"><button class="btn small" data-open-project="${p.id}">Ouvrir dans le Studio</button>
        <button class="btn small ghost" data-backup="${p.id}">${ICON.dl}Sauvegarde</button>
        <button class="btn small ghost danger" data-del-project="${p.id}">Supprimer</button></div></div></div>`).join('')}</div>` : '<div class="empty">Aucun projet. Il est créé automatiquement à la première vidéo, ou via « Enregistrer le projet ».</div>';
    $$('[data-open-project]').forEach((b) => b.addEventListener('click', () => {
      const p = ps.find((x) => x.id === +b.dataset.openProject);
      LS.set('draft', { ...(p.draft || {}), project_id: p.id }); location.hash = '#/studio';
    }));
    $$('[data-backup]').forEach((b) => b.addEventListener('click', () => download(`/api/projects/${b.dataset.backup}/sauvegarde?videos=${confirm('Inclure les fichiers vidéo (plus volumineux) ?') ? 1 : 0}`)));
    $$('[data-del-project]').forEach((b) => b.addEventListener('click', async () => {
      if (!confirm('Supprimer définitivement ce projet, ses histoires, épisodes et vidéos ?')) return;
      await api(`/api/projects/${b.dataset.delProject}`, { method: 'DELETE' }); toast('Projet supprimé.'); viewLibrary('projets');
    }));
  }
}
const epTile = (e) => `<a class="tile" href="#/episode/${e.id}"><div class="thumb" style="background-image:url('${esc(mediaUrl(e.thumb_url))}')">${e.thumb_url ? '' : esc(STATUS[e.status] || e.status || '')}</div>
  <div class="body"><span class="t">${esc(e.title)}</span><span class="small muted">${esc(e.story_title)} · épisode ${e.number}${e.current_version ? ` · v${e.current_version}` : ''}</span></div></a>`;
const charTile = (c) => `<div class="tile"><div class="thumb portrait" style="background-image:url('${esc(mediaUrl(c.ref_url))}')">${c.ref_url ? '' : '…'}</div>
  <div class="body"><span class="t">${esc(c.name)}</span><span class="small muted">${esc(c.story_title || '')}${c.role ? ' · ' + esc(c.role) : ''}</span></div></div>`;

async function download(path) {
  try {
    const r = await fetch(S.api + path, { headers: { Authorization: 'Bearer ' + S.token } });
    if (!r.ok) throw new Error('Téléchargement impossible.');
    const blob = await r.blob();
    const name = (r.headers.get('content-disposition') || '').match(/filename="([^"]+)"/)?.[1] || 'sauvegarde.zip';
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
  } catch (err) { toast(err.message, 'err'); }
}

// ------------------------------------------------------------------ HISTOIRE
async function viewStory(id) {
  const s = await api(`/api/stories/${id}`);
  const mem = s.memory || {};
  $('#view').innerHTML = `<div class="head"><div><h1>${esc(s.title)}</h1><p class="muted">${esc(s.project_name)} · ${s.episodes.length} épisode(s) · ${esc(s.genre || '')}</p></div>
    <div class="row"><button class="btn primary" id="st-continue">${ICON.next}Continuer cette histoire</button><button class="btn" id="st-new">${ICON.ep}Nouvel épisode</button></div></div>
    <div class="grid two"><div class="stack">
      <div class="card stack"><h3>Épisodes</h3>${s.episodes.length ? `<div class="grid cards">${s.episodes.map(epTile).join('')}</div>` : '<div class="muted">Aucun.</div>'}</div>
      <div class="card stack"><h3>Personnages (références visuelles)</h3><div class="grid cards">${s.characters.map(charTile).join('')}</div></div>
    </div><div class="card stack"><h3>Mémoire de l'histoire</h3>
      <p class="small muted">Ce que le moteur retient pour enchaîner les épisodes. Vous pouvez la corriger.</p>
      <label class="field"><span>Résumé</span><textarea id="m-sum" rows="6">${esc(mem.summary || '')}</textarea></label>
      <label class="field"><span>Situation finale (point de départ de la suite)</span><textarea id="m-end" rows="3">${esc(mem.ending || '')}</textarea></label>
      <label class="field"><span>Faits importants (un par ligne)</span><textarea id="m-facts" rows="5">${esc((mem.facts || []).join('\n'))}</textarea></label>
      <button class="btn" id="m-save">${ICON.save}Enregistrer la mémoire</button></div></div>`;
  $('#m-save').addEventListener('click', async () => {
    await api(`/api/stories/${id}`, { method: 'PATCH', body: { memory: { ...mem, summary: $('#m-sum').value, ending: $('#m-end').value, facts: $('#m-facts').value.split('\n').map((x) => x.trim()).filter(Boolean) } } });
    toast('Mémoire enregistrée.', 'ok');
  });
  const go = async (command) => {
    const text = prompt(command === 'continue' ? 'Indication pour la suite (facultatif) :' : 'Thème du nouvel épisode :', '') ?? null;
    if (text === null) return;
    try { const r = await api('/api/produce', { method: 'POST', body: { command, story_id: id, text } }); toast(`Production lancée : ${r.resolved.label}`, 'ok'); location.hash = '#/production'; } catch (err) { toast(err.message, 'err'); }
  };
  $('#st-continue').addEventListener('click', () => go('continue'));
  $('#st-new').addEventListener('click', () => go('new_episode'));
}

// ------------------------------------------------------------------ ÉPISODE (lecteur + retouches)
async function viewEpisode(id, keepScroll) {
  S.episodeId = id;
  const e = await api(`/api/episodes/${id}`);
  const cur = e.versions.find((v) => v.number === e.current_version) || e.versions[0];
  const vertical = e.spec && e.spec.format === '9:16';
  const sel = S.selScene && S.selScene.ep === id ? S.selScene.n : null;
  const running = e.status === 'running';
  const y = window.scrollY;
  $('#view').innerHTML = `<div class="head"><div><h1>${esc(e.title)}</h1><p class="muted"><a href="#/histoire/${e.story_id}">${esc(e.story_title)}</a> · épisode ${e.number}
    ${cur ? ` · version ${cur.number} · ${esc(cur.format)} · ${esc(cur.quality)}` : ''}${cur?.result?.duration ? ` · ${fmtDur(cur.result.duration)}` : ''}</p></div>
    <div class="row">${cur?.download_url ? `<a class="btn primary" href="${esc(mediaUrl(cur.download_url))}">${ICON.dl}Télécharger MP4</a>` : ''}
    ${cur?.srt_url ? `<a class="btn ghost" href="${esc(mediaUrl(cur.srt_url))}" download>Sous-titres .srt</a>` : ''}</div></div>
  ${running ? '<div class="notice info" style="margin-bottom:16px">Une nouvelle version est en cours de production — <a href="#/production">suivre la progression</a>.</div>' : ''}
  <div class="grid two"><div class="stack">
    <div class="player ${vertical ? 'v916' : ''}">${cur?.video_url ? `<video controls playsinline preload="metadata" poster="${esc(mediaUrl(cur.thumb_url))}" src="${esc(mediaUrl(cur.video_url))}"></video>` : '<div class="empty" style="border:0">Pas encore de vidéo.</div>'}</div>
    ${cur?.result?.renderer ? `<div class="row small muted"><span class="tag">rendu : ${esc(cur.result.renderer)}</span><span class="tag">voix : ${esc(cur.result.tts)}</span>
      <span class="tag">scènes rendues : ${esc((cur.result.scenes_rendered || []).join(', ') || 'aucune')}</span>
      <span class="tag ok">réutilisées : ${esc((cur.result.scenes_reused || []).join(', ') || 'aucune')}</span>
      ${(cur.result.qc?.checks || []).filter((c) => !c.ok).map((c) => `<span class="tag err">${esc(c.name)} : ${esc(c.detail)}</span>`).join('')}</div>` : ''}
    <div class="card stack" id="edit-card">
      <div class="row between"><h2>Modifier</h2><select id="ed-scene" style="width:auto"><option value="">Toutes les scènes</option>
        ${(e.scenes || []).map((s) => `<option value="${s.n}" ${sel === s.n ? 'selected' : ''}>Scène ${s.n}</option>`).join('')}</select></div>
      <textarea id="ed-text" rows="3" placeholder="Ex. : La caméra doit se déplacer vers la gauche."></textarea>
      <div class="chips">${EDIT_EXAMPLES.map((x) => `<button class="chip" data-edex="${esc(x)}">${esc(x)}</button>`).join('')}</div>
      <div id="ed-plan" class="understood"></div>
      <div class="row between"><label class="check"><input type="checkbox" id="ed-rewrite"> Nouvelle prise : réécrire aussi le dialogue</label>
        <div class="row"><button class="btn" id="ed-regen">${ICON.redo}Régénérer la scène</button><button class="btn primary" id="ed-apply">${ICON.wand}Appliquer</button></div></div>
    </div>
  </div><div class="stack">
    <div class="card stack"><h3>Scènes</h3><div class="scenes">${(e.scenes || []).map((s) => `<div class="scene ${sel === s.n ? 'on' : ''}" data-scene="${s.n}">
      <div class="row between"><b>Scène ${s.n}</b><span class="row"><span class="tag">${esc((S.sys?.options?.sets || {})[s.set] || s.set)}</span><span class="tag">${esc(s.camera.move)}</span></span></div>
      <ul class="lines">${s.lines.map((l) => `<li><b>${esc((e.spec.characters.find((c) => c.id === l.who) || {}).name || '')}</b> : ${esc(l.text)}</li>`).join('')}</ul>
      ${s.clip_url ? `<video hidden controls playsinline preload="none" style="width:100%;margin-top:8px;border-radius:8px" src="${esc(mediaUrl(s.clip_url))}"></video>` : ''}</div>`).join('')}</div></div>
    <div class="card stack"><h3>Exporter</h3>
      <div class="row"><select id="ex-format" style="width:auto">${['9:16', '16:9', '1:1'].map((f) => `<option ${f === e.spec?.format ? 'disabled' : ''}>${f}</option>`).join('')}</select>
        <select id="ex-method" style="width:auto"><option value="flou">Fond flouté (rapide)</option><option value="recadrage">Recadrage (rapide)</option><option value="natif">Re-rendu natif (meilleur)</option></select>
        <button class="btn" id="ex-go">Exporter</button></div>
      <p class="small muted">« Re-rendu natif » recadre la caméra 3D pour le nouveau format et crée une nouvelle version (l'audio est réutilisé).</p>
      ${cur?.exports?.length ? `<div class="stack small">${cur.exports.map((x) => `<div class="row between"><span>${esc(x.name)}</span><a class="btn small" href="${esc(mediaUrl(x.download))}">${ICON.dl}MP4</a></div>`).join('')}</div>` : ''}</div>
    <div class="card stack"><h3>Versions</h3><div class="versions">${e.versions.map((v) => `<div class="version ${v.number === e.current_version ? 'cur' : ''}">
      <div><span class="n">v${v.number}</span> <span class="status ${esc(v.status)}">${STATUS[v.status] || esc(v.status)}</span><div class="small muted">${esc(v.note || '')}</div><div class="small faint">${fmtDate(v.created)}</div></div>
      <div class="row">${v.status === 'done' && v.number !== e.current_version ? `<button class="btn small" data-setv="${v.number}">Utiliser</button>` : ''}
      ${v.download_url ? `<a class="btn small ghost" href="${esc(mediaUrl(v.download_url))}">${ICON.dl}</a>` : ''}</div></div>`).join('')}</div>
      <button class="btn small ghost danger" id="ep-del">Supprimer l'épisode</button></div>
  </div></div>`;
  if (keepScroll) window.scrollTo(0, y);

  $$('[data-scene]').forEach((el) => el.addEventListener('click', (ev) => {
    if (ev.target.tagName === 'VIDEO') return;
    const n = +el.dataset.scene;
    S.selScene = { ep: id, n };
    $$('[data-scene]').forEach((x) => x.classList.toggle('on', x === el));
    $$('[data-scene] video').forEach((vd) => { vd.hidden = vd.parentElement !== el; if (vd.hidden) vd.pause(); });
    $('#ed-scene').value = n; planEdit();
  }));
  $$('[data-edex]').forEach((b) => b.addEventListener('click', () => { $('#ed-text').value = b.dataset.edex; planEdit(); }));
  $('#ed-text').addEventListener('input', planEdit);
  $('#ed-scene').addEventListener('change', planEdit);
  const body = (command) => ({ command, episode_id: id, scene: +$('#ed-scene').value || null, text: $('#ed-text').value.trim(), rewrite_dialogue: $('#ed-rewrite').checked });
  function planEdit() {
    clearTimeout(S.interpTimer);
    S.interpTimer = setTimeout(async () => {
      const b = body('edit_scene');
      if (!b.text) { $('#ed-plan').innerHTML = ''; return; }
      try { const r = await api('/api/interpret', { method: 'POST', body: b }); $('#ed-plan').innerHTML = interpHtml(r).replace('<h3>Ce que le moteur a compris</h3>', ''); }
      catch (err) { $('#ed-plan').innerHTML = `<div class="notice">${esc(err.message)}</div>`; }
    }, 300);
  }
  $('#ed-apply').addEventListener('click', async () => {
    try { await api('/api/produce', { method: 'POST', body: body('edit_scene') }); toast('Modification lancée : seules les parties concernées seront régénérées.', 'ok'); pollJobs(); viewEpisode(id, true); }
    catch (err) { toast(err.message, 'err'); }
  });
  $('#ed-regen').addEventListener('click', async () => {
    const b = body('regenerate_scene');
    if (!b.scene) { toast('Choisissez d\'abord une scène (liste à droite ou menu « Toutes les scènes »).', 'err'); return; }
    try { await api('/api/produce', { method: 'POST', body: b }); toast(`Nouvelle prise de la scène ${b.scene} lancée.`, 'ok'); pollJobs(); viewEpisode(id, true); }
    catch (err) { toast(err.message, 'err'); }
  });
  $('#ex-go').addEventListener('click', async () => {
    try { await api(`/api/episodes/${id}/export`, { method: 'POST', body: { format: $('#ex-format').value, method: $('#ex-method').value, version: e.current_version } }); toast('Export lancé.', 'ok'); pollJobs(); }
    catch (err) { toast(err.message, 'err'); }
  });
  $$('[data-setv]').forEach((b) => b.addEventListener('click', async () => { await api(`/api/episodes/${id}/current`, { method: 'POST', body: { version: +b.dataset.setv } }); viewEpisode(id, true); }));
  $('#ep-del').addEventListener('click', async () => {
    if (!confirm('Supprimer cet épisode et toutes ses versions ?')) return;
    await api(`/api/episodes/${id}`, { method: 'DELETE' }); toast('Épisode supprimé.'); location.hash = '#/bibliotheque/episodes';
  });
}

// ------------------------------------------------------------------ RÉGLAGES
async function viewSettings() {
  const [{ settings: s, allowed_origins: origins }, sys] = await Promise.all([api('/api/settings'), api('/api/system')]);
  S.sys = sys;
  const opt = (v, list) => list.map(([k, l]) => `<option value="${k}" ${k === v ? 'selected' : ''}>${esc(l)}</option>`).join('');
  $('#view').innerHTML = `<div class="head"><div><h1>Réglages</h1><p class="muted">Tout fonctionne en local : aucun service payant, aucune API Claude.</p></div></div>
  <div class="grid two"><div class="stack">
    <div class="card stack"><h2>Moteur de rendu</h2>
      <dl class="kv"><dt>Rendu actif</dt><dd>${sys.renderer === 'blender' ? `Blender — ${esc(sys.blender.version || '')}` : esc(sys.renderer === '2d' ? 'Aperçu 2D (Blender non détecté)' : sys.renderer)}</dd>
        <dt>FFmpeg</dt><dd>${sys.ffmpeg ? 'présent' : '<span class="tag err">absent — obligatoire</span>'}</dd>
        <dt>Voix</dt><dd>${esc(sys.tts_selected)} ${sys.tts.piper_models.length ? `(${sys.tts.piper_models.length} modèle(s) Piper)` : ''}</dd>
        <dt>Espace libre</dt><dd>${sys.disk_free_gb} Go</dd><dt>Données</dt><dd class="mono">${esc(sys.data_dir)}</dd></dl>
      <div class="opts" style="grid-template-columns:repeat(2,minmax(0,1fr))">
        <label class="field"><span>Moteur</span><select id="s-renderer">${opt(s.renderer, [['auto', 'Automatique'], ['blender', 'Blender (3D)'], ['2d', 'Aperçu 2D rapide']])}</select></label>
        <label class="field"><span>Chemin de Blender (facultatif)</span><input type="text" id="s-blender" value="${esc(s.blender_path)}" placeholder="détection automatique"></label>
        <label class="field"><span>Qualité par défaut</span><select id="s-quality">${opt(s.default_quality, [['brouillon', 'Brouillon (rapide)'], ['standard', 'Standard'], ['final', 'Final (1080p)']])}</select></label>
        <label class="field"><span>Format par défaut</span><select id="s-format">${opt(s.default_format, [['9:16', '9:16 vertical'], ['16:9', '16:9 horizontal'], ['1:1', '1:1 carré']])}</select></label>
        <label class="field"><span>Style par défaut</span><select id="s-style">${opt(s.default_style, Object.entries(sys.options.styles))}</select></label>
        <label class="field"><span>Durée par défaut (s)</span><input type="number" id="s-duration" min="5" max="600" value="${esc(s.default_duration)}"></label>
      </div>
      <label class="check"><input type="checkbox" id="s-subs" ${s.subtitles ? 'checked' : ''}> Sous-titres incrustés par défaut</label>
      <label class="check"><input type="checkbox" id="s-music" ${s.music ? 'checked' : ''}> Musique de fond (fichiers du dossier <span class="mono">donnees/musique</span>)</label>
      <label class="check"><input type="checkbox" id="s-blend" ${s.keep_blend ? 'checked' : ''}> Conserver les fichiers sources Blender (.blend) de chaque scène</label>
    </div>
    <div class="card stack"><h2>Voix (synthèse vocale open source)</h2>
      <label class="field"><span>Moteur de voix</span><select id="s-tts">${opt(s.tts_engine, [['auto', 'Automatique (Piper > espeak-ng)'], ['piper', 'Piper (naturel)'], ['espeak-ng', 'espeak-ng (léger)'], ['silence', 'Sans voix']])}</select></label>
      <p class="small muted">Piper : déposez des voix françaises (.onnx + .onnx.json) dans <span class="mono">donnees/voix</span>, ou lancez <span class="mono">python scripts/telecharger_voix.py</span>.</p>
    </div>
    <div class="card stack"><h2>Modèle de langage local</h2>
      <p class="small muted">Écrit les scénarios et interprète les retouches complexes. Sans modèle, le générateur intégré prend le relais.</p>
      <div class="opts" style="grid-template-columns:repeat(2,minmax(0,1fr))">
        <label class="field"><span>Fournisseur</span><select id="s-llm">${opt(s.llm_provider, [['regles', 'Aucun (générateur intégré)'], ['ollama', 'Ollama (local)'], ['openai_local', 'Serveur local compatible OpenAI']])}</select></label>
        <label class="field"><span>Adresse (locale)</span><input type="text" id="s-llm-url" value="${esc(s.llm_url)}" placeholder="http://127.0.0.1:11434"></label>
        <label class="field"><span>Modèle</span><input type="text" id="s-llm-model" list="llm-models" value="${esc(s.llm_model)}"><datalist id="llm-models">${sys.llm.suggested.map((m) => `<option value="${esc(m)}">`).join('')}</datalist></label>
        <div class="field"><span>&nbsp;</span><button class="btn" id="s-llm-test">Lister les modèles installés</button></div>
      </div>
      <div id="llm-res" class="small muted"></div>
    </div>
    <button class="btn primary big" id="s-save">${ICON.save}Enregistrer les réglages</button>
  </div><div class="stack">
    <div class="card stack"><h2>Connexion</h2>
      <dl class="kv"><dt>Moteur</dt><dd class="mono">${esc(S.api || location.origin)}</dd></dl>
      ${ON_PAGES ? '<button class="btn" id="s-api">Changer d\'adresse du moteur</button>' : ''}
      <button class="btn ghost" id="s-logout">Se déconnecter</button></div>
    <div class="card stack"><h2>Mot de passe</h2>
      <input type="password" id="pw-old" placeholder="Mot de passe actuel" autocomplete="current-password">
      <input type="password" id="pw-new" placeholder="Nouveau (10 caractères min.)" autocomplete="new-password">
      <button class="btn" id="pw-go">Changer (déconnecte les autres appareils)</button></div>
    <div class="card stack"><h2>Origines autorisées</h2>
      <p class="small muted">Sites autorisés à appeler votre moteur (ex. votre page GitHub Pages). Une par ligne, en https.</p>
      <textarea id="s-origins" rows="3" class="mono">${esc(origins.join('\n'))}</textarea></div>
    ${phoneCardHtml() || `<div class="card stack"><h2>Sur votre téléphone</h2><p class="small muted">${location.hostname.endsWith('.ts.net') ? 'Vous utilisez déjà l\'accès téléphone.' : 'Tailscale n\'est pas connecté sur ce PC : relancez l\'installateur (étape 7) pour obtenir l\'adresse du téléphone.'}</p></div>`}
    <div class="card stack"><h2>Accès à distance</h2><p class="small muted">Pour utiliser le studio depuis votre téléphone hors de chez vous : Tailscale (recommandé, gratuit, privé) ou Cloudflare Tunnel.
      Voir <span class="mono">studio/docs/ACCES_DISTANT.md</span>. Ordinateur éteint : mode « cloud » via GitHub Actions (voir la documentation).</p></div>
  </div></div>`;
  loadQr();
  $('#s-llm-test').addEventListener('click', async () => {
    const r = await api(`/api/llm/models?provider=${encodeURIComponent($('#s-llm').value)}&url=${encodeURIComponent($('#s-llm-url').value)}`);
    $('#llm-res').innerHTML = r.ok ? (r.models.length ? 'Installés : ' + r.models.map((m) => `<button class="chip" data-m="${esc(m)}">${esc(m)}</button>`).join(' ') : esc(r.note || 'Aucun modèle installé (ex. : ollama pull qwen2.5:7b-instruct).')) : `<span class="error">${esc(r.error)}</span>`;
    $$('[data-m]').forEach((b) => b.addEventListener('click', () => ($('#s-llm-model').value = b.dataset.m)));
  });
  $('#s-save').addEventListener('click', async () => {
    try {
      await api('/api/settings', { method: 'PUT', body: { settings: {
        renderer: $('#s-renderer').value, blender_path: $('#s-blender').value.trim(), default_quality: $('#s-quality').value, default_format: $('#s-format').value,
        default_style: $('#s-style').value, default_duration: +$('#s-duration').value || 30, subtitles: $('#s-subs').checked, music: $('#s-music').checked,
        keep_blend: $('#s-blend').checked, tts_engine: $('#s-tts').value, llm_provider: $('#s-llm').value, llm_url: $('#s-llm-url').value.trim(), llm_model: $('#s-llm-model').value.trim(),
      }, allowed_origins: $('#s-origins').value.split('\n').map((x) => x.trim()).filter(Boolean) } });
      S.sys = await api('/api/system'); toast('Réglages enregistrés.', 'ok'); viewSettings();
    } catch (err) { toast(err.message, 'err'); }
  });
  $('#s-logout').addEventListener('click', logout);
  $('#s-api')?.addEventListener('click', () => { LS.del('api'); S.api = ''; logout(); });
  $('#pw-go').addEventListener('click', async () => {
    try { const r = await api('/api/auth/password', { method: 'POST', body: { old: $('#pw-old').value, new: $('#pw-new').value } }); S.token = r.token; LS.set('token', r.token); toast('Mot de passe changé.', 'ok'); $('#pw-old').value = $('#pw-new').value = ''; }
    catch (err) { toast(err.message, 'err'); }
  });
}

start();
