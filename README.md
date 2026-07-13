# 오레곤 에덴 장로교회 | Eden Presbyterian Church of Oregon

현대적이고 밝고 깔끔한 이중언어(한국어 + English) 교회 웹사이트. 빌드 과정이 없는 순수 HTML/CSS/JS 정적 사이트입니다.
A modern, bright, bilingual (Korean-primary + English) church website — plain HTML/CSS/JS, no build step.

## 구조 · Structure

```
eden-presbyterian-church/
├── index.html      # 스크롤형 메인 랜딩 (Hero · 소개 · 비전 · 예배 · 설교 · 선교 · 일정 · 사진 · 헌금 · 오시는길)
├── about.html      # 교회 소개 (환영 · 비전 · 사명 · 교역자 · 연혁 타임라인)
├── worship.html    # 예배 안내 (주일·주일학교·수요·금요·새벽 전체 시간표)
├── giving.html     # 온라인 헌금 (Zelle · 수표)
├── css/styles.css  # 디자인 시스템 (토큰 · 레이아웃 · 컴포넌트 · 반응형)
├── js/main.js      # 모바일 메뉴 · 스크롤 스파이 · reveal 애니메이션
└── assets/         # 이미지 (Google Photos 연결 예정)
```

## 주요 기능 · Highlights

- **이중언어** — 한국어를 기본으로, 영어 번역을 함께 표기.
- **스크롤형 랜딩** — 부드러운 스크롤 이동, 섹션별 등장 애니메이션, 활성 메뉴 표시.
- **모바일/데스크탑 최적화** — 반응형 레이아웃 + 모바일 햄버거 메뉴.
- **실시간 임베드** — YouTube 최신 설교, Google 캘린더, Google 지도가 실제로 연동되어 표시됩니다.
- **외부 링크** — YouTube 채널/생방송, Google 캘린더 구독, 교회 주소록(Breeze), Facebook.

## 로컬 실행 · Run locally

```bash
cd eden-presbyterian-church
python3 -m http.server 5510
# → http://localhost:5510
```

## 남은 작업 · To do (다음 반복에서)

1. **Google Photos 앨범 연결** — `index.html`의 `#photos` 섹션과 `id="photosLink"` 링크에 실제 공유 앨범 URL을 넣으면 됩니다. (앨범 접근을 함께 진행하면 실제 사진 썸네일로 교체 가능)
2. **실제 사진 교체** — Hero 배경, 소개/선교 섹션의 placeholder(`.photo-ph`)를 교회 사진으로 교체.
3. **캘린더/라이브 임베드 확인** — 캘린더는 `admin@oregoneden.com` 공개 캘린더, 설교는 주일 재생목록을 임베드했습니다. 필요 시 계정에 맞게 조정.
4. **내용 검토** — 교역자·연혁·예배 시간 등은 기존 oregoneden.com에서 옮겨온 내용이므로 최신 여부 확인 부탁드립니다.

## 색상 커스터마이징 · Theme

`css/styles.css` 상단 `:root` 토큰을 수정하면 전체 색상/폰트/간격이 바뀝니다.
```
--primary  에덴 그린 (브랜드 컬러)
--accent   골드 포인트
--bg/-text 배경/본문 색
```
