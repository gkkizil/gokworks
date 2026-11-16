# Otomatik Teknik Resim — Test raporu

Tarih: 15–16 Kasım 2026.

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

## 16 Kasım — Gövde bazlı sac paftaları

**231 benzersiz test geçti, 2 canlı kabul testi atlandı.** Bu turun
çalıştırmaları `/workspace/work/drawing-dev-20261116/` altındadır;
önceki turun 748 testi tekrar çalıştırılmış gibi sayılmamıştır.

| Çalıştırma | Sonuç |
|---|---|
| Otomatik teknik resim modülü + repository structure + lazy pages + single file distribution | 151 geçti, 2 atlandı |
| DXF/DWG sheet inventory + multibody refresh/names + autosave raw dispatch; profile cutting API; packaged data; job event/deadlock | 77 geçti |
| Son tam modül kontrolü | 135 geçti, 2 atlandı; tekrarlar toplamda yeniden sayılmadı |
| Son gövde / native pafta sınırı kontrolü (`test_sheetmetal.py` + `test_native_boundary.py`) | 55 geçti; önceki çalıştırmadaki tekrarlar toplamda yeniden sayılmadı |

Kapsanan yeni durumlar:

- Aynı görünen ada sahip üç gövdenin farklı kalıcı kimlikleri, ayrı
  kalınlık / malzemeleri ve ORHAN-01/02/03 pafta başlıkları.
- GetBodies2 sırası değişince üretim kimliklerinin korunması; belirsiz
  FlatPattern eşleşmesinin veya birden çok açınım adayının atlanması.
- Türkçe yeniden adlandırılmış konfigürasyonu native özellik durumu ve
  parent ilişkisiyle tanıma; İngilizce SM-FLAT-PATTERN adına bağımlı olmama.
- AccessSelections / ReleaseSelectionAccess dengesinin korunması ve
  rollback sonrasında eski gövde pointer’larının kullanılmaması.
- IView.Bodies için IDispatch SAFEARRAY, tek gövde kapsamı, yedi argümanlı
  native açınım çağrısı, kaynak konfigürasyonu geri alma ve ayrı paftalar.
- Gerçek not API sözleşmesi, paftaya AttachAnnotation, 3 mm font ve
  ayrılmış başlık alanı; boş ActivateView ile pafta etkinleştirmeye çalışmama.
- Yeniden açma sınırında yanlış gövde / konfigürasyon, kayıp veya değişmiş
  başlık, bastırılmış FlatPattern, değişmiş Cut List üyeliği / kalınlık /
  malzemenin reddedilmesi.
- Yeni kaynak konfigürasyonu oluşunca durma, kopan COM bağlantısını
  eksik metadata gibi yutmama, iptal ve yalnız düz veri içeren cache.
- Eksik gövde kalınlığı / malzemesini modelin ortak değeriyle doldurmama;
  analiz ekranında gövde bazlı bilgilerin aynı kaynak ağacında gösterilmesi.
- Özellik okuması sırasında konfigürasyon değişirse durma ve kaynak
  kapsamını geri alma; farklı çözülmüş belgeye konfigürasyon / seçim
  işlemi uygulamadan kimlik hatasını bildirme.

Bu gövde / native pafta senaryoları açıkça raw COM **fakes** ile çalışır;
gerçek sac açınımı üretildiği anlamına gelmez. Windows’taki opt-in
çok gövde kabulü `GOKWORKS_DRAWING_LIVE_MULTIBODY_SOURCE` ve
`GOKWORKS_DRAWING_LIVE_TEMPLATE` değişkenleriyle etkinleştirilir; bu
ortamda çalıştırılmadı. Mevcut kaynakta doğru açınım konfigürasyonları
hazır olmalıdır.

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

## 15 Kasım — İlk sürümün çalıştırmaları

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
