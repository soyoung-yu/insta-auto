import json
from pathlib import Path
import truststore; truststore.inject_into_ssl()
from hanip.content import Post
from hanip.pipeline import full_caption
from hanip.render import render_post, write_preview
from hanip.config import load_settings
s = load_settings()
out = Path("out/0005")
d = json.loads((out/"post.json").read_text())
d["compare"] = {
    "a": {"name": "메서드", "caption": "무엇을 할지", "rows": [
        {"label": "뜻", "value": "할 일"},
        {"label": "예시", "value": "읽기·수정"},
        {"label": "표기", "value": "GET·PUT"}]},
    "b": {"name": "주소(URL)", "caption": "어떤 데이터에", "rows": [
        {"label": "뜻", "value": "대상"},
        {"label": "예시", "value": "3번 글"},
        {"label": "표기", "value": "/posts/3"}]},
    "conclusion": "주소는 대상, 메서드는 할 일이야",
}
post = Post.model_validate(d)
for p in out.glob("slide-*.jpg"): p.unlink()
res = render_post(post, number=5, theme="light", handle=s.account_handle, out_dir=out)
print("overflow:", res.overflow)
(out/"post.json").write_text(post.model_dump_json(indent=2))
report = (out/"factcheck.txt").read_text() if (out/"factcheck.txt").exists() else ""
paths = sorted(out.glob("slide-*.jpg"))
write_preview(paths, full_caption(post), out, report=report)
print(len(paths))
