# Nesting çalışma alanı — 29 Ekim 2026

Bu çalışma yalnız Nesting arayüzünü değiştirir. Amaç, DXF seçimi → sac ve
yerleşim koşulları → gerçek yerleşim → kontrol/çıktı akışını aynı çalışma
alanında anlaşılır kılmaktır. Mevcut PySide6 / Qt Widgets mimarisi kullanılır.

Başlangıç commit'i: `5dc713a44f56fc58f7bbd2106269c39362324347`.
Motor **GOKWORKS NFP 1.3**, DXF okuyucu **ezdxf**, geometri **Shapely**,
görüntüleyici mevcut **QGraphicsView / QGraphicsScene**'dir. Hesap motoru,
geometri dönüşümleri, DXF içe/dışa aktarma, muhasebe ve rapor hesabı korunur.

## Yeni kullanıcı akışı

1. **DOSYA → DXF içe aktar** veya soldaki **DXF ekle**: dosyaları okuyun.
   Ağaç, gerçek malzeme/kalınlık grupları ve adetleri gösterir. Sorunlu
   dosyalar ayrı görünür; çift tıkla düzeltme/yeniden okuma korunur.
2. **Parçaya tıklayın:** yerleşimden önce gerçek kontur, delikler ve ölçüler
   görünür. Sağdaki seçili nesne bölümünde alan, kg/adet ve çevreler vardır.
   Bu görüntü **yerleşim sonucu değildir** diye açıkça etiketlenir.
3. **Sacı seçin:** solda stoklar, sağda malzeme, en/boy, kalınlık ve stok
   adedi. Düzenleyip **Uygula**'ya basın. Taslak eski planın çıktısını kapatır;
   hatalı sayı gerçek proje verisini bozmaz. **Geri al** kayıtlı değere döner.
   Yerleştir/Kaydet geçerli taslağı önce uygular. Fiyat/şablon/malzeme
   kütüphanesi ve tam ayarlar penceresi korunur.
4. **YERLEŞİM / Yerleştir:** işlem mevcut arka plan iş yöneticisinde çalışır.
   Gerçek fiziksel plakalar stokların altında oluşur ve mevcut sekmelerle
   aynı kimliğe bağlanır. Seçim, zoom/pan, sığdırma ve otomatik delik içi
   yerleşim korunur. Başka plakadaki bir parça seçilince ilgili plaka açılır.
5. **RAPOR → Sonuç tablosunu göster:** sac, yerleşen/istenen adet, brüt/net/
   fire ve verim tabloları. Tamamen yerleşmeyen parça da 0 adetle görünür.
   Eksik sonuçta üretim DXF/PDF/Excel'i kapalıdır; ayrıntı ve proje kaydı
   kullanılabilir. Alt durum satırı gerçek adet, aktif plaka ve mm'yi gösterir.

[Arşiv: Yeni Nesting çalışma alanı](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/after/04-layout-dark.png)

[Arşiv: Gerçek sonuç tablosu](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/after/07-results-light.png)

## Önceki ekranın incelenmesi

