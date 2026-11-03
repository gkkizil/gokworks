# GOKWORKS kalite güvence raporu · 3 Kasım 2026

Kapsam: depodaki 16 modülün tamamı ve ortak altyapı (ana pencere, iş yöneticisi,
ayarlar, tema, rapor yazıcıları). Test ortamı: Linux bulut kapsayıcısı, Python
3.13, PySide6 6.10.3 (offscreen). Windows CI iş akışları ayrıca GitHub Actions'ta
koşar. **Bu ortamda SOLIDWORKS yoktur**; SOLIDWORKS testleri aşağıda
"Çalıştırılamayan" olarak ayrı gösterilir ve başarılı sayılmamıştır.

Başlangıç sürümü `bfa16ce`, bitiş sürümü `6d15c76` (ve bu rapor).

## A. Genel durum

| Ölçüt | Değer |
|---|---|
| Tespit edilen modül | 16 (+ ortak altyapı) |
| Test edilen modül | 16 / 16 |
| Toplam otomatik test | **2575** (+ 812 alt test) |
| Başarılı (PASS) | **2506** |
| Başarısız (FAIL) | **0** |
| Çalıştırılamayan (NOT RUN) | **69**, hepsi Windows / canlı SOLIDWORKS / ODA gerektiriyor |
| Bu çalışmada eklenen test | 64 (8 dosya) |
| Bulunan ve düzeltilen hata | 6 (P1: 1, P2: 3, P3: 2) |

Test sayıları `python -m pytest -q -rsfE` tam koşusundan alınmıştır. Testleri
geçirmek için hiçbir test silinmedi, atlanmadı veya zayıflatılmadı.

### Otomatik test dışı doğrulamalar (bu çalışmada yapılan)

| Doğrulama | Ne yapıldı | Sonuç |
|---|---|---|
| Profil kesim optimumu | 400 rastgele (sabit seed) kesim listesi, bağımsız tam arama ile minimum çubuk sayısı | 400/400 eşit |
| Nesting geometrisi | 18 senaryo (halka, delikli çerçeve, L/T, düzensiz çokgen; 4 saca kadar, 52 parça) motorun doğrulayıcısı kullanılmadan shapely ile yeniden kontrol | çakışma, aralık ihlali, kenar taşması: 0 |
| ISO 286 geçmeleri | 12 tablo değeri (H7, g6, k6, p6, H11, f7, s6, js6, F8, h9, N7) | 12/12 eşleşti |
| DIN 6885 / DIN 471 | Kama ve segman kanalı tabloları standartla karşılaştırıldı | eşleşti |
| Dişli formülleri | Düz, helisel, iç, planet, konik, sonsuz vida, sikloid ve zincir dişlisi formülleri ISO 21771 / ISO 606 bağıntılarıyla satır satır incelendi | hata yok |
| Cıvata / tork | As, d₃, Sp ve Rp0,2 (ISO 898-1) değerleri, T = K·F·d | hata yok |
| K faktörü | BA = θ(r + k·t), BD = 2(r+t)·tan(θ/2) − BA | hata yok |
| GUI fuzz | 16 sayfa × tüm sekmeler: 17 düşmanca değer (boş, negatif, 1e308, nan, inf, `1.000`, Türkçe karakter, 80 hane) ve Hesapla düğmeleri | yakalanmamış hata 0 |
| Ekran / ölçek | 1366×768, 1920×1080, 2560×1440 × %100/125/150, 16 sayfa: kesik metin ve pencere dışı kontrol taraması | 1 kusur bulundu ve düzeltildi |
| Bozuk ayar dosyası | 8 ham bozulma ve 41 anahtar × 6–11 yanlış tür | 2 hata bulundu ve düzeltildi |
| Bozuk dosyalar | Boş, rastgele, kesik ve NaN içerikli DXF, STEP, STL, IGES ve Parasolid; Türkçe/özel karakterli yol | güvenli red; 1 mesaj düzeltildi |

## B. Modül bazında sonuçlar

