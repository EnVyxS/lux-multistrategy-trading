"""Uji baseline B0: kesetiaan port + kontrak gerbang + anti look-ahead.

Yang diuji di sini adalah KONTRAK, bukan hasil. Tidak ada angka pasar nyata di
berkas ini, jadi tidak ada satu pun angka hasil yang boleh dikutip darinya.
"""
import math

from lux_ms import baseline_b0 as b0
from lux_ms.eksekusi import Biaya

TOL = 1e-12


# --------------------------------------------------------------- port murni


def test_linfit_dan_project_eksak():
    line = b0.linfit([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)])
    assert line is not None
    slope, intercept = line
    assert abs(slope - 1.0) < TOL
    assert abs(intercept - 0.0) < TOL
    assert abs(b0.project(line, 3.0) - 3.0) < TOL
    assert b0.linfit([(1.0, 5.0)]) is None
    assert b0.linfit([(1.0, 5.0), (1.0, 7.0)]) is None  # denom nol


def test_pivot_dan_atr_tangan():
    # [ts,o,h,l,c,v]; puncak tunggal di indeks 3 (swing_len=3 butuh 7 bar).
    ohlcv = [
        [0, 10.0, 10.5, 9.5, 10.0, 1.0],
        [1, 10.0, 10.6, 9.6, 10.0, 1.0],
        [2, 10.0, 10.7, 9.7, 10.0, 1.0],
        [3, 10.0, 12.0, 9.0, 11.0, 1.0],
        [4, 11.0, 10.8, 9.8, 10.0, 1.0],
        [5, 10.0, 10.9, 9.9, 10.0, 1.0],
        [6, 10.0, 10.4, 9.4, 10.0, 1.0],
    ]
    ph, pl = b0.pivot_dari_ohlcv(ohlcv, swing_len=3)
    assert ph == [(3, 12.0)]
    assert pl == [(3, 9.0)]

    # ATR tangan: rerata TR dari EKOR, period 2 -> dua TR terakhir.
    #   i=1: bar[-1]=idx6, prev=idx5 -> max(10.4-9.4, |10.4-10.0|, |9.4-10.0|) = 1.0
    #   i=2: bar[-2]=idx5, prev=idx4 -> max(10.9-9.9, |10.9-10.0|, |9.9-10.0|) = 1.0
    assert abs(b0.atr_dari_ohlcv(ohlcv, period=2) - 1.0) < TOL
    assert b0.atr_dari_ohlcv([ohlcv[0]], period=14) == 0.0


class _C:
    def __init__(self, o, h, l, c, v):
        self.open, self.high, self.low, self.close, self.volume = o, h, l, c, v


def test_ekspansi_volume_melewati_filter_bila_volume_nol():
    # Perilaku legacy yang DIPERTAHANKAN apa adanya (patterns.py:179).
    candles = [_C(1, 1, 1, 1, 0.0) for _ in range(5)]
    assert b0.ekspansi_volume(candles) is True
    candles2 = [_C(1, 1, 1, 1, 1.0) for _ in range(25)]
    assert b0.ekspansi_volume(candles2, k=1.5) is False
    candles2[-1] = _C(1, 1, 1, 1, 10.0)
    assert b0.ekspansi_volume(candles2, k=1.5) is True


def test_close_tegas_dan_displacement():
    c = _C(100.0, 101.0, 99.0, 100.5, 1.0)
    assert b0.close_tegas_melewati(c, 100.0, "LONG", atr=1.0, buf_atr=0.1) is True
    assert b0.close_tegas_melewati(c, 100.45, "LONG", atr=1.0, buf_atr=0.1) is False
    assert b0.close_tegas_melewati(c, 101.0, "SHORT", atr=1.0, buf_atr=0.1) is True
    assert b0.displacement_kuat(c, atr=0.4, body_atr=1.0) is True
    assert b0.displacement_kuat(c, atr=1.0, body_atr=1.0) is False
    assert b0.displacement_kuat(c, atr=0.0) is False


# ------------------------------------------------------------- find_tp_levels


