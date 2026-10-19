# Windows EXE

Windows 10/11 x64 için `GOKWORKS/GOKWORKS.exe` ve yanındaki `_internal` klasörü
üretilir. PySide6/Qt, pywin32 ve hesap/aktarım bağımlılıkları paket içindedir.
Kullanıcının Python kurması gerekmez. SolidWorks gereken CAD işlemleri için
SolidWorks ayrıca kurulu ve açık olmalıdır.

EXE yalnız kullanıcı istediğinde, **Run workflow → main** ile oluşturulur.
API erişimi olmayan ortamlarda `packaging/windows-build-request.json` dosyasına
benzersiz bir istek kimliği yazılıp `main` dalına gönderilebilir. İş akışı yalnız
bu istek dosyasının değişiminde çalışır; normal kod güncellemeleri EXE oluşturmaz.
İstek dosyası ayrıca bir dal açmayı gerektirmez.

[Windows derlemeleri](https://github.com/gkkizil/gokworks/actions/workflows/windows-exe.yml)
sayfasında başarılı çalışmanın **Artifacts → GOKWORKS-Windows-x64-…** paketini
indirin. ZIP'in tamamını çıkartıp `GOKWORKS/GOKWORKS.exe` dosyasını açın.
`_internal` klasörü EXE'nin yanında kalmalıdır.
GitHub oturumu gerekebilir; paket 30 gün tutulur.

Her paket gerçek Windows ortamında açılır: on çalışma alanı, kg/Newton
dönüşümü, örnek cıvata hesabı, DXF/XLSX yazma ve pywin32 importları kontrol edilir.
PDF yardımcı süreci aynı EXE üzerinden boş klasörle başlatılarak paket içi
importlar ve olay iletişimi denetlenir; ayrı pencere veya stdout gerektirmez.
Bu kontrol gerçek SolidWorks oturumuna bağlanmaz. Paket kod imzası taşımaz.

Uygulama paketi yalnız çalıştırılan Python modüllerini, bağımlılıklarını,
`gui/assets/` kaynaklarını ve `iso_fits/tables.json` verisini içerir.
Testler, belgeler, ekran görüntüleri ve geçmiş raporlar EXE'ye eklenmez.

Son başarılı paketin bağlantısı ana [README](../README.md) dosyasında bulunur.
[Paket bilgisi](latest-windows.json) ve [son derleme durumu](windows-build-status.json)
aynı `main` dalında tutulur. Başarısız bir derleme, önceki başarılı indirme
bağlantısını değiştirmez. Büyük EXE dosyaları Actions paketinde kalır.
Geçmiş derleme dalları `archive/` etiketleriyle korunur; tek çalışma dalı `main`dir.

Yerel Windows derlemesi, depo kökünden:

```powershell
py -3.13 -m venv .build-venv
.build-venv\Scripts\python -m pip install -r packaging/windows-requirements.txt
.build-venv\Scripts\python packaging/build_windows.py
```

Çıktı: `dist/GOKWORKS/GOKWORKS.exe`, yanındaki `_internal`, `dist/SHA256.txt`,
`dist/OKU.txt` ve `dist/windows-smoke.json`.
