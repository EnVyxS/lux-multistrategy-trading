"""Pelari uji polos: menjalankan seluruh fungsi test_* tanpa pytest.

Alasan ada: sandbox pengembangan TIDAK memuat pytest (terukur sesi ini:
`python3 -m pytest` -> "No module named pytest"). CI GitHub Actions tetap
memakai pytest; berkas ini adalah cadangan yang harus memberi hasil sama.

Pemakaian: python3 jalankan_uji.py
Keluar dengan kode 1 bila ada satu pun GAGAL.
"""
import importlib
import sys
import traceback

MODUL_UJI = (
    "tests.test_tangan",
    "tests.test_antilookahead",
    "tests.test_statistik",
)


def main() -> int:
    sys.path.insert(0, ".")
    lulus, gagal = 0, 0
    for nama_modul in MODUL_UJI:
        m = importlib.import_module(nama_modul)
        for nama in sorted(dir(m)):
            if not nama.startswith("test_"):
                continue
            fn = getattr(m, nama)
            if not callable(fn):
                continue
            try:
                fn()
            except Exception:
                gagal += 1
                print(f"GAGAL {nama_modul}.{nama}")
                traceback.print_exc()
            else:
                lulus += 1
                print(f"LULUS {nama_modul}.{nama}")
    print(f"=== LULUS {lulus} | GAGAL {gagal} ===")
    return 1 if gagal else 0


if __name__ == "__main__":
    raise SystemExit(main())
