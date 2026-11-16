# SolidWorks API sözleşmeleri ve doğrulama kaydı

15 Kasım 2026. Uygulama yalnız kurulu SolidWorks COM API’sini kullanır.
Enum değerleri çalışan kurulumun swconst tür kitaplığından okunur.
Drawing ve ModelDoc2 dual arayüzleri açıkça ayrılır; ITableAnnotation
kimliği de çalışan uygulamanın tür kitaplığından çözülür.

## Araştırmanın doğrulama sınırı

2026 web yardımının bazı metot bağlantıları bu ortamda yalnız Web Help
kabuğu döndürdü. Böyle durumlarda aşağıdaki erişilebilen resmi sürüm
sayfasından imza / argüman / owner kontrol edildi. Bu, kurulu 2026
üzerinde gerçek çalışma testi yerine geçmez. Uygulama gerçek revision
bilgisini rapora yazar; bulunmayan enum / metot sessizce tahmin edilmez.

## Oturum, kaynak ve geometri

| İşlem | Sözleşme ve kullanım |
|---|---|
| GetActiveObject | Mevcut oturum; otomatik Dispatch / yeni oturum başlatma yok |
| OpenDoc6 | SLDPRT, SLDASM ve yeniden açılan SLDDRW; silent / read-only, Int32 byref error / warning |
| ActivateDoc3 | Doğru belge kimliği ve aktivasyon hata kodu geri okunur; yalnız rebuild uyarısı hata sayılmaz |
| IModelDoc2.GetUpdateStamp | Bellek / geometri değişim sayacı; konfigürasyon değişiminde de artabilir |
| IConfiguration.GetRootComponent3 / IComponent2.GetChildren | Montaj örnek hiyerarşisi ve referenced configuration korunur |
| IPartDoc.GetPartBox / IAssemblyDoc.GetBox | Başlangıç kutusu; son çizim boyutu olarak kabul edilmez |
| GetBodies2 / GetFaces / GetSurface | Gerçek katı, planar ve silindirik yüzey verisi |
| CustomPropertyManager.Get6 | Parameterized PROPERTYGET ile manager; ham / çözümlenmiş değer ve durum |

