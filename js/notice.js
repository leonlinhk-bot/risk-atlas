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
  d.innerHTML =
    '<div class="vn-inner">' +
      '<b>🛡️ 访问提示 · 为什么会出现「未完成ICP备案」提醒？</b>' +
      '<p>本站托管于境外（香港，GitHub Pages），主要面向香港与境外用户，不面向内地运营，因此没有内地 ICP 备案属正常情况。大陆访问时，浏览器或运营商会在进入前弹出「该网站未完成ICP备案」提示页——那只是对境外网站的常规提醒，<b>点页面上的「继续访问」即可正常进入本站</b>，全程无需输入任何内容。</p>' +
      '<p class="vn-en">This site is hosted in Hong Kong and is not subject to mainland China ICP filing. When mainland browsers show a filing warning before the page loads, just click “继续访问 / Continue” — no input is needed. This is a public study wiki: no login, and we never ask for your phone number, password or verification code.</p>' +
      '<p>本站是公开学习百科：浏览无需登录、不收集个人信息。若你看到任何要求输入账号密码、手机验证码或付费的弹窗，<b>那不是本站所为，请直接关闭</b>。</p>' +
      '<button class="vn-close" type="button" aria-label="我知道了，关闭访问提示">✕</button>' +
    '</div>';

  document.body.insertBefore(d, document.body.firstChild);

  function fit() {
    try { document.body.style.paddingTop = d.offsetHeight + 'px'; } catch (e) {}
  }
  fit();
  window.addEventListener('resize', fit);

  var closeBtn = d.querySelector('.vn-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', function () {
      try { window.localStorage.setItem(KEY, '1'); } catch (e) {}
      document.body.style.paddingTop = '';
      if (d.parentNode) d.parentNode.removeChild(d);
      window.removeEventListener('resize', fit);
    });
  }
})();