| Modül | Test | Başarılı | Başarısız | Çalıştırılamayan | Durum |
|---|---:|---:|---:|---:|---|
| PDF aktarımı | 64 | 61 | 0 | 3 | PASS (Windows COM kısmı NOT RUN) |
| DXF / DWG | 309 | 303 | 0 | 6 | PASS (canlı SOLIDWORKS NOT RUN) |
| 3D Dönüştürücü | 166 | 165 | 0 | 1 | PASS (canlı aktarım NOT RUN) |
| BOM · Ürün ağacı | 62 | 61 | 0 | 1 | PASS (canlı NOT RUN) |
| İsimlendirme | 71 | 69 | 0 | 2 | PASS (Pack and Go NOT RUN) |
| K faktörü / yarıçap | 161 | 161 | 0 | 0 | PASS |
| ISO geçme toleransları | 39 | 39 | 0 | 0 | PASS |
| Geometrik toleranslar | 14 | 14 | 0 | 0 | PASS (1 hata düzeltildi) |
| Tolerans yığılması | 144 | 142 | 0 | 2 | PASS (1 kusur düzeltildi) |
| Cıvata hesabı | 18 | 18 | 0 | 0 | PASS |
| Hızlı tork | 77 | 77 | 0 | 0 | PASS |
| Ağırlık hesabı | 108 | 108 | 0 | 0 | PASS |
| Nesting | 309 | 308 | 0 | 1 | PASS (gerçek DWG/ODA NOT RUN) |
| Profil kesim | 120 | 119 | 0 | 1 | PASS (Weldment NOT RUN) |
| Parametrik mil | 311 | 262 | 0 | 49 | Hesap/plan PASS · **SOLIDWORKS modelleme NOT RUN** |
| Dişli hesaplama | 246 | 246 | 0 | 0 | PASS (STEP/DXF gerçek OCCT ile) |
| Ortak altyapı ve GUI (`tests/`) | 356 | 353 | 0 | 3 | PASS (1 P1 düzeltildi) |
| **Toplam** | **2575** | **2506** | **0** | **69** | |

## C. Tespit edilen hatalar

| # | Öncelik | Modül | Hata | Kök neden | Düzeltme | Tekrar test |
|---|---|---|---|---|---|---|
| 1 | **P1** | Ortak iş yöneticisi (tüm modüllerin arka plan işleri) | Arka plan işi biterken arayüz kilitlenebiliyordu ("Yanıt vermiyor"). Tam test paketi bir profil kesim sekmesi değişiminde takılınca bulundu. | `JobWorker` kendi QThread'inde `deleteLater` ile siliniyordu. `~QObject` Qt sinyal kilidini tutarken PySide GIL istiyor; aynı anda GUI iş parçacığı GIL'i tutup `connect()` içinde aynı kilidi bekliyordu (ABBA). | Worker iş bitince GUI iş parçacığına taşınıyor; native iş parçacığı kapandıktan sonra orada siliniyor (`gui_qt/workers.py`). | Eski kod: 600 işlik stres testi kilitlendi. Yeni kod: ~7 sn'de PASS ve tüm worker'lar GUI iş parçacığında siliniyor (`tests/test_qa_job_worker_deadlock.py`). |
| 2 | P2 | Ayarlar | `settings.json` içinde `NaN` varsa her çıkışta "Ayarlar kaydedilemedi" uyarısı çıkıyor, ayarlar bir daha kaydedilmiyordu. | `json.loads` NaN'ı kabul ediyor, `save_settings` ise `allow_nan=False` ile reddediyor. | NaN/Infinity içeren dosya bozuk sayılıyor: `settings.invalid-*.json` olarak yedekleniyor, temiz ayarla devam ediliyor. | `tests/test_qa_damaged_settings.py` PASS (düzeltmesiz FAIL) |
| 3 | P2 | Geometrik toleranslar (ayrıca bağımsız dişli penceresi) | Ayar dosyasında `gdt_kind` liste/sözlük olursa sayfa açılmıyordu (`unhashable type`). | Ayar değeri tür kontrolü olmadan sözlük anahtarı olarak kullanılıyordu. | Metin olmayan değer varsayılana düşüyor. | Aynı test, 41 anahtar × 6 tür: PASS |
| 4 | P2 | CSV raporları (hesap sayfaları, aktarım günlüğü, DXF sac listesi) | Yazma yarıda kesilirse (disk dolu, dosya kilitli) kullanıcının var olan dosyası yarım/bozuk kalıyordu. | Hedef dosyaya doğrudan `open('w')` ile yazılıyordu. | `shared/files.write_csv_atomic`: geçici dosyaya yaz, tamamlanınca yerine koy. | `tests/test_qa_atomic_reports.py` PASS: hata anında eski dosya korunuyor, geçici dosya kalmıyor. |
| 5 | P3 | Nesting DXF içe aktarma | Boş veya bozuk DXF dosyasında kullanıcı İngilizce `is not a DXF file` görüyordu. | ezdxf'in ham hata metni olduğu gibi gösteriliyordu. | Türkçe, dosya adlı ve yönlendirici mesaj. Eksik dosya `FileNotFoundError` olarak kalıyor. | `test_dxf_open_errors.py` PASS |
| 6 | P3 | Tolerans yığılması | "+ / −" düğme metni her ölçekte 5 px kesiliyordu. | Genişlik yalnız fonttan hesaplanıyor, tema dolgusu hesaba katılmıyordu. | Genişlik `sizeHint` ile hesaplanıyor. | `test_qa_no_clipped_text.py` PASS (düzeltmesiz FAIL); 3 çözünürlük × 3 ölçekte 0 kusur |