def test_tp_fallback_tanpa_kandidat():
    info = b0.cari_level_tp(
        "LONG", entry=100.0, sl_price=99.0, min_rr=1.5, min_gap_r=1.0, fallback_rr=2.5
    )
    assert abs(info["tp1"] - 102.5) < TOL
    assert info["rr1"] == 2.5
    assert info["is_split"] is False
    assert info["source1"] == "fallback-2.5R"
    assert info["tp2"] == 0.0


def test_tp1_terdekat_tp2_terjauh_dan_min_dist():
    info = b0.cari_level_tp(
        "LONG",
        entry=100.0,
        sl_price=99.0,
        min_rr=1.5,
        min_gap_r=1.0,
        fallback_rr=2.5,
        kandidat_tambahan=[(101.2, "DEKAT"), (102.0, "TENGAH"), (105.0, "JAUH")],
    )
    # 101.2 = 1.2R < min_rr 1.5R -> dibuang oleh gerbang jarak minimum.
    assert abs(info["tp1"] - 102.0) < TOL
    assert info["rr1"] == 2.0
    assert abs(info["tp2"] - 105.0) < TOL
    assert info["rr2"] == 5.0
    assert info["is_split"] is True


def test_tp_short_simetris_dan_sl_nol():
    info = b0.cari_level_tp(
        "SHORT",
        entry=100.0,
        sl_price=101.0,
        min_rr=1.5,
        min_gap_r=1.0,
        fallback_rr=2.0,
        htf_swing_low=97.0,
    )
    assert abs(info["tp1"] - 97.0) < TOL
    assert info["rr1"] == 3.0
    rusak = b0.cari_level_tp(
        "LONG", entry=100.0, sl_price=100.0, min_rr=1.5, min_gap_r=1.0, fallback_rr=2.0
    )
    assert rusak["source1"] == "error"
    assert rusak["rr1"] == 0.0


def test_param_wajib_menolak_nilai_tak_terukur():
    kena = False
    try:
        b0.ParamB0().wajib_terisi()
    except ValueError as e:
            kena = "BELUM DIUKUR" in str(e)
    assert kena, "ParamB0 tanpa min_rr wajib ditolak"


# ------------------------------------------------------------------ pemindaian


def seri_sintetis(n: int = 200):
    """Seri buatan: gelombang gigi-gergaji dengan puncak MENURUN eksak linear,
    lalu satu bar menembus garis resistance itu dengan volume meledak.

    Bukan data pasar. Hanya untuk membuktikan corong dan gerbang bekerja.
    Gelombang dibuat monoton di antara ekstrem supaya pivot HANYA muncul di
    puncak dan palung; bila baseline datar, `highs[i] == max(window)` benar di
    banyak bar sekaligus dan garis tren tidak pernah terbentuk.
    """
    ts = [i * 60_000 for i in range(n)]
    h = [0.0] * n
    palung = 100.0

    def puncak(m):
        return 105.0 - 0.3 * m

    for i in range(n):
        m, fase = divmod(i, 8)
        if fase == 0:
            h[i] = puncak(m)
        elif fase < 4:
            h[i] = puncak(m) + (palung - puncak(m)) * (fase / 4.0)
        elif fase == 4:
            h[i] = palung
        else:
            h[i] = palung + (puncak(m + 1) - palung) * ((fase - 4) / 4.0)
    c = [x - 0.2 for x in h]
    l = [x - 0.4 for x in h]
    o = [c[0]] + c[:-1]
    v = [1.0] * n

    # Bar tembus di indeks 44.
    o[44] = 100.0
    h[44] = 106.5
    l[44] = 100.0
    c[44] = 106.0
    v[44] = 20.0
    # Setelah tembus, harga naik landai.
    for i in range(45, n):
        o[i] = 106.0 + 0.05 * (i - 45)
        c[i] = o[i] + 0.02
        h[i] = c[i] + 0.05
        l[i] = o[i] - 0.05
    return ts, o, h, l, c, v


