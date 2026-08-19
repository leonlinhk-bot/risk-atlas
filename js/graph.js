/* graph.js — 知识图谱（ECharts 力导向图 + 无 ECharts 时的降级列表） */
(function () {
  'use strict';

  var COLORS = {
    course: '#14356a',
    concept: '#c9a227',
    tool: '#2e8b57',
    framework: '#8e44ad',
    track: '#d9534f',
    credential: '#0e7490'
  };
  var SIZE = { track: 46, course: 32, concept: 22, tool: 22, framework: 24, credential: 26 };

  function buildGraph(entries, idx) {
    var nodes = entries.map(function (e) {
      var node = {
        id: e.slug,
        name: Wiki.tr(e, 'title'),
        category: catIndex(e.type),
        symbolSize: SIZE[e.type] || 20,
        itemStyle: { color: COLORS[e.type] }
      };
      if (e.status === 'catalog') {
        node.itemStyle.opacity = 0.45;
        node.itemStyle.borderColor = '#9aa4b2';
        node.itemStyle.borderWidth = 1;
        node.itemStyle.borderType = 'dashed';
      }
      return node;
    });

    var seen = {};
    var links = [];
    entries.forEach(function (e) {
      Wiki.outgoingSlugs(e).forEach(function (s) {
        if (!idx[s]) return;
        var key = e.slug < s ? e.slug + '|' + s : s + '|' + e.slug;
        if (seen[key]) return;
        seen[key] = true;
        links.push({ source: e.slug, target: s });
      });
    });
    return { nodes: nodes, links: links };
  }

  var CATS = ['course', 'concept', 'tool', 'framework', 'track', 'credential'];
  var CAT_NAMES = ['课程', '概念', '工具', '框架', '纵深线', '考牌'];
  function catIndex(t) { var i = CATS.indexOf(t); return i === -1 ? 0 : i; }

  function render(entries, container) {
    var idx = Wiki.index(entries);
    var g = buildGraph(entries, idx);

    if (window.echarts) {
      var chart = window.echarts.init(container);
      var option = {
        backgroundColor: '#ffffff',
        tooltip: {
          formatter: function (p) {
            if (p.dataType === 'edge') return p.data.source + ' ↔ ' + p.data.target;
            var e = idx[p.data.id];
            return e ? '<b>' + e.title + '</b><br>' + (e.summary || '') : p.data.id;
          }
        },
        legend: [{
          data: CAT_NAMES.map(function (n, i) { return { name: n, icon: 'circle' }; }),
          top: 8, left: 'center', textStyle: { color: '#1c2733' }
        }],
        series: [{
          type: 'graph',
          layout: 'force',
          data: g.nodes,
          links: g.links,
          categories: CAT_NAMES.map(function (n, i) {
            return { name: n, itemStyle: { color: COLORS[CATS[i]] } };
          }),
          roam: true,
          draggable: true,
          label: { show: true, position: 'right', fontSize: 11, color: '#1c2733' },
          force: {
            repulsion: 140,
            edgeLength: [35, 95],
            gravity: 0.06,
            layoutAnimation: true
          },
          lineStyle: { color: '#c0c9d6', width: 1, curveness: 0.12, opacity: 0.7 },
          emphasis: {
            focus: 'adjacency',
            lineStyle: { width: 3, opacity: 1 }
          }
        }]
      };
      chart.setOption(option);
      chart.on('click', function (p) {
        if (p.dataType === 'node' && p.data && p.data.id) {
          window.location.href = 'wiki.html?slug=' + encodeURIComponent(p.data.id);
        }
      });
      window.addEventListener('resize', function () { chart.resize(); });
    } else {
      renderFallback(g, idx, container);
    }
  }

  function renderFallback(g, idx, container) {
    container.classList.add('graph-fallback');
    container.style.display = 'block';
    var byType = {};
    g.nodes.forEach(function (n) {
      var e = idx[n.id];
      (byType[e.type] = byType[e.type] || []).push(e);
    });
    var html = '<h2>图谱降级视图（未加载 ECharts，显示词条连接表）</h2>';
    CATS.forEach(function (t) {
      var list = byType[t] || [];
      if (!list.length) return;
      html += '<h3>' + Wiki.typeLabel(t) + '</h3><ul>';
      list.forEach(function (e) {
        var outs = Wiki.outgoingSlugs(e).filter(function (s) { return idx[s]; });
        html += '<li><a href="' + Wiki.entryHref(e.slug) + '">' + Wiki.escapeHtml(e.title) + '</a>' +
          (outs.length ? ' → ' + outs.map(function (s) {
            return '<a href="' + Wiki.entryHref(s) + '">' + Wiki.escapeHtml(idx[s].title) + '</a>';
          }).join('、') : '') + '</li>';
      });
      html += '</ul>';
    });
    container.innerHTML = html;
  }

  window.Graph = { render: render };
})();
