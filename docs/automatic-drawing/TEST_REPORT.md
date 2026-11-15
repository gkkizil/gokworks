# Otomatik Teknik Resim — Test raporu

Tarih: 15 Kasım 2026.

Ortam: Linux, Python 3.12, PySide6 6.10.3, pytest 9.0.2.
Gerçek SolidWorks / Windows / pywin32 COM sunucusu bu ortamda yoktur.
Bu rapor gerçek imalat resmi kabulü veya SolidWorks 2026 uyumluluk
onayı değildir.

## Test katmanları

1. Saf kural / geometri / yerleşim testleri.
2. Gerçek geçici dosyalar üzerinde kaynak koruma ve paket yayını.
3. Ham IDispatch çağrı sözleşmesi fakes; API owner / argüman / birim /
   PROPERTYGET / kaynak durum geri alma kontrolü.
4. Sıralı kuyruk için açıkça FAKE CAD adapter. Bu testteki dosya
   başlıkları gerçek SLDDRW veya üretim PDF’i değildir.
5. Gerçek Qt sayfa / navigasyon / worker / tema / küçük pencere testleri.
6. Ayrı opt-in Windows / lisanslı SolidWorks canlı kabul testi.

Canlı test varsayılan ortamda SKIP’tir. Modelin yeniden açılabilir gerçek
SLDDRW / PDF ürettiği ancak bu test gerçekten çalıştırılıp örnek resimler
SolidWorks’te incelendikten sonra kabul edilebilir.

## Talep senaryoları ile eşleştirme

| Talep | Yerel doğrulama | Canlı kabul durumu |
|---|---|---|
| 100×50×10 plaka | mm / metre, yüzey kanıtı, yön, A3 yerleşim, native çağrı sözleşmesi | Çalıştırılmadı |
| Delikli plaka | Ayrı aynı çap ölçülerini koruma, native merkez API sözleşmesi | Delik konumu / çap resmi incelenmedi |
| Kademeli mil | Döndürme + silindir + uzun eksen kuralı | Gerçek çap / omuz ölçüleri incelenmedi |
| Flanş | Sınıf / yön kuralı için geometri altyapısı | Otomatik PCD tamamlanmadı |
| Sac metal | Çok gövde / mevcut config / beklenmedik config durumları | Gerçek büküm çizgileri incelenmedi |
| Montaj | Hiyerarşi, native BOM çağrısı, adet ve görünen sütun denetimi | Gerçek montaj resmi incelenmedi |
| 12 aynı cıvata | Bir çizim kimliği, 12 örnek, BOM 12; override / belirsiz sayı biçimi engeli | Canlı BOM kabulü yapılmadı |
| İki seviyeli montaj | Hiyerarşi ve doğru örnek çarpımı / benzersiz çizim ayrımı | Çalıştırılmadı |
| Karmaşık parça | Muhafazakâr sınıf, kesit / detay kontrol önerisi | Otomatik kesit / detay tamamlanmadı |
| 20 dosya | Offline kuyrukta kasıtlı tek hata, diğer 19 işin tamamlanması, doğru ledger | 20 gerçek CAD dosyası çalıştırılmadı |

Ek senaryolar: kaynak dosyanın / bellekteki modelin işlem sırasında
değişmesi, kayıt sonrası kopuk model bağlantısı, yanlış konfigürasyon,
iptal, restore hatasında bütün kuyruğu durdurma, kaynak üzerinde Save
çağrısı yapılmaması, native dosya olmadan PDF-only başarı engeli,
dosya adı / mevcut dosya / yayın yarışı, bozuk ayarlar, iki tema ve
820×560 / 1024×700 / 1440×900 pencereler.

## Çalıştırmalar

Birleştirilmiş sonuç: **748 benzersiz test geçti, 5 test atlandı**;
ayrıca 5 subtest geçti. Aşağıdaki tekrar çalıştırmalar bu toplamda
ikinci kez sayılmamıştır. Ruff F denetimi ve `git diff --check` temizdir.

Modül, repo yerleşimi, gecikmeli sayfa yükleme ve tek dosya dağıtım testleri:

~~~text
python -m pytest modules/automatic_drawing/tests tests/test_repository_structure.py
  tests/test_lazy_pages_gui.py tests/test_single_file_distribution.py -q
~~~

Sonuç: 119 geçti, 1 atlandı. Bu son tam modül çalıştırması rapor yazımı,
belge sahipliği ve iki koordinatlı native görünüş konumu düzeltmelerinin
tamamını içerir.

Ortak UI / worker / ayar / paketleme regresyonları:

~~~text
python -m pytest tests/test_compact_workspaces_gui.py tests/test_qa_damaged_settings.py
  tests/test_qt_workflows.py tests/test_packaged_data_files.py
  tests/test_settings_and_connection.py tests/test_job_event_delivery.py
  tests/test_qa_job_worker_deadlock.py -q
~~~

Sonuç: 214 geçti, 1 atlandı; 5 subtest geçti. ezdxf / pyparsing
deprecation bildirimleri dış bağımlılıktan gelmektedir.

CAD bağlantı servislerini yeniden kullanan regresyonlar:

~~~text
python -m pytest modules/dxf_dwg/tests/test_autosave_raw_dispatch.py
  modules/dxf_dwg/tests/test_restore_activation_status.py
  modules/cad_converter/tests modules/profile_cutting/tests/test_api.py
  modules/profile_cutting/tests/test_scanner.py modules/tolerance_stack/tests -q
~~~

Sonuç: 415 geçti, 3 atlandı. Bu mevcut CAD servisleri regresyonları da
canlı SolidWorks testi değildir.

Son düzeltmelerin senaryoları, rapor yazımı başarısızken son aşamanın
tamamlanmış gösterilmemesini, yalnız sahip olunan teknik resim için
CloseDoc sonrasında kapanmanın okunarak doğrulanmasını ve IView.Position
verisinin üç yerine iki double ile okunup yazılmasını kapsar.

Son arayüz / paketleme kontrolü:

~~~text
python -m pytest modules/automatic_drawing/tests/test_ui.py
  tests/test_packaged_data_files.py tests/test_single_file_distribution.py -q
~~~

Sonuç: 23 geçti. İki tema için 1366×768 ve 820×560 ekran görüntüleri
ayrıca incelendi. UI ve worker testleri gerçek Qt kullanır; CAD üretiminin
yerine geçmez. EXE derlenmedi; Windows entegrasyonu otomasyonun görevidir.

Çalıştırma XML raporları geliştirme çalışma alanında
`/workspace/work/drawing-dev-20261115/` altında saklanır. Bu klasör
dağıtıma eklenmez; test kaynakları depodadır. Nihai sayılar
`module-final.xml`, `shell-regression.xml`, `cad-regression.xml` ve
`preview-final.xml` raporlarından gelir; ara hata ayıklama çalıştırmaları
nihai sonuç olarak sayılmamıştır.

## Kalan kabul çalışması

Kayıtlı parça / montaj fixture’ları ve firma DRWDOT / SLDDRT / BOM
şablonlarıyla gerçek SolidWorks 2026’da canlı testi etkinleştirin.
Referans / ölçü / büküm ve BOM çıktıları mühendis tarafından incelenmelidir.
Mock başarısı gerçek CAD testi olarak raporlanmamıştır.
