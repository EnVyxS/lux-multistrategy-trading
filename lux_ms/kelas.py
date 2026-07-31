"""Pemisahan kelas kegagalan M-3A dan M-3B. TIDAK BOLEH dicampur satu metrik.

M-3A BALIK-SEBELUM-TP : r_bersih < 0, MFE > 0, MFE < jarak ke TP1.
M-3B SL-PREMATUR      : keluar karena SL, lalu harga lanjut menembus TP1
                        dalam horizon lanjutan (counterfactual eksplisit).

Setiap ringkasan WAJIB menyertakan cacah jalur ambigu. Fungsi di sini akan
menolak menghasilkan ringkasan M-3A tanpa medan ambigu.
"""
from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np

AMBANG_MFE_R = (0.3, 0.5, 0.8)


def klasifikasi(hasil, lanjutan: dict | None = None) -> str:
    """Kembalikan satu label: 'M3A', 'M3B', 'menang', 'rugi_lain', 'horizon'."""
    if hasil.sebab_keluar == "sl":
        if lanjutan is not None and lanjutan.get("tp1_tercapai"):
            return "M3B"
    if hasil.r_bersih < 0:
        jarak_tp1 = abs(hasil.tp1 - hasil.harga_masuk_isi)
        if hasil.mfe_harga > 0 and hasil.mfe_harga < jarak_tp1:
            return "M3A"
        return "rugi_lain"
    if hasil.sebab_keluar == "horizon":
        return "horizon"
    return "menang"


def _kuantil(x: np.ndarray, q: Sequence[float]) -> Dict[str, float]:
    if x.size == 0:
        return {f"p{int(qq*100)}": float("nan") for qq in q}
    return {f"p{int(qq*100)}": float(np.quantile(x, qq)) for qq in q}


def ringkas_m3a(hasil_list: List, lanjutan_list: List[dict] | None = None) -> dict:
    """Laporan M-3A lengkap. Selalu membawa cacah ambigu (Aturan wajib)."""
    n = len(hasil_list)
    lanjutan_list = lanjutan_list or [None] * n
    label = [klasifikasi(h, l) for h, l in zip(hasil_list, lanjutan_list)]

    m3a = [h for h, lb in zip(hasil_list, label) if lb == "M3A"]
    rugi = [h for h in hasil_list if h.r_bersih < 0]

    mfe_r = np.array([h.mfe_r for h in m3a], dtype=np.float64)
    mfe_frac = np.array([h.mfe_frac_tp1 for h in m3a], dtype=np.float64)
    t_puncak = np.array([h.bar_ke_puncak_mfe for h in m3a], dtype=np.float64)
    t_sisa = np.array([h.bar_puncak_ke_keluar for h in m3a], dtype=np.float64)

    # P(TP1 | MFE >= ambang) atas SELURUH trade, bukan hanya M-3A.
    semua_mfe = np.array([h.mfe_r for h in hasil_list], dtype=np.float64)
    kena_tp1 = np.array([h.sebab_keluar == "tp1" for h in hasil_list], dtype=bool)
    p_tp1 = {}
    for a in AMBANG_MFE_R:
        m = semua_mfe >= a
        p_tp1[f"MFE>={a}R"] = {
            "n": int(m.sum()),
            "p_tp1": (float(kena_tp1[m].mean()) if m.sum() else float("nan")),
        }

    hist_r_tepi = [0.0, 0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0, np.inf]
    hist_frac_tepi = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]

    return {
        "cacah_trade_total": n,
        "cacah_trade_rugi": len(rugi),
        "cacah_M3A": len(m3a),
        "porsi_M3A_dari_rugi": (len(m3a) / len(rugi) if rugi else float("nan")),
        "porsi_rugi_pernah_floating_profit": (
            float(np.mean([h.pernah_floating_profit for h in rugi])) if rugi else float("nan")
        ),
        "histogram_mfe_R": {
            "tepi": [str(t) for t in hist_r_tepi],
            "cacah": np.histogram(mfe_r, bins=hist_r_tepi)[0].tolist() if mfe_r.size else [],
        },
        "histogram_mfe_frac_tp1": {
            "tepi": hist_frac_tepi,
            "cacah": np.histogram(mfe_frac, bins=hist_frac_tepi)[0].tolist() if mfe_frac.size else [],
        },
        "kuantil_mfe_R": _kuantil(mfe_r, (0.25, 0.5, 0.75, 0.9)),
        "kuantil_mfe_frac_tp1": _kuantil(mfe_frac, (0.25, 0.5, 0.75, 0.9)),
        "bar_ke_puncak_mfe": _kuantil(t_puncak, (0.5, 0.9)),
        "bar_puncak_ke_penutupan": _kuantil(t_sisa, (0.5, 0.9)),
        "P_TP1_bersyarat_MFE": p_tp1,
        # WAJIB, tanpa ini angka M-3A tidak sah dilaporkan:
        "cacah_jalur_ambigu": int(sum(1 for h in hasil_list if h.jalur_ambigu)),
        "cacah_jalur_ambigu_di_M3A": int(sum(1 for h in m3a if h.jalur_ambigu)),
        "asumsi_intrabar": "pesimistis: SL menang bila SL dan TP di bar yang sama",
    }