`docs/nesting-workspace/03-plates-dark.png` ve
`docs/nesting-usability/02-stock-dark.png` tarihî kaynak olarak incelendi.
Bunlar yeni denetimin kanıtı sayılmadı. Güncel başlangıç kodu değiştirilmeden
gerçek Qt uygulaması çalıştırıldı; aşağıdaki **before/** görüntüleri bu
oturumda, yukarıdaki başlangıç commit'inde alındı. Sonraki **after/**
görüntüleri de çalışan gerçek uygulamadandır.

Kaynaklar depodaki `docs/nesting-example/input/GW-001.dxf`, `GW-002.dxf`,
`GW-003.dxf` dosyalarıdır. Her biri 3 adet, 300×240×2 mm stok, 8 plaka stok
ve 45 TL/kg girişleriyle mevcut motor çalıştırıldı. **9 parça / 2 plaka**
sonucu bağımsız `validate_result` ile doğrulandı. Yerleşim koordinatları,
verim veya ağırlıklar gösterim amacıyla uydurulmadı.
Hata ekranı için geçici, açık bir LINE içeren gerçek DXF de okuyucuya
verildi; reddedilen dosya yerleşim başlamadan listeden kaldırıldı.
[Dosya SHA256'ları ve gerçek toplamlar](after/capture.json).

| Adım / önem | Önceki durum ve etkisi | Uygulanan düzenleme ve yeni durum |
| --- | --- | --- |
| 1. Başlama ve parça bulma · yüksek | Düz listede malzeme/kalınlık ilişkisi ipucuna bağlıydı; stoklar ana ekranda yoktu. [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/before/02-imported.png). | Yerel QTreeView, gerçek malzeme/kalınlık grupları ve adet toplamları; ayrıca sac/gerçek plaka ağacı. İlk içe aktarma sırası korunur. **Durum: düzeltildi.** [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/after/02-part-preview-dark.png), [Arşiv: gerçek okuma hatası](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/after/02b-import-error-dark.png). |
| 2. Kesimden önce kontrol · yüksek | Bir parça seçilse de merkez boş kalıyordu. [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/before/02-imported.png). | Gerçek parça konturu ve delikleri, kaynak/sonuç ayrımı, iki yönlü seçim ve teknik bilgiler. **Durum: düzeltildi.** [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/after/02-part-preview-dark.png). |
| 3. Sacı düzenleme · yüksek | Ölçüler için geniş ayrı pencereye geçiliyordu. [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/before/03-settings.png). | Mevcut sağ QDockWidget içinde kompakt ölçü çiftleri, açık birimler, Uygula/Geri al ve geçersiz taslak koruması. Tam stok/fiyat penceresi gerektiğinde korunur. **Durum: düzeltildi.** [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/after/03-stock-preview-dark.png), [Arşiv: geçersiz taslak](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/after/03b-stock-validation-dark.png). |
| 4. Yerleşimi okuma · yüksek | Bazı adlar komşu kontur/delik üzerine taşıyordu; yalnız üst sekmelerden plaka seçiliyordu. [Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/before/04-result.png). | Sabit okunabilir piksel boyutu, yalnız gerçek malzeme içinde sığan etiket; stok altındaki fiziksel plaka seçimi, uyarlanır grid ve görünüm komutları. **Durum: düzeltildi.** [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/after/04-layout-dark.png). |
| 5. Sonuç ve dar ekran · orta | Sonuçlar birkaç metin satırı ve ayrıntı penceresiyle sınırlıydı. | Gerçek sac/parça tabloları; küçük yükseklikte yinelenen özetler yerine kontur ve tabloya alan ayrılır. **Durum: doğrulandı.** [Arşiv: Açık tema](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/after/07-results-light.png), [Arşiv: 1024](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/after/08-compact-dark.png), [Arşiv: çizim odağı](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/after/09-canvas-focus-dark.png). |

## Yerleşim ve teknik kararlar

- Üstte kompakt başlık/proje adı ve yerel **QToolBar** içinde beş komut
  grubu. Birincil **Yerleştir** doğrudan görünür; komutlar mevcut slot'lara
  bağlanır. Gereksiz büyük komut kartları eklenmedi.
- Sol panel yaklaşık **240 mantıksal px**; parça ve sac alanları dikey
  QSplitter, geometriyle ayrımı yatay QSplitter'dır. Sağda mevcut uygulama
  **QDockWidget**'ı kullanılır; yaklaşık 300 px başlangıç ölçüsü ve kullanıcının
  önceki dock genişliği tercihi korunur. Diğer modüllerin kabuğu değiştirilmez.
- `PartTreeModel`, mevcut düz `NestingTableModel → FilterProxy` verisini
  sunar. Her yaprak kaynağın aynı satırına eşlenir. Filtre/sıralama/model
  yenilemesinde seçim satır numarasıyla değil gerçek kimlikle korunur.
  Yeni dosya/grup için satır başına QWidget oluşturulmaz.
- `SheetTreeModel` yalnız tanımlı stokları ve mevcut doğrulanmış sonucun
  fiziksel plaka anahtarlarını `(sheet_id, sheet_number)` gösterir. Kullanılmayan
  stoğa sonuç plakası uydurulmaz; stok önizlemesi ayrı durumdur.
- Ana yatay `workspace`'in iki mevcut çocuğu, eski form isimleri ve
  `part_model`, `part_proxy`, `sheet_tabs`, `selected_sheet_key()` bağlantıları
  korunur. Ağaç, düz satır üzerinden `selectRow` kullanan mevcut uygulama
  bağlantılarını kimlik eşlemesiyle destekler.
- Görüntüleyici `painter_path` ve `placed` ile aynı gerçek geometriyi çizer.
  Y ekseninin ekran dönüşümü, delikler ve kontur koordinatları korunur.
  Grid yalnız gösterimdir; snap, geometrik yuvarlama veya CAM telafisi yoktur.
- Pan sürükleme ile, zoom tekerlek/menü/klavye ile, fit `Sığdır`/Home ile
  çalışır. Seçim ve grid açma/kapama planı yeniden hesaplamaz.
- `design.py` mantıksal-piksel ölçülerini ve modüle sınırlı QSS'yi toplar;
  renkler mevcut merkezi `gui_qt.theme.COLORS` kaynağından gelir. Yeni tema
  veya GUI bağımlılığı eklenmez; nötr koyu/açık palet korunur.

## Değişen dosyalar

| Dosya | İşlev |
| --- | --- |
| `modules/nesting/ui.py` | Komut grupları, iki ağaç, önizleme/sonuç ayrımı, gerçek sonuç tabloları, durum ve mevcut iş bağlantıları. |
| `modules/nesting/ui_widgets.py` | Mevcut görüntüleyicide kaynak/stok önizlemesi, grid, zoom tuşları ve kontur içinde kalan etiketler. |
| `modules/nesting/inspector.py` | Mevcut dock içinde sac taslağı doğrulaması, uygulama/geri alma, tüm gerçek yerleşim parametreleri ve seçili parça bilgileri. |
| `modules/nesting/workspace_models.py` — yeni | Saf Qt sunum adaptörleri; kaynak kimliğini koruyan parça grupları ve gerçek stok/plaka ağacı. |
| `modules/nesting/design.py` — yeni | Nesting'e sınırlı ölçüler ve tema kullanımı. |
| `modules/nesting/tests/test_nesting_gui.py` | İki mevcut testin ağaç indeks eşlemesi ve sığan etiket davranışına uyarlanması; kontroller kaldırılmaz. |
| `modules/nesting/tests/test_workspace_models.py` — yeni | Yerel Qt model sözleşmesi, kaynak eşlemesi, filtre/sıralamada kimlik. |
| `modules/nesting/tests/test_workspace_gui.py` — yeni | Gerçek DXF, delik, taslak/çıktı koruması, JSON, plaka/seçim, zoom/grid, sonuç ve çözünürlük akışları. |
| `modules/nesting/README.md` | Güncel kullanım ve sınırlar. |
| `docs/report-tools/capture_nesting_workspace.py` — yeni | Aynı gerçek DXF/NFP akışından yeniden üretilebilir ekran görüntüleri. |
| `.github/workflows/windows-nesting.yml` — yeni | Nesting ve mevcut çalışma alanı sözleşmeleri için bağımsız Windows kapısı; %125/%150 Qt ölçekleri, açılış ve gerçek ekran kayıtları. |
| Bu rapor dizini | Önce/sonra ekranlar, kaynak sınırı ve test kanıtları. |

## Korunan hesap ve veri sözleşmeleri

`engine.py`, `geometry.py`, `models.py`, `dxf_import.py`, `batch_import.py`,
`validation.py`, `accounting.py`, `materials.py`, `storage.py`, `cutting.py`,
`render.py`, `dxf_export.py`, `report.py`, `pdf_report.py` ve modül sürümü
değiştirilmedi. [Dosya/hash sınırı](scope-checks.json).

- `.goknest.json`: `GOKWORKS-NESTING`, sürüm **1**, birim **mm**; gömülü
  geometriler, `import_sources`, parça/stock kimlikleri ve sonuç şeması aynıdır.
- İş olayları `nest_file`, `nest_import_done`, `nest_progress`, `nest_result`,
  `nest_project`, `nest_message` ve `job_error` aynıdır. Ağır işlemler mevcut
  JobManager'da kalır; widget'lara worker thread'inden erişilmez.
- Gerçek stok/sonuç değiştiğinde eski plan kapatılır. Yalnız fiyat/yoğunluk/
  operasyon maliyeti değişikliği mevcut doğrulanmış koordinatları yeniden
  fiyatlar. Eksik yerleşimde üretim çıktısı koruması sürer.
- **Delik içi yerleşim otomatiktir**; kullanıcıya yeni bir aç/kapat seçeneği
  eklenmedi. Aynalama, izinli dönüşler, kerf ve kontur hata payları aynı motor
  koşullarıdır. Kanıtlanmış matematiksel optimum iddiası eklenmedi.
- `gui_qt` ortak uygulama/tema/bileşenleri ve diğer modüllerin üretim
  kaynaklarında bu görev kapsamında değişiklik yapılmadı.

## Doğrulama

Başlangıçtaki 28 mevcut Nesting GUI testi başarılıydı. Uygulama sonrasında
Linux / Python 3.13.5 / Qt-PySide6 6.10.3 / offscreen ortamında:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=.cache/runtime-updated \
  /workspace/.cloud-setup/qt-venv/bin/python packaging/run_windows_tests.py \
  modules/nesting/tests tests/test_fusion_workbench.py

QT_QPA_PLATFORM=offscreen PYTHONPATH=.cache/runtime-updated \
  /workspace/.cloud-setup/qt-venv/bin/python main.py --self-check /tmp/gokworks-nesting-source-check.json
```

- **134 test: 0 hata, 0 başarısızlık, 0 atlanan.** On sınırlı süreç çıkış
  kodu 0. [Arşiv: JUnit](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/tests.xml), [Arşiv: çalıştırıcı kaydı](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/tests.log).
  Çalıştırıcının adı Windows olsa da bu kayıt Linux çalışmasıdır.
- **11 yeni test**, mevcut motor ve gerçek DXF/Qt kontrolleriyle çalışır.
  `qtmodeltester` hiyerarşik modelin yerel Qt sözleşmesini de kontrol eder.
- Son tablo genişlikleri/metin düzeninden sonra üç model/görünüm kontrolü
  ayrıca başarılı: [Arşiv: son sunum kontrolleri](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/final-presentation.xml).
  Kaynak Qt ölçek matrisleri de %125 ve %150'de başarılı;
  [Arşiv: 125](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/source-dpi-125.xml), [Arşiv: 150](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261029-nesting-workspace/source-dpi-150.xml). Her kayıtta iki tema,
  dört istenen boyut, gerçek istemci boyutu/DPR ve sonuç tablosu açık/kapalı
  kontrolleri bulunur.
- **16 modüllük açılış/self-check başarılı**; Nesting DXF/Excel/PDF örnekleri
  ve mevcut modül bağlantıları çalıştırıldı. [Kaynak raporu](source-smoke.json).
  İlk deneme, çalışma ortamında mevcut dişli modülünün zaten requirements'a
  yazılmış OCP paketi eksik olduğu için durmuştu; paket çalışma ortamına
  kurulduktan sonra tekrar başarılı oldu. Requirements dosyası değiştirilmedi.
- **1366×768 ve 1920×1080**, iki tema; ayrıca 1024×700 ve 820×560,
  sonuç tablosu açık/kapalı hâlleri ve panel gizleme doğrulanır.
- Yerel Windows testinde masaüstü çözünürlüğü ile pencerenin istemci alanı
  ayrılır. Başlık/kenarlık/görev çubuğu sonrası gerçekten kullanılabilir alan
  hesaplanır; istenen ve test edilen boyutlar ile DPR JUnit'e kaydedilir.
  İlk Windows çalışmasında 133 test başarılı, bir boyut varsayımı hatalıydı:
  1920×1080 istenen istemci alanı Windows tarafından 1920×1061'e kısılmıştı.
  Düzeltme test/yakalama araçlarına sınırlıdır; üretim arayüzü ve görünürlük
  eşikleri değiştirilmedi.
- Ruff `F821,F822,F823` ve `git diff --check` başarılı.
- 5000 satır / 4 grup için Qt sunum adaptörünün ilk kurulumu bu Linux
  oturumunda 142,05 ms ölçüldü. Bu, geometri veya yerleşim motorunun hız
  ölçümü değildir. [Ölçüm kapsamı](model-performance.json).

## Tamamlanan Windows kontrolü ve GitHub durumu

- Uygulama düzenlemesi: `609d6ff42caff67ee5248a6f07caacc75a1c5cfb`.
- Çerçeve/istemci alanı test düzeltmesi: `56b4927`; üretim arayüzü bu
  düzeltmede değiştirilmedi. Her ikisi de **main** dalına gönderildi.
- [Windows Nesting workspace — başarılı](https://github.com/gkkizil/gokworks/actions/runs/40865608530),
  job `123419497120`. Test edilen tam commit sayfadan doğrulandı.
- **134 test: 0 başarısızlık, 0 hata, 0 atlanan**. %125 ve %150 Qt ölçek
  kontrolleri, tam uygulama açılış/self-check'i ve gerçek DXF/NFP ile yerel
  Windows ekran yakalama adımı da ayrı ayrı başarılıdır.
- [Commit, adım sonuçları ve sayım kanıtı](windows-checks.json).
  Native ekranlar ve DPI JUnit kayıtları aynı çalışmanın
  **Windows-Nesting-workspace** artifact'ındadır. Rapor/görsel son commit'i
  uygulama kodunu değiştirmez.
- Kullanıcının isteği doğrultusunda **EXE oluşturulmadı**, derleme isteği
  veya release yayını yapılmadı.

## Erişilebilirlik ve kalan sınırlar

- Ağaçlar yerel Qt model/view kullanır; açık metin grupları, adetler, birimler,
  klavye seçimi, odak/disabled durumları ve tam içerikli araç ipuçları vardır.
  Hata/eksik yerleşim yalnız renkle anlatılmaz. Parça seçiminin kaynak ve
  plaka görünümüne iki yönlü etkisi test edilir.
- Küçük ekranlarda sağ dock mevcut uygulama davranışıyla gizlenebilir veya
  yüzer açılır. GÖRÜNÜM ve mevcut Özellikler komutu erişimi korur. Tablo
  açıkken tekrarlanan özetler kısaltılır; kontur alanı korunur.
- Buradaki görsel inceleme gerçek Linux Qt yakalamalarıdır. Windows yerel
  işlev/ölçek testleri ayrı CI kanıtıdır. Gerçek farklı marka monitörler ve
  ekran okuyucu ile insan testi yapılmadı; tam erişilebilirlik uygunluğu
  iddia edilmez.
- Motorun mevcut sezgisel en-iyi-sonuç yaklaşımı, tekrarlanabilir seed,
  zaman sınırı ve nominal DXF/CAM sınırları aynıdır. Yeni stok/yerleşim
  algoritması, serbest elle parça taşıma veya takım yolu üretilmedi.
