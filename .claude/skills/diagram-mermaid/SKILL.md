---
name: diagram-mermaid
description: 강의 본문에 Mermaid 다이어그램을 작성·삽입하고 HTML에서 안전하게 렌더링되게 하는 방법. diagram-architect 에이전트가 참조.
---

# Mermaid 다이어그램 작성 스킬

강의 본문에 텍스트 기반 다이어그램을 넣으면 `scripts/build_html.py`가 HTML로 렌더링한다.
브라우저에서 **Mermaid.js 11.15.0(CDN)**가 그림을 그리며, 오프라인이면 소스 텍스트가 그대로 노출되는 폴백이 동작한다.

## 어디에·어느 언어로 쓰나
- 영어가 원본(canonical)이므로 다이어그램은 **`content.en.md`** 에 **영어 캡션·라벨**로 넣는다(diagram-architect, 4b단계).
- 한국어 페이지의 다이어그램은 6b에서 content-localizer가 **캡션·라벨만 한국어로** 옮긴다(노드 ID·문법·화살표는 그대로). 따라서 라벨은 따옴표로 감싸 한/영 치환이 안전하도록 쓴다.

## 삽입 형식
content.md 본문에 펜스 블록으로 넣는다. ` ```mermaid ` 뒤 텍스트는 **그림 설명(figcaption)**.

````markdown
```mermaid 시스템 구성도
flowchart LR
    C[클라이언트] --> A[API 서버]
    A --> D[(데이터베이스)]
```
````

## 핵심 원칙 — 다이어그램은 이해를 높일 때만
다이어그램의 유일한 존재 이유는 **글보다 더 잘 이해시키는 것**이다. 따라서:
- 본문·사실과 어긋나거나, 단순화 과정에서 **오해를 유발할 소지가 있는 다이어그램은 먼저 고친다**(라벨·화살표·구조를 사실에 맞게 정정).
- **고쳐도 여전히 혼동을 준다면 그 다이어그램은 삭제한다.** 틀리거나 헷갈리는 그림은 없는 것만 못하다.
- 텍스트로 충분히 명확한 곳에는 애초에 넣지 않는다(억지 그림 금지).
- 삭제 시 본문 안의 "아래 그림처럼…" 같은 연결 문장도 함께 정리한다. 영문(content.en.md)에서도 동일 블록을 삭제한다.

## 다이어그램 유형 선택 가이드
| 전달할 내용 | 유형 | 키워드 |
|---|---|---|
| 컴포넌트 구성·아키텍처 | 구성도 | `flowchart LR` / `graph TD` |
| 조건 분기·절차·알고리즘 | 순서도 | `flowchart TD` |
| 시간순 상호작용(요청/응답) | 시퀀스 | `sequenceDiagram` |
| 행위자-기능 관계 | 유즈케이스 | `flowchart`(액터-유즈케이스) |
| 상태 전이 | 상태도 | `stateDiagram-v2` |
| 클래스·구조·관계 | 클래스/ER | `classDiagram` / `erDiagram` |

## 유형별 최소 예시

### 구성도 / 순서도 (flowchart)
```
flowchart TD
    A[시작] --> B{조건?}
    B -->|예| C[처리 1]
    B -->|아니오| D[처리 2]
    C --> E[종료]
    D --> E
```
- 방향: `TD`(위→아래), `LR`(좌→우). 노드: `[사각]`, `(둥근)`, `{마름모=판단}`, `[(원통=DB)]`.
- 라벨 있는 화살표: `-->|텍스트|`.

### 시퀀스 (sequenceDiagram)
```
sequenceDiagram
    participant U as 사용자
    participant S as 서버
    U->>S: 요청
    S-->>U: 응답
```
- `->>` 실선 호출, `-->>` 점선 응답. `participant X as 한글이름`.

### 유즈케이스 (flowchart로 표현)
```
flowchart LR
    actor((사용자))
    actor --> UC1([로그인])
    actor --> UC2([상품 검색])
    UC2 --> UC3([장바구니 담기])
```
- 액터는 `((원))`, 유즈케이스는 `([스타디움])` 형태로 관용 표현.

### 상태도 / 클래스
```
stateDiagram-v2
    [*] --> 대기
    대기 --> 처리중: 요청수신
    처리중 --> 완료: 성공
    완료 --> [*]
```
```
classDiagram
    class 주문 {
      +주문번호
      +결제()
    }
    주문 --> 상품
