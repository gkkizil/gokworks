# Belt Drive Designer mimarisi ve aşama sınırları

## 5 Kasım 2026 backend güncellemesi

Kullanıcı GUI geliştirmesini kapsamdan çıkardı. Aşağıdaki eski aşama planının
yanında artık `design_models`, `design_search`, `design_ranking`,
`design_pairs`, `design_serialization`, `design_cli` ve ürün/rating katalog
katmanları uygulanmıştır. Aşama 1 matematiği ve eski API'ler değiştirilmedi.

```text
DesignRequest + ProductCatalog (source/belt/pulley/rating ayrı)
  → kaynak/seri/profil/uyumluluk grupları
  → kayıtlı kasnak çiftleri → erken devir/çap/diş filtresi
  → gerçek kayıtlı kayış boyutları → mevcut tam uzunluk/C çözümü
  → bilinen boyut/sınır kontrolleri → declared-table rating
  → sert retler / ayrı doğrulanmamış grup → deterministik sıralama
  → kapsam/iptal/sınırlama raporu → v2 kayıt / JSON karşılaştırma
```

Resmî üretici sağlayıcıları için yeterli veri yoktur. Gates/Optibelt kaynak
adaptörleri normalize yerel ürün sözleşmesi içindir; gerçek üretici rating
yöntemleri uygulanmış değildir. Deneysel tablo aritmetiği `PROVISIONAL`
kalır. `OFFICIAL_VERIFIED` bir kullanıcı girdisiyle verilemez; bu sürümde
hiçbir ürün veya güç tablosuna resmî onay tanımlanmamıştır.

Tosyalı PDF adaptörü ve 342 boyut kaydı eklendi; kaynak SHA/sayfa ve 146
karantina kaydı korunur. Kayış/kapasite verisi olmadan 32 örnek kasnak çifti
bulunabilir, fakat bunlar tam sürücü tasarımı değildir. Diğer üreticilerle
çapraz uyumluluk otomatik varsayılmaz.

`ProductSource.effective_status` ve `CapacityEvaluation.manufacturer_verified`
ayrımı korunmalı. Gelecekte resmî onay için ayrı, içerik özetiyle sabitlenmiş
inceleme kanıtı ve üreticiye özgü referans hesapları gereklidir; yalnız marka
adına/URL'ye bakılarak onay veren bir yükleyici eklenmemelidir.

UI/menü/ortak dosya değişikliği yoktur. Güncel sözleşmeler ve doğrulama
kanıtları [AUTOMATIC_DESIGN_REPORT.md](AUTOMATIC_DESIGN_REPORT.md) içindedir.

## Uygulanan Aşama 1

```text
CLI / ileride Qt sayfası
       ↓ immutable BeltDriveSpecification
validation → calculation → engineering.{kinematics,belt_length,forces}
                  ↓                       ↓
             BeltDriveResult ← geometry.BeltPath (Line + Arc)
                  ↓
         serialization / CalculationReport

catalog.profiles   → profil kimliği, nominal adım, destek sınırları
catalog.models    → beyan edilen boyutlar ve kaynak metadatası
engineering.belt_selection → her boyut için yeniden fiziksel/geometrik çözüm
controller.calculation_job → JobManager events.put(('belt_result', report))
```

`models` donmuş/slots dataclass'ları kullanır. Hesap, CAD veya arayüz
nesnesi tutmaz. Sonuçlar açık birim ve referans çizgisi içerir.
Geometri, hesap ve ilerideki çizim için tek analitik kaynaktır. Motor
standart kütüphane dışında import yapmaz. İptal `threading.Event` uyumlu
`is_set()` nesnesiyle kontrol edilir; `CalculationCancelled` ayrı hatadır.
İş fabrikası tamamlanmış tek rapor yayımlar; iptalde kısmi başarı yayımlamaz.

## İncelenen mevcut GOKWORKS altyapısı

