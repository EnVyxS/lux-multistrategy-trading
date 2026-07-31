"""Syarat lulus Fase 1 #1: harness mereproduksi satu contoh trade TANGAN,
digit demi digit.

Contoh tangan (long), semua angka dihitung manual di catatan sesi:
  entry  = 100.00, sl = 99.50  -> R_harga = 0.50
  tp1    = 101.00              -> jarak_tp1 = 1.00
  bar 0: o=100.00 h=100.20 l=99.90  c=100.10
  bar 1: o=100.10 h=100.35 l=100.00 c=100.30
  bar 2: o=100.30 h=100.40 l=99.40  c=99.45   -> SL kena (99.40 <= 99.50)
                                                 TP1 TIDAK kena -> tidak ambigu
  harga keluar = 99.50 * (1 - 0.0005) = 99.450250
  MFE (bar keluar TIDAK dihitung, pesimistis) = max(0.20, 0.35) = 0.35
  MFE_R = 0.35 / 0.50 = 0.70
  MFE/jarak_tp1 = 0.35 / 1.00 = 0.35
  R kotor = (99.450250 - 100.00) / 0.50 = -1.0995
  fee masuk  (taker) = 100.000000 * 0.0005 = 0.050000000
  fee keluar (taker) =  99.450250 * 0.0005 = 0.049725125
  fee total = 0.099725125 -> dalam R = 0.19945025
  funding: 0 stempel dilewati -> 0.0
  R bersih = -1.0995 - 0.19945025 = -1.29895025
  Kelas: r_bersih<0, MFE>0, MFE<jarak_tp1 -> M3A
"""
import numpy as np

from lux_ms.eksekusi import Biaya, Rencana, simulasi_trade
from lux_ms.kelas import klasifikasi

TOL = 1e-12
T0 = 1_767_225_600_000  # 2026-01-01T00:00:00Z, dalam ms


def _pasar():
    ts = np.array([T0, T0 + 60_000, T0 + 120_000], dtype=np.int64)
    o = np.array([100.00, 100.10, 100.30])
    h = np.array([100.20, 100.35, 100.40])
    l = np.array([99.90, 100.00, 99.40])
    c = np.array([100.10, 100.30, 99.45])
    return ts, o, h, l, c


def test_trade_tangan_digit_demi_digit():
    ts, o, h, l, c = _pasar()
    r = Rencana(
        simbol="UJICOBAUSDT", strategi="tangan_v1", arah=1, idx_masuk=0,
        harga_masuk=100.00, sl=99.50, tp=[101.00], maks_bar=3,
        masuk_taker=True, keluar_sl_taker=True,
    )
    b = Biaya(fee_taker=0.0005, fee_maker=0.0002, sl_slippage_pct=0.0005,
              masuk_slippage_pct=0.0, funding_laju_per_stempel=0.0)
    x = simulasi_trade(r, ts, o, h, l, c, b)

    assert x.sebab_keluar == "sl"
    assert x.idx_keluar == 2
    assert x.jalur_ambigu is False
    assert x.cacah_bar_ambigu == 0
    assert abs(x.r_harga - 0.50) < TOL
    assert abs(x.harga_keluar_isi - 99.450250) < TOL
    assert abs(x.mfe_harga - 0.35) < TOL
    assert abs(x.mfe_r - 0.70) < TOL
    assert abs(x.mfe_frac_tp1 - 0.35) < TOL
    assert x.bar_ke_puncak_mfe == 1
    assert x.bar_puncak_ke_keluar == 1
    assert abs(x.r_kotor - (-1.0995)) < TOL
    assert abs(x.biaya_fee_r - 0.19945025) < TOL
    assert x.cacah_stempel_funding == 0
    assert abs(x.biaya_funding_r - 0.0) < TOL
    assert abs(x.r_bersih - (-1.29895025)) < TOL
    assert x.pernah_floating_profit is True
    assert x.tanggal_utc == "2026-01-01"
    assert klasifikasi(x) == "M3A"


def test_mfe_ikut_bar_keluar_menggelembungkan_m3a():
    """Bukti bahwa pilihan asumsi bisa MEMPERCANTIK M-3A. Karena itu default
    pesimistis, dan kedua varian wajib dilaporkan berpasangan."""
    ts, o, h, l, c = _pasar()
    r = Rencana("UJICOBAUSDT", "tangan_v1", 1, 0, 100.00, 99.50, [101.00], 3)
    b = Biaya()
    pesimis = simulasi_trade(r, ts, o, h, l, c, b, mfe_ikut_bar_keluar=False)
    optimis = simulasi_trade(r, ts, o, h, l, c, b, mfe_ikut_bar_keluar=True)
    assert abs(pesimis.mfe_harga - 0.35) < TOL
    assert abs(optimis.mfe_harga - 0.40) < TOL  # h bar 2 = 100.40
    assert optimis.mfe_r > pesimis.mfe_r
    assert abs(pesimis.r_bersih - optimis.r_bersih) < TOL  # P&L tidak berubah


