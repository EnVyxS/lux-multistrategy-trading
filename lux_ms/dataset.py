"""Sumber dataset: aset rilis parquet 1m milik lux-ai-research.

PATOKAN tetap `EnVyxS/lux-multistrategy-trading`. Repo `lux-ai-research` di sini
dipakai HANYA sebagai SUMBER BYTE (dataset), bukan sebagai patokan angka. Setiap
angka yang lahir dari dataset ini WAJIB diukur ulang di repo patokan, dan mewarisi
B-1 (gerbang penyebut ENAM klausa dengan dasar keputusan LIMA) serta B-5 (dua
penyebut simbol 787 & 937).

## Fakta TERUKUR sesi ini (via GitHub API, bukan tebakan)

- Pohon git `lux-ai-research` TIDAK memuat direktori `data/`. Parquet 1m TIDAK ada
  di dalam repo; ia hidup sebagai ASET RILIS (tar terbelah + SHA256SUMS), sesuai
  `lux_ai/serapan/rilis.py` (ADR-A006 keputusan 3, batas bagian 1.800.000.000 B).
- Run serapan termuda yang punya rilis: `30396803601` (2026-07-28).
  Commit yang dicatat di badan rilis: `57a04f1ea18570f4aa8bce0abee650ea97d374fa`.
- Pecahan 1 dan 7 pada run itu ADA dan terverifikasi lewat API. Badan rilis
  keduanya berbunyi "pecahan N/8".
- Tag `serapan-pecahan-8-30396803601` mengembalikan **404**. Jadi klaim "dataset
  lengkap" BELUM TERBUKTI untuk 8/8 pecahan; yang terbukti baru sebagian.
  Status kelengkapan: **BELUM DIUKUR** sampai pecahan 2..6 dan 8 dicek satu-satu.

## Sidik yang sudah dicatat (dari API, boleh dipakai sebagai gerbang unduhan)

Dipakai `gerbang_sidik()` untuk menolak byte yang tidak cocok. Sidik yang belum
dicatat di sini TIDAK boleh dianggap sah; unduhannya wajib diverifikasi terhadap
aset `SHA256SUMS` di rilis yang sama.

Aturan yang ditegakkan: 24 (medan penggugur), 38 (nilai basi ditolak),
52 (byte dibaca ulang, bukan dipercaya dari commit), 94 (angka tanpa status =
pelanggaran).
"""

from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

OWNER_SUMBER = "EnVyxS"
REPO_SUMBER = "lux-ai-research"  # SUMBER BYTE, BUKAN PATOKAN ANGKA
RUN_SERAPAN = "30396803601"
COMMIT_SERAPAN = "57a04f1ea18570f4aa8bce0abee650ea97d374fa"
PECAHAN_DIHARAP = tuple(range(1, 9))  # badan rilis berbunyi "pecahan N/8"
PECAHAN_TERBUKTI_ADA = (1, 7)  # TERUKUR via API sesi ini
PECAHAN_TERBUKTI_TIADA = (8,)  # 404 TERUKUR via API sesi ini
PECAHAN_BELUM_DICEK = (2, 3, 4, 5, 6)

POLA_TAG = "serapan-pecahan-{pecahan}-{run}"
POLA_ASET = "pecahan_{pecahan}.part{bagian:02d}.tar"
POLA_ASET_KARANTINA = "pecahan_{pecahan}_karantina.part{bagian:02d}.tar"
NAMA_SUMS = "SHA256SUMS"
BASIS_UNDUH = "https://github.com/" + "{owner}/{repo}/releases/download/{tag}/{nama}"
POTONG_BACA = 1024 * 1024

# Sidik TERUKUR dari API GitHub (digest aset). Kunci: (pecahan, nama aset).
SIDIK_TERUKUR: Dict[str, str] = {
    "pecahan_1.part01.tar": "dd7867001dbbf4ef1b7425938a3c3dda5163dfcba080d96908d0f5a5fcd50a5c",
    "pecahan_1.part02.tar": "9c01389d33f38d55a764e81ffc91c08f8d9c15605d2116c84cb3914d5d5fe7b5",
    "pecahan_1.part03.tar": "97c054402886e923b858f781c39a1d493325e1b7f4a6952970756950b2292a08",
    "pecahan_1_karantina.part01.tar": "f2377bf557528853c91395638fa41c108c09e4b70b0a284224bec25de2c48ba8",
    "pecahan_7.part01.tar": "cde0044705ee09ad37b2e851f922e5434772dc632e3107dc525eb4c8824b6ac0",
    "pecahan_7.part02.tar": "be3ad5eaf484b38bf9d6d9dd9c7498ed4686f644800ecc915da2db277e8d4c5d",
    "pecahan_7.part03.tar": "16c28d8aeec3a3f399ff4e4e41c678018ca6bf4a78cc6129f30343acc1e54773",
    "pecahan_7_karantina.part01.tar": "f34d3080f23d5ec704c7236ae473fc8e75ec4486841e046d7c647eb19d9b77fa",
}

