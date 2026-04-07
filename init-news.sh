#!/bin/bash

# Hentikan script jika salah satu perintah gagal
set -e

echo "Menjalankan stock-news-ipot"
python3 app/init/stock-news-ipot.py

echo "Menjalankan stock-news-investor-daily"
python3 app/init/stock-news-investor-daily.py

sleep 2
python3 app/init/stock-sentiment.py

echo "Semua script selesai dijalankan."
