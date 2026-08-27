/**
 * LiveTrans Voice — 管理后台
 */
(function () {
  'use strict';

  // ─── 状态 ───────────────────────────────────────────────
  var TOKEN = localStorage.getItem('livetrans_token');
  var USER = null;            // 从 /api/auth/me 获取的完整信息
  var IS_SUPER_ADMIN = false;
  var currentTab = 'dashboard';
  var eventsBound = false;

  var usersPage = 1;
  var lecturesPage = 1;
  var auditPage = 1;

  // DOM 缓存
  var sidebar = document.getElementById('sidebar');
  var sidebarToggle = document.getElementById('sidebar-toggle');
  var toastEl = document.getElementById('toast');
  var confirmModal = document.getElementById('confirm-modal');
  var confirmMessage = document.getElementById('confirm-message');
  var confirmOk = document.getElementById('confirm-ok');
  var confirmCancel = document.getElementById('confirm-cancel');
  var confirmCallback = null;
  var adminNameEl = document.getElementById('admin-name');
  var adminRoleEl = document.getElementById('admin-role');
  var reloginModal = document.getElementById('relogin-modal');
  var reloginReason = document.getElementById('relogin-reason');
  var reloginAccount = document.getElementById('relogin-account');
  var reloginPassword = document.getElementById('relogin-password');
  var reloginMsg = document.getElementById('relogin-msg');
  var reloginSubmit = document.getElementById('relogin-submit');

  function isAdminRole(role) {
    // 平台后台仅超级管理员可进；教师角色 admin 不能进。
    return role === 'super_admin';
  }

  function showReloginModal(reason) {
    if (reloginReason) reloginReason.textContent = reason || '请使用超级管理员账号登录后继续';
    if (reloginMsg) {
      reloginMsg.classList.add('hidden');
      reloginMsg.textContent = '';
    }
    if (reloginModal) reloginModal.classList.remove('hidden');
    if (reloginAccount) setTimeout(function () { reloginAccount.focus(); }, 50);
  }

  function hideReloginModal() {
    if (reloginModal) reloginModal.classList.add('hidden');
    if (reloginPassword) reloginPassword.value = '';
    if (reloginMsg) reloginMsg.classList.add('hidden');
  }

  function bootstrapAdmin(user) {
    USER = user;
    TOKEN = localStorage.getItem('livetrans_token');
    IS_SUPER_ADMIN = user.role === 'super_admin';
    if (adminNameEl) adminNameEl.textContent = user.nickname || '管理员';
    if (adminRoleEl) adminRoleEl.textContent = '超级管理员';
    var auditNav = document.getElementById('nav-audit-log');
    if (auditNav) auditNav.style.display = '';
    hideReloginModal();
    if (!eventsBound) {
      initEvents();
      eventsBound = true;
    }
    var tab = currentTab || 'dashboard';
    currentTab = '';
    switchTab(tab);
  }

  function checkAdminAccess() {
    TOKEN = localStorage.getItem('livetrans_token');
    if (!TOKEN) {
      showReloginModal('请先登录管理员账号');
      return;
    }
    fetch('/api/auth/me')
      .then(function (r) {
        return r.json().then(function (d) { return { ok: r.ok, status: r.status, data: d }; });
      })
      .then(function (res) {
        var user = res.data || {};
        if (!res.ok || !isAdminRole(user.role)) {
          if (res.status === 401 && window.LiveTransAuth && LiveTransAuth.clearSession) {
            LiveTransAuth.clearSession();
          }
          showReloginModal(
            user.role === 'admin'
              ? '教师账号不能进入平台管理后台，请使用超级管理员登录'
              : (res.ok ? '当前账号没有超级管理员权限' : '登录已失效，请重新登录')
          );
          return;
        }
        bootstrapAdmin(user);
      })
      .catch(function () {
        showReloginModal('登录已失效，请重新登录');
      });
  }

  function submitRelogin() {
    var account = reloginAccount ? reloginAccount.value.trim() : '';
    if (/^1[3-9]\d{9}$/.test(account.replace(/[\s-]/g, ''))) {
      account = '+86' + account.replace(/[\s-]/g, '');
    }
    var pwd = reloginPassword ? reloginPassword.value : '';
    if (!account || !pwd) {
      if (reloginMsg) {
        reloginMsg.textContent = '请输入账号和密码';
        reloginMsg.style.color = '#EF4444';
        reloginMsg.classList.remove('hidden');
      }
      return;
    }
    if (reloginSubmit) reloginSubmit.disabled = true;
    if (reloginMsg) {
      reloginMsg.textContent = '登录中...';
      reloginMsg.style.color = '#717782';
      reloginMsg.classList.remove('hidden');
    }
    fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account: account, password: pwd })
    })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (d) {
          if (!r.ok) throw new Error(d.detail || '登录失败');
          return d;
        });
      })
      .then(function (d) {
        if (!d.tokens || !d.tokens.access_token || !d.user) throw new Error('登录响应格式异常');
        if (!isAdminRole(d.user.role)) {
          throw new Error(d.user.role === 'admin'
            ? '教师账号不能进入平台管理后台，请使用超级管理员登录'
            : '当前账号没有超级管理员权限');
        }
        localStorage.setItem('livetrans_token', d.tokens.access_token);
        if (d.tokens.refresh_token) localStorage.setItem('livetrans_refresh_token', d.tokens.refresh_token);
        localStorage.setItem('livetrans_user', JSON.stringify(d.user));
        bootstrapAdmin(d.user);
      })
      .catch(function (e) {
        if (reloginMsg) {
          reloginMsg.textContent = e.message || '登录失败';
          reloginMsg.style.color = '#EF4444';
          reloginMsg.classList.remove('hidden');
        }
      })
      .finally(function () {
        if (reloginSubmit) reloginSubmit.disabled = false;
      });
  }

  if (reloginSubmit) reloginSubmit.addEventListener('click', submitRelogin);
  if (reloginPassword) {
    reloginPassword.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') submitRelogin();
    });
  }
  if (reloginAccount) {
    reloginAccount.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') submitRelogin();
    });
  }

  checkAdminAccess();

  // ─── 工具函数 ───────────────────────────────────────────
  function escapeHtml(str) {
    if (!str && str !== 0) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
  }

  function toast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.className = 'show fixed bottom-6 left-1/2 -translate-x-1/2 bg-ink-deep text-white px-6 py-3 rounded-2xl shadow-lg text-sm font-medium z-[100] max-w-sm text-center';
    clearTimeout(toastEl._timer);
    toastEl._timer = setTimeout(function () {
      toastEl.className = 'hidden fixed bottom-6 left-1/2 -translate-x-1/2 bg-ink-deep text-white px-6 py-3 rounded-2xl shadow-lg text-sm font-medium z-[100] max-w-sm text-center';
    }, 2500);
  }

  function showConfirm(msg, cb) {
    confirmMessage.textContent = msg;
    confirmModal.classList.remove('hidden');
    confirmCallback = cb;
  }

  function api(path, options) {
    return fetch('/api/admin' + path, Object.assign({
      headers: { 'Content-Type': 'application/json' }
    }, options || {}))
    .then(function (r) {
      return r.json().then(function (d) {
        if (r.status === 401) {
          showReloginModal('登录已失效，请重新登录');
          return Promise.reject(d);
        }
        if (r.status === 403) {
          showReloginModal('当前账号没有管理权限，请使用管理员账号重新登录');
          return Promise.reject(d);
        }
        return r.ok ? d : Promise.reject(d);
      });
    });
  }

  function formatDate(dateStr) {
    if (!dateStr) return '--';
    var d = new Date(dateStr);
    if (isNaN(d.getTime())) return String(dateStr);
    return d.getFullYear() + '-' +
      String(d.getMonth() + 1).padStart(2, '0') + '-' +
      String(d.getDate()).padStart(2, '0');
  }

  function formatDuration(seconds) {
    if (!seconds || seconds <= 0) return '0分';
    var m = Math.floor(seconds / 60);
    var s = seconds % 60;
    return m + '分' + (s > 0 ? s + '秒' : '');
  }

  function statusBadge(status) {
    var map = { active: 'badge-active', disabled: 'badge-disabled', deleting: 'badge-deleting', deleted: 'badge-deleted', completed: 'badge-completed', recording: 'badge-recording', paused: 'badge-paused', failed: 'badge-failed' };
    var cls = map[status] || '';
    return '<span class="badge ' + cls + '">' + escapeHtml(status) + '</span>';
  }

  function roleBadge(role) {
    var map = { admin: 'badge-admin', super_admin: 'badge-super' };
    var label = { user: '用户', admin: '教师', super_admin: '超管' };
    var cls = map[role] || '';
    return '<span class="badge ' + cls + '">' + (label[role] || role) + '</span>';
  }

  // ─── 事件绑定 ───────────────────────────────────────────
  function initEvents() {
    // Sidebar nav
    var navItems = sidebar.querySelectorAll('.sidebar-nav-item');
    navItems.forEach(function (btn) {
      btn.addEventListener('click', function () {
        switchTab(btn.dataset.tab);
      });
    });

    // Mobile toggle
    if (sidebarToggle) {
      sidebarToggle.addEventListener('click', function () {
        sidebar.classList.toggle('open');
      });
    }

    // Confirm modal
    confirmOk.addEventListener('click', function () {
      confirmModal.classList.add('hidden');
      if (typeof confirmCallback === 'function') confirmCallback();
      confirmCallback = null;
    });
    confirmCancel.addEventListener('click', function () {
      confirmModal.classList.add('hidden');
      confirmCallback = null;
    });

    // Users filters
    var usersSearch = document.getElementById('users-search');
    var usersStatus = document.getElementById('users-status-filter');
    var usersRole = document.getElementById('users-role-filter');
    var searchTimer = null;
    if (usersSearch) usersSearch.addEventListener('input', function () {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(function () { usersPage = 1; loadUsers(); }, 300);
    });
    if (usersStatus) usersStatus.addEventListener('change', function () { usersPage = 1; loadUsers(); });
    if (usersRole) usersRole.addEventListener('change', function () { usersPage = 1; loadUsers(); });

    // Lectures filters
    var lecturesSearch = document.getElementById('lectures-search');
    var lecturesStatus = document.getElementById('lectures-status-filter');
    var lecturesTimer = null;
    if (lecturesSearch) lecturesSearch.addEventListener('input', function () {
      clearTimeout(lecturesTimer);
      lecturesTimer = setTimeout(function () { lecturesPage = 1; loadLectures(); }, 300);
    });
    if (lecturesStatus) lecturesStatus.addEventListener('change', function () { lecturesPage = 1; loadLectures(); });

    // Audit filters
    var auditAction = document.getElementById('audit-action-filter');
    if (auditAction) auditAction.addEventListener('change', function () { auditPage = 1; loadAuditLogs(); });

    var guideSave = document.getElementById('guide-save-btn');
    var guideAdd = document.getElementById('guide-add-item');
    if (guideSave) guideSave.addEventListener('click', saveGuide);
    if (guideAdd) guideAdd.addEventListener('click', function () {
      if (document.querySelectorAll('#guide-items .guide-item-row').length >= 8) {
        toast('最多 8 条说明');
        return;
      }
      addGuideItemRow({ icon: 'info', title: '', body: '' });
    });
  }

  // ─── Tab 切换 ───────────────────────────────────────────
  function switchTab(tab) {
    if (currentTab === tab) return;
    currentTab = tab;

    // Update nav active state
    sidebar.querySelectorAll('.sidebar-nav-item').forEach(function (btn) {
      if (btn.dataset.tab === tab) {
        btn.classList.add('active', 'bg-primary/10', 'text-primary');
        btn.classList.remove('text-on-surface-variant');
      } else {
        btn.classList.remove('active', 'bg-primary/10', 'text-primary');
        btn.classList.add('text-on-surface-variant');
      }
    });

    // Show/hide tab content
    document.querySelectorAll('.tab-content').forEach(function (el) {
      el.style.display = 'none';
      el.classList.remove('active');
    });
    var target = document.getElementById('tab-' + tab);
    if (target) {
      target.style.display = '';
      target.classList.add('active');
    }

    // Lazy load
    if (tab === 'dashboard') loadDashboard();
    else if (tab === 'users') loadUsers();
    else if (tab === 'lectures') loadLectures();
    else if (tab === 'guide') loadGuide();
    else if (tab === 'audit-log') loadAuditLogs();

    // Close mobile sidebar
    sidebar.classList.remove('open');
  }

  // ─── Dashboard ──────────────────────────────────────────
  function loadDashboard() {
    Promise.all([api('/dashboard'), api('/stats/timeseries?days=30')])
      .then(function (results) {
        renderStatCards(results[0]);
        renderSystemInfo(results[0].system_info);
        renderTrendChart(results[1]);
      })
      .catch(function () { toast('加载仪表盘失败'); });
  }

  function renderStatCards(stats) {
    var cards = [
      { icon: 'group', label: '总用户', value: stats.total_users, color: 'text-primary' },
      { icon: 'today', label: '今日活跃(DAU)', value: stats.active_today, color: 'text-green-600' },
      { icon: 'calendar_month', label: '近30日活跃', value: stats.active_30d, color: 'text-teal-600' },
      { icon: 'menu_book', label: '总课堂', value: stats.total_lectures, color: 'text-blue-600' },
      { icon: 'translate', label: '总翻译句', value: stats.total_transcriptions, color: 'text-purple-600' },
      { icon: 'token', label: '近30日LLM Tokens', value: stats.llm_tokens_30d, color: 'text-amber-600' },
      { icon: 'bookmark', label: '总收藏', value: stats.total_bookmarks, color: 'text-orange-500' },
      { icon: 'admin_panel_settings', label: '管理员数', value: stats.admin_count, color: 'text-red-500' },
    ];

    var html = '';
    cards.forEach(function (c) {
      html += '<div class="bg-white rounded-2xl border border-outline-variant/10 p-5 flex items-center gap-4 hover:shadow-md transition-shadow duration-300">' +
        '<div class="w-12 h-12 rounded-xl bg-surface-container flex items-center justify-center flex-shrink-0">' +
          '<span class="material-symbols-outlined text-2xl ' + c.color + '">' + c.icon + '</span>' +
        '</div>' +
        '<div>' +
          '<p class="text-2xl font-bold text-on-surface">' + formatNumber(c.value || 0) + '</p>' +
          '<p class="text-xs text-on-surface-variant">' + c.label + '</p>' +
        '</div>' +
      '</div>';
    });

    document.getElementById('stat-cards').innerHTML = html;
  }

  function formatNumber(value) {
    var n = Number(value) || 0;
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 10000) return (n / 1000).toFixed(1) + 'k';
    return String(n);
  }

  function renderTrendChart(data) {
    var canvas = document.getElementById('trend-chart');
    var legend = document.getElementById('trend-legend');
    if (!canvas || !data || !data.points) return;
    var points = data.points || [];
    var width = Math.max(640, canvas.parentElement ? canvas.parentElement.clientWidth - 24 : 640);
    var height = 180;
    canvas.width = width;
    canvas.height = height;
    var ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, width, height);
    if (!points.length) {
      ctx.fillStyle = '#717782';
      ctx.fillText('暂无趋势数据', 16, 24);
      return;
    }
    var pad = { top: 16, right: 16, bottom: 28, left: 36 };
    var chartW = width - pad.left - pad.right;
    var chartH = height - pad.top - pad.bottom;
    var maxDau = Math.max.apply(null, points.map(function (p) { return p.dau || 0; }).concat([1]));
    var maxTokens = Math.max.apply(null, points.map(function (p) { return p.llm_tokens || 0; }).concat([1]));

    function xAt(i) { return pad.left + (points.length === 1 ? chartW / 2 : (i / (points.length - 1)) * chartW); }
    function yDau(v) { return pad.top + chartH - (v / maxDau) * chartH; }
    function yTok(v) { return pad.top + chartH - (v / maxTokens) * chartH; }

    ctx.strokeStyle = '#E5E7EB';
    ctx.beginPath();
    ctx.moveTo(pad.left, pad.top + chartH);
    ctx.lineTo(pad.left + chartW, pad.top + chartH);
    ctx.stroke();

    function drawLine(getter, color, yFn) {
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      points.forEach(function (p, i) {
        var x = xAt(i), y = yFn(getter(p));
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }
    drawLine(function (p) { return p.dau || 0; }, '#16A34A', yDau);
    drawLine(function (p) { return p.new_users || 0; }, '#2563EB', yDau);
    drawLine(function (p) { return p.llm_tokens || 0; }, '#D97706', yTok);

    ctx.fillStyle = '#9CA3AF';
    ctx.font = '10px sans-serif';
    [0, Math.floor(points.length / 2), points.length - 1].forEach(function (i) {
      if (i < 0 || i >= points.length) return;
      ctx.fillText((points[i].date || '').slice(5), xAt(i) - 12, height - 8);
    });

    if (legend) {
      legend.innerHTML =
        '<span><span class="inline-block w-3 h-1 bg-green-600 mr-1 align-middle"></span>DAU</span>' +
        '<span><span class="inline-block w-3 h-1 bg-blue-600 mr-1 align-middle"></span>新增用户</span>' +
        '<span><span class="inline-block w-3 h-1 bg-amber-600 mr-1 align-middle"></span>LLM Tokens（右轴相对）</span>';
    }
  }

  function renderSystemInfo(info) {
    if (!info) return;
    document.getElementById('system-info').innerHTML =
      '<div><span class="text-on-surface-variant">环境</span><p class="font-semibold mt-1">' + escapeHtml(info.environment) + '</p></div>' +
      '<div><span class="text-on-surface-variant">版本</span><p class="font-semibold mt-1">' + escapeHtml(info.version) + '</p></div>' +
      '<div><span class="text-on-surface-variant">额度窗口</span><p class="font-semibold mt-1">' + (info.llm_quota_window_days || 30) + ' 天</p></div>' +
      '<div><span class="text-on-surface-variant">运行状态</span><p class="font-semibold mt-1 text-green-600">正常</p></div>';
  }

  // ─── 用户管理 ───────────────────────────────────────────
  function loadUsers() {
    var search = document.getElementById('users-search') ? document.getElementById('users-search').value : '';
    var status = document.getElementById('users-status-filter') ? document.getElementById('users-status-filter').value : '';
    var role = document.getElementById('users-role-filter') ? document.getElementById('users-role-filter').value : '';

    var params = '?page=' + usersPage + '&page_size=20';
    if (search) params += '&search=' + encodeURIComponent(search);
    if (status) params += '&status=' + encodeURIComponent(status);
    if (role) params += '&role=' + encodeURIComponent(role);

    api('/users' + params)
      .then(function (data) {
        renderUsersTable(data);
        renderPagination('users-pagination', data.total_pages, usersPage, function (p) { usersPage = p; loadUsers(); });
      })
      .catch(function () { toast('加载用户列表失败'); });
  }

  function renderUsersTable(data) {
    var items = data.items || [];
    if (items.length === 0) {
      document.getElementById('users-table-body').innerHTML = '<tr><td colspan="9" class="text-center py-12 text-on-surface-variant">暂无数据</td></tr>';
      return;
    }

    var html = '';
    items.forEach(function (u) {
      var used = u.tokens_used || 0;
      var limit = u.token_limit || 0;
      var quotaLabel = formatNumber(used) + ' / ' + formatNumber(limit);
      if (u.has_custom_limit) quotaLabel += ' · 自定义';
      html += '<tr>' +
        '<td>' + u.id + '</td>' +
        '<td class="font-medium">' + escapeHtml(u.nickname) + '</td>' +
        '<td>' + escapeHtml(u.phone) + '</td>' +
        '<td>' + roleBadge(u.role) + '</td>' +
        '<td>' + statusBadge(u.status) + '</td>' +
        '<td><span class="badge ' + (u.member_level === 'premium' ? 'badge-premium' : 'badge-free') + '">' + (u.member_level === 'premium' ? '高级' : '免费') + '</span></td>' +
        '<td class="text-xs">' + escapeHtml(quotaLabel) + '</td>' +
        '<td class="text-xs text-on-surface-variant">' + formatDate(u.created_at) + '</td>' +
        '<td class="text-right">' + renderUserActions(u) + '</td>' +
      '</tr>';
    });

    document.getElementById('users-table-body').innerHTML = html;

    // 绑定操作事件
    bindUserActionEvents(items);
  }

  function renderUserActions(u) {
    var actions = '';

    // 状态切换 (不能操作自己，不能操作超管，除非自己是超管)
    if (u.status === 'active') {
      actions += '<button class="user-disable-btn text-xs px-3 py-1.5 rounded-lg bg-orange-50 text-orange-600 hover:bg-orange-100 transition-colors mr-1" data-uid="' + u.id + '">禁用</button>';
    } else if (u.status === 'disabled') {
      actions += '<button class="user-enable-btn text-xs px-3 py-1.5 rounded-lg bg-green-50 text-green-600 hover:bg-green-100 transition-colors mr-1" data-uid="' + u.id + '">启用</button>';
    }

    // 角色变更 (仅超管) — 文案：admin=教师
    actions += '<select class="user-role-select text-xs px-2 py-1.5 rounded-lg border border-outline-variant/30 bg-white mr-1" data-uid="' + u.id + '">' +
      '<option value="user"' + (u.role === 'user' ? ' selected' : '') + '>用户</option>' +
      '<option value="admin"' + (u.role === 'admin' ? ' selected' : '') + '>教师</option>' +
      '<option value="super_admin"' + (u.role === 'super_admin' ? ' selected' : '') + '>超管</option>' +
    '</select>';

    actions += '<button class="user-quota-btn text-xs px-3 py-1.5 rounded-lg bg-amber-50 text-amber-700 hover:bg-amber-100 transition-colors mr-1" data-uid="' + u.id + '" data-limit="' + (u.has_custom_limit ? (u.token_limit || '') : '') + '" data-used="' + (u.tokens_used || 0) + '">额度</button>';

    // 删除 (不能删自己或超管)
    if (u.role !== 'super_admin') {
      actions += '<button class="user-delete-btn text-xs px-3 py-1.5 rounded-lg bg-red-50 text-red-600 hover:bg-red-100 transition-colors" data-uid="' + u.id + '" data-name="' + escapeHtml(u.nickname) + '">删除</button>';
    }

    return actions || '<span class="text-xs text-on-surface-variant">--</span>';
  }

  function bindUserActionEvents(items) {
    // 禁用按钮
    document.querySelectorAll('.user-disable-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var uid = parseInt(btn.dataset.uid);
        showConfirm('确定要禁用该用户吗？', function () {
          api('/users/' + uid + '/status', { method: 'PATCH', body: JSON.stringify({ status: 'disabled' }) })
            .then(function (r) { toast(r.message); loadUsers(); })
            .catch(function (e) { toast(e.detail || '操作失败'); });
        });
      });
    });

    // 启用按钮
    document.querySelectorAll('.user-enable-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var uid = parseInt(btn.dataset.uid);
        api('/users/' + uid + '/status', { method: 'PATCH', body: JSON.stringify({ status: 'active' }) })
          .then(function (r) { toast(r.message); loadUsers(); })
          .catch(function (e) { toast(e.detail || '操作失败'); });
      });
    });

    // 角色变更下拉
    document.querySelectorAll('.user-role-select').forEach(function (sel) {
      sel.dataset.prev = sel.value;
      sel.addEventListener('change', function () {
        var uid = parseInt(sel.dataset.uid);
        var newRole = sel.value;
        var prev = sel.dataset.prev || 'user';
        sel.value = prev;
        var label = newRole === 'super_admin' ? '超级管理员' : newRole === 'admin' ? '教师(admin)' : '普通用户';
        showConfirm('确定要变更该用户角色为 ' + label + ' 吗？', function () {
          api('/users/' + uid + '/role', { method: 'PATCH', body: JSON.stringify({ role: newRole }) })
            .then(function (r) { toast(r.message); loadUsers(); })
            .catch(function (e) { toast(e.detail || '操作失败'); });
        });
      });
    });

    document.querySelectorAll('.user-quota-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var uid = parseInt(btn.dataset.uid, 10);
        var current = btn.dataset.limit;
        var used = btn.dataset.used || '0';
        var input = window.prompt(
          '设置滚动 30 天 LLM Token 上限（已用 ' + used + '）。\n留空并确定 = 恢复会员默认额度；输入 0 表示禁止调用。',
          current || ''
        );
        if (input === null) return;
        var body;
        if (String(input).trim() === '') {
          body = { token_limit: null };
        } else {
          var n = parseInt(String(input).trim(), 10);
          if (isNaN(n) || n < 0) {
            toast('请输入非负整数或留空');
            return;
          }
          body = { token_limit: n };
        }
        api('/users/' + uid + '/quota', { method: 'PATCH', body: JSON.stringify(body) })
          .then(function () { toast('额度已更新'); loadUsers(); })
          .catch(function (e) { toast(e.detail || '更新失败'); });
      });
    });

    // 删除按钮
    document.querySelectorAll('.user-delete-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var uid = parseInt(btn.dataset.uid);
        var name = btn.dataset.name;
        showConfirm('确定要删除用户「' + name + '」吗？此操作不可撤销！', function () {
          api('/users/' + uid, { method: 'DELETE' })
            .then(function (r) { toast(r.message); loadUsers(); })
            .catch(function (e) { toast(e.detail || '操作失败'); });
        });
      });
    });
  }

  // ─── 课堂管理 ───────────────────────────────────────────
  function loadLectures() {
    var search = document.getElementById('lectures-search') ? document.getElementById('lectures-search').value : '';
    var status = document.getElementById('lectures-status-filter') ? document.getElementById('lectures-status-filter').value : '';

    var params = '?page=' + lecturesPage + '&page_size=20';
    if (search) params += '&search=' + encodeURIComponent(search);
    if (status) params += '&status=' + encodeURIComponent(status);

    api('/lectures' + params)
      .then(function (data) {
        renderLecturesTable(data);
        renderPagination('lectures-pagination', data.total_pages, lecturesPage, function (p) { lecturesPage = p; loadLectures(); });
      })
      .catch(function () { toast('加载课堂列表失败'); });
  }

  function renderLecturesTable(data) {
    var items = data.items || [];
    if (items.length === 0) {
      document.getElementById('lectures-table-body').innerHTML = '<tr><td colspan="9" class="text-center py-12 text-on-surface-variant">暂无数据</td></tr>';
      return;
    }

    var html = '';
    items.forEach(function (l) {
      html += '<tr>' +
        '<td>' + l.id + '</td>' +
        '<td><span class="text-sm font-medium">' + escapeHtml(l.user_nickname) + '</span><br><span class="text-xs text-on-surface-variant">ID:' + l.user_id + '</span></td>' +
        '<td class="font-medium">' + escapeHtml(l.course_name) + '</td>' +
        '<td>' + escapeHtml(l.source_lang) + ' → ' + escapeHtml(l.target_lang) + '</td>' +
        '<td>' + formatDuration(l.duration_seconds) + '</td>' +
        '<td>' + (l.sentence_count || 0) + '</td>' +
        '<td>' + statusBadge(l.status) + '</td>' +
        '<td class="text-xs">' + formatDate(l.lecture_date) + '</td>' +
        '<td class="text-right">' +
          '<button class="lecture-delete-btn text-xs px-3 py-1.5 rounded-lg bg-red-50 text-red-600 hover:bg-red-100 transition-colors" data-lid="' + l.id + '" data-name="' + escapeHtml(l.course_name) + '">删除</button>' +
        '</td>' +
      '</tr>';
    });

    document.getElementById('lectures-table-body').innerHTML = html;

    // 绑定删除事件
    document.querySelectorAll('.lecture-delete-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var lid = parseInt(btn.dataset.lid);
        var name = btn.dataset.name;
        showConfirm('确定要删除课堂「' + name + '」吗？关联的翻译和收藏也会被删除。', function () {
          api('/lectures/' + lid, { method: 'DELETE' })
            .then(function (r) { toast(r.message); loadLectures(); })
            .catch(function (e) { toast(e.detail || '操作失败'); });
        });
      });
    });
  }

  // ─── 审计日志 ──────────────────────────────────────────
  function loadAuditLogs() {
    if (!IS_SUPER_ADMIN) return;

    var action = document.getElementById('audit-action-filter') ? document.getElementById('audit-action-filter').value : '';
    var params = '?page=' + auditPage + '&page_size=20';
    if (action) params += '&action=' + encodeURIComponent(action);

    api('/audit-logs' + params)
      .then(function (data) {
        renderAuditTable(data);
        renderPagination('audit-pagination', data.total_pages, auditPage, function (p) { auditPage = p; loadAuditLogs(); });
      })
      .catch(function () { toast('加载审计日志失败'); });
  }

  function renderAuditTable(data) {
    var items = data.items || [];
    if (items.length === 0) {
      document.getElementById('audit-table-body').innerHTML = '<tr><td colspan="7" class="text-center py-12 text-on-surface-variant">暂无记录</td></tr>';
      return;
    }

    var actionLabels = {
      'user.status_active': '用户启用',
      'user.status_disabled': '用户禁用',
      'user.role_admin': '提升教师',
      'user.role_super_admin': '提升超管',
      'user.role_user': '降级用户',
      'user.quota_update': '调整LLM额度',
      'user.delete': '删除用户',
      'lecture.delete': '删除课堂',
      'guide.update': '更新功能说明'
    };

    var html = '';
    items.forEach(function (log) {
      var detailStr = log.detail ? JSON.stringify(log.detail) : '--';
      html += '<tr>' +
        '<td>' + log.id + '</td>' +
        '<td class="font-medium">' + escapeHtml(log.admin_name) + ' (ID:' + log.admin_id + ')</td>' +
        '<td>' + escapeHtml(actionLabels[log.action] || log.action) + '</td>' +
        '<td><span class="text-xs">' + escapeHtml(log.target_type) + ' #' + (log.target_id || '--') + '</span></td>' +
        '<td class="text-xs font-mono">' + escapeHtml(log.ip_address) + '</td>' +
        '<td class="text-xs text-on-surface-variant">' + formatDate(log.created_at) + '</td>' +
        '<td><button class="audit-detail-btn text-xs px-2 py-1 rounded-lg bg-surface-container hover:bg-surface-container-high transition-colors text-on-surface-variant" data-detail="' + escapeHtml(detailStr) + '">查看</button></td>' +
      '</tr>';
    });

    document.getElementById('audit-table-body').innerHTML = html;

    // 详情查看
    document.querySelectorAll('.audit-detail-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        toast(btn.dataset.detail);
      });
    });
  }

  // ─── 功能说明 ──────────────────────────────────────────
  function addGuideItemRow(item) {
    var container = document.getElementById('guide-items');
    if (!container) return;
    item = item || {};
    var row = document.createElement('div');
    row.className = 'guide-item-row rounded-xl border border-outline-variant/20 p-3 space-y-2';
    row.innerHTML =
      '<div class="flex gap-2">' +
        '<input class="guide-item-icon w-32 px-3 py-2 bg-surface-container-low border border-outline-variant/30 rounded-lg text-sm outline-none focus:border-primary" placeholder="图标" maxlength="48" value="' + escapeHtml(item.icon || 'info') + '">' +
        '<input class="guide-item-title flex-1 px-3 py-2 bg-surface-container-low border border-outline-variant/30 rounded-lg text-sm outline-none focus:border-primary" placeholder="条目标题" maxlength="64" value="' + escapeHtml(item.title || '') + '">' +
        '<button type="button" class="guide-item-remove text-xs px-2 py-1 rounded-lg text-red-600 hover:bg-red-50 flex-shrink-0">删除</button>' +
      '</div>' +
      '<textarea class="guide-item-body w-full px-3 py-2 bg-surface-container-low border border-outline-variant/30 rounded-lg text-sm outline-none focus:border-primary resize-y" placeholder="说明内容" maxlength="300" rows="2">' + escapeHtml(item.body || '') + '</textarea>';
    row.querySelector('.guide-item-remove').addEventListener('click', function () {
      if (container.querySelectorAll('.guide-item-row').length <= 1) {
        toast('至少保留一条说明');
        return;
      }
      row.remove();
    });
    container.appendChild(row);
  }

  function collectGuideItems() {
    var rows = document.querySelectorAll('#guide-items .guide-item-row');
    var items = [];
    rows.forEach(function (row) {
      var title = (row.querySelector('.guide-item-title').value || '').trim();
      var body = (row.querySelector('.guide-item-body').value || '').trim();
      var icon = (row.querySelector('.guide-item-icon').value || 'info').trim();
      if (!title && !body) return;
      items.push({ icon: icon || 'info', title: title, body: body });
    });
    return items;
  }

  function loadGuide() {
    api('/guides/recorder_features')
      .then(function (data) {
        document.getElementById('guide-title').value = data.title || '';
        document.getElementById('guide-subtitle').value = data.subtitle || '';
        document.getElementById('guide-footer').value = data.footer_hint || '';
        var updated = document.getElementById('guide-updated');
        if (data.updated_at) {
          updated.textContent = '最近更新：' + formatDate(data.updated_at) + (data.updated_by ? ' · ' + data.updated_by : '');
        } else {
          updated.textContent = '当前为系统默认文案，保存后会覆盖默认内容';
        }
        var container = document.getElementById('guide-items');
        container.innerHTML = '';
        (data.items || []).forEach(function (item) { addGuideItemRow(item); });
        if (!container.children.length) addGuideItemRow({ icon: 'info', title: '', body: '' });
      })
      .catch(function () { toast('加载功能说明失败'); });
  }

  function saveGuide() {
    var items = collectGuideItems();
    if (!items.length) {
      toast('至少填写一条说明');
      return;
    }
    var missing = items.some(function (item) { return !item.title || !item.body; });
    if (missing) {
      toast('每条说明都需要标题和内容');
      return;
    }
    if (items.length > 8) {
      toast('最多 8 条说明');
      return;
    }
    api('/guides/recorder_features', {
      method: 'PUT',
      body: JSON.stringify({
        title: (document.getElementById('guide-title').value || '').trim(),
        subtitle: (document.getElementById('guide-subtitle').value || '').trim(),
        footer_hint: (document.getElementById('guide-footer').value || '').trim(),
        items: items
      })
    })
      .then(function () {
        toast('功能说明已保存');
        loadGuide();
      })
      .catch(function (e) {
        var msg = '保存失败';
        if (e && typeof e.detail === 'string') msg = e.detail;
        else if (e && e.detail && e.detail[0] && e.detail[0].msg) msg = e.detail[0].msg;
        toast(msg);
      });
  }

  // ─── 通用分页渲染 ───────────────────────────────────────
  function renderPagination(containerId, totalPages, currentPage, onPageChange) {
    var container = document.getElementById(containerId);
    if (!container) return;
    if (totalPages <= 1) {
      container.innerHTML = '<span class="text-xs text-on-surface-variant">共 1 页</span>';
      return;
    }

    var html = '<div class="flex items-center gap-2">';
    html += '<button class="pagination-btn" ' + (currentPage <= 1 ? 'disabled' : '') + ' data-page="' + (currentPage - 1) + '">' +
      '<span class="material-symbols-outlined text-sm">chevron_left</span></button>';

    var start = Math.max(1, currentPage - 2);
    var end = Math.min(totalPages, currentPage + 2);
    if (start > 1) {
      html += '<button class="pagination-btn" data-page="1">1</button>';
      if (start > 2) html += '<span class="text-xs text-on-surface-variant px-1">...</span>';
    }
    for (var i = start; i <= end; i++) {
      html += '<button class="pagination-btn' + (i === currentPage ? ' active' : '') + '" data-page="' + i + '">' + i + '</button>';
    }
    if (end < totalPages) {
      if (end < totalPages - 1) html += '<span class="text-xs text-on-surface-variant px-1">...</span>';
      html += '<button class="pagination-btn" data-page="' + totalPages + '">' + totalPages + '</button>';
    }

    html += '<button class="pagination-btn" ' + (currentPage >= totalPages ? 'disabled' : '') + ' data-page="' + (currentPage + 1) + '">' +
      '<span class="material-symbols-outlined text-sm">chevron_right</span></button>';
    html += '</div>';
    html += '<span class="text-xs text-on-surface-variant">共 ' + totalPages + ' 页</span>';

    container.innerHTML = html;

    // 绑定分页事件
    container.querySelectorAll('.pagination-btn[data-page]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var p = parseInt(btn.dataset.page);
        if (p && p !== currentPage && onPageChange) onPageChange(p);
      });
    });
  }

})();
