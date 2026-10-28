"""アセットボックス Instagram 自動投稿

毎朝 GitHub Actions から実行される。
1. 投稿管理表（Googleスプレッドシート「投稿」シートをCSVでウェブ公開したもの）を読む
2. 今日（日本時間）の行で、ステータスが「保留」「修正依頼」「投稿済」以外なら投稿対象
3. images/<画像ファイル> が無ければ I列のカード設定(JSON)から画像を作り、リポジトリに push
4. Instagram API で投稿し、posted.json に記録

環境変数:
  SHEET_CSV_URL  … 公開CSVのURL
  IG_USER_ID     … InstagramアカウントID
  IG_TOKEN       … アクセストークン（Secrets）
  POST_DATE      … 省略時は今日。YYYY-MM-DD で日付を指定（手動実行のテスト用）
  DRY_RUN        … "1" なら画像作成まで（投稿しない）
"""
import csv, io, json, os, subprocess, sys, time, datetime as dt
import urllib.request, urllib.parse, urllib.error
from pathlib import Path

ROOT = Path(__file__).parent
IMAGES = ROOT / "images"
POSTED = ROOT / "posted.json"
API = "https://graph.instagram.com/v23.0"
SKIP_STATUSES = {"保留", "修正依頼", "投稿済"}
JST = dt.timezone(dt.timedelta(hours=9))


def log(*a):
    print(*a, flush=True)


def http(method, url, params=None, retries=3):
    data = None
    if params is not None and method == "GET":
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    elif params is not None:
        data = urllib.parse.urlencode(params).encode()
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, method=method)
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read().decode("utf-8")
                return json.loads(body) if body.strip().startswith(("{", "[")) else body
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code < 500 or i == retries - 1:
                raise RuntimeError(f"HTTP {e.code}: {body[:500]}")
        except urllib.error.URLError as e:
            if i == retries - 1:
                raise
        time.sleep(5 * (i + 1))


def parse_date(s):
    s = (s or "").strip().replace("-", "/").split(" ")[0]
    for fmt in ("%Y/%m/%d", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def load_rows(url):
    text = http("GET", url)
    if not isinstance(text, str):
        text = json.dumps(text)
    rows = list(csv.reader(io.StringIO(text)))
    head = [h.strip() for h in rows[0]]

    def col(name, default=None):
        for i, h in enumerate(head):
            if h.startswith(name):
                return i
        return default

    idx = dict(date=col("投稿日", 0), theme=col("テーマ", 2), image=col("画像", 3),
               caption=col("Instagram", 4), status=col("ステータス", 6), card=col("カード", 8))
    out = []
    for r in rows[1:]:
        r = r + [""] * (len(head) - len(r))
        g = lambda k: r[idx[k]].strip() if idx[k] is not None and idx[k] < len(r) else ""
        out.append(dict(date=parse_date(g("date")), theme=g("theme"), image=g("image"),
                        caption=g("caption"), status=g("status"), card=g("card")))
    return out


def git(*args):
    subprocess.run(["git", *args], cwd=ROOT, check=True)


def ensure_image(row):
    name = row["image"] or ""
    if not name and row["card"]:
        name = json.loads(row["card"])["id"] + ".jpg"
    if not name:
        raise RuntimeError("画像ファイル名もカード設定もありません")
    path = IMAGES / name
    if path.exists():
        log("既存の画像を使用:", path.name)
        return path
    if not row["card"]:
        raise RuntimeError(f"images/{name} が無く、カード設定(I列)も空です")
    from make_cards import render
    card = json.loads(row["card"])
    card["id"] = Path(name).stem
    render([card], IMAGES)
    return path


def publish(image_url, caption, user_id, token):
    c = http("POST", f"{API}/{user_id}/media",
             dict(image_url=image_url, caption=caption, access_token=token))
    cid = c["id"]
    log("コンテナ作成:", cid)
    for _ in range(30):
        st = http("GET", f"{API}/{cid}", dict(fields="status_code,status", access_token=token))
        log("状態:", st.get("status_code"))
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"メディア処理エラー: {st}")
        time.sleep(5)
    else:
        raise RuntimeError("メディア処理がタイムアウトしました")
    p = http("POST", f"{API}/{user_id}/media_publish", dict(creation_id=cid, access_token=token))
    mid = p["id"]
    info = http("GET", f"{API}/{mid}", dict(fields="permalink,timestamp", access_token=token))
    return mid, info.get("permalink", "")


def main():
    today = (dt.date.fromisoformat(os.environ["POST_DATE"]) if os.environ.get("POST_DATE")
             else dt.datetime.now(JST).date())
    dry = os.environ.get("DRY_RUN") == "1"
    log("対象日:", today, "(DRY RUN)" if dry else "")

    posted = json.loads(POSTED.read_text()) if POSTED.exists() else {}
    if str(today) in posted:
        log("この日はすでに投稿済みです:", posted[str(today)])
        return

    rows = [r for r in load_rows(os.environ["SHEET_CSV_URL"]) if r["date"] == today]
    if not rows:
        log("今日の投稿予定はありません")
        return
    row = rows[0]
    log("テーマ:", row["theme"], "/ ステータス:", row["status"] or "(空)")
    if row["status"] in SKIP_STATUSES:
        log(f"ステータスが「{row['status']}」のため投稿しません")
        return
    if not row["caption"]:
        raise RuntimeError("Instagramキャプションが空です")

    path = ensure_image(row)
    rel = path.relative_to(ROOT).as_posix()
    git("add", rel)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode != 0:
        git("commit", "-m", f"画像追加 {today} {row['theme']}")
        git("push")
        time.sleep(15)

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    image_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{urllib.parse.quote(rel)}"
    log("画像URL:", image_url)
    if dry:
        log("DRY RUN のため投稿しません")
        return

    mid, link = publish(image_url, row["caption"], os.environ["IG_USER_ID"], os.environ["IG_TOKEN"])
    log("投稿しました:", link or mid)
    posted[str(today)] = dict(theme=row["theme"], media_id=mid, permalink=link,
                              image=rel, posted_at=dt.datetime.now(JST).isoformat(timespec="seconds"))
    POSTED.write_text(json.dumps(posted, ensure_ascii=False, indent=1) + "\n")
    git("add", "posted.json")
    git("commit", "-m", f"投稿記録 {today}")
    git("push")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("エラー:", e)
        sys.exit(1)
