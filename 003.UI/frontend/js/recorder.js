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

  var starBtn = document.getElementById('star-btn');
  var pauseBtn = document.getElementById('pause-btn');
  var recordBtn = document.getElementById('record-btn');
  var recordIcon = document.getElementById('record-icon');
  var statusDot = document.getElementById('status-dot');
  var statusText = document.getElementById('status-text');
  var courseName = document.getElementById('course-name');
  var historySec = document.getElementById('history-section');
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
    return block;
  }

  function updateBlockTranslation(block, text, isError) {
    if (!block) return;
    var target = block.querySelector('.js-translation-text');
    if (!target) return;
    target.textContent = text;
    target.classList.toggle('text-error', !!isError);
    target.classList.toggle('text-secondary', !isError);
  }

  function showLivePreview(text) {
    if (!historySec || !text) return;
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
  }

  function clearLivePreview() {
    if (livePreviewBlock) livePreviewBlock.remove();
    livePreviewBlock = null;
  }

  // ─── 浏览器语音识别 (Web Speech API) ──────────────
  function startSpeechRecognition() {
    var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      toast('浏览器不支持语音识别，使用演示模式');
      startDemoMode();
      return;
    }

    recognition = new SpeechRecognition();
    recognition.lang = recognitionLocale(selectedSourceLang());
    recognition.interimResults = true;  // 立即展示中间结果，停顿后再翻译最终句子
    recognition.continuous = true;     // 持续监听
    recognition.maxAlternatives = 1;

    recognition.onresult = function (event) {
      if ((!recording && !stopping) || paused) return;
      var interimText = '';
      for (var i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          var text = event.results[i][0].transcript.trim();
          if (text) {
            clearLivePreview();
            statusText.textContent = '正在翻译: ' + text.substring(0, 24);
            translateAndSave(text);
          }
        } else {
          interimText += event.results[i][0].transcript;
        }
      }
      interimText = interimText.trim();
      if (interimText) {
        statusText.textContent = '正在识别: ' + interimText.substring(0, 24);
        showLivePreview(interimText);
      }
    };

    recognition.onerror = function (event) {
      console.log('Speech error:', event.error);
      if (event.error === 'not-allowed') {
        toast('麦克风权限被拒绝');
      } else if (event.error === 'network') {
        toast('语音识别网络不可用，请检查 Chrome 网络连接');
      }
    };

    recognition.onend = function () {
      if (recording && !paused && recognition) {
        clearTimeout(recognitionRestartTimer);
        recognitionRestartTimer = setTimeout(function () {
          try { recognition.start(); } catch (e) {}
        }, 250);
      }
    };

    recognition.start();
    toast('语音识别已启动');
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

  function startAudioCapture(stream) {
    mediaStream = stream;
    audioChunks = [];
    if (!window.MediaRecorder) {
      stream.getTracks().forEach(function (track) { track.stop(); });
      mediaStream = null;
      return;
    }
    var options = {};
    if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
      options.mimeType = 'audio/webm;codecs=opus';
    }
    try {
      mediaRecorder = new MediaRecorder(stream, options);
      mediaRecorder.addEventListener('dataavailable', function (event) {
        if (event.data && event.data.size) audioChunks.push(event.data);
      });
      mediaRecorder.start(1000);
    } catch (error) {
      stream.getTracks().forEach(function (track) { track.stop(); });
      mediaStream = null;
      mediaRecorder = null;
      toast('浏览器不支持保存本次录音，但实时识别仍可使用');
    }
  }

  function finishAudioCapture(lid) {
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

  // ─── 开始/停止 ───────────────────────────────────
  async function startRecording() {
    // 先请求麦克风权限触发浏览器提示
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });
    } catch (e) {
      toast('麦克风权限被拒绝');
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
      lectureId = l.id; recording = true; stopping = false; currentSectionTransId = null;
      courseName.textContent = l.course_name;
      recordIcon.textContent = 'mic_off'; recordBtn.style.background = '#EF4444';
      recordBtn.style.animation = 'pulse-red 2s infinite';
      statusDot.classList.add('animate-pulse');
      if (sourceLangSelect) sourceLangSelect.disabled = true;
      if (targetLangSelect) targetLangSelect.disabled = true;
      startWave();
      startAudioCapture(mediaStream);
      startSpeechRecognition(); // ← 真实语音识别
    }).catch(function (error) {
      if (mediaStream) mediaStream.getTracks().forEach(function (track) { track.stop(); });
      mediaStream = null;
      toast(error.message || '课堂启动失败，请重新登录');
    });
  }

  function stopRecording() {
    recording = false;
    stopping = true;
    paused = false;
    pauseBtn.querySelector('span').textContent = 'pause';
    pauseBtn.title = '暂停';
    recordIcon.textContent = 'mic'; recordBtn.style.background = '#4CAF50';
    recordBtn.style.animation = ''; statusDot.classList.remove('animate-pulse');
    statusText.textContent = '待机中'; stopWave();
    clearInterval(demoTimer);
    demoTimer = null;
    clearTimeout(recognitionRestartTimer);
    clearLivePreview();

    if (recognition) { try { recognition.stop(); } catch (e) {} recognition = null; }
    if (!lectureId) { stopping = false; return; }
    var lid = lectureId;
    var audioJob = finishAudioCapture(lid);
    pendingJobs.add(audioJob);
    audioJob.finally(function () { pendingJobs.delete(audioJob); });

    // recognition.stop() 可能再送达最后一个 final 结果，短暂等待避免丢尾句。
    statusText.textContent = '正在完成翻译并保存…';
    setTimeout(function () {
      lectureId = null;
      Promise.allSettled(Array.from(pendingJobs)).then(function () {
        return api('/lectures/' + lid + '/stop', { method: 'POST' });
      }).then(function (l) {
        stopping = false;
        statusText.textContent = '待机中';
        if (sourceLangSelect) sourceLangSelect.disabled = false;
        if (targetLangSelect) targetLangSelect.disabled = false;
        showNameModal(lid, l.sentence_count);
      }).catch(function () {
        stopping = false;
        if (sourceLangSelect) sourceLangSelect.disabled = false;
        if (targetLangSelect) targetLangSelect.disabled = false;
        toast('停止失败');
      });
    }, 400);
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
    recording ? stopRecording() : startRecording();
  });

  // ─── 暂停/恢复 ───────────────────────────────────
  function pauseRecording() {
    if (!recording || paused) return;
    paused = true;
    pauseBtn.querySelector('span').textContent = 'play_arrow';
    pauseBtn.title = '继续';
    statusText.textContent = '已暂停';
    stopWave();
    // 暂停演示模式
    clearInterval(demoTimer);
    demoTimer = null;
    // 暂停语音识别
    if (recognition) {
      try { recognition.stop(); } catch (e) {}
    }
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      try { mediaRecorder.pause(); } catch (e) {}
    }
    api('/lectures/' + lectureId + '/pause', { method: 'POST' })
      .catch(function (error) { toast(error.message || '暂停状态同步失败'); });
  }

  function resumeRecording() {
    if (!recording || !paused) return;
    api('/lectures/' + lectureId + '/resume', { method: 'POST' })
      .then(function () {
        paused = false;
        pauseBtn.querySelector('span').textContent = 'pause';
        pauseBtn.title = '暂停';
        statusText.textContent = '录音中';
        startWave();
        if (!recognition && !demoTimer) startDemoMode();
        if (recognition) {
          try { recognition.start(); } catch (e) {}
        }
        if (mediaRecorder && mediaRecorder.state === 'paused') {
          try { mediaRecorder.resume(); } catch (e) {}
        }
      })
      .catch(function (error) { toast(error.message || '恢复状态同步失败'); });
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

  loadLanguagePreferences();
  startWave();
})();
