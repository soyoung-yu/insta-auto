# 오늘의 한입 (@hanip.byte) 자동 게시 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 평일 오전 9시, 맥에서 컴퓨터공학 용어 하나를 9장 영수증 콘셉트 캐러셀로 만들어 인스타에 게시한다. 처음 5회는 사람 승인 후 게시한다.

**Architecture:** Python 패키지 `hanip` 하나. launchd가 `python -m hanip run`을 실행하면 커리큘럼에서 주제를 고르고, GeekNews·Hacker News에서 소식을 모으고, `claude -p`로 9장 문구(JSON)를 받아 Jinja2 HTML을 Playwright로 JPEG 9장으로 찍는다. 이미지는 이 저장소의 `posts/`에 push해 raw.githubusercontent.com 주소로 공개하고, Instagram API(Instagram 로그인 방식)로 캐러셀을 게시한다.

**Tech Stack:** Python 3.12, uv, pydantic 2, Jinja2, Playwright(Chromium), requests, feedparser, python-dotenv, pytest, responses

**Spec:** `docs/superpowers/specs/2026-11-10-insta-auto-design.md` (시각 기준: `docs/superpowers/specs/2026-11-10-insta-auto-mockups/`)

## Global Constraints

- 이미지: 1080×1350, **JPEG만**, 9장 고정
- 게시: 평일(월~금) 09:00, 주말 없음, 하루 최대 1회, 놓친 날 몰아서 올리지 않음
- 반자동: 게시 회차 1~5는 승인 후 게시, 6부터 자동. 승인은 생성한 그날만 유효, 넘기면 다음 실행에서 같은 주제를 다시 생성
- 테마: 게시 회차 홀수 = light, 짝수 = dark
- 시리즈 태그 `No.{회차:02d}` (예: No.01, No.112), 계정 표기 `@hanip.byte`
- 9장 문구: `오늘의 한입 소화 완료 ♥` / `필요할 때 다시 먹으러 와`
- 색, 캐릭터 치수는 스펙 6장 값을 그대로 쓴다 (예: light 배경 `#fff7fa`, dark 배경 `#16121e`, 도트 1px/16px 간격, 9장 서류 회전 14°)
- 문구 생성은 `claude -p` (Claude Code 구독). API 키를 쓰지 않는다
- 저장소가 공개이므로 토큰·비밀값은 git 제외 경로(`.env`, `var/`)에만 둔다. `resource/`는 커밋하지 않는다
- 글꼴: Pretendard(한글 고딕), D2Coding(영수증 고정폭), 둘 다 OFL, 라이선스 파일 동봉
- 말투: 반말, 항목 10~15자 안팎, 한 장에 핵심 1문장 + 항목 3~4개 + 한입 요약

## Review Focus

1. **맥이 9시에 잠들어 있다가 오후에 깨어나거나, 같은 날 두 번 실행됨** → 그날 이미 게시했거나 승인 대기 중이면 다시 만들지 않는다 (Task 8 테스트 `test_second_run_same_day_does_nothing`, `test_pending_today_is_not_regenerated`)
2. **Claude가 JSON이 아닌 답, 글자 수 초과, 렌더 시 넘침** → 피드백을 붙여 최대 2번 다시 생성, 그래도 실패하면 게시하지 않고 알림 (Task 3 `test_invalid_json_raises_claude_error`, Task 8 `test_overflow_retries_then_fails`)
3. **push 직후 raw URL이 아직 404** → 모든 URL이 200·image/jpeg가 될 때까지 기다린 뒤 인스타 호출 (Task 6 `test_waits_until_urls_are_live`)
4. **인스타 컨테이너가 IN_PROGRESS거나 ERROR** → FINISHED까지 기다리고, ERROR면 게시하지 않고 상태를 바꾸지 않는다(다음 날 같은 주제) (Task 7 `test_error_status_raises`, Task 8 `test_publish_failure_keeps_state`)
5. **토큰 60일 만료** → 마지막 갱신 50일이 지나면 실행 시 자동 갱신 (Task 8 `test_token_refreshed_after_50_days`)

---

## File Structure

