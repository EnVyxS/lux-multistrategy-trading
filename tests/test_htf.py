"""Uji konteks HTF: kesetiaan port + tabel skor + gerbang + anti look-ahead.

Yang diuji KONTRAK, bukan hasil. Tidak ada angka pasar nyata di sini.
"""
import numpy as np

from lux_ms import htf as H
from lux_ms.resample import audit_look_ahead

T0 = 1_767_225_600_000  # 2026-01-01T00:00:00Z, kelipatan 4H tepat
MENIT = 60_000


def _dasar(n=15):
    return [[i, 10.0, 10.5, 9.5, 10.0, 1.0] for i in range(n)]


# ------------------------------------------------------------ deteksi_bias


def test_bias_netral_bila_bar_kurang():
    # strategy.py:200 -> butuh swing_len*2+3 = 9 bar.
    assert H.deteksi_bias(_dasar(8)) == H.NETRAL
    assert H.deteksi_bias([]) == H.NETRAL


def test_bias_bull_dari_bos_di_atas_pivot_high():
    b = _dasar(15)
    b[3][2], b[3][3] = 12.0, 9.0   # pivot high 12.0 dan pivot low 9.0
    b[8][2], b[8][4] = 12.6, 12.5  # close 12.5 > pivot high 12.0 -> BOS BULL
    b[11][2] = 13.0                # high lebih tinggi -> i=8 bukan pivot
    assert H.deteksi_bias(b) == H.BULL


def test_bias_bear_dari_bos_di_bawah_pivot_low():
    b = _dasar(15)
    b[3][3] = 8.0                  # pivot low 8.0
    b[8][3], b[8][4] = 7.4, 7.5    # close 7.5 < pivot low 8.0 -> BOS BEAR
    b[11][3] = 7.0                 # low lebih rendah -> i=8 bukan pivot
    assert H.deteksi_bias(b) == H.BEAR


def test_bias_deret_monoton_tetap_netral():
    # Perilaku legacy yang DIPERTAHANKAN: deret naik ketat tidak punya pivot,
    # jadi tidak ada BOS, jadi NEUTRAL. Bukan cacat, dan tidak ditambal.
    naik = [[i, 10.0 + i, 10.5 + i, 9.5 + i, 10.0 + i, 1.0] for i in range(40)]
    assert H.deteksi_bias(naik) == H.NETRAL


# --------------------------------------------------------- CHoCH dan swing


def test_choch_kurang_bar_mengembalikan_tiga_none():
    assert H.deteksi_choch_dan_swing(_dasar(8)) == (None, None, None)


def test_choch_bull_setelah_bear_lalu_kedaluwarsa():
    b = _dasar(24)
    b[3][3] = 8.0
    b[8][3], b[8][4] = 7.4, 7.5    # BEAR lebih dulu
    b[11][3] = 7.0
    b[14][2] = 13.0                # pivot high 13.0
    b[19][2], b[19][4] = 13.4, 13.2  # close di atas 13.0 -> flip BULL = CHoCH
    b[22][2] = 14.0                # high lebih tinggi -> i=19 bukan pivot
    choch, sh, sl = H.deteksi_choch_dan_swing(b)
    assert choch == H.BULL
    assert sh is not None and sl is not None

    # Tambah 30 bar datar: CHoCH jadi lebih tua dari UMUR_CHOCH_MAKS -> dibuang.
    panjang = len(b)
    b2 = b + [[panjang + i, 10.0, 10.5, 9.5, 10.0, 1.0] for i in range(30)]
    choch2, _, _ = H.deteksi_choch_dan_swing(b2)
    assert choch2 is None


# ------------------------------------------------------------ tabel skor


def test_skor_tolak_keras_hanya_dari_4h_berlawanan():
    assert H.hitung_skor(H.BEAR, H.BULL, None, "LONG")[0] == H.SKOR_TOLAK_KERAS
    assert H.hitung_skor(H.BULL, H.BEAR, None, "SHORT")[0] == H.SKOR_TOLAK_KERAS
    # 1H berlawanan BUKAN pemblokir di legacy.
    assert H.hitung_skor(H.NETRAL, H.BEAR, None, "LONG")[0] == 1


def test_tabel_skor_lengkap():
    kasus = [
        ((H.NETRAL, H.NETRAL, "LONG"), 1),
        ((H.NETRAL, H.BULL, "LONG"), 2),
        ((H.BULL, H.NETRAL, "LONG"), 2),
        ((H.BULL, H.BULL, "LONG"), 3),
        ((H.NETRAL, H.NETRAL, "SHORT"), 1),
        ((H.BEAR, H.BEAR, "SHORT"), 3),
        ((H.BEAR, H.NETRAL, "SHORT"), 2),
    ]
    for (b4, b1, arah), diharap in kasus:
        skor, _ = H.hitung_skor(b4, b1, None, arah)
        assert skor == diharap, (b4, b1, arah, skor, diharap)


def test_choch_hanya_catatan_bukan_gerbang():
    skor_a, catatan_a = H.hitung_skor(H.BULL, H.BULL, H.BEAR, "LONG")
    skor_b, catatan_b = H.hitung_skor(H.BULL, H.BULL, H.BULL, "LONG")
    skor_c, catatan_c = H.hitung_skor(H.BULL, H.BULL, None, "LONG")
    assert skor_a == skor_b == skor_c == 3  # CHoCH tidak mengubah skor
    assert catatan_a == "CHoCH15m-berlawanan(BEAR)"
    assert catatan_b == "CHoCH15m-searah"
    assert catatan_c == "noCHoCH(ok)"


