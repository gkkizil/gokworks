# Claude entegrasyonu — motor 1.1.1

Son düzeltmeler [AUDIT_FIXES.md](AUDIT_FIXES.md) içindedir. Form/proje
taşımasında `development_options`, malzemenin yoğunluk/fiyat birimi/para
birimi ve boş/0 değerler korunur. Proje üst code/revision/quantity alanları
ve her yeni öğenin benzersiz request_id'si kaybedilmemelidir. Aynı formun
kesim/pay seçenekleri birim bilgisiyle birlikte saklanır. Yeni kaynak
kimliği otomatik uygulanmış sayılmaz; dispatcher açık kimlik denetimi yapar.

Son kanıtlar: [191 satırlı kapsam](source_coverage.csv),
[doğrulama kaydı](source_validation.json), [teknik rapor](EXPANSION_REPORT.md).
`implementation_status=validated_example_with_restrictions` tam kaynak
eşdeğerliği/imalat onayı değildir. Her modelin `restrictions` ve `stages`
alanları arayüzde başarıyla çelişen eksikleri gizlememek için kullanılabilir.

Ayrıca MIT uyarlaması `core.unfolding.bend_profiles` içinde bağımsız
`develop_profile` ve `calibrate_k` vardır; ölçü türü ve kullanıcı K'sı
açıkça gereklidir. Kaynak fitting'lerin orta yüzey hesabına otomatik telafi
ekleme. Bu yardımcı henüz GUI kontrolüne bağlı değildir; [araştırma notu](research/README.md).

Kaynak `docs/unfolding/unfoldo_inventory.json`, güncel yöntem/sınırlar
`SOURCE_MODELS.md`, kabul örnekleri `examples/source_models.json` dosyasındadır.
191 kaynak kimliği / 51 aile / 11 kategori ayrı izlenir. Önceki yedi API
varyantı eski projeleri açmak için korunur; bunları kaynak sayısına ekleme.
Yeni ekran veya ikinci hesap modülü oluşturma. Mevcut
`modules/sheet_unfolding/` ve `context.jobs` kullanılmaya devam edilir.

```python
from core.unfolding import UnfoldService, UnfoldRequest
engine = UnfoldService()
catalogue = engine.list_source_models()  # 191 immutable records
schema = engine.get_schema('unfoldo/Silindir', 'cylinder-top-angle-side')
r = engine.calculate(UnfoldRequest(shape_id=schema.shape_id,
    variant_id=schema.variant_id,
    parameters={f.id: f.default for f in schema.fields}))
```

## Bağlanan ortak noktalar

- `ShapeSummary.category`, `variant_labels`, `source_ids` ve
  `ShapeSchema.source_id/model_options` servis metadatasıdır. Adaptör
  `service.py` artık bütün kaynak kategorilerini/varyantlarını buradan alır;
  manuel 191 isim/parametre listesi ekleme. Eski PLANNED başlıkları yeni
  çalışan ailelerle birlikte tekrar gösterilmez.
- `FieldSchema.id` büyük/küçük harfe duyarlıdır: W/w, A/a vb. korunur.
  `unit=length` dışında açı/adet/seçenek değerini inch'e dönüştürme.
  `type=integer`, `choices` ve model seçeneklerinin ayrık değerlerini koru.
- `numbers.py` yeni yöntem kodlarını Türkçe gösterir. Kaynak varsayılanları
  her zaman fiziksel olarak geçerli değildir. Geçerli başlangıç örnekleri
  ayrı JSON'dadır; kaynağın varsayılanını sessizce değiştirme.
- `ui.py` yalnız model seçeneklerini proje → form → yeniden hesaplama ve
  birim değişiminde kaybetmemek için küçük bir taşıma düzeltmesi aldı.
  `source_model_options` orijinal giriş birimiyle tutulur; uzunluk anahtarları
  `schema.options.model_options.length_options` üzerinden çevrilir.
