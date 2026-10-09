# ISO eklemesi ve son program kontrolü

**216 test geçti, 0 başarısız, 0 atlanan; 58 gerçek Tk GUI testi.** ISO için 8 hesap + 9 GUI testi eklendi; önceki PDF, DXF/DWG, otomatik/manuel K/R, ayar ve bağlantı testlerinin tamamı yeniden çalıştırıldı. Windows/SolidWorks COM üretimi bu Linux çalışmasının kapsamı dışındadır. ISO ekranı SolidWorks gerektirmeyen bağımsız hesap ve çizim ekranıdır.

[Word raporu](GOKWORKS_ISO_Gecme_Raporu_2026-10-09.docx), [tam test çıktısı](test-run.log), [test bazlı sonuç ve uygulama hashleri](gui-verification-results.json), [kapsam](coverage.json), [sayısal kaynak karşılaştırması](source-comparison.json), [resmî standart erişim sonuçları](standards-access.json), [görüntü hashleri](screenshots.json), [Word dosyası doğrulaması](word-report-validation.json).

Word dosyasını GitHub dosya sayfasındaki **Download raw file** düğmesiyle indirin. Raporda beş gerçek ekran görüntüsü gömülüdür; ZIP CRC ve python-docx ile içerik kontrol edildi. Yerel Microsoft Word sayfa görünümü çalıştırılmadı.

## Gerçek ekran görüntüleri

| Görünüm | Görüntü |
| --- | --- |
| Açık tema, H8/f7 | [Görüntü](screenshots/iso-light.png) |
| Koyu tema, H8/f7 | [Görüntü](screenshots/iso-dark.png) |
| Koyu tema, sapma bölgeleri | [Görüntü](screenshots/iso-zones-dark.png) |
| Koyu tema, H7/k6 ara geçme | [Görüntü](screenshots/iso-transition-dark.png) |
| Koyu tema, H7/p6 sıkı geçme | [Görüntü](screenshots/iso-interference-dark.png) |

1240×860 gerçek Tk penceresinden alındı; görsel taslak veya üretilmiş örnek resim değildir. Kesit şematiktir; sapmalar görünürlük için büyütülür. Sapma bölgeleri doğrusal sayısal ölçek kullanır.

## Sayısal doğrulama

**3217 kontrol:** 1100 gerçek dış Python API çağrısı, 1288 ikinci sınır tablosu karşılaştırması, 667 IT genişliği ve 162 temel sapma kontrolü. 3215 eşleşme; F8 ≤3 mm için yanlış kaynak satırından iki bilinen fark; 0 beklenmeyen fark. Uygulamada EI=+6, ES=+20 µm kullanıldı; IT8 genişliği 14 µm. Commitler ve SHA-256 değerleri karşılaştırma JSON'unda kayıtlıdır.

Standart temeli ISO 286-1:2010 ve ISO 286-2:2010 olarak adlandırılır. Bu oturumun ağ politikası resmî ISO/üretici sitelerine erişimi engelledi; resmî tam metin indirilmedi/incelemiş sayılmadı. Açık GitHub tabloları resmî ISO sertifikası değildir. Güncellik ve düzeltmeler resmî katalogdan kontrol edilmelidir. [Kaynaklar, elle hesap ve kapsam kılavuzu](../../iso-fits.md).

## GUI kontrolü

ISO ekranında iki tema × beş boyut/ölçek sınandı: %100'de 1000×690, 1240×860, 1366×768; %125'te 1400×900; %150'de 1920×1080. Gerçek pencere ölçüsü, alanların ekrana sığması ve kaydırılarak sonuç düğmesine erişim kontrol edildi. Tüm delik/mil/birim menüleri ve 14 eşleşme çalıştırıldı. İki grafik, üç örnek ölçü, CSV/kopyalama, kayıt hatası/iptal, geçersiz çapta sonucu temizleme, tema ve yeniden açılışta tercihlerin korunması sınandı.

Kod sayımı: **3459 uygulama Python satırı + 3204 test satırı = 6663 satır.** Boş satır/yorum dahil fiziksel sayım; 21 uygulama ve 9 test dosyası. Veri JSON'u, üçüncü taraf kütüphaneler, rapor araçları ve geçmiş yedekler bu sayımın dışındadır.

## Tekrar çalıştırma

Proje kökünde, sanal ekran hazırken:

```bash
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user COVERAGE_FILE=/tmp/gokworks-iso.coverage .venv/bin/python -m coverage run --branch --source=pdf,dxf_dwg,solidworks,main,k_factor,gui,iso_fits docs/report-tools/run_verification.py --output-dir docs/reports/iso-fits
COVERAGE_FILE=/tmp/gokworks-iso.coverage .venv/bin/python -m coverage json -o docs/reports/iso-fits/coverage.json
.venv/bin/python docs/report-tools/compare_iso_sources.py --sources /tmp/gokworks-iso-sources
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user .venv/bin/python docs/report-tools/capture_iso_gui.py
.venv/bin/python docs/report-tools/create_iso_report.py
```

Kaynak checkoutları için [kılavuzdaki sabit commitler](../../iso-fits.md) gerekir. Test JSON'u eski Git HEAD'i ve test edilen çalışma dosyalarının hashlerini birlikte kaydeder; rapor üreticisi bunların güncel dosyalarla aynı olduğunu doğrular. Önceki 199 testlik [CAD/API ve GUI denetimi](../final-audit/README.md) tarihsel kanıt olarak korunur.
