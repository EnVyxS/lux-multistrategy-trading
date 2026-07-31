"""Walk-forward IS/OOS dengan PURGING dan EMBARGO pada sumbu tanggal UTC.

Purging: buang sampel IS yang rentang hidupnya bertumpang-tindih dengan OOS.
Embargo: buang tambahan e hari sesudah blok OOS dari IS berikutnya.
Tanpa keduanya, kebocoran serial membuat OOS bukan OOS.
"""
from __future__ import annotations

from typing import List, Sequence

import numpy as np


def lipatan_walk_forward(
    tanggal_utc: Sequence[str],
    n_lipatan: int = 5,
    embargo_hari: int = 1,
    min_hari_is: int = 1,
) -> List[dict]:
    """Lipatan maju (anchored) pada sumbu hari UTC.

    Returns daftar dict: {'hari_is', 'hari_oos', 'hari_dipurge', 'embargo_hari'}
    berisi tanggal (str), bukan indeks trade, agar dapat diaudit langsung.
    """
    hari = np.unique(np.asarray(tanggal_utc))
    n = hari.size
    if n_lipatan < 1:
        raise ValueError("n_lipatan >= 1")
    if n < n_lipatan + 1:
        return []
    potong = np.array_split(np.arange(n), n_lipatan + 1)
    lipatan = []
    for k in range(1, n_lipatan + 1):
        idx_oos = potong[k]
        idx_is = np.arange(0, potong[k][0])
        # embargo: buang `embargo_hari` terakhir IS (berbatasan dengan OOS)
        n_purge = min(embargo_hari, idx_is.size)
        dipurge = idx_is[idx_is.size - n_purge:] if n_purge else np.array([], dtype=int)
        idx_is_bersih = idx_is[: idx_is.size - n_purge]
        if idx_is_bersih.size < min_hari_is:
            continue
        lipatan.append({
            "lipatan": k,
            "hari_is": hari[idx_is_bersih].tolist(),
            "hari_oos": hari[idx_oos].tolist(),
            "hari_dipurge": hari[dipurge].tolist(),
            "embargo_hari": int(embargo_hari),
        })
    return lipatan


def purge_tumpang_tindih(
    ts_masuk_ms: Sequence[int],
    ts_keluar_ms: Sequence[int],
    oos_awal_ms: int,
    oos_akhir_ms: int,
) -> np.ndarray:
    """Mask trade IS yang WAJIB dibuang karena hidupnya menyentuh jendela OOS."""
    a = np.asarray(ts_masuk_ms, dtype=np.int64)
    b = np.asarray(ts_keluar_ms, dtype=np.int64)
    return (b >= oos_awal_ms) & (a <= oos_akhir_ms)


def garis_dasar_negatif(
    n_hari: int, n_per_hari: float, rng_seed: int = 20260801
) -> dict:
    """Spesifikasi dua garis dasar negatif WAJIB.

    Belum menghasilkan angka: menghasilkan KONTRAK yang harus dijalankan
    di CI atas dataset nyata. Tanpa dataset, statusnya BELUM DIUKUR.
    """
    return {
        "acak": {
            "definisi": "arah long/short seragam, entry pada bar acak, SL/TP identik strategi uji",
            "seed": rng_seed,
            "n_hari": n_hari,
            "n_sinyal_per_hari_target": n_per_hari,
            "status": "BELUM DIUKUR",
        },
        "selalu_entry": {
            "definisi": "entry setiap bar 1m searah bar sebelumnya, SL/TP identik strategi uji",
            "status": "BELUM DIUKUR",
        },
    }
