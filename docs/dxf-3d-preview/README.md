# DXF/DWG · SolidWorks 3D önizleme — 26 Ekim 2026

Yeni özellik mevcut `DxfDwgPage` içine entegredir. Ortak `ExportPage`,
`JobManager`, bağlantı fonksiyonu ve paketleme betiği değiştirilmedi.
Kaynak geliştirmesi `main` üzerindedir. Uygulama sırasında uzak `main`'in
ilerlediği görüldü; mevcut ana dal `8fbd864` sürümüne fast-forward edildi.
Mil branch'i ayrıca birleştirilmedi, mil kaynakları düzenlenmedi. Önceki
tabanla başlatılan tam test durduruldu; sonuçları güncel tam doğrulama sayılmaz.

[Arşiv: Üçlü önizleme](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/dxf-3d-preview/dark-wide.png)

[Arşiv: Açık tema](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/dxf-3d-preview/light-wide.png) · [Arşiv: küçük pencere](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/dxf-3d-preview/light-small.png).
Görseller sentetik, delikli/bükülmüş bir mesh ve etiketlenmiş örnek açınımla
gerçek Qt ekranından alındı. **Gerçek SolidWorks kabul testi değildir.**
Normal uygulama başlangıcında örnek parça gösterilmez; gerçek kaynak gerekir.

## Veri akışı ve güvenlik

1. Kaynak veya sonuç listesi seçimi dosya/konfigürasyon/gövde/çıktı kimliği
   taşıyan değişmez bir `Request` oluşturur. Önceki üç görünüm hemen temizlenir.
2. Kısa geciktirme hızlı seçimleri birleştirir. Çalışan CAD aktarımı varsa
   önizleme bekler; ikinci COM işi veya SolidWorks sunucusu başlatılmaz.
   Kullanıcı aktarım başlatırsa kendi önizlemesi iptal edilir; canlı COM
   çağrısı tamamlanıp kaynak durumu geri alındıktan sonra aktarım başlar.
   Geri yükleme hatasında sıradaki aktarım da engellenir. Durdur ve pencere
   kapanışı, bekleyen aktarımı kendiliğinden başlatmaz.
3. Mevcut bağlantı ve read-only session yeniden kullanılır. Belge tam yolu
   doğrulanır. Gerekli konfigürasyon açılır; sadece gerçek türetilmiş parent
   ilişkisi izlenerek bükülmüş konfigürasyon bulunur. Ad benzerliği kullanılmaz.
4. `IBody2.IsSheetMetal`, gövde sayısı ve varsa kalıcı gövde kimliği kontrol
   edilir. Mevcut exporter tek gövdelidir; belirsiz çok gövdeli eşleştirme
   otomatik seçilmez. Native aktarımın kapsamı genişletilmedi.
5. Her yüzün `GetTessTriangles(True)` verisi alınır. Ekran tessellation'ı yoksa
   özel `GetTessellation(None)` / `Tessellate` / facet-fin-vertex yolu kullanılır.
   Böylece gizli belge için görüntü yakalama veya modelden STL kaydı gerekmez.
   Kullanıcının model/görüntü kalitesi tercihleri değiştirilmez.
6. Üçgen sayısı, koordinatlar ve revizyon doğrulanır. Float32 hassasiyeti
   için gösterim koordinatları merkezlenir; kaynak orijini ayrıca tutulur.
7. Önceki konfigürasyon ve aktif belge geri yüklendikten sonra yalnız düz
   veri GUI'ye iletilir. Nesiller uyuşmazsa eski sonuç atılır. Kaynak dosya
   değişirse watcher yenileme ister. Yenileme canlı update stamp'i tekrar okur.

`_PageEvents` modüle ait ayrı, GUI-affine bir QObject alıcısıdır. İlk testte
kalıtılan dekorasyonlu slotun yeni override'ı GUI dışında çalışıp Qt timer
uyarısı verdi; kompozisyonla giderildi. Bunun için paylaşılan worker protokolü
değiştirilmedi. Yeni test callback thread'ini açıkça kontrol eder.

DXF/DWG çıktı kayıtlarına geriye uyumlu `source_stamp`, `update_stamp`,
`body_ref` ve `bend_lines` bilgileri eklenir. Bu metadata okunamazsa mevcut
aktarım başarısız yapılmaz. Geometri kaydı, adlandırma, adet ve dosya yayımlama
kuralları korunur. Mevcut çıktı hiçbir önizleme işlemi tarafından değiştirilmez.

## Açınım ve bilgiler

Üretilmiş DXF modelspace'i mevcut `flatten_entity` yordamıyla okunur;
çember/arc/spline/polyline ve dönüştürülmüş BLOCK'lar desteklenir. Delikler
ve kesimler kontur olarak, büküm katmanları kesikli çizgiyle gösterilir.
BYLAYER/true-color renkleri korunur; beyaz çizgi açık kâğıtta okunabilir renge
çevrilir. Gizli/dondurulmuş katmanlar gösterilmez. Desteklenmeyen öğeler
uyarıya dönüşür; eksik geometri sessizce tam kabul edilmez.

