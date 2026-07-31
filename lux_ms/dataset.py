"""Sumber byte dataset 1m: aset rilis `EnVyxS/lux-ai-research`.

STATUS PATOKAN. Repo ini (`lux-multistrategy-trading`) adalah SATU-SATUNYA
patokan. `lux-ai-research` dipakai HANYA sebagai sumber byte parquet dan
sebagai rujukan bacaan; tidak satu pun angka hasil dari sana boleh dikutip
sebagai hasil modul ini tanpa diukur ulang di sini.

KOREKSI 22 (kesalahan agen, sesi 2026-08-01)
--------------------------------------------
Versi pertama berkas ini memakai indeks pecahan 1..8 dan menyimpulkan
"pecahan 8 tidak ada" dari 404 tag `serapan-pecahan-8-30396803601`.
Itu SALAH. `lux_ai/serapan/pecahan.py` (SHA f1b49f1b8796886ddb8e0a7f30beeb07d0ed8183)
memberi `simbol_pecahan(..., indeks, total=8)` dengan gerbang
`0 <= indeks < total`, jadi indeks sah adalah 0..7. Tag `...-pecahan-8-...`
memang tidak pernah ada, dan 404 itu BUKAN bukti dataset tidak lengkap.
Kesimpulan lama dibatalkan; kesimpulan baru diukur ulang di bawah.

STATUS KELENGKAPAN (diukur sesi ini lewat GitHub API)
-----------------------------------------------------
TERUKUR: kedelapan tag `serapan-pecahan-{0..7}-30396803601` ADA
(`list_releases`, 31 rilis, 2026-07-28). Pecahan 0, 1, 7 sudah dibuka penuh
daftar asetnya; digest + byte-nya direkam di `SIDIK_TERUKUR`/`BYTE_TERUKUR`.
BELUM DIUKUR: kecocokan sha256 isi tar (butuh unduh; sandbox tanpa jaringan),
cacah simbol/berkas parquet nyata per pecahan, dan cacah baris.
Jadi "lengkap di tingkat metadata rilis" SAH; "lengkap di tingkat byte" masih
utang, dan hanya run Actions yang boleh menutupnya (aturan 24: klaim
persistensi diikat pada pembacaan ulang).

SKEMA PARQUET (TERUKUR dari kode sumber, bukan dari byte)
---------------------------------------------------------
`lux_ai/serapan/klines.py` (SHA cc4d9287ccb7a8ea72380399c334b4d19b5301d3):
`KOLOM_SIMPAN = KOLOM[:-1]`, yaitu 11 kolom tanpa `ignore`. `open_time`
bertipe Int64 hasil `rapikan()`, urut menaik, `open_time` unik.
Status: TERUKUR-DARI-KODE. Belum TERUKUR-DARI-BYTE sampai satu parquet nyata
dibaca di runner; `muat_1m` tetap gagal-terbuka bila kolom wajib tak ada.

PEMBAGIAN PECAHAN (TERUKUR dari kode sumber)
--------------------------------------------
Round-robin `indeks % 8` atas DAFTAR SIMBOL urut abjad yang lolos
`jenis_instrumen(s) == "perpetual_usdt"`; seluruh riwayat satu simbol selalu
jatuh di satu pecahan, jadi backtest per simbol tidak pernah melintasi pecahan.
Semesta yang dirujuk: 787 simbol / 19.598 simbol-bulan (ADR-A005) dengan
realisasi persistensi 19.586 parquet (VERSI 5, run 30389402113) + 12 karantina
(KC-17, VERSI 6). Selisih 19.598 - 19.586 = 12 adalah utang B-1/KC-17 yang
DIWARISI, bukan angka modul ini.

PRA-TERBANG. Setiap laporan yang memakai angka serapan wajib menyertakan baris
pra-terbang: penyebut simbol yang dipakai (787 atau 937) + label B-1 + B-5.
Lihat `lux_ms.baris_praterbang`.
"""
from __future__ import annotations

import hashlib
import json
import os
import tarfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------- identitas

