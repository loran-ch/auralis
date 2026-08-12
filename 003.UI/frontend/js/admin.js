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

  // ─── 初始化 ─────────────────────────────────────────────
  if (!TOKEN) { window.location.href = 'login.html'; return; }

  // 获取当前用户信息，验证管理员身份
  fetch('/api/auth/me')
    .then(function (r) { return r.json(); })
    .then(function (user) {
      if (!user || !user.role || (user.role !== 'admin' && user.role !== 'super_admin')) {
        toast('无管理权限，即将跳转...');
        setTimeout(function () { window.location.href = 'recorder.html'; }, 1500);
        return;
      }
      USER = user;
      IS_SUPER_ADMIN = user.role === 'super_admin';
      adminNameEl.textContent = user.nickname || '管理员';
      adminRoleEl.textContent = IS_SUPER_ADMIN ? '超级管理员' : '管理员';

      // 超管显示审计日志 Tab
      if (IS_SUPER_ADMIN) {
        document.getElementById('nav-audit-log').style.display = '';
      }

      // 加载默认 Tab
      loadDashboard();
      initEvents();
    })
    .catch(function () {
      toast('认证失败，请重新登录');
      setTimeout(function () { window.location.href = 'login.html'; }, 1500);
    });

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
      return r.json().then(function (d) { return r.ok ? d : Promise.reject(d); });
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
    var label = { user: '用户', admin: '管理员', super_admin: '超管' };
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
    else if (tab === 'audit-log') loadAuditLogs();

    // Close mobile sidebar
    sidebar.classList.remove('open');
  }

  // ─── Dashboard ──────────────────────────────────────────
  function loadDashboard() {
    api('/dashboard')
      .then(function (stats) {
        renderStatCards(stats);
        renderSystemInfo(stats.system_info);
      })
      .catch(function () { toast('加载仪表盘失败'); });
  }

  function renderStatCards(stats) {
    var cards = [
      { icon: 'group', label: '总用户', value: stats.total_users, color: 'text-primary' },
      { icon: 'today', label: '今日活跃', value: stats.active_today, color: 'text-green-600' },
      { icon: 'menu_book', label: '总课堂', value: stats.total_lectures, color: 'text-blue-600' },
      { icon: 'translate', label: '总翻译', value: stats.total_transcriptions, color: 'text-purple-600' },
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
          '<p class="text-2xl font-bold text-on-surface">' + (c.value || 0) + '</p>' +
          '<p class="text-xs text-on-surface-variant">' + c.label + '</p>' +
        '</div>' +
      '</div>';
    });

    document.getElementById('stat-cards').innerHTML = html;
  }

  function renderSystemInfo(info) {
    if (!info) return;
    document.getElementById('system-info').innerHTML =
      '<div><span class="text-on-surface-variant">环境</span><p class="font-semibold mt-1">' + escapeHtml(info.environment) + '</p></div>' +
      '<div><span class="text-on-surface-variant">版本</span><p class="font-semibold mt-1">' + escapeHtml(info.version) + '</p></div>' +
      '<div><span class="text-on-surface-variant">数据库连接池</span><p class="font-semibold mt-1">' + (info.db_pool_size || '--') + '</p></div>' +
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
      document.getElementById('users-table-body').innerHTML = '<tr><td colspan="8" class="text-center py-12 text-on-surface-variant">暂无数据</td></tr>';
      return;
    }

    var html = '';
    items.forEach(function (u) {
      html += '<tr>' +
        '<td>' + u.id + '</td>' +
        '<td class="font-medium">' + escapeHtml(u.nickname) + '</td>' +
        '<td>' + escapeHtml(u.phone) + '</td>' +
        '<td>' + roleBadge(u.role) + '</td>' +
        '<td>' + statusBadge(u.status) + '</td>' +
        '<td><span class="badge ' + (u.member_level === 'premium' ? 'badge-premium' : 'badge-free') + '">' + (u.member_level === 'premium' ? '高级' : '免费') + '</span></td>' +
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

    // 角色变更 (仅超管)
    if (IS_SUPER_ADMIN) {
      actions += '<select class="user-role-select text-xs px-2 py-1.5 rounded-lg border border-outline-variant/30 bg-white mr-1" data-uid="' + u.id + '">' +
        '<option value="user"' + (u.role === 'user' ? ' selected' : '') + '>用户</option>' +
        '<option value="admin"' + (u.role === 'admin' ? ' selected' : '') + '>管理员</option>' +
        '<option value="super_admin"' + (u.role === 'super_admin' ? ' selected' : '') + '>超管</option>' +
      '</select>';
    }

    // 删除 (仅超管，不能删自己或超管)
    if (IS_SUPER_ADMIN && u.role !== 'super_admin') {
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
      sel.addEventListener('change', function () {
        var uid = parseInt(sel.dataset.uid);
        var newRole = sel.value;
        showConfirm('确定要变更该用户角色为 ' + (newRole === 'super_admin' ? '超级管理员' : newRole === 'admin' ? '管理员' : '普通用户') + ' 吗？', function () {
          api('/users/' + uid + '/role', { method: 'PATCH', body: JSON.stringify({ role: newRole }) })
            .then(function (r) { toast(r.message); loadUsers(); })
            .catch(function (e) { toast(e.detail || '操作失败'); });
        });
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
      'user.role_admin': '提升管理员',
      'user.role_super_admin': '提升超管',
      'user.role_user': '降级用户',
      'user.delete': '删除用户',
      'lecture.delete': '删除课堂'
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
