/**
 * LiveTrans — 共享配置: 路由 + API + 认证
 * 依据: PRD v1.01 §6.3 色彩规范
 */
window.LiveTrans = {
  // API 基础地址 (与当前页面同源)
  apiBase: window.location.origin + '/api',

  routes: {
    login:           'login.html',
    register:        'register.html',
    viewfinder:      'viewfinder.html',
    viewfinderAlt:   'viewfinder-alt.html',
    history:         'history.html',
    historyDetail:   'history-detail.html',
    profile:         'profile.html',
    editProfile:     'edit-profile.html',
    language:        'language.html',
    settings:        'settings.html',
  },

  // 统一跳转函数
  go: function(page) {
    // 如果当前在 pages/ 子目录，跳转需保持同目录
    const url = this.routes[page];
    if (url) window.location.href = url;
    else console.warn('LiveTrans: 未知路由 →', page);
  },

  goScreen: function(screenId) {
    const map = {
      'SCREEN_13': 'settings', 'SCREEN_14': 'profile',
      'SCREEN_19': 'history',  'SCREEN_21': 'historyDetail',
      'SCREEN_24': 'register', 'SCREEN_27': 'viewfinder',
      'SCREEN_30': 'login',    'SCREEN_28': 'language',
    };
    const page = map[screenId];
    if (page) this.go(page);
    else console.warn('LiveTrans: 未知屏幕ID →', screenId);
  },

  // ─── 认证 ─────────────────────────────────────────

  /** 保存登录凭证到 localStorage */
  saveAuth: function(user, tokens) {
    localStorage.setItem('livetrans_user', JSON.stringify(user));
    localStorage.setItem('livetrans_token', tokens.access_token);
    localStorage.setItem('livetrans_refresh', tokens.refresh_token);
  },

  /** 获取当前用户信息 */
  getUser: function() {
    const raw = localStorage.getItem('livetrans_user');
    return raw ? JSON.parse(raw) : null;
  },

  /** 获取 Access Token */
  getToken: function() {
    return localStorage.getItem('livetrans_token');
  },

  /** 是否已登录 */
  isLoggedIn: function() {
    return !!this.getToken();
  },

  /** 显示用户名（未登录返回空字符串） */
  getUserName: function() {
    const user = this.getUser();
    return user ? (user.nickname || user.email || '用户') : '';
  },

  /** 退出登录 */
  logout: function() {
    localStorage.removeItem('livetrans_user');
    localStorage.removeItem('livetrans_token');
    localStorage.removeItem('livetrans_refresh');
    // 跳回登录页
    window.location.href = this.isInPagesDir() ? 'login.html' : 'pages/login.html';
  },

  /** 判断是否在 pages/ 子目录中 */
  isInPagesDir: function() {
    return window.location.pathname.includes('/pages/');
  },

  /** 回到根目录登录页 */
  goLogin: function() {
    window.location.href = this.isInPagesDir() ? '../index.html' : 'index.html';
  },

  // ─── API 调用 ──────────────────────────────────────

  /** 通用 API 请求 */
  api: async function(path, options = {}) {
    const url = this.apiBase + path;
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    const token = this.getToken();
    if (token) headers['Authorization'] = 'Bearer ' + token;
    try {
      const res = await fetch(url, { ...options, headers });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || '请求失败');
      return data;
    } catch (err) {
      throw err;
    }
  },

  /** 显示页面中的某个元素 */
  showEl: function(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = '';
  },

  /** 隐藏页面中的某个元素 */
  hideEl: function(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  },

  /** 在所有页面加载完成后更新 UI（显示用户名等） */
  initUI: function() {
    const user = this.getUser();
    // 更新所有用户名占位
    document.querySelectorAll('.js-username').forEach(function(el) {
      el.textContent = user ? (user.nickname || user.email) : '';
    });
    document.querySelectorAll('.js-logged-in').forEach(function(el) {
      el.style.display = user ? '' : 'none';
    });
    document.querySelectorAll('.js-logged-out').forEach(function(el) {
      el.style.display = user ? 'none' : '';
    });
  }
};

// 页面加载完成后自动初始化 UI
document.addEventListener('DOMContentLoaded', function() {
  LiveTrans.initUI();
});

/**
 * Tailwind 配置 — 基于 PRD 色彩规范 + Alexandria Design System
 */
tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // PRD 主色
        "brand-primary": "#4A90D9",
        "brand-primary-dark": "#3A7BC8",
        "brand-green": "#4CAF50",
        "brand-green-light": "#81C784",
        "brand-orange": "#FF9800",

        // Alexandria Design System
        "primary": "#094cb2",
        "primary-container": "#3366cc",
        "primary-fixed": "#d9e2ff",
        "primary-fixed-dim": "#b1c5ff",
        "on-primary": "#ffffff",
        "on-primary-container": "#e7ebff",
        "on-primary-fixed": "#001946",
        "on-primary-fixed-variant": "#00419d",

        "secondary": "#5a5f63",
        "secondary-container": "#dfe3e8",
        "secondary-fixed": "#dfe3e8",
        "secondary-fixed-dim": "#c2c7cc",
        "on-secondary": "#ffffff",
        "on-secondary-container": "#606569",
        "on-secondary-fixed": "#171c20",
        "on-secondary-fixed-variant": "#42474b",

        "tertiary": "#6d5e00",
        "tertiary-container": "#bfab49",
        "tertiary-fixed": "#f9e37a",
        "tertiary-fixed-dim": "#dcc661",
        "on-tertiary": "#ffffff",
        "on-tertiary-container": "#4a3f00",
        "on-tertiary-fixed": "#211b00",
        "on-tertiary-fixed-variant": "#524600",

        "error": "#ba1a1a",
        "error-container": "#ffdad6",
        "on-error": "#ffffff",
        "on-error-container": "#93000a",

        "surface": "#faf9fa",
        "surface-bright": "#faf9fa",
        "surface-dim": "#dbdadb",
        "surface-variant": "#e3e2e3",
        "surface-container": "#efedee",
        "surface-container-low": "#f5f3f4",
        "surface-container-lowest": "#ffffff",
        "surface-container-high": "#e9e8e9",
        "surface-container-highest": "#e3e2e3",

        "on-surface": "#1b1c1d",
        "on-surface-variant": "#434653",
        "on-background": "#1b1c1d",

        "outline": "#737784",
        "outline-variant": "#c3c6d5",
        "background": "#faf9fa",
        "inverse-surface": "#303031",
        "inverse-primary": "#b1c5ff",
        "inverse-on-surface": "#f2f0f1",
        "surface-tint": "#2259bf",
      },
      borderRadius: {
        "DEFAULT": "0.125rem",
        "lg": "0.25rem",
        "xl": "0.5rem",
        "full": "0.75rem",
      },
      spacing: {
        "action-bar-height": "5rem",
        "viewfinder-margin": "1rem",
        "safe-area-top": "4rem",
        "card-padding": "1.25rem",
        "gutter": "1rem",
      },
      fontFamily: {
        "display": ["Noto Serif", "serif"],
        "headline": ["Noto Serif", "serif"],
        "body": ["Inter", "sans-serif"],
        "label": ["Public Sans", "sans-serif"],
      },
    },
  },
};
