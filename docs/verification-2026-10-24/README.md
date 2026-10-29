# GOKWORKS · Uygulama doğrulaması

24 Ekim 2026. Başlangıç: `main`, `2b9661c400989649226102084b68be1ff86b3771`.
Bu rapor önceki arayüz çalışmasının test sonuçlarını tekrar sunmaz; komutlar yeniden çalıştırıldı.
Ortam Linux, Python 3.13.5, PySide6/Qt 6.10.3, `offscreen`.

## Kapsam

| Alan | Çalıştırılan kontroller | Sınır |
| --- | --- | --- |
| PDF | Gerçek alt süreç/IPC, bütün sayfalar API sözleşmesi, hatalı çıkış, yarım JSON/UTF-8, iptal, geçici dosya temizliği, mevcut çıktı koruması, GUI'nin açık kalması | CAD tarafı mock; gerçek SolidWorks PDF kaydı yapılmadı |
| DXF / DWG | Kaynak tarama, biçim/kalınlık/adet kuralları, tek gövdeli sac kontrolü, çıktı/iptal/hata davranışı | Sac açınımı için gerçek COM oturumu kullanılmadı |
| 3D dönüştürücü | Sekiz format, konfigürasyon ve montaj seçenekleri, kuyruk, çoklu kaynak, filtre/temizleme, kayıt güvenliği | Gerçek STEP/Parasolid/IGES/STL üretimi yapılmadı |
| BOM | Ürün ağacı, adet/ağırlık, eksik veriler, arama, büyük sanal tablolar, gerçek Excel yazımı ve formül olarak yorumlanmayan metinler | Montaj okuma mock |
| İsimlendirme | Pack and Go interop sözleşmesi, önizleme, çakışma/dosya güvenliği, hata/iptal | Gerçek montaj referanslarıyla Pack and Go çalıştırılmadı |
| K/R | SheetMetal API çağrı sözleşmeleri, kalınlık eşleştirme, desteklenmeyen gövdeler, özel bükümleri koruma, kaydetme tercihi, canlı takım şeması | Gerçek sac parçasına değer yazılmadı |
| ISO geçmeler | ISO 286 sapmaları, manuel/asimetrik limitler, işaretler, boşluk/sıkılık, referans eşleştirmesi, kesit ve rapor | Tablo kapsamı modül dokümanındaki sınırlar içinde |
| GD&T | Katalog, datum/çerçeve, tolerans bölgesi, ölçüm açıklamaları, boyut ilişkileri ve desteklenmeyen durumlar | Desteklenmeyen 3D tolerans modelleri doğrulanmış sayılmadı |
| Tolerans yığılması | Worst-Case/RSS/Monte Carlo, işaretli/asimetrik zincir, eksik tolerans, güncellik, JSON kaydı, PDF/Excel, okuyucu/anotasyon mock'ları | Gerçek SLDDRW okuma/yazma yapılmadı |
| Cıvata | Çekme/kesme/birleşik yük, birim dönüşümü, kalite/diş, emniyet/taşıma sınırları ve grafikler | Dinamik/FEA doğrulaması iddia edilmez |
| Hızlı tork | Metrik seri, normal/ince diş, kalite/çap sınırları, K ve ön yük, geçersiz sayılar, kesit/kopyalama | Yaklaşık tork modeli; gerçek bağlantı testi değil |
| Ağırlık | Kesitler, yoğunluklar, katalog alanı, birimler, adet ve kesit çizimleri | Varsayılan malzeme yoğunlukları modül kapsamındadır |
| Nesting | Gerçek DXF konturları, delik içi yerleşim, çoklu levha/stok, aralık/çarpışma sınırları, miktar/maliyet, JSON/DXF/Excel/PDF, iptal, Inspector eşlemesi | Global optimum veya CAM kesim telafisi garanti edilmez |
| Profil kesim | Stok/kerf/gruplama, adetler, farklı konfigürasyonlar, tekrarsız aktarım, gönye inceleme kuralları, JSON/CSV | Weldments tarama COM mock; gerçek konstrüksiyon taranmadı |

Bağımsız örneklerde M10 8.8 kuru tork yaklaşık **51,9587 N·m**, ön yük **25,9793 kN**;
1000×2000×10 mm çelik levha **157 kg**; A−B−C tolerans zinciri **0,20 / 0,02 / 0,38 mm**
değerleri mevcut doğrulanmış motorlarla kontrol edildi.

## Tam test ve açılış sonuçları

Son tam koşu: **1.168 test başarılı, 878 alt test başarılı, 9 atlanan; sıfır başarısızlık/hata**.
Toplanan 1.177 bağımsız test 71 ayrı süreçte çalıştırıldı. JUnit'in alt testlerle toplamı 2.055'tir.
[Sayısal sonuç](test-summary.json), [Arşiv: JUnit](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/verification-2026-10-24/final-full-tests.xml), [süreç çıkışları](final-full-run.txt),
[9 atlama nedeni](skipped-tests.json). [Hedefli 11 arayüz testi](targeted-theme-tests.txt) de geçti;
bu sayı tam koşuyla örtüşür, toplama eklenmez. `baseline-full-tests.xml` düzeltme öncesindeki
başarılı ilk tam koşudur; iki tam koşunun sayıları da toplanmaz.

