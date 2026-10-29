# K/R değişikliği sonrası doğrulama

> Eski Tk arayüzü için verilen görsel/rapor komutları tarihîdir. Bu betikler ve
> üretilmiş görseller güncel daldan kaldırılmıştır; yeniden incelemek için
> [temizlik öncesi sürümü](https://github.com/gkkizil/gokworks/tree/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9) kullanın.

**174 test geçti; 0 başarısız, 0 atlanan. 39 gerçek Tk GUI testi.** Satır/dal birleşik kapsamı %94.4.

Bu dizin yeni K/R sürümünün tüm test sonuçlarını içerir. Önceki GUI Word
raporu ve `../gui-verification-results.json`, K/R eklenmeden önceki 140 testlik
denetimin tarihsel kaydı olarak korunur.

- [Arşiv: Güncel Word raporu](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/k-radius/GOKWORKS_K_RADIUS_GUI_Raporu_2026-10-09.docx): üç ekranın iki tema görüntüleri, BA hesabı, K/R test listesi ve kapsam sınırları.
- `screenshots.json`: yedi gerçek pencere görüntüsünün SHA-256 ve boyutları.
- `gui-verification-results.json`: test bazlı sonuçlar, süreler, alt senaryolar,
  bağımlılık sürümleri ve test edilen uygulama/test dosyalarının SHA-256 değerleri.
- `test-run.log`: bütün testlerin konsol çıktısı.
- `coverage.json`: yeni sürümün kapsam ölçümü.
- `api-contract.json`: SolidWorks 2023 interop metadata ve enum kıyaslaması.
- `reference-comparison.json`: gerçekten çalıştırılan FreeCAD elle hesap
  scriptinin çıktısı ve GOKWORKS ile sayısal karşılaştırması.

Tekrarlama, sanal ekran açıkken proje kökünden:

```bash
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user \
  COVERAGE_FILE=/tmp/gokworks-kr.coverage \
  .venv/bin/python -m coverage run --branch \
  --source=pdf,dxf_dwg,solidworks,main,k_factor,gui \
  docs/report-tools/run_verification.py --output-dir docs/reports/k-radius \
  > docs/reports/k-radius/test-run.log 2>&1
COVERAGE_FILE=/tmp/gokworks-kr.coverage .venv/bin/python -m coverage json \
  -o docs/reports/k-radius/coverage.json
.venv/bin/python docs/report-tools/create_k_radius_report.py
```

Tk GUI ve hesaplamalar gerçekten çalıştırılır; SolidWorks COM sınırı test
nesneleriyle temsil edilir. Fiziksel üretim numunesi ölçülmedi, Windows/
SolidWorks'te gerçek montaj değiştirilmedi. Katalog nominal ölçü seçenekleridir;
üretici kapasitesi onayı değildir. [Algoritma ve kullanım](../../k-factor-radius.md).
