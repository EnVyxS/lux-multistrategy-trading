"""Penurunan timeframe dari klines 1m, BEBAS LOOK-AHEAD.

Aturan tunggal yang ditegakkan di sini:
  Bar TF-tinggi hanya boleh dipakai SETELAH tertutup.
  Bar dengan open_time T dan panjang M menit tertutup pada T + M*60_000 (ms).
  `tersedia_pada` = waktu tutup. Fitur pada waktu keputusan D hanya boleh
  memakai bar dengan tersedia_pada <= D.

Tidak ada pandas di jalur ini: numpy saja, deterministik, tanpa alokasi tersembunyi.
"""
from __future__ import annotations

import numpy as np

MENIT_MS = 60_000


def resample_tertutup(ts_ms, o, h, l, c, v, tf_menit: int):
    """Resample 1m -> tf_menit. Mengembalikan hanya bar yang UTUH (penuh).

    Args:
        ts_ms: open_time bar 1m dalam milidetik UTC, naik, tanpa duplikat.
        o,h,l,c,v: array sejajar.
        tf_menit: kelipatan menit, >= 1.

    Returns:
        dict dengan kunci: ts (open_time), o,h,l,c,v, tersedia_pada, lengkap.
        Hanya bucket dengan tepat tf_menit bar 1m dikembalikan (lengkap=True).
        Bucket bolong DIBUANG, tidak ditambal, dan cacahnya dilaporkan.
    """
    if tf_menit < 1:
        raise ValueError("tf_menit harus >= 1")
    ts_ms = np.asarray(ts_ms, dtype=np.int64)
    if ts_ms.size == 0:
        raise ValueError("deret kosong")
    if np.any(np.diff(ts_ms) <= 0):
        raise ValueError("ts_ms harus naik ketat (tanpa duplikat)")
    o = np.asarray(o, dtype=np.float64)
    h = np.asarray(h, dtype=np.float64)
    l = np.asarray(l, dtype=np.float64)
    c = np.asarray(c, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)

    lebar = tf_menit * MENIT_MS
    bucket = (ts_ms // lebar) * lebar
    batas = np.flatnonzero(np.r_[True, bucket[1:] != bucket[:-1]])
    akhir = np.r_[batas[1:], ts_ms.size]

    n = batas.size
    r_ts = bucket[batas]
    r_o = o[batas]
    r_c = c[akhir - 1]
    r_h = np.empty(n)
    r_l = np.empty(n)
    r_v = np.empty(n)
    cacah = akhir - batas
    for i in range(n):
        a, b = batas[i], akhir[i]
        r_h[i] = h[a:b].max()
        r_l[i] = l[a:b].min()
        r_v[i] = v[a:b].sum()

    lengkap = cacah == tf_menit
    tersedia = r_ts + lebar  # waktu TUTUP: tidak boleh dipakai sebelum ini

    return {
        "ts": r_ts[lengkap],
        "o": r_o[lengkap],
        "h": r_h[lengkap],
        "l": r_l[lengkap],
        "c": r_c[lengkap],
        "v": r_v[lengkap],
        "tersedia_pada": tersedia[lengkap],
        "cacah_bar_1m": cacah[lengkap],
        "dibuang_tak_lengkap": int((~lengkap).sum()),
    }


def indeks_bar_terpakai(tersedia_pada, waktu_keputusan_ms: int) -> int:
    """Indeks bar TF-tinggi TERAKHIR yang sah dipakai pada waktu keputusan.

    Mengembalikan -1 bila belum ada bar yang tertutup. Batas <= disengaja:
    bar yang tutup TEPAT pada waktu keputusan sudah sah dipakai.
    """
    tersedia_pada = np.asarray(tersedia_pada, dtype=np.int64)
    return int(np.searchsorted(tersedia_pada, waktu_keputusan_ms, side="right") - 1)


def audit_look_ahead(tersedia_pada, waktu_keputusan_ms, indeks_dipakai) -> dict:
    """Vonis biner: apakah ada bar yang dipakai sebelum tertutup.

    Dipakai sebagai gerbang WAJIB di CI. Pelanggaran = harness tidak lulus.
    """
    tersedia_pada = np.asarray(tersedia_pada, dtype=np.int64)
    waktu = np.asarray(waktu_keputusan_ms, dtype=np.int64)
    idx = np.asarray(indeks_dipakai, dtype=np.int64)
    sah = idx >= 0
    pelanggaran = np.zeros(idx.shape, dtype=bool)
    pelanggaran[sah] = tersedia_pada[idx[sah]] > waktu[sah]
    return {
        "cacah_keputusan": int(idx.size),
        "cacah_tanpa_bar": int((~sah).sum()),
        "cacah_pelanggaran": int(pelanggaran.sum()),
        "lulus": bool(pelanggaran.sum() == 0),
    }
