# SolidWorks 2025 yerel kontrolü

Bulut testleri gerçek Windows/SolidWorks oturumunu çalıştırmaz. Bu kontrol,
bildirilen K/R atama hatasının gerçek montajda giderildiğini doğrulamak içindir.

## Doğru sürümü açma

GitHub dalı: `main`. PyCharm'da Git ile açtıysanız bu dala
geçip **Git → Pull** kullanın. ZIP ile açtıysanız aynı dalın güncel ZIP'ini
yeniden indirin; eski klasörü saklayıp yeni klasörü ayrı proje olarak açın.
ZIP klasöründe `git pull` kullanılamaz.

Güncellemeden önce çalışan GOKWORKS penceresini/PyCharm çalışmasını durdurun.
Pull sonrasında `main.py` dosyasını yeniden çalıştırın. Açık eski Python
işlemi, diskte güncellenen kodu kendiliğinden yüklemez. PyCharm Run
Configuration içindeki script yolunun güncel proje klasörüne ait olduğuna
bakın; eski masaüstü ZIP klasörünü çalıştırmayın.

PyCharm'ın projenin kendi `.venv` yorumlayıcısını kullandığını kontrol edin.
Aynı yorumlayıcıya bağımlılıkları kurun:

```powershell
python -m pip install -r requirements.txt
python main.py
```

Pillow, `PIL` importunu sağlar; `PIL` isimli paket kurulmaz. SolidWorks 2025 ve
Python aynı Windows kullanıcı oturumunda çalışmalıdır.

## K/R atama

1. Montajın ve parçaların bir kopyasıyla çalışın. Aktif ana montajı ve kontrol
   edeceğiniz parçaları kaydedin; parçanın montajda referans verilen
   konfigürasyonunu ve mevcut ana SAC LEVHA K/R değerlerini kaydedin.
2. **K faktörü / yarıçap → Manuel K / R**: 1,5 mm örneğinde kalınlık `1,5`,
   K `0,274`, R `1,5` girin. Ardından 2 mm örneğini `2 / 0,274 / 2` ile sınayın.
3. **Montajı tara** ile eşleşen sacları ve atlama nedenlerini okuyun.
   Tarama sonuçlarında **Uygulamaya hazır** görünür; bu aşamada K/R yazılmaz.
   **Tüm bükümlere uygula** açıkken, özel K/R kullanan bir kenar flanşı veya
   çizilmiş bükümü de kontrol kapsamına ekleyin. Tarama bu özel değerleri değiştirmemeli.
4. İlk kontrolü **Parça dosyalarını kaydet** işaretlenmeden yapın; **Montaja
   K/R uygula** kullanın. Değişiklik SolidWorks belleğinde uygulanır.
5. Başarılı parçanın doğru referans konfigürasyonunda **ana SAC LEVHA**
   parametrelerini açın. Modern parçada API türü `TemplateSheetMetal` olan
   bu unsurun K değeri 0,274, iç R değeri 1,5 mm (ikinci örnekte 2 mm), büküm
   payı türü K faktörü olmalı. Alt `SheetMetal` unsurunu ve varsa **Katıyı
   Saca Dönüştür** unsurunu da açın; aynı K/R ve değişmeyen gerçek kalınlığı
   doğrulayın. Modeli yeniden oluşturup açınım geometrisini kontrol edin.
   Sonuç ayrıntısındaki unsur adı/türü, konfigürasyon, önceki ve doğrulanan
   yeni K/R ile kaydetme bilgisini ekrandaki değerlerle karşılaştırın.
6. Farklı kalınlıklı saclarda ve parçanın diğer konfigürasyonlarında değişiklik
   olmamalı; CAD malzemesi ve sac kalınlığı korunmalı. Alt montajlar dahil sayılar
   raporda görünmeli. Malzeme/gauge tablosuna bağlı, çok gövdeli veya özel
   büküm türleri olan parçalar için destek sınırlarını rapordan kontrol edin.
   **Tüm bükümlere uygula** açıksa desteklenen bükümlerin R/büküm payı ana
   sacı kullanmalı; kapalıysa özel bükümler yazmadan durdurulmalıdır.
   Günlükte R atama yolunu ve ana K/R'ye bağlanan unsur adlarını kontrol edin.
   Türkçe karakterli/büyük harfli
   dosya yolları ve konfigürasyon adları ayrıntılarda özgün haliyle görünmeli.
