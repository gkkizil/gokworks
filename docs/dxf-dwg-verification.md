# DXF/DWG aktarımı: GitHub kaynaklarıyla doğrulama

Bu rapor DXF/DWG geliştirmesindeki geçmiş 55 testlik doğrulamayı kaydeder. Daha sonra PDF ve diğer modüller de sınandı: **140 testlik güncel sonuç ve son DXF/GUI incelemesi [tüm programın doğrulama raporundadır](program-verification.md).**

Kıyaslama, aktarım çağrısının referanslarla uyumlu olduğunu gösterdi ve önceki kodda bir COM hatası ortaya çıkardı. Hata yeniden üretilip düzeltildi. **55 yerel test geçti; gerçek SolidWorks çıktısının geometrik doğruluğu henüz doğrulanmadı.**

## Referanslar ve çalışma kanıtı

Kaynaklar belirli Git commitlerine sabitlendi; dış projeler çalıştırılmadı. Yıldız sayısı ve bir README'deki özellik listesi, tek başına çalıştırma kanıtı sayılmadı.

| GitHub kaynağı | İncelenen kanıt | Kıyaslamadaki rolü ve sınırı |
| --- | --- | --- |
| [CodeStack doğrudan DXF/DWG makrosu](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/document/sheet-metal/export-dxf-dwg/Macro.vba#L1) | Yayımlanmış VBA örneği; seçenek bitleri ve `ExportToDWG2` çağrısı. [Toplu aktarım belgesinde](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/document/sheet-metal/export-all-flat-patterns/index.md) gösterim videosu bağlantısı var. [Issue #122](https://github.com/xarial/codestack/issues/122) içinde kullanıcı “the code works on parts only when opened” diye bildiriyor; montajda ayrıca hata bildirdiği de açıkça görülüyor. | Parça aktarımı için yayımlanmış örnek ve geçmiş kullanıcı çalışma bildirimi. Bu bildirim eski makro sürümüne aittir; güncel commitin veya GOKWORKS'ün çalıştırıldığının kanıtı değildir. Video bağlantısı görüldü, video burada izlenmedi. |
| [Assem2DXF v3](https://github.com/Johanss-on/Assem2DXF/blob/32f32c3622248981fada57778ffbf7ebce9d7c48/Assem%202%20DXF%20v3.txt#L519) | Açık VBA kaynak, `.swp` makro ve kullanım talimatları. Tam yol aktivasyonu, görünürlük, konfigürasyon ve düz açınım seçimi. | Makro akışı CodeStack'e çok benziyor; bağımsız ikinci çalışma kanıtı gibi sayılmadı. Kaynak tutarlılığı için kullanıldı; bu sürümün başarılı test kaydı bulunmadı. |
| [pywin32 b312: CDispatch](https://github.com/mhammond/pywin32/blob/2a277cb5552756c2b4d42b524dc36d25e0bb6354/com/win32com/client/dynamic.py#L200) | Projenin sabitlediği `pywin32==312` sürümünün gerçek kaynak kodunda `CDispatch.__call__` varsayılan COM üyesini çağırıyor. [VARIANT belgeleri](https://github.com/mhammond/pywin32/blob/2a277cb5552756c2b4d42b524dc36d25e0bb6354/com/win32com/HTML/variant.html#L138) ve [TestDynamic](https://github.com/mhammond/pywin32/blob/2a277cb5552756c2b4d42b524dc36d25e0bb6354/com/win32com/test/testPyComTest.py#L457), `DumbDispatch` ve açık BYREF VARIANT kullanımını gösteriyor. | Python COM davranışının birincil kaynağı. Upstream test kaynağı okundu; Windows gerektiren bu testler burada çalıştırılmadı. |
| [xCAD.NET SwPart](https://github.com/xarial/xcad/blob/f9feb293f74576a6a5dbb3ffcca99502e0a257ed/src/SolidWorks/Documents/SwPart.cs#L34) | `IModelDoc2`/`IPartDoc` ayrımı, `GetBodies2(type, false)`. [Entegrasyon testinde](https://github.com/xarial/xcad/blob/f9feb293f74576a6a5dbb3ffcca99502e0a257ed/tests/integration/SolidWorks.Tests.Integration/DrawingTest.cs#L279) gerçek parça açınım görünümünde 12 kenar bekleniyor. | Parça arayüzü ve gövde erişimini destekleyen kaynak. Bu test bir DXF/DWG dışa aktarma testi değildir; başarılı çalıştırma sonucu burada doğrulanmadı. |

`ajisaacs/ExportDxf` de incelendi. Geçici teknik resimde `CreateFlatPatternViewFromModelView3` ve `SaveAs` kullanıyor; doğrudan parça `ExportToDWG2` akışımızın eşdeğer çalışma kanıtı olarak kullanılmadı. `0ptimusPrim4/export_part_to_dxf` README'si birim ve büküm çizgisi eksikleri bildiriyor; güvenilir ölçü/büküm doğrulaması için referans alınmadı. `sashaskolnik/Solidworks_DXF-Export-Tool` kullanım geçmişini anlatıyor fakat açık kaynak metni yerine ikili `.swp` sunduğundan satır bazında API doğrulamasına dahil edilmedi.

## API kıyaslaması

| Konu | Referans kullanımı | GOKWORKS sonucu |
| --- | --- | --- |
| Aktarım | `IPartDoc.ExportToDWG2(path, modelPath, ExportSheetMetal, True, Empty, False, False, options, Empty)` | Aynı argüman sırası; `VT_EMPTY` ile varsayılan yön ve boş görünüm listesi. |
| Seçenekler | Düz geometri `1`, büküm çizgileri `4` | Geometri daima açık; bükümler kapalıysa `1`, açıksa `1 \| 4 = 5`. |
| Parça arayüzü | `PartDoc`/`IPartDoc` | Gerekirse pywin32 `CastTo` ile parça arayüzüne geçiş. |
| Aktif belge | Toplu makrolarda tam yol ve `swDontRebuildActiveDoc` | Tam yol aktivasyonu; yeniden oluşturma seçeneği `1`. Önceki belge de tam yoluyla geri etkinleştiriliyor; kaydedilmemiş belgede başlığa dönülüyor. |
| Görünürlük | Gizli parça aktarım öncesi görünür yapılıyor | Geçici olarak görünür yapılıyor. Önceden açık parça kapatılmadan eski görünürlüğüne dönüyor. |
| Gövde/açınım seçimi | Çok gövdeli makrolar düz açınım unsurunu seçiyor | GOKWORKS tek katı sac gövdeyle sınırlı. CodeStack'in tek parça örneği gibi özel gövde seçimi yapılmıyor; çok gövdeli parçalar hata döndürüyor. |
| Başarı kararı | `ExportToDWG2` dönüşü `False` ise hata | Dönüş değeri ve temel çıktı kontrolü zorunlu. Bir biçim başarısızsa parça hatalı sayılıyor. |
| Dosya güvenliği | Referanslar çoğunlukla doğrudan hedefe yazıyor | GOKWORKS benzersiz geçici hedefe yazıp kontrol sonrası yayımlıyor; başarısız aktarım eski çıktıyı koruyor. Bu davranış yerel testlerle sınandı. |

## Bulunan hata ve düzeltmeler

**COM nesnesini yanlış çağırma:** Önceki `_value`, `callable(value)` sonucuna bakıp `value()` çağırıyordu. `ActiveDoc` bir `CDispatch` nesnesi olduğunda bu, belgeyi okumak yerine varsayılan COM üyesini çağırıyordu. pywin32 kaynağındaki davranışı temsil eden çağrılabilir test nesnesi eklenince önce iki test başarısız oldu: COM özellik okuma ve iki biçimde aktarım. `_oleobj_` taşıyan COM nesnelerinin çağrılmadan döndürülmesiyle ikisi de geçti. Önceki 32 test bu durumu temsil etmiyordu.

Ayrıca:

- `GetActiveObject` sonucu, açık `VT_BYREF | VT_I4` çıkış parametreleriyle tutarlı çalışmak için `dynamic.DumbDispatch` ile geç bağlamaya alınıyor. pywin32 b312 belgeleri ve testleri bu kullanım ayrımını doğruluyor.
- Aynı isimli farklı dosyaları ayırmak için aktivasyonda başlık yerine tam dosya yolu kullanılıyor.
- Aktivasyon hata bildirse bile önceki belgeye dönme denemesi yapılıyor.
- Gizli mevcut parçalar aktarım sırasında görünür yapılıyor; başarı veya hatadan sonra eski görünürlük geri yükleniyor.

## Dosya adı: kalınlık ve montajdaki adet

[CodeStack adet makrosu](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/document/assembly/components/write-quantities/Macro.vba) `ResolveAllLightWeightComponents(True)`, aktif konfigürasyonun `GetRootComponent3(True)` ağacı ve her örneğin `GetChildren` çağrısıyla alt montajları dolaşıyor. Dosya yolu ve `ReferencedConfiguration` birlikte eşleştiriliyor. GOKWORKS bu ağacı kaynak belgeleri değiştirmeden sayar; tekrar kullanılan alt montajları dosya bazında tekilleştirmez. Referans makronun BOM filtreleri ve özel ölçü/adet özellikleri yerine kullanıcının istediği fiziksel toplam esas alınır: bastırılmış bileşenler hariç, gizli/BOM dışı bileşenler dahil.

Makronun `GetModelDoc2` kontrolü de incelendi. GOKWORKS yüklenmemiş ve SpeedPak alt montajları, ayrıca çözümlenmemiş bileşenleri reddeder; eksik adetle çıktı üretmez. SpeedPak koruması yerel uygulama kararıdır; bu makrodan alınmış bir çalışma kanıtı değildir.

[ExportDxf kalınlık okuyucusu](https://github.com/ajisaacs/ExportDxf/blob/14fa1e69064f743f48edb279edd99681ff0ba783/ExportDXF/Utilities/SolidWorksHelper.cs#L31) `SheetMetal` unsurunun `GetDefinition().Thickness` değerini alıyor; [birim dönüştürücüsü](https://github.com/ajisaacs/ExportDxf/blob/14fa1e69064f743f48edb279edd99681ff0ba783/ExportDXF/Extensions/UnitConversionExtensions.cs#L31) bu değerin metre olduğunu belirtiyor. GOKWORKS milimetre için 1000 ile çarpar, aktif konfigürasyonda bastırılmış sac unsurlarını dışarıda bırakır. Geçersiz, okunamayan veya farklı birden fazla kalınlık hata üretir. Bu kaynaklar API kıyaslaması sağlar; GOKWORKS'ün Windows'ta çalıştırıldığını kanıtlamaz.

Dosya adı örneği: `BRAKET - 1.25 mm - 12 adet.dxf`. Adet yalnızca aktarılan aktif parça konfigürasyonunun montajdaki örneklerinden hesaplanır. Konfigürasyon eşleşmezse yanlış bir adet seçmek yerine hata verilir. Adlandırma, ondalık kalınlık, alt klasörler, tekrarlanan alt montajlar, bastırma, konfigürasyon ayrımı ve CSV raporu yerel testlerle sınandı.

## Yerel test sonucu

```bash
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user .venv/bin/python -m unittest discover -s tests -v
```

**55 test çalıştı: 55 başarılı, 0 başarısız, 0 atlanan.** Bunların 49'u COM davranışını temsil eden nesnelerle aktarım/adet/kalınlık testleri, 6'sı gerçek Tk arayüz testleri. Arayüzden iş parçacığına, adlandırılmış çıktı dosyalarına, sonuç satırına ve CSV raporuna uzanan akış da sınandı. `git diff --check` geçti.

Bu testlerdeki DXF/DWG dosyaları sentetik test çıktılarıdır; SolidWorks üretimi değillerdir. Sonuç, referanslara uygun API kullanımını ve sınanan hata yollarını destekler. Gerçek ölçüler, birimler, açınım yönü, kontur/büküm geometrisi ve SolidWorks sürümüne özgü COM davranışı Windows'ta gerçek bir `.SLDPRT` ile doğrulanmalıdır. [README'deki kontrol listesi](../README.md#akşam-yapılacak-solidworks-kontrolü) bu adımları içerir.
