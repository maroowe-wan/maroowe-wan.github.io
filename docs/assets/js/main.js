// 퀴즈 정답 처리 — 인라인 onclick 에서 호출되므로 전역 함수로 둔다.
function pick(el, qi, oi) {
  var quiz = el.closest('.quiz');
  if (quiz.classList.contains('answered')) return;
  var ans = parseInt(quiz.dataset.ans);
  quiz.querySelectorAll('.opt').forEach(function (o, j) {
    if (j === ans) o.classList.add('correct');
    else if (j === oi) o.classList.add('wrong');
  });
  quiz.classList.add('answered');
}

// 사이드바 활성 강의 하이라이트 (디자인 가이드: 좌측 4px Teal 바). 랜딩엔 사이드바가 없어 무시됨.
(function () {
  var links = Array.prototype.slice.call(document.querySelectorAll('nav a[href^="#lec"]'));
  var articles = document.querySelectorAll('article.lecture[id]');
  if (!links.length || !articles.length || !('IntersectionObserver' in window)) return;
  var byId = {};
  links.forEach(function (a) { byId[a.getAttribute('href').slice(1)] = a; });
  var obs = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      links.forEach(function (a) { a.classList.remove('active'); });
      var active = byId[e.target.id];
      if (active) active.classList.add('active');
    });
  }, { rootMargin: '-20% 0px -70% 0px' });
  articles.forEach(function (a) { obs.observe(a); });
})();

// Mermaid 다이어그램 — CDN 동적 import 후 mermaid.run()으로 명시 렌더.
// startOnLoad는 import가 window load 이벤트보다 늦게 끝나면(모바일=느린 망/CPU) 렌더를 놓쳐
// 소스 텍스트가 그대로 노출되므로 쓰지 않는다. 대신 명시적으로 그려 결정적으로 렌더한다.
(async function () {
  var blocks = document.querySelectorAll('.mermaid');
  if (!blocks.length) return;
  var mermaid;
  try {
    mermaid = (await import('https://cdn.jsdelivr.net/npm/mermaid@11.15.0/dist/mermaid.esm.min.mjs')).default;
    mermaid.initialize({
      startOnLoad: false, securityLevel: 'loose', theme: 'base',
      themeVariables: {
        fontFamily: 'Hanken Grotesk, sans-serif',
        primaryColor: '#d9e2ff', primaryBorderColor: '#003178', primaryTextColor: '#1a1c1e',
        lineColor: '#434652', secondaryColor: '#81f3e5', tertiaryColor: '#f3f3f6'
      }
    });
  } catch (e) {
    console.warn('Mermaid 로드 실패 — 다이어그램 소스를 텍스트로 표시합니다.', e);
    return; // 폴백 CSS(.mermaid:not([data-processed='true']))가 소스를 텍스트로 표시
  }
  function render(el) { mermaid.run({ nodes: [el] }).catch(function (e) { console.warn('Mermaid 렌더 실패', e); }); }
  // 화면에 가까워진 다이어그램만 렌더(성능). 옵저버 미지원이면 즉시 전부 렌더.
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        io.unobserve(en.target);
        render(en.target);
      });
    }, { rootMargin: '200px 0px' });
    blocks.forEach(function (el) { io.observe(el); });
  } else {
    blocks.forEach(render);
  }
})();

// 언어 토글 — 사용자가 고른 언어를 localStorage(eduLang)에 기억해 라우터(docs/index.html)가 재사용한다.
(function () {
  document.querySelectorAll('a.lang-toggle[data-lang]').forEach(function (a) {
    a.addEventListener('click', function () {
      try { localStorage.setItem('eduLang', a.getAttribute('data-lang')); } catch (e) {}
    });
  });
})();