7. Başarılı sonucu gözle kontrol ettikten sonra SolidWorks'te kaydedin.

Hata durumunda **Günlük**, satıra çift tıklama veya **Rapor kaydet** ile tam
metni alın. Yeni hata metni işlem aşamasını ve ilgili API üyesini içerir;
örneğin `Mevcut K/R ve büküm payı okuma: SolidWorks API · KFactor: ...`.
`128`, `swFileLoadWarning_AlreadyOpen` demektir: belge zaten açık/yüklüdür.
Bu bilgi tek başına atamayı engellemez. Mevcut belge yeniden kullanılmalı ve
işlem sonunda uygulama tarafından yeni açılmış gibi kapatılmamalıdır.
[Enum kaydı](reports/k-radius/api-contract.json) SolidWorks interop
metadata'sından doğrulanmıştır.

**Durum Uygulandı** ve **K/R uygulandı ve geri okumayla doğrulandı** metni,
yazılan K/R'nin SolidWorks'ten tekrar okunup kontrol edildiğini belirtir.
**Önizleme; K/R uygulanmadı** metni, değerlerin yalnız okunduğunu belirtir.
“Montaja K/R uygula” sonrası hâlâ yalnız önizleme görüyorsanız önce çalışan
proje yolunu ve güncel dalı kontrol edin; Günlük ve tam satır ayrıntısını alın.
Tarama sürerken **Tarama bitince K/R uygula** düğmesine basılırsa uygulama
isteği bekletilir; uygun parça bulunan başarılı taramadan sonra başlar.
Durdur/iptal/hata durumunda bekleyen istek uygulanmaz.

## Ana SAC LEVHA hedefi ve geri okuma

Modern parçada `Extension.GetTemplateSheetMetal()` ana sac klasörünün
unsurunu verir. Null veya eksik API üyesi için `FeatureManager.GetSheetMetalFolder`
ve `GetFeature` yolu kontrol edilir. Bu yollar sonuç vermezse ağaçtaki tek
`TemplateSheetMetal` unsuru kullanılabilir. Modern şablon yoksa eski yapıdaki
tek aktif `SheetMetal` unsuru kullanılır. Gövdeye ait sac unsurları ayrıca
klasörün `GetSheetMetals()` listesinden alınır; yalnız görünür ağaca bağlı kalınmaz.
Gerçek API çalışma hatası, çelişen tür, birden fazla aday veya okunamayan
parametre başarıya çevrilmez. Lokalize ad veya ağaç sırası hedef belirlemez.
Günlükte ana unsur, gövde unsuru ve ana unsurun bulunduğu yol gösterilir.

Kalınlık, tek sac gövdesinin aktif `SheetMetal` tanımından okunur. Yazma öncesi
ana unsur, alt sac ve dönüşüm tanımları bütün konfigürasyonlarda yedeklenir;
ağaç dolaşımında görünmeyen, API'den ayrı alınan ana unsur da yedeğe dahildir.
Yazma ve rebuild sonrasında ana unsur yeniden alınır. Konfigürasyonlar arası
kontrolün ardından ana unsur, alt sac ve dönüşüm değerleri yeniden okunur.
Yalnız alt unsurun değişmesi başarı sayılmaz. Hata halinde önce ana değerler
geri yüklenir; geri alma ayrıca doğrulanır. `GERİ ALMA HATASI` görülürse
dosyayı kaydetmeyin; ayrıntıyla birlikte modelin durumunu inceleyin.

Malzeme/gauge bağı ve alt sacın kalınlık/yarıçap veya K override'ı açıkken
yazma yapılmaz. Bu ayarlar otomatik kapatılmaz. Büküm payı türü 5 için
`BendCalculationTableFile` dosyası yedeklenir/geri yüklenir; tür 1'in
`BendTableFile` alanıyla karıştırılmaz.

