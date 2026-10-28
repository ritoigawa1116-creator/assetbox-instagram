# アセットボックス SNSテキストカード生成（1080x1350 JPEG）
# 使い方: python3 make_cards.py cards.json 出力フォルダ
import base64, json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
LOGO = base64.b64encode((HERE / "assetbox_logo.png").read_bytes()).decode()

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{width:1080px;height:1350px;font-family:'Noto Sans CJK JP',sans-serif;background:#fbf7ee;color:#0b1a45;overflow:hidden}
.wrap{position:relative;width:1080px;height:1350px;padding:70px 80px 0;display:flex;flex-direction:column}
.wrap:before{content:'';position:absolute;top:0;left:0;right:0;height:14px;background:#b08d57}
.head{display:flex;align-items:center;gap:22px}
.head img{width:92px;height:auto;mix-blend-mode:multiply}
.head .org{font-family:'Noto Serif CJK JP',serif;font-size:30px;line-height:1.35;color:#8a6a3a;font-weight:700}
.tag{display:inline-block;margin-top:70px;align-self:flex-start;background:#0b1a45;color:#fff;font-size:30px;font-weight:700;padding:10px 26px;border-radius:6px;letter-spacing:.05em}
h1{margin-top:34px;font-size:78px;line-height:1.32;font-weight:900;letter-spacing:.01em}
h1 em{font-style:normal;color:#9a7440;background:linear-gradient(transparent 68%,#efe0c2 68%)}
.lead{margin-top:34px;font-size:36px;line-height:1.7;font-weight:500;color:#26335c}
ul{margin-top:40px;list-style:none;display:flex;flex-direction:column;gap:22px}
li{font-size:40px;font-weight:700;line-height:1.4;padding-left:62px;position:relative}
li:before{content:'';position:absolute;left:0;top:10px;width:38px;height:38px;border-radius:50%;background:#b08d57}
li:after{content:'';position:absolute;left:12px;top:17px;width:10px;height:18px;border:solid #fff;border-width:0 5px 5px 0;transform:rotate(45deg)}
ol{margin-top:44px;list-style:none;display:flex;flex-direction:column;gap:20px;counter-reset:n}
ol li{padding-left:84px}
ol li:before{counter-increment:n;content:counter(n);width:58px;height:58px;top:-2px;background:#0b1a45;color:#fff;font-size:32px;display:flex;align-items:center;justify-content:center}
ol li:after{display:none}
ol li small{display:block;font-size:30px;font-weight:500;color:#4a5578;margin-top:4px}
.spacer{flex:1}
.foot{margin:0 -80px;background:#0b1a45;color:#fff;padding:40px 80px 46px;display:flex;justify-content:space-between;align-items:flex-end}
.foot .l{font-size:30px;line-height:1.5}
.foot .l b{display:block;font-size:44px;color:#e9d3a6;letter-spacing:.02em}
.foot .r{font-size:26px;text-align:right;line-height:1.6;color:#d8dcea}
"""

def card_html(c):
    body = ""
    if c.get("lead"):
        body += f'<p class="lead">{c["lead"]}</p>'
    if c.get("items"):
        body += "<ul>" + "".join(f"<li>{i}</li>" for i in c["items"]) + "</ul>"
    if c.get("steps"):
        body += "<ol>" + "".join(f"<li>{t}<small>{s}</small></li>" for t, s in c["steps"]) + "</ol>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="wrap">
  <div class="head"><img src="data:image/png;base64,{LOGO}"><div class="org">一般社団法人<br>アセットボックス</div></div>
  <span class="tag">{c['tag']}</span>
  <h1>{c['title']}</h1>
  {body}
  <div class="spacer"></div>
  <div class="foot">
    <div class="l">ご相談・現地調査・お見積り 無料<b>☎ 0573-64-2020</b></div>
    <div class="r">岐阜県中津川市<br>全国対応（一部地域除く）</div>
  </div>
</div></body></html>"""

def render(cards, out_dir):
    """cards: list of dicts. Writes <out_dir>/<id>.jpg (1080x1350 JPEG)."""
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    paths = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        for c in cards:
            pg.set_content(card_html(c))
            pg.wait_for_timeout(300)
            path = out / f"{c['id']}.jpg"
            pg.screenshot(path=str(path), type="jpeg", quality=90)
            paths.append(path)
            print("rendered", path)
        b.close()
    return paths


def main(spec_path, out_dir):
    render(json.loads(Path(spec_path).read_text()), out_dir)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
