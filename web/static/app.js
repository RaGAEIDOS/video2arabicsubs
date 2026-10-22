'use strict';

/* ════════════════════════════════════════════════════════════════════
   Video2ArabicSubs — frontend
   Upload → live SSE progress → Arabic subtitle editor → downloads
   ════════════════════════════════════════════════════════════════════ */

/* ── i18n ─────────────────────────────────────────────────────────── */
const I18N = {
  ar: {
    tagline: 'حوّل أي فيديو إلى ترجمة عربية بسهولة',
    'upload.title': 'رفع الفيديو',
    'upload.tabFile': 'ملف',
    'upload.tabUrl': 'رابط',
    'upload.drop': 'اسحب وأفلت الفيديو هنا',
    'upload.dropSub': 'أو انقر للاختيار — MP4 · MKV · AVI · MOV · WebM · …',
    'upload.max': 'الحد الأقصى للحجم',
    'upload.urlHint': 'يتطلب تثبيت yt-dlp على الخادم.',
    'opt.title': 'خيارات المعالجة',
    'opt.model': 'نموذج Whisper',
    'opt.lang': 'لغة الفيديو',
    'opt.langHint': '«تلقائي» يكتشف Whisper لغة الكلام تلقائياً.',
    'opt.engine': 'محرك الترجمة',
    'opt.engineGoogle': 'Google (عبر الإنترنت)',
    'opt.engineNone': 'بدون — الفيديو عربي أصلاً',
    'opt.format': 'صيغة الملف',
    'opt.fmtBoth': 'SRT + VTT',
    'opt.burn': 'حرق الترجمة داخل نسخة من الفيديو',
    'opt.burnBadge': 'FFmpeg',
    'opt.burnUnavailable': 'الحرق غير متاح',
    'opt.bom': 'كتابة الملفات بترميز UTF-8 مع BOM (توافق Windows)',
    'opt.auto': 'تلقائي (اكتشاف)',
    'btn.start': '▶ ابدأ الترجمة',
    'btn.startHint': 'اختر ملفاً أولاً',
    'btn.startHintUrl': 'أدخل رابط الفيديو أولاً',
    'btn.cancel': '⏹ إيقاف',
    'btn.new': '✦ مهمة جديدة',
    'btn.retry': '↻ إعادة المحاولة (استئناف)',
    'toast.retrying': 'أُعيدت المحاولة — جارٍ الاستئناف من آخر نقطة محفوظة',
    'job.title': 'حالة المعالجة',
    'log.title': 'سجل التشغيل',
    'log.clear': 'مسح',
    'idle.title': 'جاهز للترجمة',
    'idle.sub': 'ارفع فيديو، اختر الخيارات، ثم اضغط «ابدأ الترجمة». سيظهر التقدم هنا مباشرة.',
    'result.title': 'معاينة وتحرير الترجمة',
    'player.hint': 'الترجمة العربية تظهر مباشرة داخل المشغل — استخدم زر CC أسفله عند الحاجة.',
    'dl.bom': 'تحميل مع BOM',
    'dl.srt': '⬇ SRT',
    'dl.vtt': '⬇ VTT',
    'dl.video': '⬇ الفيديو المُحروق',
    'gh.title': 'رفع النتائج إلى GitHub',
    'gh.sub': 'ارفع ملفات الترجمة (والفيديو المُحروق) إلى أي مستودع GitHub لديك صلاحية الكتابة فيه — يتم الرفع من خادمك المحلي في التزام واحد.',
    'gh.repo': 'المستودع',
    'gh.repoPh': 'owner/repo',
    'gh.branch': 'الفرع',
    'gh.branchPh': 'main',
    'gh.folder': 'المجلد داخل المستودع',
    'gh.folderPh': 'subtitles (اختياري)',
    'gh.token': 'رمز الوصول الشخصي (PAT)',
    'gh.tokenPh': 'ghp_… (اتركه فارغاً إذا ضُبط GITHUB_TOKEN)',
    'gh.message': 'رسالة الالتزام (اختياري)',
    'gh.messagePh': 'إضافة ترجمة عربية للفيديو',
    'gh.files': 'الملفات المُرفوعة',
    'gh.push': '⬆ رفع إلى GitHub',
    'gh.pushing': 'جاري الرفع إلى GitHub…',
    'gh.done': '✓ تم الرفع',
    'gh.failed': 'فشل الرفع',
    'gh.openCommit': 'فتح الالتزام ↗',
    'gh.noFiles': 'اختر ملفاً واحداً على الأقل',
    'gh.badRepo': 'اكتب اسم المستودع بالشكل owner/repo',
    'gh.tokenEnv': 'ضُبط GITHUB_TOKEN على الخادم — يمكنك ترك خانة الرمز فارغة.',
    'gh.tokenPat': 'يحتاج رمز PAT بصلاحية «Contents: Read and write» — الرمز يُرسل إلى خادمك المحلي فقط ولا يُخزَّن في المتصفح.',
    'editor.count': 'عدد الأسطر',
    'editor.add': '＋ سطر',
    'editor.save': '💾 حفظ التعديلات',
    'editor.col.index': '#',
    'editor.col.start': 'البداية',
    'editor.col.end': 'النهاية',
    'editor.col.text': 'النص العربي',
    'editor.newText': 'نص جديد',
    'editor.saved': '✓ تم الحفظ',
    'editor.dirty': 'تعديلات غير محفوظة…',
    uploading: 'جاري رفع الملف…',
    'err.fileType': 'نوع الملف غير مدعوم',
    'err.fileSize': 'حجم الملف يتجاوز الحد المسموح',
    'err.noFile': 'اختر ملفاً أولاً',
    'err.noUrl': 'أدخل رابط فيديو صالحاً أولاً',
    'err.generic': 'حدث خطأ',
    'err.invalidTime': 'صيغة وقت غير صحيحة في السطر',
    'err.emptyCues': 'الترجمة فارغة — أضف سطراً واحداً على الأقل',
    'warn.emptySkipped': 'سيتم تجاهل {n} سطر فارغ',
    'toast.queued': 'بدأت المعالجة — تابع التقدم ↙',
    'toast.saved': 'تم حفظ التعديلات بنجاح',
    'toast.cancelling': 'جاري الإيقاف…',
    'toast.cancelled': 'تم إلغاء المهمة',
    'toast.error': 'فشلت المعالجة',
    'toast.offline': 'تعذر الاتصال بالخادم',
    'stage.uploading': 'رفع الملف',
  },
  en: {
    tagline: 'Turn any video into Arabic subtitles in one click',
    'upload.title': 'Upload video',
    'upload.tabFile': 'File',
    'upload.tabUrl': 'URL',
    'upload.drop': 'Drag & drop your video here',
    'upload.dropSub': 'or click to browse — MP4 · MKV · AVI · MOV · WebM · …',
    'upload.max': 'Max size',
    'upload.urlHint': 'Requires yt-dlp installed on the server.',
    'opt.title': 'Processing options',
    'opt.model': 'Whisper model',
    'opt.lang': 'Source language',
    'opt.langHint': '"Auto" lets Whisper detect the spoken language.',
    'opt.engine': 'Translation engine',
    'opt.engineGoogle': 'Google (online)',
    'opt.engineNone': 'None — video is already Arabic',
    'opt.format': 'Output format',
    'opt.fmtBoth': 'SRT + VTT',
    'opt.burn': 'Burn subtitles into a copy of the video',
    'opt.burnBadge': 'FFmpeg',
    'opt.burnUnavailable': 'Burn-in unavailable',
    'opt.bom': 'Write files as UTF-8 with BOM (Windows players)',
    'opt.auto': 'Auto-detect',
    'btn.start': '▶ Start',
    'btn.startHint': 'Choose a file first',
    'btn.startHintUrl': 'Enter a video URL first',
    'btn.cancel': '⏹ Cancel',
    'btn.new': '✦ New job',
    'btn.retry': '↻ Retry (resume)',
    'toast.retrying': 'Retrying — resuming from the last saved point',
    'job.title': 'Processing status',
    'log.title': 'Log',
    'log.clear': 'Clear',
    'idle.title': 'Ready to translate',
    'idle.sub': 'Upload a video, pick the options, then hit "Start". Progress shows up here live.',
    'result.title': 'Preview & edit subtitles',
    'player.hint': 'Arabic subtitles render natively in the player — use the CC button if needed.',
    'dl.bom': 'Download with BOM',
    'dl.srt': '⬇ SRT',
    'dl.vtt': '⬇ VTT',
    'dl.video': '⬇ Burned video',
    'gh.title': 'Push results to GitHub',
    'gh.sub': 'Upload the subtitle files (and the burned video) to any GitHub repo you can write to — pushed from your local server in a single commit.',
    'gh.repo': 'Repository',
    'gh.repoPh': 'owner/repo',
    'gh.branch': 'Branch',
    'gh.branchPh': 'main',
    'gh.folder': 'Folder inside the repo',
    'gh.folderPh': 'subtitles (optional)',
    'gh.token': 'Personal access token (PAT)',
    'gh.tokenPh': 'ghp_… (leave empty if GITHUB_TOKEN is set)',
    'gh.message': 'Commit message (optional)',
    'gh.messagePh': 'Add Arabic subtitles for the video',
    'gh.files': 'Files',
    'gh.push': '⬆ Push to GitHub',
    'gh.pushing': 'Pushing to GitHub…',
    'gh.done': '✓ Pushed',
    'gh.failed': 'Push failed',
    'gh.openCommit': 'Open commit ↗',
    'gh.noFiles': 'Choose at least one file',
    'gh.badRepo': "Enter the repository as owner/repo",
    'gh.tokenEnv': 'GITHUB_TOKEN is set on the server — the token field can stay empty.',
    'gh.tokenPat': 'Needs a PAT with "Contents: Read and write" — the token is sent only to your local server and never stored in the browser.',
    'editor.count': 'Cues',
    'editor.add': '＋ Add cue',
    'editor.save': '💾 Save edits',
    'editor.col.index': '#',
    'editor.col.start': 'Start',
    'editor.col.end': 'End',
    'editor.col.text': 'Arabic text',
    'editor.newText': 'New text',
    'editor.saved': '✓ Saved',
    'editor.dirty': 'Unsaved changes…',
    uploading: 'Uploading file…',
    'err.fileType': 'Unsupported file type',
    'err.fileSize': 'File exceeds the size limit',
    'err.noFile': 'Choose a file first',
    'err.noUrl': 'Enter a valid video URL first',
    'err.generic': 'Something went wrong',
    'err.invalidTime': 'Invalid timestamp format in a cue',
    'err.emptyCues': 'Subtitle list is empty — add at least one cue',
    'warn.emptySkipped': '{n} empty cue(s) will be skipped',
    'toast.queued': 'Processing started — watch the progress ↙',
    'toast.saved': 'Edits saved',
    'toast.cancelling': 'Cancelling…',
    'toast.cancelled': 'Job cancelled',
    'toast.error': 'Processing failed',
    'toast.offline': 'Cannot reach the server',
    'stage.uploading': 'Uploading file',
  },
};

