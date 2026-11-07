# Sac Açınımı — çekirdek/UI sözleşmesi v1 (motor 1.1.1)

**Motor 1.3.0 güncellemesi (7 Kasım 2026):** istek/proje şeması v1 korunur.
STEP varsayılanı `ExportOptions.step_kind='solid'` ile kapalı, sac kalınlıklı
katıdır. `result.capabilities.step_solid` ve `step_solid_reason` girdiye ve
ortama göre değerlendirilir; kalınlık sıfır veya CAD uygunsuzsa düğme kapatılır.
Eski açık `step_kind='surface'` yalnız teşhis içindir; otomatik geri dönüş değildir.
Fasetler için nominal normal offset sapması ölçülür ve STEP başlığında belirtilir;
imalat/proses onayı verilmez. [Güncel kabul ve sınırlar](COMPLETENESS_RECHECK.md).
Aşağıdaki tarihsel sahiplik ifadeleri yerine güncel ajan yetkisi ve iş birliği
kuralları depo kökündeki `AGENTS.md` tarafından belirlenir.

1.1.1, JSON şemasını değiştirmeden geometri/proje çevrimi düzeltmeleri
ekler; [AUDIT_FIXES.md](AUDIT_FIXES.md). Şemadaki uzunluk min/max değerleri
mm'dir ve giriş birimi çevrildikten sonra uygulanır. GUI, kayıtlı
DevelopmentOptions ve Material alanlarını varsayılanlarla değiştirmez.

Çekirdek sahibi Codex; UI, controller, menü ve UI testleri Claude'a aittir.
Bu depoda UI modül başına `modules/<modül>/ui.py` içindedir. Yeni ekran için
`modules/sheet_unfolding/ui.py` önerilir; `ui/unfolding/` kopyası açılmamalıdır.
Çekirdek `core/unfolding/`, testler `tests/unfolding/` altındadır.

```python
from core.unfolding import UnfoldService, UnfoldRequest, ExportOptions
service = UnfoldService()
request = UnfoldRequest(shape_id='cylinder', variant_id='straight',
    parameters={'diameter': 300., 'height': 200.}, thickness=0.,
    request_id='cylinder-demo', revision=1)
schema = service.get_schema(request.shape_id, request.variant_id)
validation = service.validate(request)
result = service.calculate(request)
assert result.status == 'success'
assert abs(result.parts[0].metrics.net_area_mm2 - 60000*3.141592653589793) < 1e-6
service.export(result, ExportOptions('cylinder.dxf', expected_revision=1,
    expected_input_hash=result.input_hash))
```

`UnfoldService` adresi `core.unfolding.service.UnfoldService`; tüm değişmez
modeller `core.unfolding.models`; JSON dönüşümü `models.to_data`.
`list_shapes()`, `get_schema(shape_id, variant_id)`, `validate(request)`,
`calculate(request, cancel_token=None)`, `export(result, export_options)`,
`save_project(project,path)`, `load_project(path)` public API'dir.
İptal standardı `threading.Event.is_set()`; `UnfoldCancelled` yükselir.
UI mevcut GOKWORKS JobManager'ında bu çağrıları çalıştırmalıdır. Çekirdekte
widget veya Qt iş parçacığı yoktur. Ağ, SolidWorks ve LLM kullanılmaz.

## Veri ve birimler

İstek `schema_version=1`, `request_id`, artan `revision`, `shape_id`,
`variant_id`, `parameters`, `input_units`, `thickness`, `dimension_reference`,
`material`, `seam_options`, `split_options`, `joint_options`,
`development_options` ve opsiyonel `model_options` taşır. Yeni alanın
varsayılanı boş sözlüktür; eski v1 proje kayıtları açılır. `input_units=mm|inch`; uzunluk/kalınlık/pay aynı
giriş birimindedir. Açılar dış sözleşmede **derece**dir. Geliştirme toleransları
alan adlarında belirtildiği gibi her zaman mm'dir. Sonuç mm/mm²/kg'dır.

`normalized_inputs.parameters` **orta yüzey/mm** ölçüleridir ve
`normalized_inputs.dimension_reference=mid` olur. Ölçülen kaynak yüzey
`source_dimension_reference`, bu yüzeyin mm girişleri `reference_parameters_mm`
ile korunur. Bunları tekrar inner/outer diye normalize etmeyin. Formu
geri yüklerken projedeki orijinal UnfoldRequest'i kullanın.

Parametreler ve iç içe nesneler kopyalanıp değişmez yapılır. Sonuç bir
anlık görüntüdür; exporter formdan veya başka bir istekten tekrar hesaplamaz.
UI eski bir işi göstermek/kaydetmek istemiyorsa hem `request_id/revision`
hem `input_hash` değerlerini kontrol etmeli; exporter'a `expected_revision`
ve `expected_input_hash` göndermelidir. Hash engine sürümüyle beraber cache
anahtarıdır. Cache yalnız tamamlanmış başarılı hesapları saklar.

`ShapeSchema.fields` Türkçe etiket, açıklama, varsayılan, sınırlar, tip,
birim ve görsel `dimension_id` verir. Geçerli şekilleri `list_shapes()` ile
alın; planlanan aileleri çalışan menü öğeleri gibi göstermeyin.

## Sonuç ve çizim