# Byte TERUKUR dari API (ukuran aset). Medan penggugur kedua di samping sidik.
BYTE_TERUKUR: Dict[str, int] = {
    "pecahan_1.part01.tar": 1_799_168_000,
    "pecahan_1.part02.tar": 1_799_352_320,
    "pecahan_1.part03.tar": 675_870_720,
    "pecahan_1_karantina.part01.tar": 3_174_400,
    "pecahan_7.part01.tar": 1_798_277_120,
    "pecahan_7.part02.tar": 1_799_618_560,
    "pecahan_7.part03.tar": 281_640_960,
    "pecahan_7_karantina.part01.tar": 1_095_680,
}


def tag_pecahan(pecahan: int, run: str = RUN_SERAPAN) -> str:
    return POLA_TAG.format(pecahan=int(pecahan), run=run)


def url_aset(nama: str, pecahan: int, run: str = RUN_SERAPAN) -> str:
    return BASIS_UNDUH.format(
        owner=OWNER_SUMBER,
        repo=REPO_SUMBER,
        tag=tag_pecahan(pecahan, run),
        nama=nama,
    )


def nama_bagian(pecahan: int, bagian: int, karantina: bool = False) -> str:
    pola = POLA_ASET_KARANTINA if karantina else POLA_ASET
    return pola.format(pecahan=int(pecahan), bagian=int(bagian))


def sha256_berkas(jalur: Path) -> str:
    h = hashlib.sha256()
    with open(jalur, "rb") as f:
        for bongkah in iter(lambda: f.read(POTONG_BACA), b""):
            h.update(bongkah)
    return h.hexdigest()


def baca_sums(jalur: Path) -> Dict[str, str]:
    """Baca berkas format `sha256sum`: sidik, dua spasi, nama."""
    peta: Dict[str, str] = {}
    for baris in Path(jalur).read_text(encoding="utf-8").splitlines():
        baris = baris.strip()
        if not baris:
            continue
        bagian = baris.split()
        if len(bagian) < 2:
            raise ValueError(f"baris SHA256SUMS tak berbentuk: {baris!r}")
        peta[bagian[-1]] = bagian[0]
    return peta


def gerbang_sidik(jalur: Path, sidik_harap: Optional[str] = None) -> Dict[str, Any]:
    """Verifikasi satu aset. Sidik yang tak diketahui TIDAK dianggap lulus.

    Prioritas sumber sidik: argumen `sidik_harap` (misalnya dari SHA256SUMS rilis),
    lalu `SIDIK_TERUKUR`. Bila keduanya tidak ada, hasilnya `lulus=False` dengan
    `sebab="sidik tidak diketahui"` — bukan `True` (aturan 24).
    """
    jalur = Path(jalur)
    if not jalur.exists():
        return {"nama": jalur.name, "lulus": False, "sebab": "berkas tidak ada"}
    nama = jalur.name
    harap = sidik_harap or SIDIK_TERUKUR.get(nama)
    nyata = sha256_berkas(jalur)
    byte_nyata = int(jalur.stat().st_size)
    byte_harap = BYTE_TERUKUR.get(nama)
    if harap is None:
        return {
            "nama": nama,
            "lulus": False,
            "sebab": "sidik tidak diketahui",
            "sha256_nyata": nyata,
            "byte_nyata": byte_nyata,
        }
    return {
        "nama": nama,
        "lulus": nyata == harap and (byte_harap is None or byte_nyata == byte_harap),
        "sha256_harap": harap,
        "sha256_nyata": nyata,
        "byte_harap": byte_harap,
        "byte_nyata": byte_nyata,
        "sebab": None if nyata == harap else "sidik tidak cocok",
    }


def bongkar(jalur_tar: Path, akar: Path) -> Dict[str, Any]:
    """Bongkar satu bagian tar ke `akar`; jalur `data/parquet/<simbol>/` pulih.

    Anggota dengan jalur mutlak atau yang keluar dari `akar` DITOLAK.
    """
    jalur_tar = Path(jalur_tar)
    akar = Path(akar)
    akar.mkdir(parents=True, exist_ok=True)
    dibongkar: List[str] = []
    ditolak: List[str] = []
    with tarfile.open(jalur_tar, "r") as tar:
        for m in tar.getmembers():
            if not m.isfile():
                continue
            p = Path(m.name)
            if p.is_absolute() or ".." in p.parts:
                ditolak.append(m.name)
                continue
            tar.extract(m, path=str(akar))
            dibongkar.append(m.name)
    return {
        "tar": jalur_tar.name,
        "cacah_dibongkar": len(dibongkar),
        "cacah_ditolak": len(ditolak),
        "nama_ditolak": ditolak[:20],
        "sah": not ditolak,
    }


