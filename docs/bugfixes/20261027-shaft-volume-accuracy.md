# Parametrik mil: kama kanalının hacim doğrulaması

## Bildirim ve bulgu

Kullanıcının ekranında kama kesimi oluşuyor ve katı-model taban derinliği
5,5 mm olarak doğrulanıyor; işlem daha sonra talaş hacmi karşılaştırmasında
duruyor. Görseldeki kama ölçüleri Ø45, toplam boy 50 mm, genişlik 14 mm,
radyal derinlik 5,5 mm ve başlangıç 7 mm. Küçültülmüş görüntüde ölçülen hacim
kesin okunamadı; kullanıcı pencereyi kapattığından tam hata metni alınamadı.
Özgün SLDPRT/proje dosyası sağlanmadı.

`Builder.Volume()` eski `CreateMassProperty()` / `IMassProperty.Volume`
yolunu kullanıyordu. Bu nesnede hesap doğruluğu seçilmediği için belgenin
varsayılan entegrasyon hassasiyetine bağlı iki toplam hacim, küçük bir
kanalın sıkı hacim kontrolünde birbirinden çıkarılıyordu. Eski arayüzde
`AccuracyLevel` veya `Recalculate` üyesi yoktur; güncel API'de ikisi de vardır.
Bu, gerçek CAD dosyasıyla yeniden üretildiği iddia edilen bir kernel sonucu
değildir; kodda tespit edilen kontrolsüz doğruluk yolu düzeltilmiştir.

## Değişiklik

- Her hacim okuması için geçici `IMassProperty2` nesnesi oluşturulur.
- `UseSystemUnits = true` ve `AccuracyLevel = Higher (2)` uygulanır ve geri
  okunur; ardından `Recalculate()` başarılı olmadan `Volume` okunmaz.
- Eksik nesne, uygulanmayan SI/doğruluk ayarı, başarısız yeniden hesaplama,
  sıfır/negatif/NaN/sonsuz hacim reddedilir. Eski/düşük doğruluklu API'ye
  sessiz dönüş yoktur.
- Doğruluk ayarı yalnız geçici hesap nesnesindedir. Belge tercihleri ve CAD
  geometrisi değiştirilmez. Kayıt/başarısız parçayı açık bırakma politikası
  korunur.
- Gerçek taban derinliği, native kör kesme boyu, tek gövde, rebuild ve talaş
  kontrolleri korunur. `VerifyRemoval` toleransı **değişmedi**:
  `max(1e-15 m³, beklenen × 1e-5)`.
- Python model/JSON v1 sözleşmesi, eskiz/kesim üretimi, operasyon sırası ve
  diğer modüller değiştirilmedi.

İlgili kaynak: `modules/shaft_generator/interop/ShaftHost.cs`,
`Builder.Volume()`. İmza ve `Higher=2` değeri geçici SOLIDWORKS interop
referanslarının metadata'sından kontrol edildi. Referans DLL'ler uygulamaya
paketlenmez; çalışma anında kullanıcının kurulu SolidWorks DLL'leri kullanılır.

## Kontroller

- Yerel mil paketi: **207 JUnit kaydı, 0 hata/başarısızlık, 35 atlama**;
  11 sınırlı süreç grubunun tamamı exit 0. Atlamalar canlı CAD/Windows içindir.
  [JUnit](20261027-shaft-volume-tests.xml).
- Gerçek C# host, geçici 2023 interop referanslarına karşı yerel .NET SDK ile
  derlendi: **0 hata, 0 uyarı**. Bu bir SolidWorks çalıştırması değildir.
- Yeni Windows native fixture testi gerçek `Builder.Volume()` metodunu
  .NET Framework API proxy'leriyle çağırır. 10 mod: başarılı okuma; eksik
  factory; reddedilen SI; reddedilen doğruluk; başarısız/exception atan
  recalculation; NaN; sonsuz; sıfır; negatif hacim. Kaydetme/tercih değiştirme
  gibi beklenmeyen API çağrısı testi durdurur.
- Native C# beklenen hacim testine eklenen Ø45 × 50 × 14 × 5,5 örneği,
  eksen boyunca bağımsız Python kesit integraliyle karşılaştırılır. Beklenen
  talaş yaklaşık **3390,5452 mm³**'tür. Küçük eksik/fazla kesimler de
  reddedilerek kabul toleransının gevşemediği sınanır.
- Canlı CAD için `reported_keyway_volume` senaryosu eklendi: görüntüdeki
  dört kademe ve kama ölçüleri, temsili segman/pah yerleri, kaydet-aç ve
  bağımsız son hacim kontrolü. Orijinal proje olmadığından bütün operasyon
  yerlerinin birebir kopyası olduğu iddia edilmez.
- Ruff F821/F822/F823 ve whitespace denetimi geçti.

Bu Linux ortamında lisanslı SolidWorks yoktur. Gerçek kullanıcının dosyasıyla
yüksek doğrulukta yeniden hesaplamanın sonucu henüz doğrulanamadı. Native
Windows testleri de lisanslı CAD geometrisi üretmez; API/protokol testleridir.
