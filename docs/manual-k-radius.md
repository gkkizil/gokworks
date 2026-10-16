# Kalınlığa göre manuel K / R atama

## Ana ve gövde sacında tablo kontrolü — 16 Ekim 2026

Kullanıcının günlüğünde ana `TemplateSheetMetal` ve gövde `SheetMetal`
bulunmasına rağmen `GetUseGaugeTable` için kod `2` alınıyordu. Eski hata
metni bu çağrının hangi unsurda başarısız olduğunu belirtmiyordu. Yeni hata
metninde unsur adı/türü ve API adı bulunur. Bu kod, tablonun kullanılmadığı
anlamına gelmez; başarısız çağrının çıkış değerleri veya malzeme özelliği okunmaz.

Ana şablonda kod `2` varsa gövdede başarılı tablo/malzeme kontrolü gerekir.
Gövde kod `2` döndürürse yalnızca ana şablon kontrolü başarılı olmuş ve
gövdenin iki özel parametre bayrağı da kapalıysa ana unsurun doğrulanmış
durumu kullanılabilir. Gövdedeki başarılı kontrol gerçek tablo veya malzeme
bağı gösterirse işlem durur. Her iki kaynak kullanılamıyorsa, bağımsız ayarlar
varsa veya başka hata kodu alınırsa yazılmaz. Bu durumlar önizlemede de aynıdır.
API imzaları ve enum değerleri [sözleşme kaydında](reports/k-radius/api-contract.json)
bulunur; gerçek SolidWorks doğrulamasının yerini test nesneleri almaz.

## Çok gövdeli parçalar — 16 Ekim 2026

Tek sac gövdesi yanında normal katılar bulunan parça, gövdenin sac unsuruyla
bağı doğrulandığında işlenir; normal katılar K/R kapsamı dışında kalır.
Birden fazla sac gövdesinde ortak ana `TemplateSheetMetal`, aynı gerçek sac
kalınlığı ve **Tüm bükümlere uygula** gerekir; bu durumda bütün katı gövdeler
sac olmalıdır. Her sac gövdesinin `IBody2.GetFeatures`
ile bulunan sac/dönüştürme unsurlarına bağlı olduğu doğrulanır. Bir unsurun
birden fazla gövde üretmesine izin verilir; gövde ve unsur sayıları eşit olmak
zorunda değildir.

Farklı kalınlıklar ortak ana ayarla değiştirilmez. Gövde bağı okunamıyorsa
yazılmaz. Uygulama sonrasında gövde sınıfları/sayıları, sac unsurlarının K/R
değerleri ve kalınlıklar tekrar kontrol edilir; başarısızlıkta geri alma ve
gövde kontrolü yapılır. Kullanıcının `ARMJR075001` dosyasının bu koşulları
sağladığı bu ortamda doğrulanmadı.

113 ilgili K/R arka uç ve COM sözleşmesi kontrolü geçti. Önizlemenin yazmaması,
kod 2 için doğrulanmış üst/gövde kaynağı, gerçek tablo/malzeme engelleri,
aynı/farklı kalınlıklı gövdeler, gövde sahipliği, gövde sayısının değişmesi,
diğer konfigürasyonlar ve hata sonrasında geri alma kontrol edildi.

## AccessSelections tür uyuşmazlığı düzeltmesi — 15 Ekim 2026

