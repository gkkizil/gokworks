# Power-SM K/R atama yönteminin uyarlanması

Referans: [AmenJlili/power-sm](https://github.com/AmenJlili/power-sm/tree/6c835fb712c18df8969500ec247a0768d3af0d37).
Kaynak C# akışı incelendi; GOKWORKS'ün montaj/konfigürasyon işçisine bağımsız
Python uygulaması eklendi. Power-SM bu ortamda çalıştırılmadı.

## Uygulanan yöntem

- [Ana sacın K faktörü](https://github.com/AmenJlili/power-sm/blob/6c835fb712c18df8969500ec247a0768d3af0d37/PowerSM/PowerSM/PowerGeometry_Form.cs#L1058):
  `GetSheetMetalFolder → GetFeature → GetDefinition → GetCustomBendAllowance`,
  K türü/değeri, `SetCustomBendAllowance`, `ModifyDefinition`.
- [R'yi ölçüden yazma](https://github.com/AmenJlili/power-sm/blob/6c835fb712c18df8969500ec247a0768d3af0d37/PowerSM/PowerSM/SheetMetalFolder2.cs#L70):
  GOKWORKS yalnız ana unsurun sahip olduğu tek radyal ölçüyü seçer. Kaynaktaki
  `SetSystemValue2` yerine hedef konfigürasyona `SetSystemValue3` kullanılır.
  Çap ve alt unsur ölçüleri seçilmez; ölçü yoksa unsur tanımı kullanılır.
- [Bükümleri ana ayarlara bağlama](https://github.com/AmenJlili/power-sm/blob/6c835fb712c18df8969500ec247a0768d3af0d37/PowerSM/PowerSM/PowerGeometry_Form.cs#L460):
  **Tüm bükümlere uygula** ile destekli bükümlerde `UseDefaultBendRadius` /
  `UseDefaultRadius` ve `UseDefaultBendAllowance` etkinleştirilir. Modern
  alt sac için iki K/R override'ı `SetOverrideDefaultParameter2` ile kaldırılır.
  Hem yalnız büküm payı mirasıyla işlenir. Büküm boşaltmaları değiştirilmez.

SolidWorks API belge aynasındaki `IFeature.GetTypeName2`, `IDimension.SetSystemValue3`,
`IDisplayDimension.Type2`, `IDimension.GetFeatureOwner`, ilgili büküm özellikleri ve
`ISheetMetalFeatureData.SetOverrideDefaultParameter2` sözleşmeleri kontrol edildi.
[Belge kaynağı](https://github.com/pedropaulovc/offline-solidworks-api-docs/releases/tag/v3.12.1).
`SketchBend` bir `IOneBendFeatureData`, `SM3dBend` bir `ISketchedBendFeatureData` döndürür.

## Kapsam ve hata yönetimi

Kenar flanşı, çizilmiş/tek büküm, gönye flanşı, jog, process/flatten bends,
süpürme flanşı ve hem desteklenir. Normalleştirme yalnız etkin bükümlere
uygulanır. Sac kalınlığı, malzeme, büküm boşaltma ve ölçülerin diğer
konfigürasyonlardaki değerleri korunur.

İşlem öncesi bütün konfigürasyonlardan sac ve büküm durumları alınır.
Yazma sonrası ana K/R, alt sac/dönüşüm değerleri ve varsayılan büküm ayarları
kontrol edilir. Başka konfigürasyona yayılma veya yazma/yeniden oluşturma/
geri okuma hatası, özel K/R ve override durumları da dahil geri alınır.
Geri alma doğrulanamazsa açık hata gösterilir ve otomatik kayıt yapılmaz.

Kalınlığı farklı ana/alt sac, malzeme/gauge bağı, özel dönüşüm override'ı,
çok gövdeli parça ve tanınmayan özel büküm türleri için işlem durdurulur.
**Tüm bükümlere uygula** kapalıyken önceki özel büküm koruması sürer.

Yeni regresyonlar, unsur tanımının R yazımını yok saymasını, özel büküm
ayarlarını, kısmi hatalarda geri almayı, yanlış ölçü seçimini ve gerçek Tk
tarama–uygulama akışını kapsar. [89 ilgili kontrol geçti](checks.log).
Son arayüz yerleşimi ayrıca 1000×690 ve 1240×860 pencerelerde, açık/koyu
temalarda sınandı. Ek konfigürasyon regresyonunda yalnız büküm bayraklarının
başka konfigürasyona sızması yakalandı ve iki konfigürasyonun eski ayarları
geri yüklenip doğrulandı.

Önceki `0aaabf2` koduyla [iki beklenen regresyon hatası](before.log) yeniden
üretildi: yok sayılan R tanımı ve özel alt sac K/R ayarının atamayı engellemesi.
Kontroller COM test nesneleri kullanır;
gerçek Windows/SolidWorks modeli bu bulutta doğrulanmadı.
[Yerel kontrol adımları](../../local-solidworks-check.md). EXE oluşturulmadı.