```
pyproject.toml                 의존성, pytest 설정
.env.example                   IG_USER_ID, IG_ACCESS_TOKEN, IMAGE_BASE_URL, IG_API_VERSION
.gitignore                     + .env, var/, out/, logs/
hanip/
  __main__.py                  CLI: run | approve | preview | status | curriculum
  config.py                    Settings 로드
  state.py                     회차·커리큘럼 위치·승인 대기·이력 (var/state.json)
  claude_cli.py                `claude -p` 호출 → JSON
  curriculum.py                Topic, 커리큘럼 생성/로드 (data/curriculum.json)
  content.py                   Post 스키마(pydantic) + generate_post
  prompts/post.md              9장 문구 생성 프롬프트
  prompts/curriculum.md        커리큘럼 생성 프롬프트
  crawler.py                   GeekNews RSS + HN Algolia
  render.py                    HTML 생성, Playwright 렌더, 넘침·여백 측정, 미리보기
  templates/slides.html.j2     9장 레이아웃 (장 종류별 macro)
  templates/characters.svg.j2  캐릭터 SVG macro (cover, ending, 포즈 4종 × 테마)
  templates/theme.css.j2       light/dark 색 토큰
  assets/fonts/                Pretendard, D2Coding woff2 + OFL 라이선스
  publish_images.py            posts/NNNN/ 복사 → git push → URL 대기
  instagram.py                 Instagram API 클라이언트
  notify.py                    macOS 알림, 미리보기 열기
  pipeline.py                  run_daily / approve
data/curriculum.json           커리큘럼 (커밋, 사용자가 수정 가능)
posts/NNNN/slide-01..09.jpg    게시 이미지 (커밋, 공개 URL 원천)
scripts/com.hanip.daily.plist  launchd 설정 (평일 09:00)
scripts/install_launchd.sh
docs/setup.md                  크리에이터 전환, Meta 앱, 토큰, .env, launchd 설치 안내
tests/                         각 모듈 테스트 + fixtures/
```

---

### Task 1: 프로젝트 골격, 설정, 상태 저장

**Files:**
- Create: `pyproject.toml`, `.env.example`, `hanip/__init__.py`, `hanip/config.py`, `hanip/state.py`
- Modify: `.gitignore` (추가: `.env`, `var/`, `out/`, `logs/`, `.venv/`, `__pycache__/`)
- Test: `tests/test_state.py`, `tests/test_config.py`

**Interfaces:**
- Produces:
  - `Settings(ig_user_id: str, ig_access_token: str, image_base_url: str, ig_api_version: str, repo_dir: Path, var_dir: Path, out_dir: Path, account_handle: str = "@hanip.byte")`, frozen dataclass
  - `load_settings(env_file: Path | None = None) -> Settings`. `var/token.json`이 있으면 그 토큰이 `.env`보다 우선. `ig_api_version` 기본값 `"v23.0"` (실행 전 Meta 문서의 최신 버전으로 맞출 것)
  - `Pending(date: str, topic_id: str, number: int, theme: str, dir: str)`
  - `HistoryEntry(number: int, date: str, topic_id: str, theme: str, media_id: str)`
  - `State(published_count: int = 0, curriculum_index: int = 0, history: list[HistoryEntry], pending: Pending | None = None, token_refreshed_at: str | None = None)`
  - `load_state(path: Path) -> State` (파일 없으면 기본값), `save_state(state: State, path: Path) -> None` (임시 파일에 쓴 뒤 rename)
  - `next_number(state) -> int`, `theme_for(number: int) -> Literal["light","dark"]`, `needs_approval(number: int) -> bool`, `already_published_on(state, day: str) -> bool`

- [ ] **Step 1: uv 프로젝트 생성**

Run: `uv init --package --name hanip --python 3.12 . && uv add pydantic jinja2 playwright requests feedparser python-dotenv && uv add --dev pytest responses && uv run playwright install chromium`
Expected: `uv run python -c "import hanip"` 성공

- [ ] **Step 2: 실패하는 테스트 작성** (`tests/test_state.py`)

```python
def test_theme_alternates_by_number():
    assert theme_for(1) == "light" and theme_for(2) == "dark" and theme_for(13) == "light"

def test_needs_approval_first_five_only():
    assert [needs_approval(n) for n in (1, 5, 6)] == [True, True, False]

def test_next_number_is_published_count_plus_one():
    assert next_number(State(published_count=4)) == 5

def test_roundtrip_with_pending(tmp_path):
    s = State(published_count=2, curriculum_index=2,
              pending=Pending("2026-11-11", "token", 3, "light", "out/0003"))
    save_state(s, tmp_path / "state.json")
    assert load_state(tmp_path / "state.json") == s

def test_missing_file_gives_default(tmp_path):
    assert load_state(tmp_path / "nope.json") == State()

def test_already_published_on():
    s = State(history=[HistoryEntry(1, "2026-11-11", "token", "light", "m1")])
    assert already_published_on(s, "2026-11-11") and not already_published_on(s, "2026-11-12")
```

`tests/test_config.py`: `.env`에 `IG_ACCESS_TOKEN=a`, `var/token.json`에 `{"access_token": "b"}`이면 `load_settings().ig_access_token == "b"`.

