# GOKWORKS mimarisi

Bu belge, kodun 2 Kasım 2026 tarihindeki durumunu özetler. Amacı, yeni bir
geliştirme oturumunda projeyi hızlıca tanımaktır. Kullanım rehberi için
[README](../README.md), klasör taşıma geçmişi için
[repository-structure.md](repository-structure.md) belgesine bakın.

## 1. Amaç

GOKWORKS; SolidWorks aktarımlarını (PDF, DXF/DWG, STEP/IGES/Parasolid/STL),
montaj BOM'unu, Pack and Go ile yeniden adlandırmayı, sac/profil kesim
planlamayı ve makine tasarımı hesaplarını tek bir Türkçe masaüstü uygulamasında
toplar. Öncelikler: mühendislik doğruluğu, kullanıcı CAD dosyalarının korunması
ve uzun CAD işlemlerinde arayüzün yanıt vermeye devam etmesi.

## 2. Teknolojiler

| Katman | Teknoloji |
| --- | --- |
| Dil | Python 3.13 (Windows CI ve yerel doğrulamada kullanılan sürüm) |
| Arayüz | PySide6 6.10 / Qt Widgets; bazı önizlemeler QOpenGLWidget |
| CAD otomasyonu | pywin32 COM (`SldWorks.Application`), ayrıca PowerShell `Add-Type` ile derlenen C# STA köprüleri (mil, Pack and Go, K/R denemesi) |
| Geometri | shapely 2 (GEOS), ezdxf 1.4 |
| 3D çekirdek | cadquery-ocp-novtk (OpenCascade) — yalnız dişli STEP/DXF çıktısı |
| Rapor | openpyxl (Excel), Qt PDF yazıcısı |
| Test | pytest, pytest-qt, pytest-timeout (Qt `offscreen`) |
| Paket | PyInstaller tek EXE (`packaging/build_windows.py`, GitHub Actions) |

## 3. Klasör yapısı

```text
main.py            Giriş: GUI, --pdf-export-worker, --gear-worker,
                   --process-exit-watch, --self-check
gui_qt/            Ortak Qt kabuğu: app.py (MainWindow), workers.py (JobManager),
                   components.py, models.py (tablolar), theme/icons/settings,
                   export.py (PDF/DXF ortak sayfa), calculations.py (ortak hesap
                   ekranı), package_check.py (öz denetim)
shared/            Qt'siz yardımcılar: atomik JSON ayarları, tema verisi, metin
solidworks/        COM bağlantısı, tanılama günlüğü, çıkış izleyicisi,
                   isteğe bağlı kitaplık yolu seçimi (runtime.py)
modules/<modül>/   Her özellik: saf motor + ui.py + tests/ (+ README)
tests/             Uygulama/kabuk/paketleme testleri, tests/support sahteleri
packaging/         Windows derleme, lisanslar, Windows test çalıştırıcısı
docs/              Rehberler ve tarihsel doğrulama kayıtları (değiştirilmez)
```

## 4. Gerçekte uygulanan modüller

