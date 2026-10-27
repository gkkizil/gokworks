# Profil kesim: anlaşılır giriş ve okunabilir kesim planı

27 Ekim 2026. Gerçek PySide6 / Qt Widgets uygulamasında uygulanan arayüz
düzenlemesi. İnceleme tabanı: `98912be7ff48f76094a6669eb16d6f063b2febfc`.
Hedef: ilk kez kullanan kişinin parça boyunu satın alınan çubuğun boyuyla
karıştırmadan liste oluşturması ve hesaplanan planı okuyabilmesi.

## Yeni kullanım akışı

1. **Parçalar ve stok → Parça ekle:** profil kesiti, malzeme, tek parçanın
   boyu ve adet. Örneğin `40×40×2 / S235JR / 1200 mm / 4 adet`.
2. Sağdaki **Ham profil ve kesim payı:** satın alınan tek çubuk için
   `6000 mm` (6 metre), testere için örneğin `3 mm`. Uç düzeltme isteğe
   bağlıdır ve her iki uçtan ayrı düşülür.
3. **Kesim planını hesapla:** gereken çubuk sayısını, artan boyu ve kayıpları
   görün. Çubuk listesinden seçim yapıp çizimle birlikte gerçek kesim
   sırasını okuyun. Sonuç CSV olarak kaydedilebilir.

**Örnekle dene** açıkça örnek veri yükler: `1200 × 4 + 800 × 6`,
`6000 mm` stok ve `3 mm` testere payıyla **2 çubuk, 10 parça,
2370 mm artan profil ve 30 mm testere kaybı**. Dolu listeyi değiştirmeden
önce onay istenir. Manuel kullanım için SolidWorks gerekmez.

![Parçalar ve stok](after/03-parts-dark.png)

![Kesim planı](after/04-plan-dark.png)

## Ekran kanıtına dayalı inceleme

Görseller tasarım taslağı değildir. Aynı gerçek uygulamanın başlangıç
sürümü ve yeni kaynak kodu ayrı süreçlerde çalıştırılıp yakalandı.
Başlangıç kodu yukarıdaki commit'ten geçici bir dizine okunarak yeniden
çalıştırıldı; çalışma ağacı geri alınmadı. CAD sonuç ekranındaki satırlar
**“ÖRNEK — gerçek CAD verisi değildir”** olarak etiketlenmiştir.

| Adım / önem | Önceki problem ve kullanıcı etkisi | Uygulanan düzenleme / kanıt |
| --- | --- | --- |
| 1. Listeye başlama · yüksek | Stok ve kayıp alanlarının tablonun üstünde aynı ağırlıkta durması, parça boyu ile ham boy ayrımını zorlaştırıyordu. [Önce](before/01-empty-dark.png). | Solda parça listesi, sağda ham çubuk ayarları; üç adımlı yönerge, boş durum ve açık örnek. **6 metre = 6000 mm** açıklaması sürekli görünür. [Sonra](after/01-empty-dark.png), [dolu liste](after/03-parts-dark.png). |
| 2. Parça girme · yüksek | Dokuz alanın aynı anda açılması ve önceden yazılmış üretim değerleri, ilk girişte gereksiz yük oluşturuyordu. [Önce](before/02-add-part-dark.png). | Dört gerekli alan; üretim ölçüsü/kalitesi için yalnız örnek yer tutucular. Standart, stok kodu, et, ilave boy ve not açılır bölümde. Açık kesitle çelişen et değeri düzeltilmeden kabul edilmez. [Sonra](after/02-add-part-dark.png). |
| 3. Planı okuma · yüksek | Sonuç tablosundaki sıkıştırılmış kesim ifadesi ve yöntem adı, atölyede kesim sırasını anlamayı zorlaştırıyordu. [Önce](before/04-plan-dark.png). | Çubuk/parça adediyle başlayan sonuç, ayrı artan/testere/uç kayıpları, ölçekli çizim ve sıralanamayan kesim sırası tablosu. Minimum iddiası yalnız motor bunu doğruladığında gösterilir. [Sonra](after/04-plan-dark.png). |
| 4. CAD'den alma · orta | İki satıra yayılan altı geniş komut ve teknik alan adları, sıradaki işlemi belirsizleştiriyordu. [Önce](before/05-solidworks-dark.png). | Üç kompakt okuma komutu, isteğe bağlı ileri seçenekler, **Kontrol gerekiyor** filtresi ve hazır satır sayısını söyleyen ekleme düğmesi. Kaynak bilgisi araç ipucunda korunur. [Sonra](after/05-source-dark.png). |
| 5. Dar ekran / tema · orta | Her bölümün aynı düzeni koruması sonuç çizimiyle tabloların alanını sınırlıyordu. [Önce](before/07-plan-small-light.png). | Girişte yeniden boyutlandırılabilir yatay paneller; dar sonuç ekranında dikey sıralama ve kaydırma. [1024 açık giriş](after/08-parts-small-light.png), [1024 açık sonuç](after/09-plan-small-light.png), [820 koyu giriş](after/10-parts-minimum-dark.png), [820 koyu sonuç](after/11-plan-minimum-dark.png). |

Ek işlevsel düzeltme: girdiler değiştiğinde eski planın grafik renderer'ı
da temizlenir. Pencere yeniden boyutlandırılınca geçersiz çizim geri gelmez.
Geçersiz uç düzeltme ilgili alanı açar; parça stoktan uzunsa kullanıcı
boş sonuç ekranında bırakılmadan giriş sayfasına yönlendirilir.
Kesit/et çelişkisi hücre düzenlemesinde de reddedilir; ilgili iki değerin
birlikte değiştirilebildiği **Düzenle** penceresine yönlendirilir.