- [ ] **Step 3: 실패 확인** — Run: `uv run pytest tests/test_state.py tests/test_config.py -v` / Expected: ImportError로 FAIL
- [ ] **Step 4: `hanip/config.py`, `hanip/state.py` 구현** (dataclass + `json`, `dataclasses.asdict`)
- [ ] **Step 5: 통과 확인** — 같은 명령, Expected: PASS
- [ ] **Step 6: 커밋** — `git add pyproject.toml uv.lock .env.example .gitignore hanip tests && git commit -m "feat: project skeleton, settings, state store"`

---

### Task 2: Claude CLI 호출과 커리큘럼

**Files:**
- Create: `hanip/claude_cli.py`, `hanip/curriculum.py`, `hanip/prompts/curriculum.md`
- Test: `tests/test_claude_cli.py`, `tests/test_curriculum.py`

**Interfaces:**
- Produces:
  - `class ClaudeError(Exception)`
  - `run_claude_json(prompt: str, *, runner=subprocess.run, timeout: int = 600) -> Any`: `["claude", "-p", prompt, "--output-format", "json"]` 실행. stdout JSON의 `result` 문자열에서 ```json 펜스가 있으면 벗기고 `json.loads`. 종료 코드≠0, `is_error: true`, 파싱 실패 시 `ClaudeError`
  - `Topic(id: str, title_ko: str, keyword_en: str, level: int)`, pydantic. `id`는 영어 소문자 kebab-case
  - `load_curriculum(path: Path) -> list[Topic]`, `save_curriculum(topics, path) -> None`
  - `generate_curriculum(count: int = 60, run=run_claude_json) -> list[Topic]`: id 중복이면 `ClaudeError`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def fake_runner(stdout, code=0):
    return lambda *a, **k: subprocess.CompletedProcess(a, code, stdout=stdout, stderr="")

def test_parses_fenced_json():
    out = json.dumps({"result": "```json\n{\"a\": 1}\n```", "is_error": False})
    assert run_claude_json("x", runner=fake_runner(out)) == {"a": 1}

def test_invalid_json_raises_claude_error():
    out = json.dumps({"result": "죄송해요", "is_error": False})
    with pytest.raises(ClaudeError): run_claude_json("x", runner=fake_runner(out))

def test_nonzero_exit_raises():
    with pytest.raises(ClaudeError): run_claude_json("x", runner=fake_runner("", code=1))

def test_generate_curriculum_rejects_duplicate_ids():
    run = lambda p: [{"id": "token", "title_ko": "토큰", "keyword_en": "token", "level": 1}] * 2
    with pytest.raises(ClaudeError): generate_curriculum(2, run=run)
```

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_claude_cli.py tests/test_curriculum.py -v`, Expected: FAIL
- [ ] **Step 3: 구현.** `prompts/curriculum.md`에는 다음을 적는다: 대상(AI 에이전트를 다루려는 비개발 직군), 범위(컴퓨터공학 용어 위주), 쉬운 것부터 level 1→5 순서, 반환 형식(`[{id,title_ko,keyword_en,level}]` JSON 배열만), 개수 `{count}`
- [ ] **Step 4: 통과 확인** — Expected: PASS
- [ ] **Step 5: 커밋** — `git commit -m "feat: claude -p runner and curriculum"`

---

### Task 3: 9장 문구 스키마와 생성

**Files:**
- Create: `hanip/content.py`, `hanip/prompts/post.md`
- Test: `tests/test_content.py`, `tests/fixtures/post_token.json` (모든 필드를 채운 유효한 예시. 렌더 테스트에서도 재사용)

**Interfaces:**
- Consumes: `run_claude_json`, `Topic`, `NewsItem`(Task 4. 여기서는 `title, source, url, summary` 필드를 가진 객체로만 사용)
- Produces (pydantic, 괄호 안은 최대 글자 수. 넘으면 ValidationError):
  - `Row(label: str(8), value: str(14))`
  - `Cover(title: str(12), subtitle: str(18))`
  - `Definition(definition: str(24), rows: list[Row] 3개, summary: str(14))`
  - `SetReceipt(name: str(6), caption: str(8), rows: list[Row] 2~3개, total: str(10))`
  - `Compare(a: SetReceipt, b: SetReceipt, conclusion: str(18))`
  - `Menu(items: list[Row] 3~4개, summary: str(14))`
  - `Check(text: str(14), checked: bool)`; `Options(checks: list[Check] 3~4개, summary: str(14))`
  - `Steps(steps: list[str(12)] 3~5개, summary: str(14))`
  - `Special(news: list[SpecialNews] 0~3개, fallback: str(40) | None)`; `SpecialNews(title: str(24), source: str(12), summary: str(24))`. news가 비면 fallback 필수 (model_validator)
  - `Caution(items: list[Row] 3개, summary: str(14))`
  - `Total(points: list[str(14)] 3개, next_topic: str(14) | None)`
  - `Post(topic_id: str, cover, definition, compare, menu, options, steps, special, caution, total, caption: str(600), hashtags: list[str] 5~10개)`
  - `generate_post(topic: Topic, next_topic: Topic | None, news: list[NewsItem], *, feedback: str | None = None, run=run_claude_json) -> Post`. 검증 실패 시 오류 내용을 feedback에 붙여 1회 재요청, 그래도 실패하면 `ClaudeError`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_fixture_is_valid():
    Post.model_validate_json(Path("tests/fixtures/post_token.json").read_text())

