# Manuel ISO tolerans kontrolü

**230 test geçti; 0 başarısız, 0 atlanan. 64 gerçek Tk GUI testi.** Yeni manuel kontrol için 8 hesap ve 6 GUI testi eklendi; önceki 216 testin tamamı yeniden çalıştırıldı. Gerçek Windows/SolidWorks COM üretimi veya native Windows DPI bu Linux kontrolünün kapsamı dışındadır.

[Word raporu](GOKWORKS_ISO_Gecme_Raporu_2026-10-09.docx), [test çalışması](test-run.log), [test bazlı sonuç ve kaynak hashleri](gui-verification-results.json), [kapsam](coverage.json), [ISO kaynak karşılaştırması](source-comparison.json), [görüntü hashleri](screenshots.json), [Word bütünlük kontrolü](word-report-validation.json).

GitHub Word dosyası sayfasındaki **Download raw file** düğmesiyle raporu indirin. Sekiz gerçek pencere görüntüsü rapora gömüldü; ZIP CRC ve python-docx geri okuması kontrol edildi. Microsoft Word'de yerel sayfa görüntüleme çalıştırılmadı.

## Sonuç ve kullanım

**ISO GEÇMELERİ → Manuel kontrol**: ortak nominal çap, delik üst/alt sapmaları, mil üst/alt sapmaları. Sapmalar mm olarak girilir. Sonuçlar mm/µm; kesit/bölgeler, üç örnek ölçü, CSV ve pano desteklenir. Girişler ISO seçiminden ayrı korunur; ortak çap/birim/grafik tercihleri iki yöntemde de kullanılır.

Ø50; delik alt 0/üst +0,02; mil alt −0,02/üst 0: **0–0,04 mm boşluk; kayar geçme adayı, sınırda temas**. Delik en yakın H6 ve mil en yakın h6; her biri bir limitte 4 µm farklıdır, tam eşleşme olarak sunulmaz. İki parçaya da ±0,02 girilirse −0,04…+0,04 mm ara geçme oluşur. Gerçekleşen tek ölçü için alt ve üst aynı girilir.

Tam eşitlik ve yakın sınıf ayrıdır. Karşılaştırma mevcut 11 delik/18 mil sınıfındadır. Yakınlık alt/üst sapma farklarının mutlak toplamı ile sıralanır; girilen limitler değiştirilmez. Sıkı/ara/boşluklu türü limitlerden hesaplanır. Kayar/yağlı kullanım adları öneridir; yağlama ve montaj kuvveti için ek üretim/çalışma bilgileri gerekir. [Hesap ve kaynak kılavuzu](../../iso-fits.md).

## Gerçek görüntüler

| Görünüm | Görüntü |
| --- | --- |
| Manuel, açık | [Görüntü](screenshots/iso-manual-light.png) |
| Manuel, koyu | [Görüntü](screenshots/iso-manual-dark.png) |
| Manuel, karşılaştırma alanı | [Görüntü](screenshots/iso-manual-comparison-dark.png) |
| ISO sınıf seçimi, açık/koyu | [Açık](screenshots/iso-light.png) / [Koyu](screenshots/iso-dark.png) |
| Bölgeler / ara / sıkı | [Bölgeler](screenshots/iso-zones-dark.png) / [Ara](screenshots/iso-transition-dark.png) / [Sıkı](screenshots/iso-interference-dark.png) |

1240×860 gerçek Tk pencerelerinden alındı. Manuel testler ayrıca 1000×690/%100, 1400×900/%125 ve 1920×1080/%150 boyutlarında iki temayı ve kaydırarak karşılaştırmaya erişimi doğrular. Eski ISO modu beş boyut/ölçek matrisiyle tekrar sınandı. Girişlerin min/max sırası, 1 nm hassasiyet, simetrik/tek taraflı toleranslar, gerçekleşen ölçüler, negatif/minimum temas ve bütün sınıfların altı çaptaki tam eşleşmesi sınandı.

ISO tabloları yeniden 3217 kontrolle karşılaştırıldı; 0 beklenmeyen fark. F8≤3 mm için hatalı kaynak satırından iki bilinen fark korunur. Resmî metne bu ortamın ağ erişim sınırı nedeniyle erişilemedi; [önceki erişim kanıtı](../iso-fits/standards-access.json). Bu çalışma ISO sertifikası değildir.

Kod sayımı: **3645 uygulama + 3393 test = 7038 fiziksel Python satırı** (22 uygulama, 10 test dosyası; boş satır/yorum dahil). Veri JSON'u, rapor araçları, üçüncü taraf kütüphaneler ve geçmiş yedekler bu sayımda değildir.

## Yeniden çalıştırma

Proje kökünde sanal ekran ve kılavuzdaki dört pinlenmiş kaynak checkout'u hazırken:

```bash
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user COVERAGE_FILE=/tmp/gokworks-manual-iso.coverage .venv/bin/python -m coverage run --branch --source=pdf,dxf_dwg,solidworks,main,k_factor,gui,iso_fits docs/report-tools/run_verification.py --output-dir docs/reports/manual-iso
COVERAGE_FILE=/tmp/gokworks-manual-iso.coverage .venv/bin/python -m coverage json -o docs/reports/manual-iso/coverage.json
.venv/bin/python docs/report-tools/compare_iso_sources.py --sources /tmp/gokworks-iso-sources --output docs/reports/manual-iso/source-comparison.json
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user .venv/bin/python docs/report-tools/capture_iso_gui.py --output-dir docs/reports/manual-iso
.venv/bin/python docs/report-tools/create_iso_report.py --output-dir docs/reports/manual-iso
```

Kod/test hashleri rapor üretiminde güncel dosyalarla doğrulanır. [Önceki 216 testlik rapor](../iso-fits/README.md) tarihsel kayıt olarak korunur.
