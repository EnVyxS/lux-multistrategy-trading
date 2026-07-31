"""Statistik ditulis sendiri dengan numpy. TANPA scipy.

Isi: Phi (CDF normal) & Phi^-1, uji permutasi per tanggal UTC, PBO (CSCV Bailey),
DSR (Deflated Sharpe Ratio). Semua deterministik dari seed.
"""
from __future__ import annotations

import itertools
import math
from typing import Dict, List, Sequence

import numpy as np

GAMMA_EULER = 0.5772156649015329


def phi(x: float) -> float:
    """CDF normal standar via math.erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def phi_inv(p: float) -> float:
    """Invers CDF normal, aproksimasi Acklam + satu langkah Halley.

    Galat mutlak < 1e-9 pada (0,1). Diuji di tests/test_statistik.py.
    """
    if not (0.0 < p < 1.0):
        raise ValueError("p harus di (0,1)")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        x = (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    elif p <= ph:
        q = p - 0.5
        r = q * q
        x = (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    else:
        q = math.sqrt(-2 * math.log(1 - p))
        x = -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    # penghalusan Halley
    e = phi(x) - p
    u = e * math.sqrt(2 * math.pi) * math.exp(x * x / 2)
    return x - u / (1 + x * u / 2)


def sharpe(r: np.ndarray) -> float:
    r = np.asarray(r, dtype=np.float64)
    if r.size < 2:
        return float("nan")
    s = r.std(ddof=1)
    return float(r.mean() / s) if s > 0 else float("nan")


def skew_kurt(r: np.ndarray):
    r = np.asarray(r, dtype=np.float64)
    n = r.size
    if n < 4:
        return float("nan"), float("nan")
    m = r.mean()
    s = r.std(ddof=1)
    if s == 0:
        return float("nan"), float("nan")
    z = (r - m) / s
    return float((z ** 3).mean()), float((z ** 4).mean())


def uji_permutasi_tanggal(
    r_per_trade: Sequence[float],
    tanggal_utc: Sequence[str],
    n_permutasi: int = 10_000,
    seed: int = 20260801,
) -> dict:
    """Uji permutasi PER TANGGAL UTC (bukan per trade).

    Label tanggal diacak, bukan trade individual: menjaga struktur klaster
    intra-hari sehingga p-value tidak dipercantik oleh independensi palsu.
    Statistik uji: rata-rata R bersih per trade.
    """
    r = np.asarray(r_per_trade, dtype=np.float64)
    tgl = np.asarray(tanggal_utc)
    if r.size == 0:
        return {"n": 0, "stat": float("nan"), "p_satu_sisi": float("nan"),
                "status": "BELUM DIUKUR (tanpa trade)"}
    uniq, inv = np.unique(tgl, return_inverse=True)
    n_hari = uniq.size
    per_hari = np.array([r[inv == i].mean() for i in range(n_hari)])
    bobot = np.array([int((inv == i).sum()) for i in range(n_hari)], dtype=np.float64)
    stat = float((per_hari * bobot).sum() / bobot.sum())

    rng = np.random.default_rng(seed)
    tanda = rng.choice(np.array([-1.0, 1.0]), size=(n_permutasi, n_hari))
    null = (tanda * per_hari[None, :] * bobot[None, :]).sum(axis=1) / bobot.sum()
    p = float((1 + np.sum(null >= stat)) / (1 + n_permutasi))
    return {
        "n_trade": int(r.size),
        "n_hari_utc": int(n_hari),
        "stat_rata_R_bersih": stat,
        "p_satu_sisi": p,
        "n_permutasi": int(n_permutasi),
        "seed": int(seed),
        "metode": "flip tanda per tanggal UTC, berbobot cacah trade",
    }


def pbo_cscv(matriks_r: np.ndarray, n_blok: int = 8) -> dict:
    """Probability of Backtest Overfitting, CSCV (Bailey et al. 2014).

    matriks_r: bentuk (T, N) = return per periode x per PERCOBAAN.
    N HARUS mencakup SELURUH percobaan, termasuk percobaan pada pemilih.
    """
    M = np.asarray(matriks_r, dtype=np.float64)
    if M.ndim != 2:
        raise ValueError("matriks_r harus 2D (T, N)")
    T, N = M.shape
    if N < 2:
        return {"pbo": float("nan"), "status": "BELUM DIUKUR (butuh N>=2 percobaan)"}
    if n_blok % 2 != 0 or n_blok < 2:
        raise ValueError("n_blok harus genap >= 2")
    potong = (T // n_blok) * n_blok
    if potong < n_blok:
        return {"pbo": float("nan"), "status": "BELUM DIUKUR (T terlalu kecil)"}
    blok = np.array_split(np.arange(potong), n_blok)

    logit = []
    for komb in itertools.combinations(range(n_blok), n_blok // 2):
        idx_is = np.concatenate([blok[i] for i in komb])
        idx_oos = np.concatenate([blok[i] for i in range(n_blok) if i not in komb])
        sr_is = np.array([sharpe(M[idx_is, j]) for j in range(N)])
        sr_oos = np.array([sharpe(M[idx_oos, j]) for j in range(N)])
        if np.all(np.isnan(sr_is)):
            continue
        terbaik = int(np.nanargmax(sr_is))
        sah = ~np.isnan(sr_oos)
        if sah.sum() < 2 or np.isnan(sr_oos[terbaik]):
            continue
        peringkat = float((sr_oos[sah] < sr_oos[terbaik]).sum()) / float(sah.sum())
        peringkat = min(max(peringkat, 1e-6), 1 - 1e-6)
        logit.append(math.log(peringkat / (1 - peringkat)))
    if not logit:
        return {"pbo": float("nan"), "status": "BELUM DIUKUR (tak ada kombinasi sah)"}
    lg = np.array(logit)
    return {
        "pbo": float((lg <= 0).mean()),
        "n_kombinasi": int(lg.size),
        "n_percobaan": int(N),
        "n_blok": int(n_blok),
        "logit_median": float(np.median(lg)),
    }


def dsr(
    r_terpilih: Sequence[float],
    n_percobaan: int,
    var_sr_percobaan: float | None = None,
) -> dict:
    """Deflated Sharpe Ratio (Bailey & Lopez de Prado).

    n_percobaan WAJIB mencakup seluruh percobaan yang pernah dijalankan,
    termasuk percobaan pada aturan pemilihan. Grid yang membengkak di tengah
    jalan membuat angka ini tidak sah.
    """
    r = np.asarray(r_terpilih, dtype=np.float64)
    n = r.size
    if n < 4 or n_percobaan < 1:
        return {"dsr": float("nan"), "status": "BELUM DIUKUR (sampel/percobaan kurang)"}
    sr = sharpe(r)
    g3, g4 = skew_kurt(r)
    if any(map(math.isnan, (sr, g3, g4))):
        return {"dsr": float("nan"), "status": "BELUM DIUKUR (statistik tak terdefinisi)"}
    if var_sr_percobaan is None:
        var_sr_percobaan = (1.0 - g3 * sr + (g4 - 1.0) / 4.0 * sr * sr) / (n - 1)
    sd = math.sqrt(max(var_sr_percobaan, 1e-18))
    N = int(n_percobaan)
    if N == 1:
        sr0 = 0.0
    else:
        sr0 = sd * ((1 - GAMMA_EULER) * phi_inv(1 - 1.0 / N)
                    + GAMMA_EULER * phi_inv(1 - 1.0 / (N * math.e)))
    penyebut = math.sqrt(max(1.0 - g3 * sr + (g4 - 1.0) / 4.0 * sr * sr, 1e-18))
    z = (sr - sr0) * math.sqrt(n - 1) / penyebut
    return {
        "sharpe": sr,
        "sharpe_ambang_nol": sr0,
        "skew": g3,
        "kurtosis": g4,
        "n_observasi": int(n),
        "n_percobaan": N,
        "dsr": phi(z),
    }
