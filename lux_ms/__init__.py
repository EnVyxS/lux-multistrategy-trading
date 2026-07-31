"""lux_ms — alat ukur multi-strategi LUX (Fase 1).

PATOKAN TUNGGAL: repositori ini sendiri (EnVyxS/lux-multistrategy-trading).
Repo lain mana pun — termasuk lux-ai-research, lux-research, lux-scalp-research,
dan seluruh legacy bot_v8 — berstatus REFERENSI, bukan patokan. Angka dari sana
tidak sah dijadikan dasar keputusan modul ini tanpa diukur ulang di sini.

Hukum pembukuan tetap diwarisi: setiap angka WAJIB dibawa bersama status
utangnya (Aturan 94 / ADR-A024 kep. 5).

Paket ini SENGAJA tidak memuat strategi apa pun. Fase 1 = alat ukur, bukan
strategi. Pembahasan bobot strategi DILARANG sebelum dua gerbang lulus:
  1. reproduksi satu trade tangan digit demi digit  (tests/test_tangan.py)
  2. uji anti-look-ahead lintas TF                  (tests/test_antilookahead.py)
"""

VERSI = "0.1.0-fase1"

PATOKAN = "EnVyxS/lux-multistrategy-trading"
REFERENSI_BUKAN_PATOKAN = (
    "EnVyxS/lux-ai-research",
    "EnVyxS/lux-research",
    "EnVyxS/lux-scalp-research",
    "EnVyxS/Lux",
    "EnVyxS/lux-memory",
    "legacy:bot_v8 v8.7",
)

# Baris pra-terbang WAJIB: diisi oleh pemanggil, tidak boleh dikarang di sini.
PRATERBANG_KOSONG = {
    "penyebut_simbol": None,   # 787 atau 937 — WAJIB dinyatakan (B-5)
    "label_B1": "B-1: gerbang penyebut ENAM klausa dengan dasar keputusan LIMA",
    "label_B5": "B-5: dua penyebut simbol 787 & 937",
    "status": "BELUM DIISI",
}


def praterbang(penyebut_simbol: int) -> dict:
    """Bentuk baris pra-terbang. Menolak penyebut di luar {787, 937}."""
    if penyebut_simbol not in (787, 937):
        raise ValueError("penyebut simbol harus 787 atau 937 (B-5)")
    return {
        "penyebut_simbol": penyebut_simbol,
        "label_B1": PRATERBANG_KOSONG["label_B1"],
        "label_B5": PRATERBANG_KOSONG["label_B5"],
        "status": "DIISI",
    }


def baris_praterbang(penyebut_simbol: int) -> str:
    p = praterbang(penyebut_simbol)
    return (
        f"PRA-TERBANG: penyebut simbol {p['penyebut_simbol']} | "
        f"{p['label_B1']} | {p['label_B5']}"
    )


def sumber_sah(repo: str) -> bool:
    """Gerbang patokan: hanya repo ini yang sah sebagai patokan pengukuran."""
    return repo == PATOKAN
