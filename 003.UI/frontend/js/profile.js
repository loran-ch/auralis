/**
 * LiveTrans Voice — 个人中心
 */
(function () {
  var TOKEN = localStorage.getItem('livetrans_token');
  if (!TOKEN) { window.location.href = 'login.html'; return; }

  var API = '/api/auth';
  var currentNickname = '';

  // DOM elements
  var avatarImg = document.getElementById('avatar-img');
  var avatarPlaceholder = document.getElementById('avatar-placeholder');
  var avatarInput = document.getElementById('avatar-input');
  var nameText = document.getElementById('name-text');
  var nameDisplay = document.getElementById('name-display');
  var nameEdit = document.getElementById('name-edit');
  var nameInput = document.getElementById('name-input');
  var nameSave = document.getElementById('name-save');
  var nameCancel = document.getElementById('name-cancel');
  var userSubtitle = document.getElementById('user-subtitle');
  var toastEl = document.getElementById('toast');
  var universityInput = document.getElementById('profile-university');
  var majorInput = document.getElementById('profile-major');
  var focusInput = document.getElementById('profile-focus');
  var sourceLangSetting = document.getElementById('setting-source-lang');
  var targetLangSetting = document.getElementById('setting-target-lang');
  var darkModeSetting = document.getElementById('setting-dark-mode');
  var cloudSyncSetting = document.getElementById('setting-cloud-sync');

  function toast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.remove('hidden');
    setTimeout(function () { toastEl.classList.add('hidden'); }, 2500);
  }

  // ─── 加载用户信息 ─────────────────────────────
  function loadProfile() {
    fetch(API + '/me', { headers: { 'Authorization': 'Bearer ' + TOKEN } })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (user) {
        currentNickname = user.nickname || '用户';
        nameText.textContent = currentNickname;

        // 头像
        if (user.avatar_url) {
          avatarImg.src = user.avatar_url;
          avatarImg.style.display = '';
          if (avatarPlaceholder) avatarPlaceholder.style.display = 'none';
        } else {
          avatarImg.style.display = 'none';
          if (avatarPlaceholder) avatarPlaceholder.style.display = 'flex';
        }

        // 副标题
        var parts = [];
        if (user.university) parts.push(user.university);
        if (user.major) parts.push(user.major);
        userSubtitle.textContent = parts.length ? parts.join(' · ') : '';
        if (universityInput) universityInput.value = user.university || '';
        if (majorInput) majorInput.value = user.major || '';
        if (focusInput) focusInput.value = user.focus_area || '';
      })
      .catch(function (err) {
        console.error('加载个人信息失败:', err);
        nameText.textContent = '未登录';
      });
  }

  function requestJson(url, options) {
    return fetch(url, options || {}).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok) throw new Error(data.detail || '请求失败');
        return data;
      });
    });
  }

  function fillLanguageSelect(select, languages, selected, allowAuto) {
    if (!select) return;
    select.innerHTML = '';
    if (allowAuto) {
      var autoOption = document.createElement('option');
      autoOption.value = 'auto'; autoOption.textContent = '🌐 自动检测';
      select.appendChild(autoOption);
    }
    languages.forEach(function (language) {
      var option = document.createElement('option');
      option.value = language.code;
      option.textContent = (language.flag_emoji || '🌐') + ' ' + language.name_native;
      select.appendChild(option);
    });
    select.value = selected;
    if (!select.value) select.selectedIndex = 0;
  }

  function loadPreferences() {
    Promise.all([
      requestJson('/api/languages'),
      requestJson('/api/settings', { headers: { 'Authorization': 'Bearer ' + TOKEN } })
    ]).then(function (results) {
      var languages = results[0];
      var settings = results[1];
      fillLanguageSelect(sourceLangSetting, languages, settings.default_source_lang, true);
      fillLanguageSelect(targetLangSetting, languages, settings.default_target_lang, false);
      darkModeSetting.value = settings.dark_mode || 'system';
      cloudSyncSetting.checked = !!settings.cloud_sync_enabled;
    }).catch(function (error) {
      console.error('加载偏好失败:', error);
    });
  }

  var savePreferencesButton = document.getElementById('save-preferences');
  if (savePreferencesButton) {
    savePreferencesButton.addEventListener('click', function () {
      savePreferencesButton.disabled = true;
      var profileBody = {
        university: universityInput.value.trim(),
        major: majorInput.value.trim(),
        focus_area: focusInput.value.trim()
      };
      var settingsBody = {
        default_source_lang: sourceLangSetting.value,
        default_target_lang: targetLangSetting.value,
        dark_mode: darkModeSetting.value,
        cloud_sync_enabled: cloudSyncSetting.checked
      };
      Promise.all([
        requestJson(API + '/profile', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN },
          body: JSON.stringify(profileBody)
        }),
        requestJson('/api/settings', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN },
          body: JSON.stringify(settingsBody)
        })
      ]).then(function (results) {
        var user = results[0].user;
        if (user) {
          localStorage.setItem('livetrans_user', JSON.stringify(user));
          var parts = [user.university, user.major].filter(Boolean);
          userSubtitle.textContent = parts.join(' · ');
        }
        localStorage.setItem('livetrans-theme', settingsBody.dark_mode);
        if (settingsBody.dark_mode !== 'system') {
          document.documentElement.setAttribute('data-theme', settingsBody.dark_mode);
        }
        toast('资料与偏好已保存');
      }).catch(function (error) {
        toast(error.message || '保存失败');
      }).finally(function () {
        savePreferencesButton.disabled = false;
      });
    });
  }

  var dayNames = ['', '周一', '周二', '周三', '周四', '周五', '周六', '周日'];

  function renderSchedules(items) {
    var list = document.getElementById('schedule-list');
    if (!list) return;
    list.innerHTML = '';
    if (!items.length) {
      list.textContent = '暂未添加课程';
      return;
    }
    items.forEach(function (item) {
      var row = document.createElement('div');
      row.className = 'flex items-center justify-between bg-white rounded-xl px-3 py-2 border border-outline-variant/20';
      var info = document.createElement('div');
      var title = document.createElement('p');
      title.className = 'font-semibold text-on-surface';
      title.textContent = item.course_name;
      var meta = document.createElement('p');
      meta.className = 'text-xs text-on-surface-variant';
      meta.textContent = dayNames[item.day_of_week] + ' ' + item.start_time.slice(0, 5) + '–' + item.end_time.slice(0, 5) +
        (item.room ? ' · ' + item.room : '') + (item.professor_name ? ' · ' + item.professor_name : '');
      info.appendChild(title); info.appendChild(meta);
      var remove = document.createElement('button');
      remove.className = 'text-error p-2 rounded-full hover:bg-error/5';
      remove.innerHTML = '<span class="material-symbols-outlined text-lg">delete</span>';
      remove.addEventListener('click', function () {
        requestJson('/api/schedules/' + item.id, {
          method: 'DELETE', headers: { 'Authorization': 'Bearer ' + TOKEN }
        }).then(loadSchedules).catch(function (error) { toast(error.message); });
      });
      row.appendChild(info); row.appendChild(remove); list.appendChild(row);
    });
  }

  function loadSchedules() {
    requestJson('/api/schedules', { headers: { 'Authorization': 'Bearer ' + TOKEN } })
      .then(renderSchedules)
      .catch(function (error) {
        var list = document.getElementById('schedule-list');
        if (list) list.textContent = error.message || '课程表加载失败';
      });
  }

  var addScheduleButton = document.getElementById('add-schedule');
  if (addScheduleButton) {
    addScheduleButton.addEventListener('click', function () {
      var body = {
        course_name: document.getElementById('schedule-name').value.trim(),
        source_lang: sourceLangSetting.value === 'auto' ? 'en' : (sourceLangSetting.value || 'en'),
        target_lang: targetLangSetting.value || 'zh-CN',
        day_of_week: Number(document.getElementById('schedule-day').value),
        start_time: document.getElementById('schedule-start').value,
        end_time: document.getElementById('schedule-end').value,
        room: document.getElementById('schedule-room').value.trim() || null,
        professor_name: document.getElementById('schedule-professor').value.trim() || null
      };
      if (!body.course_name) { toast('请输入课程名称'); return; }
      requestJson('/api/schedules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN },
        body: JSON.stringify(body)
      }).then(function () {
        document.getElementById('schedule-name').value = '';
        toast('课程已添加');
        loadSchedules();
      }).catch(function (error) { toast(error.message || '课程添加失败'); });
    });
  }

  // ─── 加载统计数据 ─────────────────────────────
  function loadStats() {
    fetch(API + '/stats', { headers: { 'Authorization': 'Bearer ' + TOKEN } })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (stats) {
        document.getElementById('stat-hours').textContent = (stats.total_hours || 0) + 'h';
        document.getElementById('stat-bookmarks').textContent = stats.bookmark_count || 0;
        document.getElementById('stat-lectures').textContent = stats.lecture_count || 0;

        document.getElementById('stat-streak').textContent = stats.weekly_bookmark_count || 0;
      })
      .catch(function (err) {
        console.error('加载统计数据失败:', err);
      });
  }

  // ─── 头像上传 ─────────────────────────────────
  if (avatarInput) {
    document.getElementById('avatar-wrapper').addEventListener('click', function () {
      avatarInput.click();
    });

    avatarInput.addEventListener('change', function () {
      var file = this.files && this.files[0];
      if (!file) return;

      // 预览
      var reader = new FileReader();
      reader.onload = function (e) {
        avatarImg.src = e.target.result;
        avatarImg.style.display = '';
        if (avatarPlaceholder) avatarPlaceholder.style.display = 'none';
      };
      reader.readAsDataURL(file);

      // 上传
      var formData = new FormData();
      formData.append('file', file);

      fetch(API + '/avatar', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + TOKEN },
        body: formData
      })
        .then(function (r) { if (!r.ok) throw new Error('上传失败'); return r.json(); })
        .then(function (data) {
          avatarImg.src = data.avatar_url + '?t=' + Date.now();
          toast('头像已更新');
        })
        .catch(function (err) {
          console.error('头像上传失败:', err);
          toast('头像上传失败，请重试');
        });

      avatarInput.value = '';
    });
  }

  // ─── 昵称编辑 ─────────────────────────────────
  if (nameDisplay) {
    nameDisplay.addEventListener('click', function () {
      nameInput.value = currentNickname;
      nameDisplay.style.display = 'none';
      nameEdit.style.display = 'flex';
      nameInput.focus();
      nameInput.select();
    });
  }

  function cancelEdit() {
    nameEdit.style.display = 'none';
    nameDisplay.style.display = '';
  }

  function saveNickname() {
    var newName = nameInput.value.trim();
    if (!newName || newName === currentNickname) { cancelEdit(); return; }

    fetch(API + '/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN },
      body: JSON.stringify({ nickname: newName })
    })
      .then(function (r) { if (!r.ok) throw new Error('保存失败'); return r.json(); })
      .then(function (data) {
        currentNickname = data.nickname;
        nameText.textContent = currentNickname;
        toast('昵称已更新');
        cancelEdit();
      })
      .catch(function (err) {
        console.error('昵称更新失败:', err);
        toast('保存失败，请重试');
      });
  }

  if (nameSave) nameSave.addEventListener('click', saveNickname);
  if (nameCancel) nameCancel.addEventListener('click', cancelEdit);
  if (nameInput) {
    nameInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') saveNickname();
      if (e.key === 'Escape') cancelEdit();
    });
  }

  // ─── 头部滚动效果 ─────────────────────────────
  window.addEventListener('scroll', function () {
    var header = document.querySelector('header');
    if (!header) return;
    if (window.scrollY > 20) {
      header.classList.add('bg-surface/95', 'shadow-sm');
      header.classList.remove('bg-surface/80');
    } else {
      header.classList.add('bg-surface/80');
      header.classList.remove('bg-surface/95', 'shadow-sm');
    }
  });

  // ─── 退出登录 ─────────────────────────────────
  var logoutMenuBtn = document.getElementById('logoutMenuBtn');
  var logoutDropdown = document.getElementById('logoutBtn');
  var doLogoutBtn = document.getElementById('doLogout');

  if (logoutMenuBtn && logoutDropdown) {
    logoutMenuBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      logoutDropdown.classList.toggle('hidden');
    });
  }

  // 点击外部关闭
  document.addEventListener('click', function (e) {
    if (logoutDropdown && !logoutDropdown.classList.contains('hidden') &&
        !logoutDropdown.contains(e.target) && e.target !== logoutMenuBtn) {
      logoutDropdown.classList.add('hidden');
    }
  });

  // 执行退出
  if (doLogoutBtn) {
    doLogoutBtn.addEventListener('click', function () {
      var token = localStorage.getItem('livetrans_token');
      var refreshToken = localStorage.getItem('livetrans_refresh_token');
      function finishLogout() {
        if (window.LiveTransAuth) {
          window.LiveTransAuth.clearSession();
        } else {
          localStorage.removeItem('livetrans_token');
          localStorage.removeItem('livetrans_refresh_token');
          localStorage.removeItem('livetrans_user');
        }
        window.location.href = 'login.html';
      }
      if (token || refreshToken) {
        fetch('/api/auth/logout', {
          method: 'POST',
          headers: token ? { 'Authorization': 'Bearer ' + token } : {}
        }).catch(function () {}).finally(finishLogout);
      } else {
        finishLogout();
      }
    });
  }

  // ─── 页面加载 ─────────────────────────────────
  loadProfile();
  loadStats();
  loadPreferences();
  loadSchedules();
})();