OWNER_SUMBER = "EnVyxS"
REPO_SUMBER = "lux-ai-research"  # sumber byte, BUKAN patokan
RUN_SERAPAN = "30396803601"
COMMIT_SERAPAN = "57a04f1ea18570f4aa8bce0abee650ea97d374fa"
VERSI_PECAHAN_SUMBER = 6  # pecahan.py VERSI 6 (KC-17: karantina dikemas)

TOTAL_PECAHAN = 8
PECAHAN_DIHARAP: Tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6, 7)
# Tag terukur ada lewat list_releases (metadata rilis, bukan byte):
PECAHAN_TAG_TERUKUR_ADA: Tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6, 7)
# Daftar aset sudah dibuka penuh untuk pecahan ini:
PECAHAN_ASET_TERUKUR: Tuple[int, ...] = (0, 1, 7)
# Dibatalkan: tidak ada indeks 8. Lihat KOREKSI 22 di docstring.
INDEKS_TAK_SAH: Tuple[int, ...] = (8,)

RUN_LAIN_BERILIS: Tuple[str, ...] = ("30376241019", "30383278359", "30389402113")

POLA_TAG = "serapan-pecahan-{indeks}-{run}"
POLA_ASET = "pecahan_{indeks}.part{bagian:02d}.tar"
POLA_ASET_KARANTINA = "pecahan_{indeks}_karantina.part{bagian:02d}.tar"
NAMA_SUMS = "SHA256SUMS"
NAMA_SUMS_KARANTINA = "SHA256SUMS_KARANTINA"
BASIS_UNDUH = "https://github.com/" + "{owner}/{repo}/releases/download/{tag}/{nama}"

JENIS_DIIZINKAN = "perpetual_usdt"
AKAR_PARQUET = "data/parquet"

# ------------------------------------------------------------------ skema

KOLOM_ARSIP: Tuple[str, ...] = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trades",
    "taker_buy_base",
    "taker_buy_quote",
    "ignore",
)
# Yang benar-benar ditulis ke parquet: tanpa "ignore" (klines.KOLOM_SIMPAN).
KOLOM_PARQUET_DIHARAP: Tuple[str, ...] = KOLOM_ARSIP[:-1]
KOLOM_WAJIB: Tuple[str, ...] = ("open_time", "open", "high", "low", "close", "volume")
STATUS_SKEMA = "TERUKUR-DARI-KODE (klines.py SHA cc4d9287); byte parquet BELUM DIUKUR"

# --------------------------------------------------- sidik & byte terukur

SIDIK_TERUKUR: Dict[str, str] = {
    # pecahan 0, rilis 361385756
    "pecahan_0.part01.tar": "0e41f2e0644f9d2d7c53a66302fc2f70539a02261b9cf3baad31b3890968e02b",
    "pecahan_0.part02.tar": "6703c40e5f32f958331e680a6e49749905a06f0777f23f78a96cf51a277ded4a",
    "pecahan_0.part03.tar": "8e57f54e634e5c83d84c939836650b3711cb5cd11d97cbb45e9669c0f706efab",
    "pecahan_0_karantina.part01.tar": "ea34b5c9007795fa4f060d1f1e194d26eedeb01a9c72aeaeb704d7eb841e79da",
    # pecahan 1, rilis 361394828
    "pecahan_1.part01.tar": "dd7867001dbbf4ef1b7425938a3c3dda5163dfcba080d96908d0f5a5fcd50a5c",
    "pecahan_1.part02.tar": "9c01389d33f38d55a764e81ffc91c08f8d9c15605d2116c84cb3914d5d5fe7b5",
    "pecahan_1.part03.tar": "97c054402886e923b858f781c39a1d493325e1b7f4a6952970756950b2292a08",
    "pecahan_1_karantina.part01.tar": "f2377bf557528853c91395638fa41c108c09e4b70b0a284224bec25de2c48ba8",
    # pecahan 7, rilis 361391980
    "pecahan_7.part01.tar": "cde0044705ee09ad37b2e851f922e5434772dc632e3107dc525eb4c8824b6ac0",
    "pecahan_7.part02.tar": "be3ad5eaf484b38bf9d6d9dd9c7498ed4686f644800ecc915da2db277e8d4c5d",
    "pecahan_7.part03.tar": "16c28d8aeec3a3f399ff4e4e41c678018ca6bf4a78cc6129f30343acc1e54773",
    "pecahan_7_karantina.part01.tar": "f34d3080f23d5ec704c7236ae473fc8e75ec4486841e046d7c647eb19d9b77fa",
}

