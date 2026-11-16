# Teknik resim otomasyonu — Kaynak araştırması

15 Kasım 2026. Aşağıdaki değerlendirme yalnız README’lere değil, gerçek
kaynak dosyaları ve lisanslara dayanır. Üçüncü taraf kaynak kodu alınmadı.

## 1. SolidworksMCP-python

İncelenen ağaç: 0403bdb60a0743739ae1fe9ab88653fb65e05a6a.

- [PyWin32Adapter](https://github.com/andrewbartels1/SolidworksMCP-python/blob/0403bdb60a0743739ae1fe9ab88653fb65e05a6a/src/solidworks_mcp/adapters/pywin32_adapter.py)
- [COM executor](https://github.com/andrewbartels1/SolidworksMCP-python/blob/0403bdb60a0743739ae1fe9ab88653fb65e05a6a/src/solidworks_mcp/adapters/com_executor.py)
- [Drawing package / BOM](https://github.com/andrewbartels1/SolidworksMCP-python/blob/0403bdb60a0743739ae1fe9ab88653fb65e05a6a/src/solidworks_mcp/adapters/solidworks/drawing_standard.py)
- [Ölçü / anotasyon işlemleri](https://github.com/andrewbartels1/SolidworksMCP-python/blob/0403bdb60a0743739ae1fe9ab88653fb65e05a6a/src/solidworks_mcp/adapters/solidworks/documentation.py)
- [Ölçü yerleşimi](https://github.com/andrewbartels1/SolidworksMCP-python/blob/0403bdb60a0743739ae1fe9ab88653fb65e05a6a/src/solidworks_mcp/adapters/solidworks/dimension_layout.py)

Tek COM thread’i, açık arayüz sözleşmeleri, gerçek outline ve display-data
okuma, model ölçüsü kimliğiyle tekrar denetimi ve kayıt sonrası inceleme
yararlı yaklaşımlardır. GOKWORKS’te mevcut JobManager ve raw bağlantı
kullanıldı; sunucu / async adapter bağımlılığı eklenmedi. Kaynakta yeni
SolidWorks başlatabilen fallback davranışı bu modüle aktarılmadı.

Lisans: MIT, ESPO Corporation. Pinned drawing_standard ve dimension_layout
dosyalarının incelenen branch içerikleriyle aynı olduğu ayrıca karşılaştırıldı.

## 2. solidworks-automate-drawing

İncelenen ağaç: 4b7444f06ce5ab47da4a7332f05667e2ef4c2fc0.

[Gerçek VBA kodu: src/AutoDrawing.bas](https://github.com/kilwizac/solidworks-automate-drawing/blob/4b7444f06ce5ab47da4a7332f05667e2ef4c2fc0/src/AutoDrawing.bas).

ResolveOrientation, SpaceOutViews, FitAfterDimensions ve ArrangeDims;
başlangıçta kutudan yön / ölçek tahmini, daha sonra gerçek görünüşlerden
yeniden sığdırma yapar. Şablon / format ayrımı ve ölçülerden sonra tekrar
yerleşim yapılması araştırıldı.

FilterDims → DeleteCrossViewDupes / ValueExistsOnEarlierView sayısal değere
göre farklı görünüşlerden ölçü silebiliyor. Bu davranış alınmadı: iki ayrı
Ø10 deliğin ölçüsü aynı tasarım ölçüsü değildir. Ayrıca kaynak makronun
inç / ANSI tercihleri ISO / mm varsayılanına taşınmadı.

İncelenen ağaçta lisans dosyası yok; kod kopyalanmadı.

## 3. sw-drawings

İncelenen ağaç: 87ba029d499d3cda74bf6d31f6336f6f175c46ef.

İstenen dosyaların tamamı gerçekten mevcut:

- [src/view_manager.py](https://github.com/BLAZE-TAN/sw-drawings/blob/87ba029d499d3cda74bf6d31f6336f6f175c46ef/src/view_manager.py)
- [src/dimension_manager.py](https://github.com/BLAZE-TAN/sw-drawings/blob/87ba029d499d3cda74bf6d31f6336f6f175c46ef/src/dimension_manager.py)
- [src/smart_dimension.py](https://github.com/BLAZE-TAN/sw-drawings/blob/87ba029d499d3cda74bf6d31f6336f6f175c46ef/src/smart_dimension.py)
- [src/drawing_exporter.py](https://github.com/BLAZE-TAN/sw-drawings/blob/87ba029d499d3cda74bf6d31f6336f6f175c46ef/src/drawing_exporter.py)
- [src/core/sw_connection.py](https://github.com/BLAZE-TAN/sw-drawings/blob/87ba029d499d3cda74bf6d31f6336f6f175c46ef/src/core/sw_connection.py)
- [src/batch_drawing.py](https://github.com/BLAZE-TAN/sw-drawings/blob/87ba029d499d3cda74bf6d31f6336f6f175c46ef/src/batch_drawing.py)

set_projection_type boş bırakılmış; center-mark yardımcısı yüzey işleme
sembolü annotation türünü kullanıyor. BOM örneğinde InsertBomTable4
DrawingDoc üzerinden çağrılmış; resmi sözleşmede bu metot IView üzerindedir.
Exporter örneklerinde dönüş / out hata kodu denetimi eksiktir.
Dolayısıyla özellik isimleri çalışabilirlik kanıtı kabul edilmedi.
Lisans MIT; kaynak kodu aktarılmadı.

## 4. CodeStack

İncelenen ağaç: 0cde3849a184cdbbface61238ef431a6ebb9d530.

- [Montajı hiyerarşik dolaşma](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/document/assembly/components/traversing-tree/Macro.vba)
- [FlatPattern / CutList / gövde eşleştirme](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/document/sheet-metal/export-all-flat-patterns/Macro.vba)
- [Balon örneği](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/document/drawing/insert-bom-balloons/Macro.vba)

GetChildren ile örnek ağacı ve dosya / konfigürasyon kimliğini ayırma;
FlatPattern’in FixedFace2 gövdesiyle CutList’i eşleştirme mekanizması
incelendi. 16 Kasım geliştirmesinde bu ilişki kalıcı native kimliklerle
uygulandı; geçici tanım erişiminden sonra gövde pointer’ları yeniden
alınır. Mevcut konfigürasyon / feature durumu ve kayıt sonrası IView.Bodies
geri okuması ayrıca denetlenir. Mevcut GOKWORKS servisleri yeniden kullanıldı.
MIT bildirimi mevcut proje bildirimleriyle birlikte korunur.

## 5. SolidWorks-Automation-Tool

İncelenen ağaç: e80590ff6d09308666a819bc7e34519d850ef62d.

- [drawings.py](https://github.com/RylanLN/SolidWorks-Automation-Tool/blob/e80590ff6d09308666a819bc7e34519d850ef62d/drawings.py)
- [GUI_main.py](https://github.com/RylanLN/SolidWorks-Automation-Tool/blob/e80590ff6d09308666a819bc7e34519d850ef62d/GUI_main.py)
- [basic_functions.py](https://github.com/RylanLN/SolidWorks-Automation-Tool/blob/e80590ff6d09308666a819bc7e34519d850ef62d/basic_functions.py)

İşlem sonuçlarını dosya bazında ayırma ve çıktı klasörü yaklaşımı
incelendi. Sabit makine şablon yolu, model özelliklerini otomatik değiştirme
ve dosyanın varlığını başarı kabul etme davranışları alınmadı.
İncelenen ağaçta lisans dosyası bulunmadı; kod kopyalanmadı.

## 6. xCAD

İncelenen ağaç: f9feb293f74576a6a5dbb3ffcca99502e0a257ed.

[SwDrawingView.cs](https://github.com/xarial/xcad/blob/f9feb293f74576a6a5dbb3ffcca99502e0a257ed/src/SolidWorks/Documents/SwDrawingView.cs).

GetOutline ile gerçek görünüş boyutları ve CreateUnfoldedViewAt3 ile
ana görünüşe bağlı projeksiyonlar araştırıldı. .NET altyapısı eklenmedi;
GOKWORKS’ün mevcut raw Python COM yaklaşımı korundu. Lisans MIT.

## 7. FreeCAD TechDraw — yalnız algoritma

İncelenen dosya:
[DrawProjGroup.cpp](https://github.com/FreeCAD/FreeCAD/blob/d956ec561639cfa83f755504b1b3358ea799428e/src/Mod/TechDraw/App/DrawProjGroup.cpp).

checkFit, autoScale, getRect ve autoPositionChildren; görünüş grubu
sınırlarından yer ayırma ve projeksiyon ilişkilerini koruma açısından
incelendi. Dosya başlığı GNU Library GPL v2 veya sonrası bildiriyor.
Kaynak kodu, C++ kitaplığı veya CAD backend eklenmedi.

## Standartlar ve uygulama sınırı

ISO 128 / 129-1 / 5455 / 5456 / 5457 / 7200 / 1101 / 2768 hedef
referanslardır. Lisanslı tam standart metinleri bu ortamda sağlanmadı.
Bu nedenle otomatik ISO uygunluk sertifikası, tahmini genel tolerans
veya uydurma datum üretilmez. Uygulanan somut kurallar, kapsamlarıyla
birlikte DRAWING_RULES belgesinde tanımlıdır.

## Sonuç

Depolardaki bütün işlevler hazır / doğru kabul edilmedi. Kod geliştirme
öncesinde kaynak ve lisanslar incelendi; uygulama kendi worker, bağlantı,
ayar, tema ve paketleme mimarisi içinde geliştirildi. Gerçek CAD üretimi
için SolidWorks 2026 kabul testi ayrıca gereklidir.