def test_row_value_too_long_rejected():
    with pytest.raises(ValidationError): Row(label="단위", value="가" * 15)

def test_special_requires_fallback_when_no_news():
    with pytest.raises(ValidationError): Special(news=[], fallback=None)

def test_generate_post_retries_once_on_validation_error():
    good = json.loads(Path("tests/fixtures/post_token.json").read_text())
    bad = {**good, "cover": {"title": "가" * 30, "subtitle": "x"}}
    calls = []
    def run(p): calls.append(p); return bad if len(calls) == 1 else good
    post = generate_post(TOPIC, None, [], run=run)
    assert post.cover.title == good["cover"]["title"] and "cover" in calls[1]

def test_prompt_includes_news_and_next_topic():
    seen = {}
    def run(p): seen["p"] = p; return json.loads(Path("tests/fixtures/post_token.json").read_text())
    generate_post(TOPIC, NEXT, [NEWS], run=run)
    assert NEWS.title in seen["p"] and NEXT.title_ko in seen["p"]
```

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_content.py -v`, Expected: FAIL
- [ ] **Step 3: 구현.** `prompts/post.md` 필수 내용: 대상 독자, 말투(반말, 짧게, 용어는 바로 풀어 쓰기), 장별 역할(스펙 5.3 표), 글자 수 한도(위 스키마와 같은 숫자), 소식(news)이 있으면 그 안에서만 고르고 지어내지 말 것, 없으면 fallback에 "요즘 왜 중요한지" 일반 설명, `Post` JSON만 반환. `next_topic`은 다음 Topic의 `title_ko`를 그대로 쓴다
- [ ] **Step 4: 통과 확인** — Expected: PASS
- [ ] **Step 5: 커밋** — `git commit -m "feat: post schema and generation via claude -p"`

---

### Task 4: 7장용 소식 크롤링

**Files:**
- Create: `hanip/crawler.py`
- Test: `tests/test_crawler.py`, `tests/fixtures/geeknews.xml`, `tests/fixtures/hn.json`

**Interfaces:**
- Produces:
  - `NewsItem(title: str, source: str, url: str, summary: str)`, dataclass
  - `fetch_geeknews(keyword: str, *, http_get=requests.get) -> list[NewsItem]`: `https://news.hada.io/rss/news`를 feedparser로 읽어 제목·요약에 keyword(대소문자 무시)나 한글 제목이 들어간 항목. source=`"GeekNews"`
  - `fetch_hn(keyword: str, *, since_days: int = 30, now: datetime | None = None, http_get=requests.get) -> list[NewsItem]`: `https://hn.algolia.com/api/v1/search_by_date?query={keyword}&tags=story&numericFilters=created_at_i>{ts}`. source=`"Hacker News"`
  - `find_news(topic: Topic, limit: int = 3, **fetchers) -> list[NewsItem]`: GeekNews 우선, 부족하면 HN으로 채움. URL 중복 제거. **예외를 밖으로 던지지 않고**, 실패한 소스는 건너뛴다(로그만)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_geeknews_filters_by_keyword(): ...   # fixture 5건 중 "token" 포함 2건만
def test_hn_uses_since_window(): ...          # http_get이 받은 URL에 created_at_i> 타임스탬프 포함
def test_find_news_dedupes_and_limits(): ...  # 두 소스에 같은 url → 1건, limit=3
def test_find_news_survives_source_error():
    boom = lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError())
    assert find_news(TOPIC, http_get=boom) == []
```

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_crawler.py -v`
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 확인**
- [ ] **Step 5: 커밋** — `git commit -m "feat: news crawler for slide 7"`

---

### Task 5: 템플릿과 렌더링

