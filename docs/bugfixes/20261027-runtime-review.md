# DXF/DWG kayıt, önizleme, iptal ve uygulama genel kontrolü

Dal `main`; son uygulama kaynağı `50611d6efd5b287faf5fd05db25f98f3c01ca007`.

## Yapılan düzeltmeler

- **Tümünü Kaydet:** DXF/DWG toplu aktarımının kullanıcı tarafından istenen
  davranışı açık değiştirilmiş native belgeleri sessiz kaydeder. `GetDocuments`,
  `GetSaveFlag`, `IsOpenedReadOnly`, `Save3(Silent|SaveReferenced)` kullanılır.
  Kayıt penceresi/tuş taklidi, rastgele Farklı Kaydet yolu veya kalıcı CAD
  tercih değişikliği yoktur. Daha önceki kullanıcı düzenlemeleri de bu
  açıkça istenen Save All kapsamındadır; arayüzde belirtilir.
- Her kayıt sonrası bayraklar tekrar okunur. Bir alt parçanın kaydının
  montajı sonradan değiştirilmiş yapması ve SaveReferenced kayıtları desteklenir.
  Kayıt hatası, isimsiz veya salt okunur belgede sonraki işlere geçilmez;
  mevcut düzenlemeler kapatılarak atılmaz. Dosya kayıt uyarıları rapora eklenir.
- Açılma hatası veren veya gövdesi doğrulanmayan **yeni yüklenmiş** bir model,
  cleanup sırasında otomatik kaydedilmez. Başarısız OpenDoc6 sonucu diske
  yazılmamalıdır. Bu durumlar için disk içeriğini koruyan testler eklendi.
- Native DXF/DWG API'sinin değiştirdiği aktif konfigürasyon **her biçimden
  sonra**, sonraki biçimden/kayıttan önce geri alınır ve doğrulanır. Geri alma
  başarısızsa kaynak kaydedilmez/kapatılmaz. Sonuçların kaynak dosya/güncelleme
  kimliği otomatik kayıttan sonra yenilenir; yeni çıktı hemen eski sanılmaz.
- **3D önce gösterilir:** bükülmüş gövde bağımsız okunur, tüm kaynak durumu
  geri alındıktan sonra GUI'ye iletilir. Sonraki açınım okuması/native geçici
  DXF işlemi bu ilk 3D'yi bekletmez. `EventSink.flush` ile ilk sonuç, sonraki
  COM çağrısından önce gerçekten GUI'ye gönderilir. COM nesnesi GUI'ye taşınmaz.
- **Durdur:** bekleyen/otomatik önizlemeleri, ertelenmiş aktarımı ve eski seçim
  sonuçlarını iptal eder. Sonuç güncellemesi ve QFileSystemWatcher olayı
  durdurulan işi kendiliğinden başlatamaz. Yeni seçim/Yenile tekrar çalıştırır.
  Durdurma alındığında düğme tekrar tekrar komut göndermez; yalnız native
  thread temizliği bitince durum Durduruldu olur.
- Format/parça sınırlarında iptal kontrolü vardır. Native çağrıdan dönen
  geçici çıktı, iptal edilmişse yayımlanmaz; sonraki DXF/DWG biçimine geçilmez.
- Windows okunur önizleme STA'sında `CoEnableCallCancellation` ve ayrı bir
  iptal STA'sında `CoGetCancelObject(thread_id).Cancel(0)` kullanılır. Stop veya
  60 saniyede iptal **istenir**. Bu, hard-kill veya sunucunun mutlaka iptal
  ettiğinin kanıtı değildir. SolidWorks/worker thread zorla sonlandırılmaz.
  Kaynak geri alınmadan CAD kilidi serbest bırakılmaz.
- Kaynak/COM temizleme hatası iptal mesajıyla gizlenmez. Bilinen bir geri alma
  hatasının ardından sessiz kayıt başlatılması engellenir; kaynak kontrolü ve
  başarılı yeniden okuma gerekir. Önizleme kaynakları kaydetmez.

