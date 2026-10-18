# Kalınlığa göre manuel K / R atama

## Doğrudan Sac-Levha parametreleri — 18 Ekim 2026

Manuel montaj ataması artık `k_factor/sheetmetal_parameters.py` içindeki
bağımsız parametre düzenleyicisini kullanır. `GetUseGaugeTable` sorgusu,
büküm tablosu hesabı, alt büküm eşitleme ve görünür yarıçap ölçüsü taraması
bu akışta bulunmaz. Günlükte işlemi durduran tablo API kodu `2`, bu yolun
önkoşulu değildir.

**Girdiğiniz K ve R aynen kullanılır.** Sac kalınlığı yalnız doğru kullanıcı
satırını seçmek için okunur; kalınlığa yeni bir değer yazılmaz.

| Sac kalınlığı (mm) | K faktörü | İç yarıçap R (mm) |
| ---: | ---: | ---: |
| 1,5 | 0,274 | 1,5 |
| 2 | 0,30 | 2 |
| 3 | 0,32 | 3 |

Bunlar kullanım örneğidir; malzeme veya büküm önerisi değildir. Ondalık virgül
ve nokta kabul edilir. K `0–1` aralığında, kalınlık ve R pozitif ve sonlu
olmalıdır. Kalınlık eşleştirmesi için sabit `0,000001 mm` tolerans kullanılır.

## Kullanım

1. SolidWorks'te ana montajı etkinleştirin.
2. **Manuel K / R** sekmesinde her kalınlığın yanına K ve R girin.
   **Satır ekle** ile diğer kalınlıkları tanımlayın.
3. **Montajı tara** yalnız okur; parçaları veya dosyaları değiştirmez.
4. **Montaja K/R uygula** eşleşen parçanın ana Sac-Levha parametrelerini yazar.
5. Değişiklik varsayılan olarak açık SolidWorks belgesinde kalır.
   **Parça dosyalarını kaydet** ayrıca seçilirse doğrulama sonrası `Save3` kullanılır.

Aktif montaj ve alt montajlar dolaşılır. Aynı dosya/referans konfigürasyonu
bir kez işlenir; adet raporda gösterilir. Sac olmayan ve girilen kalınlıklara
uymayan parçalar atlanır. **Hesap yardımı** bağımsızdır; oradaki tablo veya
BA/BD hesabı manuel atamaya aktarılmaz.

## API algoritması

1. Modern parçada `IModelDocExtension.GetTemplateSheetMetal()` ile ana
   `TemplateSheetMetal` bulunur. Sac klasörü ve unsur ağacı, API türleriyle
   taranır. Eski yapıda tek aktif `SheetMetal` kullanılır. Türkçe/İngilizce
   unsur adları ve kullanıcı tarafından verilen adlar hedef seçimini etkilemez.
2. Gövde `SheetMetal.Thickness` değeri metre olarak okunup mm'ye çevrilir.
   Katıdan dönüştürülen parçada da mevcut SheetMetal unsurları kullanılır;
   dönüşüm bayrakları kaldırılmaz ve şablonun varsayılan kalınlığı eşitlenmez.
3. Eşleşen kullanıcı satırı seçilir. K veya R için malzeme, kalıp, Excel,
   gauge veya büküm tablosuna başvurulmaz.
4. Mevcut parametreler geri alma için saklanır. `GetDefinition()` sonucundaki
   `ISheetMetalFeatureData.AccessSelections(part, null-dispatch)` çağrılır.
5. `GetCustomBendAllowance()` nesnesinde `KFactor` yazılır; ardından **en son**
   `Type=2` (`swBendAllowanceKFactor`) yazılır ve `SetCustomBendAllowance()` çağrılır.
   Bu nesne bir tablo okuyucusu değildir; SolidWorks'ün K-faktörü parametresini
   taşıyan API nesnesidir.
6. `ISheetMetalFeatureData.BendRadius = R_mm / 1000` doğrudan yazılır.
   `Thickness`, malzeme, tablo bağlantısı ve alt büküm override alanları yazılmaz.
7. `IFeature.ModifyDefinition(data, part, null-dispatch)` ve yeniden oluşturma
   sonrası tanım yeniden alınır. İstenen K, R, K-faktörü modu ve korunmuş
   kalınlık geri okumada eşleşmeden başarı raporlanmaz.

Python tarafındaki gerçek COM çağrıları doğrudan `IDispatch.GetIDsOfNames /
Invoke` üzerinden açık metot/özellik bayraklarıyla yapılır. MakePy veya
`GetTypeInfo` üretimi gerektirmez. Boş bileşen argümanı açıkça
`VARIANT(VT_DISPATCH, None)` olarak gönderilir; `VT_NULL` kullanılmaz.

Eski aktif büküm izni bir tablo türündeyse yalnız bağlantı dosyasının adı geri
alma için saklanır. Tablo dosyası açılmaz ve içinden K/R hesaplanmaz.

## Kapsam ve hata davranışı

Hedef **ana Sac-Levha → Büküm yarıçapı / Büküm izni → K-Faktörü** alanlarıdır.
Özel alt büküm veya gövde parametreleri ana değere bağlanmaz. Bu nedenle eski
**Tüm bükümlere uygula** seçeneği manuel arayüzden kaldırılmıştır. Ana alanın
başarıyla değişmesi, özel override kullanan bütün alt bükümlerin değiştiği
anlamına gelmez.

Bir parçanın birden fazla SheetMetal gövdesi varsa tümü bir kullanıcı satırıyla
eşleşmeli ve aynı K/R hedefini istemelidir. Farklı hedefler ortak ana parametreye
zorlanmaz; parça değiştirilmeden neden bildirilir. Normal katı gövdeler işlenmez.

Diğer konfigürasyonlardaki okunabilir sac parametreleri de kontrol edilir.
K/R başka konfigürasyona yayılırsa veya SolidWorks istenen değeri reddeder /
yeniden oluşturma sırasında geri değiştirirse işlem başarısızdır. Eski aktif
büküm izni türü/değeri ve yarıçap geri yüklenip tekrar okunur. Geri alma
başarısızsa **Parçayı kaydetmeyin** uyarısı gösterilir; otomatik kayıt yapılmaz.

## Kaynaklar ve doğrulama sınırı

- [SheetMetal BendRadius](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISheetMetalFeatureData~BendRadius.html)
- [GetCustomBendAllowance](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISheetMetalFeatureData~GetCustomBendAllowance.html)
- [SetCustomBendAllowance](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISheetMetalFeatureData~SetCustomBendAllowance.html)
- [ICustomBendAllowance.Type: türü en son yazma](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ICustomBendAllowance~Type.html)
- [GetTemplateSheetMetal örneği](https://help.solidworks.com/2026/english/api/sldworksapi/Get_Template_Sheet_Metal_Feature_Data_Example_CSharp.htm)
- [Yerel API imza sözleşmesi ve sabitlenmiş referans kaynağı](reports/k-radius/api-contract.json)

Bu değişiklikte daha önce alınmış API açıklamaları ve mevcut interop imzaları
incelendi. Resmi yardım sitesine yeni erişim ağ geçidinden `403` döndürdü.
Hedefli testler COM sözleşmesini, doğru alanları, kalınlık filtresini,
konfigürasyon kontrolünü, geri okumayı ve geri almayı test nesneleriyle sınar.
Gerçek SolidWorks parçasında atama bu Linux ortamında henüz doğrulanmadı.
