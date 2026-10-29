# Son düzeltmelerin kontrolü ve BOM izometrik görselleri

Kaynak sürüm `fad7108`, geliştirme dalı `main`, çalışma dizini
`/workspace/gokworks`. Bu çalışma önceki segman/kama/pah/açınım düzeltmelerinin
kontrolünü ve kullanıcının BOM Excel'e parça izometriklerini ekleme isteğini kapsar.

## İnceleme bulgusu ve düzeltme

Önceki pah/radyüs düzeltmesinde ek hata bulundu: formun hedef kademesi
değiştirilip ilk kenar eklendiğinde yeni kayıt modu eski kademe seçimini geri
getiriyordu. İki ayrı Qt testiyle pah ve radyüs için hata yeniden üretildi.
`modules/shaft_generator/ui.py::add_operation` şimdi eklenen operasyonun
`stage_id` değerini seçili kademe olarak korur. Diğer kenar aynı kademeye
eklenir; mevcut kaydın kenarı taşınmaz. İki regresyon testi düzeltmeden önce
başarısız, düzeltmeden sonra başarılıdır. Geometrik çakışma kuralları korunur.

Segman/kama C# değişiklikleri yeniden okundu ve gerçek 2023 interop / .NET
Framework 4.8 referanslarıyla C# 5, warnings-as-errors derlemesi tekrar geçti.
Windows STA/PowerShell köprü kontrolü son kaynakta da başarılıdır. Bu, CAD
çekirdeğinde gerçek kesme başarısı iddiası değildir. Önceki ham COM açınım
regresyonları da ilgili tam koşuya dahildir.

## Eklenen BOM özelliği

**Montajı oku → Excel kaydet** her kaynak parça/konfigürasyon için native
SolidWorks izometrik görünüşü alır. `ShowNamedView2` sonrasında perspektif
kaldırılır; dünya eksenlerinin ekrandaki kısalmalarının eşitliği doğrulanır.
BMP geçici klasörde okunur, PNG'ye dönüştürülür ve XLSX içine gömülür. Harici
resim klasörü veya bağlantı yoktur. Aynı kaynak/konfigürasyon bir kez okunur;
aynı dosyanın farklı konfigürasyonları ayrı görseldir.

“Parça listesi” ve “Ürün ağacı” sayfalarında mevcut sütunlar aynı sıradadır;
son sütun **Kaynak parça · izometrik** olarak eklenir. Görseli alınamayan satır
silinmez; nedeni ilgili hücreye yazılır. Alt montaj satırları “Alt montaj”
olarak kalır, yaprak parçalarda görsel vardır. Ağırlık, adet ve hiyerarşi
hesapları değiştirilmedi. Görseller Excel kaydı anındaki kaynak parça
geometrisidir; montaj bağlamındaki örneğe özel kesimleri temsil etmez. Bu
kapsam Excel üst bilgisinde açıkça yazılıdır.

İşlem mevcut worker/STA bağlantısında çalışır. Yeni SolidWorks sunucusu
başlatılmaz. Görünüm matrisi, kaydırma, ölçek, perspektif, kamera ilişkisi,
konfigürasyon, seçim, görünürlük ve aktif belge geri yüklenir. Kaynak CAD
dosyası kaydedilmez/rebuild edilmez. Sadece araç tarafından açılan belgeler
görselden sonra kapatılır. İptal veya geri yükleme hatasında mevcut XLSX
değiştirilmez; başarılı çıktı atomik yayımlanır.

## Dosyalar ve sözleşmeler

- Yeni: `modules/bom/images.py`,
  `modules/bom/tests/test_images.py`, `modules/bom/tests/test_images_live.py`,
  `.github/workflows/windows-bom.yml`.
- Değişen: `modules/bom/exporter.py`, `modules/bom/ui.py`,
  `modules/bom/README.md`, `modules/shaft_generator/ui.py`,
  `modules/shaft_generator/tests/test_ui.py`.
- `Part`, `Node`, `Result`, BOM ağırlık/adet ve mil JSON v1 sözleşmeleri aynı.
  Saf Excel API'sine yalnız opsiyonel keyword `previews=None` eklendi;
  bu fonksiyon kendi başına COM açmaz. Qt akışı yeni `export_worker` kullanır.
- Ortak 11 dosya, bağlantı/worker API'leri ve paketleme betiği değişmedi.
  Yedek depo ve `release` dalına dokunulmadı. Yeni EXE derlenmedi/yayımlanmadı.
  Başka ajanın çalışma ağacına girilmedi; değişiklikler mevcut `main` üzerinde
  kullanıcının hata bildirimi ve BOM talebiyle sınırlıdır.

## Doğrulama

- Linux / offscreen Qt: **416 JUnit kaydı, 0 başarısızlık/hata, 25 atlama**.
  Kapsam mil, DXF/DWG, BOM ve BOM'un gerçek Qt Excel/temizleme akışlarıdır.
  [Arşiv: JUnit](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261026-review-bom-tests.xml).
- [Windows BOM/Qt kontrolü](https://github.com/gkkizil/gokworks/actions/runs/40323751594):
  **89 kayıt, 0 başarısızlık/hata, 1 canlı SolidWorks atlaması**. Gerçek Windows
  Qt, Pillow, pywin32 VARIANT ve XLSX okuma/yazma kullanılır; CAD sınırı mock'tur.
- [Windows STA/köprü kontrolü](https://github.com/gkkizil/gokworks/actions/runs/40323751585):
  host derlemesi, ROT/ProgID, kesme çağrı argümanları, seçim, metre dönüşümü ve
  hata halinde kısmi belgeyi koruma testleri başarılıdır.
- PNG renkleriyle iki konfigürasyonun karışmadığı, iki sayfadaki resim
  anchor'ları, ZIP içi medya, sayısal değerler, literal hata metni, tekrar
  kullanımı, named camera ilişkisi, sadece sahip olunan belgeyi kapatma,
  iptal/başarısız kayıt ve eski görünümü geri yükleme kontrol edildi.
- Ruff F821/F822/F823 ve `git diff --check` geçti.
  [Kaynak/Windows/korunan dosya kontrol kaydı](20261026-review-bom-checks.json).
  Örtüşen Windows ve Linux test sayıları toplanmaz.

Gerçek lisanslı SolidWorks ve Microsoft Excel UI bu ortamda çalıştırılmadı.
`modules/bom/tests/test_images_live.py` açık bir test kopyasıyla kaynak hash'i,
konfigürasyon, görünüm ve PNG/XLSX kabulü için hazırdır. Çalıştırma talimatı
`modules/bom/README.md` içindedir. Önceki EXE bu yeni kaynak değişikliklerini
içermez. Sonraki güvenli adım, açık test kopyasıyla canlı CAD kabulüdür.