const STAGE_LABELS = {
  queued:        { ar: 'في الانتظار',        en: 'Queued' },
  uploading:     { ar: 'رفع الملف',          en: 'Uploading' },
  downloading:   { ar: 'تنزيل الفيديو',      en: 'Downloading video' },
  extracting:    { ar: 'استخراج الصوت',      en: 'Extracting audio' },
  transcribing:  { ar: 'تحويل الكلام إلى نص', en: 'Transcribing speech' },
  translating:   { ar: 'الترجمة إلى العربية', en: 'Translating to Arabic' },
  generating:    { ar: 'إنشاء ملف الترجمة',   en: 'Generating subtitles' },
  burning:       { ar: 'حرق الترجمة في الفيديو', en: 'Burning subtitles' },
  done:          { ar: 'اكتمل ✔',            en: 'Done ✔' },
  error:         { ar: 'فشل ✕',              en: 'Failed ✕' },
  cancelled:     { ar: 'أُلغيت',             en: 'Cancelled' },
};

const MODEL_HINTS = {
  ar: {
    tiny: 'الأسرع — دقة أقل',
    base: 'سريع',
    small: 'موصى به — توازن دقة/سرعة',
    medium: 'أدق — أبطأ',
    large: 'الأدق — ثقيل جداً',
    turbo: 'سريع ودقيق (أحدث نموذج)',
  },
  en: {
    tiny: 'fastest — least accurate',
    base: 'fast',
    small: 'recommended — balanced',
    medium: 'more accurate, slower',
    large: 'most accurate — heavy',
    turbo: 'fast + accurate (newest)',
  },
};