- PyInstaller envanter JSON'unu `docs/unfolding` konumunda paketler. Yeni
  bağımlılık, SolidWorks bağlantısı veya menü kaydı eklenmedi.

## Eklenecek görünür kontroller

Ekran düzenini kullanıcı talimatı dışında değiştirme. Mevcut parametre paneli
ve Gelişmiş seçenekler bölümü içinde şu alanlar servis tarafından hazırdır:

| Kontrol | Şema / istek alanı |
|---|---|
| Modele özgü kesim/dikiş seçimi | `schema.options.model_options.cut_options` → `request.model_options.cut_type` |
| Üst/alt/sol/sağ kenar payları | `lap_top/lap_bottom/lap_left/lap_right` |
| Şerit payı | `strip_lap`; yalnız kaynak özelliği varsa |
| Yardımcı örnek/numara seçimi | `helper_divisions` = 12/24/36/48/72/96; `numbering` boolean |
| Köşegen gibi ayrık alan | `FieldSchema.choices` ve `model_options.parameter_options` etiketleriyle ComboBox |
| Geçerli örnek yükleme | `examples/source_models.json` içindeki kendi `source_id` kaydı |

`source_features` yalnız kaynak metadatasıdır. `option_support.heel=False`:
topuk kutusunu çalışan özellik gibi açma; istek açık hatayla reddedilir.
`noNumbers=true` modeller numaralama açılmasını reddeder. `meanOnly` ve
`supported_dimension_references` dışındaki yüzey seçenekleri gizlenmelidir.
`seam_supported=False` ise ortak dikiş açısını açma; kaynak `seam` alanı
varsa zaten parametre formunda gösterilir. Kaynak modellerde `SplitOptions`
ile keyfî bölme yerine `cut_type`, `parts`, `levels`, `segments`, `n` kullanılır.

Kanallarda `lap_top` iki uzun duvar kenarındaki flanştır; `lap_left` iki
uçtaki bindirmedir. Genel kontur/bounding-box büyütmesi yapma. Kaynak
`lapFields` açıklamasını göster. Parametre adedini gerçek parça veya gerçek
katlama adediyle karıştırma.

## Çizim ve üretim sınırları

- `geometry_2d` mm; Arc2D açıları derece, negatif sweep CW'dir. Gerçek
  kesim eğrilerini çiz. Mesh yalnız önizlemedir. STEP ayrı doğrulanmış
  SurfacePatch tanımlarından üretilir. 1.3.0'da katı uygunluğu
  `step_solid`/`step_solid_reason` ile değerlendirilir; güncel bölüm aşağıdadır.
- `bending_lines` artık gerçek faset/plaka katlama konumlarını içerebilir.
  İşaretli yukarı/aşağı yön henüz değerlendirilmediğinden yeni DXF çizgileri
  nötr `BEND` katmanındadır. Kaynak `bendFace` yön hesabı kanıtı değildir.
- `construction_lines` G numaraları `true_lengths` ile ilişkilidir. Örnekleme
  sayısı eğri doğruluk toleransı değildir. Delikler ana gövde kılavuzlarını
  böler; boşluk üzerinden sahte malzeme boyu verilmez.
- Faset/bombe/helezon uyarılarını görünür tut. Geometrik başarı, düzgün
  yüzeyin gerinimsiz açınımı veya imalat onayı değildir. Katı/CAD düğmesini
  yalnız `result.capabilities` ile aç. STEP başarılı dosya demek değildir;
  exporter geri okuma kanıtından sonra complete döndürür.
- Rapor/çıktı, formdan yeniden hesaplanmaz: gösterilen `engine_result`
  snapshot'ı ve `expected_revision/input_hash` kullanılır. Geç gelen sonuç
  ve iptal davranışını mevcut controller gibi koru.
- JSON proje ve toplu ZIP sözleşmesi devam eder. Adet çarpanlarını UI'de
  tekrar uygulama. Hatalı tek öğeyi manifestten gizleme. Nesting için
  `core.unfolding.nesting.to_nesting_parts` kullan; özgün kesim DXF'i taşınır.