## Kapsam ve sözleşmeler

- `modules/profile_cutting/ui.py`: üç mevcut sekmenin indeksleri korunarak
  giriş, isteğe bağlı CAD alma ve sonuç akışı yeniden düzenlendi.
- `modules/profile_cutting/dialogs.py`: sade manuel giriş, kaydın kimliğini
  koruyan düzenleme ve ayrı zorunlu CAD kontrolü.
- `modules/profile_cutting/widgets.py`: boy biçimleme, kayıp özeti ve gerçek
  kesim sırasını gösteren ortak Qt bileşeni. Yeni bağımlılık eklenmedi.
- `modules/profile_cutting/tests/test_workflow_ui.py`: 12 yeni kullanıcı
  akışı regresyon testi.
- `.github/workflows/windows-bom.yml`: profil testleri Windows kontrolüne
  eklendi. `.github/workflows/windows-shaft-bridge.yml`: aynı kaynak için
  Windows kontrollerinin tetiklenmesi sağlandı. Kontroller kaldırılmadı.

`optimizer.py`, `models.py`, `scanner.py`, `properties.py`, `solidworks.py`,
`storage.py` ve `geometry.py` değişmedi. Mevcut `.gokprofile` JSON ve CSV
biçimleri, Decimal hesap, gruplama, tekrar aktarım engeli ve COM/STA sınırı
korundu. CAD satırları yeniden aktarılırken manuel liste silinmez.
Tablo görüntü başlıkları değişse de dahili durum değerleri değişmedi.

Motor sabit boy ve yeterli sayıda ham çubuk varsayar; sonlu envanter,
karma satın alma boyları veya gönye CAM çözümü eklenmedi. Arayüz bu
varsayımı gösterir. İlave boy, testere payından ayrı tutulur.

Paylaşılan korumalı 11 dosya hem mevcut taban commit'i hem kayıtlı SHA256
listesiyle karşılaştırıldı; tümü değişmedi. [Kapsam kontrolü](scope-checks.json).

## Çalıştırılan kontroller

Linux / Python 3.13.5 / PySide6 6.10.3 / `QT_QPA_PLATFORM=offscreen`:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=.cache/runtime-updated \
  /workspace/.cloud-setup/qt-venv/bin/python packaging/run_windows_tests.py \
  modules/profile_cutting/tests tests/test_fusion_workbench.py

QT_QPA_PLATFORM=offscreen PYTHONPATH=.cache/runtime-updated \
  /workspace/.cloud-setup/qt-venv/bin/python main.py --self-check /tmp/gokworks-profile-source-smoke.json
```

- **125 test kaydı: 124 başarılı, 0 hata, 1 atlanan.** Sekiz sınırlı test
  süreci çıkış kodu 0. [JUnit](tests.xml), [çalıştırıcı çıktısı](tests.log).
  Çalıştırıcının adı `run_windows_tests.py` olsa da bu sonuç **Linux**'ta alındı.
- **12 yeni Qt akışı:** gerçek optimizasyonla örnek plan, dört alanla manuel
  giriş, kaynak kimliği korunan düzenleme, geçersiz grafiğin resize sonrası
  dönmemesi, örneğin dolu listeyi onaysız silmemesi, ayrı kayıplar,
  mock-COM tarama/filtre/ekleme, gerçek CSV worker, hatalı uç düzeltme,
  stoktan uzun parça, minimumu ispatlanmamış plan, kesit/et tutarlılığı.
- **Uygulama self-check başarılı:** 15 modül, iki tema ve dört çözünürlük
  (1024×700, 1366×768, 1920×1080, 2560×1440).
  [Makine raporu](source-smoke.json). Bu başlangıç ve örnek iş akışı
  kontrolüdür; bütün modüllerde gerçek CAD entegrasyonu testi değildir.
- Son görseller gerçek Qt uygulamasından 1440×900, 1024×700 ve 820×560
  boyutlarında alındı. [Manifest](after/capture.json),
  [yeniden üretim aracı](../../report-tools/capture_profile_workflow.py).
- Ruff `F821,F822,F823` ve `git diff --check` başarılı.

## Doğrulanamayanlar ve yayımlama durumu

- Atlanan tek test, kurulu/lisanslı SolidWorks ve açıkça seçilmiş gerçek
  Weldment dosyası gerektiren canlı testtir. Burada çalıştırılmadı.
- Windows yerel ekranı, Windows DPI ölçekleri, gerçek SolidWorks okuma ve
  yeni arayüzün donmuş EXE çalışması bu Linux sonuçlarından çıkarılamaz.
- Bu görev için yeni EXE oluşturulmadı. Önceden verilen EXE bu arayüz
  değişikliğini içermez.
- GitHub oturumunun `GH_TOKEN` doğrulaması başarısız oldu. Bu rapor
  hazırlanırken `main` gönderimi ve yeni Windows CI çalışması bekliyordu;
  bu nedenle uzak depo güncellendi veya Windows geçti denmiyor.
- Klavye/hücre düzenleme ve yerel bileşenler korunmuştur. Görsel inceleme
  tek başına ekran okuyucu veya tam erişilebilirlik uygunluğu kanıtı değildir.

Sonraki doğrulama: GitHub bağlantısı yenilendiğinde `main`'e gönderim,
aynı commit için Windows testleri ve kullanıcıya ait bir Weldment test
kopyasıyla okuma → kontrol → listeye ekleme → plan/CSV akışı.
