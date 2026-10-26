# BOM · Ürün ağacı

Aktif SolidWorks montajını okuyarak parça adetlerini, hiyerarşiyi ve ağırlıkları
çıkarır. Üretim dosyalarını değiştirmeden Excel çıktısı oluşturur.

- [exporter.py](exporter.py): montaj okuma, adet/ağırlık ve Excel motoru.
- [ui.py](ui.py): GOKWORKS içindeki Qt ekranı.
- [images.py](images.py): dosya/konfigürasyona göre yerel SolidWorks izometrik
  görseli ve oturum görünümünü geri yükleme.
- [tests/](tests): motor ve SolidWorks sınırlarının regresyon testleri.
- [Ayrıntılı kullanım ve API sınırları](../../docs/bom.md).

Test: `python -m pytest modules/bom/tests`.

## Excel içinde izometrik parça görselleri

**Montajı oku → Excel kaydet** akışında parça görselleri otomatik alınır.
“Parça listesi” ve “Ürün ağacı” sayfalarının sonuna **Kaynak parça · izometrik**
sütunu eklenir. PNG'ler XLSX içine gömülür; Excel'i alan kişinin yan resim
klasörüne, SolidWorks'e veya internete ihtiyacı yoktur. Diğer sütunların sırası,
sayısal adet/ağırlık değerleri ve hiyerarşi korunur. Alt montaj satırlarının
yerine sahte parça görseli konmaz; ilgili yaprak parça satırlarında görsel vardır.

Görsel, Excel kaydı sırasında açık/lisanslı yerel SolidWorks üzerinden ilgili
SLDPRT ve **tam konfigürasyon adıyla** alınır. Aynı dosyanın farklı
konfigürasyonları ayrı değerlendirilir; yinelenen örnekler aynı görüntüyü
yeniden kullanır. Bunlar kaynak parça görselleridir; montaj bağlamındaki
örneğe özel kesimler görsele dahil değildir. Bu kapsam Excel üst bilgisinde
de yazılıdır. Ağırlık hesabı montaj örneklerini kullanmaya devam eder.

Mevcut STA bağlantısı yeniden kullanılır; yeni SolidWorks sunucusu
başlatılmaz. `ShowNamedView2(swIsometricView)` sonrası perspektif kaldırılır;
üç dünya ekseninin ekrandaki kısalmalarının eşit olduğu `MathUtility` ile
doğrulanır. Bu kontrol yeniden çizimden sonra **`IModelView.Transform`**
(modelden ekran pikseline dönüşüm) üzerinden, zoom'dan bağımsız oranlarla
yapılır. `Orientation3` yalnız önceki görünümü geri yüklemek içindir; onu
ekran dönüşümü gibi kullanmak geçerli izometrik görünüşleri reddediyordu.
`SaveBMP` yalnız geçici görüntü dosyası üretir; kaynak CAD kaydı,
yeniden oluşturma veya üretim parametresi değişikliği yapılmaz. Önceki
konfigürasyon, görünüm matrisi, kaydırma, ölçek, perspektif, kamera, seçim,
pencere görünürlüğü ve aktif belge geri yüklenir. Araç tarafından açılan
parçalar tek tek kapatılır; kullanıcının açık belgeleri kapatılmaz.

Görsel alınamazsa parça, adet ve ağırlık satırı korunur; neden ilgili görsel
hücresine yazılır. SolidWorks kapalıysa Excel verileri yine alınabilir, fakat
görseller için yeniden açık oturum gerekir. Geri yükleme başarısızlığı veya
iptalde mevcut Excel dosyası değiştirilmez. İşlem GOKWORKS worker'ında çalışır;
ilerleme ve iptal mevcut durum alanındadır.

Saf `export_excel(result, destination, stop_event=None, *, previews=None)`
çağrısı COM bağlantısı kurmaz; eski kullanım sözleşmesi korunur. Qt ekranı
`export_worker` üzerinden görselleri toplayıp bu parametreyi verir. `Part`,
`Node`, `Result` ve mevcut JSON/worker bağlantı sözleşmeleri değişmedi.

Testler BMP→PNG→XLSX gömmeyi, hücre bağlantılarını, konfigürasyon eşleşmesini,
bilinmeyen görselleri, iptali ve eski görünümün geri yüklenmesini kapsar. CAD
sınırı bu testlerde mock'tur. Gerçek SolidWorks kabulü için açık bir **test
kopyası** ile ayrıca:

```powershell
$env:GOKWORKS_BOM_IMAGE_LIVE_SOURCE='C:\test\part-copy.SLDPRT'
$env:GOKWORKS_BOM_IMAGE_LIVE_CONFIG='Default'
python -m pytest modules/bom/tests/test_images_live.py -v
```

Bu canlı test, açık test parçasının dosya hash'ini, görünümünü ve
konfigürasyonunu denetler. Otomatik Windows kontrolü lisanslı CAD çalıştırmaz;
Excel görseli için üretilen OOXML/PNG içeriğini okur, Microsoft Excel UI'sini
çalıştırmaz.
