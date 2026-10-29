# BOM izometrik reddi, segman kesimi ve karma mil operasyonları

Kaynak: `2d15abe`, dal: `main`, dizin: `/workspace/gokworks`.

## Kullanıcıda görülen hatalar ve değişiklikler

**BOM:** Excel'in tüm görsel hücrelerinde “izometrik görünüş doğrulanamadı”
yazıyordu. Eski kontrol `Orientation3` kamera matrisini modelden piksele
dönüşüm gibi kullanıyordu. Resmî `IModelView.Transform` sözleşmesi bu dönüşüm
içindir. Kontrol artık doğru matrisi, ekrana sığdırma ve yeniden çizimden
sonra kullanır. Üç model ekseninin ekran uzunlukları zoom'dan bağımsız
oranlarla karşılaştırılır; görüntü matrisi yuvarlaması için %0,01 tolerans
vardır. `Orientation3` önceki görünümü geri yüklemek için korunur.

Test fixture'ında kamera ve piksel matrisleri ayrıldı. Önce başarısız olan
senaryolar: ters kamera matrisinde geçerli izometri, çok küçük/büyük zoom,
kamerası izometrik olsa da ekranı ön görünüş olan yanlış görüntü ve yalnız
redraw sonrasında güncellenen native görünüm. Bu senaryolar düzeltmeyle geçti.
Görsel gömme, konfigürasyon eşleme, iptal ve görünüm geri yükleme testleri de
yeniden geçti. Gerçek CAD görüntüsü yerine test resmi üretildiği iddia edilmez;
otomatik testlerin CAD sınırı mock'tur.

**Segman:** Kullanıcının gerçek oturumunda eskiz/eksen seçilmiş olmasına
rağmen `FeatureRevolve2` null döndürdü. Önceki seçim düzeltmesi bu CAD hatasını
çözmedi. Segman artık kurulu interop'ta açık olan **`FeatureRevolveCut2`**
uyumluluk sözleşmesini kullanır: tek yön tam 360°, `swAutoCloseSketch`, tek
katı gövde üzerinde otomatik kapsam. Eskiz işareti 0, eksen 4'tür. Çağrıdan
sonra native `RevCut`, rebuild, tek gövde ve analitik talaş hacmi doğrulanır.
Bu, daha az parametreli doğrudan kesme API'sidir; ASME/ISO hesap değişikliği
veya ithal/mesh gövde çözümü eklenmedi. Bu eski API'nin gerçek CAD çekirdeği
sonucu burada çalıştırılmadı; null dönüşünün bütün olası sebeplerinin
belirlendiği veya kesmenin canlı ortamda geçtiği iddiası yoktur.

**Kama ile pah/radyüs:** Yapım sırası kademeler → pah → radyüs → segman → kama
oldu. Uç kenarları, kanal kesmeleri topolojiyi değiştirmeden işlenir. Gerçek
çakışmaların engellenmesi korunur. Python işlem planı ve C# sırası aynıdır;
model alanları ve operasyon kimlikleri değişmez. Kenar merkezi/normalinin
profil koordinatlarından model uzayına dönüşümü kullanılır.

Sabit radyüs için `FeatureFillet3`, SW 2020'den beri bu işlemde eski API
olarak belirtilmektedir. Güncel `CreateDefinition(swFmFillet)` +
`ISimpleFilletFeatureData2.Initialize(swConstRadiusFillet)` + `CreateFeature`
kullanılır. Dairesel, tek sabit yarıçap ve yalnız seçilen kenar açıkça atanır.
Başlatma hatasında `CreateFeature` çağrılmaz. Kısmi parça, hata halinde
inceleme için açık bırakılmaya devam eder; otomatik kaydedilmez.

## Dosyalar ve sözleşmeler

- `modules/bom/images.py`, `modules/bom/tests/test_images.py`, BOM README.
- `modules/shaft_generator/geometry.py`, `interop/ShaftHost.cs`, mil README.
- Mil testleri: `test_geometry.py`, `test_channel_selection.py`,
  `test_windows_transport.py`, `test_live.py`, `native/ChannelProbe.cs`.
- Mil JSON v1, `Part/Node/Result`, bağlantı, JobManager, Pack and Go ve PDF
  API'leri korunur. Mil `plan` yeniden hesaplanan bir iş anlık görüntüsüdür;
  alanları aynı, yapım sırası yukarıdaki gibidir. Eski/stale planlar mevcut
  doğrulama tarafından reddedilir.
- Ortak 11 korunan dosya, ana pencere ve paketleme betiği değiştirilmedi.
  Yedek depo ve `release` dalı güncellenmedi.

## Doğrulama

- Linux/offscreen: **426 JUnit kaydı, 0 hata/başarısızlık, 29 atlama**:
  [Arşiv: JUnit](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261026-native-iso-tests.xml).
- [Windows BOM/Qt](https://github.com/gkkizil/gokworks/actions/runs/40333962663):
  **94 kayıt, 0 hata/başarısızlık, 1 lisanslı CAD atlaması**.
- [Windows STA/köprü](https://github.com/gkkizil/gokworks/actions/runs/40333962808):
  gerçek PowerShell ve interop ile derleme, doğrudan cut API'sinin tüm
  parametreleri, modern radyüs tanımı/kenar kapsamı ve başarısız Initialize
  denetimleri geçti. Proxy testi native geometri başarısı uydurmaz.
- C# 5 / warnings-as-errors, gerçek 2023 interop / .NET 4.8 referanslarıyla
  yerel derleme ve Ruff F821/F822/F823 geçti.

Canlı kabul için `modules/bom/tests/test_images_live.py` ve
`modules/shaft_generator/tests/test_live.py` hazırdır. Mil canlı listesine aynı
kademede kama+pah, kama+radyüs, iki uç işlemi+kama ve segman+kama+iki uç işlemi
eklendi. Yeni parçaların hacimleri bağımsız referanslarla denetlenir. Bunlar
bu ortamda **çalıştırılmadı**. Kontrol kayıtları:
[doğrulama özeti](20261026-native-iso-checks.json).
