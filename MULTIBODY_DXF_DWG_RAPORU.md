# GOKWORKS — Multi-body DXF/DWG entegrasyon raporu

Tarih: 30 Ekim 2026. Kapsam: mevcut `modules/dxf_dwg` ekranı ve servisleri.
Yeni uygulama modülü, CAD motoru, teknoloji yığını veya ücretli servis eklenmedi.

## Sonuç ve kullanım

DXF/DWG ekranında kaynak bölümündeki **Aktif montajı tara** ya da **Dosya seç…**
ile SLDASM/SLDPRT okunur. **Klasörü tara** da korunur: etkin ana montaj varsa
klasör kapsamındaki gerçek örnekleri, yoksa bağımsız parça dosyalarını kullanır.
Liste üretim sacı bazındadır; normal katı, cıvata, rulman, profil vb. için
ayrı tablo/sekme oluşturulmaz. Sınıflandırılamayan kaynaklar Günlük'te açıklanır.

Kutu, parça/kod, gövde, kalınlık, malzeme, adet ve açınım durumu görünür.
Gövde sütunu tek gövdeli listede gizlenebilir; veri kaybolmaz. Ayrıntılar satır
ipucunda / Enter / rapordadır. **Tümünü seç / Seçimi kaldır** yalnız hazır
sacları etkiler. **Grupla** aynı dosya, referenced configuration ve kalıcı
gövdeye ait fiziksel montaj örneklerini birleştirir. Ayrı görünümde yapılan
kısmi seçim geri gruplanınca korunur; yalnız seçilen örneklerin adedi dışa aktarılır.

**Seçili parçaları dışa aktar** mevcut kaynak/çıktı, biçim, büküm çizgisi,
kalınlık klasörü ve kayıt öncesi görsel kontrol akışını kullanır. İnceleme
kendiliğinden üretim kaydına dönüşmez. Hatalı/işaretsiz bir gövde, hazır seçili
başka gövdenin önizlenmesini engellemez. Kaynak kapsamı değişince eski doğrulanmış
liste temizlenir; eski listeyle yanlış klasör aktarımı başlatılmaz.

## Dosyalar ve sorumluluklar

| Dosya | Görev |
|---|---|
| `modules/dxf_dwg/sheetmetal.py` | Mevcut read-only STA oturumunun uzantısı; montaj örnekleri, gerçek sac sınıflandırması, gövde/Flat-Pattern/Cut List eşleşmesi |
| `modules/dxf_dwg/inventory.py` | COM/Qt içermeyen gruplama, seçim ve çakışmasız hedef planı |
| `modules/dxf_dwg/table.py` | Mevcut ResultsPanel içindeki sanallaştırılmış, kutulu QTableView modeli |
| `modules/dxf_dwg/exporter.py` | Mevcut geçici çıktı, doğrulama ve atomik yayımlama yoluna gövde/konfigürasyon parametreleri; seçili liste aktarımı |
| `modules/dxf_dwg/geometry_check.py` | DXF sonlu/dejenere/mükerrer geometri kontrolü; dosyaya onarım uygulamaz |
| `modules/dxf_dwg/ui.py` | Aynı ekranın tarama düğmeleri, seçim/gruplama, çıktı ve CSV yönlendirmesi |
| `modules/dxf_dwg/preview/{models,solidworks,panel,cancellation}.py` | Mevcut önizlemenin doğru gövde/Flat-Pattern, kalınlık ve başlıkla çalışması; tarama iptali için toplam-süre sınırı olmayan seçenek |
| `gui_qt/services.py` | DXF klasör taramasını gerçek sınıflandırmaya yönlendirir; PDF yolu ayrıdır |
| `gui_qt/export.py` | Varsayılanı eski davranış olan iki küçük extension hook: `export_arguments`, `prepare_export_results` |
| `gui_qt/components.py` | Kaynak listesi varsa gövdeye özgü `source_label` gösterir; diğer ekranların davranışı korunur |
| `modules/dxf_dwg/tests/sheet_fakes.py` | API sözleşmesine uygun yapısal test nesneleri; CAD çekirdeği değildir |
| `modules/dxf_dwg/tests/test_sheet_inventory.py` | Parça/montaj, adet, kimlik, performans ve aktarım hata senaryoları |
| `modules/dxf_dwg/tests/test_sheet_inventory_ui.py` | Gerçek Qt ile seçim, gruplama, iptal, ayrı gövde sonucu, önizleme, CSV ve worker bağlantısı |
| `modules/dxf_dwg/tests/test_multibody_preview.py` | Gerçek mevcut önizleme adapteri + yapısal COM double üzerinden ikinci gövdenin geçici açınımı |
| `modules/dxf_dwg/tests/test_flat_checks.py` | DXF geometri/layer kontrolleri |
| `modules/dxf_dwg/tests/test_multibody_live.py` | Açıkça etkinleştirilen, lisanslı Windows/SolidWorks kabul testi |
| `README.md`, `modules/dxf_dwg/README.md` | Güncel kullanım ve sınırlar |