const TERMINAL = new Set(['done', 'error', 'cancelled']);

/* ── state ────────────────────────────────────────────────────────── */
const state = {
  lang: localStorage.getItem('v2a_lang') || 'ar',
  health: null,
  file: null,
  source: 'file',
  jobId: null,
  job: null,
  cues: [],
  es: null,
  esClosed: false,
  stageOrder: [],
  uploading: false,
  trackEl: null,
  trackURL: null,
  editorLoaded: false,
  cueDirty: false,
  previewTimer: null,
  ghFiles: new Set(['srt', 'vtt']),
};

/* ── tiny helpers ─────────────────────────────────────────────────── */
const $ = (id) => document.getElementById(id);
const t = (key) => I18N[state.lang][key] ?? I18N.en[key] ?? key;
const TERMINAL_STAGES = TERMINAL;

function stageLabel(stage) {
  const entry = STAGE_LABELS[stage];
  return entry ? entry[state.lang] : stage;
}

function pad(n) { return String(n).padStart(2, '0'); }

function fmtTs(sec) {
  let ms = Math.max(0, Math.round(Number(sec) * 1000));
  const millis = ms % 1000;
  let total = Math.floor(ms / 1000);
  const s = total % 60;
  total = Math.floor(total / 60);
  const m = total % 60;
  const h = Math.floor(total / 60);
  return `${pad(h)}:${pad(m)}:${pad(s)},${String(millis).padStart(3, '0')}`;
}

function parseTs(raw) {
  const s = String(raw).trim().replace('.', ',');
  const m = /^(?:(\d{1,2}):)?(\d{1,2}):(\d{2}),(\d{1,3})$/.exec(s);
  if (!m) return null;
  const h = Number(m[1] || 0);
  const mi = Number(m[2]);
  const se = Number(m[3]);
  if (mi > 59 || se > 59) return null;
  return h * 3600 + mi * 60 + se + Number(m[4].padEnd(3, '0')) / 1000;
}

function fmtBytes(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function toast(message, kind = 'info', ms = 4200) {
  const box = $('toasts');
  const node = document.createElement('div');
  node.className = `toast ${kind}`;
  node.textContent = message;
  box.appendChild(node);
  setTimeout(() => {
    node.style.opacity = '0';
    node.style.transition = 'opacity .3s';
    setTimeout(() => node.remove(), 320);
  }, ms);
}

async function fetchJSON(url, opts) {
  let res;
  try {
    res = await fetch(url, opts);
  } catch (err) {
    throw new Error(t('toast.offline'));
  }
  let data = null;
  try { data = await res.json(); } catch (_) { /* empty body */ }
  if (!res.ok) {
    const detail = data && data.detail;
    let msg;
    if (typeof detail === 'string') msg = detail;
    else if (Array.isArray(detail)) msg = detail.map((d) => d.msg || JSON.stringify(d)).join('; ');
    else msg = `HTTP ${res.status}`;
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return data;
}

function postForm(url, fd, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);
    xhr.upload.onprogress = (e) => { if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total); };
    xhr.onload = () => {
      let data = null;
      try { data = JSON.parse(xhr.responseText); } catch (_) { /* noop */ }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data);
      } else {
        const detail = data && data.detail;
        let msg;
        if (typeof detail === 'string') msg = detail;
        else if (Array.isArray(detail)) msg = detail.map((d) => d.msg || JSON.stringify(d)).join('; ');
        else msg = `HTTP ${xhr.status}`;
        reject(new Error(msg));
      }
    };
    xhr.onerror = () => reject(new Error(t('toast.offline')));
    xhr.send(fd);
  });
}

/* ── i18n application ─────────────────────────────────────────────── */
function applyI18n() {
  const html = document.documentElement;
  html.lang = state.lang === 'ar' ? 'ar' : 'en';
  html.dir = state.lang === 'ar' ? 'rtl' : 'ltr';
  $('langToggle').textContent = state.lang === 'ar' ? 'EN' : 'عربي';
  document.querySelectorAll('[data-i18n]').forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll('[data-i18n-ph]').forEach((node) => {
    node.placeholder = t(node.dataset.i18nPh);
  });
  if (state.health) populateOptions();
  renderStepper();
  renderStageLabel();
  renderDownloadBar();
  renderGhFiles();
  renderGhHint();
  updateStartHint();
}

/* ── health + options UI ──────────────────────────────────────────── */
function populateOptions() {
  const h = state.health;
  const modelSel = $('optModel');
  const current = modelSel.value || h.defaults.model_size;
  modelSel.innerHTML = '';
  h.models.forEach((size) => {
    const opt = document.createElement('option');
    opt.value = size;
    const hint = (MODEL_HINTS[state.lang] || MODEL_HINTS.en)[size] || '';
    opt.textContent = hint ? `${size} — ${hint}` : size;
    modelSel.appendChild(opt);
  });
  modelSel.value = h.models.includes(current) ? current : h.defaults.model_size;
  $('optModelHint').textContent = '';

  const langSel = $('optLang');
  const curLang = langSel.value || h.defaults.source_language;
  langSel.innerHTML = '';
  const auto = document.createElement('option');
  auto.value = 'auto';
  auto.textContent = t('opt.auto');
  langSel.appendChild(auto);
  Object.entries(h.languages).forEach(([code, name]) => {
    if (code === 'auto') return;
    const opt = document.createElement('option');
    opt.value = code;
    opt.textContent = `${name} (${code})`;
    langSel.appendChild(opt);
  });
  langSel.value = curLang && langSel.querySelector(`option[value="${curLang}"]`) ? curLang : 'auto';

  $('maxSizeLabel').textContent = `${h.max_upload_mb} MB`;

  if (!h.url_support) $('tabUrl').classList.add('hidden');
  if (state.source === 'url' && !h.url_support) switchSource('file');

  const burnBox = $('optBurn');
  const burnHint = $('burnHint');
  if (h.burn && h.burn.available) {
    burnBox.disabled = false;
    burnHint.classList.add('hidden');
  } else {
    burnBox.disabled = true;
    burnBox.checked = false;
    burnHint.textContent = `${t('opt.burnUnavailable')}: ${(h.burn && h.burn.reason) || 'FFmpeg'}`;
    burnHint.classList.remove('hidden');
  }
}