- `main.py`: GUI, mevcut ayrı süreç bayrakları ve `--self-check` girişi.
- `gui_qt/app.py` / `pages.py`: 17 mevcut menü sayfası, `PageRegistry`
  üzerinden tembel yükleme. Belt motoru bu aşamada menüye kaydedilmedi.
- `gui_qt/workers.py`: ortak, sıralı `JobManager`; sayfa ana iş parçacığında
  olay gruplarını alır, `EventSink` ile sınırlı paketler iletilir.
- `gui_qt/theme.py` / `components.py`: Qt Widgets tasarım sistemi,
  semantik renkler ve ortak form/çalışma alanı bileşenleri.
- `gear_calculator`: saf modeller/doğrulama, analitik geometri, geçerli OCP
  katıları, STEP yeniden okuma, DXF, JSON, ayrı CAD süreci ve hareket görünümü.
  Dişli veya sprocket özel iç API'leri yeni motora bağlanmadı/değiştirilmedi.
- `shaft_generator/bridge.py`: C# STA köprüsü, hazır olma/proses kimliği
  protokolü; mil işlemlerine özgü sözleşme genel kasnak API'si sayılmadı.
- `solidworks/`: COM bağlantısı ve oturum güvenliği. Belt motorunda import yok.
- `dfm_analyzer`: mevcut ve menüye bağlıdır; desteklenmeyen ölçümlerde açık
  `NOT_EVALUATED` yaklaşımı korunur. DFM kuralları değiştirilmedi.
- `shared/`: gelecek dosya yayımlarında ortak atomik yazım kullanılabilir.
- `packaging/`: PyInstaller kaynak/hidden-import listeleri ve Windows test
  çalıştırıcısı. Henüz yeni sayfa/veri kaynağı olmadığı için değiştirilmedi.
- `.github/workflows/`: mevcut testli agent PR/merge otomasyonu korunur.

`docs/GOKWORKS_ARCHITECTURE.md` 2 Kasım tarihli tarihsel özettir; 16 modül
ve otomatik teknik resmin yokluğu gibi ifadeler güncel kodla uyuşmaz.
4 Kasım tabanı `0513196` içindeki 17 sayfa, DFM ve mil teknik resim kodu
esas alındı. Ortak mimari belgesi ve AGENTS.md bu görevde değiştirilmedi.

## Aşama 2 — Qt çalışma alanı (henüz uygulanmadı)

`modules/belt_drive/ui.py` kendi sayfasını oluşturmalı. Yalnız o aşamada
`app.py` PAGE_TYPES/MODULES içine “Makine elemanları → Kayış–Kasnak Tasarımı”
kaydı ve gerekli paket denetimi eklenmeli. Diğer sayfalar yeniden tasarlanmamalı.

Sol form aileye göre datum çapı veya diş sayısı/adım göstermeli. Güç/tork ve
C/uzunluk modları karşılıklı dışlayan girişler olmalı. `CalculationReport`
aynen sonuç tablosuna taşınmalı; `NOT_EVALUATED` yeşil onay sayılmamalı.
Geçersiz girişten sonra eski sonucun güncelmiş gibi sunulması önlenmeli.

Merkez görünümü `BeltPath` çizgi/yaylarını Qt koordinatına (`+Y` dönüşümü)
çevirmeli. Sürükleme `path_between_centers` ile C ve eksen açısını
güncellemeli. Elips/spline tahmini eklenmemeli. Saat yönünde yol mesafesi
`s=v·1000·t·speed_scale` mm; CCW için işaret tersidir. İki kasnak aynı yönde,
`ω₂=ω₁/i` dönmeli. Zaman duvar saatiyle ölçülmeli; kare sayısıyla fiziksel
devir değiştirilmemeli. Bu yalnız nominal kinematik gösterim olacaktır.

Uzun işler mevcut `JobManager.start(owner, calculation_job(...))` üzerinden
yürümeli. İptal/çıkışta iş bitmeden Qt nesneleri silinmemeli. Proje kaydı
mevcut atomik dosya yardımcılarını ve açık üzerine yazma kararını kullanmalı.

## Aşama 3 — doğrulanmış üretici adaptörleri (henüz uygulanmadı)