def param_uji(**ganti):
    dasar = dict(min_rr=1.5, min_gap_r=1.0, fallback_rr=2.5, bar_pemanasan=30)
    dasar.update(ganti)
    return b0.ParamB0(**dasar)


def test_pindai_menghasilkan_setup_dan_entry_di_bar_berikutnya():
    ts, o, h, l, c, v = seri_sintetis()
    keluar = b0.pindai_b0("UJIUSDT", ts, o, h, l, c, v, param_uji())
    assert keluar.corong["diterima"] >= 1, keluar.corong
    for kep, ren in zip(keluar.keputusan, keluar.rencana):
        assert ren.idx_masuk == kep["idx_keputusan"] + 1
        assert abs(ren.harga_masuk - o[ren.idx_masuk]) < TOL
        assert kep["waktu_keputusan_ms"] == ts[kep["idx_keputusan"]] + 60_000
        assert kep["label_sl"] == b0.LABEL_SL


def test_gerbang_rr1_menolak_saat_min_rr_dinaikkan():
    ts, o, h, l, c, v = seri_sintetis()
    longgar = b0.pindai_b0("UJIUSDT", ts, o, h, l, c, v, param_uji())
    # fallback_rr diturunkan di bawah min_rr supaya tidak ada jalan pintas.
    ketat = b0.pindai_b0(
        "UJIUSDT",
        ts,
        o,
        h,
        l,
        c,
        v,
        param_uji(min_rr=999.0, fallback_rr=1.0),
    )
    assert longgar.corong["diterima"] >= 1
    assert ketat.corong["diterima"] == 0
    assert ketat.corong["rr1_di_bawah_min"] >= 1


def test_tanpa_partial_tp_selalu_tp_tunggal():
    ts, o, h, l, c, v = seri_sintetis()
    keluar = b0.pindai_b0("UJIUSDT", ts, o, h, l, c, v, param_uji())
    assert keluar.rencana
    for ren, kep in zip(keluar.rencana, keluar.keputusan):
        assert len(ren.tp) == 1  # config.py:294 enable_partial_tp=False
        assert kep["split_dipakai"] is False


def test_tak_ada_look_ahead_saat_masa_depan_dirusak():
    ts, o, h, l, c, v = seri_sintetis()
    asli = b0.pindai_b0("UJIUSDT", ts, o, h, l, c, v, param_uji())
    batas = 100
    o2, h2, l2, c2, v2 = list(o), list(h), list(l), list(c), list(v)
    for i in range(batas, len(ts)):
        o2[i] = 1.0
        h2[i] = 500.0
        l2[i] = 0.5
        c2[i] = 400.0
        v2[i] = 9999.0
    rusak = b0.pindai_b0("UJIUSDT", ts, o2, h2, l2, c2, v2, param_uji())

    def sebelum(keluaran):
        return [
            (k["idx_keputusan"], k["side"], round(k["level"], 12), round(k["sl"], 12))
            for k in keluaran.keputusan
            if k["idx_keputusan"] < batas - 1
        ]

    assert sebelum(asli), "tak ada keputusan sebelum batas; uji jadi hampa"
    assert sebelum(asli) == sebelum(rusak)


def test_jalankan_b0_satu_posisi_tidak_tumpang_tindih():
    ts, o, h, l, c, v = seri_sintetis()
    lap = b0.jalankan_b0(
        "UJIUSDT", ts, o, h, l, c, v, param_uji(), Biaya(), satu_posisi=True
    )
    assert lap["bukan_bukti"] is False
    assert lap["cacah_trade"] >= 1
    assert lap["label_sl"] == b0.LABEL_SL
    assert "BELUM DIUKUR" in lap["status_angka"]
    assert "trendline_min_htf_score=3" in lap["belum_diport"]
    hasil = lap["hasil"]
    for a, b in zip(hasil, hasil[1:]):
        assert b.idx_masuk > a.idx_keluar
    for r in hasil:
        assert r.sebab_keluar in ("sl", "tp1", "horizon")
        assert math.isfinite(r.r_bersih)
        assert r.biaya_r >= 0.0
