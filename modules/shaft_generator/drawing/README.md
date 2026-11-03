# Parametrik mil · Otomatik teknik resim

**Parametrik mil → Teknik resim · Tolerans ve yüzey** bölümü, GOKWORKS ile
oluşturulup kaydedilmiş bir mil parçası için yeni ve düzenlenebilir bir
SOLIDWORKS `.SLDDRW` hazırlar. Mevcut `create_shaft` komutu ve `ShaftHost.cs`
değişmedi. Teknik resim ayrı bir `create_shaft_drawing` komutudur.

> **Doğrulama durumu (3 Kasım 2026):** Planlayıcı, toleranslar, yerleşim ve
> proje uyumluluğu Linux'ta otomatik testlerle doğrulandı. `ShaftDrawingHost.cs`,
> SOLIDWORKS 2024 interop tanımlarına karşı (C# 5, uyarılar hata) derleniyor.
> **Gerçek SOLIDWORKS oturumunda henüz çalıştırılmadı.** Canlı test:
> `GOKWORKS_SHAFT_DRAWING_LIVE=1` ile `test_drawing.py::test_live_part_drawing_pdf_and_reopen`.

## Kullanım

1. Kademeleri ve operasyonları tanımlayın.
2. Bölüm listesinden **Teknik resim · Tolerans ve yüzey** seçin.
3. Ölçü listesinden bir ölçü seçin. Tolerans türünü belirleyin: yok,
   simetrik, çift yönlü, limit veya ISO 286 geçme. Önizleme gerçek sapmaları
   gösterir.
4. Yüzey listesinden bir yüzey seçip **Bu yüzeye gereksinim ata** ile Ra,
   sembol, yöntem ve iz yönünü girin. Toplu değer yalnız **Uygula** ile
   bütün silindirik dış yüzeylere verilir; yüzeye özel değer önceliklidir.
5. Gerekirse datum (A, B, C…) ve geometrik tolerans ekleyin. Salgı, diklik,
   paralellik ve konum, tanımlı bir datum olmadan eklenemez.
6. **Otomatik teknik resim oluştur** açıksa **SLDPRT oluştur ve kaydet…**
   önce parçayı, ardından aynı klasöre `MIL_001.SLDDRW` ve seçilen
   `MIL_001.PDF` / `.DWG` dosyalarını oluşturur. Kayıtlı bir parça için
   **Kayıtlı SLDPRT’den teknik resim…** kullanılır.

Var olan hiçbir çıktı dosyasının üzerine yazılmaz. Parça oluşur ama teknik
resim başarısız olursa model korunur ve durum **kısmi başarı** olarak bildirilir.

## Mimari

| Dosya | Görev |
| --- | --- |
| `drawing/models.py` | `DrawingSettings`: toleranslar, yüzeyler, datum/GD&T, sayfa, antet, çıktılar |
| `drawing/targets.py` | Kimliğe bağlı ölçü/yüzey hedefleri, silinen öğelerin temizlenmesi, doğrulanmış diş adı |
| `drawing/tolerances.py` | ISO 286 sapmaları (`modules/iso_fits/tables.json`), SOLIDWORKS tolerans türü |
| `drawing/planner.py` | Görünüşler, ölçüler, notlar, semboller ve gerçek geometri referansları |
| `drawing/layout.py` | ISO 5455 ölçek, sayfa seçimi, iki geçişli bant/hat yerleşimi, çakışma raporu |
| `drawing/controller.py` | Komut yükü, PowerShell STA köprüsü, sonuç sınıflandırması |
| `drawing/ui.py` | PySide6 paneli |
| `interop/ShaftDrawingHost.cs` | SOLIDWORKS çizim oluşturma ve geri okuma doğrulaması |

Proje dosyası: teknik resim ayarı varsa `.gokshaft.json` **sürüm 3**,
yoksa eskisi gibi sürüm 1/2. Ayarlar `stage_id` / `operation_id` ile bağlıdır;
kademe sırası değişince kaymaz, kademe veya operasyon silinince ilgili
gereksinimler kaldırılıp kullanıcıya bildirilir.

## Ölçülerin geometriye bağlanması

Plan her ölçü için eksenel konum `x` ve yarıçap `r` verir. Köprü parçanın
tek gövdesindeki kenarları sınıflandırır: eksenel daireler, eksene paralel
doğrular ve kama tabanındaki yaylar. Bu kenarları `IView.SelectEntity` ile
görünüşte seçer ve `IModelDoc2.AddDimension2` ile referans ölçü oluşturur.
Ölçü değeri (`IDimension.SystemValue`) plandaki değerle karşılaştırılır;
farklıysa ölçü silinir ve hata raporlanır. Kama boyu iki yayın **max** uç
koşuluyla (`IDimension.SetArcEndCondition`), kama derinliği ise DIN 6885
çizimlerindeki gibi **d − t1** olarak gösterilir: taban kenarından karşı
siluete (`ISilhouetteEdge`).

Ana görünüş yönü profil düzleminin normalinden seçilir. Görünüş
`ModelToViewTransform` ile okunup mil ekseni yatay, kama tarafı yukarı
olacak biçimde döndürülür ve bu durum doğrulanır.

## Kullanılan SOLIDWORKS API'leri

`ISldWorks.NewDocument`, `OpenDoc6` (parça salt okunur), `GetOpenDocumentByName`,
`IDrawingDoc.CreateDrawViewFromModelView3`, `CreateUnfoldedViewAt3`,
`CreateSectionViewAt5`, `CreateDetailViewAt4`, `SetupSheet5`,
`ISheet.SetProperties2`, `IView.SelectEntity`, `GetVisibleEntities2`,
`ModelToViewTransform`, `GetOutline`, `IModelDoc2.AddDimension2`,
`InsertNote`, `InsertDatumTag2`, `InsertGtol`, `IGtol.SetFrameSymbols2`,
`SetFrameValues2`, `IDimensionTolerance.Type`, `SetValues2`, `SetFitValues`,
`GetMinValue`, `GetMaxValue`, `IModelDocExtension.InsertSurfaceFinishSymbol3`,
`IAnnotation.GetAttachedEntities3`, `IDrawingDoc.InsertCenterLine2`,
`ICustomPropertyManager.Add3`, `IModelDocExtension.SaveAs3` (SLDDRW/PDF/DWG).

İmzalar SOLIDWORKS 2024 (interop 32.1.0) üzerinden derlenerek doğrulandı.
`AutoDimension` kullanılmaz: otomatik ölçüler hangi geometriye bağlandığı
doğrulanamadığı için bilerek dışarıda bırakıldı.

## Bilinen sınırlar

- Ölçüler referans ölçüdür; teknik resimden model değiştirilemez. Parçanın
  `CAP_nn` / `BOY_nn` sürücü ölçüleri önce ve sonra okunup karşılaştırılır.
- ISO geçme sapmaları GOKWORKS tablosundan gelir. SOLIDWORKS kendi tablosuyla
  farklı sapma hesaplarsa ölçü "tolerans doğrulanamadı" olarak raporlanır.
- ISO 21920-1 Ra değeri, SOLIDWORKS'ün ISO 1302 tabanlı yüzey işaretine yazılır.
  ISO 21920'nin parametre ve değerlendirme uzunluğu gibi yeni öğeleri bu
  sembolde desteklenmez.
- Geometrik tolerans sembol kodları SOLIDWORKS `gtol.sym` adlarıdır
  (`<IGTOL-SRUN>` vb.); canlı ortamda doğrulanmalıdır.
- Antet alanları çizim özelliği olarak yazılır (`Malzeme`, `ResimNo`,
  `Revizyon`, `GenelTolerans`, `Cizen`, `Aciklama`, `Tarih`). Şablonun bu
  özelliklere bağlı olması gerekir. Malzeme parçadan okunur; tanımsızsa boş kalır.
- Üçüncü açı izdüşümde soldan kör delik için yan görünüş sağa yerleşir;
  delik çapı görünmeyebilir ve raporlanır.
- Yerleşim kontrolü, yaklaşık metin kutularıyla (3,5 mm yazı) yapılır.
