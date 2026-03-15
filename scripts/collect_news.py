import feedparser
import json
import os
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime
import google.generativeai as genai

# Gemini APIの設定
genai.configure(api_key=os.environ['GEMINI_API_KEY'])
model = genai.GenerativeModel('gemini-2.5-flash')

# ========================================
# RSSフィード設定（追加・削除はここで）
# ========================================
RSS_FEEDS = [
    {"name": "ITmedia", "url": "https://rss.itmedia.co.jp/rss/2.0/enterprise.xml", "count": 1},
    {"name": "GIGAZINE", "url": "https://gigazine.net/news/rss_2.0/", "count": 1},
    {"name": "TechCrunch Japan", "url": "https://jp.techcrunch.com/feed/", "count": 1},
]

# ========================================
# Zenn / Qiita / はてなブックマーク設定
# ========================================
ZENN_TOPICS = ["ai", "machinelearning", "dx", "iot", "chatgpt", "claude"]
QIITA_TAGS = ["AI", "機械学習", "DX", "生成AI", "ChatGPT", "Claude"]
HATENA_CATEGORY = "it"  # テクノロジーカテゴリ

# はてなブックマークで除外するドメイン
HATENA_BLOCKED_DOMAINS = ["nhk.or.jp", "nhk.jp"]

# Gemini API呼び出し間隔（秒）レート制限対策
API_WAIT_SECONDS = 4

# 1回の実行で作る記事の上限
MAX_ARTICLES_PER_RUN = 4

# ========================================
# カテゴリ定義
# ========================================
CATEGORIES = {
    "AI・生成AI": ["AI", "人工知能", "LLM", "GPT", "Claude", "Gemini", "生成AI", "機械学習", "深層学習", "ChatGPT", "Copilot"],
    "DX・業務改善": ["DX", "デジタルトランスフォーメーション", "業務改善", "自動化", "RPA", "ペーパーレス", "IoT"],
    "セキュリティ": ["脆弱性", "セキュリティ", "CVE", "攻撃", "マルウェア", "EDR", "認証", "暗号"],
    "クラウド・インフラ": ["AWS", "Azure", "GCP", "クラウド", "サーバー", "Kubernetes", "Docker", "6G"],
    "開発・プログラミング": ["開発", "プログラミング", "コーディング", "GitHub", "API", "フレームワーク", "OSS"],
    "ビジネス・戦略": ["経営", "戦略", "投資", "市場", "営業", "マーケティング", "導入事例"],
}


def categorize_article(title, summary):
    """タイトルと要約からカテゴリを判定"""
    text = f"{title} {summary}"
    scores = {}
    for category, keywords in CATEGORIES.items():
        score = sum(1 for kw in keywords if kw.lower() in text.lower())
        if score > 0:
            scores[category] = score
    if scores:
        return max(scores, key=scores.get)
    return "その他"


def summarize_in_japanese(title, description):
    """記事を日本語で要約する"""
    prompt = f"""以下の記事を日本語で3-4文で簡潔に要約してください。重要なポイントや数字があれば含めてください。
タイトル: {title}
内容: {description}"""
    try:
        time.sleep(API_WAIT_SECONDS)  # レート制限対策
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"要約エラー: {str(e)}"


