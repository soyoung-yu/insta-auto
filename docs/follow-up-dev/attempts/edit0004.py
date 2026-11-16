import json
from pathlib import Path
import truststore; truststore.inject_into_ssl()
from hanip.content import Post
from hanip.pipeline import full_caption
from hanip.render import render_post, write_preview
from hanip.config import load_settings
s = load_settings()
out = Path("out/0004")
d = json.loads((out/"post.json").read_text())
d["definition"] = {
    "definition": "요청·응답의 형식을 정한, 웹 통신 규칙이야.",
    "rows": [
        {"label": "풀네임", "value": "하이퍼텍스트 전송 규약"},
        {"label": "요청에 담는 것", "value": "메서드·주소·헤더"},
        {"label": "응답에 담는 것", "value": "상태 코드·데이터"},
    ],
}
d["menu"]["items"] = [
    {"name": "페이지 열기", "src": "브라우저", "action": "GET 요청", "dst": "웹 서버"},
    {"name": "페이지 받기", "src": "웹 서버", "action": "200 OK", "dst": "브라우저"},
    {"name": "글 올리기", "src": "모바일 앱", "action": "POST 요청", "dst": "API 서버"},
    {"name": "로그인 유지", "src": "브라우저", "action": "매번 쿠키 첨부", "dst": "웹 서버"},
]
d["steps"]["steps"] = [
    {"text": "HTTP 요청 메시지 작성", "who": "a"},
    {"text": "메서드·주소 담아 전송", "who": "a"},
    {"text": "같은 형식이라 서버가 이해", "who": "other"},
    {"text": "상태 코드 담아 응답", "who": "b"},
    {"text": "브라우저가 형식대로 해석", "who": "b"},
]
post = Post.model_validate(d)
for p in out.glob("slide-*.jpg"): p.unlink()
res = render_post(post, number=4, theme="dark", handle=s.account_handle, out_dir=out)
print("overflow:", res.overflow)
(out/"post.json").write_text(post.model_dump_json(indent=2))
report = (out/"factcheck.txt").read_text() if (out/"factcheck.txt").exists() else ""
paths = sorted(out.glob("slide-*.jpg"))
write_preview(paths, full_caption(post), out, report=report)
print(len(paths))
