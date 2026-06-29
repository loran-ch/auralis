/**
 * LiveTrans Voice — 浏览器语音识别 + 实时翻译
 */
(function () {
  var API = '/api';
  var lectureId = null;
  var recording = false;
  var recognition = null;
  var currentTransId = null;

  var starBtn = document.getElementById('star-btn');
  var pauseBtn = document.getElementById('pause-btn');
  var recordBtn = document.getElementById('record-btn');
  var recordIcon = document.getElementById('record-icon');
  var statusDot = document.getElementById('status-dot');
  var statusText = document.getElementById('status-text');
  var courseName = document.getElementById('course-name');
  var historySec = document.getElementById('history-section');
  var toastEl = document.getElementById('toast');

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

  function toast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg; toastEl.classList.remove('hidden');
    setTimeout(function () { toastEl.classList.add('hidden'); }, 2500);
  }

  var bars = document.querySelectorAll('.waveform-bar');
  var waveInterval;
  function startWave() { waveInterval = setInterval(function () { bars.forEach(function (b) { b.style.height = (Math.floor(Math.random() * 28) + 6) + 'px'; }); }, 80); }
  function stopWave() { clearInterval(waveInterval); }

  function addSubtitle(source, translation, isBookmarked) {
    if (historySec) historySec.style.display = '';
    var old = document.querySelector('.subtitle-current');
    if (old) { old.classList.remove('subtitle-current'); old.classList.add('opacity-60'); }
    var block = document.createElement('div');
    block.className = 'space-y-unit border-l-2 border-primary/20 pl-4 py-2 subtitle-enter';
    block.innerHTML =
      '<div class="flex justify-between items-start"><div>' +
        '<p class="font-body-history-source text-body-history-source text-on-surface">' + source + '</p>' +
        '<p class="font-body-history-trans text-body-history-trans text-secondary font-medium">' + translation + '</p>' +
      '</div>' +
      '<button class="elastic-star p-2 rounded-full hover:bg-tertiary-fixed/50 transition-colors js-bookmark-btn">' +
        '<span class="material-symbols-outlined text-tertiary text-xl">star</span></button></div>';
    historySec.appendChild(block);
    historySec.scrollTop = historySec.scrollHeight;

    block.querySelector('.js-bookmark-btn').addEventListener('click', function () {
      if (!currentTransId) return;
      var tag = prompt('1=重要 2=疑问 3=考点 4=定义', '1');
      var tags = { '1': 'important', '2': 'question', '3': 'exam', '4': 'definition' };
      api('/bookmarks', { method: 'POST', body: JSON.stringify({ transcription_id: currentTransId, tag: tags[tag] || 'important' }) })
        .then(function () { toast('已收藏'); block.querySelector('span').style.fontVariationSettings = "'FILL' 1"; })
        .catch(function () { toast('请先登录'); });
    });
    block.classList.add('subtitle-current');
    historySec.scrollTop = historySec.scrollHeight;
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
    recognition.lang = 'en-US';        // 识别英文
    recognition.interimResults = false; // 只返回最终结果
    recognition.continuous = true;     // 持续监听
    recognition.maxAlternatives = 1;

    recognition.onresult = function (event) {
      if (!recording) return;
      for (var i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          var text = event.results[i][0].transcript.trim();
          if (text) {
            statusText.textContent = '识别: ' + text.substring(0, 20) + '...';
            translateAndSave(text);
          }
        }
      }
    };

    recognition.onerror = function (event) {
      console.log('Speech error:', event.error);
      if (event.error === 'not-allowed') {
        toast('麦克风权限被拒绝');
      }
      // 自动重启
      if (recording && recognition) {
        setTimeout(function () { try { recognition.start(); } catch (e) {} }, 1000);
      }
    };

    recognition.onend = function () {
      if (recording && recognition) {
        try { recognition.start(); } catch (e) {}
      }
    };

    recognition.start();
    toast('语音识别已启动 - 请说英文');
  }

  function translateAndSave(text) {
    if (!lectureId) return;
    // 调用翻译 API
    fetch('/api/translate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text, source: 'en', target: 'zh-CN' })
    }).then(function (r) { return r.json(); })
    .then(function (result) {
      if (!recording) return;
      currentTransId = Date.now(); // 临时 ID
      addSubtitle(text, result.translated_text, false);
      // 同时保存到后端
      api('/lectures/' + lectureId + '/transcribe/text', {
        method: 'POST',
        body: JSON.stringify({ source_text: text, translated_text: result.translated_text })
      }).then(function (t) {
        currentTransId = t.id;
      }).catch(function () {});
    }).catch(function () {
      // 翻译失败时仍然显示原文
      addSubtitle(text, '[翻译中...]', false);
    });
  }

  // ─── 演示模式 (无语音识别时降级) ──────────────────
  var demoTimer = null;
  function startDemoMode() {
    demoTimer = setInterval(function () {
      if (!recording || !lectureId) return;
      api('/lectures/' + lectureId + '/transcribe', { method: 'POST' })
        .then(function (t) {
          if (!recording || !t.id) return;
          currentTransId = t.id;
          addSubtitle(t.source_text, t.translated_text, t.is_bookmarked);
        }).catch(function () {});
    }, 4000);
  }

  // ─── 开始/停止 ───────────────────────────────────
  async function startRecording() {
    // 先请求麦克风权限触发浏览器提示
    try {
      var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(function (t) { t.stop(); });
    } catch (e) {
      toast('麦克风权限被拒绝');
    }

    api('/lectures/start', {
      method: 'POST',
      body: JSON.stringify({ course_name: '课堂录音', source_lang: 'en', target_lang: 'zh-CN' })
    }).then(function (l) {
      lectureId = l.id; recording = true;
      courseName.textContent = l.course_name;
      recordIcon.textContent = 'mic_off'; recordBtn.style.background = '#EF4444';
      recordBtn.style.animation = 'pulse-red 2s infinite';
      statusDot.classList.add('animate-pulse');
      startWave();
      startSpeechRecognition(); // ← 真实语音识别
    }).catch(function () { toast('请先登录'); });
  }

  function stopRecording() {
    recording = false;
    recordIcon.textContent = 'mic'; recordBtn.style.background = '#4CAF50';
    recordBtn.style.animation = ''; statusDot.classList.remove('animate-pulse');
    statusText.textContent = '待机中'; stopWave();
    clearInterval(demoTimer);

    if (recognition) { try { recognition.stop(); } catch (e) {} recognition = null; }
    if (!lectureId) return;
    var lid = lectureId; lectureId = null;

    api('/lectures/' + lid + '/stop', { method: 'POST' })
      .then(function (l) {
        showNameModal(lid, l.sentence_count);
      }).catch(function () { toast('停止失败'); });
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
    recording ? stopRecording() : startRecording();
  });

  if (starBtn) starBtn.addEventListener('click', function () {
    var f = this.style.fontVariationSettings.indexOf("'FILL' 1") !== -1;
    this.style.fontVariationSettings = f ? "'FILL' 0" : "'FILL' 1";
  });

  startWave();
})();
