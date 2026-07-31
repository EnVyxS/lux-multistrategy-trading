"""Pelari uji minimal (sandbox tanpa pytest). Di CI, pytest yang dipakai."""
import importlib
import sys
import traceback

sys.path.insert(0, "/data/ms")

MODUL = [
    "tests.test_tangan",
    "tests.test_antilookahead",
    "tests.test_statistik",
    "tests.test_baseline_b0",
]

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