def ringkas_m3b(hasil_list: List, lanjutan_list: List[dict]) -> dict:
    """Laporan M-3B. Vonis eksplisit atas klaim 'porsinya kecil'."""
    sl = [(h, l) for h, l in zip(hasil_list, lanjutan_list) if h.sebab_keluar == "sl"]
    m3b = [(h, l) for h, l in sl if l and l.get("tp1_tercapai")]
    lewat = np.array([l["excursion_lewat_sl_r"] for _, l in m3b], dtype=np.float64)
    waktu = np.array(
        [l["bar_ke_tp1"] for _, l in m3b if l["bar_ke_tp1"] is not None], dtype=np.float64
    )
    porsi = (len(m3b) / len(sl)) if sl else float("nan")
    return {
        "cacah_keluar_SL": len(sl),
        "cacah_M3B": len(m3b),
        "porsi_M3B_dari_SL": porsi,
        "excursion_lewat_SL_dalam_R": _kuantil(lewat, (0.5, 0.9)),
        "bar_ke_TP1_hipotetis": _kuantil(waktu, (0.5, 0.9)),
        "cacah_jalur_ambigu_di_M3B": int(sum(1 for h, _ in m3b if h.jalur_ambigu)),
        "vonis_klaim_operator_porsinya_kecil": (
            "BELUM DIUKUR (tanpa trade)" if not sl else
            ("DIDUKUNG" if porsi < 0.10 else ("DIBANTAH" if porsi > 0.25 else "TAK KONKLUSIF"))
        ),
        "catatan": "M-3B adalah counterfactual pasca-keluar; tidak masuk P&L.",
    }


def tabel_trade_off(sebelum: dict, sesudah: dict) -> dict:
    """Setiap usulan WAJIB dinilai terhadap KEDUA kelas sekaligus."""
    return {
        "delta_ekspektasi_R_bersih": sesudah["ekspektasi_R_bersih"] - sebelum["ekspektasi_R_bersih"],
        "delta_win_rate": sesudah["win_rate"] - sebelum["win_rate"],
        "delta_porsi_M3A": sesudah["porsi_M3A_dari_rugi"] - sebelum["porsi_M3A_dari_rugi"],
        "delta_porsi_M3B": sesudah["porsi_M3B_dari_SL"] - sebelum["porsi_M3B_dari_SL"],
        "vonis": (
            "DITOLAK: win rate naik tapi ekspektasi R turun"
            if sesudah["win_rate"] > sebelum["win_rate"]
            and sesudah["ekspektasi_R_bersih"] <= sebelum["ekspektasi_R_bersih"]
            else (
                "DITOLAK: kerugian dipindah ke kelas lain"
                if sesudah["ekspektasi_R_bersih"] > sebelum["ekspektasi_R_bersih"]
                and sesudah["porsi_M3B_dari_SL"] > sebelum["porsi_M3B_dari_SL"]
                else "LAYAK LANJUT KE OOS"
            )
        ),
    }
