# Claude entegrasyonu — motor 1.1.0

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
  SurfacePatch tanımlarından üretilir; `step_solid=False`.
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