[GetUpdateStamp — resmi 2025 açıklaması](https://help.solidworks.com/2025/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDoc2~GetUpdateStamp.html) ·
[GetBodies2 — 2026](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IPartDoc~GetBodies2.html) ·
[Assembly GetBox — 2026](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAssemblyDoc~GetBox.html).

## Drawing / View

| API | Doğrulanan uygulama ayrıntısı |
|---|---|
| NewDocument | DRWDOT; user-defined sayfa boyutu metre cinsinden |
| SetupSheet6 | 17 argüman; son altı zone bilgisi zorunlu; FirstAngle bool; genişlik / yükseklik metre |
| NewSheet4 | 16 argüman; SetupSheet6’daki RemoveModifiedNotes argümanı burada yok |
| GetProperties2 | Pafta genişlik / yükseklik indeksleri 5 / 6; ölçek 2 / 3; izdüşüm 4 |
| SetScale | Sayfa oranı; annotation position ölçeklenebilir, metin yüksekliği küçültülmez |
| CreateDrawViewFromModelView3 | Kaynak dosya, standart model yönü, üç metre koordinatı |
| CreateUnfoldedViewAt3 | Seçili parent görünüş; dört argüman; bağımsız kopya görünüş kullanılmaz |
| IView.GetOutline | Gerçek sheet-space sınırlar; metre → mm dönüşümü |
| IView.Position | İki double içeren SAFEARRAY (X, Y); anotasyonların üç koordinatlı konumuyla karıştırılmaz |
| IView.ReferencedDocument / ReferencedConfiguration | Yalnız kayıtlı dosya adı değil, çözülmüş model belgesi de doğrulanır |
| CreateFlatPatternViewFromModelView3 | Yedi argüman; HideBendLines ters anlamı gözetilir; sonuç View nesnesi |

[SetupSheet6 — resmi 2018 imzası](https://help.solidworks.com/2018/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDrawingDoc~SetupSheet6.html) ·
[NewSheet4 — resmi 2016 imzası](https://help.solidworks.com/2016/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDrawingDoc~NewSheet4.html) ·
[CreateUnfoldedViewAt3 — resmi 2026 örneği](https://help.solidworks.com/2026/english/api/sldworksapi/create_unfolded_view_example_vb.htm) ·
[View Position — resmi iki koordinat sözleşmesi](https://help.solidworks.com/2023/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IView~Position.html) ·
[Flat-pattern view — resmi 2018 imzası](https://help.solidworks.com/2018/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDrawingDoc~CreateFlatPatternViewFromModelView3.html).

## Ölçüler ve anotasyonlar

| API | Kullanım |
|---|---|
| IModelDoc2.SetUnits | Beş argüman; mm / decimal; kaynak yerine yeni çizime uygulanır |
| InsertModelAnnotations3 | Altı argüman; DuplicateDims=True resmi belgede tekrar eleme anlamındadır |
| AutoDimension | Seçili drawing view; beş argüman; swAutodimStatusSuccess karşılaştırılır |
| GetFirstDisplayDimension5 / GetNext5 | Gerçek ölçü zinciri, döngü / sayı kontrolü |
| GetDimension2 / GetSystemValue3 | Model ölçüsü kimliği, doğru konfigürasyon ve SI nominal değer |
| IAnnotation.GetDisplayData | Döndürülmüş ölçü metni geometrisi; tahmin kullanılırsa raporlanır |
| IAnnotation.IsDangling | Geometri bağlantısı kontrolü |
| IModelDocExtension.AlignDimensions | Seçili native ölçüler; AutoArrange türü ve metre aralığı |
| IAnnotation.SetPosition2 | Metin konumu taşınır; model ölçüsü değeri / toleransı yazılmaz |
| IView.AutoInsertCenterMarks2 | On argüman; drawing view etkinleştirilir; DrawingDoc metodu değildir |

[SetUnits — resmi 2022 imzası](https://help.solidworks.com/2022/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~SetUnits.html) ·
[InsertModelAnnotations3 — resmi imza / DuplicateDims açıklaması](https://help.solidworks.com/2016/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDrawingDoc~InsertModelAnnotations3.html) ·
[AutoDimension — 2024](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDrawingDoc~AutoDimension.html) ·
[AlignDimensions](https://help.solidworks.com/2016/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.imodeldocextension~aligndimensions.html) ·
[IsDangling](https://help.solidworks.com/2016/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAnnotation~IsDangling.html) ·
[AutoInsertCenterMarks2 — 2025](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IView~AutoInsertCenterMarks2.html) ·
[Merkez işareti enum’u — 2026](https://help.solidworks.com/2026/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swAutoInsertCenterMarkTypes_e.html).

## BOM, balon ve kayıt

| API | Kullanım / önemli önkoşul |
|---|---|
| IView.InsertBomTable4 | On argüman; IView arayüzünde çağrılır; native tablo oluşturulur |
| IBomFeature.SetConfigurations | Üst seviye BOM’da yalnız istenen konfigürasyon görünür yapılır |
| GetComponentsCount2 / GetComponents2 | Top-level için config adı; parts / indented için boş config |
| ITableAnnotation.GetColumnType3 | Dört argüman; PROPERTY data ve status byref; Qty sütunu metadata ile seçilir |
| ITableAnnotation.DisplayedText2 | Üç indeks argümanlı PROPERTYGET; görünen adet instance sayısıyla karşılaştırılır |
| IView.SetKeepLinkedToBOM | Balonlardan önce native BOM feature adıyla link kurulur |
| CreateAutoBalloonOptions / AutoBalloon5 | Önce görünüş seçilir; sonuç native note dizisidir |
| IModelDocExtension.SaveAs | Altı argüman; native boolean sonuç ve byref hata / uyarı doğrulanır |
| IExportPdfData.SetSheets | Tüm paftalar açıkça seçilir; PDF görüntüleyicisi worker’dan açılmaz |

[InsertBomTable4 — resmi 2023 imzası](https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IView~InsertBomTable4.html) ·
[SetConfigurations](https://help.solidworks.com/2021/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IBomFeature~SetConfigurations.html) ·
[GetComponentsCount2](https://help.solidworks.com/2011/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.ibomtableannotation~getcomponentscount2.html) ·
[GetColumnType3](https://help.solidworks.com/2022/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ITableAnnotation~GetColumnType3.html) ·
[DisplayedText2](https://help.solidworks.com/2023/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ITableAnnotation~DisplayedText2.html) ·
[Sütun durum enum’u — 2026](https://help.solidworks.com/2026/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swColumnTypeStatus_e.html) ·
[SetKeepLinkedToBOM](https://help.solidworks.com/2020/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IView~SetKeepLinkedToBOM.html) ·
[AutoBalloon seçenekleri — 2026](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAutoBalloonOptions.html) ·
[SaveAs — 2026](https://help.solidworks.com/2026/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~SaveAs.html).

IGetBodies / IGetComponents2 gibi in-process unmanaged C++ yöntemleri
kullanılmaz. Aynı isimli eski veya farklı owner’daki overload’lar
çağrılmamıştır. Firma şablonu ve kurulu SolidWorks sürümüyle canlı test
gereksinimi KNOWN_LIMITATIONS belgesinde açıkça belirtilmiştir.

## 16 Kasım — gövde bazlı sac paftaları

| API | Doğrulanan sözleşme |
|---|---|
| GetPersistReference3 | Gövde ve unsur için kalıcı kimlik; görünen ad üretim kimliği değildir |
| IFlatPatternFeatureData.FixedFace2 / AccessSelections / ReleaseSelectionAccess | Sabit yüzün GetBody ilişkisi; tanım erişiminin geçici rollback kapsamı mutlaka kapatılır |
| IFeature.IsSuppressed2 | İki argüman; swSpecifyConfiguration ve BSTR SAFEARRAY; her adayın gerçek durumu okunur |
| IBodyFolder.GetBodies / IBody2.GetBodyBox | Cut List üyeliği ve gövde dış ölçüleri; kalınlık kutudan tahmin edilmez |
| IView.Bodies / GetBodiesCount | IDispatch SAFEARRAY ile tek hedef gövde; kapsam kayıt sonrası tekrar okunur |
| IModelDoc2.InsertNote / INote.GetName / GetText | Gerçek, düzenlenebilir pafta başlığı ve kalınlık / malzeme metni |
| IAnnotation.Select3 / IDrawingDoc.AttachAnnotation | Seçilen başlık swAttachAnnotationOption_Sheet ile paftaya bağlanır |
| ITextFormat.CharHeight / SetTextFormat | Metre cinsinden 3 mm yazı; gerçek display-data sınırları kontrol edilir |
| IView.GetNotes | Kayıtlı paftanın kendi başlıkları gerçek sheet-view üzerinden okunur |

[FixedFace2](https://help.solidworks.com/2016/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFlatPatternFeatureData~FixedFace2.html) ·
[Resmi sabit yüz / AccessSelections örneği](https://help.solidworks.com/2021/English/api/sldworksapi/Get_Fixed_Face_of_Flat-Pattern_Feature_Example_VB.htm) ·
[IsSuppressed2](https://help.solidworks.com/2016/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature~IsSuppressed2.html) ·
[Bodies](https://help.solidworks.com/2023/English/api/sldworksapi/SolidWorks.interop.sldworks~SolidWorks.interop.sldworks.IView~Bodies.html) ·
[Resmi tek gövde gösterme örneği](https://help.solidworks.com/2019/english/api/sldworksapi/Set_Body_for_View_Example_VB.htm) ·
[InsertNote](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~InsertNote.html) ·
[AttachAnnotation](https://help.solidworks.com/2016/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDrawingDoc~AttachAnnotation.html) ·
[CharHeight](https://help.solidworks.com/2015/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ITextFormat~CharHeight.html) ·
[GetNotes](https://help.solidworks.com/2017/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IView~GetNotes.html).

ActivateView bir paftayı etkinleştirmek için kullanılmaz; bu durumda false
döndürebildiği resmi açıklamada belirtilir. Başlık için ActivateSheet ve
açık annotation attachment kullanılmıştır. Bu ek API araştırması canlı
SolidWorks testi değildir.
