# GOKWORKS · Mühendislik çalışma alanı

24 Ekim 2026 · Mevcut Python/PySide6/Qt Widgets uygulamasına uygulanmış arayüz düzenlemesi.
Autodesk Fusion için verilen tasarım brief'indeki çalışma alanı, Browser, bağlamsal komut ve
Inspector yaklaşımı esas alındı. Autodesk'in kodu, markası veya görsel varlıkları kopyalanmadı.

[Arşiv: Nesting çalışma alanı](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/nesting-dark.png)

[Arşiv: Açık tema](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/nesting-light.png) · [Arşiv: Küçük pencere](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/nesting-dark-minimum.png) ·
[Arşiv: Önceki aynı ekran](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/nesting-dark.png) · [Yakalama kaydı](after/capture.json)

## İnceleme ve uygulama kapsamı

İlk incelemede çalışma dizini `main` üzerindeki `3339ad65ee07f21853bcf3597a955a76fdbd5eb9`
sürümündeydi. Depodaki 332 PNG/JPG/JPEG/WEBP varlık listelendi; README ve önceki arayüz
raporlarındaki ekranlar güncel `ui.py` dosyalarıyla eşleştirildi. Tarihî ekran görüntülerine
dayanarak kod değiştirmek yerine uygulama çalıştırılıp 14 modülün başlangıç görüntüleri alındı.
Product Design denetim akışıyla önce ekran kanıtları, sonra kaynak kod ve etkileşimler incelendi.

Bulgu → uygulanan çözüm:

| Bulgu | Uygulanan düzenleme | Kontrol |
| --- | --- | --- |
| Uzun, iki genel başlık altındaki düz modül listesi | Aktarım, Montaj, Üretim ve Hesaplar grupları; açılır başlıklar, araç araması, etkin satırda ince vurgu | Ctrl+K, Ctrl+B, arama filtresi, grup tercihi ve sayfa verilerinin korunması |
| Ana komutların bazı ekranlarda başlıkta, bazılarında kaynak panelinin altında olması | Mevcut düğmeleri kullanan ortak üst komut şeridi | Kaynak paneli kaydırılırken komutlar görünür; aynı sinyal/işlem nesneleri |
| Geniş kartlar, maviye kayan koyu yüzeyler, yüksek başlıklar | Tek QSS, nötr gri yüzeyler, bir ana vurgu rengi, küçük köşeler ve ölçülü aralıklar | Koyu/açık tema; ortak yazı renkleri için kontrast hesabı |
| Nesting parametrelerini görmek için çalışma alanından ayrılmak | Solda parça listesi, merkezde levha, sağda bağlamsal native `QDockWidget` | Seçim, iki yönlü alan eşlemesi, mevcut sac/parça editörleri, sonuç geçersizleştirme |
| Küçük pencerede üç panelin çizimi sıkıştırma riski | Sağ panel genişliğe göre gizlenir; istenirse ayrı pencere açılır | 820×560, 1024×700, paneli yüzdürme/kapatma ve genişlik tercihi |
| Aynı başarı mesajının sayfa altında ve durum çubuğunda tekrarı | Başarı/ilerleme alttaki durum çubuğunda; hata sayfada ayrıntısıyla da gösterilir | Tam mesaj araç ipucunda, hataya özel renk ve boş durum mesajı |

Önce/sonra ve ara aşama görüntüleri gerçek Qt widget yakalamalarıdır. Ekranların HTML veya
görsel üretim aracıyla hazırlanmış maketleri kullanılmadı. Autodesk çevrimiçi yardım sayfası
bu ortamda 403 yanıtı verdi; canlı Fusion uygulamasının incelendiği iddia edilmiyor.
Sonraki görüntülerde 3D kuyruk ve profil planı ayrıca örnek girdilerle doldurulmuştur;
bu fark yeni CAD okuma veya hesaplama yeteneği eklenmiş olduğu anlamına gelmez.

## Kullanım

1. Üstteki **Çalışma alanı** listesinden grubu veya soldan modülü seçin. Aynı gruba geri
   dönüldüğünde bu oturumda son kullanılan modül açılır. Sayfalar yeniden oluşturulmaz.