BYTE_TERUKUR: Dict[str, int] = {
    "pecahan_0.part01.tar": 1798359040,
    "pecahan_0.part02.tar": 1799782400,
    "pecahan_0.part03.tar": 526766080,
    "pecahan_0_karantina.part01.tar": 3297280,
    "pecahan_1.part01.tar": 1799168000,
    "pecahan_1.part02.tar": 1799352320,
    "pecahan_1.part03.tar": 675870720,
    "pecahan_1_karantina.part01.tar": 3174400,
    "pecahan_7.part01.tar": 1798277120,
    "pecahan_7.part02.tar": 1799618560,
    "pecahan_7.part03.tar": 281640960,
    "pecahan_7_karantina.part01.tar": 1095680,
}

SIDIK_SUMS_TERUKUR: Dict[int, str] = {
    0: "ea9c41361b5843616fb66b38b0a6017c748095f04e66d4913fb2c4bcf0787268",
    1: "d01fc8c3685793267703a5bf79915b7273bfad5a2efcea705fcbcbe561cd264a",
    7: "a3ce61041adcda284b98724cc4dc4717067d0f3abca137011aa64a0d148ac996",
}
BYTE_SUMS_TERUKUR = 261  # ketiga SHA256SUMS yang sudah dibuka sama-sama 261 B

# Ukuran kasar untuk perencanaan cakram runner (~14 GB), BUKAN klaim hasil.
BYTE_SEMESTA_TERSIMPAN = 32_706_262_375  # pecahan.py VERSI 5, run 30389402113
CACAH_PARQUET_TERSIMPAN = 19_586  # idem; utang B-1
CACAH_KARANTINA = 12  # KC-17


def gerbang_indeks(indeks: int) -> None:
    """Tolak indeks di luar 0..7 (KOREKSI 22)."""
    if indeks in INDEKS_TAK_SAH or not 0 <= indeks < TOTAL_PECAHAN:
        raise ValueError(
            f"indeks pecahan {indeks} tidak sah; indeks sah 0..{TOTAL_PECAHAN - 1} "
            "(pecahan.py simbol_pecahan)"
        )


def tag_pecahan(indeks: int, run: str = RUN_SERAPAN) -> str:
    gerbang_indeks(indeks)
    return POLA_TAG.format(indeks=indeks, run=run)


def nama_bagian(indeks: int, bagian: int, karantina: bool = False) -> str:
    gerbang_indeks(indeks)
    if bagian < 1:
        raise ValueError("nomor bagian mulai dari 1")
    pola = POLA_ASET_KARANTINA if karantina else POLA_ASET
    return pola.format(indeks=indeks, bagian=bagian)


def url_aset(nama: str, indeks: int, run: str = RUN_SERAPAN) -> str:
    return BASIS_UNDUH.format(
        owner=OWNER_SUMBER,
        repo=REPO_SUMBER,
        tag=tag_pecahan(indeks, run),
        nama=nama,
    )


def daftar_aset_diharap(indeks: int, cacah_bagian: int = 3) -> List[str]:
    """Nama aset yang diharapkan ada. Cacah bagian nyata WAJIB dari SHA256SUMS,
    bukan dari tebakan ini; nilai bawaan 3 hanya cocok untuk pecahan 0/1/7 yang
    sudah diukur."""
    nama = [nama_bagian(indeks, b) for b in range(1, cacah_bagian + 1)]
    return nama + [NAMA_SUMS]


# ------------------------------------------------------------ sidik berkas