Önceki UI testlerinin iki tarama sınırı, artık CAD gerektiren klasör keşfini
mock ederek test edecek biçimde güncellendi. Bu mock'lar gerçek SolidWorks
sınıflandırması gibi raporlanmaz. Ortak kaynak-listesi testi yeni sac sayacının
başlığını denetler. Nesting, profil kesim veya mil hesap motorları değiştirilmedi.

## SolidWorks API akışı

| API | Kullanım |
|---|---|
| `IConfiguration.GetRootComponent3(True)` / `IComponent2.GetChildren()` | Aktif montaj ağacı ve örneğe özgü alt dallar |
| `GetSuppression2`, `ReferencedConfiguration`, `GetModelDoc2`, `IsVirtual` | Suppressed dalın dışarıda bırakılması; doğru konfigürasyon ve sanal/lightweight değerlendirmesi |
| `IPartDoc.GetBodies2(swSolidBody, False)` / `IBody2.IsSheetMetal()` | Dosya adından bağımsız gerçek sac tespiti; karışık katılar desteklenir |
| `IFeature.GetTypeName2`, iki feature bağlantısı | Tekrar gösterilen FeatureManager düğümleri ağaç döngüsü sanılmadan taranır |
| `FlatPattern.GetDefinition().FixedFace2.GetBody()` | Yüz/kenar/köşe üzerinden açınımın gerçek gövdesi |
| `CutListFolder.GetSpecificFeature2().GetBodies()` | Yalnız aynı gövdenin Cut List metadata'sı |
| `ICustomPropertyManager.Get6` | Ham, evaluated ve resolved durumu ayrı; çözümlenmeyen ifade üretim ölçüsü sayılmaz |
| `IBody2.GetFeatures()` / SheetMetal `Thickness` | Öncelikli gövdeye özgü kalınlık, metre→mm |
| `IModelDocExtension.GetPersistReference3` | Gövde ve Flat-Pattern kimlikleri; ad eşitliği sahiplik kanıtı sayılmaz |
| `IFeature.Select2(False,-1)` / `ExportToDWG2` | Her biçimde yalnız doğru Flat-Pattern seçilerek mevcut native sheet-metal export |
| `SuspendSelectionList` / `ResumeSelectionList2(False)` | Kullanıcının seçiminin saklanması ve geri alınması |
| `ShowConfiguration2`, `ActivateDoc3`, read-only `OpenDoc6` | Gizli belgede doğrudan konfigürasyon okuma; sadece aktarımda görünür belge aktivasyonu; sonunda önceki durum |

Kalınlık için önce gövdeye bağlı SheetMetal verisi okunur; uygun çözümlenmiş
Cut List kalınlığı ve belge birimi desteklenir. Belge geneli ancak bütün aktif
SheetMetal kalınlıkları aynıysa ortak kaynak olabilir. Farklı kalınlıklar
arasından ilk değer seçilmez. Eksik Cut List tek başına doğru gövdeyi elemez;
doğrudan gövde verisi yeterliyse uyarıyla devam edilir.

Malzeme sırası gövdenin çözümlenmiş Cut List alanı, native gövde ataması,
konfigürasyon/belge alanı, native parça atamasıdır. Tarama ve önizleme aynı
okuyucuyu kullanır; belge geneli malzeme, gövdeye özel kaliteyi gölgelemez.

Native export öncesi eşleşme, güncel kalınlık ve malzeme yeniden doğrulanır. Gövde ve
Flat-Pattern sahipliği her biçimde tekrar kontrol edilir. Geçersiz çıktı,
başarısız biçim ve iptal edilmiş geçici dosya yayımlanmaz. Başarısız bir
parça/biçim diğer doğrulanmış parçaları durdurmaz. Oturum geri alınamıyorsa
kalan işler durur; son satır İşleniyor durumunda bırakılmaz. Oluşmuş çıktı
kısmi sonuç olarak raporlanır; geri alma hatası başarı/iptal diye gizlenmez.

