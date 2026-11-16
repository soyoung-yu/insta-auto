from pathlib import Path
import truststore; truststore.inject_into_ssl()
from hanip.config import load_settings
from hanip.content import Post
from hanip.pipeline import full_caption, Deps
from hanip.publish_images import publish_images
from hanip.state import load_state, save_state
s = load_settings(); out = Path("out/0005")
post = Post.model_validate_json((out/"post.json").read_text())
paths = sorted(out.glob("slide-*.jpg")); assert len(paths) == 10
urls = publish_images(paths, number=5, repo_dir=s.repo_dir, base_url=s.image_base_url)
client = Deps().make_instagram(s)
media_id = client.post_carousel(urls, full_caption(post))
st = load_state(s.state_path)
h = st.history[-1]; assert h.number == 5
h.media_id = media_id
save_state(st, s.state_path)
print("media_id", media_id)
