# 1. Aksi Korporasi & Kepemilikan
corporate_actions = [
    "buy", "buyback", "stock split", "akuisisi", "merger", "tender offer", 
    "dividen", "cum date", "right issue", "private placement", 
    "investor strategis", "pengendali baru", "borong saham", 
    "menambah kepemilikan", "pembentukan JV", "joint venture", "JV", "IPO", "Right Issue", "RUPS"
]

# 2. Kinerja Keuangan (Fundamental)
fundamental_performance = [
    "laba bersih naik", "laba melonjak", "laba tumbuh", "pendapatan naik", 
    "all time high", "turnaround", "balikkan rugi", "efisiensi biaya", 
    "margin menebal", "kinerja positif", "melampaui estimasi", 
    "pertumbuhan double digit", "eps naik", "laba rekor", "ROA naik",
    "rasio utang menurun", "DER membaik",
    "ROE meningkat",
    "ROA naik",
    "kinerja kuartalan solid",
    "outlook positif",
    "guidance naik",
    "earning surprise",
    "margin laba tertinggi"
]

# 3. Ekspansi & Proyek
expansion_projects = [
    "kontrak baru", "proyek baru", "pabrik baru", "ekspansi usaha", 
    "peningkatan kapasitas", "izin operasional", "eksplorasi", 
    "penemuan cadangan", "produk baru", "kerja sama strategis", 
    "mou", "pemenang tender",
    "jangka panjang", "hilirisasi", "dana segar", "suntikan", "stimulus"
]

# 4. Sentimen Makro & Sektoral
macro_sentiments = [
    "harga komoditas naik", "suku bunga turun", "insentif pajak", 
    "naik",
    "subsidi pemerintah", "kebijakan baru", "permintaan meningkat", 
    "meningkat",
    "pemulihan",
    "pemulihan sektor", "capital inflow", "net buy asing", "masuk indeks", "asing", "rebound",
    "stimulus ekonomi", "relaksasi regulasi",
    "pelonggaran kebijakan",
    "pemangkasan suku bunga",
    "msci",
    "danantara",
    "presiden",
    "purbaya",
    "suku bunga",
    "bunga",
    "free float"
]

# 5. Kata Sifat/Katalis Pasar (Sentimen Berita)
market_catalysts = [
    "prospek cerah", "rekomendasi beli", "target harga naik", 
    "undervalued", "murah", "potensi naik", "bullish", "sentimen positif", 
    "katalis", "proyeksi optimis",
    "optimis",
    "breakout",
    "akumulasi asing",
    "melonjak",
    "volume melonjak",
    "smart money",
    "smart",
    "big",
    "masuk",
    "re-rating",
    "valuasi menarik",
    "hidden gem",
    "saham favorit",
    "top pick",
    "market darling",
    "technical rebound",
    "trend reversal",
    "trend",
    "momentum",
    "positif",
    "momentum positif"
]

# 6. Pemiliki Saham
owners = [
    "Prajogo Pangestu",
    "Low Tuck Kwong",
    "Sukanto Tanoto",
    "Budi Hartono",
    "Michael Hartono",
    "Anthoni Salim",
    "Antoni Salim",
    "Otto Toto Sugiri",
    "Otto Toto",
    "Toto Sugiri",
    "Sri Prakash Lohia",
    "Sri Prakash",
    "Marina Budiman",
    "Tahir",
    "Agoes Projosasmito",
    "Haryanto Tjiptodihardjo",
    "Wijono",
    "Hermanto Tanoko",
    "Lim Hariyanto Wijaya Sarwono",
    "Lim Hariyanto",
    "Hariyanto Wijaya",
    "Wijaya Sarwono",
    "Chairul Tanjung",
    "Dewi Kam",
    "Han Arming Hanafia",
    "Han Arming",
    "Arming Hanafia",
    "Theodore Rachmat",
    "Martua Sitorus",
    "Djoko Susanto",
    "Mochtar Riady",
    "Peter Sondakh",
    "Alexander Ramlie",
    "Bambang Sutantio",
    "Bachtiar Karim",
    "Jogi Hendra Atmadja",
    "Jogi Hendra",
    "Hendra Atmadja",
    "Susilo Wonowidjojo",
    "Keluarga Setiawan",
    "Ciliandra Fangiono",
    "Hary Tanoesoedibjo",
    "Lo Kheng Hong",
    "Bakrie",
    "Salim Group",
    "CT Corp",
    "Sinarmas Group",
    "Eka Tjipta Widjaja",
    "Agung Sedayu"
]

# Menggabungkan semua menjadi satu array besar
keywords = (
    corporate_actions + 
    fundamental_performance + 
    expansion_projects + 
    macro_sentiments + 
    market_catalysts +
    owners
)