/* ── source tabs + file selection ─────────────────────────────────── */
function switchSource(src) {
  state.source = src;
  $('tabFile').classList.toggle('tab-active', src === 'file');
  $('tabUrl').classList.toggle('tab-active', src === 'url');
  $('dropZone').classList.toggle('hidden', src === 'url');
  $('urlBox').classList.toggle('hidden', src !== 'url');
  updateStartHint();
}

function allowedExtensions() {
  const h = state.health;
  return [...h.video_extensions, ...h.audio_extensions].map((e) => e.toLowerCase());
}

function selectFile(file) {
  if (!file || !state.health) return;
  const zone = $('dropZone');
  const ext = ('.' + (file.name.split('.').pop() || '')).toLowerCase();
  const okType = allowedExtensions().includes(ext) || file.type.startsWith('video/') || file.type.startsWith('audio/');
  const okSize = file.size <= state.health.max_upload_mb * 1024 * 1024;
  if (!okType) {
    zone.classList.add('invalid');
    setTimeout(() => zone.classList.remove('invalid'), 400);
    toast(`${t('err.fileType')}: ${ext}`, 'error');
    return;
  }
  if (!okSize) {
    zone.classList.add('invalid');
    setTimeout(() => zone.classList.remove('invalid'), 400);
    toast(`${t('err.fileSize')} (${state.health.max_upload_mb} MB)`, 'error');
    return;
  }
  state.file = file;
  $('fileChipName').textContent = file.name;
  $('fileChipSize').textContent = fmtBytes(file.size);
  $('fileChip').classList.remove('hidden');
  updateStartHint();
}

function clearFile() {
  state.file = null;
  $('fileInput').value = '';
  $('fileChip').classList.add('hidden');
  updateStartHint();
}

function updateStartHint() {
  const btn = $('startBtn');
  const hint = $('startHint');
  let ready = false;
  if (state.source === 'file') {
    ready = Boolean(state.file);
    hint.textContent = ready ? '' : t('btn.startHint');
  } else {
    ready = $('urlInput').value.trim().length > 8;
    hint.textContent = ready ? '' : t('btn.startHintUrl');
  }
  const jobActive = Boolean(state.jobId && state.job && !TERMINAL.has(state.job.stage));
  btn.disabled = !ready || state.uploading || jobActive;
}

/* ── job submission ───────────────────────────────────────────────── */
function collectOptions() {
  return {
    model_size: $('optModel').value,
    source_language: $('optLang').value,
    engine: $('optEngine').value,
    output_format: $('optFormat').value,
    burn_video: $('optBurn').checked,
    add_bom: $('optBom').checked,
  };
}

function computeStageOrder(opts, source) {
  const order = [];
  if (source === 'url') order.push('downloading');
  order.push('extracting', 'transcribing', 'translating', 'generating');
  if (opts.burn_video) order.push('burning');
  order.push('done');
  return order;
}

async function startJob() {
  if (state.uploading) return;
  const opts = collectOptions();
  const fd = new FormData();
  let endpoint;

  if (state.source === 'file') {
    if (!state.file) { toast(t('err.noFile'), 'error'); return; }
    endpoint = '/api/upload';
    fd.append('file', state.file);
  } else {
    const url = $('urlInput').value.trim();
    if (url.length < 9) { toast(t('err.noUrl'), 'error'); return; }
    endpoint = '/api/url';
    fd.append('url', url);
  }
  Object.entries(opts).forEach(([k, v]) => fd.append(k, String(v)));

  state.uploading = true;
  updateStartHint();
  $('idleCard').classList.add('hidden');
  $('jobCard').classList.remove('hidden');
  $('cancelBtn').classList.add('hidden');
  $('newJobBtn').classList.add('hidden');
  $('errorBox').classList.add('hidden');
  $('retryBtn').classList.add('hidden');
  $('resultSection').classList.add('hidden');
  $('logBox').innerHTML = '';
  $('jobFile').textContent = state.source === 'file' ? state.file.name : $('urlInput').value.trim();
  state.stageOrder = computeStageOrder(opts, state.source);
  state.job = {
    stage: 'uploading', percent: 0, stage_percent: null, error: null,
    options: opts, source: state.source, has_subtitles: false, files: [],
  };
  renderStepper();
  setProgress(0, 'uploading');

  try {
    const data = await postForm(endpoint, fd, (fraction) => {
      setProgress(fraction * 100, 'uploading');
      $('percentLabel').textContent = `${Math.round(fraction * 100)}%`;
    });
    state.uploading = false;
    connectJob(data.job_id, opts, state.source);
    toast(t('toast.queued'), 'success');
  } catch (err) {
    state.uploading = false;
    toast(`${t('toast.error')}: ${err.message}`, 'error', 7000);
    $('jobCard').classList.add('hidden');
    $('idleCard').classList.remove('hidden');
    updateStartHint();
  }
}

function connectJob(jobId, opts, source) {
  state.jobId = jobId;
  state.stageOrder = computeStageOrder(opts, source);
  state.editorLoaded = false;
  state.cues = [];
  localStorage.setItem('v2a_job', jobId);
  $('cancelBtn').classList.remove('hidden');
  $('newJobBtn').classList.add('hidden');
  openSSE();
}

