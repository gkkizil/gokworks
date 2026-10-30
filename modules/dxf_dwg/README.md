# DXF / DWG — Sac gövdesi ve montaj bazında aktarım

Mevcut Qt Widgets ekranı, SolidWorks COM bağlantısı ve güvenli geçici dosya
altyapısı genişletildi. Yerel, kurulu ve lisanslı SolidWorks gerekir. Python
native SLDPRT/SLDASM dosyasını ayrıştırmaz; yeni CAD okuyucu veya bulut API yoktur.

## Kullanım

1. **Aktif montajı tara**: SolidWorks'teki etkin SLDASM ve aktif konfigürasyonundan
   başlar. Etkin SLDPRT de okunabilir.
2. **Dosya seç…**: SLDPRT veya SLDASM seçilir. Araç belgeleri sessiz/salt okunur
   açar; kullanıcının önceden açtığı belgeler korunur.
3. **Klasörü tara**: klasör/alt klasör kapsamını korur. Etkin ana montaj varsa
   yalnız kapsamdaki kullanılan sacları ve gerçek montaj adetlerini okur.
   Etkin montaj yoksa her bağımsız parça dosyası bir örnek sayılır.
4. Yalnız `IBody2.IsSheetMetal()` ile doğrulanan sac gövdeleri listelenir.
   Mekanik bileşenler için başka liste/gizli sekme oluşturulmaz. Doğrulanamayan
   kaynak/bileşenler **Günlük** bölümünde açıklanır.
5. **Tümünü seç / Seçimi kaldır**, hazır sacların kutularını değiştirir.
   **Grupla** kapatılırsa aynı dosya/konfigürasyon/gövdenin montaj örnekleri
   ayrı görünür. Seçimler kaybolmaz. Kısmen seçili grubun kutusu ara durumdadır;
   yalnız işaretli örneklerin adedi aktarılır.
6. Çıktı klasörü/türü, büküm çizgileri ve kalınlık klasörlemesini belirleyin.
   **Seçili parçaları dışa aktar** yalnız işaretli, doğrulanmış gövdeleri işler.

Sütunlar: seçim, parça/kod, gerektiğinde gövde, kalınlık (mm), malzeme, adet,
açınım durumu, açıklama. Kaynak dosya, konfigürasyon ve Cut List klasörü satır
ayrıntılarında/ipuçlarında korunur. Açınımı bozuk gerçek sac, hatalı satır olarak
kalır; diğer hazır sacların aktarımını engellemez.

## Kaynak güvenliği ve durdurma

Yeni envanterden tarama, önizleme ve aktarım, kaynaklara `Save3`/`SaveAs`
uygulamaz; kaydedilmemiş kullanıcı çalışması da otomatik kaydedilmez.
Konfigürasyon, seçili nesneler, görünürlük ve aktif belge geri alınır.
Geometri, suppression, otomatik Cut List ve layer ayarları değiştirilmez.
Araç yalnız kendisinin açtığı belgeleri kapatır. Cut List yenilenmez, rebuild
yapılmaz. Güncellik doğrulanamıyorsa SolidWorks'te rebuild yapıp yeniden tarayın.

**Durdur**, sonraki gövde/biçimi ve geçici çıktının yayımlanmasını engeller.
Tarama STA'sında bekleyen okunur COM çağrısına iptal istenir; büyük montajın
toplam tarama süresine sabit 60 saniye sınırı konmaz. Önizleme mevcut 60 saniye
korumasını kullanır. SolidWorks sunucusu iptali reddedebilir; native export
çağrısı zorla kesilmez. Durum geri alınmadan CAD işi bırakılmaz; geri alma
hatası iptal/başarı gibi gizlenmez.

Eski scriptlerin `export_parts(..., items=None)` ve `export_one_part` çağrı
sözleşmeleri korunur. Eski script yolu tek etkin gövde sınırını ve daha önce
istenmiş Save All politikasını taşır; normal yeni Qt akışı `items` gönderir
ve kaynak kaydetmez. Kimlik verilmeden çok gövdeli aktarım yapılmaz.

