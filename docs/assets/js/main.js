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

// Mermaid 다이어그램 — CDN 동적 import. 라이트 테마(Academic Clarity). 실패 시 .mermaid 폴백 CSS.
(async function () {
  if (!document.querySelector('.mermaid')) return;
  try {
    const { default: mermaid } = await import('https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs');
    mermaid.initialize({
      startOnLoad: true, securityLevel: 'loose', theme: 'base',
      themeVariables: {
        fontFamily: 'Hanken Grotesk, sans-serif',
        primaryColor: '#d9e2ff', primaryBorderColor: '#003178', primaryTextColor: '#1a1c1e',
        lineColor: '#434652', secondaryColor: '#81f3e5', tertiaryColor: '#f3f3f6'
      }
    });
  } catch (e) {
    console.warn('Mermaid 로드 실패 — 다이어그램 소스를 텍스트로 표시합니다.', e);
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
