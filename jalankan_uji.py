"""Pelari uji polos (saksi ke-2 di samping pytest).

Kedua saksi WAJIB sepakat. Sebelum perbaikan ini pelari polos menyisipkan jalur
sandbox keras "/data/ms", yang tidak ada di runner; ia tetap lolos di runner
hanya karena cwd kebetulan akar repo. Jalur keras itu menyembunyikan beda
lingkungan, jadi diganti dengan akar yang dihitung dari lokasi berkas ini.
"""

import importlib
import os
import sys
import traceback

AKAR = os.path.dirname(os.path.abspath(__file__))
if AKAR not in sys.path:
    sys.path.insert(0, AKAR)

MODUL = [
    "tests.test_tangan",
    "tests.test_antilookahead",
    "tests.test_statistik",
    "tests.test_baseline_b0",
    "tests.test_htf",
]

print(f"akar sys.path: {AKAR}")

lulus = gagal = 0
for nama in MODUL:
    try:
        m = importlib.import_module(nama)
    except Exception:
        print(f"[IMPORT GAGAL] {nama}")
        traceback.print_exc()
        gagal += 1
        continue
    for fn in sorted(d for d in dir(m) if d.startswith("test_")):
        try:
            getattr(m, fn)()
            print(f"LULUS  {nama}.{fn}")
            lulus += 1
        except Exception as e:
            print(f"GAGAL  {nama}.{fn}: {type(e).__name__}: {e}")
            traceback.print_exc()
            gagal += 1

print(f"\n=== LULUS {lulus} | GAGAL {gagal} ===")
sys.exit(1 if gagal else 0)
