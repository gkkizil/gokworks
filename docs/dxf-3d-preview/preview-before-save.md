# DXF/DWG: kayıttan önce açınım kontrolü

DXF/DWG ekranındaki **Aktarım seçenekleri → Kaydetmeden önce önizle**
varsayılan açıktır. Tercih `dxf_dwg_preview_before_export` boolean alanında
saklanır; eski ayar dosyalarında alan bulunmuyorsa açık kabul edilir.

## Kullanım

1. Kaynak klasörü seçin ve **Klasörü tara** veya **Önizleme** düğmesine basın.
   İlk görünür parça seçilir; 3D gövde, ardından altındaki açınım gösterilir.
   Üretim çıktısı klasörü henüz gerekli değildir.
2. Listeden diğer parçaları seçerek açınımlarını aynı alanda kontrol edin.
   Dar pencerede **Önizleme** sekmesi kullanılır.
3. Önizleme yokken **Aktarımı başlat** da bu kontrolü açar. Okuma bitince
   kayıt otomatik başlamaz. Hazır olunca düğmeye tekrar basın; mevcut toplu
   aktarım, klasörleme ve sessiz Tümünü Kaydet politikası bu aşamada çalışır.
4. Açınım hatalı/boşsa yalnız 3D'nin okunması bu kontrolü geçirmez.
   **Yenile** ile tekrar okuyun. Ayarı kapatmak eski doğrudan aktarımı seçer.

Bu akış seçili parçanın görüntüsünü kullanıcıya sunar; bütün satırlara ayrı
bir onay verildiği veya imalat geometrisinin sertifikalandığı anlamına gelmez.
Kaynak/konfigürasyon CAD tarafında değiştirilirse tekrar Yenile kullanılmalıdır.

## Korunan davranışlar

- Önizleme mevcut `capture`/`capture_geometry` STA adaptörünü kullanır.
  COM nesnesi GUI'ye taşınmaz, yeni SolidWorks süreci başlatılmaz.
- Üretim DXF/DWG veya native kaynak dosyası kaydedilmez. Gerekli geçici DXF
  mevcut native aktarım adaptörüyle oluşturulur, okunur ve silinir. DWG
  çözümleyici eklendiği veya DWG'den 3D üretildiği iddia edilmez.
- Önizleme sürerken Başlat, okumayı iptal etmez ve sonrasına otomatik kayıt
  kuyruğa koymaz. Durdur bu akışı ve bekleyen tarama seçimini de iptal eder.
- Büküm çizgileri seçimi değiştiğinde eski biçime sahip üretim DXF'si
  kullanılmaz; önizleme yeni tercihle tekrar okunur.
- Başlat anında dosyanın boyut/zaman kimliği kontrol edilir. Dosya değişmişse
  watcher bildirimi henüz gelmese bile eski açınımla kayıt başlatılmaz.
- Kaynak klasör değişirse önceki klasörün parçası kontrol yerine kullanılamaz.
- Bilinen kaynak geri alma hatası sessiz kayıtla örtülmez; kaynak durumunun
  yeniden okunarak doğrulanması gerekir.
- Hesap motorları, dışa aktarma API imzaları ve diğer modüller değiştirilmedi.
  EXE derlemesi isteği `cancelled=true` olarak korunur.

## Doğrulama

DXF paketinin tamamı ve `tests/test_qt_workflows.py` **340 pytest öğesi /
384 JUnit kaydıyla** çalıştı: **0 hata/başarısızlık, 3 atlama**. 156 sınırlı
süreç grubunun tamamı exit 0 döndü.
[Regresyon JUnit](before-save-regression-tests.xml).

`modules/dxf_dwg/tests/test_preview_before_export_ui.py` gerçek Qt arayüzünü
kullanır. **14 test geçti**: DXF/DWG için önce göster/sonra kaydet, seçimsiz
Önizleme, çıktısız tarama, devam eden okumanın korunması, eksik açınımın kayda
geçememesi, tercih kaydı, büküm çizgisi değişikliği, watcher öncesi dosya
değişikliği, Durdur/Yenile, farklı klasör ve gizli dar sekmenin açılması.
[Son akış JUnit](before-save-ui-tests.xml).

İki test UI → `capture` → `export_one_part` → gerçek `ezdxf` okuma → Qt
sahnesi zincirini birlikte çalıştırır. Yalnız CAD sunucusu taklittir;
üretim klasörünün oluşmadığı, geçici DXF'nin silindiği, native dosya baytları
ve önceki aktif belgenin korunduğu kontrol edilir.
Bu son iki zincir testi genel taramanın envanterinden sonra eklendi;
son 14 testlik akış çalışması bunları da içerir. Son ayar başlığı da dar
ekrana sığması için kısaltıldı. Ruff isim çözümleme ve git whitespace denetimi
geçti. Önceden korunan 11 ortak kaynak dosyasının hash'leri değişmedi.

Lisanslı SolidWorks ve kullanıcının gerçek parçaları bu Linux ortamında yoktur.
Bu testler gerçek SolidWorks açınım üretiminin canlı kabul testi değildir.

## Görsel kontrol

Gerçek Qt uygulamasından, açıkça etiketli **sentetik test verisiyle** alındı.
Koyu/açık tema; 1920×1080 ve 820×560 kontrol edildi. Küçük pencerede yeni
ayar metni taşmıyor; açınım 3D'nin altındaki kaydırılabilir bölümde görünüyor.

![Koyu tema, kayıt öncesi açınım; sentetik veri](before-save-dark-wide.png)

![Dar pencere, açınım sekmesi; sentetik veri](before-save-light-small.png)
