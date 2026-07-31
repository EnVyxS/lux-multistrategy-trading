# Penyesuaian `backtest.py` legacy dan status utang B0

Pra-terbang: penyebut simbol **787** (`perpetual_usdt`) - **B-1** gerbang penyebut
ENAM klausa dengan dasar keputusan LIMA: TERBUKA - **B-5** dua penyebut simbol
787 & 937: TERBUKA.

Patokan: `EnVyxS/lux-multistrategy-trading`. Semua repo lain (termasuk
`lux-ai-research` dan zip legacy) adalah REFERENSI atau SUMBER BYTE, bukan
patokan. Angka yang diwarisi dari sana tetap berstatus DIWARISI sampai diukur
ulang di repo ini.

## 1. Perubahan hukum dari operator (Pesan 4 dan 5)

1. Larangan memakai `backtest.py` legacy sebagai alat ukur **DICABUT**, dengan
   syarat "ada beberapa hal yang perlu disesuaikan". Penyesuaian itu tidak boleh
   ditafsirkan longgar; daftar cacat terukur di bagian 3 adalah syarat minimum.
2. `backup_data_ml` **tidak dipakai**.
3. `ApexPredatorMarket`, `ApexPredatorMarket_Retail`, `trade_god` dinyatakan
   publik oleh operator. **BELUM DIUKUR** di sesi ini (visibilitas belum
   ditanyakan ulang lewat API setelah pernyataan itu).
4. Bila operator menulis "lanjut" / "lanjutkan" / "continue", agen memilih sesuai
   rekomendasinya sendiri tanpa bertanya lagi.

## 2. Keputusan B0 (dipilih di bawah aturan 5 di atas)

**B0 = reimplementasi jalur keputusan `engine.py` di atas harness Fase 1;
`backtest.py` legacy dipakai sebagai PEMBANDING SILANG, bukan alat ukur utama.**

Alasan terukur, bukan selera: `backtest.py` (1009 baris, sha256-16
`ecfa51177cdc4a70`) tidak menghitung MFE/MAE sama sekali, sedangkan M-3A
SELURUHNYA bertumpu pada MFE. Memakainya sebagai alat ukur utama membuat M-3A
tidak terukur menurut definisi.

Pembanding silang tetap berguna: bila B0 dan `backtest.py` berselisih pada trade
yang sama, selisih itu WAJIB dijelaskan, bukan dirata-ratakan.

## 3. Cacat terukur `backtest.py` yang wajib disesuaikan sebelum dipakai

| # | Cacat | Bukti | Penyesuaian wajib |
|---|---|---|---|
| 1 | Biaya masuk sebagai R rata | `backtest.py:134` `fee_r: float = 0.0` | biaya dihitung dari fee taker/maker dan slippage atas harga, lalu dibagi jarak SL |
| 2 | R bersih = R kotor - biaya rata | `backtest.py:426` `return {"reason": reason, "r": realized - fee_r, "bars": bars}` | pisahkan `r_kotor`, `biaya_fee_r`, `biaya_funding_r`, `r_bersih` |
| 3 | MFE/MAE tidak ada | seluruh berkas: nol kemunculan | wajib MFE dalam R, fraksi jarak TP1, bar ke puncak MFE, puncak->tutup |
| 4 | Funding tidak ada | nol kemunculan | tiga stempel UTC 00/08/16, mode sinyal = nol funding |
| 5 | Kebijakan intrabar tak terverifikasi | tidak ada uji urutan SL/TP dalam satu bar | ambiguitas WAJIB pesimistis, dan cacah bar ambigu WAJIB dilaporkan |
| 6 | Tanpa purge/embargo/walk-forward | tidak ada pembagian waktu | `lux_ms.pembagian` (5 lipatan, embargo 1 hari, purge tumpang tindih) |

Keenam penyesuaian itu sudah tersedia di `lux_ms/eksekusi.py`, `lux_ms/kelas.py`,
dan `lux_ms/pembagian.py`. Karena itu, memakai `backtest.py` apa adanya tetap
DILARANG; yang diizinkan adalah `backtest.py` yang sudah disesuaikan, atau
`backtest.py` sebagai pembanding pada besaran yang memang ia hitung (sebab
keluar dan R harga), bukan pada MFE.

## 4. Apa yang B0 port, dan apa yang tidak