def sha256_berkas(jalur: str, blok: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(jalur, "rb") as f:
        while True:
            b = f.read(blok)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def baca_sums(jalur: str) -> Dict[str, str]:
    """Baca berkas gaya `sha256sum`: `<hex>  <nama>` per baris."""
    hasil: Dict[str, str] = {}
    for baris in Path(jalur).read_text(encoding="utf-8").splitlines():
        baris = baris.strip()
        if not baris:
            continue
        bagian = baris.split()
        if len(bagian) < 2:
            continue
        hex_ = bagian[0].strip()
        nama = bagian[-1].lstrip("*").strip()
        hasil[os.path.basename(nama)] = hex_
    return hasil


def gerbang_sidik(jalur: str, sums: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Sidik satu berkas harus cocok dengan SHA256SUMS rilis DAN, bila namanya
    sudah pernah diukur di sesi ini, dengan `SIDIK_TERUKUR`.

    Sidik yang tidak dikenal SELALU gagal. Tidak ada jalur "anggap benar".
    """
    nama = os.path.basename(jalur)
    ada = os.path.exists(jalur)
    sidik = sha256_berkas(jalur) if ada else None
    byte_ = os.path.getsize(jalur) if ada else None
    harap_sums = (sums or {}).get(nama)
    harap_tetap = SIDIK_TERUKUR.get(nama)
    byte_tetap = BYTE_TERUKUR.get(nama)

    if not ada:
        return {"nama": nama, "lulus": False, "sebab": "berkas tidak ada"}
    if harap_sums is None and harap_tetap is None:
        return {
            "nama": nama,
            "lulus": False,
            "sebab": "sidik tidak diketahui",
            "sha256": sidik,
            "byte": byte_,
        }
    beda: List[str] = []
    if harap_sums is not None and harap_sums != sidik:
        beda.append("sha256 != SHA256SUMS")
    if harap_tetap is not None and harap_tetap != sidik:
        beda.append("sha256 != SIDIK_TERUKUR")
    if byte_tetap is not None and byte_tetap != byte_:
        beda.append("byte != BYTE_TERUKUR")
    return {
        "nama": nama,
        "lulus": not beda,
        "sebab": "; ".join(beda) if beda else "cocok",
        "sha256": sidik,
        "byte": byte_,
        "diperiksa_terhadap": [
            k
            for k, v in (("SHA256SUMS", harap_sums), ("SIDIK_TERUKUR", harap_tetap))
            if v is not None
        ],
    }


# --------------------------------------------------------------- pembongkar


def anggota_aman(nama: str) -> bool:
    p = Path(nama)
    if p.is_absolute():
        return False
    return ".." not in p.parts


def bongkar(jalur_tar: str, akar: str = ".") -> Dict[str, Any]:
    """Bongkar satu bagian tar ke `akar`; jalur `data/parquet/<simbol>/` pulih
    apa adanya. Anggota absolut atau memuat `..` DITOLAK, tidak dibongkar."""
    ditulis: List[str] = []
    ditolak: List[str] = []
    with tarfile.open(jalur_tar, "r:") as t:
        for anggota in t:
            if not anggota.isreg():
                continue
            if not anggota_aman(anggota.name):
                ditolak.append(anggota.name)
                continue
            t.extract(anggota, path=akar)
            ditulis.append(anggota.name)
    return {
        "tar": os.path.basename(jalur_tar),
        "cacah_ditulis": len(ditulis),
        "cacah_ditolak": len(ditolak),
        "contoh_ditolak": ditolak[:10],
        "lulus": not ditolak,
    }


# ----------------------------------------------------------- pembacaan data


def daftar_simbol(akar: str = ".") -> List[str]:
    basis = Path(akar) / AKAR_PARQUET
    if not basis.exists():
        return []
    return sorted(p.name for p in basis.iterdir() if p.is_dir())


def berkas_parquet(simbol: str, akar: str = ".") -> List[str]:
    basis = Path(akar) / AKAR_PARQUET / simbol
    if not basis.exists():
        return []
    return sorted(str(p) for p in basis.glob("*.parquet"))


def simbol_pecahan_lokal(
    simbol_semua: Sequence[str], indeks: int, total: int = TOTAL_PECAHAN
) -> List[str]:
    """Ulangi pembagian round-robin `i % total == indeks` atas daftar urut abjad.

    Dipakai untuk MEMERIKSA bahwa isi pecahan yang dibongkar memang milik
    indeks itu, bukan untuk menebak daftar simbol.
    """
    gerbang_indeks(indeks)
    urut = sorted(simbol_semua)
    return [s for i, s in enumerate(urut) if i % total == indeks]


def muat_1m(jalur: Iterable[str]) -> Dict[str, Any]:
    """Muat parquet 1m menjadi satu tabel urut waktu.

    Bila kolom wajib tidak ada, kembalikan skema NYATA dengan `lulus=False`.
    Nama kolom TIDAK PERNAH ditebak atau dipetakan otomatis.
    """
    import pandas as pd

    daftar = list(jalur)
    if not daftar:
        return {"lulus": False, "sebab": "tidak ada berkas", "kolom": [], "cacah_baris": 0}
    bagian = [pd.read_parquet(p, engine="pyarrow") for p in daftar]
    df = pd.concat(bagian, ignore_index=True) if len(bagian) > 1 else bagian[0]
    kolom = list(map(str, df.columns))
    hilang = [k for k in KOLOM_WAJIB if k not in kolom]
    if hilang:
        return {
            "lulus": False,
            "sebab": "kolom wajib tidak ada",
            "kolom": kolom,
            "kolom_hilang": hilang,
            "kolom_diharap": list(KOLOM_PARQUET_DIHARAP),
            "cacah_baris": int(len(df)),
        }
    df = df.sort_values("open_time", kind="mergesort")
    sebelum = int(len(df))
    df = df.drop_duplicates(subset=["open_time"], keep="first").reset_index(drop=True)
    return {
        "lulus": True,
        "sebab": "cocok",
        "kolom": kolom,
        "cacah_baris": int(len(df)),
        "cacah_duplikat_dibuang": sebelum - int(len(df)),
        "open_time_awal": int(df["open_time"].iloc[0]) if len(df) else None,
        "open_time_akhir": int(df["open_time"].iloc[-1]) if len(df) else None,
        "cacah_berkas": len(daftar),
        "df": df,
    }


# -------------------------------------------------------------- pelaporan


def laporan_kelengkapan() -> Dict[str, Any]:
    """Kelengkapan dataset dengan status utang eksplisit (aturan 94)."""
    return {
        "bukan_bukti": False,
        "sumber": {
            "owner": OWNER_SUMBER,
            "repo": REPO_SUMBER,
            "peran": "sumber byte, BUKAN patokan",
            "run": RUN_SERAPAN,
            "commit": COMMIT_SERAPAN,
            "versi_pecahan": VERSI_PECAHAN_SUMBER,
            "run_lain_berilis": list(RUN_LAIN_BERILIS),
        },
        "indeks_sah": list(PECAHAN_DIHARAP),
        "tag_terukur_ada": list(PECAHAN_TAG_TERUKUR_ADA),
        "aset_terukur_penuh": list(PECAHAN_ASET_TERUKUR),
        "status_metadata_rilis": "TERUKUR: 8/8 tag ada (list_releases 2026-07-28)",
        "status_byte": "BELUM DIUKUR: sha256sum -c hanya bisa di Actions",
        "status_skema": STATUS_SKEMA,
        "status_cacah_baris": "BELUM DIUKUR di repo patokan",
        "koreksi": (
            "KOREKSI 22: indeks pecahan 0..7, bukan 1..8. Kesimpulan lama "
            "'pecahan 8 tidak ada => dataset tidak lengkap' DIBATALKAN; 404 pada "
            "tag pecahan-8 bukan bukti apa pun."
        ),
        "angka_diwarisi": {
            "cacah_parquet_tersimpan": CACAH_PARQUET_TERSIMPAN,
            "cacah_karantina": CACAH_KARANTINA,
            "byte_semesta_tersimpan": BYTE_SEMESTA_TERSIMPAN,
            "status": (
                "DIWARISI dari lux-ai-research; utang B-1 (gerbang penyebut ENAM "
                "klausa dengan dasar keputusan LIMA) dan KC-17 masih terbuka. "
                "Tidak boleh dikutip sebagai hasil modul ini."
            ),
        },
        "batas_cakram": (
            "runner ~14 GB; satu pecahan ~3,8-4,3 GB dalam 3 bagian tar. "
            "Backtest WAJIB per pecahan atau per simbol, tidak pernah semesta "
            "penuh dalam satu job."
        ),
    }


def tulis_laporan(jalur: str, isi: Dict[str, Any]) -> str:
    p = Path(jalur)
    p.parent.mkdir(parents=True, exist_ok=True)
    bersih = {k: v for k, v in isi.items() if k != "df"}
    p.write_text(
        json.dumps(bersih, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(p)