İşlem günlüğündeki `AccessSelections: -2147352571, Tür uyuşmazlığı, 2`
hatası için parça bağlamındaki boş `Component` parametresi artık açıkça
`VARIANT(VT_DISPATCH, None)` gönderilir. pywin32, çıplak Python `None`
değerini `VT_NULL` yapar; bu değer SolidWorks'ün beklediği boş bileşen
nesnesi değildir. İlgili
[pywin32 b312 dönüşümü](https://github.com/mhammond/pywin32/blob/2a277cb5552756c2b4d42b524dc36d25e0bb6354/com/win32com/src/oleargs.cpp#L217)
incelendi.

Aynı çağrı yolu `AccessSelections` ve `ModifyDefinition` için ana sac,
alt büküm ve katıdan saca dönüşümde kullanılır. Geri alma da aynı türlenmiş
parametreyle çalışır. Hata metni sonuç satırının başına alınır; geri alma
doğrulanamazsa uyarı en başta gösterilir ve dosya kaydedilmez.

K/R ve geri alma akışındaki 76 ilgili kontrol geçti. Üç yeni COM sözleşmesi
kontrolü, aynı tür hatasını eski kodda yeniden üretti; düzeltilmiş kodda
kullanıcının K/R değerleri, sac kalınlığı ve önceki büküm ayarlarının geri
alınması doğrulandı. Dönüştürme unsuru bulunmayan parçalarda farklı ana/gövde
kalınlıkları yazmadan önce durdurulur. Canlı SolidWorks bu ortamda çalıştırılmadı.

**K faktörü / yarıçap** artık **Manuel K / R** sekmesiyle açılır. SolidWorks'e
atama her zaman burada girilen değerleri kullanır. **Hesap yardımı** sekmesi
bağımsız hesap içindir; tablo sonucu montaj atamasına gönderilmez. Buradan
tarama veya uygulama başlatıldığında da manuel değerler gerekir.

Hedef, SolidWorks ağacındaki **Sac-Levha** unsurunun **Büküm yarıçapı** ve
**Büküm izni → K-Faktörü** alanlarıdır. Örneğin R=2 mm, K=0,274 girilince
bu alanlara sırasıyla 2 mm ve 0,274 yazılır; mevcut sac kalınlığı korunur.
Ana `TemplateSheetMetal` unsuru ve ona bağlı `SheetMetal` gövde unsuru adları
yerine API türleriyle bulunur; Türkçe ad veya kullanıcı tarafından ad
değiştirilmesi seçimi etkilemez. İşlem günlüğünde bulunan unsur adları gösterilir.

Her kalınlık için ayrı satıra üç değer girilir. **Satır ekle** ile başka
kalınlıklar eklenir; **Sil** ile satır kaldırılır. Eski tek satır ayarları ve
yeni satırlar kaydedilir; sonraki açılışta geri yüklenir.

14 Ekim 2026 güncellemesinde 18 ilgili kontrol geçti: hesap yardımından atama
başlatıldığında da yalnız manuel değerlerin kullanılması, tablo çağrısının
atamaya girmemesi, Sac-Levha ana/alt unsuruna yazma, kalınlık filtresi,
tarama sırasında sıraya alınan uygulama, kayıt/rapor ve küçük ekran yerleşimi.
Sol kod incelemesi de tamamlandı. SolidWorks COM sınırı test nesneleriyle
temsil edildi; gerçek montaj bu bulut ortamında çalıştırılmadı.

| Sac kalınlığı (mm) | K faktörü | Yarıçap R (mm) |
| ---: | ---: | ---: |
| 1,5 | 0,274 | 1,5 |
| 2 | 0,30 | 2 |
| 3 | 0,32 | 3 |

Bu değerler ekran örneğidir; malzeme önerisi değildir. Her satırdaki K ve R
kullanıcının verdiği değerlerdir. Tek montaj işleminde tüm satırlar eşlenir;
sac olmayan parçalar ve satırı bulunmayan kalınlıklar atlanır.

Nokta ve virgül ondalık ayırıcı olarak kabul edilir. Hedef kalınlık listeden
seçilebilir veya özel değer olarak yazılabilir. K ve R kullanıcı tarafından
doldurulur; başlangıçta bu alanlara üretim değeri atanmaz.

1. Ana montajı SolidWorks'te aktif yapın; **Manuel K / R** sekmesini açın.
2. Kalınlık, K ve R değerlerini girin. Başka kalınlıklar için **Satır ekle** kullanın.
3. **Montajı tara** ile yazma yapmadan eşleşmeleri ve girdiğiniz hedef değerleri görün.
   Uygun parçalar **Uygulamaya hazır** gösterilir; “Önizleme; K/R uygulanmadı”
   açıklaması mevcut ve hedef değerleri ayırır.
4. **Montaja K/R uygula** ile eşleşen sac parçalarının sac metal parametrelerini
   güncelleyin. `2 mm → K=0.274, R=2 mm` örneğinde 1, 1.99, 2.01 ve 3 mm
   saclar, kendileri için başka satır girilmediyse atlanır; bu parçalar için
   K/R yazımı veya dosya kaydı yapılmaz.
5. Varsayılan değişiklik SolidWorks belleğindedir. Dosyalara da kaydetmek
   isterseniz **Parça dosyalarını kaydet** seçeneğini işaretleyin.

Gerçek uygulama sonucu **Uygulandı** gösterilir. Başarı, istenen K ve R'nin
yazılması, yeniden oluşturma ve değerlerin SolidWorks'ten geri okunmasıyla
doğrulanır. Bellekte uygulama ile dosyaya kaydetme ayrı işlemlerdir.
`128` açma bilgisi, parçanın zaten yüklü olduğunu belirtir; hata anlamına
gelmez. [Güncelleme ve yerel kontrol adımları](local-solidworks-check.md).

Aktif montajın aktif konfigürasyonu, alt montajlar dahil dolaşılır. Aynı
dosya/referans konfigürasyonu bir kez işlenir, montaj adedi raporda gösterilir.
Sac kalınlığı SolidWorks sac metal unsurundan okunur; mm hesabına çevrilir.
Birimi dönüştürürken oluşan kayan nokta hataları için sabit `0.000001 mm`
tolerans kullanılır; kalınlıklar iki ondalığa yuvarlanarak eşleştirilmez.

Girdiğiniz **K ve R aynen kullanılır**. Manuel sekme malzeme tablosu, V kalıp
tahmini, bıçak ölçüsü veya BA kalibrasyonu istemez. Hesap yardımı sekmesindeki
ayarlar ve manuel değerler ayrı saklanır; iki sekme arasında geçişte korunur.
K `0–1` aralığında; kalınlık ve R pozitif ve sonlu olmalıdır. Boş/geçersiz
alanlarla tarama ve uygulama başlatılmaz.
Aynı kalınlık iki satıra girilemez; eşleştirme aralıkları çakışacak kadar yakın
kalınlıklar da reddedilir. İlk uygun satır rastgele seçilmez.

SolidWorks'e `KFactor=0.274`, büküm payı türü `K factor (2)` ve
`R=0.002 metre` yazılır. Ana sacın kendisine ait tek yarıçap ölçüsü varsa
`SetSystemValue3` ile yalnız hedef konfigürasyona yazılır; ölçü yoksa
`BendRadius` unsur tanımı kullanılır. Mevcut sac kalınlığı değiştirilmez. Önceki
K/R sürümündeki geri okuma, rebuild, konfigürasyonların korunması, hata
halinde geri alma ve önceki montaja dönüş kontrolleri kullanılır. Farklı
kalınlıklı/bağı doğrulanamayan çok gövdeli veya gauge/malzeme tablosuna bağlı
parçalar için destek sınırları sürer;
[ayrıntılar](k-factor-radius.md).

**Tüm bükümlere uygula** başlangıçta açıktır. Özel K/R kullanan destekli
bükümler ana sacın yarıçapını ve büküm payını kullanacak şekilde güncellenir.
Modern `SheetMetal` alt unsurundaki K/R override'ları da kaldırılır; bunun
kalınlığı değiştireceği bir parça işleme alınmaz. Seçenek kapalıysa özel
büküm ayarı bulunan parça, açıklamasıyla birlikte durdurulur. Tercih iki
atama sekmesinde ortaktır ve sonraki açılışta korunur.

Tarama yalnız uygulanacak kapsamı kontrol eder. Gerçek uygulamada ana K/R,
alt sac değerleri ve bükümlerin varsayılan ayarları geri okunur. Hata halinde
önceki K/R ile özel yarıçap, büküm payı türü/değeri ve override durumları
birlikte geri yüklenip doğrulanır.

[Power-SM uyarlamasının kaynakları ve kapsamı](reports/power-sm-adaptation/README.md).

CSV raporunda başarılı, farklı kalınlık nedeniyle atlanan ve hatalı parçalar
ayrı görünür. Küçük pencerede form kaydırılabilir; tarama, uygulama ve sonuç
listesi erişilebilir kalır.

[Açık GUI](screenshots/gui-manual-k-radius-light.png) ·
[Koyu GUI](screenshots/gui-manual-k-radius-dark.png)

Linux testlerinde gerçek Tk arayüzü çalıştırıldı; SolidWorks COM sınırı test
nesneleriyle temsil edilir. Gerçek Windows/SolidWorks montajında uygulama
bu bulut ortamında çalıştırılamaz.

## Çoklu kalınlık ve katıdan dönüştürülen saclar — 15 Ekim 2026

Atama `AssignmentTable` içindeki kullanıcı satırlarıyla yapılır. Kalınlık,
gövdenin `SheetMetal.Thickness` veya `SolidToSheetMetal.SheetThickness`
alanından metre cinsinden okunup mm'ye çevrilir. Gövdenin sac bayrağı kapalı
olsa da etkin `SolidToSheetMetal` unsuru varsa ana sac hedefi ayrıca doğrulanır.
Gerçek katı parçalar atlanır. K/R okuma için DXF aktarım arayüzü gerekmez.

COM keşif metotları ilgili alt nesnede açıkça metot olarak işaretlenir.
Sacla ilgisiz unsurların K/R tanımları sorgulanmaz. **Tüm bükümlere uygula**
açıkken dönüştürme unsurunun özel K/R ayarları ana sac değerlerine bağlanır.
Ana varsayılan kalınlığı gerçek sacdan farklıysa önce bu varsayılan gerçek
kalınlığa eşitlenir, sonra miras ayarları değiştirilir. Fiziksel sac kalınlığı
korunur; bu eşitleme günlükte açıkça gösterilir. Hata halinde eski ana kalınlık,
K/R ve özel ayarlar geri yüklenip tekrar kontrol edilir. Başka konfigürasyona
yayılan değişiklikler de geri alınır.

Tek gövdeli sac kapsamı sürer; çok gövdeli veya gauge/malzeme tablosuna bağlı
parçalar sessizce başarılı gösterilmez. Sonuçta ilgili parça ve engel yazılır.

91 ilgili kural/COM/kayıt kontrolü ve 15 gerçek Tk arayüz kontrolü doğrulandı.
Karma montaj senaryosunda iki farklı kalınlık ayrı K/R satırlarıyla güncellendi;
eşleşmeyen sac ve katı parça atlandı. Mevcut konfigürasyon, dosya kayıt durumu,
geri okuma ve geri alma kontrolleri korundu. Canlı SolidWorks geometrisi bu
bulutta doğrulanmadı; tam test paketi çalıştırılmadı ve EXE oluşturulmadı.

[Çoklu kalınlık ekranı](../k_factor/examples/thickness-assignments-dark.png) ·
[Ekranı yeniden çekme](../k_factor/examples/capture.py).

## SolidWorks 2025 hata incelemesi

Dönen COM nesnesi çağrılabilir olsa da varsayılan üyesi çağrılmaz. Büküm payının yalnız etkin türünün alanı okunur; K atamasında tür 2, K ve R yazılır. Başka türden dönüşte geri alma o türün aktif alanını geri yükler. Kalınlık filtresi eşleşmeyen saclar için K/R API erişiminden önce uygulanır. Hatalar aşama ve üye adını gösterir. Aynı `Üye bulunamadı` HRESULT davranışı test nesnesiyle yeniden üretildi; gerçek SolidWorks 2025 bu bulutta çalıştırılmadı.

[Yeni yerleşim ve kanıtlar](reports/kr-workspace-fix/README.md) · [Yerel kabul kontrolü](local-solidworks-check.md).

## 13 Ekim 2026 çağrı ve hata görünürlüğü düzeltmesi

`GetUseGaugeTable`, `GetOverrideDefaultParameter2` ve `Save3` çağrıları,
kendi COM nesnelerinde `DumbDispatch` üzerinden yapılıyor. Yalnız ana
SolidWorks nesnesini dönüştürmek yeterli değildi: alt nesneler yeniden tür
bilgisiyle oluşturulabiliyor; çıkış değerleri tuple olarak dönüyor veya
açık VARIANT çıkışlarıyla çakışıyordu. Bu durum başarılı bir sac kontrolünü
hatalı gösterebiliyor, kayıt hatasının okunmasını da etkileyebiliyordu.
[pywin32 b312 çağrı sarmalayıcısı](https://github.com/mhammond/pywin32/blob/2a277cb5552756c2b4d42b524dc36d25e0bb6354/com/win32com/client/dynamic.py#L361)
incelendi; regresyonlar test nesneleriyle doğrulandı.

Kaydedilmemiş değişiklik kontrolü artık belge etkinleştirilmeden ve
konfigürasyon değiştirilmeden önce alınır. Programın kendi geçişinin
oluşturduğu kayıt işareti atamayı engellemez; önceden bulunan kullanıcı
düzenlemeleri için kayıt koruması sürer.

Geçersiz girişle uygulama istendiğinde form görünür hale gelir ve neden
başlatılmadığı durum satırında yazılır. Parça bazında hata oluştuğunda
**Günlük** açılır. **Günlüğü kopyala**, girilen manuel değerleri, dosya adını
ve tam hata metnini birlikte kopyalar. **Hesapla ve kontrol et** sonuç
ekranından girişlere ve hesap özetine geri döner.

Bu düzeltmelerin kullanıcının montajındaki hatayı giderdiği henüz gerçek
SolidWorks oturumunda doğrulanmadı. Devam eden hatanın tam metni günlükten
alınabilir. Güncel ekranlar ve hedefli kontrol kayıtları [burada](ui-preview/README.md).

## Montaj içinde yüklü parçaların okunması

K/R işçisi artık sac parametrelerini `ActivateDoc3` tarafından döndürülen
güncel parça belgesinden okur. Önceden montaj bağımlılığı için alınan eski
`GetOpenDocument` nesnesi kullanılmaya devam ediyordu. SolidWorks belgesi,
kendi penceresinde açılmamış bir parçanın bu nesnesinde yöntemlerin düzgün
çalışmayabileceğini belirtir. İlk nesne yalnız önceki konfigürasyon, kayıt
durumu ve belge sahipliğini korumak için kullanılır.

`swDocNeedsRebuildWarning = 2` belgeyi etkinleştirme hatası değildir. Bu
uyarıda belge yeniden oluşturulup ardından sac değerleri okunur. Yeniden
oluşturma başarısızsa veya gerçek etkinleştirme hatası gelirse K/R yazılmaz.
Aynı kontrol işlem sonunda ana montaja dönülürken de kullanılır.

Montajdan gelen eski nesnede gövde okuması başarısız olduğunda ve
etkinleştirme uyarısı 2 döndüğünde, eski kodun hatası iki regresyonla yeniden
üretildi. Düzeltmeden sonra **9 hedefli kontrol geçti**; bunlar parça
sahipliği, mevcut düzenlemeleri koruma, ana montaja dönüş ve gerçek Tk
tarama–uygulama akışını da içerir. SolidWorks COM davranışı test nesneleriyle
temsil edildi; kullanıcının montajı bu bulutta çalıştırılmadı.

## Ana sac ve gövde sac unsurunu bulma

Ana parametre hedefi `TemplateSheetMetal`, gövdenin kalınlık kaynağı ise
`SheetMetal` unsurudur. Bunlar ağaçta aynı adla görünmek zorunda değildir.
Keşif API'si boş veya eksikse klasör API'si, ardından ağaçtaki tek ana sac
unsuru kontrol edilir. Gövde unsuru klasörün `GetSheetMetals()` listesinden
de alınır; listede ve ağaçta görünen aynı unsur bir kez işlenir.

Günlük artık seçilen ana/gövde unsurunu ve keşif yolunu gösterir. PowerSM
ve CodeStack karşılaştırması, desteklenen koşullar ve kontrol sonuçları
[araştırma kaydında](reports/sheetmetal-discovery/README.md) bulunur.
