import os
import redis
from dotenv import load_dotenv

# Load variabel dari .env
load_dotenv()

class RedisDB:
    def __init__(self):
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", 6379))
        self.password = os.getenv("REDIS_PASSWORD", None)
        self.db_index = int(os.getenv("REDIS_DB", 0))
        self._client = None

    def get_client(self):
        """Fungsi untuk mengembalikan objek client Redis."""
        if self._client is None:
            try:
                # Membuat koneksi baru
                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    password=self.password,
                    db=self.db_index,
                    decode_responses=True # Otomatis decode bytes ke string
                )
                
                # Cek apakah koneksi berhasil (Ping)
                if self._client.ping():
                    print(f"✅ Terhubung ke Redis: {self.host}:{self.port} (DB: {self.db_index})")
                
            except redis.ConnectionError as e:
                print(f"❌ Gagal terhubung ke Redis: {e}")
                self._client = None
                raise
        return self._client

    def close_connection(self):
        """Menutup koneksi Redis."""
        if self._client:
            self._client.close()
            print("🔌 Koneksi Redis ditutup.")

# Inisialisasi instance agar bisa di-import langsung
redis_provider = RedisDB()