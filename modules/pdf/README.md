# PDF aktarımı

Qt ekranı `pdf.process.export_drawings` ile bir yardımcı süreç başlatır. Kaynak
koddan `main.py --pdf-export-worker <istek.json>`, Windows paketinde aynı EXE'nin
özel çalışma biçimi kullanılır. Yardımcı süreç arayüz açmaz; ek kurulum gerektirmez.
Tek EXE dağıtımında PDF işçisi, ömrü boyunca açık kalan ana uygulamanın geçici
kaynaklarını yeniden kullanır. Çıkış izleyicisi bağımsız geçici kaynaklarla
başlatılır. İzlenen PID, onefile başlatıcısından değil `worker_ready` mesajındaki
gerçek Python işçisinden alınır; Windows hata olayı doğru süreçle eşleştirilir.
İstek ve JSON satırı olayları özel geçici klasörde tutulup işlem sonunda silinir.
Windowed EXE'de stdout bulunması gerekmez. Yeni bağımlılık eklenmemiştir.

`pdf.exporter` mevcut SolidWorks oturumuna kendi COM apartment'ı içinde bağlanır.
Çizimin tüm sayfalarını benzersiz bir geçici PDF'e kaydeder; PDF başlığı ve dosya
sonu doğrulanınca çıktı yayımlanır. Üzerine yazma kapalıysa mevcut PDF korunur.
Önceden açık çizimler kapatılmaz; yalnız aktarımın açtığı çizim kapatılır ve önceki
aktif belge geri getirilir. Kaynak CAD dosyası kaydedilmez. Alt COM nesneleri belge
kapatılmadan, uygulama nesnesi de `CoUninitialize` çağrısından önce bırakılır.

PDF kaydı, mevcutsa `IModelDocExtension.SaveAs3` ile yapılır. Gelişmiş kayıt
seçenekleri açıkça null `IDispatch` olarak iletilir. Tüm sayfalar
`swExportData_ExportAllSheets` ile seçilir; eski sürüm/yöntem uyumluluğunda
`SaveAs` ve bütün sayfa adlarını içeren `swExportData_ExportSpecifiedSheets`
kullanılır. Genel/ayrıntısız kayıt hatasında (kod 0/1) en fazla bir uyumluluk
denemesi yapılır. Kilit, salt okunur, biçim ve yol hataları tekrar edilmez.
Durdurma istenmişse ikinci kayıt başlatılmaz; yalnız aktif sayfayı kaydeden
bir yedek yöntem kullanılmaz. Sayfa seçimi, API sonucu ve PDF bütünlük
kontrolleri başarısızsa mevcut PDF korunur.

Geçici çıktı, hedefle aynı klasörde normal ve kısa `gokworks-<kimlik>.pdf`
adı kullanır. Çıktı klasörünün yazılabilirliği COM kaydından önce sınanır.
API hatası; kullanılan yöntem, hata bitleri, uyarı kodu ve kayıt klasörüyle
birlikte raporlanır. Kod 1 tek başına kök nedeni belirlemez; bu ortamda
kullanıcının canlı SolidWorks belgesiyle hata yeniden üretilememiştir.

## Beklenmedik kapanma

Eski akışta SolidWorks COM çağrıları arayüzle aynı süreçteydi. Yerel pywin32/COM
hataları Python `try/except` bloğunu aşarak GOKWORKS'ü kapatabilirdi. Ayrıca
uygulama nesnesinin `CoUninitialize` sırasında hâlâ tutulduğu bir yaşam süresi
hatası testle doğrulandı ve düzeltildi. Kullanıcının bildirdiği gerçek kapanmanın
kesin nedeni, mevcut günlüklerde işletim sisteminin çıkış bilgisi bulunmadığı
için henüz doğrulanmış değildir.

Yeni akış, yardımcı sürecin temiz çıkışını beklemeden aktarımı tamamlandı olarak
göstermez. Yalnız PDF yardımcısı çöktüğünde ana pencere kullanılabilir kalır;
çıkış kodu ve son aşama
günlüğe yazılır. Tamamlanan ve önceden mevcut çıktılara dokunulmaz. Yalnız bu
aktarımın çıktı klasörü içindeki `gokworks-<benzersiz kimlik>.pdf` geçici dosyası
temizlenir. Çökme sırasında SolidWorks'ün açtığı bir belge açık kalabilir; başka
bir süreçten belge kapatma denenmez.

