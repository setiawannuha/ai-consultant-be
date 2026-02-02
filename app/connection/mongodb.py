import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

# Load variabel dari .env
load_dotenv()

class MongoDB:
    def __init__(self):
        self.uri = os.getenv("MONGODB_URI")
        self.db_name = os.getenv("DB_NAME", "default_db")
        self.client = None
        self.db = None

    def get_database(self):
        """Fungsi untuk mengembalikan objek database."""
        if self.db is None:
            try:
                # Membuat koneksi baru jika belum ada
                self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
                # Cek apakah koneksi berhasil
                self.client.admin.command('ping')
                self.db = self.client[self.db_name]
                print(f"✅ Terhubung ke MongoDB: {self.db_name}")
            except ConnectionFailure:
                print("❌ Gagal terhubung ke MongoDB. Periksa URI Anda!")
                raise
        return self.db

    def close_connection(self):
        """Menutup koneksi jika diperlukan."""
        if self.client:
            self.client.close()
            print("🔌 Koneksi MongoDB ditutup.")

# Inisialisasi instance agar bisa di-import langsung
db_provider = MongoDB()