def test_ambiguitas_intrabar_pesimistis():
    """SL dan TP1 di bar yang sama -> SL menang, dan trade DICAP ambigu."""
    ts = np.array([T0, T0 + 60_000], dtype=np.int64)
    o = np.array([100.00, 100.00])
    h = np.array([100.10, 101.50])   # menembus tp1 101.00
    l = np.array([99.90, 99.00])     # menembus sl 99.50
    c = np.array([100.00, 100.50])
    r = Rencana("UJICOBAUSDT", "ambigu", 1, 0, 100.00, 99.50, [101.00], 2)
    x = simulasi_trade(r, ts, o, h, l, c, Biaya())
    assert x.sebab_keluar == "sl"
    assert x.jalur_ambigu is True
    assert x.cacah_bar_ambigu == 1
    assert x.r_bersih < 0


def test_short_simetris():
    ts = np.array([T0, T0 + 60_000], dtype=np.int64)
    o = np.array([100.00, 99.80])
    h = np.array([100.10, 99.90])
    l = np.array([99.80, 98.90])   # tp1 = 99.00 kena
    c = np.array([99.80, 99.00])
    r = Rencana("UJICOBAUSDT", "short", -1, 0, 100.00, 100.50, [99.00], 2,
                keluar_tp_taker=False)
    x = simulasi_trade(r, ts, o, h, l, c, Biaya())
    assert x.sebab_keluar == "tp1"
    assert abs(x.r_harga - 0.50) < TOL
    assert abs(x.r_kotor - 2.0) < TOL   # (100.00-99.00)/0.50
    # fee: masuk taker 100*0.0005=0.05 ; keluar maker 99*0.0002=0.0198
    assert abs(x.biaya_fee_r - (0.05 + 0.0198) / 0.50) < TOL
    assert x.r_bersih > 0


def test_stempel_funding_nol_bila_tak_melewati():
    """Posisi yang tidak melewati stempel settlement membayar NOL PERSIS."""
    ts = np.array([T0 + 3_600_000, T0 + 3_660_000], dtype=np.int64)  # 01:00 UTC
    o = np.array([100.00, 100.00])
    h = np.array([101.50, 101.50])
    l = np.array([99.90, 99.90])
    c = np.array([101.00, 101.00])
    r = Rencana("UJICOBAUSDT", "funding", 1, 0, 100.00, 99.50, [101.00], 2)
    b = Biaya(funding_laju_per_stempel=0.0001)
    x = simulasi_trade(r, ts, o, h, l, c, b)
    assert x.cacah_stempel_funding == 0
    assert x.biaya_funding_r == 0.0


def test_stempel_funding_dihitung_bila_melewati():
    n = 600  # 10 jam bar 1m mulai 01:00 UTC -> melewati 08:00 UTC
    ts = (T0 + 3_600_000 + np.arange(n, dtype=np.int64) * 60_000)
    o = np.full(n, 100.00)
    h = np.full(n, 100.10)
    l = np.full(n, 99.90)
    c = np.full(n, 100.00)
    r = Rencana("UJICOBAUSDT", "funding", 1, 0, 100.00, 99.50, [101.00], n)
    b = Biaya(funding_laju_per_stempel=0.0001)
    x = simulasi_trade(r, ts, o, h, l, c, b)
    assert x.sebab_keluar == "horizon"
    assert x.cacah_stempel_funding == 1
    assert abs(x.biaya_funding_r - (1 * 100.00 * 0.0001) / 0.50) < TOL


def test_mode_sinyal_swing_nol_funding():
    """Swing = mode 'sinyal' = asumsi SPOT = NOL funding perpetual, eksplisit."""
    n = 600
    ts = (T0 + 3_600_000 + np.arange(n, dtype=np.int64) * 60_000)
    o = np.full(n, 100.00); h = np.full(n, 100.10)
    l = np.full(n, 99.90); c = np.full(n, 100.00)
    r = Rencana("UJICOBAUSDT", "swing", 1, 0, 100.00, 99.50, [101.00], n,
                mode="sinyal")
    x = simulasi_trade(r, ts, o, h, l, c, Biaya(funding_laju_per_stempel=0.0001))
    assert x.mode == "sinyal"
    assert x.cacah_stempel_funding == 0
    assert x.biaya_funding_r == 0.0
