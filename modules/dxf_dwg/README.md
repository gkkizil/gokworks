# DXF / DWG — Sac kalınlığına göre klasörleme

## Aktarımda otomatik kayıt ve durdurma

**Aktarımı başlat**, kullanıcının istediği sessiz **Tümünü Kaydet** davranışını
uygular: açık değiştirilmiş SLDPRT/SLDASM/SLDDRW belgeleri, mevcut kaydedilmemiş
düzenlemeler dahil, kendi yollarına kaydedilir. API `GetSaveFlag` ve
`Save3(Silent | SaveReferenced)` kullanır; ekran düğmesine tıklamaz. Kayıt,
parça açılmadan, aktarım öncesinde ve kapatmadan önce kontrol edilir. Alt parça
kaydının montajı değiştirilmiş işaretleyebildiği durumlar tekrar okunur.

İsimsiz, salt okunur veya kaydı başarısız belgelerde Farklı Kaydet penceresi
açılmaz; dosya adı uydurulmaz. Hata günlüğe yazılır, belge açık bırakılır ve
sonraki parçalara geçilmez. Açınımın değiştirdiği konfigürasyon her biçimden
sonra geri alınır; bu doğrulanmadan kaynak kaydedilmez/kapatılmaz.

**Durdur**, yeni biçim/parça başlatılmasını ve geçici çıktının yayımlanmasını
engeller. Önizlemenin bekleyen istekleri ve eski seçim sonuçları iptal edilir;
dosya değişikliği/sonuç güncellemesi önizlemeyi kendiliğinden yeniden başlatmaz.
Yeni seçim veya **Yenile** kullanıcı isteğiyle tekrar çalıştırır.

3D önce ayrı okunur ve kaynak durumu geri getirildikten sonra gösterilir;
geçici DXF açınımını beklemez. Windows önizleme STA'sında
`CoEnableCallCancellation` / `CoGetCancelObject.Cancel` ile bekleyen okunur
COM çağrısına iptal istenir; 60 saniyelik süre sınırı vardır. SolidWorks veya
thread zorla sonlandırılmaz. Native sunucunun iptal edemediği işlemde oturum
geri alınmadan CAD kilidi bırakılmaz; geri alma hatası iptal gibi gizlenmez.
Gerçek SolidWorks sunucusunun iptal davranışı ayrıca canlı test gerektirir.
Önizleme, aktarımın otomatik kayıt politikasını çağırmaz; kaynakları kaydetmez.

## SolidWorks 3D / açınım önizlemesi

Listeden bir kaynak veya sonuç satırı seçildiğinde sağda üç bölüm açılır:
gerçek bükülmüş SolidWorks gövdesi, açınım ve parça bilgileri. Dar pencerede
**Önizleme** sekmesi/üst düğmesi kullanılır; panelin içi kaydırılabilir.

- Sol fare: döndür; sağ/orta fare: kaydır; tekerlek: yakınlaştır.
- İzometrik, ön/arka/sağ/sol/üst/alt, **Sığdır**, perspektif/ortografik ve
  kenar çizgileri desteklenir. **Yenile** güncel kaynak verisini tekrar okur.
- 3D, DXF'ten türetilmez: seçilen SLDPRT, konfigürasyon ve sac gövdesinin
  `IFace2.GetTessTriangles` verisidir. Gerektiğinde `IBody2.GetTessellation`
  ile özel bir bellek tessellation nesnesi oluşturulur. Kullanıcı görüntü
  kalitesi ayarı değiştirilmez. Metre koordinatları mm'ye çevrilir.
- Açınım normalde üretilmiş DXF'ten okunur. DWG için DWG dosyası çözülmez:
  aynı kaynak/konfigürasyondan mevcut SolidWorks aktarım API'siyle geçici
  DXF üretilir. Aktarım öncesi önizleme de bu yöntemi kullanır. Bu fark
  panelde açıkça yazılır; geçici dosya silinir, üretim çıktısı değiştirilmez.
- Parça kodu/açıklama/malzeme/büküm sayısı çözümlenmiş property'lerden,
  kalınlık aktif SheetMetal verisinden, adet mevcut aktarım sonucundan gelir.
  Okunamayan bilgi uydurulmaz. Dosya adından alınan kod ayrıca belirtilir.