DWG için ham DWG çözümleyici eklenmedi. Aynı kaynak ve konfigürasyondan
geçici DXF alınır ve panelde **DWG dosyası okunmadığı** belirtilir. Bu yol
aktarım öncesi veya kaynak revizyonu eski çıktıyla uyuşmadığında da kullanılır.
Geçici klasör işlem sonunda temizlenir. Mevcut dosya atlanmışsa güncelliğinin
doğrulanmadığı açıkça yazılır.

Malzeme/kod/açıklama/büküm bilgisi çözümlenmiş belge ve eşleşen Cut List
property'lerinden okunur. Kalınlık aktif SheetMetal'den, adet mevcut montaj
aktarımı sonucundan gelir. Bilinmeyen alanlar `Okunamadı` olarak kalır;
büküm sayısı, feature sayısı veya çizgi sayısından tahmin edilmez. Birimsiz
DXF'te mm ölçüsü/çizgi uzunluğu iddia edilmez. Çizgi toplamı, katman ayrımı ve
eğri örneklemesine dayalı yaklaşık görsel bilgidir; CAM kesim hesabı değildir.

## Görüntüleyici ve sınırlar

Yerel Qt Widgets + OpenGL shader/VBO/derinlik tamponu; sürücü/context sorunu
olduğunda aynı mesh'i kullanan asenkron NumPy CPU derinlik tamponu. NumPy
zaten Shapely/ezdxf bağımlılık ağacındadır; yeni paket eklenmedi. Donanım
olmasa da arayüz thread'inde raster yapılmaz. Ortografik/perspektif, 7 standart
görünüş, döndürme, kaydırma, tekerlek, ekrana sığdırma ve crease/boundary
kenarları desteklenir. Üçgen iç köşegenleri CAD kenarı gibi gösterilmez.
Kamera yönleri SolidWorks ön XY (+Z), üst XZ (+Y), sağ YZ (+X) düzenindedir;
izometrikte üç eksenin ortografik kısalması eşittir. Altı yön ve bu eşitlik
ayrı matematiksel testlerle doğrulanır.

- En fazla 120.000 üçgen; mesh LRU en fazla 8 kayıt / 32 MiB.
- DXF en fazla 50 MiB, 200.000 örnek nokta, BLOCK derinliği 16.
- CPU yedeği büyük modellerde daha yavaştır; üretim CAD doğruluğunu temsil etmez.
- Doğrulanamayan bükülmüş konfigürasyon, eksik gövde veya rebuild gereksinimi
  açık hata verir. FlatPattern suppression/rebuild/save uygulanmaz.
- Canlı geometri kabulü ve hedef ekran sürücüsü doğrulaması ayrı adımlardır.

## İncelenen açık kaynak projeler

| Kaynak | İncelenen sürüm | Lisans / karar |
|---|---|---|
| xarial/xcad | `f9feb293` | MIT; SwBody/SwTessellation native API, scope ve private tessellation akışı incelendi |
| xarial/xcad-examples | `69556596` | README ve C# örnek organizasyonu incelendi; bağımsız lisans doğrulanamadı, kod alınmadı |
| xarial/codestack | `0cde3849` | MIT; native import/export ve mevcut bağlantı örnekleri incelendi |
| mrdoob/three.js | `a94d557d`, package 0.186.1 | MIT; browser/WebGL runtime'ı mevcut Qt paketine eklenmedi |
| bernhard-42/three-cad-viewer | `060536e8`, package 5.1.3 | MIT; tessellated mesh, kamera ve kaynak temizliği yaklaşımı incelendi; three 0.184.0 / postprocessing / n8ao bağımlılıkları değerlendirilerek kullanılmadı |

Bu depolardan kaynak kodu veya web varlığı kopyalanmadı. Native Python/Qt
uygulaması bağımsız yazıldı; C# servis, WebEngine, localhost portu veya CDN
eklenmedi. Mevcut PySide6/NumPy/ezdxf lisans paketlemesi korunur.
[Kaynak sürüm ve içerik özetleri](references.json),
[interop metadata imzaları](api-contract.json),
[korunan dosyalar](protected-files.json).

## Doğrulama

Yeni testler gerçek Qt olaylarını ve yerel DXF/raster işlemlerini kullanır;
COM sınırı mock'tur. Kapsam: yanlış aktif belge, tam kaynak yolu, konfigürasyon
geri alma, türetilmiş flat parent, açık gövde kimliği, boş/bozuk mesh, private
tessellation, kaynak revizyonu/önbellek, iptal, eski seçim sonucu, GUI thread'i,
mevcut aktarım önceliği, bağlantı hatası/yenileme, bütün kameralar, delikten
arka planın görünmesi, katman/renk/büküm ve küçük ekran kaydırması.

[Arşiv: İlk ilgili regresyon](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/dxf-3d-preview/related-tests.xml) önceki `2b3cfbf` tabanında çalıştı;
güncel ana dalın tam testinin yerine geçmez. Son tam koşu ve sayıları ayrı
raporlanır. Bu dokümanın varlığı canlı SolidWorks testinin geçtiği anlamına gelmez.

