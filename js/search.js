/* search.js — 轻量客户端全文搜索（无外部依赖，离线可用） */
(function () {
  'use strict';

  function stripLinks(s) {
    return String(s == null ? '' : s).replace(/\[\[[^\]]*\]\]/g, ' ');
  }

  function buildDocs(entries) {
    return entries.map(function (e) {
      var hay = [
        e.title, e.en, e.code, e.summary, stripLinks(e.body),
        (e.track && e.track.name) || '',
        (e.modules || []).join(' '),
        (e.modules_en || []).join(' '),
        (e.modules_hk || []).join(' '),
        (e.aliases || []).join(' ')
      ].join(' ').toLowerCase();
      return { slug: e.slug, title: e.title, code: e.code || '', type: e.type, summary: e.summary, aliases: e.aliases || [], hay: hay };
    });
  }

  function score(doc, q) {
    var title = doc.title.toLowerCase();
    var en = (doc.en || '').toLowerCase();
    var code = (doc.code || '').toLowerCase();
    var slug = doc.slug.toLowerCase();
    var s = 0;
    if (title === q) s += 100;
    else if (title.indexOf(q) === 0) s += 80;
    else if (title.indexOf(q) !== -1) s += 60;
    if (en.indexOf(q) !== -1) s += 35;
    if (code === q || slug === q) s += 90;
    if ((doc.aliases || []).some(function (a) { return a.toLowerCase().indexOf(q) !== -1; })) s += 30;
    if (doc.summary && doc.summary.toLowerCase().indexOf(q) !== -1) s += 25;
    if (doc.hay.indexOf(q) !== -1) s += 12;
    return s;
  }

  function search(docs, q, typeFilter) {
    q = String(q || '').trim().toLowerCase();
    if (!q) return [];
    var out = [];
    docs.forEach(function (d) {
      if (typeFilter && typeFilter !== 'all' && d.type !== typeFilter) return;
      var s = score(d, q);
      if (s > 0) out.push({ doc: d, score: s });
    });
    out.sort(function (a, b) { return b.score - a.score; });
    return out.slice(0, 14).map(function (o) { return o.doc; });
  }

  /* 挂载到输入框 + 结果容器 */
  function attach(inputEl, resultEl, entries, opts) {
    opts = opts || {};
    var docs = buildDocs(entries);
    var typeFilter = 'all';
    var tm;

    function typeTag(d) {
      return '<span class="tag ' + (window.Wiki ? Wiki.tagClass(d.type) : 'tag-course') + '">' +
        (window.Wiki ? Wiki.typeLabel(d.type) : d.type) + '</span>';
    }
    function render(list) {
      resultEl.innerHTML = '';
      if (!inputEl.value.trim()) { resultEl.classList.remove('show'); return; }
      if (list.length === 0) {
        resultEl.innerHTML = '<div class="sr-empty">没有找到匹配词条</div>';
      } else {
        list.forEach(function (d) {
          var a = document.createElement('a');
          a.className = 'sr-item';
          a.href = 'wiki.html?slug=' + encodeURIComponent(d.slug);
          a.innerHTML = '<b>' + window.Wiki.escapeHtml(d.title) + '</b> ' +
            (d.code ? '<span class="muted">' + d.code + '</span> ' : '') +
            typeTag(d) +
            '<small class="muted">' + window.Wiki.escapeHtml(d.summary || '') + '</small>';
          resultEl.appendChild(a);
        });
      }
      resultEl.classList.add('show');
    }

    inputEl.addEventListener('input', function () {
      clearTimeout(tm);
      tm = setTimeout(function () {
        render(search(docs, inputEl.value, typeFilter));
      }, 120);
    });
    inputEl.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { resultEl.classList.remove('show'); inputEl.blur(); }
      if (e.key === 'Enter') {
        var first = resultEl.querySelector('.sr-item');
        if (first) window.location.href = first.href;
      }
    });
    document.addEventListener('click', function (e) {
      if (!resultEl.contains(e.target) && e.target !== inputEl) resultEl.classList.remove('show');
    });

    if (opts.filterEl) {
      opts.filterEl.addEventListener('change', function () {
        typeFilter = opts.filterEl.value;
        render(search(docs, inputEl.value, typeFilter));
      });
    }
    return { setType: function (t) { typeFilter = t; } };
  }

  window.Search = { search: search, attach: attach, buildDocs: buildDocs };
})();
