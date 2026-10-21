# Gömülü Pack and Go interop yolu

19 Ekim 2026. Yeni bir arayüz veya bağımsız kullanıcı uygulaması değildir.
GOKWORKS isimlendirme işçisinin kullandığı, kısa ömürlü STA .NET istemcisidir.

## Hangi hatayı ele alır?

`IModelDocExtension.GetPackAndGo` sıfır giriş parametresi alır. Buna rağmen
kullanıcının Automation çağrısı `-2147352561 / DISP_E_PARAMNOTOPTIONAL`
döndürüyor; aynı sunucunun tür bilgisi de `-2147352565` ile okunamıyor.
Eski yol, tür bilgisi alınamayınca yine aynı başarısız `InvokeTypes` çağrısına
dönüyordu. Canlı SolidWorks'ün bu davranışının iç nedeni doğrulanmış değildir.

Bu belirli parametre bağlama hatasında, başka parametreler tahmin edilmez.
SolidWorks kurulumundaki gerçek `SolidWorks.Interop.sldworks.dll` yüklenerek
`IModelDocExtension.GetPackAndGo()` **güçlü türlenmiş dual arayüzden** çağrılır.
C# `dynamic`, reflection Invoke veya aynı Automation çağrısı kullanılmaz.
Farklı API hataları rastgele tekrar denenmez; asıl hata korunur.

## Çalışma ve gereksinimler

- Windows 10/11 x64'ün Windows PowerShell 5.1/.NET Framework ortamı kullanılır.
  Yeni Python bağımlılığı, ayrı .NET SDK kurulumu veya bulut bağlantısı gerekmez.
- DLL, bağlı SolidWorks işleminin gerçek `SLDWORKS.exe` yoluna göre yalnız
  `api/redist` veya kurulumun ana dizininden bulunur. Başka bir SolidWorks yılı
  veya internetten indirilen DLL, uygulamanın çalışma zamanında kullanılmaz.
- Bu SolidWorks DLL'si GOKWORKS'e kopyalanmaz veya EXE ile dağıtılmaz.
  API interop bileşeni kurulumda yoksa anlaşılır hata verilir.
- Yardımcı kod kaynak olarak pakete dahil edilir; PowerShell bellekte derler.
  Sistem yürütme ilkesi değiştirilmez, yönetici yetkisi istenmez.
- Mevcut SolidWorks oturumunun işlem kimliği ve kaynak dosyanın tam yolu iki
  tarafta doğrulanır. Yardımcı hiçbir belge açmaz/kapatmaz, etkin belgeyi
  değiştirmez ve SolidWorks'ü başlatmaz/kapatmaz.
- Kaynak sahipliği/görünürlük/konfigürasyon yönetimi mevcut Python kodundadır.
  Teknik resimleri/bastırılmış parçaları/Toolbox'u dahil etme, hedef adlarını
  aynı belge sırasıyla geri okuma ve yeni dosya referanslarını doğrulama korunur.
- Yardımcı yalnız Pack and Go nesnesini ayarlar ve açık **Paketi oluştur**
  işleminde `SavePackAndGo` çağırır. Kaynak üzerinde `Save`, `SaveAs`, yeniden
  adlandırma veya parametre değişikliği yapmaz. Kayıt öncesi kirli kaynak reddedilir.
- Unicode JSON satırları stdio üzerinden aktarılır; kullanıcı metni PowerShell
  kaynak koduna eklenmez. Yalnız izin verilen Pack and Go işlemleri vardır.
- Tarama/kayıt/hata/iptal sonunda kendi istemcisi ve COM referansları bırakılır.
  Devam eden tek `SavePackAndGo` COM çağrısı zorla kesilmez; iptal çağrıdan sonra
  uygulanır. Uygulama GUI'si Qt işçisi sayesinde yanıt vermeye devam eder.

## Doğrulama

`PackAndGoHost.cs`, gerçek 2023 SolidWorks interop DLL'sine ve .NET Framework
4.8 referanslarına karşı derlendi: **0 hata, 0 uyarı**. Kaynak referansı:
[AngelSix, 58787e2](https://github.com/angelsix/solidworks-api/tree/58787e2cefdcc03aebc15a51bd52ba151f3969d4/References/2023).
DLL SHA256: `7a6bf74d2a9f60563959d738c3c85f825f257c9def2a3bec464511aaebfc88e4`.
Bu yalnız geliştirme/test referansıdır; yeniden dağıtılmaz.

Hedefli Linux testleri: 95 geçti, 28 alt senaryo geçti. Windows pywin32,
Windows PowerShell derleme ve canlı SolidWorks testleri ayrı koşullarla atlanır.
Qt isimlendirme kontrolleri: 4 geçti. Kaynak Qt paket açılış kontrolü de
gömülü interop dosyasını, 10 modülü ve iki temayı doğruladı.

`.github/workflows/solidworks-bindings.yml` gerçek Windows pywin32 modülü ve
PowerShell 5.1 derleyicisini kontrol eder; yalnız test için kullanılan referans
DLL'sini sabit commit ve SHA256 ile doğrular. EXE üretmez, SolidWorks çalıştırmaz.
Son Windows sonucu `../examples/windows-bindings.json` içinde yayımlanır.

Son [gerçek Windows kontrolü](https://github.com/gkkizil/gokworks/actions/runs/39199385108):
**20 test geçti, atlanan/başarısız test yok**. Gerçek pywin32 API dışa aktarımları
ve gerçek Windows PowerShell derleyicisi kullanıldı. İlk başlatıcı sözdizimi
hatası bu kontrolle yakalanıp düzeltildi. Bu sonuç canlı SolidWorks testi değildir;
EXE oluşturulmadı.

Canlı, salt okunur kabul testi açık kullanıcı oturumunda ve kaydedilmiş, temiz
bir test montajı üzerinde çalıştırılır:

```powershell
$env:GOKWORKS_TEST_PACKANDGO_ASSEMBLY='C:\test\Montaj.sldasm'
python -m pytest modules/naming/tests/test_naming_native_live.py -v
```

Bu test dosya adlarını değiştirmez/kaydetmez. Native kaydetme, mate çözümü ve
teknik resim görünüşlerinin gerçek SolidWorks'te kabulü ayrıca yapılmalıdır.
COM sınırı taklit edilen testler veya derleme başarısı bu kabulün yerine geçmez.
Önceden indirilmiş EXE bu kaynak düzeltmesini içermez; otomatik EXE üretilmez.