**Durdur** iş birliğine dayalıdır: mevcut `SaveAs` çağrısı bitince sonraki dosyaya
geçilmez. COM içinde yanıt vermeyen bir kayıt zorla kesilmez. Bu durumda arayüz
açık kalır; işlem bitmeden ikinci bir CAD işi başlatılmaz.

Qt iş yöneticisi, `QThread.finished` sinyalinden sonra işletim sistemi iş
parçacığının da tamamen bitmesini `wait(0)` ile kontrol eder. Sinyal, native
thread-local temizliğinden önce gelebilir. Temizlik sürerken iş kilidi ve nesne
referansları korunur; GUI'yi bloklamak yerine kısa Qt zamanlayıcısıyla yeniden
kontrol edilir. QThread ancak bu aşamadan sonra silinir. Bu sıra PDF dahil bütün
arka plan işlerinde uygulanır.

Linux üzerinde gerçek bir C++ thread-local yıkıcısını 300 ms geciktiren deneyde
eski akış, temizlik bitmeden boşta/iş bitti bildirimlerini gönderiyordu. Yeni
akışta her iki bildirim de native temizlikten sonra gönderildi. Hedefli Qt
kontrolleri; kilidin korunmasını, arayüzün çalışmasını, iptali ve sıradaki K/R
işlemlerini kapsar. Bu deney, kullanıcının Windows'taki kapanmasının kesin
nedenini tek başına doğrulamaz; güncel GUI/PDF kayıtlarıyla eşleştirilmelidir.

## Tanılama

Windows: `%LOCALAPPDATA%\GOKWORKS\logs`. Bu konum yazılamazsa sistemin geçici
klasörü kullanılır. Ana pencere için `GOKWORKS-gui-*.log`, PDF süreci için
`GOKWORKS-pdf-worker-*.log` oluşturulur. Başarılı aktarım kayıtları da tutulur;
eski kayıtlar döndürülür. Kayıtlar yereldir, otomatik gönderilmez.

Kalıcı çökme kaydı aşama, sıra numarası, çıkış kodu ve varsa Python yığın izini
içerir; CAD içeriği, COM nesneleri veya Python yerel değişkenleri yazılmaz. Kaynak
dosya yolları kullanıcıya gösterilen sonuçlarda bulunabilir; özel işlem dosyaları
iş sonunda silinir.

PDF işçisi her API aşamasını `pdf_phase` olarak kendi kalıcı kaydına yazar.
Ana süreç; iş başlangıcı/bitişi, PDF işçisiyle iletişim, tablo olaylarının
öncesi/sonrası ve pencerenin normal kapanışını ayrı işaretler. Böylece ana süreç
kesilse bile geçici işlem klasörüne bağlı kalmadan son aşama görülebilir.

Qt'nin ölümcül `qFatal` mesajı, Windows'ta Python istisnası üretmeden süreci
sonlandırabilir. Ana arayüzdeki Qt mesaj işleyicisi bu mesajı ve Python çağrı
yığınını Qt sonlandırmasından **önce** kaydeder. Genel widget metinleri kayda
alınmaz; tanınan Qt çalışma zamanı mesajlarındaki nesne adları/yollar temizlenir.
Yalnız `role=... pid=... python=...` satırı içeren bir eski kayıt, kapanmanın
nedenini belirlemez. Windows Application Error (olay 1000) kaydındaki uygulama,
hatalı modül ve istisna kodu ayrıca incelenmelidir.

Windows'ta GUI ve PDF işçisi için ayrı, arayüz açmayan bir çıkış izleyicisi
başlatılır. İzleyici süreç başlamadan önce alınmış yalnız sorgulama/bekleme
yetkili süreç tanıtıcısını devralır; PID yeniden kullanılsa bile aynı sürecin
gerçek çıkış kodunu (`process_exit`, ondalık ve hex) günlüğe ekler. Qt/COM
yüklemez; hiçbir süreci sonlandırmaz ve CAD dosyalarına erişmez. Normal çalışmada
işletim sisteminde uyur; GUI iş parçacığını bekletmez. Tanılama başlatılamazsa
aktarım engellenmez (`process_watch_unavailable`).

