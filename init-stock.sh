#!/bin/bash

# Hentikan script jika salah satu perintah gagal
set -e

echo "Menjalankan stock-history.py..."
python3 app/init/stock-history.py

echo "Menjalankan stock-fundamental.py..."
python3 app/init/stock-fundamental.py

echo "Semua script selesai dijalankan."
