// Dynamic LabSystems loading screen. Leaves once the page has loaded AND the
// logo animation has had time to finish, then is skipped for the rest of
// this browser session. Later page changes show a thin red bar instead.
(function () {
  var MIN_MS = 2300;
  var start = Date.now();
  var splash = document.getElementById('dl-splash');

  function remember() { try { sessionStorage.setItem('dl-splash-seen', '1'); } catch (e) {} }

  function leave() {
    if (!splash || splash.classList.contains('is-leaving')) return;
    var wait = Math.max(0, MIN_MS - (Date.now() - start));
    setTimeout(function () {
      splash.classList.add('is-leaving');
      remember();
      setTimeout(function () { if (splash.parentNode) splash.parentNode.removeChild(splash); }, 600);
    }, wait);
  }

  if (splash && !document.documentElement.classList.contains('dl-splash-seen')) {
    if (document.readyState === 'complete') leave(); else window.addEventListener('load', leave);
  }

  // Page-change progress bar.
  var bar = document.getElementById('dl-topbar');
  function go() { if (bar) { bar.classList.remove('is-active'); void bar.offsetWidth; bar.classList.add('is-active'); } }
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (a.target && a.target !== '_self') return;
    if (a.hasAttribute('download')) return;
    var url = new URL(a.href, location.href);
    if (url.origin !== location.origin) return;
    if (url.pathname === location.pathname && url.hash) return;
    if (/\.(pdf|csv|xlsx?)$/i.test(url.pathname) || /\/pdf\/?$/i.test(url.pathname)) return; // downloads don't navigate
    go();
  });
  // Block double submits (double tap, or keyboard "Go" + button tap on a
  // phone): the second copy arrives after the first has already changed
  // things (e.g. signed in) and gets rejected.
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (e.defaultPrevented) return;
    if (form.dataset.submitting === '1') { e.preventDefault(); return; }
    form.dataset.submitting = '1';
    setTimeout(function () { delete form.dataset.submitting; }, 8000);
    go();
  });
  window.addEventListener('pageshow', function () {
    if (bar) bar.classList.remove('is-active');
    document.querySelectorAll('form[data-submitting]').forEach(function (f) { delete f.dataset.submitting; });
  });
})();
