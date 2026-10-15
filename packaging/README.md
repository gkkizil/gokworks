# Windows EXE

Windows 10/11 x64 için tek dosyalık `GOKWORKS.exe` üretilir. Python, Tk,
CustomTkinter, pywin32 ve hesap/aktarım bağımlılıkları paket içindedir.
Kullanıcının Python kurması gerekmez. SolidWorks gereken CAD işlemleri için
SolidWorks ayrıca kurulu ve açık olmalıdır.

EXE yalnız kullanıcı istediğinde, **Run workflow → main** ile oluşturulur.
API erişimi olmayan ortamlarda `packaging/windows-build-request.json` dosyasına
benzersiz bir istek kimliği yazılıp `main` dalına gönderilebilir. İş akışı yalnız
bu istek dosyasının değişiminde çalışır; normal kod güncellemeleri EXE oluşturmaz.
İstek dosyası ayrıca bir dal açmayı gerektirmez.

[Windows derlemeleri](https://github.com/gkkizil/gokworks/actions/workflows/windows-exe.yml)
sayfasında başarılı çalışmanın **Artifacts → GOKWORKS-Windows-x64-…** paketini
indirin. ZIP içindeki `GOKWORKS.exe` dosyasını çıkartıp açın.
GitHub oturumu gerekebilir; paket 30 gün tutulur.

Her paket gerçek Windows ortamında açılır: dokuz çalışma alanı, kg/Newton
dönüşümü, örnek cıvata hesabı, DXF/XLSX yazma ve pywin32 importları kontrol edilir.
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

Çıktı: `dist/GOKWORKS.exe`, `SHA256.txt`, `OKU.txt` ve `windows-smoke.json`.