Çıkış kodu sıfır değilse izleyici en fazla altı saniye boyunca Windows Application
Error olay 1000 kaydını arar. Yalnız PID ve süreç oluşturulma zamanı eşleşen
olayın hatalı DLL/EXE adı ve istisna
kodu alınır; olayın ham XML'i, kişisel dosya yolları ve CAD verileri kaydedilmez.
Olay bulunmaması, Defender veya başka bir programın kapattığını kanıtlamaz.
İzleyici de birlikte zorla kapatılırsa bu kayıt alınamayabilir.

19 Ekim 2026 tarihli altı kullanıcı kaydının karşılaştırmasında eski üç kayıt
yalnız başlangıç satırından oluşuyordu. Bir yeni GUI kaydı yalnız açılışı
gösteriyordu. Eşleşen diğer GUI/PDF kayıtlarında ilk iki PDF'nin doğrulanıp
yayımlandığı ve tamamlandığı; üçüncünün doğrulanıp `publish_pdf` aşamasına geldiği
görüldü. Normal kapanış, Python istisnası, Qt fatal veya süreç çıkış kodu yoktu.
Bu nedenle bu kayıtlardan tek başına gerçek kapanma nedeni belirlenemez; bu
olay, daha önce düzeltilen QThread kapanış hatasını da doğrulamamaktadır.

## Doğrulama

```bash
python -m pytest -q modules/pdf/tests/test_pdf_exporter.py modules/pdf/tests/test_pdf_process.py
python -m pytest -q tests/test_process_watch.py
QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_qt_workflows.py -k 'pdf or worker or close_cancel'
```

Süreç testlerinde gerçek alt süreçler çalıştırılır; CAD sınırında COM test
nesneleri kullanılır. Ani süreç çıkışı, bitiş mesajından sonraki çökme, yarım JSON,
parçalı UTF-8, durdurma, dosya güvenliği ve Qt'nin açık kalması kontrol edilir.
EXE paketleme kontrolü boş kaynak klasörüyle gerçek paketlenmiş PDF sürecini
başlatır; COM bağlantısı kurmaz. Gerçek Windows/SolidWorks oturumunda çok sayfalı,
önceden açık ve kapalı çizimlerin aktarımı ayrıca doğrulanmalıdır.

Çıkış izleyicisinin iki gerçek süreç/tanıtıcı testi yalnız Windows'ta çalışır;
normal ve `0xC0000409` çıkışlarının Python kapanış kancaları olmadan da
kaydedildiğini kontrol eder. Linux'ta bunlar atlanır; bu ortamda yalnız olay
ayrıştırma, gizlilik, hata yalıtımı ve CLI ayrımı doğrulanabilir. Gerçek
SolidWorks kapanmasının düzeldiği bu testlere dayanarak söylenemez.

`test_pdf_windows.py`, gerçek pywin32 `VARIANT` nesneleriyle Türkçe sayfa
adlarını, BYREF hata/uyarılarını ve null `IDispatch` aktarımını Windows'ta
doğrular. `Windows PDF export` iş akışı bu testleri, süreç testlerini ve ilgili
Qt iptal/kapanış testlerini çalıştırır; SolidWorks kurulumu veya lisansı yoktur.

Canlı entegrasyon testi için Windows'ta SolidWorks'te kaydedilmiş bir teknik
resmi aktif bırakıp aşağıdaki komut çalıştırılabilir. Test, geçici PDF'nin
sayfa sayısını gerçek çizimin sayfalarıyla karşılaştırır; kaynak dosyanın
özetini, kaydedilmemiş değişiklik bayrağını ve aktif belgeyi kontrol eder.
Kaynak teknik resmi kaydetmez veya kapatmaz. Bu test varsayılan olarak atlanır;
çalıştırılmamış olması canlı CAD doğrulaması olarak raporlanamaz.

```powershell
$env:GOKWORKS_PDF_LIVE_TEST = '1'
.venv\Scripts\python.exe -m pytest -q modules/pdf/tests/test_pdf_solidworks.py
```