Güncel `8fbd864` tabanındaki ilk tam koşu **1.458 pytest item / 2.336 JUnit
kontrolü, 0 hata, 31 platform/canlı API atlaması** ile geçti:
[Arşiv: kayıt](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/dxf-3d-preview/baseline-full-tests.xml). Son aktarım önceliği ve GPU kaynak temizliği
kontrolleri ardından **142 ilgili item / 186 JUnit kontrolü, 0 hata, 2 atlama**
ile geçti: [Arşiv: kayıt](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/dxf-3d-preview/final-targeted-tests.xml). Son küçük durum mesajı/geri
yükleme koruması için 3 hedefli test tekrar geçti. Örtüşen sayılar toplanmaz.
Windows tam regresyonu ve EXE açılışı ayrı derleme kaydında raporlanır;
gerçek SolidWorks testi, ortam seçilmedikçe atlanır.
Son standart görünüş/kapanış kontrolleri dahil modül koşusu **150 item /
194 JUnit kontrolü, 0 hata, 2 platform/canlı CAD atlaması** ile geçti:
[Arşiv: kayıt](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/dxf-3d-preview/standard-view-tests.xml). Son Linux tam koşusu **2.340 kontrol,
0 hata, 31 atlama**: [Arşiv: JUnit](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/dxf-3d-preview/final-full-tests.xml), [özet](final-linux-checks.json).
Tam koşu envanterinden sonra eklenen kapanış ve görünüş testleri ayrıca
yukarıdaki modül koşusunda yer alır; sayılar örtüştüğü için toplanmaz.

```bash
python -m pytest modules/dxf_dwg/tests
python main.py
QT_QPA_PLATFORM=offscreen python docs/report-tools/capture_dxf_preview.py /tmp/dxf-preview-images
```

Windows / açık lisanslı SolidWorks'te, yalnız ayrı bir test kopyasıyla:

```powershell
$env:GOKWORKS_DXF_PREVIEW_LIVE_SOURCE='C:\test\preview-copy.SLDPRT'
$env:GOKWORKS_DXF_PREVIEW_LIVE_CONFIG='Default'
python -m pytest modules/dxf_dwg/tests/test_preview_live.py -v -s
```

Canlı test hash, etkin belge/konfigürasyon, gerçek mesh ve native açınımı
kontrol eder. Ayrı Windows renderer testi SolidWorks gerektirmez; OpenGL
veya CPU yedeğinin gerçek masaüstünde delikli mesh'i gösterdiğini denetler.

## Teslim edilen Windows EXE

Son kaynak `522cb83`, derleme isteği `e3322de`:
[Windows çalışması](https://github.com/gkkizil/gokworks/actions/runs/40304312494)
başarıyla tamamlandı. Windows regresyonunda **2.348 JUnit kaydı, 0 hata,
26 atlama** var. Gerçek masaüstü renderer testi geçti; lisanslı SolidWorks
gerektiren kaynak/model kabul testi çalıştırılmadı.

Tek dosyalık paket 15 modül, iki tema ve %100 / %125 / %150 ölçeklerde
açılış kontrollerini geçti. Kullanıcıya ayrıca `_internal` klasörü verilmez.
[GOKWORKS.exe indir](https://github.com/gkkizil/gokworks/releases/download/windows-onefile-40304312494-1/GOKWORKS.exe)
(88.807.813 bayt). İndirilen dosyanın PE başlığı, boyutu ve SHA256 değeri
derleme kaydıyla ayrıca karşılaştırıldı:

```text
2a802f049fcc1dfe2d79b2a0f76d5e27517a8e33099a83b54575d3d4d6522f0d
```

[Doğrulama özeti](windows-verification.json). Bu doğrulama, gerçek
SolidWorks oturumunda parça/konfigürasyon eşleşmesi kabulünün yerini almaz.

## EXE sonrası bildirilen açınım düzeltmesi

`PyIDispatch object has no attribute ActiveDoc` hatası, önizlemenin ham COM
nesnesini mevcut açınım exporter'ına iletmesiyle oluşuyordu. Exporter yalnız
`_oleobj_` taşıyan makepy/dynamic sarmalayıcılarını tanıyordu. `_late_bound`
artık ham `Invoke` / `GetIDsOfNames` nesnesini de `DumbDispatch` ile sarar;
BYREF, kaynak dosya, konfigürasyon ve belge geri yükleme kuralları korunur.

Yeni testler `export_one_part` yordamını mock'lamadan geçer: henüz çıktısı
olmayan parça ve DWG seçimi için geçici DXF gerçekten yazılır/okunur, temizlenir;
üretim çıktısı ve önceki aktif belge korunur. COM sunucusu test çiftidir;
lisanslı SolidWorks kabulü değildir. Yukarıdaki EXE bu sonraki kaynak
düzeltmesini içermez; yeni EXE istenirse yeniden derlenmelidir.