def test_arah_tidak_sah_ditolak():
    try:
        H.hitung_skor(H.BULL, H.BULL, None, "BELI")
    except ValueError as e:
        assert "arah tidak sah" in str(e)
    else:
        raise AssertionError("arah tidak sah harus melempar ValueError")


# --------------------------------------------------------------- gerbang


def test_gerbang_trendline_tiga_vonis():
    k_tolak = H.KonteksHTF(bias_4h=H.BEAR, bias_1h=H.BEAR)
    v = H.gerbang_trendline(k_tolak, "LONG")
    assert v["lulus"] is False and v["sebab"] == "htf_tolak_keras_4h"

    k_dua = H.KonteksHTF(bias_4h=H.BULL, bias_1h=H.NETRAL)
    v2 = H.gerbang_trendline(k_dua, "LONG")
    assert v2["skor"] == 2
    assert v2["lulus"] is False and v2["sebab"] == "htf_score_di_bawah_min_tb"

    k_tiga = H.KonteksHTF(bias_4h=H.BULL, bias_1h=H.BULL)
    v3 = H.gerbang_trendline(k_tiga, "LONG")
    assert v3["skor"] == 3 and v3["lulus"] is True and v3["sebab"] is None


def test_min_htf_score_legacy_adalah_tiga():
    assert H.TRENDLINE_MIN_HTF_SCORE == 3
    assert (H.CACAH_TERTUTUP_4H, H.CACAH_TERTUTUP_1H, H.CACAH_TERTUTUP_15M) == (59, 59, 79)


# --------------------------------------------------- konteks + look-ahead


def _seri_1m(n=2000):
    ts = np.arange(n, dtype=np.int64) * MENIT + T0
    x = np.arange(n, dtype=np.float64)
    c = 100.0 + np.sin(x / 37.0) * 5.0
    o = c.copy()
    h = c + 0.4
    l = c - 0.4
    v = np.full(n, 10.0)
    return ts, o, h, l, c, v


def test_pra_htf_membuang_bucket_tak_lengkap():
    ts, o, h, l, c, v = _seri_1m(2000)
    pra = H.bangun_pra_htf(ts, o, h, l, c, v)
    # 2000 bar 1m -> 8 bucket 4H penuh (1920 bar), sisa 80 bar dibuang.
    assert pra.tf[H.TF_MENIT_4H]["ts"].size == 8
    assert pra.dibuang_tak_lengkap[H.TF_MENIT_4H] == 1
    assert pra.tf[H.TF_MENIT_1H]["ts"].size == 33
    assert pra.tf[H.TF_MENIT_15M]["ts"].size == 133


def test_konteks_sebelum_bar_htf_tertutup_tetap_netral():
    ts, o, h, l, c, v = _seri_1m(2000)
    pra = H.bangun_pra_htf(ts, o, h, l, c, v)
    k = H.konteks_pada(pra, int(T0 + 100 * MENIT))
    assert k.idx_4h == -1 and k.bias_4h == H.NETRAL
    assert k.cacah_bar_4h == 0
    assert k.htf_siap is False


def test_konteks_memakai_bar_tertutup_terakhir_dan_dibatasi_cacah():
    ts, o, h, l, c, v = _seri_1m(2000)
    pra = H.bangun_pra_htf(ts, o, h, l, c, v)
    k = H.konteks_pada(pra, int(T0 + 1999 * MENIT))
    assert k.idx_4h == 7            # delapan bar 4H sudah tutup
    assert k.cacah_bar_4h == 8      # semuanya dipakai (< 59)
    assert k.idx_15m == 132
    assert k.cacah_bar_15m == H.CACAH_TERTUTUP_15M  # dibatasi 79


def test_batas_tutup_tepat_sudah_sah():
    ts, o, h, l, c, v = _seri_1m(2000)
    pra = H.bangun_pra_htf(ts, o, h, l, c, v)
    tutup_pertama = int(pra.tf[H.TF_MENIT_4H]["tersedia_pada"][0])
    assert H.konteks_pada(pra, tutup_pertama - 1).idx_4h == -1
    assert H.konteks_pada(pra, tutup_pertama).idx_4h == 0


def test_audit_look_ahead_lulus_di_semua_waktu_keputusan():
    ts, o, h, l, c, v = _seri_1m(2000)
    pra = H.bangun_pra_htf(ts, o, h, l, c, v)
    waktu = []
    idx4 = []
    idx15 = []
    for i in range(0, 2000, 7):
        d = int(ts[i])
        k = H.konteks_pada(pra, d)
        waktu.append(d)
        idx4.append(k.idx_4h)
        idx15.append(k.idx_15m)
    a4 = audit_look_ahead(pra.tf[H.TF_MENIT_4H]["tersedia_pada"], waktu, idx4)
    a15 = audit_look_ahead(pra.tf[H.TF_MENIT_15M]["tersedia_pada"], waktu, idx15)
    assert a4["lulus"] is True and a4["cacah_pelanggaran"] == 0
    assert a15["lulus"] is True and a15["cacah_pelanggaran"] == 0
    assert a4["cacah_tanpa_bar"] > 0  # awal deret memang belum punya bar 4H
