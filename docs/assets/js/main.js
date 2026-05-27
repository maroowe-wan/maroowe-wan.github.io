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
    // BBG 풍 테마는 devops-basics 강좌 페이지에만 적용(시험 적용). 그 외는 기존 팔레트 유지.
    var bbg = location.pathname.indexOf('/courses/devops-basics/') !== -1;
    if (bbg) document.documentElement.classList.add('bbg-diagrams');
    mermaid.initialize(bbg ? {
      startOnLoad: false, securityLevel: 'loose', theme: 'base',
      flowchart: { curve: 'basis', htmlLabels: true, padding: 16, nodeSpacing: 55, rankSpacing: 64, useMaxWidth: false },
      sequence: { useMaxWidth: false, actorMargin: 60 },
      themeVariables: {
        fontFamily: 'Hanken Grotesk, sans-serif', fontSize: '16px',
        primaryColor: '#dbeafe', primaryBorderColor: '#2563eb', primaryTextColor: '#13315c',
        lineColor: '#334155', secondaryColor: '#dcfce7', tertiaryColor: '#eef4fc',
        clusterBkg: '#eef4fc', clusterBorder: '#93b4d8', edgeLabelBackground: '#ffffff',
        noteBkgColor: '#fff8e1', noteBorderColor: '#f5c518'
      }
    } : {
      startOnLoad: false, securityLevel: 'loose', theme: 'base',
      flowchart: { useMaxWidth: false }, sequence: { useMaxWidth: false },
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
  // 렌더된 다이어그램을 그것이 놓일 영역의 폭에 맞춰 배치한다.
  // useMaxWidth:false 라 SVG는 원본 크기로 그려진다 → 읽기 칼럼에 들어가면 가운데 정렬,
  // 칼럼보다 넓으면 본문(main) 폭까지 그림 영역을 넓혀 키우고, 그래도 넘치면 원본 크기로 가로 스크롤.
  function fitDiagram(el) {
    var fig = el.closest('figure.diagram'); if (!fig) return;
    var svg = el.querySelector('svg'); if (!svg) return;
    fig.style.width = ''; fig.style.maxWidth = ''; el.style.justifyContent = ''; // 측정 전 초기화
    var natural = svg.getBoundingClientRect().width;
    var colW = fig.parentElement ? fig.parentElement.clientWidth : natural;      // 읽기 칼럼(.lecture, ~720)
    var mainEl = el.closest('main'), mainW = colW;                               // 본문 영역 = 브레이크아웃 한계
    if (mainEl) { var cs = getComputedStyle(mainEl); mainW = mainEl.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight); }
    if (natural <= colW + 1) return;             // 칼럼에 들어가면 가운데 정렬 그대로 둔다
    var target = Math.min(natural, mainW);       // 칼럼을 넘어서면 본문 폭까지 그림 영역을 넓힌다
    if (target > colW) { fig.style.width = target + 'px'; fig.style.maxWidth = 'none'; }
    if (natural > target + 1) el.style.justifyContent = 'flex-start'; // 본문 폭도 넘으면 가로 스크롤(원본 크기)
  }
  var rendered = [];
  function render(el) {
    return mermaid.run({ nodes: [el] })
      .then(function () { rendered.push(el); fitDiagram(el); })
      .catch(function (e) { console.warn('Mermaid 렌더 실패', e); });
  }
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
  // 창 폭이 바뀌면 가용 폭이 달라지므로 배치를 다시 계산(디바운스).
  var rt;
  window.addEventListener('resize', function () {
    clearTimeout(rt);
    rt = setTimeout(function () { rendered.forEach(fitDiagram); }, 150);
  });
})();

// 언어 토글 — 사용자가 고른 언어를 localStorage(eduLang)에 기억해 라우터(docs/index.html)가 재사용한다.
(function () {
  document.querySelectorAll('a.lang-toggle[data-lang]').forEach(function (a) {
    a.addEventListener('click', function () {
      try { localStorage.setItem('eduLang', a.getAttribute('data-lang')); } catch (e) {}
    });
  });
})();
