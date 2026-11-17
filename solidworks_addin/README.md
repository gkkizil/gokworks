# GOKWORKS SolidWorks eklentisi

SolidWorks'e **GOKWORKS** menüsü, araç çubuğu ve (parça, montaj, teknik resim
belgelerinde) bir **GOKWORKS** sekmesi ekler. Komutlar:

| Komut | Açılan araç | Açık model |
|---|---|---|
| GOKWORKS | ana pencere | — |
| Otomatik Teknik Resim | `automatic_drawing` | parça / montaj okunur |
| Ağırlık hesabı | `weight` | parça / montaj okunur |
| BOM · Ürün ağacı | `bom` | montaj okunur |
| İsimlendirme aracı | `naming` | montaj okunur |
| DXF / DWG | `dxf_dwg` | parça / montaj taranır |
| Abkant Simülasyonu | `press_brake` | parça okunur |
| Tolerans yığılması | `tolerance_stack` | teknik resim okunur |
| DFM, Sac Açınımı, Nesting | araç açılır | — |

Model gerektiren komut, uygun belge açık değilken soluk görünür.

## Nasıl çalışır

GOKWORKS SolidWorks'ün **içine yüklenmez**; ayrı süreçte çalışır. Komut
`GOKWORKS.exe --open <araç> [--active]` başlatır. GOKWORKS zaten açıksa yeni pencere
açılmaz: komut yerel kanal üzerinden açık pencereye iletilir (`gui_qt/remote.py`),
araç öne gelir ve `--active` ise aracın kendi "aktif modeli al" komutu çalışır.
GOKWORKS çökerse SolidWorks etkilenmez. Yalnız bilinen araç adları ve izin
listesindeki okuma komutları kabul edilir.

## Derleme (Windows, SolidWorks kurulu)

Gerekenler: .NET SDK (8 veya üzeri; hedef .NET Framework 4.8) veya Visual Studio 2019+.

```bat
cd solidworks_addin
dotnet build -c Release
```

SolidWorks başka klasördeyse interop DLL'lerinin yolunu verin:

```bat
dotnet build -c Release -p:SolidWorksApi="D:\SOLIDWORKS\api\redist"
```

Çıktı: `bin\Release\net48\GokworksSolidWorksAddin.dll` ve `icons\`.

## Kurulum

1. `GokworksSolidWorksAddin.dll` ve `icons` klasörünü GOKWORKS klasörüne (GOKWORKS.exe'nin
   yanına) ya da bir alt klasöre (`GOKWORKS\SolidWorksAddin\`) kopyalayın.
2. **Yönetici** komut isteminde kaydedin (64 bit RegAsm):

   ```bat
   %WINDIR%\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe /codebase GokworksSolidWorksAddin.dll
   ```
3. SolidWorks'ü açın: **Araçlar › Eklentiler** listesinde **GOKWORKS** görünür ve
   başlangıçta yüklenir.

GOKWORKS.exe sırayla şuralarda aranır: `GOKWORKS_EXE` ortam değişkeni,
`HKCU\Software\GOKWORKS\SolidWorksAddin` altındaki `Executable` (ve isteğe bağlı
`Arguments`) değeri, eklenti klasörü ve onun bir üstü. Geliştirme kurulumunda
`Executable` = `python.exe`, `Arguments` = `C:\...\gokworks\main.py` verilebilir.

Kaldırma: `RegAsm.exe /unregister GokworksSolidWorksAddin.dll` (yönetici).

## Doğrulama durumu

- Linux'ta SolidWorks yok: eklenti, kullandığı SolidWorks API üyelerinin imzalarını taşıyan
  `verify/SolidWorksStubs.cs` ile derlenir (`dotnet build -p:SwStubs=true`), SolidWorks'ten
  bağımsız mantık `verify/ToolsCheck` ile çalıştırılarak denenir. Gerçek SolidWorks'te
  yükleme, menü ve sekme ilk kez kullanıcının bilgisayarında doğrulanmalıdır.
- `tests/test_solidworks_addin.py` komut tablosunu GOKWORKS araçları ve izin listesiyle,
  `tests/test_remote_commands.py` komut iletimini (gerçek yerel soketle) sınar.
- İkonlar: `python solidworks_addin/make_icons.py` GOKWORKS'ün kendi araç ikonlarından üretir.