## Adet, önbellek ve performans

Aynı alt montajın her fiziksel örneği ayrı dolaşılır. Belge+konfigürasyon
analizi önbelleğe alınır; aynı parça beş kez yeniden incelenmez. Bütün dosyalar
sadece ad/uzantıya göre sac sayılmaz. Sac olmayan belgeye feature/property,
mesh veya açınım işlemi yapılmaz. Flat-Pattern/Cut List eşleşmeleri kalıcı
kimlik indeksleriyle, Cut List özellikleri klasör bazında yeniden kullanılır.

500 bileşen / 30 sac kullanımının testinde iki benzersiz kaynak
(sac + mekanik parça) iki kez sınıflandırılır; sonuç tek sac grubu ve 30 adettir.
Bu, API çağrı sayısının mock doğrulamasıdır; gerçek 500 bileşenli SolidWorks
montajı için saniye cinsinden performans ölçümü yapılmış değildir.

Klasör modunda sonradan açılan bağımsız belgeler işlendikçe serbest bırakılır.
Tarama ve aktarım ayrı işlerdir. GUI JobManager tek CAD işini STA worker'da
çalıştırır; widget'lara worker'dan dokunulmaz. COM nesnesi UI'ye taşınmaz.
Önizleme mevcut sınırlı mesh önbelleğini kullanır (8 kayıt / 32 MiB).

Gizli parçanın referenced configuration verisi, belge öne getirilmeden doğrudan
`ShowConfiguration2` ile okunur. Önceki konfigürasyon ve seçim listesi korunur.
`IConfiguration.IsSpeedPak` gerçek bir property olarak okunur; eksik SpeedPak
ağacı kabul edilmez. Lightweight bileşen gerektiğinde referenced dosyanın salt okunur modeliyle
incelenir. `SetSuppression2` veya global resolve/suppression ayarı değiştirilmez.
Belirli bir parça okunamıyorsa diğer parçaların doğrulanmış adetleri korunur.
Okunamayan alt montaj daha fazla aynı parçayı saklıyor olabileceğinden, eksik
ağaçtaki miktarlar doğrulanmış sayılmaz; bu durumda yeniden tam tarama istenir.

## Dosya adları ve CSV

Tek gövdede eski ad: `BRAKET - 1.5 mm - 12 adet.dxf`.
Çok gövdede gövde adı + sabit kimlik, farklı kullanılan konfigürasyonlarda
konfigürasyon ayrımı eklenir. Uzun adlar kısalırken zorunlu kimlik eki korunur.
Seçili alt küme değişince bu gövde adı değişmez. Kaynak klasör dışındaki
montaj referansları da çakışmasız ad alır. Kod, gövde, malzeme ve konfigürasyon
adlandırma seçenekleri mevcuttur. Kalınlık/adet Nesting'in mevcut `mm` / `adet`
kurallarıyla okunur. Aynı kaynak olmayan gövdeler isim/kalınlık eşitliğiyle birleşmez.
Özel adlandırma veya uzun ad kısaltması kullanıldığında tek gövdede de sabit
kimlik eki zorunludur; ayrı zamanlarda seçilen iki parça birbirinin üzerine yazmaz.

Kaynak alt klasör ve kalınlık klasörü düzeni korunur. Mevcut dosya varsayılan
atlanır; kullanıcı üzerine yazmayı açarsa geçerli geçici çıktı atomik yayımlanır.
Yeni envanter CSV'si kaynak, konfigürasyon, kod, gövde, kalınlık, malzeme,
montaj adedi, seçili adet, durum, çıktı ve açıklamayı içerir. Bozuk gerçek saclar
ve henüz aktarılmamış satırlar da raporda kaybolmaz.

## Kaynak koruma ve iptal

Yeni Qt envanteri aktarımında kaynak CAD dosyaları otomatik kaydedilmez.
Kullanıcının önceden açtığı belgeler kapatılmaz. Geometri/suppression/Cut List
ayarları, global DXF layer tercihleri ve görüntü kalitesi değiştirilmez.
Rebuild veya `UpdateCutList` zorlanmaz; güncellik doğrulanamıyorsa hata gösterilir.
Geçici aktif konfigürasyon, seçim, görünürlük ve aktif belge geri alınır.

`export_parts(..., items=None)` eski script çağrı biçimi için korunmuştur;
eski klasör yolu tek etkin gövde ve daha önce istenmiş Save All davranışını
korur. Yeni ekran doğrulanmış `items` gönderir, bu eski yola düşmez. Kaynak
kapsamı değişirse eski envanterle aktarım yapılmamasının regresyon testi vardır.

