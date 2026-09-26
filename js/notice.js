/* notice.js — 「访问提示」：向经大陆拦截页点「继续访问」进入的用户说明情况 */
(function () {
  'use strict';

  var KEY = 'riskatlas.visitnote';

  // 已关闭过 → 不再打扰（同一浏览器）
  try { if (window.localStorage.getItem(KEY) === '1') return; } catch (e) {}

  var d = document.createElement('div');
  d.className = 'visit-note';
  d.setAttribute('role', 'note');
  d.setAttribute('aria-label', '访问提示');
  // 默认折叠为 2 行 + 「详情」展开：桌面首访不再占 158px、窄屏不再占 356px（实测值）
  d.innerHTML =
    '<div class="vn-inner">' +
      '<div class="vn-top">' +
        '<b>🛡️ 访问提示 · 为什么提示「未完成 ICP 备案」？</b>' +
        '<span class="vn-ctrl">' +
          '<button class="vn-more" type="button" aria-expanded="false" aria-controls="vn-body">详情 ▾</button>' +
          '<button class="vn-close" type="button" aria-label="我知道了，关闭访问提示">✕</button>' +
        '</span>' +
      '</div>' +
      '<div class="vn-body" id="vn-body">' +
        '<p>本站托管于境外（香港，GitHub Pages），主要面向香港与境外用户，不面向内地运营，因此没有内地 ICP 备案属正常情况。大陆访问时，浏览器或运营商会在进入前弹出「该网站未完成ICP备案」提示页——那只是对境外网站的常规提醒，<b>点页面上的「继续访问」即可正常进入本站</b>，全程无需输入任何内容。</p>' +
        '<p class="vn-en">This site is hosted in Hong Kong and is not subject to mainland China ICP filing. When mainland browsers show a filing warning before the page loads, just click “继续访问 / Continue” — no input is needed. This is a public study wiki: no login, and we never ask for your phone number, password or verification code.</p>' +
        '<p>本站是公开学习百科：浏览无需登录、不收集个人信息。若你看到任何要求输入账号密码、手机验证码或付费的弹窗，<b>那不是本站所为，请直接关闭</b>。</p>' +
      '</div>' +
    '</div>';

  document.body.insertBefore(d, document.body.firstChild);

  function fit() {
    var h = 0;
    try { h = d.offsetHeight; } catch (e) {}
    try { document.body.style.paddingTop = h + 'px'; } catch (e) {}
    // 供吸顶元素（就业页 .career-toc、词条页 .wk-side）取用：让它们贴在提示条下方而非被盖住
    try { document.documentElement.style.setProperty('--stick-top', h + 'px'); } catch (e) {}
  }
  fit();
  window.addEventListener('resize', fit);

  var moreBtn = d.querySelector('.vn-more');
  if (moreBtn) {
    moreBtn.addEventListener('click', function () {
      var open = d.classList.toggle('open');
      moreBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      moreBtn.textContent = open ? '收起 ▴' : '详情 ▾';
      fit();
    });
  }

  var closeBtn = d.querySelector('.vn-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', function () {
      try { window.localStorage.setItem(KEY, '1'); } catch (e) {}
      document.body.style.paddingTop = '';
      document.documentElement.style.setProperty('--stick-top', '0px');
      if (d.parentNode) d.parentNode.removeChild(d);
      window.removeEventListener('resize', fit);
    });
  }
})();