/* ── SSE progress ─────────────────────────────────────────────────── */
function openSSE() {
  if (state.es) { state.es.close(); state.es = null; }
  state.esClosed = false;
  const es = new EventSource(`/api/events/${state.jobId}`);
  state.es = es;
  es.onmessage = (msg) => {
    let data;
    try { data = JSON.parse(msg.data); } catch (_) { return; }
    handleEvent(data);
  };
  es.onerror = () => {
    if (state.esClosed) es.close();
    /* otherwise EventSource retries automatically */
  };
}

function handleEvent(ev) {
  if (!ev || !ev.type) return;
  if (ev.type === 'snapshot') {
    state.job = ev;
    if (state.job.options) {
      state.stageOrder = computeStageOrder(state.job.options, state.job.source);
    }
    renderJob();
    if (state.job.stage === 'done' && state.job.has_subtitles) loadEditor();
    if (TERMINAL.has(state.job.stage)) onTerminal();
  } else if (ev.type === 'progress') {
    if (!state.job) state.job = {};
    const stageChanged = state.job.stage !== ev.stage;
    state.job.stage = ev.stage;
    state.job.percent = ev.percent;
    state.job.stage_percent = ev.stage_percent;
    if (ev.message) state.job.message = ev.message;
    renderJob();
    if (stageChanged) renderStepper();
  } else if (ev.type === 'log') {
    appendLog(ev.text);
  } else if (ev.type === 'end') {
    if (!state.job) state.job = {};
    state.job.stage = ev.stage;
    state.job.percent = ev.percent;
    state.job.error = ev.error;
    renderJob();
    renderStepper();
    onTerminal();
  } else if (ev.type === 'eof') {
    closeSSE();
  }
}

function closeSSE() {
  state.esClosed = true;
  if (state.es) { state.es.close(); state.es = null; }
}

async function onTerminal() {
  closeSSE();
  $('cancelBtn').classList.add('hidden');
  $('newJobBtn').classList.remove('hidden');
  const stage = state.job && state.job.stage;

  if (stage === 'done') {
    try {
      const status = await fetchJSON(`/api/status/${state.jobId}`);
      state.job = { ...state.job, ...status };
      renderJob();
      renderStepper();
      if (status.has_subtitles) await loadEditor();
    } catch (err) {
      toast(err.message, 'error');
    }
  } else if (stage === 'error') {
    const box = $('errorBox');
    box.textContent = `${t('toast.error')}: ${state.job.error || ''}`;
    box.classList.remove('hidden');
    $('retryBtn').classList.remove('hidden');
    toast(`${t('toast.error')}: ${state.job.error || ''}`, 'error', 8000);
  } else if (stage === 'cancelled') {
    $('retryBtn').classList.remove('hidden');
    toast(t('toast.cancelled'), 'info');
  }
}

/* ── retry a failed/cancelled job (resumes cached progress) ───────── */
async function retryJob() {
  if (!state.jobId) return;
  const btn = $('retryBtn');
  btn.disabled = true;
  try {
    await fetchJSON(`/api/job/${state.jobId}/retry`, { method: 'POST' });
    $('errorBox').classList.add('hidden');
    btn.classList.add('hidden');
    $('idleCard').classList.add('hidden');
    $('jobCard').classList.remove('hidden');
    $('cancelBtn').classList.remove('hidden');
    $('newJobBtn').classList.add('hidden');
    if (state.job) {
      state.job.stage = 'queued';
      state.job.percent = 0;
      state.job.stage_percent = null;
      state.job.error = null;
    }
    setProgress(0, 'queued');
    renderStepper();
    renderStageLabel();
    appendLog(`↻ ${t('toast.retrying')}`);
    toast(t('toast.retrying'), 'success');
    openSSE();
  } catch (err) {
    toast(`${t('err.generic')}: ${err.message}`, 'error', 8000);
  } finally {
    btn.disabled = false;
  }
}

/* ── job rendering ────────────────────────────────────────────────── */
function renderJob() {
  const job = state.job;
  if (!job) return;
  if (job.original_filename) $('jobFile').textContent = job.original_filename;
  renderStageLabel();
  const terminal = TERMINAL.has(job.stage);
  if (job.stage !== 'uploading') {
    setProgress(job.percent || 0, job.stage, job.stage_percent, terminal);
  }
  $('cancelBtn').classList.toggle('hidden', terminal || job.stage === 'uploading');
  updateStartHint();
}

function setProgress(percent, stage, stagePercent = null, terminal = false) {
  $('progressFill').style.width = `${Math.max(0, Math.min(100, percent))}%`;
  const unknown = !terminal && (stagePercent === null || stagePercent === undefined)
    && stage !== 'uploading' && stage !== 'queued';
  $('progressShimmer').classList.toggle('hidden', !unknown);
  if (!state.uploading || stage !== 'uploading') {
    $('percentLabel').textContent = `${Math.round(percent)}%`;
  }
}

function renderStageLabel() {
  const job = state.job;
  if (!job) return;
  $('stageLabel').textContent = stageLabel(job.stage);
}

function renderStepper() {
  const box = $('stepper');
  if (!box) return;
  const order = state.stageOrder && state.stageOrder.length ? state.stageOrder : ['extracting', 'transcribing', 'translating', 'generating', 'done'];
  const current = state.job ? state.job.stage : 'queued';
  const idx = order.indexOf(current);
  box.innerHTML = '';
  order.forEach((stage, i) => {
    const li = document.createElement('li');
    li.className = 'step';
    let dot = '';
    if (current === 'error' && i === idx) { li.classList.add('error'); dot = '✕'; }
    else if (current === 'cancelled' && i === idx) { li.classList.add('error'); dot = '✕'; }
    else if (current === 'done') { li.classList.add('done'); dot = '✓'; }
    else if (idx >= 0 && i < idx) { li.classList.add('done'); dot = '✓'; }
    else if (i === idx) { li.classList.add('active'); dot = '●'; }
    const dotSpan = document.createElement('span');
    dotSpan.className = 'dot';
    dotSpan.textContent = dot;
    const label = document.createElement('span');
    label.textContent = stageLabel(stage);
    li.appendChild(dotSpan);
    li.appendChild(label);
    box.appendChild(li);
  });
}