Durdur, native çağrı sınırlarında denetlenir; çıktı doğrulaması/yayımlaması
öncesinde tekrar kontrol edilir. Okunur taramada Windows COM call cancellation
isteği desteklenir; toplam büyük-montaj taramasına sabit süre limiti konmaz.
Önizleme mevcut 60 saniye korumasını korur. Geç sonuç, Stop'tan sonra listeyi
veya başka seçimin önizlemesini boyamaz. SolidWorks sunucusunun iptali reddetmesi
mümkündür; zorla thread/process öldürme yoktur. Native `ExportToDWG2` çalışıyorsa
Durdur onun güvenle dönmesini bekleyebilir. Gerçek server iptal gecikmesi ölçülmedi.

## Doğrulama sınırları

- Sentetik DXF testleri seçilen gövdenin farklı bilinen sınırlarını, bend layer'ını,
  dosya adındaki adedi/kalınlığı, yanlış sahipliğin engellenmesini ve kaynak baytlarının
  değişmemesini denetler. Bu, gerçek CAD geometrisinin kabulü değildir.
- DXF audit, boş/dejenere/nonfinite geometri ve yaygın entity türlerinin aynı
  katmandaki kesin mükerrerleri denetlenir. Bütün farklı entity temsillerindeki
  üst üste binmeler veya bütün kendini kesmeler için CAM sertifikası verilmez.
- DWG'de dosya başlığı denetlenir. Binary DWG geometrisi ayrıştırılmaz. DWG
  önizlemesi, aynı seçili native gövdeden alınmış geçici DXF'tir.
- `ExportToDWG2` native sheet-metal 1:1 yolu kullanılır. Gerçek SolidWorks'te
  kalibre edilmiş parça boyutları, layer mapping ve yalnız seçilen gövdenin
  çıktıya girmesi ayrıca canlı kabul gerektirir.
- SpeedPak tam kaynak yerine kullanılamaz. Okunabilen sanal saclar listelenir;
  dışa aktarım/önizleme için önce harici SLDPRT kaydı gerekir.
- Açınımı olmayan/bozuk Flat-Pattern otomatik düzeltilmez. SheetMetal
  suppression ve flatten/bend-correction operasyonları uygulanmaz.
- Üretim geometrisi kaynak parça dokümanındandır; montaj seviyesinde örneğe özgü
  kesimler/assembly-context geometri değişiklikleri bağımsız biçimde doğrulanmadı.
- Konfigürasyon aktivasyonu/export, SolidWorks'ün oturum içi dirty/update
  işaretlerini etkileyebilir. Bunları zorla temizleyen save/flag işlemi yapılmaz;
  kaynak dosya kaydedilmez. Gerçek sürüm davranışı canlı test gerektirir.

## Gerçek Windows/SolidWorks kabulü

