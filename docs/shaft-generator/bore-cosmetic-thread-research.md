# İç delik ve kozmetik diş: araştırma ve uygulama

27 Ekim 2026. Kullanıcı dişin **kozmetik** olmasını seçti: diş bilgisi/gösterimi
eklenir, helisel katı kesilmez. İç delik gerçek malzeme kaldırır.

## İncelenen GitHub kaynakları

Yalnız README açıklamaları değil aşağıdaki kaynak dosyalar ve testler okundu.
Kaynaklardaki canlı test başarıları proje yazarlarının bildirimidir; bu ortamda
başka projelerin SOLIDWORKS testleri çalıştırılmadı.

| Proje / incelenen sürüm | Somut kod | GOKWORKS'e etkisi |
| --- | --- | --- |
| [soheil-mp/solidworks-mcp](https://github.com/soheil-mp/solidworks-mcp/tree/f450dabcd02a9a7ba705ee9e18a77aaeee9fe802), MIT | [AdvancedFeatureService.cs, CosmeticThreadAsync / ThreadIntent](https://github.com/soheil-mp/solidworks-mcp/blob/f450dabcd02a9a7ba705ee9e18a77aaeee9fe802/src/SolidWorksMcp.Core/Services/AdvancedFeatureService.cs#L916) | C# `InsertCosmeticThread3`, dairesel kenar seçimi, `ICosmeticThreadFeatureData` üzerinden boy/ölçü geri okuma. Aynı dosyada gerçek helis ayrı, kozmetik diş ayrı bir işlemdir. |
| [hjbaard/SolidWorks-MCP](https://github.com/hjbaard/SolidWorks-MCP/tree/95bcd56306e63a8a44e18afa487469dcccc71774), MIT | [session.py, add_hole / add_counterbore_hole](https://github.com/hjbaard/SolidWorks-MCP/blob/95bcd56306e63a8a44e18afa487469dcccc71774/src/solidworks_mcp/session.py#L2021), [gerçek diş ve hata testleri](https://github.com/hjbaard/SolidWorks-MCP/blob/95bcd56306e63a8a44e18afa487469dcccc71774/tests/test_features.py#L356) | Delik için gerçek kesme ve hacim kontrolü; kozmetik ile gerçek dişin farkı. `add_thread` gerçekten helis üretir, ancak kullanıcı tercihi nedeniyle bu yol kullanılmadı. Bilinmeyen profil/ölçüleri sessizce kabul etmenin riski görüldü. |
| [xarial/codestack](https://github.com/xarial/codestack/tree/0cde3849a184cdbbface61238ef431a6ebb9d530), MIT | [determine-hole-boss/Macro.cs](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/geometry/determine-hole-boss/Macro.cs) | İç delik ile dış silindir yüzeyini ayırma örneği. GOKWORKS'ün dış diş seçiminde merkez, eksen ve dış yarıçap birlikte eşleştirilir; iç delik açıldıktan sonra ilk bulunan daireye güvenilmez. |

[qdaia/Auto-SolidWorks](https://github.com/qdaia/Auto-SolidWorks/tree/1bf68f425a1b541f597beaa1842cf2bc1bb9feb8)
deposunun yerel özellik rehberi de incelendi: `Tapped` deliğin kozmetik çağrı
ekleyebildiği, bunun gerçek helis olmadığı belirtilir. Üst düzey lisansı MIT'dir;
depo ayrıca farklı lisanslı üçüncü taraf yüzey araçları taşır. Bunlar alınmadı.

Bu projeler hazır, GOKWORKS'e doğrudan takılan mil modülleri değildir. C#/.NET 10
ve Python COM yapıları mevcut PowerShell/C# 5 köprüsüne kütüphane olarak
eklenmedi. Uygulama resmi API sözleşmeleri ve mevcut GOKWORKS yapı taşlarıyla
yazıldı; üçüncü taraf motor/kaynak klasörü kopyalanmadı.

## Resmi API doğrulaması

- [InsertCosmeticThread3](https://help.solidworks.com/2016/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~InsertCosmeticThread3.html): ISO standardı, tip, ölçü, çap, sonlandırma, boy ve not. 2015'ten itibaren API vardır.
- [Cosmetic Threads PropertyManager](https://help.solidworks.com/2021/english/SolidWorks/sldworks/HIDD_DVE_CTHREAD.htm): dış silindirde gösterim çapı küçük çap, iç delikte büyük çaptır; standart seçiliyse çağrı standarda bağlıdır. Çağrının çizimde görünmesi ayrıca Insert Callout gerektirebilir.
- [ICosmeticThreadFeatureData](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ICosmeticThreadFeatureData~Size.html): boy ve ölçü okuması için native feature data kullanılır.
- [Gerçek Thread özelliği](https://help.solidworks.com/2022/english/api/sldworksapiprogguide/Overview/Thread_Features_and_ThreadFeatureData_Objects.htm): `.sldlfp` profil bağımlılığı olan ayrı bir modelleme yoludur; kozmetik diş yerine kullanılmadı.

`InsertCosmeticThread3`, ilgili veri arayüzü ve enum adları ayrıca SOLIDWORKS
interop 32.1.0 metadatasından okundu. `swStandardType_StandardISO=8`,
`swEndConditionBlind=0`, `swStandardType_StandardNone=-2`; sihirli sayı kopyalamak
yerine üretim C# kodunda enum adları kullanılır.

## Uygulanan özellikler

### İç delik

İç delik sekmesinde etkinleştirme, iç çap, boydan boya/kör ve soldan/sağdan
giriş seçilir. Tek eksenli, sabit çaplı bir delik oluşturulur. Kör taban düzdür;
matkap uç konisi veya kademeli iç çap modellenmez.

İlk dış kademelerden sonra tam tanımlı eksenel profil ve native Cut-Revolve
oluşturulur. Mevcut segman kesmesinin doğrulanmış native kesme yordamı kullanılır.
Çap construction circle `IC_CAP@IC_DELIK_01_ESKIZI` ile sürülür; profil yüksekliği
daireye geometrik bağlıdır. Boydan boya delik boyu dış kademe boylarının toplamına,
kör delik boyu `IC_DELIK_DERINLIK` globaline bağlıdır. Sağ kör deliğin başlangıcı
`toplam boy - derinlik` olarak güncellenir. Kaldırılan gerçek hacim
`π × (iç çap/2)² × delik boyu` ile karşılaştırılır.

Et kalınlığı yalnız deliğin geçtiği kademelerde kontrol edilir. Kör deliğin
tabanı daha küçük bir omuza tam denk gelirse arka tarafta da yeterli malzeme
aranır. Segman/kama tabanı ile iç delik arasındaki et kontrol edilir. İçbükey
omuz pahı/radyüsü malzeme eklediği için dışbükey kenar gibi yanlış düşülmez.

### Kademelerde kozmetik dış diş

Kozmetik diş sekmesinde hedef kademe, sol/sağ başlangıç kenarı, boy ve adım
seçilir. Metrik sağ diş gösterilir. Native ISO `Machine Threads` ölçüsü
`M{kademe çapı}x{adım}` olarak istenir. Kurulumun ISO tablosu bu ölçüyü
sağlamıyorsa işlem hata verir; özel/standartsız dişe sessiz dönüşüm yapılmaz.

Başlangıç, aynı uçtaki pah/radyüs sonrası tam çaplı silindirik yüzeydedir.
Boy bu yüzeyden ölçülür. Eş çaplı, dairesel kenarı olmayan kademe geçişi
reddedilir. Dişin eksenel aralığı diğer operasyonlarla çakışma denetimine girer.
Kozmetik gösterim hacim kaldırmasa da belirtilen nominal diş dip çapının iç
delikle minimum et bırakması aranır; yalnız delikle kesişen diş aralığı etkilenir.
Kozmetik görünüm çapı önizlemede nominal temel küçük çapla gösterilir; katı
geometri kesilmez. Native ölçü/sonlandırma/boy geri okunur, katı hacminin
değişmediği ayrıca doğrulanır. Yeni oluşturulan Part belgesinde kozmetik ve
gölgeli kozmetik gösterim açılır; başka belgelerin/sistemin ayarı değiştirilmez.

Kozmetik özellik silindirin altında alt unsur olabilir; yeniden açmada hem
adla hem gerekirse alt unsur ağacında bulunur. ISO ölçü çağrısı geometrik
delik/helis veya imalat toleransı hesabı yerine geçmez. SOLIDWORKS içinde dış
çap elle değiştirilince ISO ölçü adı otomatik yeniden seçilmez; uygulamada
kademe/diş parametrelerini güncelleyip parçayı yeniden üretmek gerekir.

## JSON ve API sözleşmesi

Eski özellikleri kullanan projeler aynı v1 alanlarıyla kaydedilir. İç delik veya
kozmetik diş varsa v2 kullanılır; taşıma protokolü `shaft_ready protocol:1` ve
`operation:create_shaft` değişmez. İki schema sürümü köprü tarafından doğrulanır.

```json
{
  "schema": "gokworks.shaft",
  "version": 2,
  "units": "mm",
  "name": "BORULU_MIL",
  "minimum_wall": 0.5,
  "stages": [{"id": "s1", "diameter": 30, "length": 80}],
  "bore": {"diameter": 10, "depth": 20, "end_condition": "through_all", "entry": "left"},
  "operations": [{"id": "t1", "kind": "cosmetic_thread", "stage_id": "s1", "edge": "left", "length": 20, "pitch": 1.5}]
}
```

`bore` kapalıysa null olur. `depth` boydan boya modunda saklanır ama kesmeyi
sınırlamaz. `entry`, diş yönü değildir; milin hangi ucundan/kenarından başlandığını
belirtir. Bu sürümde diş sağ helis çağrısıdır. v1 dosyada yeni operasyon
bulunması, bilinmeyen alanlar ve eksik delik alanları açıkça reddedilir.

Plan sırası: dış kademeler → iç delik → pah → radyüs → segman → kama → kozmetik
diş. İç delik yoksa eski sıra aynen kalır. `features/feature_count` içine varsa
`IC_DELIK_01` ve her `KOZMETIK_DIS_nn` dahil edilir. `fully_defined` yalnız native
eskizlerin durumudur; kozmetik diş için helis eskizi üretildiği anlamına gelmez.

## Değişen dosyalar ve doğrulama sınırı

- `modules/shaft_generator/models.py`, `validation.py`, `geometry.py`: v1/v2, eksenel aralık, et ve çakışma denetimi.
- `modules/shaft_generator/ui.py`, `preview.py`: iç delik ve kozmetik diş sekmeleri, kesitte boşluk ve dış görünüşte gizli delik çizgileri, kozmetik çizgiler/çağrı.
- `modules/shaft_generator/interop/ShaftHost.cs`: gerçek delik kesmesi, kozmetik native özellik, ölçü/hacim geri okuma ve kaydet/aç denetimleri.
- `tests/test_axial_features.py`, `tests/test_ui.py`: geometri/JSON/et sınırları ve arayüz akışları.
- `tests/test_axial_transport.py`: Windows'ta gerçek C# host derlemesi ve API argümanları. Proxy geometri üretmez; özellik oluşturma çağrısından null döndürür. Metadata proxy yalnız doğrulayıcının yanlış boy/ölçü/standardı reddini sınar.
- `tests/test_live.py`: sekiz yeni opt-in canlı senaryo: tam/kör delikler, iç delikle kanallar, iki uçtan kozmetik diş, boşluklu mil ve pah sonrası kozmetik diş; edit/rebuild/save/reopen ve bağımsız hacim karşılaştırması.

Bu Linux ortamında gerçek SOLIDWORKS CAD kabulü **çalıştırılmadı**. Kaynak/Qt
testleri, derleme ve Windows API sözleşme testleri bu eksikliği gizlemez. EXE
paketleme isteği veya dağıtım çıktısı bu çalışmaya dahil değildir.
