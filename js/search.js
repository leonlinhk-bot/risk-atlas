/* search.js — 轻量客户端全文搜索（无外部依赖，离线可用）
 * v2（2026-09-09）：语料补齐 title_en/summary_en/body_en 与繁中字段；支持多词 AND 检索；
 * 支持「先用精简索引出结果，首次输入时懒加载全量语料再精修」。 */
(function () {
  'use strict';

  function stripLinks(s) {
    return String(s == null ? '' : s).replace(/\[\[[^\]]*\]\]/g, ' ');
  }

  /* 搜索语料（短键 s/t/n/e/c/a/b）展开为词条形态；summary 从已加载的索引补齐 */
  function expandRecords(list, base) {
    if (!list || !list.length || list[0].slug) return list || [];
    return list.map(function (r) {
      var b = (base && base[r.s]) || {};
      return {
        slug: r.s, type: r.t, title: r.n, title_en: r.e, en: r.e, code: r.c,
        cross: r.x || '',
        summary: b.summary || b.summary_en || '',
        summary_en: b.summary_en || b.summary || '',
        summary_hk: b.summary_hk || b.summary || '',
        body: r.b || '', aliases: r.a || []
      };
    });
  }

  function buildDocs(entries) {
    return entries.map(function (e) {
      var en = e.en || e.title_en || '';
      var hay = [
        e.title, e.title_en, en, e.cross, e.code, e.slug, e.category,
        e.summary, e.summary_en, e.summary_hk,
        stripLinks(e.body), stripLinks(e.body_en), stripLinks(e.body_hk),
        (e.track && e.track.name) || '',
        (e.modules || []).join(' '),
        (e.modules_en || []).join(' '),
        (e.modules_hk || []).join(' '),
        (e.aliases || []).join(' ')
      ].join(' ').toLowerCase();
      return {
        slug: e.slug, title: e.title, titleEn: e.title_en || en, en: en,
        cross: e.cross || '', code: e.code || '', type: e.type, summary: e.summary,
        aliases: e.aliases || [], hay: hay
      };
    });
  }

  /* 单词打分（q 已小写） */
  function scoreToken(doc, q) {
    var s = 0;
    var t = doc.title.toLowerCase();
    var te = String(doc.titleEn || '').toLowerCase();
    var code = doc.code.toLowerCase();
    var slug = doc.slug.toLowerCase();
    if (t === q) s += 100; else if (t.indexOf(q) === 0) s += 80; else if (t.indexOf(q) !== -1) s += 60;
    if (te) { if (te === q) s += 95; else if (te.indexOf(q) === 0) s += 75; else if (te.indexOf(q) !== -1) s += 55; }
    var cx = String(doc.cross || '').toLowerCase();
    if (cx) { if (cx === q) s += 85; else if (cx.indexOf(q) === 0) s += 65; else if (cx.indexOf(q) !== -1) s += 50; }
    if (code === q || slug === q) s += 90; else if (code.indexOf(q) !== -1 || slug.indexOf(q) !== -1) s += 40;
    if ((doc.aliases || []).some(function (a) { return String(a).toLowerCase().indexOf(q) !== -1; })) s += 30;
    if (doc.summary && doc.summary.toLowerCase().indexOf(q) !== -1) s += 25;
    if (doc.hay.indexOf(q) !== -1) s += 12;
    return s;
  }

  /* 多词查询：所有词都要命中（AND），总分相加 */
  function score(doc, q) {
    var parts = String(q).split(/\s+/).filter(Boolean);
    if (!parts.length) return 0;
    var total = 0;
    for (var i = 0; i < parts.length; i++) {
      var s = scoreToken(doc, parts[i]);
      if (s === 0) return 0;
      total += s;
    }
    return total + (parts.length > 1 ? 10 : 0); // 多词精确匹配轻微加权
  }

  function search(docs, q, typeFilter) {
    q = String(q || '').trim().toLowerCase();
    if (!q) return [];
    var parts = q.split(/\s+/).filter(Boolean);
    function collect(any) {
      var out = [];
      docs.forEach(function (d) {
        if (typeFilter && typeFilter !== 'all' && d.type !== typeFilter) return;
        if (!any) { var s = score(d, q); if (s > 0) out.push({ doc: d, score: s }); return; }
        // OR 降级：命中任一 token 即入选，按命中数 + 分数排序
        var hit = 0, tot = 0;
        for (var i = 0; i < parts.length; i++) { var sc = scoreToken(d, parts[i]); if (sc > 0) { hit++; tot += sc; } }
        if (hit > 0) out.push({ doc: d, score: tot + hit * 5 });
      });
      out.sort(function (a, b) { return b.score - a.score; });
      return out.slice(0, 14).map(function (o) { return o.doc; });
    }
    var strict = collect(false);
    return strict.length ? strict : (parts.length > 1 ? collect(true) : strict);
  }

  /* 挂载到输入框 + 结果容器
   * opts.fullLoader: 可选，返回 Promise<entries>；用于「先用精简索引秒出结果，再懒加载全量语料精修」 */
  function attach(inputEl, resultEl, entries, opts) {
    opts = opts || {};
    var docs = buildDocs(entries);
    var baseMap = {};
    (entries || []).forEach(function (e) { baseMap[e.slug] = e; });
    var typeFilter = 'all';
    var tm, fullLoading = false, fullLoaded = false;

    function typeTag(d) {
      return '<span class="tag ' + (window.Wiki ? Wiki.tagClass(d.type) : 'tag-course') + '">' +
        (window.Wiki ? Wiki.typeLabel(d.type) : d.type) + '</span>';
    }
    function render(list, note) {
      resultEl.innerHTML = '';
      if (!inputEl.value.trim()) { resultEl.classList.remove('show'); return; }
      if (note) resultEl.innerHTML = '<div class="sr-empty">' + note + '</div>';
      if (list.length === 0) {
        if (!note) resultEl.innerHTML = '<div class="sr-empty">没有找到匹配词条</div>';
      } else {
        if (note) resultEl.insertAdjacentHTML('beforeend', '<div class="sr-empty">' + note + '</div>');
        list.forEach(function (d) {
          var a = document.createElement('a');
          a.className = 'sr-item';
          a.href = 'wiki.html?slug=' + encodeURIComponent(d.slug);
          a.innerHTML = '<b>' + window.Wiki.escapeHtml(window.Wiki.compactTitle(d.title, 46)) + '</b> ' +
            (d.titleEn && d.titleEn !== d.title ? '<span class="muted">' + window.Wiki.escapeHtml(d.titleEn) + '</span> ' : '') +
            (d.code ? '<span class="muted">' + d.code + '</span> ' : '') +
            typeTag(d) +
            '<small class="muted">' + window.Wiki.escapeHtml(d.summary || '') + '</small>';
          resultEl.appendChild(a);
        });
      }
      resultEl.classList.add('show');
    }
    function run() {
      render(search(docs, inputEl.value, typeFilter));
      if (opts.fullLoader && !fullLoaded) {
        if (!fullLoading) {
          fullLoading = true;
          Promise.resolve()
            .then(opts.fullLoader)
            .then(function (list) {
              if (list && list.length) { docs = buildDocs(expandRecords(list, baseMap)); fullLoaded = true; }
            })
            .catch(function () {})
            .then(function () { fullLoading = false; if (inputEl.value.trim()) render(search(docs, inputEl.value, typeFilter)); });
        } else {
          render(search(docs, inputEl.value, typeFilter), '正在加载完整索引…');
        }
      }
    }

    inputEl.addEventListener('input', function () {
      clearTimeout(tm);
      tm = setTimeout(run, 120);
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
    return { setType: function (t) { typeFilter = t; }, docs: function () { return docs; } };
  }

  window.Search = { search: search, attach: attach, buildDocs: buildDocs, expandRecords: expandRecords };
})();
