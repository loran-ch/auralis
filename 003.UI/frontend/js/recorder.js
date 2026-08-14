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
  var mediaRecorder = null;
  var audioChunks = [];
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
  var currentSourceEl = document.getElementById('current-source');
  var currentTargetEl = document.getElementById('current-target');
  var currentSectionEl = document.getElementById('current-section');

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
    return targetLangSelect && targetLangSelect.value ? targetLangSelect.value : 'zh-CN';
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
        default_target_lang: selectedTargetLang()
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

  if (sourceLangSelect) sourceLangSelect.addEventListener('change', saveLanguagePreferences);
  if (targetLangSelect) targetLangSelect.addEventListener('change', saveLanguagePreferences);

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

  function setCurrentSubtitle(source, translation) {
    if (!currentSectionEl) return;
    currentSectionEl.style.display = '';
    if (currentSourceEl) currentSourceEl.textContent = source || '';
    if (currentTargetEl) currentTargetEl.textContent = translation || '';
  }

  function hideCurrentSubtitle() {
    if (currentSectionEl) currentSectionEl.style.display = 'none';
    if (currentSourceEl) currentSourceEl.textContent = '';
    if (currentTargetEl) currentTargetEl.textContent = '';
  }

  function enqueueRecognizedText(text) {
    text = String(text || '').trim();
    if (!text) return;
    if (!lectureId) {
      pendingPhrases.push(text);
      setCurrentSubtitle(text, '正在启动课堂…');
      showLivePreview(text);
      return;
    }
    translateAndSave(text);
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
  var GUIDE_COLORS = ['primary', 'secondary', 'tertiary', 'primary', 'accent-purple'];
  var currentGuide = {
    title: '课堂实时翻译助手',
    subtitle: '听外语课、记重点、课后复习。打开就能看它能做什么。',
    footer_hint: '点下方绿色麦克风开始 · 未登录会提示注册',
    items: [
      { icon: 'subtitles', title: '实时双语字幕', body: '授课语音转文字，原文和译文同步出现，像字幕一样往下走。' },
      { icon: 'translate', title: '多语种听译', body: '选择授课语言和你的母语，适合留学课堂、讲座和讨论课。' },
      { icon: 'star', title: '一键收藏知识点', body: '把句子标成重要、疑问、考点或定义，课后变成知识卡片。' },
      { icon: 'history', title: '课堂回看', body: '保存完整记录和录音，双语对照回放，从收藏处跳回原句。' },
      { icon: 'psychology', title: '课后课堂助教', body: '自动生成简报，还能问「这节课讲了什么」「有哪些考点」。' }
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
        '<p class="font-body-history-trans text-body-history-trans text-secondary font-medium js-translation-text">' + escapeHtml(translation) + '</p>' +
      '</div>' +
      '<button class="elastic-star p-2 rounded-full hover:bg-tertiary-fixed/50 transition-colors js-bookmark-btn"' +
        (transId ? '' : ' disabled style="opacity:0.4"') + ' title="' + (transId ? '收藏' : '保存中...') + '">' +
        '<span class="material-symbols-outlined text-tertiary text-xl" style="font-variation-settings:' + starFilled + '">star</span></button></div>';
    historySec.appendChild(block);
    historySec.scrollTop = historySec.scrollHeight;

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
    historySec.scrollTop = historySec.scrollHeight;
    setCurrentSubtitle(source, translation || '正在翻译…');
    return block;
  }

  function updateBlockTranslation(block, text, isError) {
    if (!block) return;
    var target = block.querySelector('.js-translation-text');
    if (!target) return;
    target.textContent = text;
    target.classList.toggle('text-error', !!isError);
    target.classList.toggle('text-secondary', !isError);
    if (block.classList.contains('subtitle-current')) {
      var sourceEl = block.querySelector('.font-body-history-source');
      setCurrentSubtitle(sourceEl ? sourceEl.textContent : '', text);
    }
  }

  function showLivePreview(text) {
    if (!historySec || !text) return;
    hideFeatureIntro();
    historySec.style.display = '';
    if (!livePreviewBlock) {
      livePreviewBlock = document.createElement('div');
      livePreviewBlock.className = 'space-y-unit border-l-2 border-primary/40 pl-4 py-2 opacity-70';
      var sourceLine = document.createElement('p');
      sourceLine.className = 'font-body-history-source text-body-history-source text-on-surface js-live-source';
      var hintLine = document.createElement('p');
      hintLine.className = 'font-body-history-trans text-body-history-trans text-on-surface-variant';
      hintLine.textContent = '正在识别…';
      livePreviewBlock.appendChild(sourceLine);
      livePreviewBlock.appendChild(hintLine);
      historySec.appendChild(livePreviewBlock);
    }
    livePreviewBlock.querySelector('.js-live-source').textContent = text;
    historySec.scrollTop = historySec.scrollHeight;
    setCurrentSubtitle(text, '正在识别…');
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
        if (mediaStream && recording && !paused) startSegmentLoop(mediaStream);
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
          try { recognition.start(); } catch (e) {}
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
    // 原文立即上屏，翻译和保存异步完成。
    var block = addSubtitle(text, '正在翻译…', false, null);
    if (block) block.setAttribute('data-pending-id', pendingId);

    var job = api('/translate', {
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
    }).then(function (result) {
      var translatedText = result.translated_text || text;
      if (result.success === false) {
        updateBlockTranslation(block, result.warning || '翻译服务暂时不可用，已保留原文', true);
        toast(result.warning || '翻译服务暂时不可用');
      } else {
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

  // ─── 演示模式 (无语音识别时降级) ──────────────────
  var demoTimer = null;
  function startDemoMode() {
    if (demoTimer) clearInterval(demoTimer);
    demoTimer = setInterval(function () {
      if (!recording || paused || !lectureId) return;
      api('/lectures/' + lectureId + '/transcribe', { method: 'POST' })
        .then(function (t) {
          if (!recording || !t.id) return;
          currentSectionTransId = t.id;
          addSubtitle(t.source_text, t.translated_text, t.is_bookmarked, t.id);
        }).catch(function () {});
    }, 4000);
  }

  function pickRecorderMime() {
    if (!window.MediaRecorder) return '';
    var types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/aac', 'audio/mpeg'];
    for (var i = 0; i < types.length; i++) {
      if (MediaRecorder.isTypeSupported(types[i])) return types[i];
    }
    return '';
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

  function stopRealtimeStream(sendFinish) {
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
        ws.send(floatTo16BitPCM(frame).buffer);
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
    stopRealtimeStream(false);
    realtimeActive = true;
    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var ws = new WebSocket(proto + '//' + location.host + '/api/lectures/' + lid + '/stream');
    realtimeSocket = ws;
    ws.binaryType = 'arraybuffer';
    var fallbackStarted = false;

    function fallback(reason) {
      if (fallbackStarted || !recording || paused) return;
      fallbackStarted = true;
      stopRealtimeStream(false);
      startSegmentLoop(stream);
      if (reason) toast(reason);
    }

    ws.onopen = function () {
      ws.send(JSON.stringify({ type: 'auth', token: token, offset_ms: 0 }));
    };
    ws.onmessage = function (event) {
      var msg;
      try { msg = JSON.parse(event.data); } catch (e) { return; }
      if (!msg || !msg.type) return;
      if (msg.type === 'ready') {
        try {
          connectPcmPump(ctx, stream, ws, msg.sample_rate || 16000, msg.frame_duration_ms || 160);
          setCurrentSubtitle('正在聆听…', '边说边出字');
        } catch (err) {
          fallback('当前浏览器不支持实时音频，已切换分片识别');
        }
        return;
      }
      if (msg.fallback) {
        fallback(msg.message || '已切换较快的分片识别');
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
      fallback('实时识别中断，已切换分片识别');
    };
    ws.onclose = function () {
      if (realtimeActive) fallback();
    };
  }

  function startSegmentLoop(stream) {
    if (!stream) return;
    mediaStream = stream;
    liveAsrActive = true;
    segmentLoopActive = true;
    function run() {
      if (!segmentLoopActive || paused || !mediaStream) return;
      if (!window.MediaRecorder) {
        toast('当前浏览器无法录音识别，请用 Safari 或 Chrome 打开');
        return;
      }
      var mime = pickRecorderMime();
      var rec;
      try {
        rec = new MediaRecorder(mediaStream, mime ? { mimeType: mime } : {});
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
        if (segmentLoopActive && !paused && mediaStream) {
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
    mediaStream = stream;
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
      if (mediaStream) mediaStream.getTracks().forEach(function (track) { track.stop(); });
      mediaStream = null;
      return Promise.resolve();
    }
    return new Promise(function (resolve) {
      mediaRecorder.addEventListener('stop', function () {
        var mimeType = mediaRecorder.mimeType || 'audio/webm';
        var blob = new Blob(audioChunks, { type: mimeType });
        if (mediaStream) mediaStream.getTracks().forEach(function (track) { track.stop(); });
        mediaStream = null;
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
    if (!mediaStream) return;
    if (mediaRecorder && mediaRecorder.state === 'paused') {
      try { mediaRecorder.resume(); } catch (e) {}
      return;
    }
    if (mediaRecorder && mediaRecorder.state === 'recording') return;
    var mime = pickRecorderMime();
    var options = mime ? { mimeType: mime } : {};
    try {
      mediaRecorder = new MediaRecorder(mediaStream, options);
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
    if (!lid) return Promise.resolve();
    return api('/lectures/' + lid + '/transcriptions').then(function (items) {
      if (!items || !items.length) {
        if (historySec && historySec.children.length) historySec.style.display = '';
        return;
      }
      hideFeatureIntro();
      items.forEach(function (t) {
        if (historySec && historySec.querySelector('[data-trans-id="' + t.id + '"]')) return;
        addSubtitle(t.source_text, t.translated_text, t.is_bookmarked, t.id);
      });
    }).catch(function () {});
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
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });
    } catch (e) {
      toast('麦克风权限被拒绝，请在系统设置里允许浏览器使用麦克风');
      releaseSpeechRecognition();
      return;
    }

    api('/lectures/start', {
      method: 'POST',
      body: JSON.stringify({
        course_name: '课堂录音',
        source_lang: selectedSourceLang(),
        target_lang: selectedTargetLang()
      })
    }).then(function (l) {
      var continuing = keepExistingTranscript(l);
      lectureId = l.id;
      recording = true;
      stopping = false;
      paused = false;
      currentSectionTransId = null;
      if (!continuing) clearTranscriptUi();
      hideFeatureIntro();
      courseName.textContent = l.course_name;
      setSessionChrome('recording');
      if (!pendingPhrases.length) {
        setCurrentSubtitle('正在聆听…', useServerAsr ? '请对着手机说话，字幕会尽快出现' : '说完一句后会显示原文和翻译');
      }
      if (sourceLangSelect) sourceLangSelect.disabled = true;
      if (targetLangSelect) targetLangSelect.disabled = true;
      startWave();
      if (useServerAsr) {
        releaseSpeechRecognition();
        startRealtimeStream(mediaStream, lectureId);
      } else {
        startAudioCapture(mediaStream, continuing);
        if (hasSpeechRecognition()) {
          if (!recognition) startSpeechRecognition({ silent: continuing });
        } else {
          startSegmentLoop(mediaStream);
        }
      }
      flushPendingPhrases();
      if (continuing) {
        restoreTranscriptions(l.id).then(function () {
          toast('已继续上一堂未结束的课，前文仍在');
        });
      }
    }).catch(function (error) {
      stopRealtimeStream(false);
      stopSegmentLoop();
      if (mediaStream) mediaStream.getTracks().forEach(function (track) { track.stop(); });
      mediaStream = null;
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
    clearLivePreview();
    releaseSpeechRecognition();
    stopRealtimeStream(true);
    if (!lectureId) { stopping = false; return; }
    var lid = lectureId;
    var wrap = stopSegmentLoop().then(function () {
      return finishAudioCapture(lid);
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
        if (targetLangSelect) targetLangSelect.disabled = false;
        showFeatureIntroIfIdle();
        showNameModal(lid, l.sentence_count);
      }).catch(function () {
        stopping = false;
        lectureId = null;
        if (sourceLangSelect) sourceLangSelect.disabled = false;
        if (targetLangSelect) targetLangSelect.disabled = false;
        showFeatureIntroIfIdle();
        toast('停止失败');
      });
    }, 500);
  }

  // ─── 命名弹窗 ───────────────────────────────────
  function showNameModal(lid, count) {
    document.getElementById('nameModalInfo').textContent = '共 ' + count + ' 句话';
    document.getElementById('nameInput').value = '课堂录音';
    document.getElementById('nameModal').classList.remove('hidden');
    document.getElementById('nameInput').focus();
    document.getElementById('nameInput').select();

    function save() {
      var name = document.getElementById('nameInput').value.trim();
      document.getElementById('nameModal').classList.add('hidden');
      if (name) {
        api('/lectures/' + lid + '/rename', {
          method: 'PUT', body: JSON.stringify({ course_name: name })
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
    }
    document.getElementById('nameSave').addEventListener('click', save);
    document.getElementById('nameCancel').addEventListener('click', cancel);
    document.getElementById('nameInput').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { save(); }
      if (e.key === 'Escape') { cancel(); }
    });
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
    clearLivePreview();
    releaseSpeechRecognition();
    stopRealtimeStream(true);
    stopSegmentLoop();
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      try { mediaRecorder.pause(); } catch (e) {}
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
      if (preferServerAsr() || liveAsrActive) {
        startRealtimeStream(mediaStream, lectureId);
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
  startWave();
})();
