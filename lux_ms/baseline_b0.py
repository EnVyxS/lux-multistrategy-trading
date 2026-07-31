"""BASELINE B0 — port jalur keputusan legacy ke repo patokan.

Keputusan: reimplementasi jalur `engine.py` di atas harness Fase 1, dengan
`backtest.py` legacy hanya sebagai PEMBANDING SILANG, bukan alat ukur utama.
Alasan terukur: `backtest.py` (1009 baris, sha256-16 ecfa51177cdc4a70) tidak
menghitung MFE/MAE sama sekali (baris 134 `fee_r: float = 0.0`, baris 426
`"r": realized - fee_r`), sedangkan M-3A SELURUHNYA bertumpu pada MFE.

APA YANG BENAR-BENAR DIPORT (verbatim dari byte legacy, sudah dibaca)
---------------------------------------------------------------------
dari `patterns.py` (727 baris):
  - `pivots_from_ohlcv` (38)      -> `pivot_dari_ohlcv`
  - `_atr_from_ohlcv` (52)        -> `atr_dari_ohlcv`
  - `linfit` (147), `project` (164)
  - `avg_volume` (169), `volume_expansion` (179)
  - `decisive_close_beyond` (192), `strong_displacement` (201)
  - `confirm_breakout` (210)
  - `detect_trendline` (241), `detect_trendline_break` (265)
dari `strategy.py`:
  - `find_tp_levels` (945) -> `cari_level_tp`, termasuk urutan tier, pengurutan
    kandidat menurut jarak, TP2 = kandidat TERJAUH yang >= gap_r di luar TP1,
    `is_split = tp2 > 0.0`, dan pembulatan `round(rr, 2)`.
dari `engine.py`:
  - gerbang `rr1 < _min_rr_eff` (1997)
  - `is_split and settings.enable_partial_tp` (2006) dengan
    `enable_partial_tp = False` terukur di `config.py:294` -> B0 SELALU TP tunggal.

APA YANG BELUM DIPORT (jangan dibaca sebagai "tidak ada")
---------------------------------------------------------
  - EQH/EQL, order block, FVG/IFVG, regime, dan sepuluh detektor pola lain
    (`_first_pattern_ctx` def 1125). B0 hanya memakai TRENDLINE_BREAK, yaitu
    detektor PERTAMA pada urutan legacy (`strategy.py:1135`).
  - gerbang `trendline_min_htf_score = 3` (`engine.py:1601`, `config.py:517`):
    skor HTF belum diport, jadi gerbang ini DILEWATI dan dicacah terpisah
    sebagai `gerbang_htf_score_belum_diport`. Cacah setup yang lolos B0 karena
    itu adalah BATAS ATAS, bukan cacah legacy.
  - `btc_correlation_block` (1626), loss breaker, blacklist pair, saldo/sizing
    (`risk.size_position` 291): tidak relevan untuk R per trade, dan tidak
    diport supaya tidak ada angka yang diselundupkan.
  - penempatan SL legacy berasal dari TEPI ZONA OB; OB belum diport. B0 memakai
    `sl_pendekatan_pivot`, DIBERI LABEL `PENDEKATAN_B0` di setiap keluaran.
    Itu BUKAN port dan tidak boleh disebut "SL legacy".

PARAMETER YANG SENGAJA TANPA NILAI BAWAAN
-----------------------------------------
`min_rr`, `min_gap_r`, `fallback_rr` WAJIB diisi pemanggil. Nilai per-strategi
legacy (`_min_rr_eff`, `settings.min_tp_gap_r`, `_fallback_rr`) BELUM DIUKUR di
sesi ini, dan menebaknya akan menyulam angka.

STATUS ANGKA: seluruh keluaran modul ini BELUM DIUKUR sampai dijalankan di
GitHub Actions atas parquet nyata. Kelulusan uji di sandbox membuktikan
KONTRAK, bukan hasil.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .eksekusi import Biaya, HasilTrade, Rencana, simulasi_trade

LABEL_SL = "PENDEKATAN_B0"
NAMA_STRATEGI = "B0-TRENDLINE_BREAK"


# --------------------------------------------------------------------- baris


class Baris:
    """Padanan `_Row` legacy (`patterns.py:29`)."""

    __slots__ = ("open", "high", "low", "close", "volume")

    def __init__(self, r: Sequence[float]) -> None:
        self.open = r[1]
        self.high = r[2]
        self.low = r[3]
        self.close = r[4]
        self.volume = r[5] if len(r) > 5 else 0.0


# ------------------------------------------------------- port dari patterns.py


def pivot_dari_ohlcv(ohlcv, swing_len: int = 3):
    """Port `pivots_from_ohlcv` (patterns.py:38)."""
    n = len(ohlcv)
    highs = [r[2] for r in ohlcv]
    lows = [r[3] for r in ohlcv]
    ph: List[Tuple[int, float]] = []
    pl: List[Tuple[int, float]] = []
    for i in range(swing_len, n - swing_len):
        if highs[i] == max(highs[i - swing_len : i + swing_len + 1]):
            ph.append((i, highs[i]))
        if lows[i] == min(lows[i - swing_len : i + swing_len + 1]):
            pl.append((i, lows[i]))
    return ph, pl


def atr_dari_ohlcv(ohlcv, period: int = 14) -> float:
    """Port `_atr_from_ohlcv` (patterns.py:52). Rerata TR sederhana dari EKOR."""
    if len(ohlcv) < 2:
        return 0.0
    trs = []
    for i in range(1, min(period + 1, len(ohlcv))):
        c = ohlcv[-i]
        prev = ohlcv[-(i + 1)]
        trs.append(max(c[2] - c[3], abs(c[2] - prev[4]), abs(c[3] - prev[4])))
    return sum(trs) / len(trs) if trs else 0.0


def linfit(points: Sequence[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
    """Port `linfit` (patterns.py:147)."""
    n = len(points)
    if n < 2:
        return None
    sx = sum(p[0] for p in points)
    sy = sum(p[1] for p in points)
    sxx = sum(p[0] * p[0] for p in points)
    sxy = sum(p[0] * p[1] for p in points)
    denom = n * sxx - sx * sx
    if denom == 0:
        return None
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


def project(line: Tuple[float, float], x: float) -> float:
    """Port `project` (patterns.py:164)."""
    slope, intercept = line
    return slope * x + intercept


def rerata_volume(candles, lookback: int = 20) -> float:
    """Port `avg_volume` (patterns.py:169)."""
    if len(candles) < 2:
        return 0.0
    prev = candles[-(lookback + 1) : -1]
    vols = [getattr(c, "volume", 0.0) or 0.0 for c in prev]
    vols = [v for v in vols if v > 0]
    return (sum(vols) / len(vols)) if vols else 0.0


def ekspansi_volume(candles, k: float = 1.5, lookback: int = 20) -> bool:
    """Port `volume_expansion` (patterns.py:179).

    Catatan legacy yang DIPERTAHANKAN apa adanya: bila volume tidak tersedia
    (semua nol), fungsi ini mengembalikan True, yaitu filter volume DILEWATI.
    Pada parquet Binance volume selalu ada, jadi jalur itu semestinya tak
    terpakai; tetap dicacah lewat `filter_volume_dilewati`.
    """
    if len(candles) < 3:
        return False
    last = getattr(candles[-1], "volume", 0.0) or 0.0
    base = rerata_volume(candles, lookback)
    if base <= 0:
        return True
    return last >= k * base


def close_tegas_melewati(
    candle, level: float, side: str, atr: float, buf_atr: float = 0.1
) -> bool:
    """Port `decisive_close_beyond` (patterns.py:192)."""
    buf = max(atr * buf_atr, 0.0)
    if side == "LONG":
        return candle.close > level + buf
    return candle.close < level - buf


def displacement_kuat(candle, atr: float, body_atr: float = 1.0) -> bool:
    """Port `strong_displacement` (patterns.py:201)."""
    if atr <= 0:
        return False
    return abs(candle.close - candle.open) >= body_atr * atr


def konfirmasi_breakout(
    candles,
    level: float,
    side: str,
    atr: float,
    *,
    buf_atr: float = 0.1,
    vol_k: float = 1.5,
    vol_lookback: int = 20,
    momentum_body_atr: float = 1.2,
) -> bool:
    """Port `confirm_breakout` (patterns.py:210)."""
    if not candles:
        return False
    c = candles[-1]
    if not ekspansi_volume(candles, vol_k, vol_lookback):
        return False
    if close_tegas_melewati(c, level, side, atr, buf_atr):
        return True
    if displacement_kuat(c, atr, momentum_body_atr):
        if side == "LONG" and c.close > level:
            return True
        if side == "SHORT" and c.close < level:
            return True
    return False


def deteksi_trendline(
    pivots: Sequence[Tuple[int, float]],
    kind: str,
    atr: float,
    *,
    lookback: int = 5,
    min_points: int = 3,
    tol_atr: float = 0.6,
) -> Optional[Tuple[float, float]]:
    """Port `detect_trendline` (patterns.py:241)."""
    if atr <= 0 or len(pivots) < min_points:
        return None
    pts = list(pivots[-lookback:])
    if len(pts) < min_points:
        return None
    line = linfit([(float(i), float(p)) for i, p in pts])
    if line is None:
        return None
    tol = tol_atr * atr
    touches = sum(1 for i, p in pts if abs(p - project(line, i)) <= tol)
    if touches < min_points:
        return None
    return line


def deteksi_trendline_break(
    pivot_highs,
    pivot_lows,
    candles,
    cur_index: int,
    atr: float,
    *,
    lookback: int = 5,
    min_points: int = 3,
    tol_atr: float = 0.6,
    buf_atr: float = 0.1,
) -> Optional[Dict[str, Any]]:
    """Port `detect_trendline_break` (patterns.py:265). Urutan LONG lalu SHORT
    dipertahankan: bila keduanya memenuhi, legacy mengembalikan LONG."""
    if not candles:
        return None
    c = candles[-1]
    res = deteksi_trendline(
        pivot_highs, "res", atr, lookback=lookback, min_points=min_points, tol_atr=tol_atr
    )
    if res is not None:
        lvl = project(res, cur_index)
        if close_tegas_melewati(c, lvl, "LONG", atr, buf_atr):
            return {
                "side": "LONG",
                "source": "TRENDLINE_BREAK",
                "level": lvl,
                "allow_market": True,
                "pattern": "trendline-break-up",
            }
    sup = deteksi_trendline(
        pivot_lows, "sup", atr, lookback=lookback, min_points=min_points, tol_atr=tol_atr
    )
    if sup is not None:
        lvl = project(sup, cur_index)
        if close_tegas_melewati(c, lvl, "SHORT", atr, buf_atr):
            return {
                "side": "SHORT",
                "source": "TRENDLINE_BREAK",
                "level": lvl,
                "allow_market": True,
                "pattern": "trendline-break-down",
            }
    return None


# ------------------------------------------------------ port dari strategy.py


def cari_level_tp(
    side: str,
    entry: float,
    sl_price: float,
    *,
    min_rr: float,
    min_gap_r: float,
    fallback_rr: float,
    htf_swing_high: Optional[float] = None,
    htf_swing_low: Optional[float] = None,
    kandidat_tambahan: Optional[Sequence[Tuple[float, str]]] = None,
) -> Dict[str, Any]:
    """Port `find_tp_levels` (strategy.py:945).

    Tier EQL/EQH dan OB legacy TIDAK ADA di sini karena belum diport; yang
    tersisa adalah tier HTF swing dan tier kandidat tambahan. Karena kandidat
    lebih sedikit, `rr1` B0 cenderung LEBIH BESAR daripada legacy (TP terdekat
    legacy sering EQL/EQH). Arah bias itu dicatat, bukan dikoreksi diam-diam.
    """
    sl_dist = abs(entry - sl_price)
    if sl_dist <= 0:
        return dict(
            tp1=entry,
            tp2=0.0,
            rr1=0.0,
            rr2=0.0,
            is_split=False,
            source1="error",
            source2="",
        )

    min_dist = min_rr * sl_dist
    gap_r = min_gap_r * sl_dist
    is_short = side == "SHORT"

    def calc_rr(tp_price: float) -> float:
        return abs(entry - tp_price) / sl_dist

    def searah_profit(level: float) -> bool:
        return (level < entry) if is_short else (level > entry)

    def lewat_minimum(level: float) -> bool:
        return abs(entry - level) >= min_dist

    candidates: List[Tuple[float, str]] = []

    # Tier 3 legacy (satu-satunya tier struktural yang sudah diport).
    if is_short and htf_swing_low is not None:
        if searah_profit(htf_swing_low) and lewat_minimum(htf_swing_low):
            candidates.append((htf_swing_low, "HTF-SwL"))
    if (not is_short) and htf_swing_high is not None:
        if searah_profit(htf_swing_high) and lewat_minimum(htf_swing_high):
            candidates.append((htf_swing_high, "HTF-SwH"))

    # Tier 4 legacy: target confluence HTF.
    if kandidat_tambahan:
        for price, src in kandidat_tambahan:
            if price and searah_profit(price) and lewat_minimum(price):
                candidates.append((price, src))

    candidates.sort(key=lambda k: abs(entry - k[0]))

    tp1 = tp2 = 0.0
    src1 = src2 = ""
    rr1 = rr2 = 0.0

    if candidates:
        tp1, src1 = candidates[0]
        rr1 = calc_rr(tp1)
        tp1_dist = abs(entry - tp1)
        for price, src in reversed(candidates):
            if abs(entry - price) - tp1_dist >= gap_r:
                tp2 = price
                src2 = src
                rr2 = calc_rr(tp2)
                break

    if tp1 == 0.0:
        tp1 = (
            (entry - sl_dist * fallback_rr) if is_short else (entry + sl_dist * fallback_rr)
        )
        src1 = f"fallback-{fallback_rr:.1f}R"
        rr1 = fallback_rr

    is_split = tp2 > 0.0
    return dict(
        tp1=tp1,
        tp2=tp2,
        rr1=round(rr1, 2),
        rr2=round(rr2, 2),
        is_split=is_split,
        source1=src1,
        source2=src2,
    )


# ------------------------------------------------------------------- param B0


@dataclass(frozen=True)
class ParamB0:
    """Parameter B0. Yang berasal dari legacy diberi rujukan barisnya."""

    # dari legacy (terukur)
    swing_len: int = 3  # patterns.htf_context default
    atr_period: int = 14  # patterns._atr_from_ohlcv
    tl_lookback: int = 5  # detect_trendline
    tl_min_points: int = 3  # detect_trendline
    tl_tol_atr: float = 0.6  # htf_context tl_tol_atr
    buf_atr: float = 0.1  # decisive_close_beyond
    vol_k: float = 1.5  # volume_expansion
    vol_lookback: int = 20  # avg_volume
    momentum_body_atr: float = 1.2  # confirm_breakout
    enable_partial_tp: bool = False  # config.py:294 (TERUKUR)
    # WAJIB dari pemanggil: nilai legacy per-strategi BELUM DIUKUR
    min_rr: float = float("nan")
    min_gap_r: float = float("nan")
    fallback_rr: float = float("nan")
    # PENDEKATAN B0, bukan port
    sl_lookback: int = 20
    sl_buf_atr: float = 0.25
    htf_pivot_lookback: int = 6  # htf_context target_lookback_pivots
    # harness
    bar_pemanasan: int = 120
    maks_bar: int = 1440
    mode: str = "eksekusi"

    def wajib_terisi(self) -> None:
        for nama in ("min_rr", "min_gap_r", "fallback_rr"):
            nilai = getattr(self, nama)
            if nilai != nilai:  # NaN
                raise ValueError(
                    f"{nama} wajib diisi pemanggil; nilai legacy per-strategi "
                    "BELUM DIUKUR dan tidak boleh ditebak"
                )


def sl_pendekatan_pivot(
    side: str, ohlcv, atr: float, p: ParamB0
) -> Tuple[float, str]:
    """SL PENDEKATAN B0 (bukan port): ekstrem `sl_lookback` bar tertutup + buffer.

    Legacy menaruh SL di tepi zona OB; OB belum diport. Label dikembalikan supaya
    setiap keluaran menyatakan asal-usulnya.
    """
    ekor = ohlcv[-p.sl_lookback :]
    if side == "LONG":
        return min(r[3] for r in ekor) - p.sl_buf_atr * atr, LABEL_SL
    return max(r[2] for r in ekor) + p.sl_buf_atr * atr, LABEL_SL


def _corong_kosong() -> Dict[str, int]:
    return {
        "bar_diperiksa": 0,
        "atr_nol": 0,
        "tanpa_pola": 0,
        "gagal_konfirmasi_breakout": 0,
        "filter_volume_dilewati": 0,
        "sl_nol_atau_salah_sisi": 0,
        "rr1_di_bawah_min": 0,
        "tanpa_bar_masuk": 0,
        "diterima": 0,
        "gerbang_htf_score_belum_diport": 0,
    }


@dataclass
class KeluaranB0:
    simbol: str
    corong: Dict[str, int] = field(default_factory=_corong_kosong)
    rencana: List[Rencana] = field(default_factory=list)
    keputusan: List[Dict[str, Any]] = field(default_factory=list)
    hasil: List[HasilTrade] = field(default_factory=list)


def pindai_b0(
    simbol: str,
    ts_ms: Sequence[int],
    o: Sequence[float],
    h: Sequence[float],
    l: Sequence[float],
    c: Sequence[float],
    v: Sequence[float],
    p: ParamB0,
) -> KeluaranB0:
    """Pindai bar 1m dan hasilkan Rencana. TANPA look-ahead.

    Kontrak yang ditegakkan:
      - keputusan pada indeks `i` HANYA melihat bar 0..i (bar i sudah tertutup);
      - isian entry SELALU pada `idx_masuk = i + 1` di harga OPEN bar itu;
      - satu posisi pada satu waktu diurus pemanggil `jalankan_b0`.
    """
    p.wajib_terisi()
    n = len(ts_ms)
    keluar = KeluaranB0(simbol=simbol)
    ohlcv_penuh = [
        [int(ts_ms[i]), float(o[i]), float(h[i]), float(l[i]), float(c[i]), float(v[i])]
        for i in range(n)
    ]

    for i in range(p.bar_pemanasan, n - 1):
        keluar.corong["bar_diperiksa"] += 1
        tertutup = ohlcv_penuh[: i + 1]
        atr = atr_dari_ohlcv(tertutup, p.atr_period)
        if atr <= 0:
            keluar.corong["atr_nol"] += 1
            continue
        ph, pl = pivot_dari_ohlcv(tertutup, p.swing_len)
        candles = [Baris(r) for r in tertutup]
        ctx = deteksi_trendline_break(
            ph,
            pl,
            candles,
            i,
            atr,
            lookback=p.tl_lookback,
            min_points=p.tl_min_points,
            tol_atr=p.tl_tol_atr,
            buf_atr=p.buf_atr,
        )
        if ctx is None:
            keluar.corong["tanpa_pola"] += 1
            continue

        if rerata_volume(candles, p.vol_lookback) <= 0:
            keluar.corong["filter_volume_dilewati"] += 1
        if not konfirmasi_breakout(
            candles,
            ctx["level"],
            ctx["side"],
            atr,
            buf_atr=p.buf_atr,
            vol_k=p.vol_k,
            vol_lookback=p.vol_lookback,
            momentum_body_atr=p.momentum_body_atr,
        ):
            keluar.corong["gagal_konfirmasi_breakout"] += 1
            continue

        # Gerbang legacy trendline_min_htf_score = 3 (engine.py:1601) BELUM
        # DIPORT: skor HTF tidak ada. Dilewati dan dicacah, bukan dipalsukan.
        keluar.corong["gerbang_htf_score_belum_diport"] += 1

        side = ctx["side"]
        arah = 1 if side == "LONG" else -1
        harga_masuk = float(o[i + 1])
        sl, label_sl = sl_pendekatan_pivot(side, tertutup, atr, p)
        if (arah == 1 and sl >= harga_masuk) or (arah == -1 and sl <= harga_masuk):
            keluar.corong["sl_nol_atau_salah_sisi"] += 1
            continue

        ekor_ph = [pp for _, pp in ph[-p.htf_pivot_lookback :]]
        ekor_pl = [pp for _, pp in pl[-p.htf_pivot_lookback :]]
        tp_info = cari_level_tp(
            side,
            harga_masuk,
            sl,
            min_rr=p.min_rr,
            min_gap_r=p.min_gap_r,
            fallback_rr=p.fallback_rr,
            htf_swing_high=(max(ekor_ph) if ekor_ph else None),
            htf_swing_low=(min(ekor_pl) if ekor_pl else None),
        )

        # Gerbang engine.py:1997 — verbatim: rr1 < min_rr -> tolak.
        if tp_info["rr1"] < p.min_rr:
            keluar.corong["rr1_di_bawah_min"] += 1
            continue

        # config.py:294 enable_partial_tp=False -> TP tunggal, tanpa split.
        tp = [float(tp_info["tp1"])]
        if tp_info["is_split"] and p.enable_partial_tp:
            tp.append(float(tp_info["tp2"]))

        keluar.rencana.append(
            Rencana(
                simbol=simbol,
                strategi=NAMA_STRATEGI,
                arah=arah,
                idx_masuk=i + 1,
                harga_masuk=harga_masuk,
                sl=float(sl),
                tp=tp,
                maks_bar=p.maks_bar,
                masuk_taker=True,
                keluar_tp_taker=False,
                keluar_sl_taker=True,
                mode=p.mode,
            )
        )
        keluar.keputusan.append(
            {
                "idx_keputusan": i,
                "waktu_keputusan_ms": int(ts_ms[i]) + 60_000,
                "idx_masuk": i + 1,
                "side": side,
                "pola": ctx["pattern"],
                "level": float(ctx["level"]),
                "atr": float(atr),
                "sl": float(sl),
                "label_sl": label_sl,
                "rr1": float(tp_info["rr1"]),
                "sumber_tp1": tp_info["source1"],
                "is_split_legacy": bool(tp_info["is_split"]),
                "split_dipakai": len(tp) > 1,
            }
        )
        keluar.corong["diterima"] += 1

    return keluar


def jalankan_b0(
    simbol: str,
    ts_ms: Sequence[int],
    o: Sequence[float],
    h: Sequence[float],
    l: Sequence[float],
    c: Sequence[float],
    v: Sequence[float],
    p: ParamB0,
    biaya: Biaya = Biaya(),
    satu_posisi: bool = True,
) -> Dict[str, Any]:
    """Pindai lalu simulasikan. `satu_posisi=True` membuang rencana yang muncul
    saat posisi sebelumnya masih terbuka (perilaku bot: satu posisi per pair).
    """
    keluar = pindai_b0(simbol, ts_ms, o, h, l, c, v, p)
    hasil: List[HasilTrade] = []
    dipakai: List[Dict[str, Any]] = []
    batas_idx = -1
    for rencana, keputusan in zip(keluar.rencana, keluar.keputusan):
        if satu_posisi and rencana.idx_masuk <= batas_idx:
            continue
        r = simulasi_trade(rencana, ts_ms, o, h, l, c, biaya)
        hasil.append(r)
        dipakai.append(keputusan)
        batas_idx = r.idx_keluar
    keluar.hasil = hasil
    return {
        "bukan_bukti": False,
        "simbol": simbol,
        "strategi": NAMA_STRATEGI,
        "label_sl": LABEL_SL,
        "corong": dict(keluar.corong),
        "cacah_rencana": len(keluar.rencana),
        "cacah_trade": len(hasil),
        "keputusan": dipakai,
        "hasil": hasil,
        "status_angka": (
            "BELUM DIUKUR di data nyata; angka apa pun dari fungsi ini hanya sah "
            "setelah dijalankan di GitHub Actions atas parquet terverifikasi "
            "sha256, dan hanya sebagai BATAS ATAS karena gerbang "
            "trendline_min_htf_score=3 belum diport dan SL memakai " + LABEL_SL
        ),
        "belum_diport": [
            "EQH/EQL",
            "order block",
            "FVG/IFVG",
            "regime",
            "sepuluh detektor pola lain",
            "trendline_min_htf_score=3",
            "btc_correlation_block",
            "loss breaker",
            "blacklist pair",
            "risk.size_position",
        ],
    }
