# Windows EXE

Windows 10/11 x64 için tek dosyalık `GOKWORKS.exe` üretilir. Python, Tk,
CustomTkinter, pywin32 ve hesap/aktarım bağımlılıkları paket içindedir.
Kullanıcının Python kurması gerekmez. SolidWorks gereken CAD işlemleri için
SolidWorks ayrıca kurulu ve açık olmalıdır.

[Windows derlemeleri](https://github.com/gkkizil/gokworks/actions/workflows/windows-exe.yml)
sayfasında başarılı çalışmanın **Artifacts → GOKWORKS-Windows-x64-…** paketini
indirin. ZIP içindeki `GOKWORKS.exe` dosyasını çıkartıp açın.
GitHub oturumu gerekebilir; paket 30 gün tutulur.

Her paket gerçek Windows ortamında açılır: yedi çalışma alanı, kg/Newton
dönüşümü, örnek cıvata hesabı, DXF/XLSX yazma ve pywin32 importları kontrol edilir.
Bu kontrol gerçek SolidWorks oturumuna bağlanmaz. Paket kod imzası taşımaz.

Derleme durumu ve doğrudan artifact bağlantısı ayrı
[`codex/windows-build-status`](https://github.com/gkkizil/gokworks/blob/codex/windows-build-status/latest.json)
dalında küçük bir JSON olarak saklanır. Uygulama dalına derleme çıktısı veya
büyük ikili dosya eklenmez.

Yerel Windows derlemesi, depo kökünden:

```powershell
py -3.13 -m venv .build-venv
.build-venv\Scripts\python -m pip install -r packaging/windows-requirements.txt
.build-venv\Scripts\python packaging/build_windows.py
```

Çıktı: `dist/GOKWORKS.exe`, `SHA256.txt`, `OKU.txt` ve `windows-smoke.json`.
