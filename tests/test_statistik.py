"""Uji statistik buatan sendiri (tanpa scipy)."""
import math

import numpy as np

from lux_ms.pembagian import lipatan_walk_forward, purge_tumpang_tindih
from lux_ms.statistik import (
    dsr,
    pbo_cscv,
    phi,
    phi_inv,
    sharpe,
    uji_permutasi_tanggal,
)


def test_phi_nilai_acuan():
    assert abs(phi(0.0) - 0.5) < 1e-15
    assert abs(phi(1.959963984540054) - 0.975) < 1e-12
    assert abs(phi(-1.959963984540054) - 0.025) < 1e-12


def test_phi_inv_pulang_balik():
    for p in (1e-6, 0.001, 0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.975, 0.999, 1 - 1e-6):
        assert abs(phi(phi_inv(p)) - p) < 1e-12, p


def test_sharpe_dasar():
    r = np.array([1.0, 1.0, 1.0, 1.0])
    assert math.isnan(sharpe(r))  # std = 0
    r2 = np.array([1.0, -1.0, 1.0, -1.0])
    assert abs(sharpe(r2) - 0.0) < 1e-15


def test_permutasi_tanpa_edge_p_tinggi():
    rng = np.random.default_rng(7)
    n_hari, per_hari = 60, 5
    tgl = np.repeat([f"2026-01-{d+1:02d}" for d in range(n_hari)], per_hari)
    r = rng.normal(0.0, 1.0, n_hari * per_hari)
    out = uji_permutasi_tanggal(r, tgl, n_permutasi=2000, seed=1)
    assert out["n_hari_utc"] == n_hari
    assert out["n_trade"] == n_hari * per_hari
    assert out["p_satu_sisi"] > 0.05


def test_permutasi_dengan_edge_kuat_p_rendah():
    n_hari, per_hari = 60, 5
    tgl = np.repeat([f"2026-01-{d+1:02d}" for d in range(n_hari)], per_hari)
    r = np.full(n_hari * per_hari, 0.5)  # edge positif konsisten
    out = uji_permutasi_tanggal(r, tgl, n_permutasi=2000, seed=1)
    assert out["p_satu_sisi"] < 0.01


def test_permutasi_tanpa_trade_belum_diukur():
    out = uji_permutasi_tanggal([], [], n_permutasi=10)
    assert out["status"].startswith("BELUM DIUKUR")


def test_pbo_derau_murni_mendekati_setengah():
    rng = np.random.default_rng(11)
    M = rng.normal(0, 1, size=(240, 20))  # 20 percobaan tanpa edge
    out = pbo_cscv(M, n_blok=8)
    assert out["n_percobaan"] == 20
    assert out["n_kombinasi"] == 70
    assert 0.25 < out["pbo"] < 0.75


def test_pbo_edge_nyata_rendah():
    rng = np.random.default_rng(12)
    M = rng.normal(0, 1, size=(240, 20))
    M[:, 3] += 0.9  # satu strategi ber-edge sungguhan, stabil di semua blok
    out = pbo_cscv(M, n_blok=8)
    assert out["pbo"] < 0.25


def test_pbo_percobaan_kurang_belum_diukur():
    out = pbo_cscv(np.zeros((100, 1)))
    assert out["status"].startswith("BELUM DIUKUR")


def test_dsr_ambang_naik_dengan_jumlah_percobaan():
    rng = np.random.default_rng(13)
    r = rng.normal(0.05, 1.0, 500)
    d1 = dsr(r, n_percobaan=1)
    d100 = dsr(r, n_percobaan=100)
    d10000 = dsr(r, n_percobaan=10_000)
    assert d1["sharpe_ambang_nol"] == 0.0
    assert d100["sharpe_ambang_nol"] > 0.0
    assert d10000["sharpe_ambang_nol"] > d100["sharpe_ambang_nol"]
    assert d10000["dsr"] <= d100["dsr"] <= d1["dsr"]


def test_dsr_sampel_kurang_belum_diukur():
    assert dsr([0.1, 0.2], n_percobaan=10)["status"].startswith("BELUM DIUKUR")


def test_walk_forward_embargo_membuang_hari_perbatasan():
    tgl = [f"2026-01-{d+1:02d}" for d in range(30)]
    lip = lipatan_walk_forward(tgl, n_lipatan=5, embargo_hari=2)
    assert len(lip) == 5
    for L in lip:
        assert len(L["hari_dipurge"]) == 2
        # tidak boleh ada hari IS yang >= hari OOS pertama
        assert max(L["hari_is"]) < min(L["hari_oos"])
        # hari yang dipurge harus persis di antara IS dan OOS
        assert max(L["hari_is"]) < min(L["hari_dipurge"])
        assert max(L["hari_dipurge"]) < min(L["hari_oos"])
        assert not set(L["hari_is"]) & set(L["hari_oos"])


def test_walk_forward_hari_terlalu_sedikit():
    assert lipatan_walk_forward(["2026-01-01"], n_lipatan=5) == []


def test_purge_tumpang_tindih():
    masuk = np.array([0, 100, 200, 300], dtype=np.int64)
    keluar = np.array([50, 150, 250, 350], dtype=np.int64)
    m = purge_tumpang_tindih(masuk, keluar, oos_awal_ms=140, oos_akhir_ms=260)
    assert m.tolist() == [False, True, True, False]
