# GOKWORKS performans analizi ve optimizasyon raporu

Tarih: 30 Ekim 2026 (Türkiye). Referans kaynak: `b4bb870eeebad6c91f526737158dc58f9c5e4e3a`.
Optimize edilen kaynak: `393ef067f63765cf4a74249c9056aa7b8f466dfe`.

## Kapsam ve yöntem

Uygulama Python + PySide6 **Qt Widgets** kullanır. Giriş `main.py`, ana kabuk
`gui_qt/app.py`, seri iş yöneticisi `gui_qt/workers.py` ve kalıcı ayarlar
`gui_qt/settings.py` içindedir. Web arayüzü veya yeni GUI framework'ü eklenmedi.
16 modülün kaynak/import yapısı tarandı; ana veri/işçi yolları ve tüm ekranlara
geçiş incelendi. Hesaplama formülleri, NFP arama algoritması, kesim boşlukları,
döndürme kuralları, proje şemaları ve arayüz yerleşimi korunmuştur.

Başlangıç tam test paketi ayrı, değiştirilmeyen `/tmp/gokworks-perf-baseline`
git worktree'sinde çalıştırıldı. Güncel tam paket ana çalışma kopyasında
çalıştırıldı. Ölçüm ve test raporları kaynak dosyalarından ayrı tutuldu.

Ölçümler `time.perf_counter`, `time.process_time`, cProfile ve isteğe bağlı
tracemalloc kullanır. RAM/disk sayaçları Linux'ta `/proc/self/status` ve
`/proc/self/io`, Windows'ta `GetProcessMemoryInfo`/`GetProcessIoCounters`
üzerinden okunur; yeni psutil veya başka bağımlılık eklenmedi.

**Taze süreç ile OS-soğuk açılış aynı şey değildir.** OS dosya önbelleği
boşaltılmadı. Kaynak uygulamanın art arda taze süreç açılışları ölçüldü;
aynı süreçte tekrar modül geçişleri ayrıca ölçüldü. Linux `offscreen` ve
Windows yerel Qt ölçümleri ayrı değerlendirilir. Süre karşılaştırmalarında
cProfile/tracemalloc kapalıdır; profil ve Python heap ölçümleri ayrı koşulardır.
Bir örnek veya tek makine sonucu başka kullanıcı donanımı için garanti değildir.

## Başlangıç bulguları ve öncelikler

| Öncelik | Ölçülen / incelenen sorun | Karar |
|---|---|---|
| Yüksek | Ana pencere 16 modülü ve 3.275 widget'ı ilk açılışta oluşturuyordu; ilk cProfile koşusunda yaklaşık 0,4 sn yalnız `QApplication.setStyleSheet` harcandı. | Kullanılmayan ekranların importu ve oluşturulması ilk erişime ertelendi. |
| Yüksek | PDF ekranı dahi ortak servis importları nedeniyle DXF/NumPy/diğer mühendislik modüllerini yüklüyordu. | DXF/PDF servis uygulamaları yalnız ilgili servis çağrıldığında import edilir. |
| Yüksek | 800 yerleşmiş örneğin maliyet/denetim hesabında yaklaşık 5.400 geometri çözümleme çağrısı; yerleşim döngülerinde yeniden ID kümeleri ve doğrusal nesne aramaları. | Hesaplamaya özel ölçü önbelleği ve yerel ID sözlükleri. |
| Yüksek | 150 bağımsız konturlu DXF'te 22.500 aynı sınır bandı oluşturma çağrısı; konturların tüm çiftleriyle karşılaştırma. | Mevcut STRtree ile kesin aday daraltma; sınır bandı kontur başına bir kez. |
| Düşük | 3.000 dosyalı görünümde 1.000 sonuç bildirimi yaklaşık 0,36 sn (profil açık); model zaten QTableView ve sanal Qt modelleri kullanıyor. | Görünümün/sinyallerin yeniden yazılması gerekçelendirilmedi; mevcut model ve filtreler korundu. |
| Canlı ölçüm gerekli | SolidWorks belge açma/konfigürasyon, rebuild ve dışa aktarma maliyetleri. | Lisanslı SolidWorks olmadan API çağrısı silinmedi veya CAD durumu için yeni cache eklenmedi. |

Profil süreleri darboğazı belirleme içindir; aşağıdaki performans yüzdelerinde
bu profilli koşular kullanılmaz.

## Uygulanan değişiklikler

