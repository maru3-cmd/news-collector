import feedparser
import json
import os
from datetime import datetime
import google.generativeai as genai

# Gemini APIの設定
genai.configure(api_key=os.environ['GEMINI_API_KEY'])
model = genai.GenerativeModel('gemini-3.0-flash')

# 取得するRSSフィード
RSS_FEEDS = [
    {"name": "ITmedia", "url": "https://rss.itmedia.co.jp/rss/2.0/enterprise.xml"},
    {"name": "TechCrunch Japan", "url": "https://jp.techcrunch.com/feed/"},
]

def summarize_in_japanese(title, description):
    """記事を日本語で要約する"""
    prompt = f"""
以下の記事を日本語で2-3文で要約してください。
タイトル: {title}
内容: {description}
"""
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"要約エラー: {str(e)}"

def collect_news():
    """ニュースを収集して要約する"""
    articles = []
    
    for feed_info in RSS_FEEDS:
        feed = feedparser.parse(feed_info["url"])
        
        # 各フィードから最新2件を取得
        for entry in feed.entries[:2]:
            title = entry.get("title", "タイトルなし")
            link = entry.get("link", "")
            description = entry.get("summary", entry.get("description", ""))
            
            # 要約を生成
            summary = summarize_in_japanese(title, description)
            
            articles.append({
                "source": feed_info["name"],
                "title": title,
                "link": link,
                "summary": summary,
                "collected_at": datetime.now().isoformat()
            })
    
    return articles

def save_articles(articles):
    """記事をJSONファイルに保存"""
    # docsフォルダがなければ作成
    os.makedirs("docs", exist_ok=True)
    
    # 既存のデータを読み込む
    data_file = "docs/news_data.json"
    existing = []
    if os.path.exists(data_file):
        with open(data_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
    
    # 新しい記事を追加
    existing = articles + existing
    
    # 最新100件のみ保持
    existing = existing[:100]
    
    # 保存
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    
    print(f"{len(articles)}件の記事を保存しました")

if __name__ == "__main__":
    print("ニュース収集を開始...")
    articles = collect_news()
    save_articles(articles)
    print("完了！")
