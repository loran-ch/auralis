/**
 * LiveTrans Voice — 知识卡片交互
 */
(function () {
  var TOKEN = localStorage.getItem('livetrans_token');
  var tagNames = { important: '⭐重要', question: '❓疑问', exam: '🎯考点', definition: '📖定义' };
  var tagColors = { important: 'bg-orange-500', question: 'bg-primary', exam: 'bg-alert-red', definition: 'bg-accent-purple' };

  var grid = document.getElementById('cards-grid');
  var summaryCount = document.getElementById('summary-count');

  // 没有 grid 说明不在知识卡片页面
  if (!grid) return;

  function loadCards() {
    fetch('/api/bookmarks', {
      headers: { 'Authorization': 'Bearer ' + (TOKEN || '') }
    })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (list) {
        if (!grid) return;
        grid.innerHTML = '';

        if (!list || !Array.isArray(list) || !list.length) {
          grid.innerHTML = '<div class="col-span-full text-center py-12 text-on-surface-variant">还没有收藏，去<a class="text-primary font-bold" href="recorder.html">录音</a>吧</div>';
          if (summaryCount) summaryCount.textContent = '0';
          return;
        }

        // 更新统计数
        if (summaryCount) summaryCount.textContent = String(list.length);

        list.forEach(function (b) {
          var d = document.createElement('div');
          d.className = 'knowledge-card bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-stack-md flex flex-col gap-stack-sm shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-200';
          d.innerHTML =
            '<div class="flex justify-between items-start mb-1">' +
              '<span class="' + (tagColors[b.tag] || 'bg-primary') + ' text-white px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider">' + (tagNames[b.tag] || b.tag) + '</span>' +
              '<span class="font-caption-timestamp text-ink-subdued">' + (b.created_at ? new Date(b.created_at).toLocaleString('zh-CN') : '') + '</span>' +
            '</div>' +
            '<div class="flex flex-col gap-2">' +
              '<p class="text-ink-deep leading-relaxed">' + escapeHtml(b.source_text || '') + '</p>' +
              '<p class="text-secondary leading-relaxed italic">' + escapeHtml(b.translated_text || '') + '</p>' +
            '</div>' +
            '<div class="mt-4 pt-4 border-t border-outline-variant/20 flex gap-2">' +
              '<a class="flex-1 py-2 rounded-lg bg-surface-container text-primary font-label-tag hover:bg-primary/5 transition-colors flex items-center justify-center gap-2" href="recorder.html"><span class="material-symbols-outlined text-[18px]">play_circle</span>去听录音</a>' +
            '</div>';
          grid.appendChild(d);
        });
      })
      .catch(function (err) {
        console.error('loadCards error:', err);
        if (grid) {
          grid.innerHTML = '<div class="col-span-full text-center py-12 text-error">加载失败，请确认已<a class="text-primary font-bold underline" href="login.html">登录</a></div>';
        }
      });
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  // 启动
  if (TOKEN) {
    loadCards();
  } else {
    grid.innerHTML = '<div class="col-span-full text-center py-12 text-on-surface-variant">请先<a class="text-primary font-bold" href="login.html">登录</a></div>';
  }
})();