- [Sözdizimi/import envanteri](inventory.json): izlenen kaynak ağacının AST/compile ve erken yerel import döngüsü denetimi.
- [Statik kontrol](static-checks.txt): aktif kaynaklarda Ruff F821/F822/F823.
- [Ayar ve bağımlılık ortamı](environment.json), [uyumluluk kontrolü](dependency-check.txt).
- [Güncel bağımlılık taraması](current-dependency-audit.json): çalışan 13 runtime paket sürümü ve
  mevcut Windows pywin32/PyInstaller pinleri. Sorgu anında bilinen bildirim yok;
  bu sonuç bütün kodun güvenli olduğunun veya Windows paketinin çalıştırıldığının kanıtı değildir.
- [Standart DPI](source-dpi-1.json), [%125](source-dpi-1.25.json), [%150](source-dpi-1.5.json):
  14 modül, iki tema, 1024×700 / 1366×768 / 1920×1080 / 2560×1440 mantıksal pencere boyutları;
  gerçek yerel rapor çıktıları ve izole PDF worker başlangıcı. Windows DPI testi olarak sunulmaz.

## Uzun kullanım ve hata enjeksiyonu

[Kararlılık koşusu](stability.json): **840 modül geçişi, 840 boyutlandırma, 20 tema değişimi**;
820×560, 1024×700 ve 1440×900, açık/koyu tema, geniş/dar gezinme.
Widget sayısı **2.512 → 2.512**; girdi, hesap ve yerleşim durumları korundu.
Uygulama kapatılıp tekrar açıldığında ayarlar ve örnek hesaplar geri geldi.
Widget sayısının sabitliği tüm native heap için sızıntı kanıtı değildir.

PDF stres kontrolünde:

1. İlk eski `QTest.qWait` tabanlı 20 çevrimlik koşu 60 saniyelik watchdog sınırında durdu.
   [Orijinal zaman aşımı](pdf-stress-initial-timeout.txt) saklandı. Python izinde ana iş parçacığı
   sentetik beklemedeydi; bu tek kayıtla gerçek uygulamada/COM'da kök neden belirlendiği iddia edilmez.
2. Aynı eski kontrolün izleyen 20 çevrimlik koşusu geçti:
   [tekrar kaydı](pdf-stress-original-repeat.txt). Bu, ilk zaman aşımını geçersiz kılmaz.
3. Yardımcı araç gerçek Qt olay dağıtıcısını kullanan `QEventLoop.exec()` ve işlem başına 10 saniyelik
   `QTimer` ile çalışacak şekilde güncellendi. Toplam 60 saniyelik watchdog korundu;
   beklenen sonuç/dosya/iş parçacığı kontrolleri kaldırılmadı.
4. Yeni yöntemle [20 çevrim](pdf-native-loop-recovery.json) ve ardından
   [80 çevrim](pdf-native-loop-endurance.json) geçti. Her çevrimde gerçek alt süreç kasıtlı olarak
   **23** koduyla çıktı; GUI açık kaldı, ilk PDF korundu, ikinci dosya hata gösterdi,
   geçici çıktı temizlendi ve sonuç callback'leri GUI iş parçacığında çalıştı.

Bu koşular SolidWorks kullanmaz. **İlk zaman aşımının tek kök nedeni kesinleştirilemedi**;
test aracındaki değişiklik gerçek SolidWorks kaynaklı çökmenin düzeltildiği iddiası değildir.

## Bulgu ve uygulanan düzeltme

Etkin temayı yeniden seçmek, Qt stilini ve 14 modülün teknik görünümlerini tekrar oluşturuyordu.
`MainWindow.set_theme` ilk uygulamayı koruyup zaten uygulanmış aynı tema için erken döner.
Koyu/açık tema geçişi ve bütün mevcut hesaplar korunur. Yeni regresyon testi, aynı tema için
yeniden görünüm üretimi olmadığını, farklı temada güncellemenin gerçekleştiğini kontrol eder.

[Aynı canlı pencereyle önce/sonra ölçümü](theme-reselection.json): yaklaşık
**1.223,8 ms → 0,0033 ms**. Bu tek süreç ölçümüdür. Gerçek koyu↔açık geçişi hâlâ tam Qt
yenilemesi yapar; uzun testte ortanca yaklaşık **1,27 saniye** ölçüldü. Bu gecikme devam eder.

Değişen uygulama dosyası: `gui_qt/app.py`. Ek regresyon:
`tests/test_fusion_workbench.py`. Hata enjeksiyon aracı:
`docs/report-tools/validate_pdf_fault_recovery.py`. Hesaplama, optimizasyon ve COM motorları değiştirilmedi.

## Tekrar çalıştırma

```bash
python -m pip install -r requirements-dev.txt
QT_QPA_PLATFORM=offscreen python packaging/run_windows_tests.py
QT_QPA_PLATFORM=offscreen python main.py --self-check source-selfcheck.json
QT_QPA_PLATFORM=offscreen python docs/report-tools/validate_application_stability.py stability.json --cycles 20
QT_QPA_PLATFORM=offscreen python docs/report-tools/validate_pdf_fault_recovery.py pdf-recovery.json --cycles 80
```

Gerçek Windows/SolidWorks kontrolleri mevcut opt-in testleriyle, kullanıcının CAD dosyalarının
ayrı test kopyalarında çalıştırılmalıdır: `modules/naming/tests/test_naming_native_live.py`,
`modules/cad_converter/tests/test_live.py`, `modules/tolerance_stack/tests/test_tolerance_stack_live.py`,
`modules/profile_cutting/tests/test_live.py`. Her dosyada gerekli ortam değişkenleri ve atlama
koşulları belirtilir. Burada atlanan testler başarılı gösterilmez.

Bu çalışma yeni EXE üretmez ve mevcut EXE'yi doğrulamış sayılmaz. `main` üzerinde çalışıldı;
`release` dalı ve yedek GitHub reposu değiştirilmedi.