2. **Ctrl+K** ile araç bulun. Grup adları da aranabilir. **Ctrl+B** sol gezgini simgelere
   daraltır; simgeler üzerinde araç isimleri gösterilir.
3. Kaynakları/girdileri düzenleyin. Ana okuma, hesaplama veya aktarım komutları üsttedir.
   Aktarım ve montaj araçlarında kaynaklar solda, tablo/günlük sağdadır.
4. Nesting'de parça veya levha seçin. **Özellikler** panelinde sac bilgisi, seçili parça ve
   yerleşim ayarları görünür. Grup başlıkları kapatılabilir. Formla panel aynı değerleri
   kullanır; ayar değiştirmek mevcut motorun normal sonuç geçersizleştirme işlemini tetikler.
5. Panel kenarından genişliği değiştirin veya başlığından yüzdürün/kapatın. Dar pencerede
   **Özellikler** ayrı pencere açar. Eski **Sac ve ayarlar** penceresi bütün maliyet alanlarıyla durur.
6. **Görünüm** menüsünden tema değiştirin. Ayarlar ve lisanslar da buradan/sol alt bölümden erişilir.

## Modüllere göre çalışma düzeni

| Modül | Korunan iş akışı ve yeni görsel düzen | Önce / sonra |
| --- | --- | --- |
| PDF aktarımı | Sol kaynak/çıktı, sağ dosya durumu/günlük, üst tarama/aktarım | [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/pdf-dark.png) · [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/pdf-dark.png) |
| DXF / DWG | Kaynak/çıktı ve açınım seçenekleri; sonuç listesi sağda | [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/dxf_dwg-dark.png) · [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/dxf_dwg-dark.png) |
| 3D Dönüştürücü | Kaynak dosya/klasör seçimi görünür, formatlar solda, kuyruk/ilerleme sağda | [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/cad_converter-dark.png) · [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/cad_converter-dark.png) |
| BOM | Kompakt kaynak ürün ağacı, parça/ürün ağacı sekmeleri ve dışa aktarma | [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/bom-dark.png) · [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/bom-light.png) |
| İsimlendirme | Kaynak montaj ve isim kuralları solda, önizleme sağda, paket komutu üstte | [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/naming-dark.png) · [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/naming-dark.png) |
| K faktörü / yarıçap | Manuel atama tablosu, bağımsız hesap yardımındaki canlı takım çizimi ve montaj sonuçları | [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/k_factor-dark.png) · [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/k_factor-dark.png) |
| ISO geçmeler | Solda ISO/manuel girdiler; sağda kesit, boşluk örnekleri ve teknik yorumlar | [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/iso_fits-light.png) · [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/iso_fits-light.png) |
| Geometrik toleranslar | Aranabilir teknik katalog, tolerans bölgesi/çerçeve ve ölçüm açıklamaları | [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/geometric_tolerances-dark.png) · [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/geometric_tolerances-light.png) |
| Tolerans yığılması | Ölçü kaynağı, zincir, ayarlar, sonuçlar ve teknik resim çıktısı korunur | [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/tolerance_stack-dark.png) · [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/tolerance_stack-dark.png) |
| Cıvata | Yük girdileri, mevcut emniyet grafiği, yük çizimleri ve tam rapor | [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/bolt-dark.png) · [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/bolt-dark.png) |
| Hızlı tork | Kompakt giriş paneli, ön yük/tork, bağlantı kesiti ve yaklaşık K rehberi | [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/bolt_torque-dark.png) · [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/bolt_torque-dark.png) |
| Ağırlık | Malzeme/kesit girdileri, kesit diyagramı, net sonuç ve açılır ayrıntılar | [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/weight-dark.png) · [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/weight-dark.png) |
| Nesting | Parça listesi + merkezi çizim + isteğe bağlı özellik paneli; levha sekmeleri ve sonuçlar | [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/nesting-dark.png) · [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/nesting-dark.png) |
| Profil kesim | Kesim listesi, SolidWorks taraması ve görsel kesim planı sekmeleri | [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/profile_cutting-dark.png) · [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/profile_cutting-dark.png) |

