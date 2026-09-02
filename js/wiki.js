/* wiki.js — 词条核心：加载、双链渲染、反向链接、类型标签 */
(function () {
  'use strict';

  var LINK_RE = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g;

  var TYPE_LABEL = {
    course: '课程',
    concept: '概念',
    tool: '工具',
    framework: '框架',
    track: '纵深线',
    credential: '考牌',
    job: '岗位',
    employer: '雇主',
    channel: '渠道',
    resource: '资源'
  };

  var TYPE_TAG_CLASS = {
    course: 'tag-course',
    concept: 'tag-concept',
    tool: 'tag-tool',
    framework: 'tag-framework',
    track: 'tag-track',
    credential: 'tag-credential',
    job: 'tag-job',
    employer: 'tag-employer',
    channel: 'tag-channel',
    resource: 'tag-resource'
  };

  function fetchJSON(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error('无法加载 ' + url + ' (' + r.status + ')');
      return r.json();
    });
  }

  /* 载入 entries.json */
  function load() {
    return fetchJSON('data/entries.json');
  }

  /* 建立 slug -> entry 索引 */
  function index(entries) {
    var map = {};
    (entries || []).forEach(function (e) { map[e.slug] = e; });
    return map;
  }

  /* 把 [[slug]] / [[slug|文本]] 渲染成链接 */
  function renderLinks(text, idx) {
    if (text == null) return '';
    return String(text).replace(LINK_RE, function (m, slug, label) {
      slug = slug.trim();
      var display = label ? label.trim() : (idx[slug] ? idx[slug].title : slug);
      if (idx[slug]) {
        return '<a class="wikilink" href="wiki.html?slug=' + encodeURIComponent(slug) + '">' + escapeHtml(display) + '</a>';
      }
      return '<span class="wikilink-missing" title="词条不存在">' + escapeHtml(display) + '</span>';
    });
  }

  /* body 拆成段落（双换行），逐段渲染双链 */
  function renderBody(body, idx) {
    var out = [];
    String(body || '').split(/\n\s*\n/).forEach(function (block) {
      block = block.trim();
      if (!block) return;
      var lines = block.split('\n');
      var i = 0;
      var m = lines[0].match(/^#{2,4}\s+(.*)$/);
      if (m) { out.push('<h3>' + renderLinks(m[1].trim(), idx) + '</h3>'); i = 1; }
      var rest = lines.slice(i);
      var isList = rest.length > 0 && rest.every(function (l) { return /^\s*[-*]\s+/.test(l.trim()); });
      if (isList) {
        out.push('<ul>' + rest.map(function (l) {
          return '<li>' + renderLinks(l.trim().replace(/^\s*[-*]\s+/, ''), idx) + '</li>';
        }).join('') + '</ul>');
      } else if (rest.length > 0) {
        out.push('<p>' + renderLinks(rest.join(' '), idx) + '</p>');
      }
    });
    return out.join('');
  }

  /* 收集一个词条内出现的所有出链 slug（含 body 与结构化字段） */
  function outgoingSlugs(entry) {
    var found = {};
    var body = entry.body || '';
    var m;
    LINK_RE.lastIndex = 0;
    while ((m = LINK_RE.exec(body)) !== null) found[m[1].trim()] = true;

    (entry.aiTools || []).forEach(function (t) {
      var mm = String(t).match(/^\[\[([^\]|]+)/);
      if (mm) found[mm[1].trim()] = true;
    });

    ['concepts', 'courses', 'usedIn', 'credentials', 'employers'].forEach(function (k) {
      (entry[k] || []).forEach(function (s) { found[String(s).trim()] = true; });
    });
    if (entry.pair) found[entry.pair] = true;
    if (entry.track) {
      if (typeof entry.track === 'object') found[entry.track.slug] = true;
      else found[String(entry.track).trim()] = true;
    }

    return Object.keys(found);
  }

  /* 反向链接：哪些词条引用了 slug */
  function backlinks(entries, slug) {
    return entries.filter(function (e) {
      if (e.slug === slug) return false;
      return outgoingSlugs(e).indexOf(slug) !== -1;
    });
  }

  /* 每个词条的入度（用于首页热门排序） */
  function inDegreeMap(entries) {
    var deg = {};
    entries.forEach(function (e) { deg[e.slug] = 0; });
    entries.forEach(function (e) {
      outgoingSlugs(e).forEach(function (s) {
        if (deg[s] != null) deg[s] += 1;
      });
    });
    return deg;
  }

  function typeLabel(t) { return TYPE_LABEL[t] || t; }
  function tagClass(t) { return TYPE_TAG_CLASS[t] || 'tag-course'; }

  /* 从 entry.track（对象或字符串）解析 {slug,name} */
  function trackRef(entry, idx) {
    var t = entry.track;
    if (!t) return null;
    var slug = typeof t === 'object' ? t.slug : t;
    var e = idx && idx[slug];
    return { slug: slug, name: e ? tr(e, 'title') : (typeof t === 'object' ? t.name : slug) };
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /* 通用词条 URL */
  function entryHref(slug) { return 'wiki.html?slug=' + encodeURIComponent(slug); }

  /* ---- Markdown 渲染（周报正文用：标题/列表/粗体/表格/引用）---- */
  function inlineMd(text, idx) {
    text = renderLinks(text, idx);
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    return text;
  }
  function renderTable(rows, idx) {
    var html = '<table>';
    rows.forEach(function (r, ri) {
      if (/^\s*\|[\s:|-]+\|\s*$/.test(r)) return;
      var cells = r.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|');
      var tag = ri === 0 ? 'th' : 'td';
      html += '<tr>' + cells.map(function (c) { return '<' + tag + '>' + inlineMd(c.trim(), idx) + '</' + tag + '>'; }).join('') + '</tr>';
    });
    return html + '</table>';
  }
  function renderMarkdown(md, idx) {
    var lines = String(md || '').split('\n');
    var out = [];
    var i = 0;
    var secCount = 0; // `##` 章节锚点计数器（供周报目录侧栏跳转）
    /* 递归渲染（可嵌套）列表：`- ` / `* `，子项靠缩进判定 */
    function listHtml(startIndent) {
      var html = '<ul>';
      while (i < lines.length) {
        var m = lines[i].match(/^(\s*)[-*]\s+(.*)$/);
        if (!m) break;
        var ind = m[1].length;
        if (ind < startIndent) break;
        var content = m[2];
        i++;
        var sub = '';
        if (i < lines.length) {
          var pm = lines[i].match(/^(\s*)[-*]\s+/);
          if (pm && pm[1].length > ind) {
            var r = listHtml(pm[1].length);
            sub = r.html;
            i = r.i;
          }
        }
        html += '<li>' + inlineMd(content, idx) + sub + '</li>';
      }
      return { html: html + '</ul>', i: i };
    }
    while (i < lines.length) {
      var line = lines[i];
      if (!line.trim()) { i++; continue; }
      /* 围栏代码块 ``` ... ``` */
      if (/^\s*```/.test(line)) {
        var cb = [];
        i++;
        while (i < lines.length && !/^\s*```/.test(lines[i])) { cb.push(lines[i]); i++; }
        i++; // 跳过闭合 ```
        out.push('<pre><code>' + escapeHtml(cb.join('\n')) + '</code></pre>');
        continue;
      }
      if (/^\s*\|/.test(line) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|/.test(lines[i + 1])) {
        var tb = [];
        while (i < lines.length && /^\s*\|/.test(lines[i])) { tb.push(lines[i]); i++; }
        out.push(renderTable(tb, idx));
        continue;
      }
      if (/^\s*>/.test(line)) {
        var q = [];
        while (i < lines.length && /^\s*>/.test(lines[i])) { q.push(lines[i].replace(/^\s*>\s?/, '')); i++; }
        out.push('<blockquote>' + inlineMd(q.join('<br>'), idx) + '</blockquote>');
        continue;
      }
      var hm = line.match(/^#{1,4}\s+(.*)$/);
      if (hm) {
        var lvl = line.match(/^#+/)[0].length;
        var id = (lvl === 2) ? ' id="sec-' + (secCount++) + '"' : '';
        out.push('<h' + (lvl + 1) + id + '>' + inlineMd(hm[1], idx) + '</h' + (lvl + 1) + '>');
        i++; continue;
      }
      if (/^\s*[-*]\s+/.test(line)) {
        var r = listHtml((line.match(/^\s*/) || [''])[0].length);
        out.push(r.html);
        i = r.i;
        continue;
      }
      if (/^\s*-{3,}\s*$/.test(line)) { out.push('<hr>'); i++; continue; }
      var para = [];
      while (i < lines.length && lines[i].trim() && !/^\s*(#|>|\||-\s+|\*\s+|`{3})/.test(lines[i])) { para.push(lines[i]); i++; }
      if (para.length === 0) { i++; continue; } // 防御：确保 i 一定前进
      out.push('<p>' + inlineMd(para.join(' '), idx) + '</p>');
    }
    return out.join('');
  }

  /* ---- 三语支持（默认英文优先，缺失回退中文）---- */
  function currentLang() {
    try { return window.localStorage.getItem('riskatlas.lang') || 'en'; } catch (e) { return 'en'; }
  }
  function tr(e, field) {
    if (!e) return '';
    var lang = currentLang();
    var v = e[field];
    if (lang === 'zh-hk' && e[field + '_hk'] && String(e[field + '_hk']).trim()) v = e[field + '_hk'];
    if (lang === 'en' && e[field + '_en'] && String(e[field + '_en']).trim()) v = e[field + '_en'];
    return v || '';
  }
  function trModules(e) {
    if (!e) return [];
    var lang = currentLang();
    if (lang === 'en' && Array.isArray(e.modules_en) && e.modules_en.length) return e.modules_en;
    if (lang === 'zh-hk' && Array.isArray(e.modules_hk) && e.modules_hk.length) return e.modules_hk;
    return Array.isArray(e.modules) ? e.modules : [];
  }
  function attachLangSwitcher(container) {
    var langs = [['zh-cn', '简'], ['zh-hk', '繁'], ['en', 'EN']];
    var cur = currentLang();
    container.innerHTML = langs.map(function (l) {
      return '<a class="lang-btn' + (l[0] === cur ? ' active' : '') + '" href="#" data-lang="' + l[0] + '">' + l[1] + '</a>';
    }).join('');
    container.addEventListener('click', function (ev) {
      var a = ev.target && ev.target.closest ? ev.target.closest('.lang-btn') : null;
      if (a) {
        ev.preventDefault();
        try { window.localStorage.setItem('riskatlas.lang', a.getAttribute('data-lang')); } catch (err) {}
        window.location.reload();
      }
    });
  }

  window.Wiki = {
    load: load,
    index: index,
    renderLinks: renderLinks,
    renderBody: renderBody,
    backlinks: backlinks,
    inDegreeMap: inDegreeMap,
    typeLabel: typeLabel,
    tagClass: tagClass,
    trackRef: trackRef,
    entryHref: entryHref,
    escapeHtml: escapeHtml,
    outgoingSlugs: outgoingSlugs,
    renderMarkdown: renderMarkdown,
    currentLang: currentLang,
    tr: tr,
    trBody: function (e) { return tr(e, 'body'); },
    trModules: trModules,
    attachLangSwitcher: attachLangSwitcher
  };
})();
