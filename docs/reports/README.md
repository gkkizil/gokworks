# GUI yeniden denetim kanıtları

2026-10-09 06:14:08–06:14:28 UTC, Linux/Python 3.12.14, Xorg :99. **140 test geçti, 0 başarısız, 0 atlanan; 34 gerçek Tk GUI testi.** Testler değiştirilen çalışma kopyasında çalıştı; depo başlangıç commit'i `76ccd67`, ref `main`.

- [Word raporu](GOKWORKS_GUI_Test_Raporu_2026-10-09.docx): sonuç, ortam, yöntem, işlev değerlendirmeleri, 34 GUI testinin tek tek listesi, dört gerçek ekran görüntüsü ve kapsam sınırları. Görüntüler DOCX içine gömülüdür; raporu açmak için ayrı görsel dosyaları gerekmez.
- [Test bazlı JSON](gui-verification-results.json): sonuçlar, süreler, alt senaryolar, sürümler, kod SHA-256 özetleri ve satır sayımı.
- [Tam konsol çıktısı](gui-test-run.log), [kapsam ölçümü](gui-coverage.json).
- [DOCX doğrulama kaydı](word-report-validation.json): ZIP/XML/görsel kontrolü ve rapor SHA-256 değeri.

Önce 128 mevcut test tekrar çalıştırıldı. Ek 12 kabul testinin ilk denemesinde bir ilk yerleşim zamanlayıcısı erişimi hatası çıktı. İlk GUI boyutlandırması açıkça zamanlandı; sonrasında 12 ek test ve 140 testlik tam çalışma geçti. Bu durum kullanıcı açılışında gözlemlenmiş bir çökme olarak sunulmaz.

SolidWorks COM, native Windows dosya diyalogları ve Explorer açılışı test sınırında temsil edildi. Gerçek CAD geometrisi, SolidWorks sürümüne özgü davranışlar ve tüm Windows DPI/monitör kombinasyonları doğrulanmadı. K Faktörü kasıtlı olarak devre dışı.

Tekrar çalıştırma (sanal ekran açıkken, proje kökünden):

```bash
.venv/bin/python -m pip install -r docs/report-tools/requirements.txt
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user \
  COVERAGE_FILE=/tmp/gokworks-gui-reaudit.coverage \
  .venv/bin/python -m coverage run --branch \
  --source=pdf,dxf_dwg,solidworks,main,k_factor,gui \
  docs/report-tools/run_verification.py > docs/reports/gui-test-run.log 2>&1
COVERAGE_FILE=/tmp/gokworks-gui-reaudit.coverage \
  .venv/bin/python -m coverage json -o docs/reports/gui-coverage.json
.venv/bin/python docs/report-tools/create_word_report.py
```

Word raporu son kaydedilmiş test sonuçları ve `assets/` görüntülerini kullanır. Gelecekte GUI değiştirilirse rapor üretmeden önce testleri ve gerçek pencere görüntülerini yenileyin. Rapor üreticisi uygulamanın çalışma bağımlılığı değildir.