def daftar_simbol(akar: Path, sub: str = "data/parquet") -> List[str]:
    dasar = Path(akar) / sub
    if not dasar.exists():
        return []
    return sorted(p.name for p in dasar.iterdir() if p.is_dir())


def berkas_parquet(akar: Path, simbol: str, sub: str = "data/parquet") -> List[Path]:
    dasar = Path(akar) / sub / simbol
    if not dasar.exists():
        return []
    return sorted(dasar.rglob("*.parquet"))


KOLOM_WAJIB = ("open_time", "open", "high", "low", "close", "volume")


def muat_1m(
    akar: Path,
    simbol: str,
    kolom: Sequence[str] = KOLOM_WAJIB,
    sub: str = "data/parquet",
) -> Dict[str, Any]:
    """Muat klines 1m satu simbol dari parquet yang sudah dibongkar.

    Tidak menebak nama kolom: bila skema parquet tidak memuat `KOLOM_WAJIB`,
    fungsi ini MENGEMBALIKAN skema yang benar-benar ada dengan `lulus=False`
    supaya nama kolom nyata diukur, bukan diasumsikan.
    """
    import pandas as pd  # pandas ada di runner; sandbox tanpa jaringan tak dipakai

    berkas = berkas_parquet(akar, simbol, sub=sub)
    if not berkas:
        return {"simbol": simbol, "lulus": False, "sebab": "tidak ada parquet"}
    contoh = pd.read_parquet(berkas[0])
    ada = list(contoh.columns)
    hilang = [k for k in kolom if k not in ada]
    if hilang:
        return {
            "simbol": simbol,
            "lulus": False,
            "sebab": "kolom wajib tidak ada",
            "kolom_hilang": hilang,
            "kolom_nyata": ada,
            "berkas_contoh": str(berkas[0]),
        }
    bingkai = pd.concat(
        [pd.read_parquet(b, columns=list(kolom)) for b in berkas], ignore_index=True
    )
    bingkai = bingkai.sort_values("open_time", kind="mergesort").reset_index(drop=True)
    ts = bingkai["open_time"].to_numpy()
    naik = bool((ts[1:] > ts[:-1]).all()) if len(ts) > 1 else True
    return {
        "simbol": simbol,
        "lulus": True,
        "cacah_berkas": len(berkas),
        "cacah_baris": int(len(bingkai)),
        "ts_menaik_ketat": naik,
        "ts_awal": int(ts[0]) if len(ts) else None,
        "ts_akhir": int(ts[-1]) if len(ts) else None,
        "bingkai": bingkai,
    }


def laporan_kelengkapan(pecahan_terbukti: Iterable[int] = PECAHAN_TERBUKTI_ADA) -> Dict[str, Any]:
    """Status kelengkapan dataset, dengan status utang eksplisit (aturan 94)."""
    ada = sorted(set(int(p) for p in pecahan_terbukti))
    return {
        "run_serapan": RUN_SERAPAN,
        "commit_serapan": COMMIT_SERAPAN,
        "pecahan_diharap": list(PECAHAN_DIHARAP),
        "pecahan_terbukti_ada": ada,
        "pecahan_terbukti_tiada": list(PECAHAN_TERBUKTI_TIADA),
        "pecahan_belum_dicek": list(PECAHAN_BELUM_DICEK),
        "status": "BELUM DIUKUR",
        "sebab": (
            "tag serapan-pecahan-8-30396803601 mengembalikan 404 dan pecahan 2..6 "
            "belum dicek satu-satu; klaim 'dataset lengkap' belum bisa disahkan"
        ),
        "warisan": (
            "angka apa pun dari dataset ini mewarisi B-1 dan B-5 dan wajib diukur "
            "ulang di repo patokan sebelum jadi dasar keputusan"
        ),
    }


def tulis_laporan(jalur: Path, isi: Dict[str, Any]) -> Path:
    jalur = Path(jalur)
    jalur.parent.mkdir(parents=True, exist_ok=True)
    jalur.write_text(json.dumps(isi, ensure_ascii=False, indent=2), encoding="utf-8")
    return jalur
