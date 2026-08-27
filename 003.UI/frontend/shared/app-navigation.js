/* LiveTrans Voice — 主页面统一导航菜单。 */
(function () {
  'use strict';

  function currentPage() {
    var page = window.location.pathname.split('/').pop();
    return page || 'recorder.html';
  }

  function closeMenu(menu, toggle) {
    menu.classList.add('hidden');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
  }

  function initMenu(menu) {
    var toggle = document.querySelector('[data-nav-toggle][aria-controls="' + menu.id + '"]');
    var page = currentPage();
    menu.querySelectorAll('[data-nav-page]').forEach(function (link) {
      if (link.getAttribute('href') === page) link.classList.add('is-active');
    });

    if (toggle) {
      toggle.addEventListener('click', function (event) {
        event.stopPropagation();
        var opening = menu.classList.contains('hidden');
        menu.classList.toggle('hidden', !opening);
        toggle.setAttribute('aria-expanded', opening ? 'true' : 'false');
      });
    }

    menu.addEventListener('click', function (event) { event.stopPropagation(); });
    document.addEventListener('click', function () { closeMenu(menu, toggle); });
  }

  function initAuthLink(link) {
    var loggedIn = Boolean(localStorage.getItem('livetrans_token'));
    if (loggedIn) {
      link.innerHTML = '<span class="material-symbols-outlined">logout</span>退出登录';
      link.classList.remove('is-login');
      link.addEventListener('click', function (event) {
        event.preventDefault();
        if (window.LiveTransAuth && window.LiveTransAuth.clearSession) window.LiveTransAuth.clearSession();
        else {
          localStorage.removeItem('livetrans_token');
          localStorage.removeItem('livetrans_refresh_token');
          localStorage.removeItem('livetrans_user');
        }
        window.location.href = 'recorder.html';
      });
      return;
    }
    link.innerHTML = '<span class="material-symbols-outlined">login</span>登录 / 注册';
    link.classList.add('is-login');
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.app-nav-menu').forEach(initMenu);
    document.querySelectorAll('[data-nav-auth]').forEach(initAuthLink);
    document.addEventListener('keydown', function (event) {
      if (event.key !== 'Escape') return;
      document.querySelectorAll('.app-nav-menu:not(.hidden)').forEach(function (menu) {
        var toggle = document.querySelector('[data-nav-toggle][aria-controls="' + menu.id + '"]');
        closeMenu(menu, toggle);
      });
    });
  });
})();