Diport verbatim: `pivots_from_ohlcv` (patterns.py:38), `_atr_from_ohlcv` (52),
`linfit` (147), `project` (164), `avg_volume` (169), `volume_expansion` (179),
`decisive_close_beyond` (192), `strong_displacement` (201), `confirm_breakout`
(210), `detect_trendline` (241), `detect_trendline_break` (265),
`find_tp_levels` (strategy.py:945), gerbang `rr1 < _min_rr_eff` (engine.py:1997),
masking `is_split and enable_partial_tp` (engine.py:2006 dengan
`config.py:294 enable_partial_tp=False`, jadi TP selalu tunggal).

BELUM diport, dan itu mengubah tafsir setiap angka B0:

- gerbang `trendline_min_htf_score = 3` (engine.py:1601, config.py:517) DILEWATI
  dan dicacah sebagai `gerbang_htf_score_belum_diport`. Akibatnya cacah setup B0
  adalah **BATAS ATAS**, bukan cacah legacy.
- SL legacy berasal dari tepi zona order block; OB belum diport. B0 memakai
  `sl_pendekatan_pivot` berlabel **`PENDEKATAN_B0`**. Itu BUKAN SL legacy, dan
  label itu ikut di setiap keluaran.
- Tier TP EQH/EQL dan OB belum ada. Karena kandidat lebih sedikit, `rr1` B0
  cenderung LEBIH BESAR daripada legacy. Arah bias dicatat, tidak dikoreksi
  diam-diam.
- `btc_correlation_block` (1626), loss breaker, blacklist pair,
  `risk.size_position` (risk.py:291): tidak diport.

`min_rr`, `min_gap_r`, `fallback_rr` sengaja tanpa nilai bawaan
(`ParamB0.wajib_terisi` melempar `ValueError`). Nilai legacy per-strategi
(`_min_rr_eff`, `settings.min_tp_gap_r`, `_fallback_rr`) **BELUM DIUKUR**.

## 5. Alur pengukuran dan gerbang byte

`.github/workflows/baseline_b0.yml` + `ukur_b0.py`: satu pecahan per jalan, dua
saksi sidik wajib lulus sebelum satu angka pun ditulis, yaitu `sha256sum -c
SHA256SUMS` (GNU) dan `lux_ms.dataset.gerbang_sidik` (sidik yang diukur sesi
ini). Sidik tak dikenal SELALU gagal; tidak ada jalur "anggap benar".

Cacat alur yang sudah ditemukan dan diperbaiki: pola aset rilis yang TERUKUR
adalah `pecahan_<i>.partNN.tar`, bukan `serapan_pecahan_*`. Pola salah membuat
unduhan hanya mengambil `SHA256SUMS` dan job tampak sehat. Karena itu ditambah
gerbang cacah tar: nol tar = job GAGAL.

Bila `lux-ai-research` privat, `GITHUB_TOKEN` bawaan tidak cukup dan job GAGAL
dengan pesan eksplisit; sediakan secret `LINTAS_REPO_TOKEN`.

## 6. Utang yang tetap terbuka

- Seluruh angka hasil B0: **BELUM DIUKUR**. Kelulusan uji sandbox membuktikan
  kontrak, bukan hasil.
- Byte parquet: **BELUM DIUKUR** (`sha256sum -c` hanya bisa di Actions).
- Cacah baris, cacah simbol per pecahan, skema 11 kolom pada byte nyata: BELUM
  DIUKUR (skema baru TERUKUR-DARI-KODE, `klines.py` SHA `cc4d9287`).
- Bacaan CI ke-**85** belum ada. Nilai basi DITOLAK: run `30628719235`, commit
  `95021cda`, blob `fedd1e89...`.
- Konflik cacah berkas alur kerja `lux-ai-research`: tugas menyebut 46, terukur
  **51**. Menunggu adjudikasi.
- Cacah baris `.py` legacy: terukur **25.646**, tugas menyebut ~25.811.
- Klaim `enable_hs` TERBALIK (`config.py:504` bawaan `True`).
- Tiga belas utang DITUTUP PAKSA tetap TIDAK dikurangkan dari cacah utang.
- KOREKSI 22 (indeks pecahan 0..7, bukan 1..8) tercatat; kesimpulan lama
  "pecahan 8 tidak ada maka dataset tidak lengkap" DIBATALKAN.