### Başlangıç, RAM ve modül yaşam döngüsü

- `gui_qt/pages.py` içindeki `PageRegistry`, bütün modül anahtarlarını koruyan
  bir Mapping'dir. Üyelik/anahtar iterasyonu ekran oluşturmaz; açık `pages[key]`
  erişimi ekranı oluşturur ve daha sonra aynı örneği döndürür. Açık
  `dict(pages)`/`values()` erişimleri geriye uyumlu şekilde ekranları yükler.
- Kabuk iç işlemleri `loaded_values()`/`peek()` kullanır. Tema değiştirme,
  durum gösterme ve kapanış gizli ekranları istemeden oluşturmaz.
- Kullanıcının kaydedilmiş başlangıç ekranı açılışta hazırlanır; yalnız PDF
  varsayılmadı. İlk açılışta widget sayısı **195** oldu (PDF başlangıcı).
- İlk kullanılan ekranda import/oluşturma maliyeti vardır. Sonraki geçişler
  aynı widget ve kullanıcı girdilerini korur. Sık kullanılan modül başlangıç
  tercihi ise ilk pencereyle birlikte hazırdır; arka planda gizli ekranları
  yeniden oluşturan bir polling döngüsü eklenmedi.
- Tema, komut ikonları ve Inspector ilk erişimde uygulanır. Başka bir iş
  sürerken oluşturulan Inspector aynı CAD iş kilidine uyar. İş sahibi,
  iptal/ilerleme sinyalleri ve kapanış bekleme koşulları değişmedi.
- `from gui_qt.app import PdfPage` gibi açık eski sınıf importları modül
  `__getattr__` üzerinden korunur. `pages`'in somut türüne `dict` diye güvenen
  dış eklentiler Mapping arayüzünü kullanmalıdır.
- `packaging/hooks/hook-gui_qt.app.py`, deklaratif 16 ekran kataloğunu AST ile
  okuyup hepsini PyInstaller hidden-import listesine ekler. Hook çalışırken Qt
  import edilmez. Onefile/onedir kaynak ve lisans yolları değiştirilmedi.

### Nesting maliyet ve bağımsız doğrulama

- `accounting.calculate()` içinde geometri, alan, çevre, delik sayısı ve
  sınırlar her kullanılan parça için bir kez çözülür. Önbellek sadece o
  çağrıya aittir; yeni hesapta geometri, kalınlık ve fiyat değişiklikleri tekrar
  okunur. Küresel/sınırsız cache yoktur.
- Parça/sac/malzeme aramaları yerel sözlüklerle yapılır. Parça özetleri için
  tüm sonuç satırları her parçaya tekrar taranmaz; oluşma sırası korunur.
- Decimal maliyet dağıtımı ve son parçaya kalan kuruşun verilmesi korunur.
- Bağımsız `validate_result()` ID kümelerini her örnekte tekrar kurmaz.
  Gerçek geometri, kenar payı, çakışma, mesafe, adet, stok ve izinli açı
  denetimleri kaldırılmadı; NFP önbelleği doğrulayıcıyla paylaşılmaz.

### DXF okuma

- 20.000 nokta sınırı aynı anlamla artan sayaç üzerinden kontrol edilir.
- Konturların değme/çakışma ve iç içe olma kontrolleri STRtree üzerinden aynı
  kesin `intersects`/`within` ilişkileriyle yapılır. Bounding box yalnız aday
  daraltır; yaklaşık geometriyle kabul kararı verilmez.
- Özgün DXF nesnelerinin parçaya atanmasında sınır bandı tek kez üretilir.
  Mekânsal sorgudan sonra eski kesin `difference(...).length` koşulu korunur.
  Çok kısa çizgilerin tarihsel kabul koşulu ayrıca korunur; sıra değişmez.
- Sınıflandırma ve kaynak nesnesi seçimi döngülerine iptal kontrol noktaları
  eklendi. Kaynak dosyayı iki kez doğrulama/hash koruması kaldırılmadı.

## Modül bazlı değerlendirme