/* ── log console ──────────────────────────────────────────────────── */
function appendLog(text) {
  if (!text) return;
  const box = $('logBox');
  const line = document.createElement('div');
  line.className = 'log-line';
  const trimmed = text.trim();
  if (/^(❌|Error|Traceback|\[.*error)/i.test(trimmed)) line.classList.add('err');
  else if (/^(✓|✔|Done)/.test(trimmed)) line.classList.add('ok');
  line.textContent = text;
  box.appendChild(line);
  while (box.children.length > 600) box.removeChild(box.firstChild);
  const nearBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 70;
  if (nearBottom) box.scrollTop = box.scrollHeight;
}

/* ── editor + player ──────────────────────────────────────────────── */
async function loadEditor() {
  if (state.editorLoaded && state.cues.length) return;
  try {
    const data = await fetchJSON(`/api/subtitles/${state.jobId}`);
    state.cues = data.cues;
    state.editorLoaded = true;
    $('resultSection').classList.remove('hidden');
    const video = $('preview');
    if (video.dataset.jobId !== state.jobId) {
      if (state.trackEl) { state.trackEl.remove(); state.trackEl = null; }
      if (state.trackURL) { URL.revokeObjectURL(state.trackURL); state.trackURL = null; }
      video.dataset.jobId = state.jobId;
      video.src = `/api/video/${state.jobId}`;
    }
    renderCues();
    renderDownloadBar();
    renderGhFiles();
    syncTrack();
    $('resultSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (err) {
    if (err.status !== 409) toast(err.message, 'error');
  }
}

function buildVTT(cues) {
  let out = 'WEBVTT\n\n';
  cues.forEach((cue) => {
    out += `${fmtTs(cue.start).replace(',', '.')} --> ${fmtTs(cue.end).replace(',', '.')}\n${cue.text}\n\n`;
  });
  return out;
}

function syncTrack() {
  const video = $('preview');
  if (!video || !state.editorLoaded) return;
  const valid = state.cues.filter((c) => c.text && c.text.trim());
  const vtt = buildVTT(valid);
  if (state.trackEl) { state.trackEl.remove(); state.trackEl = null; }
  if (state.trackURL) { URL.revokeObjectURL(state.trackURL); state.trackURL = null; }
  if (!valid.length) return;
  state.trackURL = URL.createObjectURL(new Blob([vtt], { type: 'text/vtt' }));
  const track = document.createElement('track');
  track.kind = 'subtitles';
  track.label = 'العربية';
  track.srclang = 'ar';
  track.default = true;
  track.src = state.trackURL;
  video.appendChild(track);
  state.trackEl = track;
  const showModes = () => {
    const tracks = video.textTracks;
    for (let i = 0; i < tracks.length; i++) {
      if (tracks[i].kind !== 'subtitles' && tracks[i].kind !== 'captions') continue;
      const isCurrent = state.trackEl && tracks[i] === state.trackEl.track;
      tracks[i].mode = isCurrent ? 'showing' : 'disabled';
    }
  };
  showModes();
  requestAnimationFrame(showModes);
  setTimeout(showModes, 120);
}

function renderCues() {
  const list = $('cueList');
  list.innerHTML = '';
  state.cues.forEach((cue, i) => list.appendChild(buildCueRow(cue, i)));
  $('cueCount').textContent = String(state.cues.length);
  $('saveState').textContent = '';
  state.cueDirty = false;
}

function buildCueRow(cue, i) {
  const row = document.createElement('div');
  row.className = 'cue-row';
  row.dataset.i = String(i);

  const idx = document.createElement('span');
  idx.className = 'cue-idx';
  idx.textContent = String(i + 1);

  const start = document.createElement('input');
  start.className = 'cue-time';
  start.value = fmtTs(cue.start);
  start.dir = 'ltr';
  start.setAttribute('aria-label', 'start');

  const end = document.createElement('input');
  end.className = 'cue-time';
  end.value = fmtTs(cue.end);
  end.dir = 'ltr';
  end.setAttribute('aria-label', 'end');

  const seek = document.createElement('button');
  seek.className = 'cue-seek';
  seek.type = 'button';
  seek.title = '▶';
  seek.textContent = '▶';
  seek.addEventListener('click', () => {
    const video = $('preview');
    const parsed = parseTs(start.value);
    if (parsed !== null && video.src) {
      video.currentTime = parsed;
      video.play().catch(() => {});
    }
  });

  const text = document.createElement('textarea');
  text.className = 'cue-text';
  text.rows = 1;
  text.dir = 'rtl';
  text.value = cue.text;

  const del = document.createElement('button');
  del.className = 'cue-del';
  del.type = 'button';
  del.title = '✕';
  del.textContent = '✕';
  del.addEventListener('click', () => {
    row.remove();
    reindexRows();
    markDirty();
    schedulePreviewSync();
  });

  [start, end].forEach((input) => {
    input.addEventListener('input', () => {
      const ok = parseTs(input.value) !== null;
      input.classList.toggle('invalid', !ok);
      markDirty();
      schedulePreviewSync();
    });
    input.addEventListener('blur', () => {
      const parsed = parseTs(input.value);
      if (parsed !== null) input.value = fmtTs(parsed);
    });
  });
  text.addEventListener('input', () => { markDirty(); schedulePreviewSync(); });

  row.append(idx, start, end, seek, text, del);
  return row;
}

function reindexRows() {
  const rows = $('cueList').querySelectorAll('.cue-row');
  rows.forEach((row, i) => {
    row.dataset.i = String(i);
    row.querySelector('.cue-idx').textContent = String(i + 1);
  });
  $('cueCount').textContent = String(rows.length);
}

function markDirty() {
  state.cueDirty = true;
  $('saveState').textContent = t('editor.dirty');
}

function schedulePreviewSync() {
  clearTimeout(state.previewTimer);
  state.previewTimer = setTimeout(() => {
    const gathered = gatherCues(false);
    state.cues = gathered.cues;
    syncTrack();
  }, 350);
}

function gatherCues(strict) {
  const rows = Array.from($('cueList').querySelectorAll('.cue-row'));
  const cues = [];
  let invalid = false;
  rows.forEach((row) => {
    const startRaw = row.querySelector('.cue-time').value;
    const endRaw = row.querySelectorAll('.cue-time')[1].value;
    const text = row.querySelector('.cue-text').value;
    const start = parseTs(startRaw);
    const end = parseTs(endRaw);
    if (start === null || end === null || end < start) {
      invalid = true;
      if (strict) {
        row.querySelectorAll('.cue-time').forEach((input) => {
          const ok = parseTs(input.value) !== null;
          input.classList.toggle('invalid', !ok);
        });
      }
      return;
    }
    if (!text.trim()) return; // empty cues are dropped
    cues.push({ start, end, text: text.trim() });
  });
  cues.sort((a, b) => a.start - b.start);
  return { cues, invalid, total: rows.length };
}

function addCue() {
  const list = $('cueList');
  const rows = list.querySelectorAll('.cue-row');
  let start = 0;
  if (rows.length) {
    const last = rows[rows.length - 1];
    const parsed = parseTs(last.querySelectorAll('.cue-time')[1].value);
    start = parsed !== null ? parsed + 0.2 : 0;
  } else {
    const video = $('preview');
    start = video && video.src ? video.currentTime || 0 : 0;
  }
  const cue = { start, end: start + 1.5, text: t('editor.newText') };
  const row = buildCueRow(cue, rows.length);
  list.appendChild(row);
  reindexRows();
  markDirty();
  row.scrollIntoView({ block: 'nearest' });
  row.querySelector('.cue-text').focus();
  schedulePreviewSync();
}

async function saveCues() {
  const { cues, invalid } = gatherCues(true);
  if (invalid) { toast(t('err.invalidTime'), 'error'); return; }
  if (!cues.length) { toast(t('err.emptyCues'), 'error'); return; }
  const skipped = gatherCues(false).total - cues.length;
  if (skipped > 0) toast(t('warn.emptySkipped').replace('{n}', skipped), 'info');
  try {
    await fetchJSON(`/api/subtitles/${state.jobId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cues }),
    });
    state.cues = cues;
    renderCues();
    syncTrack();
    $('saveState').textContent = t('editor.saved');
    state.cueDirty = false;
    toast(t('toast.saved'), 'success');
    renderDownloadBar();
  } catch (err) {
    toast(`${t('err.generic')}: ${err.message}`, 'error');
  }
}

function downloadURL(fmt) {
  const bom = $('dlBom').checked ? 'true' : 'false';
  return `/api/download/${state.jobId}?format=${fmt}&bom=${bom}`;
}

function renderDownloadBar() {
  const bar = $('downloadBar');
  if (!bar || !state.jobId || !state.job || state.job.stage !== 'done') {
    if (bar) bar.innerHTML = '';
    return;
  }
  const files = state.job.files || [];
  bar.innerHTML = '';
  const makePill = (fmt, key, primary) => {
    const a = document.createElement('a');
    a.className = 'dl-pill' + (primary ? ' dl-primary' : '');
    a.textContent = t(key);
    a.href = downloadURL(fmt);
    return a;
  };
  bar.appendChild(makePill('srt', 'dl.srt', true));
  bar.appendChild(makePill('vtt', 'dl.vtt', false));
  if (files.includes('video')) bar.appendChild(makePill('video', 'dl.video', false));
}

/* ── GitHub push ──────────────────────────────────────────────────── */
function renderGhFiles() {
  const box = $('ghFiles');
  if (!box) return;
  const files = (state.job && state.job.files) || [];
  // drop formats that are no longer available for this job
  Array.from(state.ghFiles).forEach((key) => {
    if (key !== 'srt' && key !== 'vtt' && !files.includes(key)) state.ghFiles.delete(key);
  });
  box.innerHTML = '';
  const addBox = (key, label) => {
    if (key === 'video' && !files.includes('video')) return;
    const row = document.createElement('label');
    row.className = 'check-row';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.className = 'check';
    input.checked = state.ghFiles.has(key);
    input.addEventListener('change', () => {
      if (input.checked) state.ghFiles.add(key);
      else state.ghFiles.delete(key);
    });
    const span = document.createElement('span');
    span.textContent = label;
    row.append(input, span);
    box.appendChild(row);
  };
  addBox('srt', 'SRT');
  addBox('vtt', 'VTT');
  addBox('video', t('dl.video').replace('⬇ ', ''));
}

function renderGhHint() {
  const hint = $('ghHint');
  if (!hint) return;
  const envOk = !!(state.health && state.health.github && state.health.github.env_token);
  hint.textContent = envOk ? t('gh.tokenEnv') : t('gh.tokenPat');
}

function ghStatusBox(kind, text) {
  const status = $('ghStatus');
  const palette = {
    busy: 'border-slate-700 bg-slate-900/60 text-slate-300',
    ok: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
    err: 'border-red-500/40 bg-red-500/10 text-red-300',
  };
  status.className = `mt-3 rounded-xl border p-3 text-sm ${palette[kind] || palette.busy}`;
  status.textContent = text;
  return status;
}

async function pushToGitHub() {
  if (!state.jobId) return;
  const selected = Array.from(state.ghFiles);
  if (!selected.length) { toast(t('gh.noFiles'), 'error'); return; }
  const repo = $('ghRepo').value.trim();
  if (!repo.includes('/')) { toast(t('gh.badRepo'), 'error'); $('ghRepo').focus(); return; }

  const btn = $('ghPushBtn');
  btn.disabled = true;
  ghStatusBox('busy', t('gh.pushing'));
  try {
    const res = await fetchJSON('/api/github/push', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_id: state.jobId,
        repo,
        branch: $('ghBranch').value.trim() || 'main',
        folder: $('ghFolder').value.trim(),
        files: selected,
        message: $('ghMsg').value.trim(),
        token: $('ghToken').value.trim(),
      }),
    });
    const status = ghStatusBox('ok', `${t('gh.done')} — ${res.files.length} · ${String(res.commit_sha || '').slice(0, 7)}`);
    if (res.html_url) {
      const link = document.createElement('a');
      link.href = res.html_url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.className = 'mx-2 font-bold underline';
      link.textContent = t('gh.openCommit');
      status.appendChild(link);
    }
    toast(t('gh.done'), 'success');
    appendLog(`⬆ ${t('gh.done')} → ${res.repo}@${res.branch} (${String(res.commit_sha || '').slice(0, 7)})`);
  } catch (err) {
    ghStatusBox('err', `${t('gh.failed')}: ${err.message}`);
    toast(`${t('gh.failed')}: ${err.message}`, 'error', 8000);
  } finally {
    btn.disabled = false;
  }
}

/* ── reset ────────────────────────────────────────────────────────── */
async function newJob() {
  const id = state.jobId;
  closeSSE();
  if (id) {
    try { await fetchJSON(`/api/job/${id}`, { method: 'DELETE' }); } catch (_) { /* TTL cleans up */ }
  }
  state.jobId = null;
  state.job = null;
  state.cues = [];
  state.editorLoaded = false;
  state.trackEl = null;
  state.trackURL = null;
  localStorage.removeItem('v2a_job');
  clearFile();
  $('urlInput').value = '';
  $('jobCard').classList.add('hidden');
  $('resultSection').classList.add('hidden');
  $('idleCard').classList.remove('hidden');
  $('errorBox').classList.add('hidden');
  $('logBox').innerHTML = '';
  const retry = $('retryBtn');
  retry.classList.add('hidden');
  retry.disabled = false;
  state.ghFiles = new Set(['srt', 'vtt']);
  $('ghRepo').value = '';
  $('ghFolder').value = '';
  $('ghMsg').value = '';
  $('ghToken').value = '';
  ghStatusBox('busy', '');
  $('ghStatus').classList.add('hidden');
  renderGhFiles();
  const video = $('preview');
  video.pause();
  video.removeAttribute('src');
  video.load();
  updateStartHint();
}

async function cancelJob() {
  if (!state.jobId) return;
  toast(t('toast.cancelling'));
  try {
    await fetchJSON(`/api/cancel/${state.jobId}`, { method: 'POST' });
  } catch (err) {
    toast(err.message, 'error');
  }
}

/* ── resume after reload ──────────────────────────────────────────── */
async function resumeJob() {
  const id = localStorage.getItem('v2a_job');
  if (!id) return;
  try {
    const status = await fetchJSON(`/api/status/${id}`);
    state.jobId = id;
    state.job = status;
    state.stageOrder = computeStageOrder(status.options, status.source);
    $('idleCard').classList.add('hidden');
    $('jobCard').classList.remove('hidden');
    $('jobFile').textContent = status.original_filename;
    (status.logs || []).forEach(appendLog);
    renderJob();
    renderStepper();
    $('newJobBtn').classList.remove('hidden');
    if (TERMINAL.has(status.stage)) {
      if (status.stage === 'done' && status.has_subtitles) await loadEditor();
      if (status.stage === 'error') {
        const box = $('errorBox');
        box.textContent = `${t('toast.error')}: ${status.error || ''}`;
        box.classList.remove('hidden');
      }
      if (status.stage === 'error' || status.stage === 'cancelled') {
        $('retryBtn').classList.remove('hidden');
      }
      if (status.stage !== 'error') $('cancelBtn').classList.add('hidden');
      $('newJobBtn').classList.remove('hidden');
    } else {
      $('cancelBtn').classList.remove('hidden');
      openSSE();
    }
  } catch (err) {
    if (err.status === 404) localStorage.removeItem('v2a_job');
  }
}

/* ── events ───────────────────────────────────────────────────────── */
function bindEvents() {
  $('langToggle').addEventListener('click', () => {
    state.lang = state.lang === 'ar' ? 'en' : 'ar';
    localStorage.setItem('v2a_lang', state.lang);
    applyI18n();
  });

  const zone = $('dropZone');
  const input = $('fileInput');
  zone.addEventListener('click', () => input.click());
  zone.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') input.click(); });
  input.addEventListener('change', () => { if (input.files[0]) selectFile(input.files[0]); });

  ['dragenter', 'dragover'].forEach((evt) => zone.addEventListener(evt, (e) => {
    e.preventDefault();
    zone.classList.add('dragover');
  }));
  ['dragleave', 'drop'].forEach((evt) => zone.addEventListener(evt, (e) => {
    e.preventDefault();
    zone.classList.remove('dragover');
  }));
  zone.addEventListener('drop', (e) => {
    const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) selectFile(file);
  });

  $('fileChipClear').addEventListener('click', (e) => { e.stopPropagation(); clearFile(); });
  $('tabFile').addEventListener('click', () => switchSource('file'));
  $('tabUrl').addEventListener('click', () => switchSource('url'));
  $('urlInput').addEventListener('input', updateStartHint);

  $('startBtn').addEventListener('click', startJob);
  $('cancelBtn').addEventListener('click', cancelJob);
  $('newJobBtn').addEventListener('click', newJob);
  $('retryBtn').addEventListener('click', retryJob);
  $('addCueBtn').addEventListener('click', addCue);
  $('saveCuesBtn').addEventListener('click', saveCues);
  $('dlBom').addEventListener('change', renderDownloadBar);
  $('ghPushBtn').addEventListener('click', pushToGitHub);
  $('logClear').addEventListener('click', () => { $('logBox').innerHTML = ''; });

  window.addEventListener('beforeunload', (e) => {
    if (state.cueDirty) { e.preventDefault(); e.returnValue = ''; }
  });
}

/* ── init ─────────────────────────────────────────────────────────── */
async function init() {
  bindEvents();
  applyI18n();
  try {
    state.health = await fetchJSON('/api/health');
  } catch (err) {
    toast(t('toast.offline'), 'error', 10000);
    return;
  }
  populateOptions();
  applyI18n();
  updateStartHint();
  await resumeJob();
}

document.addEventListener('DOMContentLoaded', init);