Kaynakla eşdeğerliği doğrulanmamış torus E/Z/X yorumu ve dış ölçülü çift
gönye varsayımı `SOURCE_MODELS.md` içinde açıkça listelenmiştir. Bunları
üretime uygun diye yeniden etiketleme. Windows/EXE/SolidWorks/ODA canlı
kabulü ayrıca yapılmalıdır; Linux/OCP testini bu kabulün yerine yazma.
# Motor 1.3.0 — katı STEP ve katalog kontrolü (7 Kasım 2026)

- STEP düğmesi **katı model** üretir. `result.capabilities.step_solid` ve
  `step_solid_reason` esas alınır; adapter `step_kind='solid'`, `step_reason`
  döndürür. Yüzey seçeneğini kullanıcı akışına ekleme, katı hatasında yüzeye
  dönme. API'nin açık `step_kind='surface'` yolu yalnız eski teşhis içindir.
- Pozitif sac kalınlığı şarttır. Faset normal kalınlık kontrolü girdiye göre
  STEP'i kapatabilir; 2D hesap devam eder. Kullanıcı kalınlığını sessizce
  değiştirme. `rectangle-to-round-angled-top` CAD kabul örneği 0.5 mm'dir;
  2 mm örneği normal sapma sınırı nedeniyle açıkça reddedilir.
- STEP sadece üretildikten ve tekrar okunduktan sonra complete olur: kapalı
  B-Rep, pozitif hacim, fiziksel parça başına tek gövde, yüzey artığı bulunmaması,
  hacim/alan/sınır kutusu kontrolleri korunmalıdır. Fasetli tasarım fasetli
  nominal katı olarak kalır; proses veya dayanım onayı değildir.
- Arama `search_text` ile Türkçe İ/ı ve aksansız girişleri eşler. Varyant DTO'su
  `search_name` taşır; aile kartına tıklamak eşleşen varyantı seçer. 51 aileyi
  191 hesap varyantından ayrı say. Kartlarda varyant sayısı vardır.
- Güncel kaynak/çıktı kanıtı: [COMPLETENESS_RECHECK.md](COMPLETENESS_RECHECK.md),
  [live_source_audit.json](live_source_audit.json), [source_coverage.csv](source_coverage.csv).
  Kaynakla tam özellik eşdeğerliği ve imalat onayı bayraklarını model kaydı veya
  katı dosya oluştu diye true yapma.

# Motor 1.2.0 — şekillendirme entegrasyonu (6 Kasım 2026)

- Opsiyonel `forming_options` istek alanını aç/kaydet, çoğaltma ve servis DTO'larında koru.
- `forming_report` sonuç alanı malzeme/proses kaynağını, BA/BD, yaylanma ve `NOT_EVALUATED` durumlarını taşır.
- `nominal_part`/`nominal_geometry_2d` telafiden önceki geometriyi korur; nominal görünümü telafili diye etiketleme.
- Çıktı `development`: `current`, `nominal`, `compensated`, `comparison`. Desteklenmeyen telafi dışa aktarımı reddedilir.
- Yeni yerel `bent_profile` ailesi (tek/iki büküm) kaynak Unfoldo'nun 191 envanterine eklenmez.
- GUI'deki `FormingPanel`, çıktı seçimi ve sonuç sekmesi gerçek çekirdek fonksiyonlarına bağlıdır.
- Kıvırma ile segment birleştirme farklı proseslerdir; kaynak katalog ifadesi kaynaklı birleştirme hesabı değildir.
- 1.2.0'da STEP nominal hedef orta yüzeydi; 1.3.0 katı değişikliği yukarıdadır.
  STEP telafili 2D açınım veya SW feature tree diye sunulmaz.
- DWG düğmesi yalnız ODA bulunduğunda etkin; canlı ODA testi ayrıca gerekir.
- Ayrıntılı sözleşme, fiziksel varsayımlar ve kaynaklar: [FORMING.md](FORMING.md).
