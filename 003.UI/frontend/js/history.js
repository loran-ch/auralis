/**
 * LiveTrans Voice — 课堂记录页
 * 会话检查 + API 加载
 */
(function () {
  var API = '/api';
  function api(path, method) {
    var token = localStorage.getItem('livetrans_token') || '';
    return fetch(API + path, {
      method: method || 'GET',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token }
    }).then(function (r) {
      return r.json().then(function (d) { return r.ok ? d : Promise.reject(d); });
    });
  }

  // 未登录时进入登录页，不在前端内置任何账号密码。
  function ensureLogin() {
    if (localStorage.getItem('livetrans_token')) return Promise.resolve();
    window.location.href = 'login.html';
    return Promise.reject(new Error('未登录'));
  }

  function fmSec(s) { var m = Math.floor(s / 60); return m + ':' + String(s % 60).padStart(2, '0'); }
  function escapeHtml(value) {
    var div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  function renderCard(l) {
    var d = (l.started_at || '').split('T')[0] || '';
    var t = '';
    if (l.started_at) { var p = l.started_at.split('T')[1]; t = p ? p.substring(0, 5) : ''; }
    var el = document.createElement('div');
    el.className = 'bg-surface-container-lowest rounded-xl p-4 card-shadow hover:scale-[1.01] transition-transform duration-200 cursor-pointer border border-outline-variant/20';
    el.onclick = function () { window.location.href = 'review.html?id=' + l.id; };
    el.innerHTML =
      '<div class="flex justify-between items-start mb-2">' +
        '<div><h3 class="font-display-current-source text-lg text-ink-deep">' + escapeHtml(l.course_name || '未命名') + '</h3>' +
        '<p class="font-caption-timestamp text-ink-subdued">' + d + ' · ' + t + '</p></div>' +
        '<div class="flex flex-col items-end">' +
          '<span class="font-label-tag text-primary bg-primary-container/20 px-2 py-1 rounded-lg">' + fmSec(l.duration_seconds || 0) + '</span>' +
          (l.bookmark_count > 0 ? '<div class="flex items-center gap-1 mt-1 text-tertiary"><span class="material-symbols-outlined text-[14px]" style="font-variation-settings:\'FILL\' 1;">star</span><span class="font-label-tag">' + l.bookmark_count + '</span></div>' : '') +
        '</div></div>' +
      '<p class="font-body-history-trans text-on-surface-variant line-clamp-2 mt-2 italic border-l-2 border-primary-container pl-3">' +
        escapeHtml(l.source_lang || '') + ' → ' + escapeHtml(l.target_lang || '') + ' | ' + (l.sentence_count || 0) + ' 句话</p>';
    return el;
  }

  function init() {
    var container = document.getElementById('records-container');
    if (!container) return setTimeout(init, 100);

    container.innerHTML = '<div class="text-center py-12 text-on-surface-variant">加载中...</div>';

    // 先确保登录再拉数据
    ensureLogin().then(function () {
      return api('/lectures');
    }).then(function (list) {
      container.innerHTML = '';
      if (!list || !list.length) {
        var empty = document.getElementById('empty-state');
        if (empty) { empty.classList.remove('hidden'); empty.classList.add('flex'); }
        return;
      }
      var empty = document.getElementById('empty-state');
      if (empty) empty.classList.add('hidden');
      list.forEach(function (l) { container.appendChild(renderCard(l)); });
    }).catch(function (err) {
      container.innerHTML = '<div class="text-center py-12 text-error">加载失败<br><button class="mt-3 text-primary underline" onclick="location.reload()">刷新重试</button></div>';
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
