"""Syarat lulus Fase 1 #2: uji anti-look-ahead lintas TF WAJIB lulus.

Konstruksi: lonjakan sengaja ditaruh di menit TERAKHIR sebuah bucket 5m.
Bila resample bocor, bar 5m yang memuat lonjakan akan terlihat sebelum tutup.
"""
import numpy as np

from lux_ms.resample import (
    audit_look_ahead,
    indeks_bar_terpakai,
    resample_tertutup,
)

T0 = 1_767_225_600_000  # 2026-01-01T00:00:00Z
M = 60_000


def _deret(n=30):
    ts = T0 + np.arange(n, dtype=np.int64) * M
    o = np.full(n, 100.0)
    h = np.full(n, 100.1)
    l = np.full(n, 99.9)
    c = np.full(n, 100.0)
    v = np.ones(n)
    return ts, o, h, l, c, v


def test_bucket_lengkap_dan_waktu_tersedia():
    ts, o, h, l, c, v = _deret(30)
    r = resample_tertutup(ts, o, h, l, c, v, 5)
    assert r["ts"].size == 6
    assert r["dibuang_tak_lengkap"] == 0
    # bar 5m pertama buka 00:00 dan TUTUP 00:05 -> tersedia_pada = T0 + 5m
    assert int(r["tersedia_pada"][0]) == T0 + 5 * M
    assert np.all(r["tersedia_pada"] == r["ts"] + 5 * M)
    assert np.all(r["cacah_bar_1m"] == 5)


def test_bucket_bolong_dibuang_bukan_ditambal():
    ts, o, h, l, c, v = _deret(30)
    pilih = np.ones(30, dtype=bool)
    pilih[7] = False  # bolongi bucket ke-2 (menit 5..9)
    r = resample_tertutup(ts[pilih], o[pilih], h[pilih], l[pilih], c[pilih], v[pilih], 5)
    assert r["dibuang_tak_lengkap"] == 1
    assert r["ts"].size == 5
    assert (T0 + 5 * M) not in set(r["ts"].tolist())


def test_lonjakan_menit_terakhir_tidak_bocor():
    ts, o, h, l, c, v = _deret(30)
    h = h.copy()
    h[9] = 999.0  # menit ke-9 = menit TERAKHIR bucket 00:05-00:10
    r = resample_tertutup(ts, o, h, l, c, v, 5)
    idx_lonjakan = int(np.flatnonzero(r["ts"] == T0 + 5 * M)[0])
    assert r["h"][idx_lonjakan] == 999.0

    # Keputusan pada 00:09:00 TIDAK BOLEH melihat bar itu.
    i = indeks_bar_terpakai(r["tersedia_pada"], T0 + 9 * M)
    assert i == 0
    assert r["h"][i] != 999.0
    # Tepat pada 00:10:00 bar sudah tertutup -> sah dipakai.
    j = indeks_bar_terpakai(r["tersedia_pada"], T0 + 10 * M)
    assert j == idx_lonjakan
    assert r["h"][j] == 999.0


def test_sebelum_bar_pertama_tutup_tidak_ada_bar():
    ts, o, h, l, c, v = _deret(30)
    r = resample_tertutup(ts, o, h, l, c, v, 5)
    assert indeks_bar_terpakai(r["tersedia_pada"], T0) == -1
    assert indeks_bar_terpakai(r["tersedia_pada"], T0 + 4 * M) == -1


def test_audit_look_ahead_lulus_untuk_pemakaian_benar():
    ts, o, h, l, c, v = _deret(30)
    r = resample_tertutup(ts, o, h, l, c, v, 5)
    waktu = ts.copy()
    idx = np.array([indeks_bar_terpakai(r["tersedia_pada"], int(w)) for w in waktu])
    a = audit_look_ahead(r["tersedia_pada"], waktu, idx)
    assert a["lulus"] is True
    assert a["cacah_pelanggaran"] == 0
    assert a["cacah_keputusan"] == 30


def test_audit_look_ahead_menangkap_pelanggaran():
    """Gerbang harus BENAR-BENAR menangkap, bukan hanya selalu bilang lulus."""
    ts, o, h, l, c, v = _deret(30)
    r = resample_tertutup(ts, o, h, l, c, v, 5)
    waktu = np.array([T0 + 9 * M], dtype=np.int64)
    idx_curang = np.array([1])  # bar 00:05-00:10, tutup 00:10 > 00:09
    a = audit_look_ahead(r["tersedia_pada"], waktu, idx_curang)
    assert a["lulus"] is False
    assert a["cacah_pelanggaran"] == 1


def test_banyak_tf_konsisten():
    ts, o, h, l, c, v = _deret(240)
    for tf in (1, 3, 5, 15, 30, 60):
        r = resample_tertutup(ts, o, h, l, c, v, tf)
        assert np.all(r["tersedia_pada"] > r["ts"]) 
        assert np.all(r["tersedia_pada"] == r["ts"] + tf * M)
        assert np.all(np.diff(r["ts"]) == tf * M)
