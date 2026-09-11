/* graph.js — 知识宇宙（ECharts 力导向图 + 无 ECharts 时的降级列表）
 * v2（2026-09-09）：改为消费预计算的 data/graph.json（nodes + links），
 *   前端不再加载 2.8MB entries.json、不再现算边；支持 limit（按度数取 top-N）与类型筛选。 */
(function () {
  'use strict';

  var COLORS = {
    course: '#14356a',
    concept: '#c9a227',
    tool: '#2e8b57',
    framework: '#8e44ad',
    track: '#d9534f',
    credential: '#0e7490',
    job: '#b45309',
    employer: '#1d4ed8',
    channel: '#7c3aed',
    resource: '#0d9488'
  };
  var LABEL = {
    course: '课程', concept: '概念', tool: '工具', framework: '框架', track: '纵深线',
    credential: '考牌', job: '岗位', employer: '雇主', channel: '渠道', resource: '资源'
  };
  var SIZE = { track: 46, course: 32, concept: 22, tool: 22, framework: 24, credential: 26, job: 24, employer: 24, channel: 22, resource: 22 };
  var KIND_SYMBOL = { skill: 'circle', tool: 'circle', mcp: 'rect', website: 'triangle', agent: 'diamond', model: 'diamond' };

  var CATS = ['course', 'concept', 'tool', 'framework', 'track', 'credential', 'job', 'employer', 'channel', 'resource'];
  var CAT_NAMES = ['课程', '概念', '工具', '框架', '纵深线', '考牌', '岗位', '雇主', '渠道', '资源'];
  function catIndex(t) { var i = CATS.indexOf(t); return i === -1 ? 2 : i; }

  function lang() { try { return (window.Wiki && Wiki.currentLang) ? Wiki.currentLang() : 'en'; } catch (e) { return 'en'; } }
  function pick(n, base) {
    var l = lang();
    var f = l === 'zh-hk' ? base + '_hk' : (l === 'en' ? base + '_en' : base);
    return n[f] || n[base] || '';
  }
  function typeLabel(t) { return (window.Wiki && Wiki.typeLabel) ? Wiki.typeLabel(t) : (LABEL[t] || t); }
  function entryHref(slug) { return (window.Wiki && Wiki.entryHref) ? Wiki.entryHref(slug) : ('wiki.html?slug=' + encodeURIComponent(slug)); }
  function escapeHtml(s) { return (window.Wiki && Wiki.escapeHtml) ? Wiki.escapeHtml(s) : String(s == null ? '' : s); }

  function nodeTitle(graph, slug) {
    var i = graph.__idx || (graph.__idx = (function () {
      var m = {}; graph.nodes.forEach(function (n) { m[n.id] = n; }); return m;
    })());
    return i[slug] ? pick(i[slug], 'title') : slug;
  }

  /* 选取要展示的节点：先按类型过滤，再按度数取 top-N（limit=0 表示全部） */
  function selectNodes(graph, opts) {
    opts = opts || {};
    var types = opts.types;
    var nodes = graph.nodes.filter(function (n) {
      return !types || !types.length || types.indexOf(n.type) !== -1;
    });
    if (opts.limit && nodes.length > opts.limit) {
      nodes = nodes.slice().sort(function (a, b) { return (b.degree || 0) - (a.degree || 0); }).slice(0, opts.limit);
    }
    return nodes;
  }

  function buildSeries(graph, opts) {
    var nodes = selectNodes(graph, opts);
    var keep = {};
    nodes.forEach(function (n) { keep[n.id] = 1; });
    var links = graph.links.filter(function (l) { return keep[l.source] && keep[l.target]; });
    var data = nodes.map(function (n) {
      return {
        id: n.id,
        name: pick(n, 'title'),
        category: catIndex(n.type),
        symbolSize: SIZE[n.type] || 20,
        symbol: KIND_SYMBOL[n.kind] || 'circle',
        itemStyle: { color: COLORS[n.type] }
      };
    });
    return { nodes: data, links: links, total: graph.nodes.length, shown: nodes.length };
  }

  function renderData(graph, container, opts) {
    opts = opts || {};
    if (!graph || !graph.nodes) throw new Error('graph 数据为空');
    var series = buildSeries(graph, opts);
    if (container.__chart) { try { container.__chart.dispose(); } catch (e) {} container.__chart = null; }

    if (!window.echarts) { renderFallback(graph, container, opts); return series; }

    var chart = window.echarts.init(container);
    chart.setOption({
      backgroundColor: '#ffffff',
      tooltip: {
        formatter: function (p) {
          if (p.dataType === 'edge') return escapeHtml(p.data.source) + ' ↔ ' + escapeHtml(p.data.target);
          var n = (graph.__idx || {})[p.data.id];
          if (!n) return escapeHtml(p.data.id);
          return '<b>' + escapeHtml(pick(n, 'title')) + '</b>' +
            (n.en ? '<br><i style="color:#8a94a6">' + escapeHtml(n.en) + '</i>' : '') +
            '<br><span style="color:#0e7490;font-weight:700">' + typeLabel(n.type) + '</span>' +
            (pick(n, 'summary') ? '<br>' + escapeHtml(pick(n, 'summary')).slice(0, 120) : '');
        }
      },
      legend: [{
        data: CAT_NAMES.map(function (n) { return { name: n, icon: 'circle' }; }),
        top: 8, left: 'center', textStyle: { color: '#1c2733' }
      }],
      series: [{
        type: 'graph',
        layout: 'force',
        data: series.nodes,
        links: series.links,
        categories: CAT_NAMES.map(function (n, i) { return { name: n, itemStyle: { color: COLORS[CATS[i]] } }; }),
        roam: true,
        draggable: true,
        label: { show: true, position: 'right', fontSize: 11, color: '#1c2733' },
        force: { repulsion: 140, edgeLength: [35, 95], gravity: 0.06, layoutAnimation: true },
        lineStyle: { color: '#c0c9d6', width: 1, curveness: 0.12, opacity: 0.7 },
        emphasis: { focus: 'adjacency', lineStyle: { width: 3, opacity: 1 } }
      }]
    });
    chart.on('click', function (p) {
      if (p.dataType === 'node' && p.data && p.data.id) window.location.href = entryHref(p.data.id);
    });
    window.addEventListener('resize', function () { chart.resize(); });
    container.__chart = chart;
    return series;
  }

  /* 降级列表（无 ECharts 时） */
  function renderFallback(graph, container, opts) {
    container.classList.add('graph-fallback');
    container.style.display = 'block';
    var nodes = selectNodes(graph, opts);
    var byType = {};
    nodes.forEach(function (n) { (byType[n.type] = byType[n.type] || []).push(n); });
    var linkMap = {};
    graph.links.forEach(function (l) {
      (linkMap[l.source] = linkMap[l.source] || []).push(l.target);
      (linkMap[l.target] = linkMap[l.target] || []).push(l.source);
    });
    var html = '<h2>图谱降级视图（未加载 ECharts，显示词条连接表）</h2>';
    CATS.forEach(function (t) {
      var list = byType[t] || [];
      if (!list.length) return;
      html += '<h3>' + typeLabel(t) + '</h3><ul>';
      list.forEach(function (n) {
        var outs = (linkMap[n.id] || []).slice(0, 8);
        html += '<li><a href="' + entryHref(n.id) + '">' + escapeHtml(pick(n, 'title')) + '</a>' +
          (outs.length ? ' → ' + outs.map(function (s) {
            return '<a href="' + entryHref(s) + '">' + escapeHtml(nodeTitle(graph, s)) + '</a>';
          }).join('、') : '') + '</li>';
      });
      html += '</ul>';
    });
    container.innerHTML = html;
  }

  window.Graph = { renderData: renderData, selectNodes: selectNodes, CATS: CATS, CAT_NAMES: CAT_NAMES };
})();