Bu değişiklik BOM'a yeni bir malzeme editörü eklemez; mevcut veri modeli ve okuma/raporlama
işlevleri korunur. Teknik hesap açıklamaları, güvenlik uyarıları, kullanıcı onayları ve CAD
yazma sınırları kaldırılmadı. Hesaplama/optimizasyon/COM motorları değiştirilmedi.

## Tasarım sistemi ve kaynak dosyaları

- `gui_qt/theme.py`: koyu/açık palet, ortak QSS; 12 px normal metin, 17 px sayfa başlığı,
  24 px birincil hesap sonucu, yaklaşık 26 px kontrol yüksekliği, 28 px standart tablo satırı,
  2–3 px köşeler. Bunlar Qt mantıksal piksel değerleridir; DPI'ı Qt uygular.
- `gui_qt/workspace.py`: tekrar kullanılabilir modül gezgini ve daraltılabilir gezinme grupları.
- `gui_qt/app.py`: native çalışma alanı `QToolBar`, bağlamsal `QDockWidget`, durum çubuğu.
- `gui_qt/components.py`: mevcut `BasePage.actions` API'sini kullanan komut şeridi,
  kaynak/sonuç sütunları ve ortak formlar.
- `gui_qt/icons.py`, `assets/qt/`: önbellekli çizgisel ikonlar ve temaya uygun açılır liste oku.
- `gui_qt/models.py`: sayısal tablo hücrelerinin sağ hizası; veri/sonuç biçimleri korunur.
- `gui_qt/diagrams.py`: eski çizim kâğıdı arka planlarını ortak temayla eşleştirme.
- `modules/nesting/inspector.py`: mevcut parametrelerle bağlı bağlamsal özellikler.
- `modules/nesting/ui.py`, `modules/bolt_torque/ui.py`, `modules/naming/ui.py`:
  modüle özgü panel ölçüleri, üstte hizalanmış kaynak formu ve yerleşim.
- `packaging/build_windows.py`: yeni küçük tema varlıklarının tek EXE'ye dahil edilmesi.
- `packaging/run_windows_tests.py`: yeni workbench GUI testlerinin de mevcut 8 testlik
  süreç sınırına alınması; testler atlanmaz, başarısız süreçler gizlenmez.

Yeni uygulama bağımlılığı, web arayüzü veya ticari eklenti eklenmedi. Mevcut PySide6 lisans
bildirimleri ve paketleme düzeni korunur; eklenen ikonlar projeye ait çizimlerdir.

Ek görünümler: [Arşiv: K/R takım kesiti](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/kr-tooling-helper.png),
[Arşiv: tolerans yığılması sonuçları](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/stack-results.png),
[Arşiv: dar pencerede ayrı özellikler penceresi](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/nesting-floating-properties.png),
[Arşiv: araç araması](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/after/module-search.png).

## Doğrulama

- Son tam regresyon: **1.167 test başarılı, 878 alt test başarılı, 9 atlanan; sıfır hata/başarısızlık**.
  Toplam 1.176 bağımsız test toplandı; 71 ayrı süreçte çalıştı. Alt testlerle JUnit toplamı 2.054'tür.
  [Sayısal özet](test-summary.json), [Arşiv: JUnit](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/final-regression.xml), [süreç çıkışları](final-regression-summary.txt).
- Yeni çalışma alanı kontrolleri; grup geçişleri/arama, kayıtlı sayfa verileri, üst komutlar,
  Inspector alan eşlemesi, seçimle sonucun korunması, parametreyle geçersizleştirme,
  bölüm kapatma, mevcut editörler, panel genişliği, dar/yüzer panel, worker sırasında
  kilitleme, hata mesajı ve iki temayı kapsar: `tests/test_fusion_workbench.py`.
- İlk tam turdaki iki paket kaynağı kontrolü başarısız oldu: klasör yerine dosya bekleyen
  paketleme sözleşmesi yeni ikonlar için sağlanmıyordu. İki PNG ayrı kaynak olarak eklenerek
  düzeltildi. [Arşiv: İlk sonuç](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/initial-regression.xml), [düzeltme sonrası 21 hedefli test](targeted-fixes.txt)
  ve ardından yukarıdaki tam başarılı tur saklanır. Başarısızlıklar silinerek başarı raporlanmadı.