**Files:**
- Create: `hanip/templates/slides.html.j2`, `hanip/templates/characters.svg.j2`, `hanip/templates/theme.css.j2`, `hanip/assets/fonts/` (Pretendard-Regular/Bold/ExtraBold/Black.woff2, D2Coding.woff2, `OFL-Pretendard.txt`, `OFL-D2Coding.txt`), `hanip/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `Post` (Task 3)
- Produces:
  - `POSES = ("waddle", "rolling", "butterfly", "daze")`
  - `build_html(post: Post, *, number: int, theme: str, handle: str, filler: dict[int, str] | None = None) -> list[str]`: 9개의 완전한 HTML 문서. 글꼴은 `file://` 절대경로 `@font-face`
  - `measure(page) -> dict`: 브라우저에서 `{"overflow": bool, "content_bottom": float}` 반환. overflow = `.fit` 요소 중 scrollHeight>clientHeight 또는 scrollWidth>clientWidth, content_bottom = `.content` 요소의 bottom(px)
  - `RenderResult(paths: list[Path], overflow: list[int])` (overflow = 넘친 장 번호 1~9)
  - `render_post(post, *, number: int, theme: str, handle: str, out_dir: Path) -> RenderResult`: 1차 렌더·측정 → 2~8장 중 `content_bottom < 675`(1350의 절반)인 장에 `POSES[(number + slide_no) % 4]` 포즈를 넣어 2차 렌더. viewport 1080×1350, `page.screenshot(type="jpeg", quality=92)`, 파일명 `slide-01.jpg`~`slide-09.jpg`
  - `write_preview(paths: list[Path], caption: str, out_dir: Path) -> Path`: 9장을 나란히 + 캡션을 보여 주는 `preview.html`

- [ ] **Step 1: 글꼴 받기**

Run: Pretendard는 `https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/woff2/`에서 4종, D2Coding은 `https://github.com/naver/d2codingfont` 릴리스에서 받아 woff2로 변환(`uv run --with fonttools --with brotli pyftsubset ... --flavor=woff2` 또는 ttf 그대로 사용 가능). 라이선스 파일 함께 저장
Expected: `ls hanip/assets/fonts`에 5개 글꼴 + 2개 라이선스

- [ ] **Step 2: 실패하는 테스트 작성**

```python
@pytest.fixture
def post(): return Post.model_validate_json(Path("tests/fixtures/post_token.json").read_text())

def test_build_html_has_nine_pages_with_series_tag(post):
    pages = build_html(post, number=7, theme="light", handle="@hanip.byte")
    assert len(pages) == 9 and "No.07" in pages[1] and "@hanip.byte" in pages[0]

def test_ending_copy_is_fixed(post):
    last = build_html(post, number=1, theme="dark", handle="@hanip.byte")[8]
    assert "오늘의 한입 소화 완료" in last and "필요할 때 다시 먹으러 와" in last

def test_theme_colors(post):
    assert "#fff7fa" in build_html(post, number=1, theme="light", handle="h")[1]
    assert "#16121e" in build_html(post, number=2, theme="dark", handle="h")[1]

def test_dark_character_is_white_with_blue_star(post):
    cover = build_html(post, number=2, theme="dark", handle="h")[0]
    assert "#f7f5fb" in cover and "#5b9dff" in cover

def test_render_outputs_nine_jpegs(post, tmp_path):
    r = render_post(post, number=1, theme="light", handle="@hanip.byte", out_dir=tmp_path)
    assert [p.name for p in r.paths] == [f"slide-{i:02d}.jpg" for i in range(1, 10)]
    assert all(Image.open(p).size == (1080, 1350) and Image.open(p).format == "JPEG" for p in r.paths)
    assert r.overflow == []

def test_overflow_detected(post, tmp_path):
    long = post.model_copy(deep=True)
    long.definition.definition = "아주긴단어" * 5   # 스키마 검증을 우회해 강제로 넘치게
    assert 2 in render_post(long, number=1, theme="light", handle="h", out_dir=tmp_path).overflow

def test_short_slide_gets_filler(post, tmp_path, monkeypatch):
    seen = {}
    real = build_html
    def spy(*a, **k): seen.update(k.get("filler") or {}); return real(*a, **k)
    monkeypatch.setattr("hanip.render.build_html", spy)
    render_post(post, number=1, theme="light", handle="h", out_dir=tmp_path)
    assert seen and set(seen.values()) <= set(POSES)
```

(이미지 확인용 `pillow`는 dev 의존성으로 추가: `uv add --dev pillow`)