## Gövde eşleşmesi, adet ve performans

`GetBodies2(swSolidBody, False)` ile gövdeler okunur. Sac olmayan belgede
özellik/metadata/mesh/açınım taraması yapılmaz. `FlatPattern` tanımındaki
`FixedFace2.GetBody()` gövdeyi belirler. `CutListFolder` ve
`GetSpecificFeature2().GetBodies()` aynı gövdenin Cut List özelliklerini verir.
`Get6` ham/çözümlenmiş değerleri ayrı saklar. Kalınlık gövdenin SheetMetal
unsurundan metre→mm çevrilir; belirsiz çoklu kalınlık tahmin edilmez.

Montaj her fiziksel örnek için dolaşılır; parça analizi dosya+referenced
configuration başına önbelleklenir. Suppressed dal dışarıda kalır. Lightweight
model gerekiyorsa ayrı salt okunur belgeden yüklenir; montaj suppression durumu
değiştirilmez. Eksik alt montaj yüzünden eksik kalabilecek adetler doğrulanmış
sayılmaz. Sanal saclar okunabildiğinde listelenir; üretim dosyası/önizleme için
harici SLDPRT olarak kaydedilmeleri istenir. SpeedPak için tam montaj gerekir.

Her biçimde kalıcı gövde ve Flat-Pattern kimlikleri tekrar çözülüp sahiplik
kontrol edilir. `SuspendSelectionList` ile seçim saklanır; yalnız ilgili
`FlatPattern.Select2(False,-1)` seçilip `ExportToDWG2` çağrılır. Sonunda
`ResumeSelectionList2(False)` önceki seçimi geri getirir.

## Adlandırma ve geometri kontrolü

Tek gövdede eski ad korunur: `BRAKET - 1.5 mm - 12 adet.dxf`.
Çok gövdede gövde adı ve sabit kimlik; birden fazla kullanılan konfigürasyonda
konfigürasyon ayrımı eklenir. Kod/gövde/malzeme/konfigürasyon adlandırma seçenekleri
vardır. `mm` ve `adet` alanları Nesting okuyucusuyla uyumludur. Kalınlık klasöründe
virgül, dosya adında nokta kullanılır. Hedef çakışmaları kimlik ekiyle ayrılır.
Mevcut dosya varsayılan atlanır; üzerine yazmada önce geçici çıktı doğrulanır.

DXF yapı/audit, geçerli geometri ve yaygın çizgi/yay/daire/polyline türlerinin
aynı katmandaki kesin mükerrerleri denetlenir; layer'lar yeniden yazılmaz.
DWG başlığı denetlenir; binary DWG geometri çözümleyicisi eklenmedi. Native
sheet-metal API'si 1:1 üretim yolu olarak kullanılır; gerçek boyutlar ve
katman eşdeğerliği lisanslı Windows kabul testi gerektirir.

## Önizleme ve doğrulama

Mevcut sağ 3D / açınım / bilgi paneli korunur. İstek/önbellek dosya,
konfigürasyon, kalıcı gövde ve revizyonla ayrılır. Aynı dosyanın ikinci gövdesi
birincinin görüntüsünü kullanmaz. Açınım seçilen Flat-Pattern üzerinden geçici
DXF ile okunur; DWG dosyası okunmuş gibi sunulmaz. Önizleme üretim çıktısını
ve kaynak CAD'ı kaydetmez. İlk tıklama görsel kontrolü açar, kayıt kendiliğinden
başlamaz. Bu, bütün gövdeler için imalat geometri sertifikası değildir.

Yeni testler: `tests/test_sheet_inventory*.py`, `test_flat_checks.py`.
Gerçek SolidWorks kabulü: `tests/test_multibody_live.py`.
[Ayrıntılı rapor, sınırlamalar ve test komutları](../../MULTIBODY_DXF_DWG_RAPORU.md).
