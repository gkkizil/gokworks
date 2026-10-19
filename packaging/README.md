# Windows EXE

Windows 10/11 x64 için tek **GOKWORKS.exe** üretilir. Yanında klasör gerekmez.
PySide6/Qt, pywin32 ve hesap/aktarım bağımlılıkları EXE içindedir.
Kullanıcının Python kurması gerekmez. SolidWorks gereken CAD işlemleri için
SolidWorks ayrıca kurulu ve açık olmalıdır.

EXE yalnız kullanıcı istediğinde, **Run workflow** ile ilgili kaynak dalda oluşturulur.
API erişimi olmayan ortamlarda `packaging/windows-build-request.json` dosyasına
benzersiz bir istek kimliği yazılıp çalışma dalına gönderilebilir. İş akışı yalnız
bu istek dosyasının değişiminde çalışır; normal kod güncellemeleri EXE oluşturmaz.
İstek dosyası ayrıca bir dal açmayı gerektirmez.

[Windows derlemeleri](https://github.com/gkkizil/gokworks/actions/workflows/windows-exe.yml)
sayfasında başarılı çalışmanın **Artifacts → GOKWORKS-Tek-EXE-Windows-x64-…**
paketi yalnız `GOKWORKS.exe` içerir. Ayrıca GitHub ön sürümünde doğrudan `.exe`
indirme bağlantısı yayımlanır. EXE tek başına başka klasöre/PC'ye taşınabilir.
GitHub oturumu gerekebilir; paket 30 gün tutulur.

Her paket gerçek Windows ortamında açılır: on çalışma alanı, kg/Newton
dönüşümü, örnek cıvata hesabı, DXF/XLSX yazma ve pywin32 importları kontrol edilir.
EXE kaynak ağacından ayrı, boş ve Türkçe karakter/boşluk içeren klasöre kopyalanır;
yanında başka dosya olmadan üç DPI ölçeğinde çalıştırılır. PDF yardımcı süreci
aynı EXE üzerinden boş klasörle başlatılarak paket içi importlar, olay iletişimi
ve donmuş çıkış izleyicisinin gerçek süreç tanıtıcısı denetlenir.
PDF işçisi açık ana paketin geçici kaynaklarını kullanır; normal kapanışta işçi
bitmeden ana pencere kapanmaz. Ana pencereden bağımsız çıkış izleyicisi kendi
geçici kaynaklarıyla çalışarak ana pencerenin kapanışından sonra da kayıt yazabilir.
Bu kontrol gerçek SolidWorks oturumuna bağlanmaz. Paket kod imzası taşımaz.

Uygulama paketi yalnız çalıştırılan Python modüllerini, bağımlılıklarını,
`gui/assets/` kaynaklarını ve `iso_fits/tables.json` verisini içerir.
Testler, belgeler, ekran görüntüleri ve geçmiş raporlar EXE'ye eklenmez.

Son başarılı paketin bağlantısı ana [README](../README.md) dosyasında bulunur.
[Paket bilgisi](latest-windows.json) ve [son derleme durumu](windows-build-status.json)
aynı kaynak dalda tutulur. Başarısız bir derleme, önceki başarılı indirme
bağlantısını değiştirmez. Büyük EXE dosyaları Actions paketinde kalır.
Yeni derleme için ayrıca dal oluşturulmaz; yedek depoya işlem yapılmaz.

Yerel Windows derlemesi, depo kökünden:

```powershell
py -3.13 -m venv .build-venv
.build-venv\Scripts\python -m pip install -r packaging/windows-requirements.txt
.build-venv\Scripts\python packaging/build_windows.py
```

Çıktı: **`dist/GOKWORKS.exe`**. SHA256, kullanım notu ve açılış kontrolü raporları
derleme kayıtlarında tutulur; kullanıcı EXE yanında bunları taşımak zorunda değildir.

Lisans metinleri EXE içindedir: **Lisanslar → Lisansları kaydet** ile tam bildirim
arşivi kaydedilebilir. Uyumlu değiştirilmiş LGPL kitaplıklarını kullanmak için
`GOKWORKS_LIBRARY_DIR`, `PySide6` ve `shiboken6` paketlerini içeren klasöre
ayarlanabilir. Python 3.13 x64 / Qt-PySide ABI uyumu gerekir. Bu yol özel runtime
hook ile Qt yüklenmeden önce uygulanır; üçüncü DPI kontrolü dış paketlerden
yüklenen PySide/Shiboken ve gerçek Qt6Core DLL konumunu da doğrular. Normal
kullanımda bu değişken veya dış kitaplık gerekmez.

Geliştirici gerekirse `python packaging/build_windows.py --onedir` ile açık
klasörlü bir dağıtım üretebilir; kullanıcıya verilen varsayılan çıktı tek EXE'dir.