| Modül | İncelenen yol / sonuç |
|---|---|
| PDF | Kaynak tarama, ayrı process worker, SaveAs3/geri dönüş ve atomik yayın. Servis importu ertelendi; CAD kayıt mantığı değiştirilmedi. |
| DXF/DWG | Seri işçi, geçici açınım, katlı geometri, bounded mesh cache ve kaynak/konfigürasyon/update-stamp doğrulaması. Cache doğruluğu korundu. |
| 3D dönüştürücü | `Session` STA yaşam döngüsü, belge sahipliği, ayarların geri yüklenmesi ve çıktı doğrulaması incelendi; canlı ölçüm olmadan COM çağrısı kaldırılmadı. |
| BOM | Örnek bazlı ağırlık okuyucu, kademeli ağaç/filtre ve isteğe bağlı görseller. Aynı dosya/konfigürasyondan iki montaj örneği farklı kütle taşıyabileceği için global ağırlık cache'i eklenmedi. |
| İsimlendirme | PackAndGo tarama, iptal ve dosya referansı doğrulaması. Güvenlik/doğrulama turları hız için atlanmadı. |
| K faktörü | Tarif ve kaynak okuma, asenkron uygulama, teknik çizim. Açılıştan kaldırıldı; formüller/uygulama kuralları aynı. |
| ISO geçmeler | Katalog ve vektörel çizim ilk açılan modüle kadar ertelenir; tablo verileri aynı. |
| GD&T | Katalog, filtre ve teknik çizimler ilk kullanımda; hesaplama kuralları aynı. |
| Tolerans yığılması | Manuel/Monte Carlo işçisi, dosya izleme ve raporlar incelendi; örnekleme sonucu/formülü değiştirilmedi. |
| Cıvata | Formüller ve çizim başlangıçta hazırlanmaz; ilk kullanım ve durum kalıcılığı test edildi. |
| Hızlı tork | Mevcut tek-atımlı güncelleme yaklaşımı korundu; tork/ön yük sonuçları değişmedi. |
| Ağırlık | Malzeme kütüphanesi ve çizimler ilk kullanımda; yoğunluk/alan birimleri aynı. |
| Nesting | DXF okuma, maliyet ve doğrulama iyileştirildi. NFP/yerleşim araması, toleranslar, kalite bütçesi ve sonuç fingerprint şeması değiştirilmedi. |
| Profil kesim | Best-fit/bounded exact arama zaten mevcut; Decimal stok korunumu ve kaynak veri modelleri değiştirilmedi. |
| Parametrik mil | Plan/snapshot ve ayrı C# köprüsü korundu. Geometri/operasyon doğrulaması değiştirilmedi. |
| Dişli | OCCT işlemleri ayrı process'te, animasyon kullanıcı başlatınca çalışıyor. İlk erişime erteleme dışında geometri/CAD worker algoritması aynı. |

## Ölçüm sonuçları

Üç tekrarlı dönüşümlü taze süreç ölçümlerinin medyanları aşağıdadır.
Her kökte aynı veri, aynı Python ve aynı Qt platformu kullanıldı. Yerel Linux
benchmark'ı iki tam test koşusu da bittikten sonra, başka doğrulama işçisi
çalışmıyorken yapıldı. Windows koşusunda da regresyon ile benchmark ardışıktır.

### Yerel Windows (GitHub Actions, gerçek Qt masaüstü)

| Ölçüm | Önce | Sonra | Azalma |
|---|---:|---:|---:|
| İlk pencere kullanılabilir | 1.235 sn | 0.250 sn | %79.8 |
| Açılış process CPU zamanı | 1.203 CPU sn | 0.219 CPU sn | %81.8 |
| 200 tip / 800 örnek maliyet ve doğrulama | 0.270 sn | 0.199 sn | %26.0 |
| 150 bağımsız konturlu DXF okuma | 1.409 sn | 0.511 sn | %63.7 |
| Aynı DXF, gerçek UI/JobManager üzerinden | 1.642 sn | 0.587 sn | %64.2 |
| İlk pencere resident RAM | 263.2 MiB | 93.6 MiB | %64.4 |

Windows boştaki CPU: **%1,53 → %1,55** (bir saniyelik örnek). Bu alanda
anlamlı iyileşme iddia edilmiyor. Sıcak modül geçişi medyanı **16,49 → 15,76 ms**;
bu küçük fark için genel bir hızlanma garantisi verilmez. DXF yüklenirken 10 ms
Qt heartbeat'in gözlenen en uzun aralığı **39,90 → 33,96 ms**. Bu, 150 konturlu
örnekte event loop'un çalışmaya devam ettiğini gösterir; her CAD dosyası için
gecikme üst sınırı değildir.