def fetch_json(url):
    """URLからJSONを取得"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NewsCollector/2.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  取得エラー ({url}): {e}")
        return None


def collect_rss():
    """RSSフィードからニュースを収集"""
    articles = []
    for feed_info in RSS_FEEDS:
        print(f"  RSS取得中: {feed_info['name']}...")
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:feed_info["count"]]:
                title = entry.get("title", "タイトルなし")
                link = entry.get("link", "")
                description = entry.get("summary", entry.get("description", ""))
                summary = summarize_in_japanese(title, description)
                articles.append({
                    "source": feed_info["name"],
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "category": categorize_article(title, summary),
                    "content_type": "news",
                    "collected_at": datetime.now().isoformat()
                })
        except Exception as e:
            print(f"  {feed_info['name']}取得エラー: {e}")
    return articles


def collect_zenn():
    """Zennのトレンド記事を収集"""
    articles = []
    print("  Zenn取得中...")
    for topic in ZENN_TOPICS[:1]:  # 1トピックのみ
        url = f"https://zenn.dev/api/articles?topicname={topic}&order=latest&count=1"
        data = fetch_json(url)
        if not data or "articles" not in data:
            continue
        for item in data["articles"][:1]:
            title = item.get("title", "タイトルなし")
            link = f"https://zenn.dev{item.get('path', '')}"
            summary = summarize_in_japanese(title, title)
            articles.append({
                "source": "Zenn",
                "title": title,
                "link": link,
                "summary": summary,
                "category": categorize_article(title, summary),
                "content_type": "article",
                "collected_at": datetime.now().isoformat()
            })
    return articles


def collect_qiita():
    """Qiitaの最新記事を収集"""
    articles = []
    print("  Qiita取得中...")
    for tag in QIITA_TAGS[:1]:  # 1タグのみ
        encoded_tag = urllib.parse.quote(tag)
        url = f"https://qiita.com/api/v2/tags/{encoded_tag}/items?per_page=1"
        data = fetch_json(url)
        if not data:
            continue
        for item in data[:1]:
            title = item.get("title", "タイトルなし")
            link = item.get("url", "")
            body = item.get("body", "")[:500]
            summary = summarize_in_japanese(title, body)
            articles.append({
                "source": "Qiita",
                "title": title,
                "link": link,
                "summary": summary,
                "category": categorize_article(title, summary),
                "content_type": "article",
                "collected_at": datetime.now().isoformat()
            })
    return articles


def collect_hatena():
    """はてなブックマークのテクノロジー人気記事を収集"""
    articles = []
    print("  はてなブックマーク取得中...")
    url = "https://b.hatena.ne.jp/hotentry/it.rss"
    try:
        feed = feedparser.parse(url)
        count = 0
        for entry in feed.entries:
            if count >= 1:  # 1件まで
                break
            title = entry.get("title", "タイトルなし")
            link = entry.get("link", "")

            # ブロックドメインのチェック
            is_blocked = False
            for domain in HATENA_BLOCKED_DOMAINS:
                if domain in link:
                    print(f"  除外（NHK）: {title[:40]}...")
                    is_blocked = True
                    break
            if is_blocked:
                continue

            description = entry.get("summary", entry.get("description", ""))
            summary = summarize_in_japanese(title, description)
            articles.append({
                "source": "はてなブックマーク",
                "title": title,
                "link": link,
                "summary": summary,
                "category": categorize_article(title, summary),
                "content_type": "news",
                "collected_at": datetime.now().isoformat()
            })
            count += 1
    except Exception as e:
        print(f"  はてなブックマーク取得エラー: {e}")
    return articles


def deduplicate(new_articles, existing_articles):
    """タイトル一致で重複を排除"""
    existing_titles = set()
    for article in existing_articles:
        existing_titles.add(article.get("title", "").strip())

    unique = []
    seen_titles = set()
    for article in new_articles:
        title = article.get("title", "").strip()
        if title and title not in existing_titles and title not in seen_titles:
            unique.append(article)
            seen_titles.add(title)
        else:
            if title in existing_titles or title in seen_titles:
                print(f"  重複スキップ: {title[:40]}...")
    return unique


def save_articles(articles):
    """記事をJSONファイルに保存"""
    os.makedirs("docs", exist_ok=True)
    data_file = "docs/news_data.json"
    existing = []
    if os.path.exists(data_file):
        with open(data_file, "r", encoding="utf-8") as f:
            existing = json.load(f)

    # 重複排除
    unique_articles = deduplicate(articles, existing)
    print(f"  新規記事: {len(unique_articles)}件 (重複除外: {len(articles) - len(unique_articles)}件)")

    # 新しい記事を先頭に追加
    existing = unique_articles + existing

    # 最新150件のみ保持（ソース増加に対応）
    existing = existing[:150]

    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"  合計: {len(existing)}件を保存")


if __name__ == "__main__":
    print("=" * 50)
    print("ニュース収集を開始...")
    print(f"1回あたりの上限: {MAX_ARTICLES_PER_RUN}件")
    print("=" * 50)

    all_articles = []

    # RSS収集
    print("\n[1/4] RSSフィード収集")
    all_articles.extend(collect_rss())

    # Zenn収集（上限チェック）
    if len(all_articles) < MAX_ARTICLES_PER_RUN:
        print("\n[2/4] Zenn収集")
        all_articles.extend(collect_zenn())
    else:
        print("\n[2/4] Zenn収集: 上限到達のためスキップ")

    # Qiita収集（上限チェック）
    if len(all_articles) < MAX_ARTICLES_PER_RUN:
        print("\n[3/4] Qiita収集")
        all_articles.extend(collect_qiita())
    else:
        print("\n[3/4] Qiita収集: 上限到達のためスキップ")

    # はてなブックマーク収集（上限チェック）
    if len(all_articles) < MAX_ARTICLES_PER_RUN:
        print("\n[4/4] はてなブックマーク収集")
        all_articles.extend(collect_hatena())
    else:
        print("\n[4/4] はてなブックマーク収集: 上限到達のためスキップ")

    # 上限でカット
    all_articles = all_articles[:MAX_ARTICLES_PER_RUN]

    print(f"\n収集完了: 合計{len(all_articles)}件")

    # 保存
    save_articles(all_articles)
    print("\n完了！")
