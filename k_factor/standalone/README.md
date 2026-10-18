# Bağımsız Sac-Levha K/R ataması

<!-- kr-windows-release:start -->
**Windows paketi:** [K/R atama aracını indir](https://github.com/gkkizil/gokworks/actions/runs/39053084291/artifacts/12108791079). ZIP dosyasını çıkartıp **GOKWORKS-KR-Deneme.exe** dosyasını açın. Alt klasörleri koruyun; EXE’yi tek başına taşımayın. Python ve .NET kurulumu gerekmez.

[Derleme kaydı](https://github.com/gkkizil/gokworks/actions/runs/39053084291) · Kaynak: `fda7848` · [SHA256, Defender taraması ve açılış kontrolü](windows-build-status.json)
<!-- kr-windows-release:end -->

## Kullanım

1. SolidWorks'te kaydedilmiş sac parçasını kendi penceresinde açın.
2. **Parçayı oku** düğmesine basın. Ana Sac-Levha unsuru, mevcut
   konfigürasyon, kalınlık, K ve iç yarıçap okunur.
3. İstediğiniz K faktörünü ve iç yarıçapı **mm** olarak girin.
4. **K/R uygula** düğmesine basın. Değerler yazılır, parça yeniden
   oluşturulur ve yeni unsur tanımından geri okunarak kontrol edilir.
5. Başarılı atamada **yeni değerler açık parçada kalır**. SolidWorks'te
   kontrol edip kaydedin. Araç dosyayı kendiliğinden kaydetmez.

ZIP'i bütün alt klasörleriyle çıkartın. `GOKWORKS-KR-Deneme.exe` dosyasını
tek başına taşımayın; dosya adı önceki paketlerle uyumluluk için korunmuştur.
Yeni pencerenin başlığı **K/R ataması**, işlem düğmesi **K/R uygula** olur.
Güncel arayüz: [K/R atama ekranı](../../docs/screenshots/kr-direct-assignment.png).
Python veya .NET kurmanız gerekmez. SolidWorks kurulu ve açık olmalıdır;
yerel API DLL'leri kurulumun `api\redist` klasöründen alınır, pakette dağıtılmaz.

Okunan belge/konfigürasyon veya başlangıç değerleri değişirse uygulama
yazmaya başlamadan durur. Parçayı yeniden okuyun. Aynı değerleri tekrar
uygulamak geçerlidir. Yazma ya da geri okuma hatasında eski parametreleri
geri yüklemek denenir. Geri alma doğrulanamazsa **parçayı kaydetmeyin**
uyarısı gösterilir. Başarılı atamada geri alma yapılmaz.

## Ekrandaki okuma hatasının giderilmesi

Önceki masaüstü uygulaması C# okumasından sonra zorunlu Python COM
karşılaştırması çalıştırıyordu. Kullanıcının ekranındaki
`(-2147319765, 'Eleman bulunamadı.') / TYPE_E_ELEMENTNOTFOUND` hatası bu
ikinci aşamada çıktı; C# motorunun okuduğu parça da arayüze gösterilemedi.
Bu akış, kullanıcının Sac-Levha parametrelerini doğrudan değiştirme isteğiyle
uyuşmuyordu. Ayrıca eski ana düğme bir yazma **denemesiydi** ve başarılı
olunca eski değerleri geri yüklüyordu.

Masaüstünün normal okuma ve atama yolu artık yalnız tipli C# motorunu
kullanır. Python tür kitaplığı oluşturma veya iki motorun uyuşması bu yolun
koşulu değildir. Python COM hatasının alt düzey nedeni bu değişiklikle
kanıtlanmış veya giderilmiş sayılmaz; hatalı zorunlu bağımlılık kaldırılmıştır.

Normal C# ataması `GetUseGaugeTable` sorgusunu kullanmaz. K/R, kullanıcının
girdiği değerlerdir; gauge/büküm tablosundan hesaplanmaz. Tablo ve malzeme
bağları kapatılmaz. Başarı için K/R'nin yeniden oluşturma sonrasında hedef
değerlerle eşleşmesi gerekir; SolidWorks değeri reddeder veya başka bir ayar
geri yazarsa hata bildirilir ve eski parametreler geri yüklenir.

## Kapsam ve raporlar

Yalnız açık `.SLDPRT` dosyasının mevcut konfigürasyonundaki benzersiz ana
`TemplateSheetMetal` veya eski tek `SheetMetal` tanımı değiştirilir. Alt
bükümlerin ve gövdelerin özel geçersiz kılma ayarları korunur. Ana unsurun
okunması bütün alt bükümlerin veya çok gövdeli parçanın değiştiğini kanıtlamaz.
Kalınlık, ana unsurun değeridir; şablon varsayılanıyla gövde kalınlığı
farklı olabilir. Montaj dolaşımı bu bağımsız araçta yoktur.

K, `GetCustomBendAllowance / SetCustomBendAllowance` ve `ModifyDefinition`
ile yazılır. R doğrudan `ISheetMetalFeatureData.BendRadius` alanına metre
cinsinden yazılır. Görünen ölçüler taranmaz veya değiştirilmez. Başarıda kalınlık,
aktif büküm payı türü ve hedef K/R yeniden okunur. Aktif büküm payı türleri
1–4 hata halinde geri yükleme için desteklenir.

**Rapor klasörü**, `%LOCALAPPDATA%\GOKWORKS\KR-Deneme\reports` altındaki
son işlem dosyalarını açar. `csharp.json` gerçek native çağrı sırasını,
önce/sonra değerlerini ve varsa geri alma sonucunu içerir.

Bu araç ana GOKWORKS montaj K/R menüsünden bağımsızdır. Ana uygulamaya
aktarma için gerçek SolidWorks parçasındaki sonuçlar ayrıca doğrulanmalıdır.

## İsteğe bağlı geliştirici tanısı

Bağımsız Python çevirisi ve C#/Python karşılaştırması kaynak kodda bulunur;
masaüstünün **Parçayı oku / K/R uygula** yolu bunları çalıştırmaz.
`run-check.ps1 -Mode inspect` yalnız okumaları karşılaştırır;
`-Mode verify` iki motorla geçici yazma ve geri alma tanısıdır. Bu tanı için
.NET 8 SDK, Python ve pywin32 gerekir. Normal EXE kullanımı için gerekmez.

Kaynak yöntem olarak [Power-SM](https://github.com/AmenJlili/power-sm/tree/6c835fb712c18df8969500ec247a0768d3af0d37)
ve [SolidWorks API belgeleri](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISheetMetalFeatureData.html)
incelendi. Mevcut C# kodu bağımsız yazıldı; Power-SM kaynak dosyaları kopyalanmadı.

Derleme ve kontrol nesneleri gerçek SolidWorks yazma denemesi değildir.
Windows paket açılış kontrolü gerçek Sac-Levha dosyasına yazmaz.
18 Ekim 2026 revizyonunda native derlemesi sıfır hata/uyarıyla ve 20 saf
native kontrolüyle geçti. Önceki paket için yapılan Windows açılış kontrolü
bu yeni kaynak revizyonunun canlı SolidWorks testi değildir. Bu revizyonda
yeni EXE üretilmedi.
