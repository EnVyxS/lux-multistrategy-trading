"""Pengukur B0 di GitHub Actions: unduh -> sidik -> bongkar -> pindai -> lapor.

Satu pecahan per job. Tidak ada satu pun angka yang diterbitkan berkas ini
tanpa status utang; bila gerbang sidik gagal, job GAGAL dan tidak ada laporan
hasil yang ditulis. Sandbox tanpa jaringan, jadi berkas ini hanya bisa berjalan
sungguhan di runner.

Parameter `--min-rr`, `--min-gap-r`, `--fallback-rr` WAJIB diberikan; nilai
legacy per-strategi BELUM DIUKUR dan tidak boleh ditebak (ParamB0.wajib_terisi).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

from lux_ms import baseline_b0 as b0
from lux_ms import dataset as ds
from lux_ms import kelas
from lux_ms.eksekusi import Biaya, excursion_lanjutan


def argumen(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--indeks", type=int, required=True, help="indeks pecahan 0..7")
    p.add_argument("--akar-rilis", default="data/rilis")
    p.add_argument("--akar-bongkar", default=".")
    p.add_argument("--batas-simbol", type=int, default=0, help="0 = semua simbol")
    p.add_argument("--min-rr", type=float, required=True)
    p.add_argument("--min-gap-r", type=float, required=True)
    p.add_argument("--fallback-rr", type=float, required=True)
    p.add_argument("--maks-bar", type=int, default=1440)
    p.add_argument("--bar-pemanasan", type=int, default=120)
    p.add_argument("--hapus-tar", action="store_true", help="hemat cakram runner")
    p.add_argument("--hanya-laporan", action="store_true", help="tanpa data; uji asap")
    p.add_argument("--keluaran", default="")
    return p.parse_args(argv)


def tahap_sidik(a) -> Dict[str, Any]:
    """Verifikasi byte SEBELUM apa pun dibongkar. Gagal = berhenti."""
    ds.gerbang_indeks(a.indeks)
    jalur_sums = os.path.join(a.akar_rilis, ds.NAMA_SUMS)
    if not os.path.exists(jalur_sums):
        return {"lulus": False, "sebab": f"{ds.NAMA_SUMS} tidak ada di {a.akar_rilis}"}
    sums = ds.baca_sums(jalur_sums)
    laporan: List[Dict[str, Any]] = []
    lulus = True
    for nama in sorted(sums):
        jalur = os.path.join(a.akar_rilis, nama)
        g = ds.gerbang_sidik(jalur, sums)
        laporan.append(g)
        lulus = lulus and bool(g.get("lulus"))
    g_sums = ds.gerbang_sidik(jalur_sums, None)
    return {
        "lulus": lulus,
        "tag": ds.tag_pecahan(a.indeks),
        "cacah_aset_di_sums": len(sums),
        "aset": laporan,
        "sums_itu_sendiri": g_sums,
        "sidik_sums_terukur_sesi_ini": ds.SIDIK_SUMS_TERUKUR.get(a.indeks, "BELUM DIUKUR"),
    }


def tahap_bongkar(a, sidik: Dict[str, Any]) -> Dict[str, Any]:
    hasil = []
    for g in sidik["aset"]:
        nama = g.get("nama", "")
        if not nama.endswith(".tar"):
            continue
        jalur = os.path.join(a.akar_rilis, nama)
        r = ds.bongkar(jalur, a.akar_bongkar)
        hasil.append(r)
        if a.hapus_tar:
            os.remove(jalur)
    return {
        "lulus": all(r["lulus"] for r in hasil) and bool(hasil),
        "bagian": hasil,
        "tar_dihapus_setelah_bongkar": bool(a.hapus_tar),
    }


def ukur_satu_simbol(simbol: str, a, param: b0.ParamB0) -> Dict[str, Any]:
    berkas = ds.berkas_parquet(simbol, a.akar_bongkar)
    muat = ds.muat_1m(berkas)
    if not muat["lulus"]:
        return {"simbol": simbol, "lulus_muat": False, "muat": muat}
    df = muat["df"]
    ts = [int(x) for x in df["open_time"].tolist()]
    o = [float(x) for x in df["open"].tolist()]
    h = [float(x) for x in df["high"].tolist()]
    l = [float(x) for x in df["low"].tolist()]
    c = [float(x) for x in df["close"].tolist()]
    v = [float(x) for x in df["volume"].tolist()]
    del df

    lap = b0.jalankan_b0(simbol, ts, o, h, l, c, v, param, Biaya(), satu_posisi=True)
    hasil = lap["hasil"]
    lanjutan = [excursion_lanjutan(r, ts, h, l) for r in hasil]
    return {
        "simbol": simbol,
        "lulus_muat": True,
        "cacah_baris": muat["cacah_baris"],
        "cacah_berkas": muat["cacah_berkas"],
        "cacah_duplikat_dibuang": muat["cacah_duplikat_dibuang"],
        "open_time_awal": muat["open_time_awal"],
        "open_time_akhir": muat["open_time_akhir"],
        "kolom": muat["kolom"],
        "corong": lap["corong"],
        "cacah_trade": lap["cacah_trade"],
        "m3a": kelas.ringkas_m3a(hasil, lanjutan),
        "m3b": kelas.ringkas_m3b(hasil, lanjutan),
    }


def main(argv=None) -> int:
    a = argumen(argv)
    mulai = time.time()
    param = b0.ParamB0(
        min_rr=a.min_rr,
        min_gap_r=a.min_gap_r,
        fallback_rr=a.fallback_rr,
        maks_bar=a.maks_bar,
        bar_pemanasan=a.bar_pemanasan,
    )
    param.wajib_terisi()

    laporan: Dict[str, Any] = {
        "bukan_bukti": False,
        "peran_berkas": "pengukur; bukan patokan hasil sampai sidik byte LULUS",
        "indeks_pecahan": a.indeks,
        "tag": ds.tag_pecahan(a.indeks),
        "run_serapan": ds.RUN_SERAPAN,
        "commit_serapan": ds.COMMIT_SERAPAN,
        "param": {
            "min_rr": a.min_rr,
            "min_gap_r": a.min_gap_r,
            "fallback_rr": a.fallback_rr,
            "maks_bar": a.maks_bar,
            "bar_pemanasan": a.bar_pemanasan,
            "status_param": (
                "min_rr/min_gap_r/fallback_rr DIBERIKAN OPERATOR; nilai legacy "
                "per-strategi (_min_rr_eff, min_tp_gap_r, _fallback_rr) BELUM DIUKUR"
            ),
        },
        "label_sl": b0.LABEL_SL,
        "kelengkapan_dataset": ds.laporan_kelengkapan(),
        "status_angka": (
            "Angka corong dan M-3A/M-3B di bawah adalah BATAS ATAS: gerbang "
            "trendline_min_htf_score=3 belum diport dan SL memakai " + b0.LABEL_SL
            + ". Bukan replikasi legacy."
        ),
    }

    if a.hanya_laporan:
        laporan["tahap"] = "hanya-laporan (tanpa data, uji asap)"
        keluaran = a.keluaran or f"reports/b0_pecahan{a.indeks}_status.json"
        ds.tulis_laporan(keluaran, laporan)
        print(json.dumps({"lulus": True, "keluaran": keluaran}, ensure_ascii=False))
        return 0

    sidik = tahap_sidik(a)
    laporan["sidik"] = sidik
    if not sidik["lulus"]:
        laporan["vonis"] = "GAGAL SIDIK: byte tidak terverifikasi, pengukuran DIBATALKAN"
        ds.tulis_laporan(
            a.keluaran or f"reports/b0_pecahan{a.indeks}_status.json", laporan
        )
        print("GAGAL SIDIK", file=sys.stderr)
        return 2

    laporan["bongkar"] = tahap_bongkar(a, sidik)
    if not laporan["bongkar"]["lulus"]:
        laporan["vonis"] = "GAGAL BONGKAR"
        ds.tulis_laporan(
            a.keluaran or f"reports/b0_pecahan{a.indeks}_status.json", laporan
        )
        return 3

    simbol_ada = ds.daftar_simbol(a.akar_bongkar)
    laporan["simbol"] = {
        "cacah_simbol_dibongkar": len(simbol_ada),
        "contoh": simbol_ada[:10],
        "catatan_pembagian": (
            "simbol_pecahan_lokal hanya bisa memeriksa keanggotaan bila daftar "
            "simbol SEMESTA tersedia; di job satu pecahan daftar itu tidak ada, "
            "jadi pemeriksaan round-robin i%8 tetap BELUM DIUKUR di sini."
        ),
    }

    dipakai = simbol_ada if a.batas_simbol <= 0 else simbol_ada[: a.batas_simbol]
    per_simbol: List[Dict[str, Any]] = []
    corong_total: Dict[str, int] = {}
    for s in dipakai:
        r = ukur_satu_simbol(s, a, param)
        per_simbol.append(r)
        for k, val in (r.get("corong") or {}).items():
            corong_total[k] = corong_total.get(k, 0) + int(val)
        print(f"[selesai] {s} trade={r.get('cacah_trade')}", flush=True)

    laporan["cacah_simbol_diukur"] = len(per_simbol)
    laporan["corong_total"] = corong_total
    laporan["per_simbol"] = per_simbol
    laporan["detik"] = round(time.time() - mulai, 3)
    keluaran = a.keluaran or f"reports/b0_pecahan{a.indeks}_status.json"
    ds.tulis_laporan(keluaran, laporan)
    print(json.dumps({"lulus": True, "keluaran": keluaran}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
