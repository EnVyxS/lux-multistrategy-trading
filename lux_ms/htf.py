"""Konteks HTF (4H / 1H / 15m) dan gerbang `trendline_min_htf_score`.

Port dari legacy `bot_v8`:
  - `HTFAnalyzer.detect_bias`            strategy.py:190-242
  - `HTFAnalyzer.detect_choch_and_swings` strategy.py:245-305
  - `HTFAnalyzer.compute_score`          strategy.py:308-359
  - pemanggil `_refresh_htf_context`     engine.py:312-396
  - gerbang `htf_score < settings.trendline_min_htf_score` engine.py:1601
    dengan `config.py:517 trendline_min_htf_score = 3`
  - tolak keras `htf_score == -1`        engine.py:1526 dan engine.py:1248

STATUS ANGKA: modul ini adalah ALAT, bukan hasil. Tidak ada satu pun angka
hasil di sini. Sebelum dijalankan di Actions atas byte rilis yang sidiknya
lulus, seluruh angka keluarannya BELUM DIUKUR.

DUA PENYIMPANGAN DARI LEGACY, DICATAT BUKAN DIRAPIKAN:

1. `PENDEKATAN_B0_HTF_SEGAR`. Legacy menyegarkan HTF tiap `htf_refresh_sec`
   (bawaan 300 detik; 90 detik bila ada pending setup), jadi bias yang dipakai
   legacy bisa BASI sampai lima menit. B0 memakai bar HTF tertutup TERBARU pada
   waktu keputusan. Akibatnya konteks B0 lebih segar daripada legacy, dan
   keputusan bisa berbeda pada bar-bar di sekitar tutupnya bar HTF. Arah bias
   tidak dapat ditentukan tanpa pengukuran; jangan diklaim.

2. Legacy meminta `limit=60` (4H), `60` (1H), `80` (15m) lalu MEMBUANG candle
   yang masih berjalan, sehingga yang dianalisis 59 / 59 / 79 bar tertutup.
   Angka itu ditiru persis di sini lewat CACAH_TERTUTUP_*, bukan dibulatkan
   ke 60/60/80.

BEBAS LOOK-AHEAD: bar HTF hanya boleh dipakai setelah tertutup. Gerbangnya
`resample.indeks_bar_terpakai`, dan `resample.audit_look_ahead` dipakai di uji.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .resample import indeks_bar_terpakai, resample_tertutup

LABEL_HTF = "PENDEKATAN_B0_HTF_SEGAR"

# config.py:517
TRENDLINE_MIN_HTF_SCORE = 3
# engine.py:1526 / 1248
SKOR_TOLAK_KERAS = -1

# settings.htf_swing_len bawaan 3 (engine.py:335)
HTF_SWING_LEN = 3

# engine.py:336-338 meminta 60/60/80 lalu membuang candle berjalan.
CACAH_TERTUTUP_4H = 59
CACAH_TERTUTUP_1H = 59
CACAH_TERTUTUP_15M = 79

TF_MENIT_4H = 240
TF_MENIT_1H = 60
TF_MENIT_15M = 15

# strategy.py:299 — CHoCH dianggap relevan bila terbentuk di 25 bar terakhir.
UMUR_CHOCH_MAKS = 25

NETRAL = "NEUTRAL"
BULL = "BULL"
BEAR = "BEAR"


def deteksi_bias(ohlcv, swing_len: int = HTF_SWING_LEN) -> str:
    """Port verbatim `HTFAnalyzer.detect_bias` (strategy.py:190).

    Dua pass disengaja di legacy: pass 1 mengumpulkan pivot (butuh jendela
    kiri+kanan), pass 2 memeriksa BOS di SEMUA bar termasuk bar terbaru.
    Tanpa pass terpisah, bar terakhir tidak pernah diperiksa.
    """
    if len(ohlcv) < swing_len * 2 + 3:
        return NETRAL

    highs = [c[2] for c in ohlcv]
    lows = [c[3] for c in ohlcv]
    closes = [c[4] for c in ohlcv]
    n = len(ohlcv)

    ph_at: List[Tuple[int, float]] = []
    pl_at: List[Tuple[int, float]] = []
    for i in range(swing_len, n - swing_len):
        if highs[i] == max(highs[i - swing_len : i + swing_len + 1]):
            ph_at.append((i, highs[i]))
        if lows[i] == min(lows[i - swing_len : i + swing_len + 1]):
            pl_at.append((i, lows[i]))

    if not ph_at and not pl_at:
        return NETRAL

    bias = NETRAL
    ph_ptr = 0
    pl_ptr = 0
    last_ph: Optional[float] = None
    last_pl: Optional[float] = None

    for i in range(n):
        while ph_ptr < len(ph_at) and ph_at[ph_ptr][0] <= i:
            last_ph = ph_at[ph_ptr][1]
            ph_ptr += 1
        while pl_ptr < len(pl_at) and pl_at[pl_ptr][0] <= i:
            last_pl = pl_at[pl_ptr][1]
            pl_ptr += 1
        if last_ph is not None and closes[i] > last_ph:
            bias = BULL
        if last_pl is not None and closes[i] < last_pl:
            bias = BEAR

    return bias


def deteksi_choch_dan_swing(ohlcv, swing_len: int = HTF_SWING_LEN):
    """Port verbatim `HTFAnalyzer.detect_choch_and_swings` (strategy.py:245).

    Return (choch, swing_high, swing_low). CHoCH dibuang bila terbentuk lebih
    dari UMUR_CHOCH_MAKS bar lalu.
    """
    if len(ohlcv) < swing_len * 2 + 3:
        return None, None, None

    highs = [c[2] for c in ohlcv]
    lows = [c[3] for c in ohlcv]
    closes = [c[4] for c in ohlcv]
    n = len(ohlcv)

    ph_at: List[Tuple[int, float]] = []
    pl_at: List[Tuple[int, float]] = []
    for i in range(swing_len, n - swing_len):
        if highs[i] == max(highs[i - swing_len : i + swing_len + 1]):
            ph_at.append((i, highs[i]))
        if lows[i] == min(lows[i - swing_len : i + swing_len + 1]):
            pl_at.append((i, lows[i]))

    prev_bias = NETRAL
    choch: Optional[str] = None
    choch_idx = -1
    last_ph: Optional[float] = None
    last_pl: Optional[float] = None
    ph_ptr = pl_ptr = 0

    for i in range(n):
        while ph_ptr < len(ph_at) and ph_at[ph_ptr][0] <= i:
            last_ph = ph_at[ph_ptr][1]
            ph_ptr += 1
        while pl_ptr < len(pl_at) and pl_at[pl_ptr][0] <= i:
            last_pl = pl_at[pl_ptr][1]
            pl_ptr += 1
        if last_ph is not None and closes[i] > last_ph:
            if prev_bias == BEAR:
                choch = BULL
                choch_idx = i
            prev_bias = BULL
        if last_pl is not None and closes[i] < last_pl:
            if prev_bias == BULL:
                choch = BEAR
                choch_idx = i
            prev_bias = BEAR

    if choch is not None and choch_idx < n - UMUR_CHOCH_MAKS:
        choch = None

    swing_high = ph_at[-1][1] if ph_at else None
    swing_low = pl_at[-1][1] if pl_at else None

    return choch, swing_high, swing_low


def hitung_skor(bias_4h: str, bias_1h: str, choch_15m: Optional[str], arah: str):
    """Port verbatim `HTFAnalyzer.compute_score` (strategy.py:308).

    Tabel skor legacy:
      -1 : TOLAK KERAS, 4H berlawanan (satu-satunya pemblokir)
      base 1 : 4H searah atau NEUTRAL
      +1 : 1H searah
      +1 : 4H tegas (bukan NEUTRAL)
      maksimum 3

    CHoCH 15m TIDAK memblokir; hanya catatan. Itu keputusan legacy yang
    disengaja ("CHoCH adalah AKIBAT, bukan sinyal"), jadi tidak diubah di sini.
    """
    if arah not in ("LONG", "SHORT"):
        raise ValueError(f"arah tidak sah: {arah!r}")

    if (arah == "LONG" and bias_4h == BEAR) or (arah == "SHORT" and bias_4h == BULL):
        return SKOR_TOLAK_KERAS, f"4H {bias_4h} berlawanan {arah}"

    skor = 1
    if (arah == "LONG" and bias_1h == BULL) or (arah == "SHORT" and bias_1h == BEAR):
        skor += 1
    if bias_4h != NETRAL:
        skor += 1

    if choch_15m is None:
        catatan = "noCHoCH(ok)"
    elif (arah == "LONG" and choch_15m == BULL) or (arah == "SHORT" and choch_15m == BEAR):
        catatan = "CHoCH15m-searah"
    else:
        catatan = f"CHoCH15m-berlawanan({choch_15m})"

    return skor, catatan


@dataclass
class PraHTF:
    """Hasil resample sekali jalan untuk satu simbol. Dibangun sekali, dipakai
    di setiap bar keputusan; tidak ada resample per bar."""

    tf: Dict[int, dict] = field(default_factory=dict)
    dibuang_tak_lengkap: Dict[int, int] = field(default_factory=dict)


def bangun_pra_htf(ts_ms, o, h, l, c, v) -> PraHTF:
    """Resample 1m -> 15m / 1H / 4H sekali. Bucket bolong DIBUANG oleh
    `resample_tertutup`, tidak ditambal, dan cacah buangannya disimpan supaya
    bisa dilaporkan sebagai keterangan hasil."""
    pra = PraHTF()
    for tf in (TF_MENIT_15M, TF_MENIT_1H, TF_MENIT_4H):
        r = resample_tertutup(ts_ms, o, h, l, c, v, tf)
        pra.tf[tf] = r
        pra.dibuang_tak_lengkap[tf] = int(r["dibuang_tak_lengkap"])
    return pra


def _baris_htf(r: dict, idx_akhir: int, cacah: int):
    """Ambil `cacah` bar tertutup terakhir sampai idx_akhir (inklusif), dalam
    bentuk baris legacy [ts, o, h, l, c, v]."""
    if idx_akhir < 0:
        return []
    awal = max(0, idx_akhir - cacah + 1)
    ts = r["ts"]
    return [
        [int(ts[i]), float(r["o"][i]), float(r["h"][i]), float(r["l"][i]), float(r["c"][i]), float(r["v"][i])]
        for i in range(awal, idx_akhir + 1)
    ]


@dataclass
class KonteksHTF:
    bias_4h: str = NETRAL
    bias_1h: str = NETRAL
    choch_15m: Optional[str] = None
    swing_high_15m: Optional[float] = None
    swing_low_15m: Optional[float] = None
    idx_4h: int = -1
    idx_1h: int = -1
    idx_15m: int = -1
    cacah_bar_4h: int = 0
    cacah_bar_1h: int = 0
    cacah_bar_15m: int = 0
    label: str = LABEL_HTF

    @property
    def htf_siap(self) -> bool:
        """Cukup bar untuk menghitung bias 4H DAN 1H. Bila False, bias yang
        dipakai adalah NEUTRAL bawaan legacy, bukan tebakan."""
        batas = HTF_SWING_LEN * 2 + 3
        return self.cacah_bar_4h >= batas and self.cacah_bar_1h >= batas


def konteks_pada(pra: PraHTF, waktu_keputusan_ms: int, swing_len: int = HTF_SWING_LEN) -> KonteksHTF:
    """Bangun konteks HTF yang SAH pada satu waktu keputusan.

    Hanya bar yang sudah TUTUP pada waktu_keputusan_ms dipakai
    (`indeks_bar_terpakai`, batas <=). Bila belum ada bar tertutup, bias tetap
    NEUTRAL — itu perilaku bawaan legacy (HTFBias field default), bukan tebakan.
    """
    r4 = pra.tf[TF_MENIT_4H]
    r1 = pra.tf[TF_MENIT_1H]
    r15 = pra.tf[TF_MENIT_15M]

    i4 = indeks_bar_terpakai(r4["tersedia_pada"], waktu_keputusan_ms)
    i1 = indeks_bar_terpakai(r1["tersedia_pada"], waktu_keputusan_ms)
    i15 = indeks_bar_terpakai(r15["tersedia_pada"], waktu_keputusan_ms)

    b4 = _baris_htf(r4, i4, CACAH_TERTUTUP_4H)
    b1 = _baris_htf(r1, i1, CACAH_TERTUTUP_1H)
    b15 = _baris_htf(r15, i15, CACAH_TERTUTUP_15M)

    choch, sh, sl = deteksi_choch_dan_swing(b15, swing_len) if b15 else (None, None, None)

    return KonteksHTF(
        bias_4h=deteksi_bias(b4, swing_len) if b4 else NETRAL,
        bias_1h=deteksi_bias(b1, swing_len) if b1 else NETRAL,
        choch_15m=choch,
        swing_high_15m=sh,
        swing_low_15m=sl,
        idx_4h=i4,
        idx_1h=i1,
        idx_15m=i15,
        cacah_bar_4h=len(b4),
        cacah_bar_1h=len(b1),
        cacah_bar_15m=len(b15),
    )


def gerbang_trendline(
    konteks: KonteksHTF,
    arah: str,
    min_htf_score: int = TRENDLINE_MIN_HTF_SCORE,
):
    """Gerbang legacy untuk setup trendline break.

    Urutan legacy dipertahankan:
      1. engine.py:1526 -> skor == -1 : TOLAK KERAS (4H berlawanan)
      2. engine.py:1601 -> skor < settings.trendline_min_htf_score : SKIP TB

    Return dict: {skor, catatan, lulus, sebab}. `sebab` = None bila lulus.
    """
    skor, catatan = hitung_skor(konteks.bias_4h, konteks.bias_1h, konteks.choch_15m, arah)
    if skor == SKOR_TOLAK_KERAS:
        return {"skor": skor, "catatan": catatan, "lulus": False, "sebab": "htf_tolak_keras_4h"}
    if skor < min_htf_score:
        return {
            "skor": skor,
            "catatan": catatan,
            "lulus": False,
            "sebab": "htf_score_di_bawah_min_tb",
        }
    return {"skor": skor, "catatan": catatan, "lulus": True, "sebab": None}
