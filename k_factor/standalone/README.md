# Bağımsız K/R denemesi: C# → Python

<!-- kr-windows-release:start -->
**Windows paketi:** [K/R deneme aracını indir](https://github.com/gkkizil/gokworks/actions/runs/38902089258/artifacts/12047305175). ZIP dosyasını çıkartıp **GOKWORKS-KR-Deneme.exe** dosyasını açın. Alt klasörleri koruyun; EXE’yi tek başına taşımayın. Python ve .NET kurulumu gerekmez.

[Derleme kaydı](https://github.com/gkkizil/gokworks/actions/runs/38902089258) · Kaynak: `8b94bd9` · [SHA256, Defender taraması ve açılış kontrolü](windows-build-status.json)
<!-- kr-windows-release:end -->

## EXE ile kullanım

Chrome önceki paketi tehlikeli indirme olarak işaretledi. Özgün iki EXE'nin
hashleri doğrulandı, yayıncı imzası bulunmadı ve güncel Windows Defender
taramasında tehdit tespit edilmedi. [Özgün paket taraması](windows-security-status.json).
Chrome uyarısının kesin nedeni doğrulanmadı. Yeni standart klasör paketi,
yayınlanmadan ve çalıştırılmadan önce ayrıca taranır. Defender sonucu,
Chrome'un paketi kabul edeceğini veya kesin güvenli olduğunu kanıtlamaz.

Windows paketini tamamen çıkartıp `GOKWORKS-KR-Deneme.exe` dosyasını açın.
`_internal` ve `native` alt klasörlerini koruyun. Python, .NET,
SDK veya terminal kurulumu/kullanımı gerekmez. SolidWorks kurulu ve açık
olmalıdır; API arayüzleri kurulu SolidWorks'ün `api\redist` klasöründen alınır.

Bir sac parçasını kendi penceresinde etkinleştirip **Parçayı oku** düğmesine
basın. Ardından farklı bir K veya R girip **K/R yazma denemesi** düğmesine
basın. Araç önce C#, sonra Python ile yazmayı dener, değerleri geri okur ve
eski değerleri geri yükleyip doğrular. Dosyalar otomatik kaydedilmez.
İlk denemeyi bir kopyada yapın. İşlem bitene kadar SolidWorks'te belge veya
konfigürasyon değiştirmeyin. **Rapor klasörü** düğmesi sonuçları açar.

Raporlar ve oluşturulan Python COM arayüzleri kullanıcıya özel
`%LOCALAPPDATA%\GOKWORKS\KR-Deneme` klasöründedir. Geri alma hatası
görünürse parçayı kaydetmeyin. Ana GOKWORKS uygulamasının K/R menüsü bu
ayrı denemeden bağımsızdır.

## Kaynak kodu

Bu klasör, mevcut GOKWORKS K/R işçisinden bağımsız iki uygulama içerir.
C# sürümü SolidWorks'ün tipli .NET arayüzlerini, Python sürümü kurulu
SolidWorks'ün tür kitaplığından üretilen MakePy arayüzlerini kullanır.
Tür dönüşümleri önbellekteki arayüz sınıfına açık `QueryInterface` ile
yapılır; her çağrıda MakePy yeniden çalıştırılmaz.
Python uygulaması C# çalıştırmaz ve `k_factor/apply.py` dosyasını kullanmaz.

Amaç, aynı gerçek parçada aynı API akışını karşılaştırarak Python–COM
bağlantısından kaynaklanan hataları model/unsur davranışından ayırmaktır.
Bu bulutta Windows/SolidWorks yoktur; derleme ve taklit nesne kontrolleri
gerçek dosyada çalıştığının kanıtı değildir.

## Kaynak kodundan ilk gerçek deneme

Windows'ta SolidWorks açık olsun. Denenecek `.SLDPRT` dosyasını **ayrı bir
parça penceresinde etkinleştirin**. İlk denemede dosyanın bir kopyasını
kullanın. Montaj penceresi bu deneme için kabul edilmez.

Kaynak kodundan çalıştırmak için: .NET 8 SDK, Python 3 ve `pywin32==312`; SolidWorks ile terminal
aynı Windows kullanıcısında ve aynı yetki düzeyinde çalışmalıdır.
SolidWorks API arayüz DLL'leri kurulumun `api\redist` klasöründen alınır;
bu depoda DLL dağıtılmaz.

Depo kökünde PowerShell'den önce yalnız okuma:

```powershell
& .\k_factor\standalone\run-check.ps1 -Mode inspect
```

Kurulum farklı bir konumdaysa `-SolidWorksInteropDir 'D:\...\api\redist'`
verin. Python yolu için `-PythonCommand 'C:\...\python.exe'` kullanılabilir.
Betik önce C#'ı derler/çalıştırır, başarılıysa Python'u çalıştırır ve
iki okuma raporunu karşılaştırır. `inspection_match` yalnız okuma uyumudur.

`examples/verify.json` içindeki kalınlık/K/R satırlarını düzenleyin.
**Mevcut K/R'den farklı bir hedef seçin**; değişmeyen değerler yazma
başarısı sayılmaz. Ardından:

```powershell
& .\k_factor\standalone\run-check.ps1 -Mode verify
```

`verify` gerçekten yazar, yeniden oluşturur, yeni tanımdan hedef K/R'yi
okur; sonra eski büküm payı türünü/değerini ve R'yi geri yükleyip kontrol
eder. Başarılı sonuç `verified_match` olur. C# başarısızsa Python
başlatılmaz. Hiçbir mod dosyayı otomatik kaydetmez. Geri alma hatası
raporlanırsa dosyayı kaydetmeyin.

Raporlar tek yerde: `k_factor/standalone/reports/<tarih-saat>/` altında
`csharp.json`, `python.json` ve `comparison.json`. Bu klasör Git'e eklenmez.

## Kapsam

- Yalnız etkin, diske daha önce kaydedilmiş parça ve mevcut konfigürasyon.
- Modern sacda `GetTemplateSheetMetal` ile ana unsur; eski sacda benzersiz
  `SheetMetal` unsuru. Belirsiz seçimde işlem durur.
- Gerçek sac kalınlığı girilen satırlarla eşleştirilir. Eşleşmeyen parça
  atlanır; birden çok eşleşme reddedilir.
- K, `GetCustomBendAllowance / SetCustomBendAllowance` ile; R, aynı
  unsura ait tek radyal ölçüyle, uygun ölçü yoksa unsur tanımıyla yazılır.
  Ölçü yolu yalnız mevcut konfigürasyonu hedefler.
- Alt bükümlerin özel değerleri, sac kalınlığı, malzeme ve tablo bağları
  değiştirilmez. Ana unsurun geri okunması bütün alt bükümlerin
  değiştiği anlamına gelmez.
- Derlenen API sözleşmesinde okunup geri yüklenebilen büküm payı türleri
  1–4 desteklenir. Diğer türler incelenir; geri alma güvenceye alınamadığı
  için yazılmaz.
- Gauge kodu `2 / NotEnabledOnTemplate`, incelemede ham durumuyla
  gösterilir; başarısız sorgunun `false` çıkışı geçerli veri sayılmaz.
  `verify` bu durumu uyarıyla deneyebilir; kalıcı `apply` için kontrollerin
  doğrulanması gerekir. Etkin olduğu bilinen tablo/malzeme kontrolü engeldir.

`apply` modu da her iki motorda vardır: doğrulanan değerleri açık parçada
bırakır, kaydetmez. Karşılaştırma betiği `apply` sonuçlarını yazma eşdeğerliği
kanıtı saymaz; karşılaştırma için `verify` kullanın.

Montajdaki bütün parçaları işleme, başka konfigürasyonlara geçme ve özel
alt bükümleri ana değerlere bağlama mevcut uygulamada kalır. Yeni motorun
o akışa alınması için önce bu yerel denemenin gerçek SolidWorks raporları
gereklidir. Buradaki araç mevcut uygulama menüsüne henüz bağlanmamıştır.

## Kaynak ve yöntem

[Power-SM](https://github.com/AmenJlili/power-sm/tree/6c835fb712c18df8969500ec247a0768d3af0d37)
K/R yöntemi için incelendi. Yeni kod bağımsız yazılmıştır; Power-SM kaynak
dosyaları kopyalanmamıştır.
[K yöntemi](https://github.com/AmenJlili/power-sm/blob/6c835fb712c18df8969500ec247a0768d3af0d37/PowerSM/PowerSM/PowerGeometry_Form.cs#L1058),
[R yöntemi](https://github.com/AmenJlili/power-sm/blob/6c835fb712c18df8969500ec247a0768d3af0d37/PowerSM/PowerSM/SheetMetalFolder2.cs#L70).
R için kaynak projedeki bütün konfigürasyonları etkileyebilen eski çağrı
yerine konfigürasyon kapsamı belirtilen `SetSystemValue3` kullanılır.

API sözleşmeleri: SolidWorks 2023 interop metadata'sı,
[SolidWorks API belgeleri](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISheetMetalFeatureData.html)
ve [pywin32 MakePy](https://github.com/mhammond/pywin32/tree/b312/com/win32com/client).

## Bulutta doğrulananlar

C# derlemesi ve 18 saf sözleşme kontrolü, Python/karşılaştırıcı için 30
odaklı test geçti. Ayrıntılar [validation.json](validation.json) içindedir.
Python işlem testleri COM test nesneleri kullanır; Windows başlatıcısı ve
gerçek SolidWorks yazma işlemi bu ortamda çalıştırılmadı.