`status=success|error`. Hatalı sonuçta üretim konturu yoktur. Uyarı/hatalar
`code,severity,field_ids,part_id,message` içerir. Yöntem
`analytic_developable|sampled_developable|faceted_developable|faceted_real_length|formed_approximation`.
Son iki yöntem düzgün yüzey/imalat onayı değildir. Güncel kaynak kapsamı,
model seçenekleri ve sınırlar `SOURCE_MODELS.md` ve `CLAUDE_HANDOFF.md` içindedir.

Her parça kimlik/montaj ilişkisi/adet, `geometry_2d.outer/holes`, `mesh_3d`,
`surface_patches`, `drawing_views`, `dimension_annotations`, `bending_lines`,
`construction_lines`, `seams`, `labels`, `true_lengths`, `mappings`, `metrics`
taşır. Kontur elemanları tipli `Line2D/Arc2D/Circle2D/Polyline2D`'dir.
Yaylar merkez/yarıçap/başlangıç/süpürme dereceyle tanımlanır; negatif süpürme
saat yönüdür. UI yayları elips/spline ile değiştirmemelidir. Mesh yalnız
önizlemedir. STEP üreticisi mesh'i kullanmaz; `surface_patches` üzerinden
analitik yüzeyler ve gerçek düz faset B-Rep yüzleri kurar.

Ölçü çizgileri ve yardımcı çizgiler kesim konturundan ayrıdır. V1, abkant
büküm sırası veya yaylanma çözümü iddia etmez. Gerçek boylar numaralı 3D
kenar uçlarıyla verilir. `mappings` örneklenen 2D/3D eşleşmeleridir.

## Çıktı ve kayıt

`capabilities` çalışma ortamında kullanılabilen çıktıları verir; UI düğmeleri
buna göre açmalıdır. STEP **orta yüzey** B-Rep'tir; kalınlıklı solid veya
SolidWorks özellik ağacı değildir. Kaynak doğruluk, eğri hatası ve mesh
hatası ayrı metriklerdir; imalat toleransı otomatik atanmaz.
Eğik silindir/dirsek ve bindirmede STEP kapalıdır. Bindirme şeridi 2D'de
kesilir; 3D nominal yüzeyi gösterir. Maksimum örnek adedi ve 250000 örnek
bütçesi bellek tahsisi öncesinde denetlenir; gereksiz hassasiyet sessizce
yuvarlanmaz, açık hata döner.

`ExportOptions.format=dxf|pdf|step|zip|json`; DXF tek parça ister, çoklu parça
için ZIP kullanın. ZIP ayrı DXF'ler, isteğe bağlı PDF/STEP ve manifest taşır.
`part_ids` boşsa tüm parçalar seçilir. Overwrite varsayılan kapalıdır.
`ExportResult.status=complete|partial|error`; istenen bir çıktı başarısızsa
`complete` dönmez. PDF ölçeği sayfaya sığdırılır ve açıkça yazılır.
`service.export(...,cancel_token=stop)` iptal destekler. STEP ayrı süreçte
120 s varsayılan sınırla, headless `main.py --unfold-worker` üzerinden çalışır;
readback kanıtı dosya imzasıyla eşleştirilmeden yayınlanmaz.

Projeler `gokworks.unfolding.project`, version 1, `UnfoldProject` içerir;
`items=(ProjectItem(code,request,quantity),...)`. Proje ve öğe adetleri ayrı
saklanır. Üretim hesabı/adet çarpımı yalnız bir kere yapılmalıdır.
`needs_recalculation` eski motor sürümünü bildirir; dosyadan saklanmış
geometriye güvenilmez, tekrar hesaplanır.
`service.export_project(project, ExportOptions(path,'zip'),cancel_token=stop)`
her öğeyi hesaplar, ayrı dosyalar ve proje manifesti üretir. Burada ek
`quantity_multiplier` kullanmayın; proje/öğe adetleri zaten uygulanır.

Nesting adaptörü `core.unfolding.nesting.to_nesting_parts` gerçek kapalı
kontur/delik, tolerans, kalınlık, malzeme ve sabit kimlikleri taşır. Eğriler
nesting'in polygon sözleşmesine belirtilen kord hata sınırıyla çevrilir;
orijinal DXF yayları `Part.original_dxf` metninde ayrıca korunur. Nesting
algoritması değiştirilmez. Bu adaptör CUT konturları dışındaki çizgileri
nesting'e taşımaz; saat yönlü bulge'ları native ARC/LINE'a kayıpsız çevirir.

## 1.1.0 kaynak kataloğu eklentisi

`list_source_models()` 191 kaydı ayrı kaynak kimlikleriyle döndürür.
`ShapeSummary.category/variant_labels/source_ids` ve
`ShapeSchema.source_id/model_options` UI metadatasıdır. Eski beş aile/yedi
varyant korunur; kaynak sayımına eklenmez. `model_options` kesim seçimi,
kenar/şerit payı, yardımcı örnekleme ve numaralama ayarlarını taşır.
Yalnız `length_options` içindeki seçenekler mm/inch çevrilir.
Kaynağın `source_features` alanı hesap desteği kanıtı değildir.

`bending_lines` artık boş olmak zorunda değildir; gerçek faset/plaka
katlama konumlarını içerir. Yön henüz değerlendirilmediği için yeni DXF
çizgileri BEND katmanındadır. Yardımcı G çizgileri ayrı tutulur.
STEP yüzey dosyaları analitik veya açıkça fasetli gerçek B-Rep içerir;
NOT A SOLID / manufacturing NOT VALIDATED açıklamaları dosyaya yazılır.