- Kaynak değişirse çıktı eski olarak işaretlenir; eski seçimin geciken
  sonucu yeni parçayı boyamaz. Önbellek dosya, konfigürasyon, gövde ve canlı
  güncelleme kimliğiyle doğrulanır; en fazla 8 mesh / 32 MiB tutar.

Mevcut tek gövdeli aktarım sınırı korunur. Çok gövdeli kaynağın yalnız açık
kalıcı gövde kimliğiyle eşleşen önizlemesi kabul edilir; eşleşme yoksa hata
gösterilir. Açınım konfigürasyonundan yalnız gerçek türetilmiş-üst ilişkisi
izlenir; bükülmüş konfigürasyon adı tahmin edilmez veya FlatPattern bastırılmaz.
Geçici konfigürasyon ve önceki aktif belge geri alınır; kaynak kaydedilmez.

Görüntüleme yerel Qt/OpenGL'dir; uygun sürücü yoksa GUI dışındaki bir thread'de
derinlik tamponlu CPU çizimi kullanılır. WebEngine, sunucu, CDN veya yeni bir
SolidWorks oturumu yoktur. Büyük mesh'lerde CPU yedeği daha yavaş olabilir.
Mesh 120.000 üçgenle sınırlıdır. Önizleme ve yaklaşık DXF çizgi toplamı,
imalat ölçümü veya geometri eşdeğerliği sertifikası değildir.

[Mimari, kaynak incelemesi, testler ve canlı Windows kontrolü](../../docs/dxf-3d-preview/README.md).

## Çıktı klasörleri

**DXF / DWG → Sac kalınlığına göre klasörle** seçeneği
açıkken uygulama, sacın SolidWorks'ten okunan gerçek kalınlığına göre çıktı
klasörleri oluşturur. Başlangıçta açıktır; tercih kaydedilir.

```text
Çıktı/
  1,5 mm/
    BRAKET - 1.5 mm - 12 adet.dxf
  2 mm/
    KAPAK - 2 mm - 3 adet.dxf
    Alt montaj/
      DESTEK - 2 mm - 6 adet.dxf
```

Klasör adında Türkçe ondalık virgül, mevcut dosya adlarında ondalık nokta
kullanılır. DXF ve DWG aynı kurala uyar; seçtiğiniz biçim kaydedilir.
Kaynak alt klasörler kalınlık klasörünün içinde korunur: farklı kaynak
klasörlerindeki aynı adlı parçalar birbirinin üzerine yazılmaz.

Seçenek kapalıysa önceki çıktı düzeni kullanılır: kaynak alt klasör yapısı,
seçtiğiniz çıktı klasörünün altında korunur. PDF aktarımı bu seçenekten etkilenmez.

Mevcut dosyaları atlama ve güvenli üzerine yazma kuralları seçilen hedef
klasörde uygulanır. Sonuç listesi, dosya ayrıntıları ve CSV raporu gerçek
çıktı yolunu gösterir. Kalınlık okunamazsa, geçersizse veya parçada birden
fazla farklı kalınlık varsa tahmini bir klasöre aktarım yapılmaz; hata bildirilir.

[Genel kullanım ve SolidWorks kontrol adımları](../../README.md#sac-metal-açınımı) ·
[Aktarım yöntemi ve kaynak karşılaştırması](../../docs/dxf-dwg-verification.md).

Bu eklemede **12 ilgili kontrol geçti**: 8 aktarım/yol kontrolü ve 4 gerçek
Tk arayüz kontrolü. Karışık kalınlıklar, aynı adlı kaynak alt klasörleri,
DXF/DWG çıktıları, geçersiz kalınlık, mevcut dosyaları atlama, güvenli üzerine
yazma, CSV yolu, tercih kaydı, sayfa önbelleği ve PDF ayrımı doğrulandı.
Aktarım kontrolleri SolidWorks COM davranışını temsil eden test nesneleriyle
yapıldı; gerçek Windows/SolidWorks aktarımı bu bulut ortamında çalıştırılmadı.
EXE oluşturulmadı.

[Klasörleme seçeneğinin güncel ekran görüntüsü](examples/thickness-folders-dark.png).
Görüntü, kullanıcı tercihlerini değiştirmeden
`python modules/dxf_dwg/examples/capture.py` ile gerçek Tk ekranından yeniden alınabilir.