Mevcut `LengthCatalog` üretici onayı veremez; bu ayrımı koruyun. Ayrı bir
rating veri sözleşmesi üretici/seri/belge/sayfa/revizyon/birim/referans
çapı-geçerlilik aralığı/izin verilen enterpolasyon/kanıt bilgisi taşımalı.
Yüklenen bir kaynağın kendini “verified” ilan etmesi yeterli değildir.

Güç tablosu, çap/hız, sarılma ve uzunluk düzeltmeleri ile servis faktörleri
aynı üretici yöntemine ait olmalı. Tablo dışına ekstrapolasyon yapılmamalı.
Kayış adedi, germe prosedürü ve izin verilen yükler ayrı doğrulanmalı.
Matematiksel nominal sonuç, listelenen boyut ve doğrulanmış güç kapasitesi
ayrı statüler olarak kalmalı. Test kaynağı olan sentetik boyutlar üretici
ürün kataloğuna taşınmamalı.

## Aşama 4 — gerçek B-Rep / DXF / rapor (henüz uygulanmadı)

`cad/` ancak gerçek geometri uygulandığında eklenmeli; boş çalışan düğme
veya silindirden “imalata uygun dişli kasnak” oluşturulmamalı. Doğrulanmış
kanal/diş boşluğu verileri lisans, tolerans ve profil ailesiyle saklanmalı.
HTD, T, AT ve üretici GT geometrileri ayrı tutulmalı.

Mevcut OCP bağımlılığı kullanılabilir; CadQuery/build123d zorunlu yeni
bağımlılık olarak eklenmedi. CAD işi ayrı süreçte, sürümlü JSON ve süre/iptal
sınırıyla yürümeli. Dişli servisinin davranışını değiştirmeden süreç
deseni örnek alınmalı; gerekirse kararlı ortak yardımcı ayrıca tartışılmalı.

Her parça tek geçerli katı, pozitif hacim ve gerçek delik/kama boşluğu
kontrolü geçmeli. STEP yeniden okunarak katı sayısı, hacim ve sınır kutusu
karşılaştırılmalı. İki kasnak ayrı katılar kalmalı. DXF mm birimi ve kapalı
konturlar doğrulanmalı. Güzergâh doğrulaması kayışın 3D kesit/süpürme
geometrisinin doğrulandığı anlamına gelmez. PDF/Excel aynı sonuç, varsayım,
kaynak ve destek sınırlarını raporlamalı.

## Aşama 5–6 — SolidWorks ve genişletme (henüz uygulanmadı)

SolidWorks kasnağı için yeni güvenli C# STA host gerekirse kendi işlemleri
ve sözleşmesi olmalı. Kullanıcının aktif belgesi/konfigürasyonu, belge
sahipliği ve COM ömrü korunmalı. İlk sürüm yalnız yeni parça oluşturmalı;
kullanıcının mevcut parça/montajına kör güncelleme yapmamalı. Özellik ağacı
ve yeniden açılan kayıt Windows + gerçek SolidWorks ile doğrulanmadan
parametrik SLDPRT başarı iddiası yapılmamalı. SLDASM ve mate'ler sonraki adımdır.

Çapraz, gergili/çok kasnaklı, çok kademeli ve Poly-V sistemler bu motorun
iki kasnaklı çözümüne sessizce indirgenmemeli. Yeni topoloji ve doğrulanmış
üretici yöntemleri ayrı modellerle genişletilmeli.

## Ajanlar arası çakışma sınırı

Bu görev yalnız `modules/belt_drive/` altında yeni dosya ekler. Ortak dosya,
bağımlılık ve eski motor değişikliği yoktur. Aşama 2'de `gui_qt/app.py`,
paket kontrolü ve `packaging/build_windows.py`; Aşama 4–5'te giriş noktası ve
CAD köprüleri paylaşılacağından güncel Claude/Codex farkları tekrar okunmalı.
Ana worktree'deki komitlenmemiş mil teknik resim taslakları taşınmamalı.