| Sayfa anahtarı | Klasör | Motor (Qt'siz) | Dış bağımlılık |
| --- | --- | --- | --- |
| `pdf` | `modules/pdf` | `exporter.py`, ayrı süreç `process.py` | SolidWorks COM |
| `dxf_dwg` | `modules/dxf_dwg` | `sheetmetal.py`, `exporter.py`, `inventory.py`, `preview/` | SolidWorks COM |
| `cad_converter` | `modules/cad_converter` | `api.py`, `exporter.py`, `validation.py` | SolidWorks COM |
| `bom` | `modules/bom` | `ui.py` okuma, `exporter.py` (Excel), `images.py` | SolidWorks COM |
| `naming` | `modules/naming` | `hierarchy.py`, `native.py` (C# Pack and Go) | SolidWorks interop |
| `k_factor` | `modules/k_factor` | `rules.py`, `apply.py`, `sheetmetal_parameters.py` | Atama için COM |
| `iso_fits` | `modules/iso_fits` | `rules.py` + `tables.json` (ISO 286, nm tamsayı) | — |
| `geometric_tolerances` | `modules/geometric_tolerances` | `rules.py`, `catalog.py` | — |
| `tolerance_stack` | `modules/tolerance_stack` | `chain.py`, `calculator.py`, `monte_carlo.py`, `storage.py` | SLDDRW okuma/yazma için COM |
| `bolt` | `modules/bolt` | `rules.py` (statik gövde kontrolü) | — |
| `bolt_torque` | `modules/bolt_torque` | `rules.py` (T = K·F·d) | — |
| `weight` | `modules/weight` | `rules.py`, `materials.py` | — |
| `nesting` | `modules/nesting` | `engine.py` (NFP + çoklu başlangıç), `validation.py`, `accounting.py`, `dxf_import.py` | shapely, ezdxf; DWG için paketteki LibreDWG (kuruluysa ODA) |
| `profile_cutting` | `modules/profile_cutting` | `optimizer.py` (1D best-fit + sınırlı tam arama), `scanner.py` | Weldments taraması için COM |
| `shaft_generator` | `modules/shaft_generator` | `models.py`, `validation.py`, `geometry.py`, `bridge.py` | C# STA köprüsü |
| `gear_calculator` | `modules/gear_calculator` | `calculation.py`, `geometry.py`, `families/`, `sprockets/` | OCP (ayrı süreç) |

Hedeflenip **uygulanmamış** alanlar: genel parametrik parça oluşturma
(yalnız mil ve dişli var), otomatik teknik resim/ölçülendirme, mil mukavemet
hesabı (mil modülü yalnız geometri/CAD üretir). Nesting DWG'yi paketteki LibreDWG
ile geçici DXF üzerinden okur (DWG'nin doğrudan yerel ayrıştırılması yoktur).

## 5. Çalışma mimarisi

1. `main.py` önce `solidworks.runtime.configure_libraries()` çağırır; sonra
   argümana göre GUI'yi veya Qt'siz bir işçi sürecini başlatır.
2. `gui_qt.app.MainWindow` 16 sayfayı `PageRegistry` ile **ilk açılışta**
   oluşturur (`PAGE_TYPES`). Sol menü `MODULES` listesinden gelir.
3. Uzun işler `gui_qt.workers.JobManager` ile tek bir `QThread` üzerinde,
   sırayla çalışır. Motorlar `events.put((tür, veri))` arayüzünü kullanır;
   `EventSink` olayları en çok 16 ms / 64 olaylık paketlerle Qt kuyruğuna
   iletir. Sayfa `handle_events(batch)` ile ana iş parçacığında işler.
   İptal `threading.Event` ile istenir; motorlar düzenli kontrol eder.
4. PDF aktarımı ve dişli OCP işleri ayrı süreçte çalışır (aynı EXE, özel
   bayrak, dosya tabanlı JSON protokolü). COM nesneleri süreç sınırını geçmez.
5. Mil ve Pack and Go, çalışan SolidWorks kurulumunun interop DLL'leriyle
   PowerShell içinde derlenen C# STA sunucusu üzerinden, satır bazlı JSON ile
   çalışır.
6. Ayarlar `%APPDATA%/GOKWORKS/settings.json` dosyasına benzersiz geçici dosya
   + fsync + `os.replace` ile atomik yazılır. Proje dosyaları
   (`tolerance_stack.storage.atomic_write`) aynı modeli kullanır ve varsayılan
   olarak var olan dosyanın üzerine yazmaz.

## 6. SolidWorks entegrasyonu

- Bağlantı: `solidworks/connection.py` → `GetActiveObject("SldWorks.Application")`;
  uygulama SolidWorks'ü kendisi başlatmaz.
- Her COM işi kendi iş parçacığında `CoInitialize`/`CoUninitialize` yapar;
  COM sarmalayıcıları `CloseDoc` öncesinde `None` yapılarak bırakılır.
- Aktarım motorları yalnız kendi açtıkları belgeleri kapatır, önceki etkin
  belgeyi/konfigürasyonu geri yükler; geri yükleme başarısızsa işlem durur.
- Çıktılar geçici adla yazılıp doğrulandıktan sonra yayımlanır; "Üzerine yaz"
  kapalıyken mevcut dosyalara dokunulmaz.
- Testlerde COM; `tests/support/solidworks.py`, `modules/*/tests/fakes.py` ve
  `sheet_fakes.py` sahteleriyle izole edilir. `*_live.py` testleri yalnız
  Windows + SolidWorks ortamında çalışır; Linux'ta atlanır.

## 7. Önemli sınıflar ve fonksiyonlar

| Ad | Konum | Görev |
| --- | --- | --- |
| `MainWindow`, `create_application`, `main` | `gui_qt/app.py` | Kabuk, tema, sayfa yönetimi, güvenli kapanış |
| `JobManager`, `JobWorker`, `EventSink` | `gui_qt/workers.py` | Tek CAD işi, olay paketleme, iptal |
| `PageRegistry` | `gui_qt/pages.py` | Tembel sayfa oluşturma |
| `SettingsStore` | `gui_qt/settings.py` | Arayüz tercihleri |
| `nest`, `validate_result`, `calculate` | `modules/nesting/engine.py`, `validation.py`, `accounting.py` | Yerleşim, bağımsız doğrulama, maliyet |
| `read_dxf` | `modules/nesting/dxf_import.py` | Katı DXF kontur okuma (açık/dallanan kontur reddi) |
| `optimize`, `validate_plan` | `modules/profile_cutting/optimizer.py` | 1D kesim planı |
| `calculate` | `modules/tolerance_stack/calculator.py` | WC / RSS (+ Monte Carlo) |
| `calculate_pair` | `modules/gear_calculator/calculation.py` | Düz dişli çifti |
| `calculate` | `modules/{bolt,bolt_torque,weight,k_factor,iso_fits}/rules.py` | Hesap motorları |

## 8. Test ve çalıştırma

```bash
pip install -r requirements-dev.txt
# Linux'ta Qt için libEGL/libGL/libxkbcommon/libfontconfig gerekir.
QT_QPA_PLATFORM=offscreen python -m pytest            # tüm regresyon
QT_QPA_PLATFORM=offscreen python -m pytest modules/nesting/tests
QT_QPA_PLATFORM=offscreen python main.py --self-check /tmp/gokworks-check.json
python main.py                                         # uygulama
python packaging/build_windows.py                      # Windows EXE (Windows'ta)
```

`pytest.ini`: `testpaths = tests modules`; yalnız `examples` klasörleri
toplanmaz. Windows'a özel testler `packaging/run_windows_tests.py` ile
GitHub Actions'ta parçalı süreçlerde çalışır.

## 9. Bilinen teknik sınırlamalar

- Gerçek SolidWorks davranışı bu Linux ortamında doğrulanamaz; COM yolları
  sahte nesnelerle test edilir.
- Nesting sezgiseldir (NFP + çoklu başlangıç + zaman bütçesi); matematiksel
  optimum iddia edilmez. Sonuçlar bağımsız `validate_result` ile kontrol edilir.
- Profil kesim planı, alt sınıra ulaşıldığında veya ≤22 parçalık grupta tam
  arama bittiğinde minimumdur; aksi halde "minimum garanti edilmez" yazar.
- Cıvata hesabı statik, eşit yük paylaşımlı gövde kontrolüdür; tork hesabı
  K katsayısı varsayımına dayanır.
- Ağırlık hesabı ölçülerden profil kesitinde radyüsleri ihmal eder
  (`approximate=True`).
- Tip denetimi (Pyright) temiz değildir; dinamik COM dönüşleri başlıca
  kaynaktır.

## 10. Yeni modül kuralları

1. `modules/<ad>/` altında Qt ve COM import etmeyen bir motor yazın; birimleri
   (mm, N, N·m, MPa) fonksiyon adına veya belgeye açıkça yazın.
2. Geçersiz girişte yalnız Türkçe, eyleme dönük `ValueError` üretin; NaN/inf,
   bool ve taşmaları reddedin.
3. `ui.py` sayfasını `gui_qt/app.py` içindeki `PAGE_TYPES` ve `MODULES`
   listelerine ekleyin; uzun işleri `JobManager.start(owner, operation)` ile
   çalıştırın, ana iş parçacığında COM çağrısı yapmayın.
4. CAD işlerinde yalnız kendi açtığınız belgeleri kapatın, kullanıcının
   belgesini kaydetmeyin; çıktıları atomik yazın ve üzerine yazma iznini
   kullanıcıdan alın.
5. `modules/<ad>/tests/` altında bağımsız referans değerli sayısal testler ve
   sahte COM nesneli testler ekleyin; canlı testleri `*_live.py` olarak ayırın.
6. Yeni veri dosyalarını `packaging/build_windows.py` paket listesine ekleyin.
