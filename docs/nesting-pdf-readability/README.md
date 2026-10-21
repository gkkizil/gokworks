# Nesting PDF okunabilirlik düzeltmesi

20 Ekim 2026. Örnek, depodaki gerçek DXF'lerden oluşturulmuş
[22 parçalı taşınabilir projeden](../nesting-example/Ornek.goknest.json)
yeniden dışa aktarıldı. Kaynak DXF dosyaları ve proje değiştirilmedi.

- [Güncel PDF](Nesting.pdf): dört A4 sayfa; üretim/maliyet özeti,
  parça özeti ve hesap notları, 22 yerleşen örnek, gerçek plaka çizimi.
- [Önce](before-01.png): Qt metin rengi `#eeeeee` olduğunda eski çıktı.
- [Güncel özet](after-01.png), [parça ve hesap bilgisi](after-02.png),
  [örnek tablosu](after-03.png), [plaka çizimi](after-04.png).
- [Makine tarafından okunan kontrol sonuçları](checks.json).

Rapor gövdesi **10,5 punto, `#17212b`**; kağıt ve kenar boşlukları açıkça
beyazdır. Açık ve koyu uygulama paletleriyle üretilen dört sayfanın QtPdf
görüntüleri birebir aynıdır. Özet, uzun tek bir tablo yerine kısa metrik
gruplarına ayrıldı. Uzun kod/açıklama/SHA256 metinleri satıra sarılır;
tablolar gerçek sayfa boyutuna göre bölünür ve başlıkları tekrarlanır.
Sayfa numaraları içerikten ayrı alandadır. Parça açıklamaları da rapora eklendi.

Üretim PDF'inde kullanılan malzemelerin adı ve yoğunluğu gösterilir;
uzun GitHub/kaynak URL dökümü kaldırıldı. Dört sayfada bağlantı açıklaması
(PDF link annotation) yoktur. Malzeme kaynak kayıtları proje dosyasında
ve Excel'in **Malzemeler** sayfasında kalır; üçüncü taraf lisans bildirimleri
[mevcut lisans belgesinde](../THIRD_PARTY_NOTICES.md) korunur.

Kalıcı testler [test_nesting_pdf_report.py](../../modules/nesting/tests/test_nesting_pdf_report.py)
ile gerçek PDF açar ve görüntüler: açık/koyu palet eşitliği, koyu glifler,
beyaz kenarlar, uzun kod/açıklama/malzeme adı/SHA256, 90 örneğin eksiksizliği,
tekrarlanan tablo başlıkları, sayfa sınırları, bağlantı yokluğu ve iptal sırasında
mevcut PDF/kaynak DXF'in korunması denetlenir. Yeni bağımlılık eklenmedi;
test okuyucusu PySide6 ile gelen QtPdf'dir. Renk ve yazı büyüklükleri ayrıca
üretilmiş PDF üzerinden PyMuPDF ile okundu.

Çalıştırma: `QT_QPA_PLATFORM=offscreen python -m pytest
modules/nesting/tests/test_nesting_pdf_report.py modules/nesting/tests/test_nesting.py -q`.
Son doğrulamada **56 test geçti**; mevcut ezdxf/pyparsing kullanımından
gelen kullanımdan kaldırma uyarıları dışında hata görülmedi.

Doğrulama Linux/offscreen Qt ve gerçek PDF üzerindedir. Fiziksel yazıcı
ve Windows PDF görüntüleyicisi bu çalışmada çalıştırılmadı.