Düzeltme gerektirmeyen notlar:

- **Nesting NFP:** Motor, dejenere köşelerde shapely'den "invalid value in buffer" uyarısı alabiliyor. Her aday konum ayrıca tam kesişim ve mesafe kontrolünden (`engine.py:213`) ve sonunda `validate_result`'tan geçtiği için yanlış yerleşim üretemez.
- **Profil kesim:** Testere payı her parçaya uygulanıyor (README'de belgeli). Örneğin 6000 mm stoktan tam 6000 mm parça "sığmıyor" sonucunu veriyor. Muhafazakâr bir model; değiştirilmedi, kullanıcı kararı.
- **Nesting dosya adı okuma:** `x4` ve `Q12` gibi adet yazımları tanınmıyor. Bu durumda "Kısmen algılandı" diye uyarıyor, sessizce yanlış değer kullanmıyor.

## D. Performans

Aynı makinede, `packaging/benchmark_performance.py --repeat 3` (taze süreç):

| Ölçüm | Önce (`bfa16ce`) | Sonra |
|---|---|---|
| Açılışta hazır olma (medyan) | 0,31 sn | 0,38 sn* |
| Tüm modüller açıkken bellek | 214,6 MB | 214,4 MB |
| Boşta işlemci | %0,3 | %0,3 |
| Maliyet hesabı | 0,26–0,34 sn | 0,28–0,32 sn |
| DXF okuma | 0,71–0,84 sn | 0,74–0,79 sn |
| İlk açılış: DXF/DWG · Mil sayfası | 0,49 · 0,44 sn | 0,50 · 0,46 sn |

\* "Sonra" ölçümü, aynı anda bir ayar fuzz testi çalışırken alındı. Düzeltmeler
açılış yolunu değiştirmiyor; fark ölçüm gürültüsü sınırında.

Ek ölçümler (`bfa16ce` öz denetim ve stres testi):

- 50 bin satırlık tablo 118–140 ms'de yükleniyor.
- 300 hesap döngüsü, 10 tema değişimi ve 2000 satırlık DXF tablosu birlikte 41 sn sürdü; bellek 216 → 236 MB.
- Sayfalar arasında tekrar tekrar gezinmede bellek artışı 0,26 MB.
- Kapatılan ana pencereler tamamen bırakılıyor: 4 turda canlı widget sayısı 0.

## E. Kod değişiklikleri

| Commit | Dosyalar | Açıklama |
|---|---|---|
| `d62894d` | `shared/files.py` (yeni), `gui_qt/calculations.py`, `gui_qt/components.py`, `modules/dxf_dwg/ui.py`, `modules/nesting/dxf_import.py`, `modules/tolerance_stack/ui.py` | Atomik CSV, Türkçe DXF hataları, kesik düğme |
| `b324b33` | `gui_qt/workers.py` | P1 kilitlenme düzeltmesi |
| `6d15c76` | `shared/settings.py`, `gui_qt/settings.py`, `modules/geometric_tolerances/ui.py`, `modules/gear_calculator/__main__.py` | Bozuk ayar dayanıklılığı |

Eklenen testler:

- `tests/test_qa_all_pages_hostile_inputs.py`: 16 sayfa, tüm sekmeler, düşmanca değerler.
- `tests/test_qa_no_clipped_text.py`: 1366×768 ve 1920×1080.
- `tests/test_qa_job_worker_deadlock.py`: alt süreçte stres testi.
- `tests/test_qa_damaged_settings.py`: 15 senaryo.
- `tests/test_qa_atomic_reports.py`
- `modules/nesting/tests/test_dxf_open_errors.py`
- `modules/nesting/tests/test_independent_geometry_oracle.py`: sabit seed.
- `modules/profile_cutting/tests/test_optimizer_exhaustive_oracle.py`: sabit seed, 150 senaryo.

Yeni bağımlılık eklenmedi. Mimari değiştirilmedi.

## F. Kalan riskler ve çalıştırılamayan testler

1. **SOLIDWORKS entegrasyonu (kritik kapsam), NOT RUN.** Bu ortamda SOLIDWORKS yok. Aşağıdakiler yalnızca sahte (mock) COM nesneleriyle ve Windows CI'da derleme/sözleşme düzeyinde doğrulandı:
   - COM bağlantısı, parça/montaj/teknik resim oluşturma, sketch/extrude/revolve
   - FeatureManager, rebuild, kaydetme
   - STEP/DXF/DWG dışa aktarma

   Bunlar gerçek entegrasyon testi sayılmamıştır. Canlı testler hazırdır ve atlanmıştır: mil 38, DXF/DWG 3, PDF, BOM, 3D Dönüştürücü, Profil kesim, İsimlendirme ve Tolerans yığılmasında birer tane. Açmak için Windows'ta SOLIDWORKS açıkken ilgili ortam değişkeni ayarlanır (`GOKWORKS_SHAFT_LIVE=1`, `GOKWORKS_SHAFT_DRAWING_LIVE=1`, `GOKWORKS_CAD_LIVE_SOURCE=…` vb.).
2. **SOLIDWORKS geometri doğruluğu.** Mil modelinin hacim/boyut kontrolü (`volume_reference.py` ile bağımsız integral) canlı testlerin içinde. Bu ortamda koşturulamadı.
3. **Gerçek Windows DPI.** Ölçek testleri `QT_SCALE_FACTOR` ile yapıldı. Windows'un monitör başına DPI davranışı ve gerçek görev çubuğu yüksekliği Windows CI performans iş akışı dışında doğrulanmadı.
4. **DWG.** Gerçek DWG dönüştürme ODA File Converter gerektiriyor, NOT RUN.
5. **3D önizleme düzeltmesi** (`bfa16ce`). Canlı SOLIDWORKS'te doğrulanması kullanıcı makinesinde bekleniyor.
6. **Ayar fuzz testi.** İkinci aşama 41 anahtarın 23'ünü tek tek bitirdi (zaman sınırı). Kalan 18 anahtar, kalıcı testte her yanlış türde tüm anahtarlar birlikte denenerek kapsandı.
7. **Uzun Windows yolları (>260 karakter)** Linux'ta test edilemedi.
