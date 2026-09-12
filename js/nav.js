/* nav.js — 全站导航单一来源（#11 导航单点化）
 * 各页只需保留 <nav class="nav" id="site-nav"></nav>，导航项与「当前页高亮」在此统一维护。
 * 说明：本脚本在页面底部、wiki.js 之前同步执行，因此 #lang-switch 容器在其后调用
 *      Wiki.attachLangSwitcher() 时已存在。 */
(function () {
  'use strict';

  var ITEMS = [
    ['index.html', '首页'],
    ['weekly.html', '周报'],
    ['catalog.html', '课程目录'],
    ['career.html', '就业情报'],
    ['companies.html', '机构全景'],
    ['map.html', '知识宇宙'],
    ['categories.html', '分类索引']
  ];

  function currentFile() {
    var p = location.pathname.split('/').pop();
    return p || 'index.html';
  }

  function render() {
    var el = document.getElementById('site-nav');
    if (!el) return;
    var cur = currentFile();
    var html = ITEMS.map(function (it) {
      var active = it[0] === cur ? ' class="active" aria-current="page"' : '';
      return '<a href="' + it[0] + '"' + active + '>' + it[1] + '</a>';
    }).join('');
    html += '<div class="lang-switch" id="lang-switch"></div>';
    el.innerHTML = html;
    el.setAttribute('aria-label', '主导航');
  }

  render();
})();