JSON v1 mil/diğer hesap modelleri, hesap motorları, PDF process izolasyonu,
Pack and Go, Weldments ve bağlantı helper'ı korunmuştur. Korunan 11 ortak
kaynak dosyanın hash'leri aynıdır. `release` veya yedek depo değiştirilmedi.

## Uygulama genelinde tarama ve doğrulama

- Tüm takip edilen/yeni Python kaynakları AST üzerinden derlendi: sözdizimi
  hatası ve eager içe aktarma döngüsü yok. Sayılar makine özetindedir.
  Riskli API isimlerinin bulunması otomatik güvenlik açığı iddiası sayılmadı.
- Genel regresyon: **1.584 pytest öğesi / 2.462 JUnit kaydı; 0 hata/başarısızlık,
  45 atlama**. Subtest kayıtları ayrıca sayılır. Tüm hesap/üretim/aktarım
  modülleri ve mevcut iş başlatma, iptal, kapatma, hata sonrası toparlanma
  senaryoları bu taramaya dahildir. [Arşiv: Genel JUnit](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261027-runtime-global-tests.xml).
- Genel tarama sürerken eklenen son iptal-cleanup ve doğrulanmamış-yükleme
  korumaları ayrıca **son kaynakta tüm DXF paketiyle** sınandı:
  **226 kayıt, 0 hata/başarısızlık, 3 atlama**.
  [Arşiv: Son DXF JUnit](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261027-runtime-dxf-tests.xml).
- Gerçek Qt kaynak uygulaması `main.py --self-check` ile açıldı:
  **15 modül, koyu/açık tema, 1024×700, 1366×768, 1920×1080, 2560×1440**.
  Formül/dışa aktarma/clipboard ve kuyruk kontrolleri de geçti.
  [Kaynak smoke](20261027-runtime-source-smoke.json). Bu EXE değildir.
- Ruff F821/F822/F823 ve git whitespace denetimi geçti.
- [Windows DXF/BOM/Qt](https://github.com/gkkizil/gokworks/actions/runs/40456185382)
  ve [Windows STA/köprü](https://github.com/gkkizil/gokworks/actions/runs/40456185374)
  son kaynakta başarılıdır: **321 kayıt, 0 hata/başarısızlık, 3 atlama**;
  STA/köprü işi de başarılı. Sonuçlar [makine özetindedir](20261027-runtime-checks.json). Windows testi mock CAD sınırı, gerçek Qt ve pywin32 COM runtime'ını
  kapsar; gerçek SolidWorks oturumu kurulduğu anlamına gelmez.

## Gerçek ortam sınırları

Bu ortamda lisanslı SolidWorks yoktur. Kullanıcının gerçek BTFM parçalarıyla
Save All, açınım, tessellation ve iptal davranışı **çalıştırılmadı**.
[Microsoft ICancelMethodCalls.Cancel sözleşmesi](https://learn.microsoft.com/en-us/windows/win32/api/objidl/nf-objidl-icancelmethodcalls-cancel)
S_OK'un yalnız istek yapıldığını belirttiğini açıklar; sunucunun davranışı
uygulayıcıya bağlıdır. İptal edilemeyen native kernel/diyalog çağrısı kaynak
geri alma işlemini geciktirebilir. Başarı veya anlık zorla durdurma uydurulmaz.
Sessiz Save All gelecekteki kayıt istemlerini önlemek içindir; hâlihazırda
SolidWorks'te açık modal pencereye tıklayan bir UI robotu eklenmedi.

Kullanıcının **EXE oluşturma** talimatıyla derleme isteği `cancelled=true`
yapıldı ve Windows workflow'una buna göre build job'unu atlayan bir kapı
eklendi. Önceden başlamış EXE derlemesi durdurma ulaşmadan tamamlanmıştı;
bundan sonra yeni EXE istenmedi. Bu düzeltmeler `main` kodu olarak sunulur.