- [ ] **Step 3: 실패 확인** — `uv run pytest tests/test_render.py -v`
- [ ] **Step 4: 템플릿 작성.** 시안 `slides-light.html`, `slides-dark.html`, `character-light-cover-ending.html`, `filler-poses.html`의 SVG 좌표·색을 그대로 옮기고 1080×1350에 맞게 키운다. 장별 레이아웃은 스펙 5.3 표. 8장은 배경을 바꾸지 않고, 종이 테두리(light `#f2b632` / dark `#ffd166`)와 노란 띠로만 경고를 표시한다. 1장 입 안에 혀를 넣지 않는다. 넘침을 검사할 텍스트 상자에는 `class="fit"`, 장의 본문 묶음에는 `class="content"`
- [ ] **Step 5: `render.py` 구현** (Playwright sync API, 브라우저 1개로 9장 렌더)
- [ ] **Step 6: 통과 확인** — Expected: PASS
- [ ] **Step 7: 눈으로 확인** — Run: `uv run python -c "from hanip.render import *; ..."`로 fixture를 light와 dark로 렌더하고 `write_preview`를 연 뒤 시안과 비교. 사용자에게 캡처를 보여 주고 확인받는다
- [ ] **Step 8: 커밋** — `git commit -m "feat: receipt-style slide templates and jpeg renderer"`

---

### Task 6: 이미지를 GitHub에 올려 공개 URL 만들기

**Files:**
- Create: `hanip/publish_images.py`
- Test: `tests/test_publish_images.py`

**Interfaces:**
- Produces:
  - `class ImageHostError(Exception)`
  - `publish_images(paths: list[Path], *, number: int, repo_dir: Path, base_url: str, git=subprocess.run, http_head=requests.head, sleep=time.sleep, wait_timeout: int = 300) -> list[str]`: `repo_dir/posts/{number:04d}/`에 복사 → `git add posts/{number:04d}` → `git commit -m "post: No.{number:02d}" -- posts/{number:04d}` (다른 변경 파일은 커밋하지 않음) → `git push origin HEAD` → `f"{base_url}/posts/{number:04d}/slide-XX.jpg"` 목록. 모든 URL이 200이고 content-type이 `image/jpeg`가 될 때까지 10초 간격으로 확인, 시간 초과면 `ImageHostError`. 이미 같은 파일이 커밋돼 있으면(commit할 변경 없음) 그대로 진행

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_commits_only_post_dir_and_pushes(tmp_path): ...  # git 호출 인자 기록: commit 명령 끝이 ["--", "posts/0003"], push 호출 존재
def test_returns_raw_urls_in_order(tmp_path): ...        # base_url + /posts/0003/slide-01.jpg ... 09
def test_waits_until_urls_are_live(tmp_path):
    codes = iter([404] * 9 + [200] * 9)
    head = lambda url, **k: SimpleNamespace(status_code=next(codes), headers={"content-type": "image/jpeg"})
    urls = publish_images(PATHS, number=3, repo_dir=tmp_path, base_url="https://x", git=ok_git, http_head=head, sleep=lambda s: None)
    assert len(urls) == 9
def test_timeout_raises(tmp_path): ...                   # 계속 404 → ImageHostError
```

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_publish_images.py -v`
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 확인**
- [ ] **Step 5: 커밋** — `git commit -m "feat: publish slide images via git push"`

---

### Task 7: Instagram API 클라이언트

**Files:**
- Create: `hanip/instagram.py`
- Test: `tests/test_instagram.py` (`responses`로 HTTP 모킹)

**Interfaces:**
- Produces:
  - `class InstagramError(Exception)`
  - `InstagramClient(user_id: str, token: str, *, api_version: str, session: requests.Session | None = None, sleep=time.sleep)`, 기본 주소 `https://graph.instagram.com/{api_version}`
    - `create_image_item(image_url: str) -> str`: `POST /{user_id}/media` (`image_url`, `is_carousel_item=true`)
    - `create_carousel(children: list[str], caption: str) -> str`: `POST /{user_id}/media` (`media_type=CAROUSEL`, `children`=쉼표로 이은 id, `caption`)
    - `wait_until_ready(container_id: str, timeout: int = 300) -> None`: `GET /{container_id}?fields=status_code`를 5초 간격. `FINISHED`면 반환, `ERROR`/`EXPIRED`/시간 초과면 `InstagramError`
    - `publish(container_id: str) -> str`: `POST /{user_id}/media_publish` (`creation_id`), 반환 media id
    - `post_carousel(image_urls: list[str], caption: str) -> str`: 각 이미지 컨테이너 생성 → 각각 wait → 캐러셀 생성 → wait → publish
  - `refresh_token(token: str, *, session=None) -> tuple[str, int]`: `GET https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=...` → `(access_token, expires_in)`
  - 모든 HTTP 오류 응답(4xx/5xx 또는 `error` 필드)은 메시지를 담아 `InstagramError`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
