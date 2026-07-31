"""Harness eksekusi Fase 1: simulator JALUR HARGA per trade.

Yang direkam per trade (tidak ada di backtest.py legacy):
  - MFE / MAE dalam harga DAN dalam R
  - MFE sebagai fraksi jarak ke TP1
  - waktu (bar) ke puncak MFE, dan dari puncak ke penutupan
  - apakah jalur AMBIGU (SL dan TP1 di bar yang sama)
  - biaya per eksekusi (taker/maker terpisah), slippage SL, funding per stempel

Asumsi intrabar: PESIMISTIS. Bila SL dan TP ada di bar yang sama, SL dianggap
kena lebih dulu. Selain itu, pada bar keluar-SL, excursion menguntungkan bar itu
TIDAK dihitung ke MFE secara default (`mfe_ikut_bar_keluar=False`), karena
menghitungnya akan MENGGELEMBUNGKAN kelas M-3A lewat pilihan asumsi belaka.
Kedua varian dapat dilaporkan berpasangan.

Tidak ada scipy. numpy saja.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np

MENIT_MS = 60_000
JAM_MS = 3_600_000
# Stempel settlement funding perpetual USDS-M: 00:00, 08:00, 16:00 UTC.
STEMPEL_JAM_UTC = (0, 8, 16)


@dataclass(frozen=True)
class Biaya:
    fee_taker: float = 0.0005
    fee_maker: float = 0.0002
    sl_slippage_pct: float = 0.0005
    tp_slippage_pct: float = 0.0
    masuk_slippage_pct: float = 0.0
    # Laju funding per stempel sebagai fraksi notional. 0.0 = belum diukur.
    funding_laju_per_stempel: float = 0.0


@dataclass(frozen=True)
class Rencana:
    """Rencana trade. R didefinisikan |harga_masuk - sl|, harus > 0."""
    simbol: str
    strategi: str
    arah: int              # +1 long, -1 short
    idx_masuk: int         # indeks bar 1m saat isian entry terjadi
    harga_masuk: float
    sl: float
    tp: Sequence[float]    # tp[0] = TP1
    maks_bar: int = 1440   # horizon maksimum (bar 1m). intraday default 24 jam
    masuk_taker: bool = True
    keluar_tp_taker: bool = False   # TP lazimnya limit -> maker
    keluar_sl_taker: bool = True    # SL lazimnya stop market -> taker
    mode: str = "eksekusi"          # "eksekusi" (scalp/intraday) | "sinyal" (swing)


@dataclass
class HasilTrade:
    simbol: str
    strategi: str
    arah: int
    mode: str
    idx_masuk: int
    idx_keluar: int
    ts_masuk_ms: int
    ts_keluar_ms: int
    harga_masuk_isi: float
    harga_keluar_isi: float
    sl: float
    tp1: float
    r_harga: float
    sebab_keluar: str          # "sl" | "tp1" | "horizon"
    jalur_ambigu: bool
    cacah_bar_ambigu: int
    mfe_harga: float
    mae_harga: float
    mfe_r: float
    mae_r: float
    mfe_frac_tp1: float
    bar_ke_puncak_mfe: int
    bar_puncak_ke_keluar: int
    r_kotor: float
    biaya_r: float
    biaya_fee_r: float
    biaya_funding_r: float
    cacah_stempel_funding: int
    r_bersih: float
    pernah_floating_profit: bool
    tanggal_utc: str


def _cacah_stempel(ts_masuk_ms: int, ts_keluar_ms: int) -> int:
    """Cacah stempel settlement funding yang DILEWATI posisi.

    Stempel pada 00/08/16 UTC. Posisi yang tidak melewati stempel membayar NOL
    persis. Batas: stempel dihitung bila ts_masuk < stempel <= ts_keluar.
    """
    if ts_keluar_ms <= ts_masuk_ms:
        return 0
    n = 0
    for jam in STEMPEL_JAM_UTC:
        awal_hari = (ts_masuk_ms // 86_400_000) * 86_400_000
        t = awal_hari + jam * JAM_MS
        while t <= ts_keluar_ms:
            if t > ts_masuk_ms:
                n += 1
            t += 86_400_000
    return n


def _fee(harga: float, taker: bool, b: Biaya) -> float:
    return harga * (b.fee_taker if taker else b.fee_maker)


def simulasi_trade(
    rencana: Rencana,
    ts_ms,
    o,
    h,
    l,
    c,
    b: Biaya = Biaya(),
    mfe_ikut_bar_keluar: bool = False,
) -> HasilTrade:
    ts_ms = np.asarray(ts_ms, dtype=np.int64)
    o = np.asarray(o, dtype=np.float64)
    h = np.asarray(h, dtype=np.float64)
    l = np.asarray(l, dtype=np.float64)
    c = np.asarray(c, dtype=np.float64)

    arah = int(rencana.arah)
    if arah not in (1, -1):
        raise ValueError("arah harus +1 atau -1")
    entry = float(rencana.harga_masuk)
    sl = float(rencana.sl)
    tp1 = float(rencana.tp[0])
    r_harga = abs(entry - sl)
    if not (r_harga > 0):
        raise ValueError("R harga nol: sl == harga_masuk")
    if arah == 1 and not (sl < entry < tp1):
        raise ValueError("long butuh sl < entry < tp1")
    if arah == -1 and not (tp1 < entry < sl):
        raise ValueError("short butuh tp1 < entry < sl")

    jarak_tp1 = abs(tp1 - entry)
    entry_isi = entry * (1 + arah * b.masuk_slippage_pct)

    i0 = int(rencana.idx_masuk)
    i_akhir = min(i0 + int(rencana.maks_bar), ts_ms.size)

    mfe = 0.0
    mae = 0.0
    bar_puncak = 0
    cacah_ambigu = 0
    jalur_ambigu = False
    sebab = "horizon"
    idx_keluar = i_akhir - 1
    harga_keluar = float(c[idx_keluar])
    keluar_taker = True

    for i in range(i0, i_akhir):
        hi, lo = float(h[i]), float(l[i])
        if arah == 1:
            fav, adv = hi - entry_isi, entry_isi - lo
            sl_kena, tp_kena = lo <= sl, hi >= tp1
        else:
            fav, adv = entry_isi - lo, hi - entry_isi
            sl_kena, tp_kena = hi >= sl, lo <= tp1

        bar_terakhir = sl_kena or tp_kena
        hitung_fav = (not bar_terakhir) or mfe_ikut_bar_keluar or (tp_kena and not sl_kena)
        if hitung_fav and fav > mfe:
            mfe = fav
            bar_puncak = i - i0
        if adv > mae:
            mae = adv

        if sl_kena and tp_kena:
            cacah_ambigu += 1
            jalur_ambigu = True
        if sl_kena:  # PESIMISTIS: SL menang di bar yang sama
            sebab = "sl"
            idx_keluar = i
            harga_keluar = sl * (1 - arah * b.sl_slippage_pct)
            keluar_taker = rencana.keluar_sl_taker
            break
        if tp_kena:
            sebab = "tp1"
            idx_keluar = i
            harga_keluar = tp1 * (1 - arah * b.tp_slippage_pct)
            keluar_taker = rencana.keluar_tp_taker
            break

    ts_masuk = int(ts_ms[i0])
    ts_keluar = int(ts_ms[idx_keluar]) + MENIT_MS

    r_kotor = arah * (harga_keluar - entry_isi) / r_harga
    fee_total = _fee(entry_isi, rencana.masuk_taker, b) + _fee(harga_keluar, keluar_taker, b)
    biaya_fee_r = fee_total / r_harga

    if rencana.mode == "sinyal":
        # Swing = asumsi SPOT: NOL funding perpetual, dinyatakan eksplisit.
        n_stempel = 0
        biaya_funding_r = 0.0
    else:
        n_stempel = _cacah_stempel(ts_masuk, ts_keluar)
        biaya_funding_r = (n_stempel * entry_isi * b.funding_laju_per_stempel) / r_harga

    biaya_r = biaya_fee_r + biaya_funding_r
    r_bersih = r_kotor - biaya_r

    return HasilTrade(
        simbol=rencana.simbol,
        strategi=rencana.strategi,
        arah=arah,
        mode=rencana.mode,
        idx_masuk=i0,
        idx_keluar=idx_keluar,
        ts_masuk_ms=ts_masuk,
        ts_keluar_ms=ts_keluar,
        harga_masuk_isi=entry_isi,
        harga_keluar_isi=harga_keluar,
        sl=sl,
        tp1=tp1,
        r_harga=r_harga,
        sebab_keluar=sebab,
        jalur_ambigu=jalur_ambigu,
        cacah_bar_ambigu=cacah_ambigu,
        mfe_harga=mfe,
        mae_harga=mae,
        mfe_r=mfe / r_harga,
        mae_r=mae / r_harga,
        mfe_frac_tp1=(mfe / jarak_tp1 if jarak_tp1 > 0 else float("nan")),
        bar_ke_puncak_mfe=bar_puncak,
        bar_puncak_ke_keluar=(idx_keluar - i0) - bar_puncak,
        r_kotor=r_kotor,
        biaya_r=biaya_r,
        biaya_fee_r=biaya_fee_r,
        biaya_funding_r=biaya_funding_r,
        cacah_stempel_funding=n_stempel,
        r_bersih=r_bersih,
        pernah_floating_profit=bool(mfe > 0.0),
        tanggal_utc=np.datetime64(ts_masuk, "ms").astype("datetime64[D]").astype(str),
    )


def excursion_lanjutan(
    hasil: HasilTrade, ts_ms, h, l, bar_lanjut: int = 1440
) -> dict:
    """Counterfactual SETELAH keluar. Hanya untuk kelas M-3B.

    Menjawab: setelah SL kena, apakah harga lanjut searah plan sampai TP1?
    Ini eksplisit sebuah counterfactual, BUKAN bagian dari P&L.
    """
    h = np.asarray(h, dtype=np.float64)
    l = np.asarray(l, dtype=np.float64)
    a, bb = hasil.idx_keluar + 1, min(hasil.idx_keluar + 1 + bar_lanjut, h.size)
    if a >= bb:
        return {"tp1_tercapai": False, "bar_ke_tp1": None, "excursion_lewat_sl_r": 0.0}
    if hasil.arah == 1:
        kena = np.flatnonzero(h[a:bb] >= hasil.tp1)
        lewat = max(0.0, hasil.sl - float(l[a:bb].min()))
    else:
        kena = np.flatnonzero(l[a:bb] <= hasil.tp1)
        lewat = max(0.0, float(h[a:bb].max()) - hasil.sl)
    return {
        "tp1_tercapai": bool(kena.size > 0),
        "bar_ke_tp1": (int(kena[0]) + 1 if kena.size else None),
        "excursion_lewat_sl_r": lewat / hasil.r_harga,
    }
