# PRA-REGISTRASI UKURAN GRID — dikunci sebelum pengukuran apa pun

Status berkas ini: **DIKUNCI 2026-08-01 (waktu sesi Asia/Jakarta)**, sebelum satu
pun angka dataset diukur. Grid yang membengkak setelah tanggal ini **membatalkan**
seluruh hasil PBO/DSR yang mengacu padanya.

PATOKAN: repositori ini sendiri. Repo lain (`lux-ai-research`, `lux-research`,
`lux-scalp-research`, `Lux`, `lux-memory`, legacy `bot_v8 v8.7`) berstatus
**REFERENSI, bukan patokan** — angka dari sana tidak sah menjadi dasar keputusan
tanpa diukur ulang di sini.

## 0. Pra-terbang wajib

Penyebut simbol yang dipakai: **BELUM DIPILIH** — wajib dinyatakan 787 atau 937
sebelum hasil pertama (B-5). Label yang selalu ikut: **B-1** (gerbang penyebut
ENAM klausa dengan dasar keputusan LIMA) dan **B-5** (dua penyebut simbol
787 & 937). Enam syarat penyeberangan UKUR v24 §13 ikut setiap kali angka
serapan dipakai.

## 1. Ukuran grid yang dipra-registrasi

| Sumbu | Cacah dikunci | Isi |
|---|---|---|
| Keluarga strategi | 6 | akan dinamai di Fase 4; tak boleh bertambah |
| Himpunan TF | 5 | `{1m}`, `{1m,5m}`, `{1m,15m}`, `{5m,15m}`, `{1m,5m,15m,1h}` |
| Rezim | 4 | vol tinggi/rendah × tren/ranging |
| Varian manajemen perjalanan harga (Fase 3) | 6 | TP1 struktural, TP1 ATR-multiple, partial TP awal, breakeven pasca-MFE, trailing ATR/struktur, exit momentum melemah |
| Varian aturan pemilihan | 4 | ambang minimum × aturan seri |

**N percobaan yang WAJIB dilaporkan ke PBO/DSR** = 6 × 5 × 4 × 6 × 4 = **2.880**
(TURUNAN dari tabel di atas, aritmetika sesi ini). Termasuk percobaan pada
**pemilih**, bukan hanya pada strategi.

Satu strategi = satu kesatuan utuh. Versi 1m-saja dan versi multi-TF dari
kondisi yang sama adalah **dua strategi terpisah** dan sudah dihitung lewat
sumbu himpunan TF.

## 2. Prediksi & ambang lulus/gagal (dikunci)

| Hipotesis | Prediksi | LULUS bila | GAGAL bila |
|---|---|---|---|
| H-1 M-3A dominan | M-3A > M-3B pada cacah trade rugi | pangsa M-3A ≥ 2× pangsa M-3B, dan cacah jalur ambigu dilaporkan | M-3A ≤ M-3B, atau cacah ambigu > 25% M-3A (kesimpulan digantung) |
| H-2 M-3B kecil (klaim operator) | pangsa M-3B < 10% total SL | < 10% → klaim DIDUKUNG | > 25% → klaim DIBANTAH, prioritas naik; 10–25% → TAK KONKLUSIF |
| H-3 gerbang `rr1 < min_rr` mendorong TP menjauh | korelasi positif RR yang diminta vs jarak TP1 dalam ATR | koefisien > 0 dan MFE/jarak-TP1 median < 0,5 | tidak ada hubungan terukur |
| H-4 ambang funding | proporsi trade melewati stempel settlement kecil | < 10% → funding **DITUTUP permanen** sebagai isu biaya | > 25% → funding jadi biaya wajib |
| H-5 perbaikan Fase 3 | ≥1 varian menaikkan ekspektasi R bersih OOS | naik tanpa menaikkan kerugian kelas lainnya | hanya win-rate naik sementara ekspektasi R turun → **DITOLAK** |

## 3. Hipotesis diblokir (dicatat, tidak dijalankan)

**H-6 funding sebagai fitur/penanda rezim — DIBLOKIR.** Prasyarat: label funding
lulus uji ketepatan lebih dulu. Dasar blokir: tabel silang funding SAH sebagai
pembukuan tapi **BELUM DIUJI** ketepatannya terhadap kenyataan; `877/19.586`
`funding_hilang` (842 di antaranya MATI, status: angka warisan, **belum diukur
ulang di repo ini**); `funding_ada` di manifes medan mati `{"null":19598}`
(status sama); ketiga modul penemu tak berpasangan uji (B-2/B-3/B-4).
DILARANG menyimpulkan data funding tidak ada — hanya **manifes** yang tak
memuatnya.

## 4. Yang WAJIB dilaporkan bersama setiap hasil

- Baris pra-terbang (penyebut simbol + B-1 + B-5).
- Cacah **jalur ambigu** — angka M-3A tanpa cacah ambigu = tidak sah.
- Asumsi intrabar (default **pesimistis**: SL menang bila SL dan target satu bar).
- Efek setiap perubahan ke **kedua** kelas M-3A dan M-3B sekaligus.
- Garis dasar negatif (acak, selalu-entry).
- commit + seed (seed baku `20260801`).

## 5. Status pengukuran saat berkas ini dikunci

Seluruh angka dataset: **BELUM DIUKUR**. Sebab struktural: sandbox tanpa
jaringan, pengukuran hanya lewat GitHub Actions, dan CI repositori ini baru
dipasang. Tidak ada angka funnel M-2, histogram M-3A, vonis M-3B, PBO, DSR,
atau bobot strategi yang boleh dikutip sebelum Actions menghasilkannya.
