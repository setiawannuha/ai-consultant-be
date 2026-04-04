from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import sys
import os
from config import keywords
from datetime import datetime
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from connection.mongodb import db_provider

chrome_options = Options()
chrome_options.add_argument("--headless")
driver = webdriver.Chrome(options=chrome_options)

def clean_and_convert_date(date_str):
    clean_str = date_str.replace("WIB", "").strip()
    clean_str = re.sub(r'\s+', ' ', clean_str)
    dt_object = datetime.strptime(clean_str, "%A, %B %d, %Y %H:%M")
    return dt_object

def scrape_dynamic_news(url):
    try:
        db = db_provider.get_database()
        collection = db["stock_news"]
        collection.create_index([("id", 1), ("symbol", 1)], unique=True)

        driver.get(url)
        
        # Tunggu sampai elemen .news-stock-content-data muncul (maksimal 10 detik)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "news-stock-content-data")))

        links_pages = driver.find_elements(By.CSS_SELECTOR, ".pagination > ul > li > a")
        pages = [link.get_attribute('href') for link in links_pages]
        print(f"Ditemukan {len(pages)} pages.")

        for page in pages:
            print(f"\n========= Mengakses Halaman Daftar: {page} =========")
            driver.get(page)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".news-stock-content-data")))

            time.sleep(2)
            links_elements = driver.find_elements(By.CSS_SELECTOR, ".news-stock-content-data > div > dl > dt > a")
            urls = [link.get_attribute('href') for link in links_elements]
            print(f"Ditemukan {len(urls)} pages.")

            for news_url in urls:
                print(f"\n--- Mengakses: {news_url} ---")
                driver.get(news_url)
                try:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".newsContent")))
                    contents = driver.find_elements(By.CSS_SELECTOR, ".newsContent div .listNews")
                    print(f"Ditemukan {len(contents)} contents.")

                    for item in contents:
                        try:
                            try:
                                date = item.find_element(By.TAG_NAME, "small").text
                            except:
                                date = "Tidak ada info small"
                            try:
                                article_content = item.find_element(By.TAG_NAME, "article").text
                            except:
                                article_content = "Tidak ada info article"

                            content_lower = article_content.lower()
                            matched_keywords = [k for k in keywords if k.lower() in content_lower]

                            if matched_keywords:
                                id = f"indopremier-{date}"
                                data = {
                                    "id": id,
                                    "date": clean_and_convert_date(date).strftime("%Y-%m-%d %H:%M"),
                                    "article": article_content,
                                    "scraped_at": datetime.now(),
                                    "url": news_url,
                                    "keywords": matched_keywords,
                                    "from": "indopremier"
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

                except Exception as e:
                    print(f"Gagal mengambil konten di halaman ini: {e}")

            print(f"\n========= Selesai Mengakses Halaman Daftar: {page} =========")
    finally:
        driver.quit()

target_url = "https://ipotnews.com/ipotnews/nw-saham.php?level4=stocks"
scrape_dynamic_news(target_url)