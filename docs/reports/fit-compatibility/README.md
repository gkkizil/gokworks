# Montaj uyumu ve en yakın geçme kontrolü

**240 test geçti; 0 başarısız, 0 atlanan. 68 gerçek Tk GUI testi.** Montaj uyumu için 6 hesap ve 4 GUI testi eklendi; önceki 230 testin tamamı tekrar çalıştırıldı. Gerçek Windows/SolidWorks üretimi bu Linux çalışmasının kapsamında değildir.

[Word raporu](GOKWORKS_ISO_Gecme_Raporu_2026-10-09.docx), [test çıktısı](test-run.log), [test bazlı sonuçlar ve kaynak hashleri](gui-verification-results.json), [kapsam](coverage.json), [kaynak karşılaştırması](source-comparison.json), [gerçek ekran hashleri](screenshots.json), [Word dosyası bütünlüğü](word-report-validation.json).

Word raporunu GitHub dosya sayfasındaki **Download raw file** ile indirin. Dokuz gerçek pencere görüntüsü rapora gömüldü. ZIP CRC ve python-docx ile içerik geri okuması doğrulandı; yerel Microsoft Word sayfa görünümü çalıştırılmadı.

## Örnek ve açıklama

**Mil 50 ±0,1 mm**, **delik 50 +0/−0,05 mm**: delik 49,950–50,000; mil 49,900–50,100 mm. Delik − mil aralığı **−0,150…+0,100 mm**; ara geçme. Bazı izin verilen ölçüler boşluklu, bazıları sıkı takılır. Her parçada serbest/kayar veya her parçada sıkı/pres geçme garanti değildir. Ara/konumlandırma hedefi boyutsal olarak oluşur. Bütün sapma girişleri mm'dir.

Kart **en yakın ISO çift N7/h9** (toplam limit farkı 0,163 mm) ve **en yakın yaygın geçme H8/e8** (0,250 mm) bilgisini ayrı gösterir. H8/e8 boşluklu bir referanstır; girilen ölçülerin sonucu ara geçme olarak korunur. Kaynak tolerans genişliğini aşan limit farkı açıklanır. Yakınlık kontrolü, tam ISO eşitliği veya üretim kabul kuralı değildir.

**Montaj hedefi**: Genel kontrol, Serbest/kayar, Ara/konumlandırma, Sıkı/pres. Uygunluk bütün limitler üzerinden hesaplanır; sıfır boşluk/sıkılık sınırda temas olarak açıklanır. Pres kuvveti, malzeme, şekil, yüzey ve çalışma koşulları ayrıca değerlendirilir. Hedef ve açıklamalar CSV/pano raporuna dahil edilir; tercihler yeniden açılışta korunur. [Algoritma ve kullanım kılavuzu](../../iso-fits.md).

## Gerçek ekranlar

| Görünüm | Görüntü |
| --- | --- |
| Yeni uyumluluk kartı | [Koyu](screenshots/iso-compatibility-dark.png) |
| Manuel tolerans girişi | [Açık](screenshots/iso-manual-light.png) / [Koyu](screenshots/iso-manual-dark.png) |
| Sınıf karşılaştırması | [Görüntü](screenshots/iso-manual-comparison-dark.png) |
| ISO sınıf seçimi | [Açık](../manual-iso/screenshots/iso-light.png) / [Koyu](../manual-iso/screenshots/iso-dark.png) |
| Bölgeler / ara / sıkı | [Bölgeler](../manual-iso/screenshots/iso-zones-dark.png) / [Ara](../manual-iso/screenshots/iso-transition-dark.png) / [Sıkı](../manual-iso/screenshots/iso-interference-dark.png) |

1240×860 gerçek Tk pencereleridir. Manuel kontroller küçük/büyük pencere, iki tema, %100/%125/%150 ölçek, kaydırarak yeni karta erişim ve bütün hedef menü komutlarıyla sınandı. Bilinen sayısal örnekler, temas sınırları, farklı referans/gerçek geçme türü ve dört çapta 14 yaygın eşleşmenin tam referansı doğrulandı. Geçersiz girişte yeni açıklamalar temizlenir; ISO seçiminde manuel uyumluluk kartı gizlenir.

ISO sayısal tabloları yine 3217 kontrolle karşılaştırıldı; iki bilinen F8 kaynak satırı farkı, 0 beklenmeyen fark. Resmî ISO tam metnine erişim önceki ağ sınırlaması nedeniyle doğrulanamadı; [erişim kanıtı](../iso-fits/standards-access.json). Açık kaynak karşılaştırması ISO sertifikası değildir.

Kod sayımı: **3773 uygulama + 3513 test = 7286 fiziksel Python satırı** (22 uygulama, 10 test dosyası; boş satır/yorum dahil). Veri JSON'u, rapor araçları, üçüncü taraf kütüphaneler ve yedekler bu sayımın dışında.

## Yeniden çalıştırma

Proje kökünde sanal ekran ve kılavuzdaki dört kaynak checkout'u hazırken:

```bash
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user COVERAGE_FILE=/tmp/gokworks-fit-compatibility.coverage .venv/bin/python -m coverage run --branch --source=pdf,dxf_dwg,solidworks,main,k_factor,gui,iso_fits docs/report-tools/run_verification.py --output-dir docs/reports/fit-compatibility
COVERAGE_FILE=/tmp/gokworks-fit-compatibility.coverage .venv/bin/python -m coverage json -o docs/reports/fit-compatibility/coverage.json
.venv/bin/python docs/report-tools/compare_iso_sources.py --sources /tmp/gokworks-iso-sources --output docs/reports/fit-compatibility/source-comparison.json
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user .venv/bin/python docs/report-tools/capture_iso_gui.py --output-dir docs/reports/fit-compatibility
.venv/bin/python docs/report-tools/create_iso_report.py --output-dir docs/reports/fit-compatibility
```

Uygulama/test hashleri Word raporu üretilirken güncel dosyalarla doğrulanır. [Önceki manuel kontrolün 230 testlik raporu](../manual-iso/README.md) tarihsel kanıt olarak korunur.
