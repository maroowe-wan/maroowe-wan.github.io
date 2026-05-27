# GitHub Pages 배포 가이드

생성된 교육 사이트(`docs/`)를 GitHub Pages로 공개하는 절차다.
빌드는 `scripts/build_html.py`가 `docs/` 아래에 통합 사이트를 만든다(아래 "빌드" 참고).
배포(git·Pages 설정)는 **사용자가 직접 1회 수행**한다.

## 사이트 구조
```
docs/                     ← GitHub Pages 소스 루트
  index.html              ← 강좌 목록 랜딩
  assets/                 ← 공통 자산 (한 곳에서 관리·고도화)
    css/style.css
    js/main.js
    img/
  courses/<슬러그>/index.html   ← 강좌별 페이지
```
모든 링크는 상대경로라 저장소 이름(프로젝트 사이트 base path)과 무관하게 동작한다.

## 빌드
```bash
# 강좌 전체 빌드 + 랜딩 갱신
python scripts/build_html.py --all

# 특정 강좌만 (자산 스캐폴드 + 랜딩 자동 갱신)
python scripts/build_html.py --course courses/<슬러그>

# 공통 css/js를 기본값으로 되돌리기 (손편집 폐기)
python scripts/build_html.py --all --reset-assets
```
> `style.css`·`main.js`는 **없을 때만** 생성된다. 직접 수정한 디자인은 재빌드해도 보존된다(`--reset-assets` 제외).

## 최초 배포 (1회)
1. **git 초기화 & 커밋**
   ```bash
   git init
   git add .
   git commit -m "교육 사이트 초기 배포"
   ```
2. **GitHub 원격 저장소 연결 & 푸시** (저장소는 미리 생성)
   ```bash
   git branch -M main
   git remote add origin https://github.com/<계정>/<저장소>.git
   git push -u origin main
   ```
3. **Pages 활성화**: GitHub 저장소 → **Settings → Pages**
   - **Source**: `Deploy from a branch`
   - **Branch**: `main` / 폴더 `/docs` 선택 → Save
4. 1~2분 후 `https://<계정>.github.io/<저장소>/` 에서 확인.

## 갱신 배포 (이후)
```bash
python scripts/build_html.py --all
git add docs
git commit -m "강좌 업데이트"
git push
```
푸시하면 Pages가 자동 재배포한다.

## 참고
- `docs/.nojekyll` 가 있어 GitHub이 Jekyll 처리를 건너뛴다(언더스코어 파일·폴더 무시 방지).
- 다이어그램(Mermaid)·폰트는 CDN을 쓴다. 사내망에서 CDN이 막히면 다이어그램은 소스 텍스트로 폴백 표시된다.