[API kaynak kaydı](reports/k-radius/api-contract.json), yeniden indirilen
2026 belge aynasını ve sabit GitHub commitindeki ana klasör örneğini ayrı
kaynaklar olarak belirtir. [Ana unsur testleri](../modules/k_factor/tests/test_parent_k_radius.py)
ve [dispatch testleri](../modules/k_factor/tests/test_kr_dispatch.py) API sözleşmesini test
nesneleriyle doğrular. Bu kanıtlar Windows/SolidWorks 2025'te kullanıcının
modelinin veya açınımının çalıştırıldığı anlamına gelmez; yukarıdaki yerel
kabul kontrolü hâlâ gereklidir.

[Sac unsurunu bulma araştırması ve yeni kontroller](reports/sheetmetal-discovery/README.md).

## Katıyı Saca Dönüştür ile oluşturulan parçalar

1. Tek gövdeli bir dönüşüm parçasının kopyasını montaja ekleyin. **Gövdeyi
   koru** seçeneğiyle ikinci katı gövde kalan parça bu sürümde desteklenmez.
2. Dönüşüm unsurunda kalınlık/yarıçap ve büküm payı için varsayılan sac
   parametrelerini kullanın. Özel değerler açıksa uygulama ilgili ayarı
   bildirip K/R yazmadan durmalıdır.
3. Gerçek kalınlığa karşılık gelen manuel atamayı yapın; örneğin
   `1,5 mm → K=0,274, R=1,5 mm`. Tarama sırasında değerler değişmemeli.
4. **Montaja K/R uygula** sonrasında hem ana SheetMetal unsurunu hem de
   **Katıyı Saca Dönüştür** unsurunu düzenleyerek K, R ve kalınlığı kontrol
   edin. Sonuç ayrıntısında dönüşümün de geri okumayla doğrulandığı yazmalıdır.
5. Modeli yeniden oluşturup açınımını kontrol edin. Ardından özel K veya R
   kullanan bir dönüşüm kopyasında tekrar deneyin: işlem açık açıklamayla
   durmalı, dosya kaydedilmemelidir. Başka konfigürasyon değişmemelidir.

Buluttaki [dönüşüm ve K/R testleri](test-results/convert-solid-kr-tests.log),
API sözleşmesini ve hata/geri alma davranışını test nesneleriyle sınar;
yukarıdaki gerçek SolidWorks geometri kontrolünün yerine geçmez.

## ISO ve GUI kabul kontrolü

- **ISO seçimi → Mil esaslı**: JS7/h6, K7/h6 ve N7/h6 ara geçme örneklerini
  Ø50'de seçin. P7/h6 Ø50'de sıkı olmalı; H7/p6 Ø3'te ara, Ø50'de sıkı olmalı.
- **Manuel kontrol**, Ø50: delik alt 0/üst +0,039 → tam H8;
  alt 0/üst +0,062 → tam H9; −0,0125/+0,0125 → tam JS7.
  Mil alt −0,016/üst 0 → tam h6. Sonuç ve CSV giriş limitlerini korumalı.
- Delik alt 0/üst +0,02 tam H7 değildir: en yakın H6 referansı, üst fark
  +0,004 mm. Delik −0,05/0 ve mil ±0,1 → −0,15…+0,10 mm ara geçme.
- PDF, DXF/DWG ve K/R sayfalarında form solda, sonuçlar sağda tam yüksekliği
  kullanır. Form kaydırılırken tablo küçülmemeli. Açık/koyu tema ve Windows
  ekran ölçeğinde sekme geçişlerini kontrol edin.

## Yerel Codex oturumuna devir

Bilgisayarda Codex CLI kullanılıyorsa proje klasöründen başlatın. Bu belgeyi
ve [düzeltme raporunu](reports/kr-workspace-fix/README.md) okutun. Önce
SolidWorks COM API'sinden aktif belge, unsur ve mevcut değerleri yazma
yapmadan kontrol etmesini isteyin. Bulut sohbetine verilen izin yerel
PyCharm/SolidWorks bağlantısı oluşturmaz; yerel oturum ayrı çalışır.