@responses.activate
def test_post_carousel_happy_path(): ...  # 이미지 9개 생성 → 캐러셀(children 9개, caption) → publish, 반환 "MEDIA1"
@responses.activate
def test_waits_through_in_progress(): ... # IN_PROGRESS 2번 뒤 FINISHED, sleep 호출 2번
@responses.activate
def test_error_status_raises():           # status_code=ERROR → InstagramError, publish 호출 안 됨
    ...
    assert not any("media_publish" in c.request.url for c in responses.calls)
@responses.activate
def test_api_error_message_surfaces(): ...  # 400 {"error":{"message":"Invalid token"}} → 메시지에 "Invalid token"
@responses.activate
def test_refresh_token(): ...               # ("NEW", 5184000)
```

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_instagram.py -v`
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 확인**
- [ ] **Step 5: 커밋** — `git commit -m "feat: instagram carousel publishing client"`

---

### Task 8: 파이프라인과 CLI (실행, 승인, 반자동)

**Files:**
- Create: `hanip/notify.py`, `hanip/pipeline.py`, `hanip/__main__.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: Task 1~7 전부
- Produces:
  - `notify(title: str, message: str) -> None` (`osascript -e 'display notification ...'`), `open_file(path: Path) -> None` (`open`)
  - `class Outcome(StrEnum)`: `SKIPPED_WEEKEND`, `ALREADY_POSTED`, `PENDING_APPROVAL`, `PUBLISHED`, `FAILED`, `CURRICULUM_EXHAUSTED`, `NOTHING_TO_APPROVE`
  - `Deps` dataclass: `find_news, generate_post, render_post, write_preview, publish_images, make_instagram, refresh_token, notify, open_file` (기본값은 실제 함수, 테스트에서 가짜로 교체)
  - `run_daily(settings: Settings, *, today: date, deps: Deps = Deps()) -> Outcome`
  - `approve(settings: Settings, *, today: date, deps: Deps = Deps()) -> Outcome`
  - CLI: `python -m hanip run | approve | preview | status | curriculum [--count 60]`. `status`는 회차, 다음 주제, 대기 중 여부, 최근 5회 이력. `curriculum`은 `data/curriculum.json`이 이미 있으면 `--force` 없이는 덮어쓰지 않음. 로그는 `logs/YYYY-MM-DD.log`

`run_daily` 순서 (각 줄이 테스트 대상):
1. 토/일 → `SKIPPED_WEEKEND`
2. 오늘 이미 게시 → `ALREADY_POSTED`
3. `pending.date == today` → 미리보기만 다시 열고 `PENDING_APPROVAL` (다시 만들지 않음)
4. `token_refreshed_at`이 없거나 50일 지났으면 `refresh_token` → `var/token.json` 저장, `token_refreshed_at` 갱신. 실패해도 계속 진행(알림만)
5. `curriculum_index`가 범위 밖 → 알림 + `CURRICULUM_EXHAUSTED`
6. 소식 수집 → 문구 생성 → 렌더. 넘침이 있으면 `feedback="N장 글자가 넘쳐. 더 짧게"`로 재생성, 최대 2회. 그래도 넘치거나 `ClaudeError`면 알림 + `FAILED` (상태 변경 없음)
7. `number = next_number`, `theme = theme_for(number)`
8. `needs_approval(number)` → 이전 pending을 지우고 새 pending 저장 → 미리보기 열기 + 알림("승인: python -m hanip approve") → `PENDING_APPROVAL`
9. 아니면 `_publish`

`approve`: pending이 없거나 `pending.date != today`면 `NOTHING_TO_APPROVE`(날짜가 지났으면 "다음 실행에서 다시 만들어요" 안내). 있으면 `_publish`.

`_publish`: `publish_images` → `make_instagram(settings).post_carousel(urls, caption + 해시태그)` → 성공 시 `published_count += 1`, `curriculum_index += 1`, history 추가, pending 삭제, 저장, 알림 → `PUBLISHED`. 어느 단계든 예외면 상태를 바꾸지 않고 알림 + `FAILED`.

- [ ] **Step 1: 실패하는 테스트 작성** (가짜 Deps, `tmp_path`의 var/·data/ 사용)

```python
def test_weekend_skips(): assert run_daily(S, today=date(2026, 11, 14), deps=D) == Outcome.SKIPPED_WEEKEND
def test_first_run_waits_for_approval_with_light_theme(): ...   # PENDING_APPROVAL, pending.number==1, theme=="light", publish_images 미호출
def test_pending_today_is_not_regenerated(): ...                # 같은 날 두 번째 run → generate_post 1회만
def test_stale_pending_regenerates_same_topic(): ...            # 어제 pending → 오늘 run이 같은 topic_id로 새 pending
def test_approve_publishes_and_advances(): ...                  # PUBLISHED, published_count 1, curriculum_index 1, pending None
def test_approve_without_pending_today(): ...                   # NOTHING_TO_APPROVE
def test_sixth_post_publishes_without_approval(): ...           # published_count=5 → run이 바로 PUBLISHED, theme "dark"
def test_second_run_same_day_does_nothing(): ...                # 게시 후 같은 날 run → ALREADY_POSTED
def test_overflow_retries_then_fails(): ...                     # render overflow 3번 → generate_post 3회, FAILED, 상태 그대로
def test_publish_failure_keeps_state(): ...                     # post_carousel이 InstagramError → FAILED, published_count 그대로
def test_token_refreshed_after_50_days(): ...                   # token_refreshed_at 51일 전 → refresh_token 호출, var/token.json 기록
def test_curriculum_exhausted(): ...                            # index == len → CURRICULUM_EXHAUSTED + notify
def test_missed_day_posts_only_next_topic(): ...                # 이틀 건너뛴 뒤 run → 게시 1건, index +1
```

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_pipeline.py -v`
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 확인** — 전체: `uv run pytest -v`, Expected: 전부 PASS
- [ ] **Step 5: 커밋** — `git commit -m "feat: daily pipeline with semi-auto approval and CLI"`