Bu bulut ortamında Windows ve lisanslı SolidWorks bulunmadığından canlı CAD
kabulü çalıştırılamadı. Test hazırlanmıştır; aşağıdaki manifest gerçek test
kopyalarına göre kullanıcı tarafından sağlanır (depo içine üretim CAD'ı eklenmez):

```json
{
  "source": "C:/SW-Test/Main.SLDASM",
  "expected": [
    {
      "source": "C:/SW-Test/Multi.SLDPRT",
      "configuration": "Default",
      "body_name": "Body-1",
      "quantity": 5,
      "thickness_mm": 1.5,
      "bounds_mm": [120.0, 80.0]
    }
  ]
}
```

`expected` tüm beklenen sac gövdelerini kapsamalıdır. Test kopyalarının temiz,
rebuild edilmiş ve gerçek isim/konfigürasyon/ölçülerle hazırlanmış olması gerekir.

```powershell
$env:GOKWORKS_DXF_MULTIBODY_MANIFEST = 'C:/SW-Test/manifest.json'
.venv\Scripts\python.exe -m pytest -q modules/dxf_dwg/tests/test_multibody_live.py -s
```

İki parametreli test DXF ve DWG üretimini, gerçek 3D/açınım önizlemesini, gerçek
montaj adetlerini, DXF'in beklenen mm sınırlarını, kaynak SHA256 değerlerini,
aktif belge/konfigürasyonu ve montaj suppression durumunu denetler. DWG'nin
geometrik eşdeğerliği ayrıca CAD yazılımında kontrol edilmelidir.

## Referanslar ve lisans

- [CodeStack — Export All Flat Patterns](https://www.codestack.net/solidworks-api/document/sheet-metal/export-all-flat-patterns/)
- [CodeStack — Export DXF/DWG](https://www.codestack.net/solidworks-api/document/sheet-metal/export-dxf-dwg/)
- İlgili VBA kaynakları CodeStack'in [GitHub aynasından](https://github.com/xarial/codestack/tree/master/solidworks-api/document/sheet-metal)
  incelendi. `FixedFace2.GetBody`, Cut List body eşleşmesi ve seçili FlatPattern
  ile native export sözleşmesi karşılaştırıldı. Depo MIT lisanslıdır.
- [Solidworks DXF Export Tool](https://github.com/sashaskolnik/Solidworks_DXF-Export-Tool):
  README'deki multi-body/assembly/configuration/instance-count davranışı incelendi.
  Binary SWP makrosu içeri alınmadı; açık lisansı doğrulanamayan kod kopyalanmadı.
- Uygulama GOKWORKS adapter ve dosya güvenliği altyapısıyla özgün olarak yazıldı;
  harici makro veya kaynak paketi dağıtıma eklenmedi.

## Çalıştırılan yerel kontroller

Son geniş regresyon, bounded Qt runner ile 334 ana test topladı. Sonuç:
**326 ana test geçti, 8 test atlandı; ayrıca 63 unittest alt kontrolü geçti.**
Birleştirilmiş JUnit: **397 kayıt, 0 failure, 0 error, 8 skipped**.
Kapsam: bütün DXF/DWG ve PDF testleri; kompakt çalışma alanları; klasör işçisi;
BOM Excel/temizleme; DXF açık/koyu tema; lazy sayfalar ve depo yapısı.

Windows/SolidWorks olmadığı için atlananlar: iki yeni multi-body canlı kabulü,
eski canlı DXF önizleme, gerçek Windows renderer, Windows COM cancellation,
canlı PDF kabulü ve iki Windows VARIANT kontrolü. Bunlar tamamlandı sayılmadı.

Son görsel düzenlemelerden sonra 9 envanter/Qt iş akışı testi ve dar/geniş
çalışma alanı testi ayrıca tekrar geçti (**10/10**). Son API sahiplik/önizleme
kontrolleri ayrıca geçti (**24/24**). `ruff F821/F822/F823` ve `git diff --check`
geçti. Native Qt uygulamasında açık/koyu tema yerleşimi sentetik verilerle
çalıştırılarak gözden geçirildi; bu görüntüler gerçek CAD kabulü değildir ve
depoya eski ekran görüntüsü/artifact eklenmedi. EXE oluşturulmadı.

Son API düzeltmelerinden sonra **79 ilgili test** (envanter, gizli konfigürasyon,
geri alma hatası, gerçek önizleme adapteri ve Qt UI) tekrar geçti. Kayıt öncesi
önizleme akışı ayrıca **14/14** geçti. Bu sonuçlar geniş regresyonun üzerine
yapılan hedefli kontrollerdir; birbirinden bağımsız toplamlar gibi toplanmaz.

## Doğrulanan Windows CI sonuçları

| Kontrol | Test edilen kaynak | Sonuç | Kanıt |
|---|---|---|---|
| DXF/DWG, profil kesim, BOM, mil UI ve domain testleri | `fa7d1f9` | **525 JUnit kaydı; 519 geçti, 6 atlandı, 0 failure/error** | [Windows BOM and shaft UI](https://github.com/gkkizil/gokworks/actions/runs/41041798260) |
| %125 ve %150 native Qt ölçek kontrolü | `fa7d1f9` | İki adım da geçti | Aynı Windows BOM/UI işi |
| PowerShell/C# yükleyici, geçici interop referansları ve IPC | `fa7d1f9` | Geçti; SolidWorks sunucusu kullanılmadı | [Windows shaft bridge](https://github.com/gkkizil/gokworks/actions/runs/41041798284) |
| Ortak çalışma alanları, ayarlar, worker, iptal ve lazy import regresyonu | `3d2934c` | **183/183 geçti**; benchmark ve tam kaynak uygulama self-check geçti | [Windows performance and workbench regression](https://github.com/gkkizil/gokworks/actions/runs/41037260446) |
| Nesting geometri, UI, raporlar ve çalışma alanı entegrasyonu | `3d2934c` | **282/282 geçti**; %125/%150, başlangıç ve native ekran yakalama geçti | [Windows Nesting workspace](https://github.com/gkkizil/gokworks/actions/runs/41037260610) |

Ortak `gui_qt` değişiklikleri `3d2934c` içinde doğrulandı; sonraki kaynak
commit'leri yalnız DXF/DWG modülündeki yönergeleri, SpeedPak property okumasını,
gizli konfigürasyon okumasını ve hata raporlamasını değiştirdi. Son modül
kaynağı `fa7d1f9` yeniden Windows DXF/BOM ve köprü kontrollerinden geçti.
Rapor güncellemesi kaynak algoritmalarını değiştirmez.

Windows benchmark'ta hesap/maliyet ve DXF içe aktarma sonuç imzalarının
referansla aynı kaldığı doğrulandı. Bu ölçüm, SolidWorks montaj tarama hızının
ölçümü değildir. Yukarıdaki Windows CI işlerinde de lisanslı SolidWorks
sunucusu çalıştırılmadı; gerçek CAD kabul testleri tamamlandı sayılmıyor.

## Sonraki ajan için veri sözleşmesi

- `sheet_inventory`: COM nesnesi içermeyen, gövde bazında gruplu liste.
  Kimlik `sheet_id = hash(normalize(source), configuration, body_ref)`;
  `instances` fiziksel montaj örneklerinin kararlı yolları, `quantity` bunların sayısıdır.
- `row_id`, gruplu görünümde `sheet_id`, ayrı görünümde gövde+örnek kimliğidir.
  Aynı kaynak yoluna sahip iki gövdeyi `source` ile upsert etmeyin.
- `body_ref` ve `flat_ref` kalıcı SolidWorks referanslarıdır. `body_name`,
  `code` ve `flat_pattern` görüntü/arama alanıdır; kimlik yerine kullanmayın.
  `FeatureByName` yalnız hızlı bulma içindir; kalıcı kimlik ve sahiplik ayrıca doğrulanır.
- `sheet_current` gövde kimliğini; `sheet_result` kaynak, konfigürasyon, gövde,
  `outputs`, durum ve ayrıntıyı taşır. Her biçimin sonucu ayrı saklanır.
- `export_parts(..., items=..., naming=...)` yeni seçim sınırıdır. `items=None`
  geriye uyumlu script yoludur. Qt ekranı doğrulanmış envanter üzerinden çalışır.
- `Request` eski alan sırasını korur; `flat_ref`, `body_name`, `thickness_mm`
  sondan eklenen isteğe bağlı alanlardır. Mesh/Flat/Payload yalnız düz veri taşır.
- `done.native_restore_failed=True`, kullanıcı kaynağı kontrol etmeden yeni
  aktarımın başlatılmamasını sağlar. Geri alma hatasını iptal olarak göstermeyin.
- PDF worker JSON/IPC, C# mil köprüsü, BOM ve Nesting proje şemaları değişmedi.

## Son kod incelemesinde giderilen regresyonlar

30 Ekim 2026, önceki kaynak `fa7d1f9` / rapor `25b2127` sonrasındaki inceleme:

| Bulgu | Düzeltme ve doğrulama |
|---|---|
| Aynı özel kod veya kısaltılmış uzun ad, ayrı aktarımlarda aynı hedefe düşüyordu | `inventory.py`: adlandırma seçili alt kümeden bağımsız kimlik taşır. Üzerine yazma açıkken iki farklı parçanın çıktıları ayrı kalır. |
| Belge malzemesi gövdenin native malzemesini gölgeleyebiliyordu | `sheetmetal.py`, `preview/solidworks.py`: ortak malzeme önceliği; beş Cut List/gövde/belge/parça/eksik değer senaryosunda tarama ve gerçek önizleme adapterinin sonuçları karşılaştırılır. |
| İlk gövdeden sonra değişen ikinci gövdenin kalınlığı/malzemesi eski önbellekten kabul edilebiliyordu | `exporter.py`: her gövde aktarılmadan hemen önce `describe(..., body_ref=...)` ile yeniden doğrulanır. Geometri damgası sabit veya okunamıyorken yapılan metadata değişiklikleri de engellenir. Seçilmemiş gövdelerin özellikleri bu doğrulamada okunmaz; taramanın dosya/konfigürasyon önbelleği korunur. |
| Doğrulama sırasında durdurulan satır İşleniyor kalabiliyordu | `exporter.py`: aktif satır ve sayaçlar sonlandırılır; tamamlanmış çıktılar korunur. İptal sırasında konfigürasyon geri alınamıyorsa sonuç yine hata olur. |
| Hata/arama filtresi kayıt öncesi kontrolü yanlış satırda bırakabiliyordu | `ui.py`: seçili hazır gövde kaynak modelden bulunup görünür yapılır; doğru önizleme gelmeden kayıt başlamaz. İşaretli montaj örnekleri korunur. |

Regresyonlar önce hatalı davranışla yeniden üretildi. Yeni testler:
`modules/dxf_dwg/tests/test_review_regressions.py`,
`modules/dxf_dwg/tests/test_multibody_preview.py`,
`modules/dxf_dwg/tests/test_sheet_inventory_ui.py`.
`modules/dxf_dwg/tests/sheet_fakes.py` yeni isteğe bağlı `body_ref` sınırını iletir.
Yerel sınırlı-process regresyon koşusu: DXF/DWG, PDF, kompakt çalışma alanları,
lazy sayfalar, depo yapısı ve seçilmiş Qt aktarım/iptal/filtre/temizleme akışları.
**361 test toplandı: 353 geçti, 8 atlandı; ayrıca 63 alt test geçti.**
Birleşik JUnit: 424 kayıt, 0 failure, 0 error, 8 skipped.
Yeni malzeme testinin ilk koşusunda property-get test nesnesi düzeltilip koşu
tam olarak tekrarlandı; yukarıdaki sayılar son başarılı koşuya aittir.
`git diff --check` ve DXF/DWG için Ruff `F821/F822/F823` temizdir.
Gerçek lisanslı SolidWorks kabulü bu incelemede de çalıştırılmış sayılmaz.

Bu düzeltmelerin kaynak commit'i **`a5f12bf`**, GitHub `main` dalına gönderildi.
Bu commit için Windows sonuçları:

- [Windows BOM/UI 41052786136](https://github.com/gkkizil/gokworks/actions/runs/41052786136):
  **543 JUnit kaydı, 537 başarılı, 6 atlanan, 0 failure/error**.
  DXF/DWG, profil, BOM, mil UI paketi ve %125/%150 ölçek kontrolleri başarılı.
- [Windows shaft bridge 41052785758](https://github.com/gkkizil/gokworks/actions/runs/41052785758):
  offline katalog/veri sözleşmesi ve gerçek PowerShell loader/pipe kontrolleri başarılı.
- Bu işlerde de lisanslı SolidWorks sunucusu çalıştırılmadı. EXE üretilmedi.
  Sonraki rapor commit'i yalnız bu doğrulama kaydını günceller.

## İkinci kontrol ve durum geri alma düzeltmesi

Kullanıcının yeniden kontrol isteğiyle `e0b5586` üzerinden DXF/DWG, profil
kesim, BOM, 3D dönüştürücü, PDF, mil UI, kompakt çalışma alanları, lazy sayfalar
ve depo yapısı yeniden test edildi: **713 test toplandı, 702 geçti, 11 atlandı;
ayrıca 74 alt test geçti** (JUnit: 787 kayıt, 0 failure/error).

Ek hata enjeksiyonuyla iki açık bulundu: `export_one_part` görünürlüğü geri
alamadığında veya önceki aktif belgeyi açamadığında yalnız uyarı yazıp sıradaki
parçaya geçebiliyordu. `modules/dxf_dwg/exporter.py` artık bu durumları
`SourceRestoreError` olarak iletir. Görünürlük yeniden okunur; `ActivateDoc3`
dönüş belgesi ve gerçek `ActiveDoc` önceki belgeyle karşılaştırılır.
Başarılı çıktı korunup kısmi sonuç verilir, kalan aktarım durur ve UI'nin mevcut
`native_restore_failed` koruması devreye girer.

`test_review_regressions.py` dört senaryoyu doğrular: görünürlük setter hatası,
sessizce uygulanmayan görünürlük, aktivasyon hatası ve yanlış belge döndüren
aktivasyon. `test_dxf_dwg.py` ilk aktivasyon hatası ile geri alma hatasını
ayrı doğrular; hiç çıktı oluşmasa da geri alma hatası artık sessiz geçmez.
Bu iki dosyanın son doğrudan koşusu **95 test + 44 alt test başarılıdır**.
Gerçek lisanslı SolidWorks kabulü ve EXE derlemesi bu kontrolün parçası değildir.

Son düzeltme sonrası DXF/DWG + PDF + kompakt çalışma alanı ve ilgili Qt
tarama/iptal/temizleme koşusu bütünüyle yeniden çalıştırıldı:
**352 test toplandı, 344 geçti, 8 atlandı; ayrıca 63 alt test geçti**.
JUnit: 415 kayıt, 0 failure/error. Ruff `F821/F822/F823` ve `git diff --check`
temiz. Düzeltmenin kaynak commit'i **`d8bf89b`**.

Bu commit için [Windows BOM/UI 41057041770](https://github.com/gkkizil/gokworks/actions/runs/41057041770)
tamamlandı: **548 JUnit kaydı, 542 başarılı, 6 atlanan, 0 failure/error**;
%125/%150 ölçek kontrolleri de başarılıdır.
[Windows shaft bridge 41057041795](https://github.com/gkkizil/gokworks/actions/runs/41057041795)
katalog, veri sözleşmesi ve PowerShell loader/pipe kontrollerinden geçti.
Bu koşular lisanslı SolidWorks sunucusu kullanmaz. Sonraki rapor commit'i
çalıştırılan kaynak kodu değiştirmez.

## Satır seçimi, önizleme tekrar kullanımı ve Nesting klasör aktarımı

31 Ekim 2026. `4d75da1` sağdaki 3D/açınım önizlemesini satır seçimiyle gösterir;
başarılı tam görüntüyü kaynak, gövde, konfigürasyon, seçenekler ve kaynak/çıktı
dosyası revizyonuyla saklar. Aynı parçaya dönüş yeniden native açınım üretmez.
Yenile canlı okur; kayıt öncesi kontrol saklanmış görüntüyü canlı doğrulama
yerine kullanmaz. Aktarım sonucu güncellemeleri ve aktarım sırasında seçim,
kendiliğinden yeni CAD işi başlatmaz. Durdurulmuş aynı satıra tıklama yeniden
çalışır. Bellek/öğe sayısı sınırlıdır; eksik/başarısız açınımlar saklanmaz.

`modules/dxf_dwg/tests/test_preview_reuse_ui.py` ve
`test_preview_snapshot_cache.py`: 10 yeni test geçti. İlk 5 regresyon önce
eski kodda hata vererek yeniden üretildi. Mevcut DXF/PDF/Qt regresyonu da geçti.
[Windows BOM/UI 41194838324](https://github.com/gkkizil/gokworks/actions/runs/41194838324):
558 JUnit kaydı, **552 başarılı, 6 atlanan, 0 failure/error**; %125/%150 başarılı.
[Windows shaft bridge 41194838391](https://github.com/gkkizil/gokworks/actions/runs/41194838391)
da başarılıdır. Bunlar lisanslı SolidWorks kabulü değildir.

Nesting **DOSYA → Klasör ve alt klasörlerden ekle…** komutu ve DXF ekle
yanındaki klasör düğmesi, arka planda recursive DXF/DWG keşfi yapar.
`modules/nesting/folder_import.py` dosyaları bulur; aynı dizindeki aynı adlı
DXF/DWG çiftinde DXF tercih edilir. Farklı dizinler ayrı kaynaktır. Mevcut
`ImportDialog` adet/kalınlık önizlemesi ve `batch_import` akışı korunur.
Başarılı kaynaklar yeniden yüklenmez, mevcut parçalar silinmez; farklı Unicode
adlar casefold genişletmesi yüzünden birleştirilmez.

`modules/nesting/dwg_import.py`, ayrıca kurulu yerel ODA File Converter'ı
yalnız geçici DWG kopyasında, 120 saniye sınırı ve iptal desteğiyle çalıştırır.
Dönüşen DXF mevcut sıkı kontur/birim okuyucusuna girer. Kaynak yol/SHA256,
orijinal DWG'ye aittir; geçici dosya proje kaynağı olarak saklanmaz.
Araç indirilmez/paketlenmez; yoksa ilgili DWG hata satırıyla raporlanır,
diğer dosyalar işlenir. Hesap/yerleşim motorları değiştirilmedi.
`test_folder_import*.py` yeni testleri klasör/iptal/tekrar yükleme, adet/kalınlık,
geometri ve DWG kaynak korumasını doğrular. Dönüştürücü sınırı mock'tur;
gerçek ODA/DWG kabul testi açık kaynak ortam değişkeniyle hazırlanmıştır ve
kurulu ODA/test kopyası olmadan atlanır. Canlı DWG ve SolidWorks bu ortamda
çalıştırılmadı. Bu görev EXE üretmez.
