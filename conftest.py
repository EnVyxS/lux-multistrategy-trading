"""Akar sys.path untuk pytest.

SEBAB (TERUKUR, bukan dugaan): pada run baseline_b0 30659603431 (commit
bb943ec3, jejak reports/b0_tahap.log) `pytest -q tests` gagal MENGUMPULKAN
kelima berkas uji dengan `ModuleNotFoundError: No module named 'lux_ms'` dan
`kode_pytest=2`, sementara pelari polos melaporkan `=== LULUS 58 | GAGAL 0 ===`
dengan `kode_plain=0`. Jadi kedua saksi uji TIDAK PERNAH sepakat di CI; yang
sepakat hanyalah laporan yang menutupi kegagalan pytest.

Sebabnya: repo ini tidak dipasang sebagai paket (tanpa pyproject/setup) dan
`tests/` bukan paket ber-__init__.py, sehingga pytest menyisipkan `tests/` ke
sys.path, BUKAN akar repo. Pelari polos lolos karena ia menyisipkan sendiri
jalurnya.

Berkas ini menyisipkan akar repo secara eksplisit. Ia sengaja TIDAK memakai
jalur absolut sandbox mana pun; akar dihitung dari lokasi berkas ini sendiri,
supaya sama di sandbox dan di runner.
"""

import os
import sys

AKAR = os.path.dirname(os.path.abspath(__file__))

if AKAR not in sys.path:
    sys.path.insert(0, AKAR)