```

## ByteByteGo 스타일 (시스템 디자인 다이어그램)
아키텍처·요청 흐름을 그릴 때는 ByteByteGo 풍으로 그리면 한눈에 읽힌다. 구성 요소는 **① 티어별 그룹(subgraph) → ② 컴포넌트별 색(classDef) → ③ 번호 매긴 흐름(엣지 라벨) → ④ 약식 아이콘(이모지)** 네 가지다. 일러스트·그라데이션·로고는 Mermaid로 못 내므로 흉내내지 않는다(억지 금지).

### 표준 팔레트 (classDef) — 그대로 복사해 쓴다
컴포넌트 종류마다 색을 일관되게 준다. 라이트 배경에 맞춘 파스텔 톤이다.
```
classDef client fill:#dbeafe,stroke:#1e40af,color:#1e3a8a;
classDef edge   fill:#fef3c7,stroke:#b45309,color:#78350f;
classDef svc    fill:#dcfce7,stroke:#15803d,color:#14532d;
classDef cache  fill:#fae8ff,stroke:#a21caf,color:#701a75;
classDef db     fill:#e0e7ff,stroke:#4338ca,color:#312e81;
classDef queue  fill:#ffe4e6,stroke:#be123c,color:#881337;
```
- 노드에 `:::client` 처럼 클래스를 붙인다. 같은 종류는 같은 색으로.
- `edge`=로드밸런서/게이트웨이, `svc`=서비스/앱, `cache`=캐시, `db`=DB, `queue`=메시지큐.

### 완성 예시 (캐시 우선 조회)
```
flowchart LR
    U(["👤 Client"]):::client
    subgraph APP["Application Tier"]
        LB["⚖️ Load Balancer"]:::edge
        S1["⚙️ Service"]:::svc
    end
    subgraph DATA["Data Tier"]
        C[("⚡ Cache")]:::cache
        DB[("🗄️ Database")]:::db
    end
    U -->|1 request| LB -->|2| S1
    S1 -->|3 read| C
    C -.->|4 miss| DB -->|5 fill| C
    S1 -->|6 response| U
    classDef client fill:#dbeafe,stroke:#1e40af,color:#1e3a8a;
    classDef edge fill:#fef3c7,stroke:#b45309,color:#78350f;
    classDef svc fill:#dcfce7,stroke:#15803d,color:#14532d;
    classDef cache fill:#fae8ff,stroke:#a21caf,color:#701a75;
    classDef db fill:#e0e7ff,stroke:#4338ca,color:#312e81;
```
규칙:
- **흐름엔 번호를 단다**: `-->|1 request|`, `-->|2|` … 요청이 도는 순서를 숫자로. ByteByteGo의 ①②③ 흐름을 대체한다.
- **티어는 subgraph로 묶는다**: `subgraph APP["Application Tier"]`. 같은 계층 컴포넌트를 한 상자에.
- **아이콘은 이모지로**: 👤 client, ⚙️ service, ⚡ cache, 🗄️ database, 📨 queue, ☁️ cloud, 🌐 gateway. 폰트 의존이 없어 오프라인에서도 깨지지 않는다.
- `classDef`는 블록 **맨 끝**에 모아 둔다(가독성). 라벨은 모두 `"..."`로 감싸 한/영 치환을 안전하게.

### 시퀀스 다이어그램의 ByteByteGo 느낌
`classDef` 색은 시퀀스 참가자에 적용되지 않는다. 대신:
- **`autonumber`** 를 첫 줄(다이어그램 선언 다음)에 넣으면 메시지마다 1·2·3… 번호가 자동으로 붙어 ByteByteGo의 번호 흐름이 된다.
- 참가자 이름에 이모지를 붙인다: `participant P as 👤 Producer`, `participant L as ⭐ Leader Broker`.
- ⚠ **`box`(참가자 티어 그룹핑)는 쓰지 않는다.** 우리 검증 파이프라인(Mermaid 11 `mermaid.parse`)에서 "Option is not defined"로 파싱 실패하므로, 그림 대신 에러가 노출될 위험이 있다. 그룹핑이 필요하면 시퀀스 대신 flowchart의 subgraph로 표현한다.

### 클라우드 아키텍처가 필요하면 — architecture-beta (Mermaid 11)
실제 클라우드 컴포넌트 아이콘(서버/디스크/클라우드 등)이 필요하면 11부터 지원하는 `architecture-beta`를 쓸 수 있다. 단 아이콘 팩(iconify) 로드가 필요하고 오프라인에서 아이콘이 빠질 수 있으니, 기본은 위 flowchart+이모지 방식을 우선한다.

## 렌더링 안전 규칙 (어기면 그림 대신 소스가 노출됨)
1. **한 블록 = 한 다이어그램 종류.** 섞지 않는다.
2. 첫 줄에 반드시 유형 선언(`flowchart`/`sequenceDiagram` 등)이 와야 한다. 캡션은 펜스줄에만.
3. 라벨에 `()`, `:`, `;`, `"`, `#`, `<`, `>` 등 파서 충돌 문자가 있으면 **`"..."`로 감싼다**: `A["가격(원)"]`.
4. 노드 식별자(id)는 영문/숫자, 화면에 보일 이름은 라벨/`as`로 한글 사용.
5. 들여쓰기는 공백으로, 줄 끝에 불필요한 기호를 남기지 않는다.
6. 화살표 문법은 유형마다 다르다(flowchart `-->`, sequence `->>`). 섞어 쓰지 않는다.

## 빌드·검증
빌드: `python scripts/build_html.py --course courses/<슬러그>` (별도 추가 명령 없음).
HTML 검증:
- `grep -c "class='mermaid'"` 로 다이어그램 개수 확인.
- 브라우저에서 index.html을 열어 **각 다이어그램이 그림으로 렌더링되는지** 확인. 코드 텍스트가 그대로 보이면 (1) 인터넷 차단이거나 (2) Mermaid 문법 오류다 → 콘솔 에러를 보고 문법을 고친다.
- 라이트 테마(`theme:'base'` + M3 팔레트)로 렌더링된다. 색을 지정하지 않으면 파랑 계열 기본색이 적용되고, 아래 **ByteByteGo 스타일**처럼 `classDef`로 컴포넌트별 색을 직접 줄 수도 있다.