[Windows performans testi ve ham JSON artifact'ı](https://github.com/gkkizil/gokworks/actions/runs/41018351344).
Native iş akışı, önce/sonra maliyet ve DXF sonuç imzalarının altı ölçümün
tamamında aynı olduğunu ayrıca assert eder. Bütün örnek kaynak dosyaları
okuma öncesi/sonrası aynı kaldı.

### Linux, Qt offscreen (kaynak uygulama)

| Ölçüm | Önce | Sonra | Azalma |
|---|---:|---:|---:|
| İlk pencere kullanılabilir | 1.194 sn | 0.243 sn | %79.7 |
| Açılış process CPU zamanı | 1.577 sn | 0.244 sn | %84.5 |
| 800 örnek maliyet ve doğrulama | 0.338 sn | 0.259 sn | %23.5 |
| 150 konturlu DXF okuma | 1.875 sn | 0.636 sn | %66.1 |
| DXF, UI/JobManager üzerinden | 2.096 sn | 0.724 sn | %65.5 |
| İlk pencere resident RAM | 193.1 MiB | 77.4 MiB | %59.9 |

CPU zamanı process'in bütün native iş parçacıklarının toplamıdır; paralel native
başlatma nedeniyle duvar süresini aşabilir. Idle CPU **%0,74 → %0,63**; bu küçük
örnek de tek başına sürekli CPU kazanımı kanıtı değildir.

Sıcak geçiş medyanı **7,08 → 7,81 ms**, gözlenen en yavaş sıcak geçiş
**13,35 → 15,66 ms** oldu. Windows'ta ters yöndeki küçük değişimle birlikte
bakıldığında, sıcak geçişte tutarlı bir hızlanma iddia edilmiyor. Açılış kazanımı
esas olarak kullanılmayan ekranların işini ertelemekten geliyor.

### İlk modül geçişinin maliyeti ve bellek sınırı

Aşağıdaki ilk geçişler Linux'ta PDF başlangıcından sonra, katalogdaki sabit
sırayla ölçüldü; bunlar bağımsız modül-soğuk süreç ölçümleri değildir. Örneğin
DXF ilk erişimi paylaşılan DXF/NumPy import maliyetinin büyük kısmını taşır.

| Modül | İlk geçiş önce, ms | İlk geçiş sonra, ms |
|---|---:|---:|
| `pdf` | 1.66 | 1.56 |
| `dxf_dwg` | 12.81 | 348.40 |
| `cad_converter` | 12.41 | 96.77 |
| `bom` | 9.04 | 40.46 |
| `naming` | 10.05 | 55.19 |
| `k_factor` | 8.81 | 132.15 |
| `iso_fits` | 38.85 | 100.37 |
| `geometric_tolerances` | 52.04 | 102.16 |
| `tolerance_stack` | 18.86 | 117.67 |
| `bolt` | 35.62 | 84.79 |
| `bolt_torque` | 15.53 | 57.51 |
| `weight` | 28.09 | 60.36 |
| `nesting` | 11.21 | 190.39 |
| `profile_cutting` | 12.33 | 92.40 |
| `shaft_generator` | 9.95 | 155.15 |
| `gear_calculator` | 24.47 | 100.12 |

İlk erişim maliyetinin yükselmesi bilinçli ertelemenin karşılığıdır. Örneğin
PDF açılışı + ilk DXF geçişinin toplamı yaklaşık **1,207 → 0,591 sn**;
uygulamanın ilk kullanılabilirliğinde ve toplam bekleyişte kazanım vardır.
Sonraki erişimlerde import veya widget kurulumu tekrarlanmaz.

Bütün ekranlar bir kez açıldıktan sonraki RSS yaklaşık **196,8 → 194,5 MiB**;
yalnız açılışta görülen büyük RAM kazancı burada beklenmemelidir. Ardından
80 tekrar geçişte RSS artışı yaklaşık **0,16 / 0,18 MiB** (önce/sonra) oldu.
Bu sınırlı gözlemde sürekli büyüyen bir ekran cache'i görülmedi; uzun süreli
CAD bellek sızıntısı testi yapıldığı anlamına gelmez.

Ayrı tracemalloc koşusunda ilk pencere Python heap'i **59,9 → 12,2 MiB**,
80 geçişten sonraki heap **59,9 / 58,8 MiB** (önce/sonra) oldu. Native Qt/GEOS
belleği bu sayılara dahil değildir. Heap ve cProfile koşularının süreleri
karşılaştırma yüzdelerine dahil edilmedi.

### Disk erişimi

Linux'ta ilk pencereye kadar medyan mantıksal read syscall sayısı
**3.636 → 639**, write syscall sayısı **5.497 → 485** oldu. Bu sayaçlar kaynak,
Qt/resource, bytecode ve çıktı akışlarını birlikte kapsar; hepsini kullanıcı
dosyası yazımı veya gereksiz disk işlemi saymak doğru değildir. İki sürümde de
ölçülen fiziksel `read_bytes`/`write_bytes` farkı **0** idi (önbellekli ortam).
Fiziksel disk I/O yüzdesi kazancı veya OS-soğuk disk testi iddia edilmiyor.

## Test sonuçları

| Koşu | Toplanan pytest testi | Geçen normal test | Geçen ilave unittest alt testi | Atlanan | Hata/başarısız |
|---|---:|---:|---:|---:|---:|
| Referans tam paket, Linux | 2.089 | 2.029 | 885 | 60 | 0 |
| Güncel tam paket, Linux | 2.100 | 2.040 | 885 | 60 | 0 |

JUnit toplamı referansta **2.974**, güncelde **2.985** vakadır; alt testlerin
ayrı kaydedilmesi nedeniyle pytest toplama sayısından büyüktür. Toplamı
benzersiz test fonksiyonu sayısı gibi yorumlamayın. Yeni 11 regresyonun tamamı
geçti. Her native test sürecinin çıkış kodu 0'dır; başarısız süreç atlanmadı.

Atlanan 60 testin 45'i canlı/opt-in SolidWorks belgesi veya açık CAD oturumu,
14'ü Windows/PowerShell/interop/pywin32/native desktop koşulları, 1'i ayrıca
opt-in isteyen analizli kopya işlemi içindir. Bu kontroller Linux'ta çalışmış
sayılmamıştır. Windows koşuları aşağıdaki seçili kapsamları ayrıca doğruladı;
bütün 60 atlamanın Windows'ta kapandığı iddia edilmiyor.

- [Windows performans / kabuk regresyonu](https://github.com/gkkizil/gokworks/actions/runs/41018351344):
  **183 test, 0 hata, 0 atlama**. Tüm modüller, iki tema, ayarlar, işçi/iptal,
  kaynak temizliği, tembel import, paketleme hook sözleşmesi ve responsive gezinme.
  Üç tekrarlı gerçek Windows benchmark'ı ve tam kaynak uygulama `--self-check`
  başarılı. Self-check yerel OCCT CAD worker'ını da çalıştırır; SolidWorks değildir.
- [Bağımsız Windows Nesting regresyonu](https://github.com/gkkizil/gokworks/actions/runs/41018351346):
  **282 test, 0 hata, 0 atlama**. Geometri, dosya adı algılama, gerçek DXF,
  kalınlık/adet, maliyet, raporlar, çalışma alanı ve yeni performans regresyonları.
  %125 ve %150 yerel Qt ölçek kontrolleri ile tam uygulama self-check başarılı.
- Python tanımsız isim denetimi (`ruff F821/F822/F823`) ve `git diff --check`
  başarılı. Geniş test paketi PDF/Excel/DXF okuma, formül, dosya güvenliği,
  konfigürasyon/COM mock sözleşmeleri ve dişli OCCT geometri testlerini de içerir.
- 150 konturlu sabit kaynak probe'unda önce/sonra parça geometrileri, adetler,
  toplam alan ve kaynak SHA256 birebir eşleşti. Tekrarlı benchmark'ta DXF ve
  maliyet çıktı SHA256 imzaları her iki kaynakta bütün tekrarlarda eşleşti.
- Kaynak DXF dosyaları değiştirilmedi. Genel PDF/STEP dosyalarının byte-byte
  eşitliği, canlı CAD çalıştırılması veya yeni frozen EXE kabulü iddia edilmiyor.

Ham yerel kanıtlar: `/tmp/gokworks-performance-final.json`,
`/tmp/gokworks-startup-baseline-heap.json`, `/tmp/gokworks-startup-current-heap.json`,
`/tmp/gokworks-perf-baseline/windows-tests.xml`, ana kopyadaki `windows-tests.xml`.
Kalıcı paylaşım için yukarıdaki Windows CI artifact'ları kullanılabilir.
Üretilmiş JSON/log/PNG/EXE dosyaları Git deposuna eklenmedi.

## Tekrarlama komutları

Ayrı referans kopyası oluşturup aynı Python/Qt/GEOS sürümleriyle çalıştırın:

```bash
git worktree add --detach /tmp/gokworks-perf-baseline b4bb870
QT_QPA_PLATFORM=offscreen python packaging/benchmark_performance.py \
  --baseline /tmp/gokworks-perf-baseline --repeat 3 \
  --output /tmp/gokworks-performance.json
python packaging/benchmark_performance.py --worker startup --root . \
  --output /tmp/startup-profile.json --profile /tmp/startup.pstats
python packaging/benchmark_performance.py --worker startup --root . \
  --output /tmp/startup-heap.json --trace
python packaging/run_windows_tests.py
```

Windows'ta `QT_QPA_PLATFORM=windows` veya yerel varsayılan kullanılır; dosya
konumları uygun Windows yollarıyla değiştirilir. `.github/workflows/windows-performance.yml`
aynı referans commit ile üç dönüşümlü taze süreç ölçümünü yerel Windows Qt'da
çalıştırır; JSON/test/açılış kanıtları artifact olarak saklanır. Benchmark
proje ayarlarını kullanıcının klasöründe değil geçici klasörde oluşturur.

## Değiştirilen dosyalar

- `gui_qt/app.py`: modül import/oluşturma, tema, durum ve kapanışta tembel erişim.
- `gui_qt/pages.py` (yeni): Mapping uyumlu ekran yaşam döngüsü.
- `gui_qt/services.py`, `gui_qt/export.py`: servis uygulamasını çağrıda yükleme.
- `modules/nesting/accounting.py`: yerel geometri ölçüleri ve ID/özet dizinleri.
- `modules/nesting/validation.py`: her çağrıya ait ID dizinleri.
- `modules/nesting/dxf_import.py`: aynı kesin kurallarla mekânsal aday daraltma.
- `tests/test_lazy_pages_gui.py` (yeni): 7 başlangıç/lifecycle/paketleme regresyonu.
- `modules/nesting/tests/test_performance_regressions.py` (yeni): 4 hesap,
  cache geçersizleştirme, iç içe kontur, değme ve kısa çizgi regresyonu.
- `packaging/benchmark_performance.py` (yeni): tekrarlanabilir ölçüm aracı.
- `packaging/hooks/hook-gui_qt.app.py` (yeni): ertelenmiş modülleri paketleme.
- `.github/workflows/windows-performance.yml` (yeni): yerel Windows doğrulaması.
- `PERFORMANS_OPTIMIZASYON_RAPORU.md` (yeni): bu rapor.

## Sınırlar ve sonraki adımlar

- Gerçek SOLIDWORKS kurulumu/lisansı ve kullanıcının büyük montaj dosyaları bu
  Linux ortamında bulunmuyor. COM/BOM/PackAndGo/PDF/DWG/STEP için canlı süre,
  canlı bellek kaçağı ve CAD çıktısının yeni sürümde byte karşılaştırması
  ölçülmedi. Mock/protokol testleri canlı CAD testi olarak sayılmaz.
- Açılışta kullanıcı tercih edilen modülün maliyetini öder; diğer modüllerin
  ilk erişimi import/kurulum gerektirir. Sonraki erişim aynı örneği kullanır.
  Bütün ekranlar açıldıktan sonraki RAM'in tümü ilk açılış tasarrufu kadar düşmez.
- Kaynak ölçümleri tek EXE'nin açılma/çıkartılma süresi değildir. Bu görevde EXE
  üretilmedi; PyInstaller hook kataloğu ve mevcut build sözleşmeleri test edilir.
  Sonraki açık paketleme isteğinde frozen smoke kontrolleri ayrıca çalışmalıdır.
- Bir saniyelik idle CPU ve 80 tekrar geçiş, uzun süreli CAD bellek sızıntısı
  testi değildir. Python heap, Qt/GEOS/OCCT native belleğinin tamamını göstermez.
- İptal işbirliklidir. Tek bir yerel GEOS veya SolidWorks çağrısını ortasından
  zorla kesme eklenmedi; yeni kontrol noktaları çağrılar arasındadır.
- Sonraki ölçüm yerel Windows'ta aynı büyük montajla belge açma, rebuild,
  önizleme cache isabeti ve çıktı sürelerini ayırmalıdır. Özellikle konfigürasyon
  veya montaj örneği farkını yutan path-only/global CAD cache'i kullanılmamalıdır.
