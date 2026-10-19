# PDF aktarımı

Qt ekranı `pdf.process.export_drawings` ile bir yardımcı süreç başlatır. Kaynak
koddan `main.py --pdf-export-worker <istek.json>`, Windows paketinde aynı EXE'nin
özel çalışma biçimi kullanılır. Yardımcı süreç arayüz açmaz; ek kurulum gerektirmez.
İstek ve JSON satırı olayları özel geçici klasörde tutulup işlem sonunda silinir.
Windowed EXE'de stdout bulunması gerekmez. Yeni bağımlılık eklenmemiştir.

`pdf.exporter` mevcut SolidWorks oturumuna kendi COM apartment'ı içinde bağlanır.
Çizimin tüm sayfalarını benzersiz bir geçici PDF'e kaydeder; PDF başlığı ve dosya
sonu doğrulanınca çıktı yayımlanır. Üzerine yazma kapalıysa mevcut PDF korunur.
Önceden açık çizimler kapatılmaz; yalnız aktarımın açtığı çizim kapatılır ve önceki
aktif belge geri getirilir. Kaynak CAD dosyası kaydedilmez. Alt COM nesneleri belge
kapatılmadan, uygulama nesnesi de `CoUninitialize` çağrısından önce bırakılır.

## Beklenmedik kapanma

Eski akışta SolidWorks COM çağrıları arayüzle aynı süreçteydi. Yerel pywin32/COM
hataları Python `try/except` bloğunu aşarak GOKWORKS'ü kapatabilirdi. Ayrıca
uygulama nesnesinin `CoUninitialize` sırasında hâlâ tutulduğu bir yaşam süresi
hatası testle doğrulandı ve düzeltildi. Kullanıcının bildirdiği gerçek kapanmanın
kesin nedeni, gerçek Windows/SolidWorks hata kaydı olmadan doğrulanmış değildir.

Yeni akış, yardımcı sürecin temiz çıkışını beklemeden aktarımı tamamlandı olarak
göstermez. Yerel çökmede ana pencere kullanılabilir kalır; çıkış kodu ve son aşama
günlüğe yazılır. Tamamlanan ve önceden mevcut çıktılara dokunulmaz. Yalnız bu
aktarımın çıktı klasörü içindeki `.gokworks-<benzersiz kimlik>.pdf` geçici dosyası
temizlenir. Çökme sırasında SolidWorks'ün açtığı bir belge açık kalabilir; başka
bir süreçten belge kapatma denenmez.

**Durdur** iş birliğine dayalıdır: mevcut `SaveAs` çağrısı bitince sonraki dosyaya
geçilmez. COM içinde yanıt vermeyen bir kayıt zorla kesilmez. Bu durumda arayüz
açık kalır; işlem bitmeden ikinci bir CAD işi başlatılmaz.

## Tanılama

Windows: `%LOCALAPPDATA%\GOKWORKS\logs`. Bu konum yazılamazsa sistemin geçici
klasörü kullanılır. Ana pencere için `GOKWORKS-gui-*.log`, PDF süreci için
`GOKWORKS-pdf-worker-*.log` oluşturulur. Başarılı PDF sürecinin boş tanılama kaydı
silinir; eski kayıtlar döndürülür. Kayıtlar yereldir, otomatik gönderilmez.

Kalıcı çökme kaydı aşama, sıra numarası, çıkış kodu ve varsa Python yığın izini
içerir; CAD içeriği, COM nesneleri veya Python yerel değişkenleri yazılmaz. Kaynak
dosya yolları kullanıcıya gösterilen sonuçlarda bulunabilir; özel işlem dosyaları
iş sonunda silinir.

## Doğrulama

```bash
python -m pytest -q tests/test_pdf_exporter.py tests/test_pdf_process.py
QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_qt_workflows.py -k 'pdf or worker or close_cancel'
```

Süreç testlerinde gerçek alt süreçler çalıştırılır; CAD sınırında COM test
nesneleri kullanılır. Ani süreç çıkışı, bitiş mesajından sonraki çökme, yarım JSON,
parçalı UTF-8, durdurma, dosya güvenliği ve Qt'nin açık kalması kontrol edilir.
EXE paketleme kontrolü boş kaynak klasörüyle gerçek paketlenmiş PDF sürecini
başlatır; COM bağlantısı kurmaz. Gerçek Windows/SolidWorks oturumunda çok sayfalı,
önceden açık ve kapalı çizimlerin aktarımı ayrıca doğrulanmalıdır.
