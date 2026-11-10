# 오늘의 한입 (@hanip.byte) 설정 안내

처음 한 번만 하면 됩니다. ①~④는 인스타·Meta 화면에서 직접 해야 합니다.

## ① 크리에이터 계정으로 전환
1. 인스타 앱 → 프로필 → ≡ → 설정 → **계정 유형 및 도구** → **프로페셔널 계정으로 전환**
2. **크리에이터** 선택 → 카테고리는 "교육" 등 아무거나
3. 무료이며 언제든 개인 계정으로 되돌릴 수 있습니다. 비공개 계정으로는 둘 수 없습니다.

## ② 아이디 변경
- 프로필 편집 → 사용자 이름 → `hanip.byte`
- 이미 쓰이고 있으면 `hanip.byte.kr`로 하고, `.env`의 `ACCOUNT_HANDLE=@hanip.byte.kr`로 맞춥니다.

## ③ Meta 개발자 앱 만들기
1. https://developers.facebook.com → 로그인 → **내 앱 → 앱 만들기**
2. 사용 사례: **Instagram에서 메시지 및 콘텐츠 관리** (Instagram API, Instagram 로그인 방식)
3. 앱 대시보드 → **Instagram → API 설정(Instagram 로그인)**
4. **역할 → Instagram 테스터**에 위 계정을 추가하고, 인스타 앱(설정 → 웹사이트 권한 → 앱 및 웹사이트)에서 초대를 수락
5. 권한: `instagram_business_basic`, `instagram_business_content_publish`

## ④ 토큰과 사용자 ID 받기
1. API 설정 화면의 **액세스 토큰 생성**에서 계정을 연결하면 장기 토큰(60일)이 나옵니다.
2. 같은 화면에 표시되는 Instagram 사용자 ID(숫자)를 확인합니다.
3. 토큰은 50일마다 프로그램이 자동으로 갱신합니다(`var/token.json`).

## ⑤ `.env` 작성
```bash
cp .env.example .env
```
`.env`에 `IG_USER_ID`, `IG_ACCESS_TOKEN`을 채웁니다. **.env는 절대 커밋하지 않습니다** (저장소가 공개).

## ⑥ 이미지 공개용 GitHub 저장소
1. soyoung-yu 계정에 `insta-auto` **공개** 저장소를 만듭니다.
2. 이 폴더에서:
   ```bash
   git remote set-url origin https://github.com/soyoung-yu/insta-auto.git
   git push -u origin main
   ```
3. `.env`의 `IMAGE_BASE_URL=https://raw.githubusercontent.com/soyoung-yu/insta-auto/main`
4. 게시할 때마다 `posts/NNNN/`가 자동으로 커밋·push 됩니다. **main 브랜치에 있는 상태로 두세요.**

## ⑦ 커리큘럼 만들기
```bash
uv run python -m hanip curriculum
```
`data/curriculum.json`을 열어 순서나 주제를 자유롭게 고친 뒤 커밋합니다.

## ⑧ 예약 실행 등록 (평일 오전 9시)
```bash
scripts/install_launchd.sh
launchctl print gui/$(id -u)/com.hanip.daily | head -20
```
- 9시에 맥이 잠자기였다면 깨어날 때 한 번 실행됩니다. 전원이 꺼져 있으면 그날은 건너뜁니다.
- 해제: `launchctl bootout gui/$(id -u)/com.hanip.daily`

## 매일 쓰는 명령
| 명령 | 하는 일 |
|---|---|
| `uv run python -m hanip status` | 다음 회차, 주제, 승인 대기 여부 |
| `uv run python -m hanip approve` | (1~5회차) 미리보기를 보고 게시 |
| `uv run python -m hanip preview` | 미리보기 다시 열기 |
| `uv run python -m hanip run` | 지금 바로 오늘 분량 실행 (평일만) |

로그: `logs/YYYY-MM-DD.log`, `logs/launchd.log`
