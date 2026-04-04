import requests
from bs4 import BeautifulSoup
import time
import sys
import os
from config import keywords
from datetime import datetime
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from connection.mongodb import db_provider

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}


def clean_and_convert_date(date_str):
    """
    Input : '13 Jan 2026 | 14:30 WIB'
    Output: datetime object
    """
    clean_str = date_str.replace("WIB", "").replace("|", "").strip()
    clean_str = re.sub(r"\s+", " ", clean_str)
    dt_object = datetime.strptime(clean_str, "%d %b %Y %H:%M")
    return dt_object

def get_soup(url):
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")

def scrape_dynamic_news(url):
    db = db_provider.get_database()
    collection = db["stock_news"]
    collection.create_index([("id", 1), ("symbol", 1)], unique=True)

    try:
        soup = get_soup(url)
    except Exception as e:
        print(f"Gagal request halaman daftar: {e}")

    main = soup.find("main")
    if not main:
        print("Tag <main> tidak ditemukan")
        return

    links_pages = soup.select(".pagination > li > a")
    pages = []

    for link in links_pages:
        href = link.get("href")
        if href:
            if href.startswith("/"):
                href = "https://investor.id" + href
            pages.append(href)

    pages = list(dict.fromkeys(pages))
    print(f"====================== Ditemukan {len(pages)} pages. ======================")
    
    for page in pages:
        container = soup.select_one(".id-grid.mx-auto.mt-4")
        if not container:
            print("Container berita tidak ditemukan")
            continue

        links_elements = container.select(".row.mb-4.position-relative > div > a.stretched-link")
        urls = []

        for link in links_elements:
            href = link.get("href")
            if href:
                if href.startswith("/"):
                    href = "https://investor.id" + href
                urls.append(href)
        print(f"Ditemukan {len(urls)} links.")
        time.sleep(1)

        for news_url in urls:
            print(f"\n--- Mengakses: {news_url} ---")
            try:
                news_soup = get_soup(news_url)
            except Exception as e:
                print(f"Gagal request detail berita: {e}")
                continue
            contents = news_soup.select(".col.fsbody2.body-content")
            for item in contents:
                try:
                    date_tag = news_soup.select_one(".row.my-3 > .col.small.pt-1 > .text-muted")
                    if date_tag:
                        date = date_tag.get_text(strip=True)
                    else:
                        date = None
                    p_tags = item.find_all("p")
                    if not p_tags:
                        print("Tidak ada tag <p>")
                        continue
                    paragraphs = [
                        p.get_text(strip=True)
                        for p in p_tags
                        if p.get_text(strip=True)
                    ]
                    full_article = " ".join(paragraphs)
                    content_lower = full_article.lower()
                    matched_keywords = [
                        k for k in keywords if k.lower() in content_lower
                    ]
                    if matched_keywords:
                        try:
                            parsed_date = clean_and_convert_date(date).strftime("%Y-%m-%d %H:%M")
                        except Exception as e:
                            print(e)
                            parsed_date = None
                        id = f"investor-daily-{parsed_date}"
                        data = {
                            "id": id,
                            "date": parsed_date,
                            "article": full_article,
                            "scraped_at": datetime.now(),
                            "url": news_url,
                            "keywords": matched_keywords,
                            "from": "investor-daily"
                        }
                        try:
                            collection.update_one(
                                {"id": id},
                                {"$setOnInsert": data},
                                upsert=True
                            )
                            print(f"Berhasil memproses id: {id}")
                        except Exception as e:
                            print(f"Gagal simpan ke MongoDB: {e}")

                except Exception as e:
                    print(f"Gagal mengambil elemen detail: {e}")

target_url = "https://investor.id/stock/indeks"
scrape_dynamic_news(target_url)