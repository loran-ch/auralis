/**
 * LiveTrans Voice — authenticated fetch with single-flight token refresh.
 * Protected pages load this before their own scripts, so existing API calls
 * gain Authorization and one safe retry without duplicating refresh logic.
 */
(function () {
  'use strict';

  var nativeFetch = window.fetch.bind(window);
  var refreshPromise = null;
  var publicAuthPaths = {
    '/api/auth/login': true,
    '/api/auth/register': true,
    '/api/auth/send-code': true,
    '/api/auth/refresh': true
  };

  function clearSession() {
    localStorage.removeItem('livetrans_token');
    localStorage.removeItem('livetrans_refresh_token');
    localStorage.removeItem('livetrans_user');
  }

  function requestUrl(input) {
    return new URL(typeof input === 'string' ? input : input.url, window.location.href);
  }

  function fetchWithToken(input, init, token) {
    var options = Object.assign({}, init || {});
    var headers = new Headers(options.headers || (input instanceof Request ? input.headers : undefined));
    // 刷新后必须覆盖调用方携带的旧令牌，否则重试仍会得到 401。
    if (token) {
      headers.set('Authorization', 'Bearer ' + token);
    }
    options.headers = headers;
    return nativeFetch(input, options);
  }

  function refreshAccessToken() {
    if (refreshPromise) return refreshPromise;
    var refreshToken = localStorage.getItem('livetrans_refresh_token');
    if (!refreshToken) return Promise.resolve(null);

    refreshPromise = nativeFetch('/api/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken })
    }).then(function (response) {
      if (!response.ok) throw new Error('session expired');
      return response.json();
    }).then(function (data) {
      if (!data.tokens || !data.tokens.access_token) throw new Error('invalid refresh response');
      localStorage.setItem('livetrans_token', data.tokens.access_token);
      if (data.tokens.refresh_token) {
        localStorage.setItem('livetrans_refresh_token', data.tokens.refresh_token);
      }
      if (data.user) localStorage.setItem('livetrans_user', JSON.stringify(data.user));
      return data.tokens.access_token;
    }).catch(function () {
      clearSession();
      return null;
    }).finally(function () {
      refreshPromise = null;
    });
    return refreshPromise;
  }

  window.fetch = function (input, init) {
    var url = requestUrl(input);
    var isApi = url.origin === window.location.origin && url.pathname.indexOf('/api/') === 0;
    if (!isApi || publicAuthPaths[url.pathname]) return nativeFetch(input, init);

    var token = localStorage.getItem('livetrans_token');
    return fetchWithToken(input, init, token).then(function (response) {
      if (response.status !== 401) return response;
      return refreshAccessToken().then(function (newToken) {
        return newToken ? fetchWithToken(input, init, newToken) : response;
      });
    });
  };

  window.LiveTransAuth = { clearSession: clearSession, refresh: refreshAccessToken };
})();
