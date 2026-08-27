/**
 * LiveTrans Voice — 浏览器语音识别 + 实时翻译
 */
(function () {
  var API = '/api';
  var lectureId = null;
  var recording = false;
  var stopping = false;
  var paused = false;
  var recognition = null;
  var recognitionRestartTimer = null;
  var currentSectionTransId = null;
  var pendingIdCounter = 0;
  var pendingJobs = new Set();
  var livePreviewBlock = null;
  var mediaStream = null;
  var audioCaptureStream = null;
  var mediaRecorder = null;
  var audioChunks = [];
  var videoRecorder = null;
  var videoUploadQueue = Promise.resolve();
  var videoUploadStarted = false;
  var videoFrameTimer = null;
  var videoEnabled = false;
  var recordingStartedAt = 0;
  var lastFrameSignature = null;
  var pendingPhrases = [];
  var lastInterimText = '';
  var liveAsrActive = false;
  var speechDesired = false;
  var segmentLoopActive = false;
  var segmentTimer = null;
  var segmentRecorder = null;
  var audioContext = null;
  var audioSource = null;
  var audioProcessor = null;
  var audioMute = null;
  var realtimeSocket = null;
  var realtimeActive = false;
  var historyDomLimit = 80;
  var maxSegmentChars = 200;
  var mergeMinChars = 40;
  var mergeWaitMs = 1800;
  var mergeParts = [];
  var mergeFlushTimer = null;
  var currentSourceEl = document.getElementById('current-source');
  var currentTargetEl = document.getElementById('current-target');
  var currentSectionEl = document.getElementById('current-section');
  var previousContextEl = document.getElementById('previous-context');
  var lastCommittedDisplay = '';
  var lastCommittedSource = '';
  var previousBridgeSource = '';

  var starBtn = document.getElementById('star-btn');
  var pauseBtn = document.getElementById('pause-btn');
  var recordBtn = document.getElementById('record-btn');
  var recordIcon = document.getElementById('record-icon');
  var statusDot = document.getElementById('status-dot');
  var statusText = document.getElementById('status-text');
  var courseName = document.getElementById('course-name');
  var historySec = document.getElementById('history-section');
  var featureIntro = document.getElementById('feature-intro');
  var toastEl = document.getElementById('toast');
  var tagPicker = document.getElementById('tagPicker');
  var sourceLangSelect = document.getElementById('source-lang');
  var targetLangSelect = document.getElementById('target-lang');
  var translationToggle = document.getElementById('translation-enabled');
  var translationArrow = document.getElementById('translation-arrow');
  var videoToggle = document.getElementById('video-enabled');
  var capturePreview = document.getElementById('capture-preview');
  var courseSelect = document.getElementById('course-select');
  var coursesById = {};
  var resumeBanner = document.getElementById('resumeBanner');
  var resumeBannerInfo = document.getElementById('resumeBannerInfo');
  var resumeContinueBtn = document.getElementById('resumeContinueBtn');
  var resumeFinishBtn = document.getElementById('resumeFinishBtn');
  var pendingActiveLecture = null;
  var startForceNew = false;
  var streamOffsetMs = 0;
  var appendBootstrapDone = false;

  function audioOnlyStream() {
    if (!mediaStream) return null;
    return new MediaStream(mediaStream.getAudioTracks());
  }

  function releaseCaptureStreams() {
    if (mediaStream) mediaStream.getTracks().forEach(function (track) { track.stop(); });
    mediaStream = null;
    audioCaptureStream = null;
    if (capturePreview) capturePreview.srcObject = null;
  }

  // ─── 标签选择弹窗 ───────────────────────────────
  var tagPickerCallback = null;

  function showTagPicker(anchorEl, callback) {
    if (!tagPicker) return;
    var rect = anchorEl.getBoundingClientRect();
    var left = Math.max(8, Math.min(rect.left + rect.width / 2 - 80, window.innerWidth - 168));
    var top = rect.bottom + 6;
    if (top + 220 > window.innerHeight) {
      top = rect.top - 220;
    }
    tagPicker.style.left = left + 'px';
    tagPicker.style.top = top + 'px';
    tagPicker.classList.remove('hidden');
    tagPickerCallback = callback;
  }

  function hideTagPicker() {
    if (!tagPicker) return;
    tagPicker.classList.add('hidden');
    tagPickerCallback = null;
  }

  // 标签选项点击
  if (tagPicker) {
    tagPicker.querySelectorAll('.tag-option').forEach(function (opt) {
      opt.addEventListener('click', function (e) {
        e.stopPropagation();
        var tag = this.getAttribute('data-tag');
        if (tag && tagPickerCallback) { tagPickerCallback(tag); }
        hideTagPicker();
      });
    });
  }

  // 点击弹窗外部关闭
  document.addEventListener('click', function (e) {
    if (!tagPicker || tagPicker.classList.contains('hidden')) return;
    if (!tagPicker.contains(e.target)) { hideTagPicker(); }
  });

  function api(path, opts) {
    opts = opts || {};
    var headers = { 'Content-Type': 'application/json' };
    var token = localStorage.getItem('livetrans_token');
    if (token) headers['Authorization'] = 'Bearer ' + token;
    var fetchOpts = { method: opts.method || 'GET', headers: headers };
    if (opts.body) fetchOpts.body = opts.body;
    return fetch(API + path, fetchOpts).then(function (r) {
      return r.json().then(function (d) { if (!r.ok) throw new Error(d.detail || 'fail'); return d; });
    });
  }

  function selectedSourceLang() {
    return sourceLangSelect && sourceLangSelect.value ? sourceLangSelect.value : 'en';
  }

  function selectedTargetLang() {
    if (!isTranslationEnabled()) return selectedSourceLang();
    return targetLangSelect && targetLangSelect.value ? targetLangSelect.value : 'zh-CN';
  }

  function isTranslationEnabled() {
    return !translationToggle || translationToggle.checked;
  }

  function syncTranslationModeUi() {
    var enabled = isTranslationEnabled();
    if (translationArrow) translationArrow.classList.toggle('hidden', !enabled);
    if (targetLangSelect) {
      targetLangSelect.classList.toggle('hidden', !enabled);
      targetLangSelect.disabled = !enabled || recording || paused;
    }
    if (currentTargetEl) currentTargetEl.classList.toggle('hidden', !enabled);
  }

  function setTranslationEnabled(enabled) {
    if (translationToggle) translationToggle.checked = !!enabled;
    syncTranslationModeUi();
  }

  function recognitionLocale(code) {
    var locales = {
      en: 'en-US', de: 'de-DE', fr: 'fr-FR', es: 'es-ES', pt: 'pt-PT',
      it: 'it-IT', ja: 'ja-JP', ko: 'ko-KR', ru: 'ru-RU', th: 'th-TH',
      vi: 'vi-VN', ar: 'ar-SA', hi: 'hi-IN', tr: 'tr-TR',
      'zh-CN': 'zh-CN', 'zh-TW': 'zh-TW'
    };
    return locales[code] || code;
  }

  function populateLanguageSelect(select, languages, selected) {
    if (!select) return;
    select.innerHTML = '';
    languages.forEach(function (language) {
      var option = document.createElement('option');
      option.value = language.code;
      option.textContent = (language.flag_emoji || '🌐') + ' ' + language.name_native;
      option.selected = language.code === selected;
      select.appendChild(option);
    });
  }

  function saveLanguagePreferences() {
    if (!isLoggedIn()) return;
    api('/settings', {
      method: 'PUT',
      body: JSON.stringify({
        default_source_lang: selectedSourceLang(),
        default_target_lang: targetLangSelect && targetLangSelect.value ? targetLangSelect.value : 'zh-CN'
      })
    }).catch(function (error) { toast(error.message || '语言偏好保存失败'); });
  }

  function loadLanguagePreferences() {
    Promise.all([api('/languages'), api('/settings')]).then(function (results) {
      var languages = results[0] || [];
      var settings = results[1] || {};
      var source = settings.default_source_lang === 'auto'
        ? 'en' : (settings.default_source_lang || 'en');
      var target = settings.default_target_lang || 'zh-CN';
      populateLanguageSelect(sourceLangSelect, languages, source);
      populateLanguageSelect(targetLangSelect, languages, target);
    }).catch(function () {
      // 保留 HTML 中的英语→中文默认选项。
    });
  }

  function selectedCourseId() {
    if (!courseSelect || !courseSelect.value) return null;
    var id = Number(courseSelect.value);
    return Number.isInteger(id) && id > 0 ? id : null;
  }

  function applyCourseDefaults(course) {
    if (!course) return;
    if (sourceLangSelect) sourceLangSelect.value = course.source_lang;
    if (targetLangSelect) targetLangSelect.value = course.target_lang;
    setTranslationEnabled(course.translation_enabled !== false);
    if (!recording && !paused) courseName.textContent = course.name;
  }

  function loadCourseOptions() {
    if (!isLoggedIn() || !courseSelect) return;
    Promise.all([api('/courses'), api('/courses/recommendation/now')]).then(function (results) {
      var courses = results[0] || [];
      var suggested = results[1];
      var selected = courseSelect.value;
      coursesById = {};
      courseSelect.innerHTML = '<option value="">临时课堂（不归入课程）</option>';
      courses.forEach(function (course) {
        coursesById[String(course.id)] = course;
        var option = document.createElement('option');
        option.value = course.id;
        option.textContent = course.name + (course.term ? ' · ' + course.term : '');
        courseSelect.appendChild(option);
      });
      var next = selected || (suggested ? String(suggested.id) : '');
      courseSelect.value = next;
      if (next && coursesById[next]) applyCourseDefaults(coursesById[next]);
    }).catch(function () {
      // 未登录、旧服务端或无课程时保留临时课堂模式。
    });
  }

  if (sourceLangSelect) sourceLangSelect.addEventListener('change', saveLanguagePreferences);
  if (courseSelect) courseSelect.addEventListener('change', function () {
    var course = coursesById[String(courseSelect.value)];
    if (course) applyCourseDefaults(course);
    else if (!recording && !paused) courseName.textContent = '课堂录音';
  });
  if (targetLangSelect) targetLangSelect.addEventListener('change', saveLanguagePreferences);
  if (translationToggle) translationToggle.addEventListener('change', syncTranslationModeUi);
  syncTranslationModeUi();

  function toast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg; toastEl.classList.remove('hidden');
    setTimeout(function () { toastEl.classList.add('hidden'); }, 2500);
  }

  function isLoggedIn() {
    return !!localStorage.getItem('livetrans_token');
  }

  function isIOSClient() {
    return /iPad|iPhone|iPod/i.test(navigator.userAgent) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  }

  function hasSpeechRecognition() {
    return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  }

  function preferServerAsr() {
    return isIOSClient() ||
      /Android|Mobile|MicroMessenger|Harmony|HUAWEI|vivo|OPPO|MiuiBrowser/i.test(navigator.userAgent);
  }

  function preferDisplayText(source, translation) {
    if (isTranslationEnabled()) {
      var translated = String(translation || '').trim();
      if (translated && translated !== '正在翻译…' && translated !== '正在识别…') {
        return translated;
      }
    }
    return String(source || '').trim();
  }

  function truncateContextText(text, maxChars) {
    var value = String(text || '').trim();
    if (!value) return '';
    maxChars = maxChars || 72;
    if (value.length <= maxChars) return value;
    return '…' + value.slice(-(maxChars - 1));
  }

  function setPreviousContext(text) {
    if (!previousContextEl) return;
    var shown = truncateContextText(text, 80);
    if (!shown) {
      previousContextEl.textContent = '';
      previousContextEl.classList.add('hidden');
      return;
    }
    previousContextEl.textContent = shown;
    previousContextEl.classList.remove('hidden');
  }

  function setCurrentSubtitle(source, translation) {
    if (!currentSectionEl) return;
    currentSectionEl.style.display = '';
    if (currentSourceEl) {
      currentSourceEl.textContent = source || '';
      // 长句时滚到尾部，保证正在说的内容仍在大字区可见。
      currentSourceEl.scrollTop = currentSourceEl.scrollHeight;
    }
    if (currentTargetEl) {
      currentTargetEl.textContent = isTranslationEnabled() ? (translation || '') : '';
      currentTargetEl.scrollTop = currentTargetEl.scrollHeight;
    }
    if (currentSectionEl.scrollHeight > currentSectionEl.clientHeight) {
      currentSectionEl.scrollTop = currentSectionEl.scrollHeight;
    }
  }

  function scrollHistoryToLatest() {
    if (!historySec) return;
    historySec.scrollTop = historySec.scrollHeight;
  }

  function hideCurrentSubtitle() {
    if (currentSectionEl) currentSectionEl.style.display = 'none';
    if (currentSourceEl) currentSourceEl.textContent = '';
    if (currentTargetEl) currentTargetEl.textContent = '';
    setPreviousContext('');
    lastCommittedDisplay = '';
    lastCommittedSource = '';
    previousBridgeSource = '';
  }

  function enqueueRecognizedText(text) {
    text = String(text || '').trim();
    if (!text) return;
    bufferFinalText(text);
  }

  function looksIncompleteClient(text, minChars) {
    var value = String(text || '').trim();
    if (!value) return true;
    if (value.length < (minChars || mergeMinChars)) return true;
    var bare = value.replace(/[。！？.!?;；…]+$/g, '');
    var endings = [
      '当中', '包括', '以及', '或者', '因为', '所以', '但是', '而且', '就是',
      '一个', '一种', '一些', '这个', '那个', '我们', '他们', '进行', '通过',
      '首先', '其次', '然后', '例如', '比如', '关于', '对于', '根据'
    ];
    for (var i = 0; i < endings.length; i++) {
      if (bare.slice(-endings[i].length) === endings[i]) return true;
    }
    var last = value.charAt(value.length - 1);
    return '，、,;:： '.indexOf(last) >= 0;
  }

  function joinClientParts(parts) {
    var cleaned = [];
    for (var i = 0; i < parts.length; i++) {
      var part = String(parts[i] || '').replace(/\s+/g, ' ').trim();
      if (part) cleaned.push(part);
    }
    if (!cleaned.length) return '';
    var out = cleaned[0];
    for (var j = 1; j < cleaned.length; j++) {
      var next = cleaned[j];
      var prev = out.charAt(out.length - 1);
      var first = next.charAt(0);
      if (/[A-Za-z0-9]/.test(prev) && /[A-Za-z0-9]/.test(first)) out += ' ' + next;
      else out += next;
    }
    return out;
  }

  function commitRecognizedText(text) {
    text = String(text || '').trim();
    if (!text) return;
    var chunks = splitClientSegments(text, maxSegmentChars);
    if (!lectureId) {
      chunks.forEach(function (chunk) { pendingPhrases.push(chunk); });
      setCurrentSubtitle(chunks[chunks.length - 1] || text, '正在启动课堂…');
      showLivePreview(chunks[chunks.length - 1] || text);
      return;
    }
    chunks.forEach(function (chunk) { translateAndSave(chunk); });
  }

  function flushMergeBuffer() {
    if (mergeFlushTimer) {
      clearTimeout(mergeFlushTimer);
      mergeFlushTimer = null;
    }
    if (!mergeParts.length) return;
    var joined = joinClientParts(mergeParts);
    mergeParts = [];
    if (joined) commitRecognizedText(joined);
  }

  function bufferFinalText(text) {
    var value = String(text || '').trim();
    if (!value) return;
    mergeParts.push(value);
    var joined = joinClientParts(mergeParts);
    showLivePreview(joined);
    statusText.textContent = '正在整理: ' + joined.substring(0, 24);
    if (joined.length >= maxSegmentChars || !looksIncompleteClient(joined, mergeMinChars)) {
      flushMergeBuffer();
      return;
    }
    if (mergeFlushTimer) clearTimeout(mergeFlushTimer);
    mergeFlushTimer = setTimeout(function () {
      mergeFlushTimer = null;
      flushMergeBuffer();
    }, mergeWaitMs);
  }

  function splitClientSegments(text, maxChars) {
    var value = String(text || '').replace(/\s+/g, ' ').trim();
    if (!value) return [];
    maxChars = maxChars || 200;
    if (value.length <= maxChars) return [value];
    var strong = '。！？；.!?;';
    var weak = '，、,;:： ';
    var segments = [];
    var start = 0;
    while (start < value.length) {
      if (value.length - start <= maxChars) {
        var tail = value.slice(start).trim();
        if (tail) segments.push(tail);
        break;
      }
      var windowEnd = start + maxChars;
      var cut = windowEnd;
      var minPos = start + Math.max(8, Math.floor(maxChars / 5));
      for (var i = windowEnd - 1; i >= minPos; i--) {
        if (strong.indexOf(value.charAt(i)) >= 0) { cut = i + 1; break; }
      }
      if (cut === windowEnd) {
        for (var j = windowEnd - 1; j >= minPos; j--) {
          if (weak.indexOf(value.charAt(j)) >= 0) { cut = j + 1; break; }
        }
      }
      var piece = value.slice(start, cut).trim();
      if (piece) segments.push(piece);
      start = cut;
      while (start < value.length && value.charAt(start) === ' ') start += 1;
    }
    return segments.length ? segments : [value];
  }

  function pruneHistoryDom() {
    if (!historySec || historyDomLimit <= 0) return;
    var blocks = historySec.querySelectorAll('.space-y-unit:not(.opacity-70)');
    var overflow = blocks.length - historyDomLimit;
    for (var i = 0; i < overflow; i++) {
      if (blocks[i] && blocks[i] !== livePreviewBlock) blocks[i].remove();
    }
  }

  function flushPendingPhrases() {
    var items = pendingPhrases.splice(0, pendingPhrases.length);
    items.forEach(function (text) { translateAndSave(text); });
  }

  function safeNextPage(page) {
    page = String(page || 'recorder.html').split('#')[0];
    if (!/^[a-zA-Z0-9._-]+\.html$/.test(page)) return 'recorder.html';
    return page;
  }

  function showAuthModal(reason, nextPage) {
    var modal = document.getElementById('authModal');
    var reasonEl = document.getElementById('authModalReason');
    var loginLink = document.getElementById('authLogin');
    var registerLink = document.getElementById('authRegister');
    var next = encodeURIComponent(safeNextPage(nextPage || 'recorder.html'));
    if (reasonEl) reasonEl.textContent = reason || '登录或注册后即可开始实时翻译';
    if (loginLink) loginLink.href = 'login.html?next=' + next;
    if (registerLink) registerLink.href = 'register.html?next=' + next;
    if (modal) modal.classList.remove('hidden');
  }

  function hideAuthModal() {
    var modal = document.getElementById('authModal');
    if (modal) modal.classList.add('hidden');
  }

  function requireAuth(nextPage, reason) {
    if (isLoggedIn()) return false;
    showAuthModal(reason, nextPage);
    return true;
  }

  function updateGuestChrome() {
    var navAuth = document.getElementById('nav-auth-link');
    if (!navAuth) return;
    // 主导航由 shared/app-navigation.js 统一维护登录 / 退出状态。
    if (navAuth.hasAttribute('data-nav-auth')) return;
    if (isLoggedIn()) {
      navAuth.href = 'login.html';
      navAuth.classList.remove('text-primary');
      navAuth.classList.add('text-error');
      navAuth.innerHTML = '<span class="material-symbols-outlined text-xl">logout</span>退出登录';
      navAuth.addEventListener('click', function (e) {
        e.preventDefault();
        if (window.LiveTransAuth && LiveTransAuth.clearSession) LiveTransAuth.clearSession();
        else {
          localStorage.removeItem('livetrans_token');
          localStorage.removeItem('livetrans_refresh_token');
          localStorage.removeItem('livetrans_user');
        }
        window.location.href = 'recorder.html';
      }, { once: true });
    }
  }

  var authCancel = document.getElementById('authCancel');
  if (authCancel) authCancel.addEventListener('click', hideAuthModal);
  var authModal = document.getElementById('authModal');
  if (authModal) {
    authModal.addEventListener('click', function (e) {
      if (e.target === authModal) hideAuthModal();
    });
  }
  document.querySelectorAll('[data-require-auth]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      if (isLoggedIn()) return;
      e.preventDefault();
      requireAuth(el.getAttribute('href'), el.getAttribute('data-auth-reason'));
    });
  });
  updateGuestChrome();

  function hideFeatureIntro() {
    if (featureIntro) featureIntro.classList.add('hidden');
  }

  function showFeatureIntroIfIdle() {
    if (recording || stopping || paused) return;
    if (historySec && historySec.children.length) return;
    if (featureIntro) featureIntro.classList.remove('hidden');
  }

  var featureModal = document.getElementById('featureModal');
  var featureHelpBtn = document.getElementById('feature-help-btn');
  var featureModalClose = document.getElementById('featureModalClose');
  var guideBtn = document.getElementById('guide-btn');
  var guidePopover = document.getElementById('guide-popover');
  var GUIDE_COLORS = ['primary', 'secondary', 'accent-purple'];
  var currentGuide = {
    title: '课堂学习助手',
    subtitle: '从上课录音到课后复习提问，一条完整学习链路：听懂、记下、汇总、带走、再提问。',
    footer_hint: '建议先在「课程中心」建课 → 回来点绿色麦克风开始 · 未登录会提示注册',
    items: [
      {
        icon: 'school',
        title: '课前：课程中心建课',
        body: '创建课程并设置授课/翻译语言；录音前选好课程，课后记录会自动归档，方便按学期管理。'
      },
      {
        icon: 'subtitles',
        title: '课上：实时双语字幕',
        body: '麦克风录音后，原文与译文同步滚动。也可关闭翻译，只保留录音与文字，适合母语课堂。'
      },
      {
        icon: 'star',
        title: '课上：一键收藏重点',
        body: '听到关键句点星标，标成重要 / 疑问 / 考点 / 定义；课后在「知识卡片」里集中复习。'
      },
      {
        icon: 'description',
        title: '课后：自动课堂简报',
        body: '结束录音后生成概览、重点、术语与待确认作业；每条结论可跳回字幕时间点核对。'
      },
      {
        icon: 'folder_zip',
        title: '资料：上传与一键导出',
        body: '在课堂记录里上传 PPT / PDF / 图片；可导出简报 Markdown，或打包下载全部学习资料。'
      },
      {
        icon: 'psychology',
        title: '随时：学习助手问答',
        body: '按课程检索笔记、拆解作业，也可粘贴报错/题目截图提问；回答会附上可跳转的课堂证据。'
      }
    ]
  };

  function isGuideOpen() {
    return guidePopover && !guidePopover.classList.contains('hidden');
  }

  function closeGuidePopover() {
    if (guidePopover) guidePopover.classList.add('hidden');
    if (guideBtn) {
      guideBtn.classList.remove('guide-open');
      guideBtn.setAttribute('aria-expanded', 'false');
    }
  }

  function openGuidePopover() {
    closeFeatureModal();
    if (guidePopover) guidePopover.classList.remove('hidden');
    if (guideBtn) {
      guideBtn.classList.add('guide-open');
      guideBtn.setAttribute('aria-expanded', 'true');
    }
  }

  function toggleGuidePopover(e) {
    if (e) e.stopPropagation();
    if (isGuideOpen()) closeGuidePopover();
    else openGuidePopover();
  }

  function openFeatureModal() {
    closeGuidePopover();
    if (featureModal) featureModal.classList.remove('hidden');
  }
  function closeFeatureModal() {
    if (featureModal) featureModal.classList.add('hidden');
  }

  function renderGuideCards(items) {
    return (items || []).map(function (item, index) {
      var color = GUIDE_COLORS[index % GUIDE_COLORS.length];
      var fill = item.icon === 'star' ? " style=\"font-variation-settings:'FILL' 1\"" : '';
      return '<div class="feature-card bg-white rounded-2xl p-4 border border-outline-variant/20 shadow-sm flex gap-3">' +
        '<div class="w-10 h-10 rounded-xl bg-' + color + '/10 text-' + color + ' flex items-center justify-center flex-shrink-0">' +
          '<span class="material-symbols-outlined"' + fill + '>' + escapeHtml(item.icon || 'info') + '</span>' +
        '</div>' +
        '<div>' +
          '<h3 class="font-bold text-ink-deep text-sm">' + escapeHtml(item.title) + '</h3>' +
          '<p class="text-xs text-on-surface-variant mt-0.5 leading-relaxed">' + escapeHtml(item.body) + '</p>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  function renderGuideCompact(items) {
    return (items || []).map(function (item) {
      return '<div class="flex gap-2.5">' +
        '<span class="material-symbols-outlined text-primary text-[20px] mt-0.5 flex-shrink-0">' + escapeHtml(item.icon || 'info') + '</span>' +
        '<div>' +
          '<p class="font-semibold text-ink-deep text-sm leading-snug">' + escapeHtml(item.title) + '</p>' +
          '<p class="text-xs text-on-surface-variant mt-0.5 leading-relaxed">' + escapeHtml(item.body) + '</p>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  function renderGuideModalItems(items) {
    return (items || []).map(function (item) {
      return '<li><span class="font-semibold text-primary">' + escapeHtml(item.title) + '</span> — ' + escapeHtml(item.body) + '</li>';
    }).join('');
  }

  function applyGuide(data) {
    if (!data) return;
    currentGuide = data;
    var title = data.title || '';
    var subtitle = data.subtitle || '';
    var footer = data.footer_hint || '';
    var items = data.items || [];
    var setText = function (id, value) {
      var el = document.getElementById(id);
      if (el) el.textContent = value;
    };
    setText('feature-intro-title', title);
    setText('feature-intro-subtitle', subtitle);
    setText('feature-intro-footer', footer);
    setText('guide-popover-title', title);
    setText('guide-popover-subtitle', subtitle);
    setText('guide-popover-footer', footer);
    setText('feature-modal-title', title);
    setText('feature-modal-subtitle', subtitle);
    var introItems = document.getElementById('feature-intro-items');
    if (introItems) introItems.innerHTML = renderGuideCards(items);
    var popoverItems = document.getElementById('guide-popover-items');
    if (popoverItems) popoverItems.innerHTML = renderGuideCompact(items);
    var modalItems = document.getElementById('feature-modal-items');
    if (modalItems) modalItems.innerHTML = renderGuideModalItems(items);
  }

  function loadGuide() {
    applyGuide(currentGuide);
    api('/guides/recorder_features').then(applyGuide).catch(function () {});
  }

  if (featureHelpBtn) featureHelpBtn.addEventListener('click', openFeatureModal);
  if (featureModalClose) featureModalClose.addEventListener('click', closeFeatureModal);
  if (featureModal) {
    featureModal.addEventListener('click', function (e) {
      if (e.target === featureModal) closeFeatureModal();
    });
  }
  if (guideBtn) guideBtn.addEventListener('click', toggleGuidePopover);
  document.addEventListener('click', function (e) {
    if (!isGuideOpen()) return;
    if (guidePopover && guidePopover.contains(e.target)) return;
    if (guideBtn && guideBtn.contains(e.target)) return;
    closeGuidePopover();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      closeGuidePopover();
      closeFeatureModal();
    }
  });

  var bars = document.querySelectorAll('.waveform-bar');
  var waveInterval;
  function startWave() { waveInterval = setInterval(function () { bars.forEach(function (b) { b.style.height = (Math.floor(Math.random() * 28) + 6) + 'px'; }); }, 80); }
  function stopWave() { clearInterval(waveInterval); }

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char];
    });
  }

  function addSubtitle(source, translation, isBookmarked, transId) {
    hideFeatureIntro();
    if (historySec) historySec.style.display = '';
    // 新句上屏前，把上一句译文/原文留在当前区上方，方便连贯阅读。
    if (lastCommittedDisplay) {
      previousBridgeSource = lastCommittedSource;
      setPreviousContext(lastCommittedDisplay);
    }
    var old = document.querySelector('.subtitle-current');
    if (old) { old.classList.remove('subtitle-current'); old.classList.add('opacity-60'); }
    var block = document.createElement('div');
    block.className = 'space-y-unit border-l-2 border-primary/20 pl-4 py-2 subtitle-enter';
    // 如果有真实 ID 就存起来，否则标记为 pending
    if (transId) {
      block.setAttribute('data-trans-id', transId);
    }
    var starFilled = isBookmarked ? "'FILL' 1" : "'FILL' 0";
    block.innerHTML =
      '<div class="flex justify-between items-start"><div>' +
        '<p class="font-body-history-source text-body-history-source text-on-surface">' + escapeHtml(source) + '</p>' +
        (isTranslationEnabled() ? '<p class="font-body-history-trans text-body-history-trans text-secondary font-medium js-translation-text">' + escapeHtml(translation) + '</p>' : '') +
      '</div>' +
      '<button class="elastic-star p-2 rounded-full hover:bg-tertiary-fixed/50 transition-colors js-bookmark-btn"' +
        (transId ? '' : ' disabled style="opacity:0.4"') + ' title="' + (transId ? '收藏' : '保存中...') + '">' +
        '<span class="material-symbols-outlined text-tertiary text-xl" style="font-variation-settings:' + starFilled + '">star</span></button></div>';
    historySec.appendChild(block);
    scrollHistoryToLatest();
    pruneHistoryDom();

    var bookmarkBtn = block.querySelector('.js-bookmark-btn');
    bookmarkBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      var tid = parseInt(block.getAttribute('data-trans-id'));
      if (!tid) { toast('请稍候，正在保存...'); return; }
      showTagPicker(this, function (tag) {
        api('/bookmarks', { method: 'POST', body: JSON.stringify({ transcription_id: tid, tag: tag }) })
          .then(function () { toast('已收藏'); bookmarkBtn.querySelector('span').style.fontVariationSettings = "'FILL' 1"; })
          .catch(function (e) { toast(e.message || '请先登录'); });
      });
    });
    block.classList.add('subtitle-current');
    scrollHistoryToLatest();
    lastCommittedSource = String(source || '').trim();
    lastCommittedDisplay = preferDisplayText(source, translation) || lastCommittedSource;
    setCurrentSubtitle(source, isTranslationEnabled() ? (translation || '正在翻译…') : '');
    return block;
  }

  function updateBlockTranslation(block, text, isError) {
    if (!block) return;
    var target = block.querySelector('.js-translation-text');
    if (!target) return;
    target.textContent = text;
    target.classList.toggle('text-error', !!isError);
    target.classList.toggle('text-secondary', !isError);
    var sourceEl = block.querySelector('.font-body-history-source');
    var sourceText = sourceEl ? sourceEl.textContent : '';
    if (block.classList.contains('subtitle-current')) {
      setCurrentSubtitle(sourceText, text);
      if (!isError) {
        lastCommittedSource = String(sourceText || '').trim();
        lastCommittedDisplay = preferDisplayText(sourceText, text) || lastCommittedSource;
      }
    } else if (!isError && previousBridgeSource && String(sourceText || '').trim() === previousBridgeSource) {
      setPreviousContext(preferDisplayText(sourceText, text) || sourceText);
    }
  }

  function showLivePreview(text) {
    if (!historySec || !text) return;
    hideFeatureIntro();
    historySec.style.display = '';
    if (lastCommittedDisplay) setPreviousContext(lastCommittedDisplay);
    if (!livePreviewBlock) {
      livePreviewBlock = document.createElement('div');
      livePreviewBlock.className = 'space-y-unit border-l-2 border-primary/40 pl-4 py-2 opacity-70';
      var sourceLine = document.createElement('p');
      sourceLine.className = 'font-body-history-source text-body-history-source text-on-surface js-live-source';
      sourceLine.style.maxHeight = '4.5em';
      sourceLine.style.overflow = 'hidden';
      livePreviewBlock.appendChild(sourceLine);
      if (isTranslationEnabled()) {
        var hintLine = document.createElement('p');
        hintLine.className = 'font-body-history-trans text-body-history-trans text-on-surface-variant js-live-hint';
        hintLine.textContent = '正在识别…';
        livePreviewBlock.appendChild(hintLine);
      }
      historySec.appendChild(livePreviewBlock);
    }
    var shown = text;
    if (shown.length > Math.max(maxSegmentChars * 2, 160)) {
      shown = '…' + shown.slice(-(Math.max(maxSegmentChars * 2, 160) - 1));
    }
    livePreviewBlock.querySelector('.js-live-source').textContent = shown;
    scrollHistoryToLatest();
    setCurrentSubtitle(shown, isTranslationEnabled() ? '正在识别…' : '');
  }

  function clearLivePreview() {
    if (livePreviewBlock) livePreviewBlock.remove();
    livePreviewBlock = null;
  }

  // ─── 浏览器语音识别 (Web Speech API) ──────────────
  function releaseSpeechRecognition() {
    speechDesired = false;
    clearTimeout(recognitionRestartTimer);
    recognitionRestartTimer = null;
    var rec = recognition;
    recognition = null;
    if (!rec) return;
    rec.onresult = null;
    rec.onerror = null;
    rec.onend = null;
    try { rec.stop(); } catch (e) {}
  }

  function startSpeechRecognition(opts) {
    opts = opts || {};
    var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      if (!opts.silent) toast('当前浏览器不支持网页语音识别');
      return false;
    }
    if (recognition && opts.reuseIfRunning) return true;

    releaseSpeechRecognition();
    speechDesired = true;
    lastInterimText = '';
    recognition = new SpeechRecognition();
    recognition.lang = recognitionLocale(selectedSourceLang());
    recognition.interimResults = true;
    recognition.continuous = !isIOSClient();
    recognition.maxAlternatives = 1;

    recognition.onresult = function (event) {
      if (paused) return;
      var interimText = '';
      for (var i = event.resultIndex; i < event.results.length; i++) {
        var piece = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          var text = String(piece || '').trim();
          lastInterimText = '';
          if (text) {
            clearLivePreview();
            statusText.textContent = '正在翻译: ' + text.substring(0, 24);
            enqueueRecognizedText(text);
          }
        } else {
          interimText += piece;
        }
      }
      interimText = interimText.trim();
      if (interimText) {
        lastInterimText = interimText;
        statusText.textContent = '正在识别: ' + interimText.substring(0, 24);
        showLivePreview(interimText);
      }
    };

    recognition.onerror = function (event) {
      console.log('Speech error:', event.error);
      if (event.error === 'not-allowed') {
        toast('麦克风权限被拒绝');
      } else if (event.error === 'network') {
        toast('网页识别不可用，已切换到服务器识别');
        releaseSpeechRecognition();
        liveAsrActive = true;
        if (audioCaptureStream && recording && !paused) {
          startRealtimeStream(audioCaptureStream, lectureId);
        }
      } else if (event.error === 'no-speech') {
        statusText.textContent = '没听清，请再说一次';
      }
    };

    recognition.onend = function () {
      var leftover = String(lastInterimText || '').trim();
      lastInterimText = '';
      if (leftover && !paused) {
        clearLivePreview();
        enqueueRecognizedText(leftover);
      }
      if (speechDesired && !paused && recognition) {
        clearTimeout(recognitionRestartTimer);
        recognitionRestartTimer = setTimeout(function () {
          try {
            recognition.start();
          } catch (e) {
            // 长时间静音后浏览器可能拒绝立刻重启：改走服务器实时，避免掉进演示/空转。
            releaseSpeechRecognition();
            liveAsrActive = true;
            if (audioCaptureStream && recording && !paused) {
              startRealtimeStream(audioCaptureStream, lectureId);
            }
          }
        }, isIOSClient() ? 80 : 250);
      }
    };

    try {
      recognition.start();
      if (!opts.silent) toast('语音识别已启动，请对着手机说话');
      return true;
    } catch (e) {
      if (!opts.silent) toast('语音识别启动失败，请再点一次麦克风');
      return false;
    }
  }

  function translateAndSave(text) {
    if (!lectureId) return;
    var targetLectureId = lectureId;
    var pendingId = ++pendingIdCounter;
    // 原文立即上屏；仅记录模式不会请求翻译服务。
    var translating = isTranslationEnabled();
    var block = addSubtitle(text, translating ? '正在翻译…' : '', false, null);
    if (block) block.setAttribute('data-pending-id', pendingId);

    var translationJob = translating ? api('/translate', {
      method: 'POST',
      body: JSON.stringify({
        text: text, source: selectedSourceLang(), target: selectedTargetLang()
      })
    }).catch(function (error) {
      return {
        translated_text: text,
        success: false,
        warning: error.message || '翻译失败，已保留原文'
      };
    }) : Promise.resolve({ translated_text: text, success: true, provider: 'disabled' });
    var job = translationJob.then(function (result) {
      var translatedText = result.translated_text || text;
      if (translating && result.success === false) {
        updateBlockTranslation(block, result.warning || '翻译服务暂时不可用，已保留原文', true);
        toast(result.warning || '翻译服务暂时不可用');
      } else if (translating) {
        updateBlockTranslation(block, translatedText, false);
      }
      return api('/lectures/' + targetLectureId + '/transcribe/text', {
        method: 'POST',
        body: JSON.stringify({ source_text: text, translated_text: translatedText })
      });
    }).then(function (t) {
      // 更新字幕块：设置真实 ID，启用收藏按钮
      if (block) {
        block.setAttribute('data-trans-id', t.id);
        var btn = block.querySelector('.js-bookmark-btn');
        if (btn) { btn.disabled = false; btn.style.opacity = ''; btn.title = '收藏'; }
      }
      currentSectionTransId = t.id;
    }).catch(function (error) {
      updateBlockTranslation(block, '内容保存失败，请重试', true);
      toast(error.message || '内容保存失败');
    }).finally(function () {
      if (block) block.removeAttribute('data-pending-id');
      pendingJobs.delete(job);
      if (recording && !paused) statusText.textContent = '正在聆听…';
    });
    pendingJobs.add(job);
    return job;
  }

  // 演示模式仅保留兼容函数；课堂录音禁止自动进入，避免静音断连后冒出英文测试句。
  var demoTimer = null;
  function startDemoMode() {
    console.warn('startDemoMode disabled during live recording');
  }

  function pickRecorderMime() {
    if (!window.MediaRecorder) return '';
    var types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/aac', 'audio/mpeg'];
    for (var i = 0; i < types.length; i++) {
      if (MediaRecorder.isTypeSupported(types[i])) return types[i];
    }
    return '';
  }

  function pickVideoMime() {
    if (!window.MediaRecorder) return '';
    var types = ['video/webm;codecs=vp8,opus', 'video/webm', 'video/mp4'];
    for (var i = 0; i < types.length; i++) {
      if (MediaRecorder.isTypeSupported(types[i])) return types[i];
    }
    return '';
  }

  function uploadVideoChunk(blob) {
    if (!lectureId || !blob || !blob.size) return Promise.resolve();
    var formData = new FormData();
    formData.append('file', blob, (blob.type || '').indexOf('mp4') >= 0 ? 'lecture.mp4' : 'lecture.webm');
    formData.append('append', videoUploadStarted ? 'true' : 'false');
    return fetch('/api/lectures/' + lectureId + '/media/video', { method: 'POST', body: formData })
      .then(function (response) {
        if (!response.ok) return response.json().catch(function () { return {}; }).then(function (data) { throw new Error(data.detail || '录像分片上传失败'); });
        videoUploadStarted = true;
        return response.json();
      });
  }

  function frameSignature(canvas) {
    var data = canvas.getContext('2d').getImageData(0, 0, 32, 18).data;
    var total = 0;
    for (var i = 0; i < data.length; i += 16) total += data[i] + data[i + 1] + data[i + 2];
    return total / (data.length / 16);
  }

  function captureVideoFrame() {
    if (!videoEnabled || !capturePreview || !lectureId || !capturePreview.videoWidth) return;
    var small = document.createElement('canvas');
    small.width = 32; small.height = 18;
    small.getContext('2d').drawImage(capturePreview, 0, 0, small.width, small.height);
    var signature = frameSignature(small);
    // 静态画面无需反复存图；显著切换或每约一分钟保留一次兜底关键帧。
    var changed = lastFrameSignature === null || Math.abs(signature - lastFrameSignature) > 12;
    if (!changed && Math.floor((Date.now() - recordingStartedAt) / 1000) % 60 !== 0) return;
    lastFrameSignature = signature;
    var canvas = document.createElement('canvas');
    canvas.width = Math.min(960, capturePreview.videoWidth);
    canvas.height = Math.max(1, Math.round(canvas.width * capturePreview.videoHeight / capturePreview.videoWidth));
    canvas.getContext('2d').drawImage(capturePreview, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(function (blob) {
      if (!blob || !lectureId) return;
      var form = new FormData();
      form.append('file', blob, 'keyframe.jpg');
      form.append('start_offset_ms', String(Math.max(0, Date.now() - recordingStartedAt)));
      fetch('/api/lectures/' + lectureId + '/media/frame', { method: 'POST', body: form }).catch(function () {});
    }, 'image/jpeg', 0.72);
  }

  function startVideoCapture(stream) {
    if (!stream || !stream.getVideoTracks().length || !window.MediaRecorder) return;
    videoEnabled = true;
    videoUploadStarted = false;
    lastFrameSignature = null;
    if (capturePreview) {
      capturePreview.srcObject = stream;
      capturePreview.play().catch(function () {});
    }
    var mime = pickVideoMime();
    try {
      videoRecorder = new MediaRecorder(stream, mime ? { mimeType: mime } : {});
      videoRecorder.addEventListener('dataavailable', function (event) {
        if (!event.data || !event.data.size) return;
        videoUploadQueue = videoUploadQueue.then(function () { return uploadVideoChunk(event.data); }).catch(function (error) {
          toast(error.message || '录像保存失败，录音仍会继续');
        });
      });
      videoRecorder.start(15000);
      videoFrameTimer = setInterval(captureVideoFrame, 10000);
      setTimeout(captureVideoFrame, 1500);
    } catch (error) {
      videoRecorder = null;
      videoEnabled = false;
      toast('摄像头可用，但当前浏览器不支持录像；已继续录音');
    }
  }

  function finishVideoCapture() {
    clearInterval(videoFrameTimer);
    videoFrameTimer = null;
    if (!videoRecorder || videoRecorder.state === 'inactive') return videoUploadQueue;
    return new Promise(function (resolve) {
      videoRecorder.addEventListener('stop', function () { resolve(); }, { once: true });
      try { videoRecorder.stop(); } catch (e) { resolve(); }
    }).then(function () { return videoUploadQueue; }).then(function () {
      videoRecorder = null;
      videoEnabled = false;
    });
  }

  function recorderFileName(mimeType) {
    if ((mimeType || '').indexOf('mp4') !== -1 || (mimeType || '').indexOf('aac') !== -1) return 'lecture.m4a';
    if ((mimeType || '').indexOf('mpeg') !== -1) return 'lecture.mp3';
    return 'lecture.webm';
  }

  function errorDetail(d, fallback) {
    if (!d) return fallback;
    if (typeof d.detail === 'string') return d.detail;
    if (Array.isArray(d.detail) && d.detail[0]) {
      return d.detail[0].msg || d.detail[0].detail || fallback;
    }
    return fallback;
  }

  function uploadAsrSegment(blob) {
    if (!lectureId || !blob || !blob.size) return Promise.resolve();
    var formData = new FormData();
    formData.append('file', blob, recorderFileName(blob.type));
    formData.append('append', 'true');
    statusText.textContent = '正在识别…';
    var job = fetch('/api/lectures/' + lectureId + '/transcribe/audio', {
      method: 'POST',
      body: formData
    }).then(function (r) {
      if (r.status === 204) return null;
      return r.json().then(function (d) {
        if (!r.ok) throw new Error(errorDetail(d, '识别失败'));
        return d;
      });
    }).then(function (t) {
      if (!t || !t.source_text) {
        if (recording && !paused) statusText.textContent = '正在聆听…';
        return;
      }
      addSubtitle(t.source_text, t.translated_text, t.is_bookmarked, t.id);
      currentSectionTransId = t.id;
      if (recording && !paused) statusText.textContent = '正在聆听…';
    }).catch(function (error) {
      if (recording && !paused) statusText.textContent = '正在聆听…';
      toast(error.message || '语音识别失败');
    });
    pendingJobs.add(job);
    job.finally(function () { pendingJobs.delete(job); });
    return job;
  }

  function stopSegmentLoop() {
    segmentLoopActive = false;
    clearTimeout(segmentTimer);
    segmentTimer = null;
    var rec = segmentRecorder;
    segmentRecorder = null;
    if (!rec || rec.state === 'inactive') return Promise.resolve();
    return new Promise(function (resolve) {
      rec.addEventListener('stop', function () { resolve(); }, { once: true });
      try { rec.stop(); } catch (e) { resolve(); }
    });
  }

  function ensureAudioContext() {
    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    if (!audioContext) audioContext = new Ctx();
    if (audioContext.state === 'suspended') {
      audioContext.resume().catch(function () {});
    }
    return audioContext;
  }

  function downsampleBuffer(buffer, fromRate, toRate) {
    if (fromRate === toRate) return buffer;
    var ratio = fromRate / toRate;
    var newLen = Math.floor(buffer.length / ratio);
    var result = new Float32Array(newLen);
    for (var i = 0; i < newLen; i++) result[i] = buffer[Math.floor(i * ratio)];
    return result;
  }

  function floatTo16BitPCM(buffer) {
    var out = new Int16Array(buffer.length);
    for (var i = 0; i < buffer.length; i++) {
      var s = Math.max(-1, Math.min(1, buffer[i]));
      out[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return out;
  }

  var realtimeReconnectTimer = null;
  var realtimeReconnectAttempts = 0;
  var realtimeAllowReconnect = false;
  var REALTIME_MAX_RECONNECT = 8;

  function clearRealtimeReconnect() {
    if (realtimeReconnectTimer) {
      clearTimeout(realtimeReconnectTimer);
      realtimeReconnectTimer = null;
    }
  }

  function stopRealtimeStream(sendFinish) {
    realtimeAllowReconnect = false;
    clearRealtimeReconnect();
    realtimeActive = false;
    if (audioProcessor) {
      audioProcessor.onaudioprocess = null;
      try { audioProcessor.disconnect(); } catch (e) {}
      audioProcessor = null;
    }
    if (audioSource) {
      try { audioSource.disconnect(); } catch (e) {}
      audioSource = null;
    }
    if (audioMute) {
      try { audioMute.disconnect(); } catch (e) {}
      audioMute = null;
    }
    if (realtimeSocket) {
      try {
        if (sendFinish && realtimeSocket.readyState === 1) {
          realtimeSocket.send(JSON.stringify({ type: 'finish' }));
        }
        realtimeSocket.onclose = null;
        realtimeSocket.close();
      } catch (e) {}
      realtimeSocket = null;
    }
  }

  function connectPcmPump(ctx, stream, ws, targetRate, frameMs) {
    audioSource = ctx.createMediaStreamSource(stream);
    audioProcessor = ctx.createScriptProcessor(4096, 1, 1);
    audioMute = ctx.createGain();
    audioMute.gain.value = 0;
    var pending = new Float32Array(0);
    var frameSamples = Math.max(160, Math.round(targetRate * frameMs / 1000));
    audioProcessor.onaudioprocess = function (event) {
      if (!realtimeActive || !ws || ws.readyState !== 1) return;
      var input = event.inputBuffer.getChannelData(0);
      var resampled = downsampleBuffer(input, ctx.sampleRate, targetRate);
      var merged = new Float32Array(pending.length + resampled.length);
      merged.set(pending);
      merged.set(resampled, pending.length);
      var offset = 0;
      while (merged.length - offset >= frameSamples) {
        var frame = merged.subarray(offset, offset + frameSamples);
        try { ws.send(floatTo16BitPCM(frame).buffer); } catch (e) { return; }
        offset += frameSamples;
      }
      pending = merged.slice(offset);
    };
    audioSource.connect(audioProcessor);
    audioProcessor.connect(audioMute);
    audioMute.connect(ctx.destination);
  }

  function startRealtimeStream(stream, lid) {
    var ctx = ensureAudioContext();
    var token = localStorage.getItem('livetrans_token');
    if (!ctx || !token || !lid || !stream) {
      startSegmentLoop(stream);
      return;
    }
    clearRealtimeReconnect();
    // 清理旧连接，但不关闭自动重连开关（由 stopRealtimeStream 显式关闭）。
    realtimeActive = false;
    if (audioProcessor) {
      audioProcessor.onaudioprocess = null;
      try { audioProcessor.disconnect(); } catch (e) {}
      audioProcessor = null;
    }
    if (audioSource) {
      try { audioSource.disconnect(); } catch (e) {}
      audioSource = null;
    }
    if (audioMute) {
      try { audioMute.disconnect(); } catch (e) {}
      audioMute = null;
    }
    if (realtimeSocket) {
      try { realtimeSocket.onclose = null; realtimeSocket.close(); } catch (e) {}
      realtimeSocket = null;
    }

    realtimeAllowReconnect = true;
    realtimeActive = true;
    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var ws = new WebSocket(proto + '//' + location.host + '/api/lectures/' + lid + '/stream');
    realtimeSocket = ws;
    ws.binaryType = 'arraybuffer';
    var fallbackStarted = false;
    var handledClose = false;

    function fallback(reason) {
      if (fallbackStarted || !recording || paused) return;
      fallbackStarted = true;
      realtimeAllowReconnect = false;
      clearRealtimeReconnect();
      stopRealtimeStream(false);
      startSegmentLoop(stream);
      if (reason) toast(reason);
    }

    function scheduleReconnect(reason) {
      if (!realtimeAllowReconnect || !recording || paused || stopping || fallbackStarted) return;
      if (realtimeReconnectAttempts >= REALTIME_MAX_RECONNECT) {
        fallback(reason || '实时识别多次中断，已切换分片识别');
        return;
      }
      realtimeReconnectAttempts += 1;
      var delay = Math.min(800 * realtimeReconnectAttempts, 5000);
      statusText.textContent = '识别重连中…';
      if (realtimeReconnectAttempts === 1) {
        toast(reason || '识别连接中断，正在自动重连');
      }
      clearRealtimeReconnect();
      realtimeReconnectTimer = setTimeout(function () {
        realtimeReconnectTimer = null;
        if (!realtimeAllowReconnect || !recording || paused || stopping) return;
        startRealtimeStream(stream, lid);
      }, delay);
    }

    ws.onopen = function () {
      realtimeReconnectAttempts = 0;
      ws.send(JSON.stringify({ type: 'auth', token: token, offset_ms: streamOffsetMs || 0 }));
    };
    ws.onmessage = function (event) {
      var msg;
      try { msg = JSON.parse(event.data); } catch (e) { return; }
      if (!msg || !msg.type) return;
      if (msg.type === 'ready') {
        if (msg.history_dom_limit) historyDomLimit = Number(msg.history_dom_limit) || historyDomLimit;
        if (msg.max_segment_chars) maxSegmentChars = Number(msg.max_segment_chars) || maxSegmentChars;
        if (msg.merge_min_chars) mergeMinChars = Number(msg.merge_min_chars) || mergeMinChars;
        if (msg.merge_wait_ms) mergeWaitMs = Number(msg.merge_wait_ms) || mergeWaitMs;
        try {
          connectPcmPump(ctx, stream, ws, msg.sample_rate || 16000, msg.frame_duration_ms || 160);
          setCurrentSubtitle('正在聆听…', '边说边出字');
          if (recording && !paused) statusText.textContent = '正在聆听…';
        } catch (err) {
          fallback('当前浏览器不支持实时音频，已切换分片识别');
        }
        return;
      }
      if (msg.type === 'info' && msg.code === 'asr_task_resumed') {
        if (recording && !paused) statusText.textContent = '正在聆听…';
        return;
      }
      if (msg.reconnect && !msg.fallback) {
        handledClose = true;
        scheduleReconnect(msg.message || '识别中断，正在重连');
        return;
      }
      if (msg.fallback) {
        fallback(msg.message || '已切换分片识别');
        return;
      }
      if (msg.type === 'interim' || msg.type === 'finalizing') {
        showLivePreview(msg.source_text);
        setCurrentSubtitle(msg.source_text, '正在翻译…');
        statusText.textContent = '正在识别: ' + String(msg.source_text || '').substring(0, 24);
      }
      if (msg.type === 'preview') {
        setCurrentSubtitle(msg.source_text, msg.translated_text || '正在翻译…');
      }
      if (msg.type === 'final' && msg.transcription) {
        var t = msg.transcription;
        clearLivePreview();
        addSubtitle(t.source_text, t.translated_text, t.is_bookmarked, t.id);
        currentSectionTransId = t.id;
        if (recording && !paused) statusText.textContent = '正在聆听…';
      }
    };
    ws.onerror = function () {
      // 交给 onclose 统一走自动重连，避免静音断连直接掉进降级。
    };
    ws.onclose = function () {
      if (handledClose || fallbackStarted) return;
      if (!realtimeAllowReconnect || !recording || paused || stopping) return;
      scheduleReconnect('识别连接中断，正在自动重连');
    };
  }

  function startSegmentLoop(stream) {
    if (!stream) return;
    audioCaptureStream = stream;
    liveAsrActive = true;
    segmentLoopActive = true;
    function run() {
      if (!segmentLoopActive || paused || !audioCaptureStream) return;
      if (!window.MediaRecorder) {
        toast('当前浏览器无法录音识别，请用 Safari 或 Chrome 打开');
        return;
      }
      var mime = pickRecorderMime();
      var rec;
      try {
        rec = new MediaRecorder(audioCaptureStream, mime ? { mimeType: mime } : {});
      } catch (err) {
        toast('当前手机浏览器无法录音，请用 Safari 或系统浏览器打开');
        return;
      }
      segmentRecorder = rec;
      var parts = [];
      rec.addEventListener('dataavailable', function (e) {
        if (e.data && e.data.size) parts.push(e.data);
      });
      rec.addEventListener('stop', function () {
        var blob = new Blob(parts, { type: rec.mimeType || mime || 'audio/webm' });
        if (blob.size > 800 && lectureId) uploadAsrSegment(blob);
        if (segmentLoopActive && !paused && audioCaptureStream) {
          segmentTimer = setTimeout(run, 80);
        }
      });
      try {
        rec.start();
      } catch (err) {
        toast('录音启动失败，请再点一次麦克风');
        return;
      }
      segmentTimer = setTimeout(function () {
        if (rec.state === 'recording') {
          try { rec.stop(); } catch (e) {}
        }
      }, 2000);
    }
    run();
  }

  function startAudioCapture(stream, append) {
    audioCaptureStream = stream;
    if (!append) audioChunks = [];
    if (append && mediaRecorder && mediaRecorder.state === 'paused') {
      try { mediaRecorder.resume(); return; } catch (e) {}
    }
    if (append && mediaRecorder && mediaRecorder.state === 'recording') return;
    if (!window.MediaRecorder) {
      return;
    }
    var mime = pickRecorderMime();
    var options = mime ? { mimeType: mime } : {};
    try {
      mediaRecorder = new MediaRecorder(stream, options);
      mediaRecorder.addEventListener('dataavailable', function (event) {
        if (event.data && event.data.size) audioChunks.push(event.data);
      });
      mediaRecorder.start(1000);
    } catch (error) {
      mediaRecorder = null;
      toast('浏览器不支持保存本次录音，但实时识别仍可使用');
    }
  }

  function finishAudioCapture(lid) {
    liveAsrActive = false;
    if (!mediaRecorder || mediaRecorder.state === 'inactive') {
      return Promise.resolve();
    }
    return new Promise(function (resolve) {
      mediaRecorder.addEventListener('stop', function () {
        var mimeType = mediaRecorder.mimeType || 'audio/webm';
        var blob = new Blob(audioChunks, { type: mimeType });
        mediaRecorder = null;
        audioChunks = [];
        if (!blob.size) { resolve(); return; }
        var formData = new FormData();
        formData.append('file', blob, 'lecture.webm');
        fetch('/api/lectures/' + lid + '/audio', {
          method: 'POST',
          body: formData
        }).then(function (response) {
          if (!response.ok) {
            return response.json().catch(function () { return {}; }).then(function (data) {
              throw new Error(data.detail || '音频上传失败');
            });
          }
          return response.json();
        }).then(function () {
          resolve();
        }).catch(function (error) {
          toast(error.message || '音频保存失败，文字记录已保留');
          resolve();
        });
      }, { once: true });
      mediaRecorder.stop();
    });
  }

  function continueAudioCapture() {
    if (!audioCaptureStream) return;
    if (mediaRecorder && mediaRecorder.state === 'paused') {
      try { mediaRecorder.resume(); } catch (e) {}
      return;
    }
    if (mediaRecorder && mediaRecorder.state === 'recording') return;
    var mime = pickRecorderMime();
    var options = mime ? { mimeType: mime } : {};
    try {
      mediaRecorder = new MediaRecorder(audioCaptureStream, options);
      mediaRecorder.addEventListener('dataavailable', function (event) {
        if (event.data && event.data.size) audioChunks.push(event.data);
      });
      mediaRecorder.start(1000);
    } catch (error) {
      mediaRecorder = null;
    }
  }

  function setSessionChrome(mode) {
    if (mode === 'recording') {
      recordIcon.textContent = 'mic_off';
      recordBtn.style.background = '#EF4444';
      recordBtn.style.animation = 'pulse-red 2s infinite';
      recordBtn.title = '结束录音';
      pauseBtn.querySelector('span').textContent = 'pause';
      pauseBtn.title = '暂停';
      statusDot.classList.add('animate-pulse');
      statusText.textContent = '正在聆听…';
    } else if (mode === 'paused') {
      recordIcon.textContent = 'mic';
      recordBtn.style.background = '#4CAF50';
      recordBtn.style.animation = '';
      recordBtn.title = '继续录制';
      pauseBtn.querySelector('span').textContent = 'play_arrow';
      pauseBtn.title = '继续';
      statusDot.classList.remove('animate-pulse');
      statusText.textContent = '已暂停';
    } else {
      recordIcon.textContent = 'mic';
      recordBtn.style.background = '#4CAF50';
      recordBtn.style.animation = '';
      recordBtn.title = '开始录音';
      pauseBtn.querySelector('span').textContent = 'pause';
      pauseBtn.title = '暂停';
      statusDot.classList.remove('animate-pulse');
      statusText.textContent = '待机中';
    }
  }

  function clearTranscriptUi() {
    clearLivePreview();
    hideCurrentSubtitle();
    if (historySec) {
      historySec.innerHTML = '';
      historySec.style.display = 'none';
    }
    currentSectionTransId = null;
  }

  function restoreTranscriptions(lid) {
    if (!lid) return Promise.resolve([]);
    return api('/lectures/' + lid + '/transcriptions?limit=400').then(function (items) {
      items = items || [];
      if (!items.length) {
        if (historySec && historySec.children.length) historySec.style.display = '';
        return items;
      }
      hideFeatureIntro();
      items.forEach(function (t) {
        if (historySec && historySec.querySelector('[data-trans-id="' + t.id + '"]')) return;
        addSubtitle(t.source_text, t.translated_text, t.is_bookmarked, t.id);
      });
      return items;
    }).catch(function () { return []; });
  }

  function refreshStreamOffset(lecture, transcriptions) {
    var fromDuration = Math.max(0, Number(lecture && lecture.duration_seconds || 0) * 1000);
    var fromSentences = 0;
    (transcriptions || []).forEach(function (t) {
      fromSentences = Math.max(
        fromSentences,
        Number(t.end_offset_ms || 0),
        Number(t.start_offset_ms || 0)
      );
    });
    streamOffsetMs = Math.max(fromDuration, fromSentences, streamOffsetMs || 0);
    return streamOffsetMs;
  }

  function keepExistingTranscript(lecture) {
    if (!lecture) return false;
    if (lectureId && lecture.id === lectureId) return true;
    return (lecture.sentence_count || 0) > 0;
  }

  // ─── 开始/停止 ───────────────────────────────────
  async function startRecording() {
    if (lectureId && (paused || recording)) {
      if (paused) resumeRecording();
      return;
    }

    var useServerAsr = preferServerAsr();
    liveAsrActive = useServerAsr;
    var wantsVideo = Boolean(videoToggle && videoToggle.checked);
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        video: wantsVideo ? { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 20, max: 24 } } : false
      });
    } catch (e) {
      if (wantsVideo) {
        try {
          mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
          });
          toast('摄像头不可用，已自动切换为仅录音');
        } catch (audioError) {
          toast('麦克风权限被拒绝，请在系统设置里允许浏览器使用麦克风');
          releaseSpeechRecognition();
          return;
        }
      } else {
        toast('麦克风权限被拒绝，请在系统设置里允许浏览器使用麦克风');
        releaseSpeechRecognition();
        return;
      }
    }

    api('/lectures/start', {
      method: 'POST',
      body: JSON.stringify({
        course_id: selectedCourseId(),
        course_name: selectedCourseId() ? ((coursesById[String(selectedCourseId())] || {}).name || '课堂录音') : '课堂录音',
        source_lang: selectedSourceLang(),
        target_lang: selectedTargetLang(),
        translation_enabled: isTranslationEnabled(),
        force_new: !!startForceNew
      })
    }).then(function (l) {
      var continuing = keepExistingTranscript(l) || !!pendingActiveLecture;
      startForceNew = false;
      hideResumeBanner();
      lectureId = l.id;
      recordingStartedAt = Date.now();
      recording = true;
      stopping = false;
      paused = false;
      currentSectionTransId = null;
      if (!continuing) clearTranscriptUi();
      hideFeatureIntro();
      courseName.textContent = l.course_name;
      setTranslationEnabled(l.translation_enabled !== false);
      setSessionChrome('recording');
      if (!pendingPhrases.length) {
        setCurrentSubtitle('正在聆听…', isTranslationEnabled() ? (useServerAsr ? '请对着手机说话，字幕会尽快出现' : '说完一句后会显示原文和翻译') : '');
      }
      if (sourceLangSelect) sourceLangSelect.disabled = true;
      if (targetLangSelect) targetLangSelect.disabled = true;
      if (translationToggle) translationToggle.disabled = true;
      if (videoToggle) videoToggle.disabled = true;
      if (courseSelect) courseSelect.disabled = true;

      function beginCapture() {
        startWave();
        var audioStream = audioOnlyStream();
        if (mediaStream && mediaStream.getVideoTracks().length) startVideoCapture(mediaStream);
        if (useServerAsr) {
          releaseSpeechRecognition();
          startRealtimeStream(audioStream, lectureId);
        } else {
          startAudioCapture(audioStream, continuing);
          if (hasSpeechRecognition()) {
            if (!recognition) startSpeechRecognition({ silent: continuing });
          } else {
            startSegmentLoop(audioStream);
          }
        }
        flushPendingPhrases();
      }

      if (continuing) {
        restoreTranscriptions(l.id).then(function (items) {
          refreshStreamOffset(l, items);
          beginCapture();
          toast(appendBootstrapDone ? '补录已开始，前文仍在' : '已继续上一堂未结束的课，前文仍在');
        });
      } else {
        streamOffsetMs = 0;
        beginCapture();
      }
    }).catch(function (error) {
      stopRealtimeStream(false);
      stopSegmentLoop();
      releaseCaptureStreams();
      liveAsrActive = false;
      releaseSpeechRecognition();
      toast(error.message || '课堂启动失败，请重新登录');
    });
  }

  function stopRecording() {
    recording = false;
    stopping = true;
    paused = false;
    setSessionChrome('idle');
    stopWave();
    clearInterval(demoTimer);
    demoTimer = null;
    flushMergeBuffer();
    clearLivePreview();
    releaseSpeechRecognition();
    stopRealtimeStream(true);
    if (!lectureId) { releaseCaptureStreams(); stopping = false; return; }
    var lid = lectureId;
    var wrap = stopSegmentLoop().then(function () {
      return finishAudioCapture(lid);
    }).then(function () {
      return finishVideoCapture();
    }).then(function () {
      releaseCaptureStreams();
    });
    pendingJobs.add(wrap);
    wrap.finally(function () { pendingJobs.delete(wrap); });

    statusText.textContent = '正在完成识别并保存…';
    setTimeout(function () {
      Promise.allSettled(Array.from(pendingJobs)).then(function () {
        lectureId = null;
        return api('/lectures/' + lid + '/stop', { method: 'POST' });
      }).then(function (l) {
        stopping = false;
        statusText.textContent = '待机中';
        if (sourceLangSelect) sourceLangSelect.disabled = false;
        if (translationToggle) translationToggle.disabled = false;
        if (videoToggle) videoToggle.disabled = false;
        if (courseSelect) courseSelect.disabled = false;
        syncTranslationModeUi();
        showFeatureIntroIfIdle();
        showNameModal(l);
      }).catch(function () {
        stopping = false;
        lectureId = null;
        if (sourceLangSelect) sourceLangSelect.disabled = false;
        if (translationToggle) translationToggle.disabled = false;
        if (videoToggle) videoToggle.disabled = false;
        if (courseSelect) courseSelect.disabled = false;
        syncTranslationModeUi();
        showFeatureIntroIfIdle();
        toast('停止失败');
      });
    }, 500);
  }

  // ─── 命名弹窗 ───────────────────────────────────
  function formatDurationSeconds(total) {
    var seconds = Math.max(0, Math.floor(Number(total) || 0));
    var hours = Math.floor(seconds / 3600);
    var minutes = Math.floor((seconds % 3600) / 60);
    var rest = seconds % 60;
    if (hours > 0) {
      return hours + ' 小时 ' + minutes + ' 分';
    }
    if (minutes > 0) {
      return minutes + ' 分 ' + String(rest).padStart(2, '0') + ' 秒';
    }
    return rest + ' 秒';
  }

  function hideResumeBanner() {
    pendingActiveLecture = null;
    if (resumeBanner) resumeBanner.classList.add('hidden');
  }

  function showResumeBanner(lecture) {
    if (!resumeBanner || !lecture) return;
    pendingActiveLecture = lecture;
    var title = lecture.title || lecture.course_name || '未命名课堂';
    var bits = [];
    bits.push(title);
    bits.push((lecture.sentence_count || 0) + ' 句');
    if (lecture.duration_seconds > 0) bits.push(formatDurationSeconds(lecture.duration_seconds));
    else if (lecture.started_at) {
      var started = String(lecture.started_at).replace('T', ' ').substring(0, 16);
      bits.push('开始于 ' + started);
    }
    if (lecture.status === 'paused') bits.push('已暂停');
    else bits.push('异常中断可续录');
    if (resumeBannerInfo) resumeBannerInfo.textContent = bits.join(' · ');
    resumeBanner.classList.remove('hidden');
  }

  function checkActiveLecture() {
    if (!isLoggedIn() || recording || paused || stopping) return;
    api('/lectures/active').then(function (lecture) {
      if (!lecture || !lecture.id) {
        hideResumeBanner();
        return;
      }
      if (lecture.status === 'recording' || lecture.status === 'paused') {
        showResumeBanner(lecture);
      } else {
        hideResumeBanner();
      }
    }).catch(function () {
      hideResumeBanner();
    });
  }

  function pauseLectureBestEffort() {
    if (!lectureId || !recording || paused || stopping) return;
    var token = localStorage.getItem('livetrans_token');
    if (!token) return;
    try {
      fetch('/api/lectures/' + lectureId + '/pause', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token },
        keepalive: true
      }).catch(function () {});
    } catch (e) {}
  }

  function formatLectureClock(value) {
    if (!value) return '';
    var text = String(value);
    var datePart = text.split('T')[0] || '';
    var timePart = (text.split('T')[1] || '').substring(0, 5);
    if (!datePart) return '';
    return timePart ? (datePart + ' ' + timePart) : datePart;
  }

  function formatAudioSize(bytes) {
    var size = Number(bytes) || 0;
    if (size <= 0) return '';
    if (size < 1024 * 1024) return Math.max(1, Math.round(size / 1024)) + ' KB';
    return (size / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function escapeModalText(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function showNameModal(lecture) {
    var lid = lecture.id;
    var count = lecture.sentence_count || 0;
    var duration = lecture.duration_seconds || 0;
    var bookmarks = lecture.bookmark_count || 0;
    var automaticTitle = lecture.title || (
      lecture.course_id && lecture.session_number
        ? lecture.course_name + ' · 第 ' + lecture.session_number + ' 节课'
        : (lecture.course_name || '课堂录音')
    );
    var summaryEl = document.getElementById('nameModalSummary');
    var metaEl = document.getElementById('nameModalMeta');
    var summaryBits = ['共 ' + count + ' 句话'];
    if (duration > 0) summaryBits.push('时长 ' + formatDurationSeconds(duration));
    if (summaryEl) summaryEl.textContent = summaryBits.join(' · ');

    var rows = [];
    if (lecture.course_name) {
      rows.push(['课程', lecture.course_name + (lecture.session_number ? ' · 第 ' + lecture.session_number + ' 节' : '')]);
    }
    var started = formatLectureClock(lecture.started_at);
    var ended = formatLectureClock(lecture.ended_at);
    if (started && ended) {
      var endClock = ended.indexOf(' ') >= 0 ? ended.slice(ended.indexOf(' ') + 1) : ended;
      rows.push(['时间', started + ' — ' + endClock]);
    } else if (started) {
      rows.push(['开始', started]);
    } else if (lecture.lecture_date) {
      rows.push(['日期', String(lecture.lecture_date)]);
    }
    if (lecture.source_lang || lecture.target_lang) {
      var langLine = (lecture.source_lang || '?') + ' → ' + (lecture.target_lang || '?');
      if (lecture.translation_enabled === false) langLine += '（仅录音）';
      rows.push(['语言', langLine]);
    }
    if (bookmarks > 0) rows.push(['收藏', bookmarks + ' 处重点']);
    if (lecture.audio_url || lecture.audio_size_bytes) {
      var audioLine = lecture.audio_url ? '已保存录音' : '录音处理中';
      var sizeText = formatAudioSize(lecture.audio_size_bytes);
      if (sizeText) audioLine += ' · ' + sizeText;
      rows.push(['音频', audioLine]);
    }
    if (lecture.room || lecture.location_name) {
      rows.push(['地点', [lecture.location_name, lecture.room].filter(Boolean).join(' · ')]);
    }
    if (metaEl) {
      if (!rows.length) {
        metaEl.innerHTML = '<p class="text-xs">可修改标题后保存，或点跳过使用默认名称。</p>';
      } else {
        metaEl.innerHTML = rows.map(function (row) {
          return '<div class="flex gap-3">'
            + '<span class="w-10 shrink-0 text-xs font-medium text-on-surface-variant/80">' + escapeModalText(row[0]) + '</span>'
            + '<span class="flex-1 text-on-surface leading-5">' + escapeModalText(row[1]) + '</span>'
            + '</div>';
        }).join('');
      }
    }

    document.getElementById('nameInput').value = automaticTitle;
    document.getElementById('nameModal').classList.remove('hidden');
    document.getElementById('nameInput').focus();
    document.getElementById('nameInput').select();

    function save() {
      var name = document.getElementById('nameInput').value.trim();
      document.getElementById('nameModal').classList.add('hidden');
      if (name) {
        api('/lectures/' + lid + '/rename', {
          method: 'PUT', body: JSON.stringify({ title: name })
        }).then(function () { toast('已命名: ' + name); });
      }
      cleanup();
    }
    function cancel() {
      document.getElementById('nameModal').classList.add('hidden');
      cleanup();
    }
    function cleanup() {
      document.getElementById('nameSave').removeEventListener('click', save);
      document.getElementById('nameCancel').removeEventListener('click', cancel);
      document.getElementById('nameInput').removeEventListener('keydown', onKey);
    }
    function onKey(e) {
      if (e.key === 'Enter') save();
      if (e.key === 'Escape') cancel();
    }
    document.getElementById('nameSave').addEventListener('click', save);
    document.getElementById('nameCancel').addEventListener('click', cancel);
    document.getElementById('nameInput').addEventListener('keydown', onKey);
  }

  recordBtn.addEventListener('click', function () {
    if (stopping) { toast('正在保存最后一句，请稍候…'); return; }
    if (paused) {
      resumeRecording();
      return;
    }
    if (!recording && requireAuth('recorder.html', '登录或注册后即可开始实时翻译')) return;
    if (recording) {
      stopRecording();
      return;
    }
    if (!preferServerAsr() && hasSpeechRecognition()) {
      startSpeechRecognition({ silent: false, reuseIfRunning: true });
    }
    if (preferServerAsr()) ensureAudioContext();
    startRecording();
  });

  // ─── 暂停/恢复 ───────────────────────────────────
  function pauseRecording() {
    if (!recording || paused || !lectureId) return;
    paused = true;
    setSessionChrome('paused');
    stopWave();
    clearInterval(demoTimer);
    demoTimer = null;
    flushMergeBuffer();
    clearLivePreview();
    releaseSpeechRecognition();
    stopRealtimeStream(true);
    stopSegmentLoop();
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      try { mediaRecorder.pause(); } catch (e) {}
    }
    if (videoRecorder && videoRecorder.state === 'recording') {
      try { videoRecorder.pause(); } catch (e) {}
    }
    api('/lectures/' + lectureId + '/pause', { method: 'POST' })
      .then(function () { toast('已暂停，点绿色麦克风继续，前文会保留'); })
      .catch(function (error) { toast(error.message || '暂停状态同步失败'); });
    if (historySec && historySec.children.length) historySec.style.display = '';
    hideCurrentSubtitle();
  }

  function resumeRecording() {
    if (!lectureId || !paused) return;
    function applyResume() {
      paused = false;
      recording = true;
      hideFeatureIntro();
      if (historySec && historySec.children.length) historySec.style.display = '';
      setSessionChrome('recording');
      startWave();
      continueAudioCapture();
      if (videoRecorder && videoRecorder.state === 'paused') {
        try { videoRecorder.resume(); } catch (e) {}
      }
      if (preferServerAsr() || liveAsrActive) {
        startRealtimeStream(audioCaptureStream, lectureId);
      } else if (hasSpeechRecognition()) {
        if (!recognition) startSpeechRecognition({ silent: true });
      }
      restoreTranscriptions(lectureId);
      toast('已继续，前文仍在本堂课中');
    }
    api('/lectures/' + lectureId + '/resume', { method: 'POST' })
      .then(applyResume)
      .catch(function () { applyResume(); });
  }

  pauseBtn.addEventListener('click', function () {
    paused ? resumeRecording() : pauseRecording();
  });

  if (starBtn) starBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    if (!currentSectionTransId) { toast('请稍候，正在保存...'); return; }
    var self = this;
    var isFilled = self.style.fontVariationSettings.indexOf("'FILL' 1") !== -1;
    if (isFilled) {
      self.style.fontVariationSettings = "'FILL' 0";
      toast('已取消收藏');
    } else {
      showTagPicker(self, function (tag) {
        api('/bookmarks', { method: 'POST', body: JSON.stringify({ transcription_id: currentSectionTransId, tag: tag }) })
          .then(function () { toast('已收藏'); self.style.fontVariationSettings = "'FILL' 1"; })
          .catch(function (e) { toast(e.message || '请先登录'); });
      });
    }
  });

  loadGuide();
  loadLanguagePreferences();
  loadCourseOptions();
  startWave();

  function bootstrapAppendFromQuery() {
    var params = new URLSearchParams(window.location.search || '');
    var appendId = Number(params.get('append') || 0);
    if (!Number.isInteger(appendId) || appendId <= 0) {
      checkActiveLecture();
      return;
    }
    if (!isLoggedIn()) {
      requireAuth('recorder.html?append=' + appendId, '登录后即可追加录音');
      return;
    }
    api('/lectures/' + appendId + '/append', { method: 'POST' })
      .then(function (lecture) {
        appendBootstrapDone = true;
        pendingActiveLecture = lecture;
        hideResumeBanner();
        if (lecture.course_id && courseSelect) {
          courseSelect.value = String(lecture.course_id);
        }
        if (lecture.course_name) courseName.textContent = lecture.course_name;
        setTranslationEnabled(lecture.translation_enabled !== false);
        toast('正在打开补录…');
        return startRecording();
      })
      .catch(function (error) {
        appendBootstrapDone = false;
        toast(error.message || '无法开始补录');
        checkActiveLecture();
      })
      .finally(function () {
        try {
          var clean = window.location.pathname.split('/').pop() || 'recorder.html';
          window.history.replaceState({}, '', clean);
        } catch (e) {}
      });
  }

  bootstrapAppendFromQuery();

  if (resumeContinueBtn) {
    resumeContinueBtn.addEventListener('click', function () {
      startForceNew = false;
      if (!requireAuth('recorder.html', '登录后即可继续未结束的课堂')) return;
      startRecording();
    });
  }
  if (resumeFinishBtn) {
    resumeFinishBtn.addEventListener('click', function () {
      var active = pendingActiveLecture;
      if (!active || !active.id) {
        hideResumeBanner();
        return;
      }
      if (!requireAuth('recorder.html', '登录后即可管理课堂')) return;
      resumeFinishBtn.disabled = true;
      api('/lectures/' + active.id + '/stop', { method: 'POST' })
        .then(function (lecture) {
          hideResumeBanner();
          toast('旧课堂已结束，可开始新的录制');
          if (lecture && lecture.id) showNameModal(lecture);
        })
        .catch(function (error) {
          toast(error.message || '结束旧课堂失败');
        })
        .finally(function () {
          resumeFinishBtn.disabled = false;
        });
    });
  }

  window.addEventListener('pagehide', pauseLectureBestEffort);
  window.addEventListener('beforeunload', pauseLectureBestEffort);
})();