- Son kaynak açılış/işlev kontrolü: **14 modül, iki tema, dört çözünürlük**.
  [Standart ölçek](source-dpi-1.json), [%125](source-dpi-1.25.json), [%150](source-dpi-1.5.json).
  Bunlar Linux `offscreen` üzerinde gerçek Qt ölçeklendirmesidir; Windows masaüstü testi değildir.
  Yerel DXF/Excel/PDF çıktıları, delik içi nesting, profil planı, tolerans örneği,
  K/R takım şeması ve izole PDF worker başlangıcı da bu kontrolde çalıştırıldı.
- Görsel kayıt: **64 native görüntü**; her modül 1440×900 ve 820×560 boyutlarında
  açık/koyu temayla açıldı. [Dosya/boyut/modül kaydı](after/capture.json).
  [Arşiv: Ara aşamalar](https://github.com/gkkizil/gokworks/tree/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/stages) uygulamanın shell ve Inspector adımlarından sonra çalıştırıldığını gösterir.
- Gerçek `QTest.keyClick` ile [Ctrl+K / Ctrl+B](keyboard.json) geçti. Ortak metin/yüzey,
  vurgu ve hata renkleri için ölçülen kontrastlar **en az 4,66:1**:
  [Renk çiftleri](contrast.json). Bu sonuç tüm erişilebilirlik kurallarını kapsamaz.
- Tanımsız isim kontrolü: değişen/yeni GUI kaynaklarında Ruff `F821/F822/F823` geçti;
  `git diff --check` ve belge bağlantıları kontrolü geçti.

Aynı Python/Qt ile ardışık iki temiz süreçte, her sürümde 140 önbellekli modül geçişi ölçüldü.
Başlangıç sürümü, düzenleme öncesinde kaydedilen commit'in ayrı geçici kopyasıdır;
projenin yedek GitHub reposu kullanılmadı.

| Ölçüm | Önce | Sonra |
| --- | ---: | ---: |
| İçe aktarmalar dahil açılış | 909,6 ms | 860,9 ms |
| Modül geçişi ortancası | 5,17 ms | 5,75 ms |
| En uzun geçiş | 40,0 ms | 54,4 ms |
| Tepe RSS | 183.988 KiB | 187.924 KiB |
| 140 geçiş öncesi/sonrası widget sayısı | 2.352 / 2.351 | 2.512 / 2.511 |

Yeni çalışma alanı/Inspector ile ortanca geçiş yaklaşık 0,58 ms, tepe bellek yaklaşık 3,84 MiB
arttı; gezinme sırasında widget sayısı büyümedi. Bunlar tek ölçüm çiftidir; istatistiksel eşdeğerlik,
heap sızıntısı olmadığı veya Windows EXE performansı kanıtı olarak sunulmaz.
[Ham karşılaştırma](performance-comparison.json) · [Kaynak dosyası SHA256 kaydı](source-manifest.json).

Tekrar çalıştırmak:

```bash
python -m pip install -r requirements.txt
python main.py
QT_QPA_PLATFORM=offscreen python docs/report-tools/capture_fusion_workbench.py docs/fusion-workspace/after
QT_QPA_PLATFORM=offscreen python packaging/run_windows_tests.py
QT_QPA_PLATFORM=offscreen python main.py --self-check docs/fusion-workspace/source-dpi-1.json
```

Windows masaüstünde ilk iki komut normal Qt platformuyla kullanılabilir. `offscreen` yalnız
ekransız test komutları içindir. Windows tek EXE derlemesi mevcut `python packaging/build_windows.py`
akışıyla yapılır; yeni tema varlıkları otomatik eklenir.

## Sınırlar

Bu çalışma Linux kaynak uygulamasında doğrulanır. Gerçek Windows masaüstü, ekran okuyucusu,
çoklu monitör geçişi, dokunmatik kullanım ve canlı SolidWorks belgeleri ayrı doğrulama gerektirir.
Kontrast hesabı tüm diyagram renklerinin veya erişilebilirlik standardının bütünüyle doğrulandığı
anlamına gelmez. Bu arayüz değişikliği için yeni Windows EXE üretilmedi. Mevcut indirme bağlantısı
önceki sürümün EXE'sidir. Yalnız `main` güncellenir; `release` dalı ve yedek repo değiştirilmez.