---

### Task 9: 예약 실행, 설정 안내, 첫 실제 실행

**Files:**
- Create: `scripts/com.hanip.daily.plist`, `scripts/install_launchd.sh`, `docs/setup.md`
- Test: 수동 검증 (아래 Step)

**Interfaces:**
- Consumes: `python -m hanip run` (Task 8)

- [ ] **Step 1: plist 작성.** `StartCalendarInterval`에 `{Weekday 1..5, Hour 9, Minute 0}` 5개, `ProgramArguments` = `[<repo>/.venv/bin/python, -m, hanip, run]`, `WorkingDirectory` = 저장소 경로, `StandardOutPath`/`StandardErrorPath` = `logs/launchd.log`, `EnvironmentVariables.PATH`에 `~/.local/bin` 포함(`claude`를 찾을 수 있게). `install_launchd.sh`는 경로를 채워 `~/Library/LaunchAgents/`에 복사하고 `launchctl bootstrap gui/$(id -u)` 실행
- [ ] **Step 2: `docs/setup.md` 작성.** 순서: ① 인스타 앱에서 크리에이터 계정으로 전환 ② 아이디를 `hanip.byte`로 변경(사용 중이면 `hanip.byte.kr`, 그 경우 `.env`의 계정 표기도 바꿈) ③ developers.facebook.com에서 앱 생성 → "Instagram API(Instagram 로그인 방식)" 추가 → 권한 `instagram_business_basic`, `instagram_business_content_publish` → 테스터에 계정 추가 → 토큰 생성 ④ IG 사용자 ID 확인 ⑤ `.env` 작성 ⑥ GitHub `soyoung-yu/insta-auto` 공개 저장소 생성 후 `git remote set-url origin https://github.com/soyoung-yu/insta-auto.git`, `IMAGE_BASE_URL=https://raw.githubusercontent.com/soyoung-yu/insta-auto/main` ⑦ `uv run python -m hanip curriculum` 후 `data/curriculum.json` 검토 ⑧ `scripts/install_launchd.sh`
- [ ] **Step 3: 사용자와 함께 setup.md ①~⑦ 진행** (계정 전환, 앱 생성, 토큰 발급은 사용자가 직접)
- [ ] **Step 4: 예약 등록 확인** — Run: `scripts/install_launchd.sh && launchctl print gui/$(id -u)/com.hanip.daily | grep -A2 "state\|calendar"`, Expected: 작업이 등록되고 평일 09:00 일정이 보임
- [ ] **Step 5: 첫 실행 (평일에)** — Run: `uv run python -m hanip run`, Expected: 알림이 뜨고 미리보기가 열림, `status`에 "No.01 승인 대기". 사용자가 미리보기 확인
- [ ] **Step 6: 첫 게시** — Run: `uv run python -m hanip approve`, Expected: `PUBLISHED`, 인스타 @hanip.byte에 9장 캐러셀, `posts/0001/` push됨
- [ ] **Step 7: 커밋** — `git add scripts docs/setup.md && git commit -m "chore: launchd schedule and setup guide"`
