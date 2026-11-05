# Claude için entegrasyon notu

Güncel Codex değişikliğini main/PR üzerinden tabanına al; eski sohbetten
veri modeli uydurma. `docs/unfolding/contract_v1.md` sözleşme kaynağıdır.
Çekirdek `core/unfolding/`; UI, controller, menü ve UI testleri senindir.
Depo düzenine göre `modules/sheet_unfolding/ui.py` ve modül README/testlerini
kullan. `gui_qt/app.py` kaydını sen yap; çekirdek bu dosyaya dokunmadı.

```python
from core.unfolding import UnfoldService, UnfoldRequest, ExportOptions
service = UnfoldService()
shapes = service.list_shapes()
schema = service.get_schema('cylinder', 'straight')
request = UnfoldRequest(request_id='tasarim-1', revision=1,
    parameters={'diameter': 300., 'height': 200.})
result = service.calculate(request)
```

- Parametre formunu `schema.fields` üzerinden kur; `dimension_id`, Türkçe
  açıklama, tip, birim ve sınırlar verilir. Birim `length` alanları seçilen
  giriş birimindedir; schema varsayılanları mm referansındadır. Açılar derece.
- İşleri mevcut `context.jobs`/`JobManager` üzerinden çağır. Controller event
  adlarını kendin belirleyebilirsin; engine Qt olayı üretmez. Hesap/dışa aktarma
  çağrılarına worker'ın stop Event'ini `cancel_token=stop` ver.
- Her form değişiminde revision artır; biten işin request_id/revision'ını
  yakalanan ve güncel değerlerle karşılaştır. `status!='success'` ise kontur
  ve export düğmelerini açma; önceki geçerli sonucu ayrı snapshot olarak tut.
- Export çağrısında `expected_revision` ve `expected_input_hash` ver. Motor
  exporter'ı başka form değerinden tekrar hesaplamaz. Uzun STEP işi zaten
  ayrı headless süreçtedir; ek SolidWorks/FreeCAD bağlantısı kurma.
- Gerçek 2D elemanları çiz: derece tabanlı Arc2D negatif süpürmesi CW'dir.
  Mesh3D mm'dir, yalnız önizlemedir. Dünya koordinatları tüm montaj için
  hazırlanmıştır; parçaları tekrar tahmini konuma taşıma.
- `drawing_views` ön/üst tel görünüşleri, `dimension_annotations` açınım
  sınır ölçülerini verir. `developed_width/developed_height` türetilmiş
  ölçülerdir; bunları çap/yükseklik girişinin kendisi gibi değiştirme.
  Giriş ölçüleri `schema.dimension_id` ile etiketlenmelidir.
- `construction_lines` üzerindeki G etiketleri `true_lengths` kayıtlarıyla
  eşleşir; bunlar abkant programı değildir. `bending_lines` v1'de boştur.
- `capabilities` dışında STEP veya solid düğmesi açma. Eğik silindir,
  dirsek ve bindirmede STEP kapalı; solid her durumda kapalıdır.
- `SplitOptions.count` çevresel bölmedir. Dirsekte `parameters.segments`
  farklıdır: iki uç yarım segment DAHİL toplam parça sayısıdır.
- Proje: `UnfoldProject(items=(ProjectItem(code,request,quantity),...),
  quantity=...)`. Dosyadan geometriye güvenme; yeniden hesapla. Eski motor
  sürümü `needs_recalculation` ile görünür. Toplu ZIP için
  `service.export_project(project, ExportOptions(path,'zip'))` kullan.
- Nesting: `core.unfolding.nesting.to_nesting_parts` mevcut Part modelini
  verir; kapalı hesap poligonu ve **yalnız kesim içeren özgün DXF metni**
  birlikte taşınır. Yay/bulge döndürme ve ötelemede korunur. Material.name,
  nesting projesinin malzeme kimliğiyle eşleştirilmelidir; yeni isim üretme.

Önce `docs/unfolding/examples/cylinder.json` ile 942,477796 × 200 mm
örneğini UI'ye bağla; ardından diğer altı örnek/varyantı ekle. Çalışmayan
bombe/helis/branşman varyantlarını hazır listesine koyma. Optional AI/OCR bu
teslimde yoktur; ağdan dosya/ölçü çıkarımı veya API key entegrasyonu eklenmedi.

Ortak değişiklikler yalnız `main.py` içindeki `--unfold-worker` dalı ve
PyInstaller'ın `core.unfolding` toplama satırıdır. Yeni dependency/font/veri
dosyası gerekmedi. Windows EXE ve senin ekranın için canlı kabul testi ayrıca
yapılmalıdır; Linux testlerini Windows/SolidWorks başarısı diye sunma.
