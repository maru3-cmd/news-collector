import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
import google.generativeai as genai

# Gemini APIの設定
genai.configure(api_key=os.environ['GEMINI_API_KEY'])
model = genai.GenerativeModel('gemini-2.5-flash')

YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# ========================================
# ウォッチするチャンネル（追加・削除はここで）
# チャンネルIDの調べ方:
#   チャンネルページ → 右クリック → ページのソースを表示
#   → "channelId" で検索、または youtube.com/channel/XXXX のXXXX部分
# ========================================
CHANNELS = [
    # AI系
    {"name": "マジAI", "id": "UCkHF7L3ZCq8HsFZMgCNkNjQ"},
    {"name": "ハック大学", "id": "UCZsIJbKQMqoKbreM5a00Gmg"},
    {"name": "AIニュースラボ", "id": "UCpXAS-M6RxbHbVPn5gNkUfg"},
    {"name": "AI仙人", "id": "UCnPHUjuDDVFi5ITwnqP87uw"},
    # ビジネス×テクノロジー
    {"name": "PIVOT", "id": "UCMlbH3wnmUwLxBMkXGBbGBw"},
    # 製造業DX系
    {"name": "ものづくり太郎", "id": "UCMlKwbkOSFSTKaGo2OAMV6A"},
    {"name": "日経クロステック", "id": "UCkBOCUsFTjPbOjNPNqFaN4A"},
]

# ========================================
# 検索キーワード（追加・削除はここで）
# ========================================
SEARCH_KEYWORDS = [
    "AI 最新 2026",
    "DX 製造業",
    "生成AI 活用",
    "最先端技術 2026",
]

# 各キーワードで取得する動画数
SEARCH_COUNT = 2
# 各チャンネルから取得する動画数
CHANNEL_COUNT = 1
# 何日以内の動画を対象とするか
DAYS_BACK = 7


def youtube_api_get(endpoint, params):
    """YouTube Data API v3にGETリクエスト"""
    params["key"] = YOUTUBE_API_KEY
    query = urllib.parse.urlencode(params)
    url = f"{YOUTUBE_API_BASE}/{endpoint}?{query}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NewsCollector/2.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  YouTube API エラー ({endpoint}): {e}")
        return None


def summarize_video(title, description):
    """動画のタイトルと説明文からサマリーを生成"""
    desc_short = description[:800] if description else ""
    prompt = f"""以下のYouTube動画を日本語で3-4文で簡潔に要約してください。動画の主要な論点や結論があれば含めてください。
タイトル: {title}
説明文: {desc_short}"""
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"要約エラー: {str(e)}"


def collect_from_channels():
    """指定チャンネルの最新動画を取得"""
    videos = []
    published_after = (datetime.utcnow() - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%dT00:00:00Z")

    for ch in CHANNELS:
        print(f"  チャンネル取得中: {ch['name']}...")
        data = youtube_api_get("search", {
            "channelId": ch["id"],
            "part": "snippet",
            "order": "date",
            "type": "video",
            "publishedAfter": published_after,
            "maxResults": CHANNEL_COUNT,
        })
        if not data or "items" not in data:
            continue

        for item in data["items"]:
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId", "")
            title = snippet.get("title", "タイトルなし")
            description = snippet.get("description", "")
            thumbnail = snippet.get("thumbnails", {}).get("medium", {}).get("url", "")
            published = snippet.get("publishedAt", "")

            summary = summarize_video(title, description)
            videos.append({
                "source": ch["name"],
                "title": title,
                "link": f"https://www.youtube.com/watch?v={video_id}",
                "video_id": video_id,
                "summary": summary,
                "thumbnail": thumbnail,
                "published_at": published,
                "content_type": "youtube",
                "search_type": "channel",
                "collected_at": datetime.now().isoformat()
            })
    return videos


def collect_from_keywords():
    """キーワード検索で最新動画を取得"""
    videos = []
    published_after = (datetime.utcnow() - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%dT00:00:00Z")

    for keyword in SEARCH_KEYWORDS:
        print(f"  キーワード検索中: {keyword}...")
        data = youtube_api_get("search", {
            "q": keyword,
            "part": "snippet",
            "order": "date",
            "type": "video",
            "relevanceLanguage": "ja",
            "publishedAfter": published_after,
            "maxResults": SEARCH_COUNT,
        })
        if not data or "items" not in data:
            continue

        for item in data["items"]:
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId", "")
            title = snippet.get("title", "タイトルなし")
            description = snippet.get("description", "")
            channel_name = snippet.get("channelTitle", "不明")
            thumbnail = snippet.get("thumbnails", {}).get("medium", {}).get("url", "")
            published = snippet.get("publishedAt", "")

            summary = summarize_video(title, description)
            videos.append({
                "source": channel_name,
                "title": title,
                "link": f"https://www.youtube.com/watch?v={video_id}",
                "video_id": video_id,
                "summary": summary,
                "thumbnail": thumbnail,
                "published_at": published,
                "content_type": "youtube",
                "search_type": "keyword",
                "search_keyword": keyword,
                "collected_at": datetime.now().isoformat()
            })
    return videos


def deduplicate_videos(new_videos, existing_videos):
    """video_idで重複排除"""
    existing_ids = set()
    for v in existing_videos:
        vid = v.get("video_id", "")
        if vid:
            existing_ids.add(vid)

    unique = []
    seen_ids = set()
    for v in new_videos:
        vid = v.get("video_id", "")
        if vid and vid not in existing_ids and vid not in seen_ids:
            unique.append(v)
            seen_ids.add(vid)
        elif vid:
            print(f"  重複スキップ: {v.get('title', '')[:40]}...")
    return unique


def save_videos(videos):
    """動画データをJSONに保存"""
    os.makedirs("docs", exist_ok=True)
    data_file = "docs/youtube_data.json"
    existing = []
    if os.path.exists(data_file):
        with open(data_file, "r", encoding="utf-8") as f:
            existing = json.load(f)

    unique_videos = deduplicate_videos(videos, existing)
    print(f"  新規動画: {len(unique_videos)}件 (重複除外: {len(videos) - len(unique_videos)}件)")

    existing = unique_videos + existing
    existing = existing[:100]  # 最新100件

    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"  合計: {len(existing)}件を保存")


if __name__ == "__main__":
    print("=" * 50)
    print("YouTube動画収集を開始...")
    print("=" * 50)

    if not YOUTUBE_API_KEY:
        print("エラー: YOUTUBE_API_KEY が設定されていません")
        exit(1)

    all_videos = []

    # チャンネルから収集
    print("\n[1/2] チャンネル新着動画の取得")
    all_videos.extend(collect_from_channels())

    # キーワード検索
    print("\n[2/2] キーワード検索")
    all_videos.extend(collect_from_keywords())

    print(f"\n収集完了: 合計{len(all_videos)}件")

    # 保存
    save_videos(all_videos)
    print("\n完了！")
