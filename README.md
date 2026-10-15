# GOKWORKS

Güncel uygulama kodunun tek çalışma dalı **[main](https://github.com/gkkizil/gokworks/tree/main)** dalıdır.

<!-- windows-release:start -->
**Güncel Windows EXE:** [GOKWORKS paketini indir](https://github.com/gkkizil/gokworks/actions/runs/38783997616/artifacts/11997580487)

ZIP dosyasını çıkartıp **GOKWORKS.exe** dosyasını açın. Windows 10/11 x64; Python kurulumu gerekmez.

Uygulama kodu: `25e5bdf` · [Derleme kaydı](https://github.com/gkkizil/gokworks/actions/runs/38783997616) · [Paket bilgisi ve SHA256](packaging/latest-windows.json)
<!-- windows-release:end -->

SolidWorks teknik resimlerini PDF'e, sac açınımlarını DXF/DWG'ye aktarır; montajdaki sac parçalara kullanıcı tarafından kalınlıklarına göre girilen K faktörü/iç yarıçap değerlerini uygular. ISO delik/mil geçmelerini bağımsız bir hesap ekranında gösterir; geometrik toleransları ASME GD&T rehberiyle açıklar.

[14 Ekim Astra incelemesi](docs/astra-review.md): K/R kayıt sırası, açık belge koruması ve isimlendirme önizlemesi düzeltmeleri; depo temizliği ve doğrulama kapsamı.

## Windows'ta çalıştırma

Python 3.12, kurulu SolidWorks ve aynı Windows kullanıcı oturumunda açık SolidWorks gerekir. Proje klasöründe:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

Mevcut kurulumu güncellerken de `pip install -r requirements.txt` komutunu çalıştırın. Arayüz için `customtkinter==6.0.0` ve ölçeklenebilir ikonlar için `Pillow==12.1.0` kullanılır.

## BOM - Ürün ağacı

**BOM - Ürün ağacı → Montajı tara**, SolidWorks'teki aktif ana montajın aktif
konfigürasyonunu ve alt montajlarını okur. CAD dosyalarını kaydetmez veya
parametrelerini değiştirmez. **Excel’e aktar**, Excel kurulu olmadan `.xlsx`
oluşturur; bağımlılıklar için `pip install -r requirements.txt` çalıştırın.

- **Parça listesi**: Parça adı, fiziksel toplam adet, konfigürasyon ve dosya
  yolu. Adlar Türkçe harflerle ve doğal sayı sırasıyla sıralanır (Parça 2,
  Parça 10). Aynı dosyanın farklı konfigürasyonları ve aynı adlı farklı
  dosyalar ayrı satırlardır.
- **Ürün ağacı**: Her alt montajın altında kendi parçaları bulunur.
  `ÖRNEK-M001 → Parça A / Parça B` ilişkisi korunur; iç içe montajlar Excel'de
  girintili ve açılır/kapanır satır gruplarıyla gösterilir. Bu sayfa fiziksel
  örnekleri ayrı satırlarda listeler; her örneğin adedi 1'dir. Aynı alt montaj
  iki kez kullanılmışsa iki dal da alınır, toplam parça adetleri birleşir.
- Bastırılmış dallar hariçtir; gizli bileşenler sayılır. BOM dışı işaretli
  dallar varsayılan olarak atlanır; **BOM dışı bileşenleri de dahil et**
  seçeneğiyle alınabilir. Tarama yeniden yapıldığında yeni seçim uygulanır.
- Arama yalnız ekrandaki toplu parça listesini süzer; Excel tam tarama
  sonucunu içerir. Eksik/çözümlenmemiş bileşen, SpeedPak veya API hatasında
  kısmi sonuç dışa aktarılmaz. Durdurma mevcut Excel dosyasını korur.

Bu çıktı uygulamanın bileşen ağacıdır; SolidWorks'te eklenmiş bir BOM
tablosunu kopyalamaz. Özel BOM miktar/birim özellikleri, satın alınmış montaj
kuralları ve Hide/Promote gösterim tercihleri fiziksel sayımı değiştirmez.
Örnek Excel, kaynaklar ve Windows kabul adımları [BOM kılavuzunda](docs/bom.md).

## İsimlendirme aracı

**Aktarım ve montaj → İsimlendirme aracı** bölümünde montajın bulunduğu **Kaynak klasörü** ve yeni montajın kaydedileceği **Hedef klasörü** seçin. Tek montaj otomatik seçilir; birden çok montaj varsa ekrandaki listeden ana montajı belirleyin. **Montajı oku** ile adları önizleyin; ön/son ek, bul–değiştir, numaralı veya dosya başına elle adlandırma kullanın. **Yeni montajı kaydet**, montajı, parçaları ve bulunan teknik resimleri seçtiğiniz boş/yeni hedef klasöre kaydeder. Kaynak proje korunur; yeni dosyaların kayıtlı referansları doğrulanmadan işlem başarılı gösterilmez. [Kullanım, kaynaklar ve sınırlar](naming/README.md).

## Cıvata hesabı

**Mühendislik hesapları → Cıvata hesabı** altında metrik ölçü, kalite sınıfı ve yükü seçin. **Kaba diş / İnce diş** ve çapa uygun diş adımı seçilebilir. Alanlar, kapasiteler ve yaklaşık kılavuz deliği seçili adıma göre güncellenir. Çekme, kesme ve birleşik yük için cıvatanın statik dayanımı, emniyet katsayısı ve güvenli/güvensiz sonucu gösterilir. Eşit yük paylaşımına göre gerekli en az cıvata adedi ve seçili emniyet hedefine göre yük marjı hesaplanır. Birleşik yükte diğer kuvvet sabitken toplam yük sınırları da verilir. Cıvata adedi, tek/çift kesme ve dişli/dişsiz kesit desteklenir. SolidWorks bağlantısı gerekmez.

Sonuç cıvata gövdesinin ön kontrolüdür; ön sıkma ve bağlantının diğer hasar türleri ayrıca değerlendirilir. **kg yük / Newton (N) / kN** seçimi hem girdiyi hem gösterilen kapasiteyi dönüştürür. [Hesap yöntemi, kapsam ve ekran görüntüleri](docs/bolt-calculator.md). [İncelenen GitHub projeleri](bolt/README.md). [Windows EXE indirme ve derleme](packaging/README.md).

## Ağırlık hesabı

**Mühendislik hesapları → Ağırlık hesabı** bölümünde kesiti, malzemeyi,
ölçüleri, boyu ve adedi seçin. Görseldeki 19 kesit türü ve 39 malzeme kaydı
desteklenir. S235/S275/S355, DC01–DC04 DKP, galvanizli sac, C45/42CrMo4 ve
304/316/316L dahil kaliteler gruplara ayrılır. **Kalıp Çelikleri** grubunda
1.2311, 1.2312, 1.2344 ve 1.2379 kendilerine ait sabit yoğunluklarla sunulur.
Yoğunluk her malzemenin yanında
gösterilir, otomatik kullanılır ve kullanıcı tarafından değiştirilemez.
mm/cm/m dönüşümü, adet başına kg, kg/m, toplam ağırlık, sade 2D kesit çizimi
ve pano raporu vardır. SolidWorks gerekmez.

Hadde/kutu profil gibi kesitlerin ölçülerden hesabı köşe yarıçaplarını ve
eğimleri içermez. **Katalog alanından** seçeneğinde üretici kesit alanını
cm² olarak girerek hesaplayabilirsiniz. [Kullanım, kaynaklar ve örnekler](weight/README.md).

## Arayüz ve temalar

Yan menü Aktarım ve montaj ile Mühendislik hesapları olarak gruplandı. Sade ayar kartları, daha büyük sonuç sekmeleri ve bağımsız çalışma alanları kullanılır. ISO geçme sonucu kesitin üstündedir; manuel K/R değerleri özet bandında görünür. Yan menüdeki **Açık / Koyu** seçimi tüm ekranları ve ayrıntı penceresini değiştirir. Seçim `appearance` ayarıyla kaydedilir; yeniden açılışta geri gelir. İlk açılış açık temadır.

- Sonuç listesinde **Ara** alanıyla dosya adı veya açıklamaya göre arayın. **Ctrl+F** dosya sekmesini açıp aramaya odaklanır.
- **Tüm durumlar** menüsüyle bekleyen, işlenen, başarılı, atlanan veya hatalı dosyaları gösterin. **Temizle** yalnızca liste filtrelerini kaldırır. Tarama/aktarım yeniden başlatıldığında filtreler sıfırlanır.
- Filtreler aktarılacak dosyaları, toplam sayaçları veya CSV raporunu değiştirmez. PDF ve DXF/DWG ekranları kendi arama/filtre durumunu korur.
- Dosyaya çift tıklayarak veya seçili dosyada **Enter** ile tam kaynak/çıktı yollarını ve açıklamayı açın. **Ayrıntıları kopyala** bilgileri panoya kopyalar. **Escape** ayrıntı penceresini kapatır.
- Küçük pencerede ayar alanı kaydırılabilir; sonuç listesi görünür kalır. İkonlar ve tablo yazıları ekran ölçeklemesine uyum sağlar. %125 widget ölçeklemesi test edildi; tüm Windows monitör/DPI kombinasyonları bu bulut testinin kapsamında değildir.

[Güncel ekran galerisi](docs/ui-preview/README.md), [açık tema](docs/ui-preview/screenshots/iso-fits-light.png), [siyah tema](docs/ui-preview/screenshots/dxf-dwg-dark.png), [GUI tasarım/doğrulama notları](docs/gui-design.md) ve [menü akıcılığı ölçümleri](docs/menu-responsiveness.md).

## ISO GEÇMELERİ

Nominal çapı yazın; delik/mil sınıfı veya yaygın eşleşme seçin. **1–400 mm**, 11 delik ve 18 mil sınıfı için ölçü/sapma limitleri, boşluk/sıkılık, şematik kesit ve doğrusal tolerans bölgeleri gösterilir. Üç örnek ölçü, mm/µm, arama, CSV ve pano desteklenir. **Manuel kontrol** menüsünde kendi delik/mil alt ve üst sapmalarınızı girin: boşluk/sıkılık ve ISO tablosunda tam/en yakın eşleşme hesaplanır. **Montaj hedefi** menüsü bütün limitlerde kayar, ara veya sıkı geçmeye uygunluğu açıklar; en yakın ISO çift ve yaygın geçme ayrıca gösterilir. SolidWorks bağlantısı gerektirmez.

Ø50 H8/f7: **0,025–0,089 mm boşluk**. H7/h6 minimum sıfır boşlukla boşluklu; H7/k6 ara; H7/p6 sıkı geçmedir. Tür çapa göre hesaplanır. ISO 286-1/-2:2010 standart temeli, GitHub tablolarının karşılaştırması, resmî metne erişim sınırı ve elle kontrol [ISO kılavuzundadır](docs/iso-fits.md). [Açık](docs/reports/fit-compatibility/screenshots/iso-light.png) / [koyu](docs/reports/fit-compatibility/screenshots/iso-dark.png) gerçek ekranlar. [Manuel tolerans ekranı](docs/reports/fit-compatibility/screenshots/iso-manual-dark.png).

## K faktörü / yarıçap

K/R ekranı **Manuel K / R** sekmesiyle açılır; ayrıca **Hesap yardımı** ve **Montaj sonuçları** sekmeleri bulunur. Form ve sonuç listesi çalışma alanının tamamını kullanır; tarama, hesap ve dosya kayıt seçeneği kaydırma dışında kalır. Tarama veya uygulama başlayınca sonuç sekmesi açılır.

**Manuel K / R** sekmesinde her sac kalınlığının yanına K ve R değerlerini girin; **Satır ekle** ile başka kalınlıklar tanımlayın. Örneğin `1,5 mm → K=0,274, R=1,5 mm` ve `2 mm → K=0,30, R=2 mm` aynı işlemde uygulanır. Aktif montaj ve alt montajlardaki gerçek sac kalınlığı okunarak ilgili satır seçilir; **Sac-Levha → Büküm yarıçapı** ve **Büküm izni → K-Faktörü** güncellenir. Sac olmayan ve girilen kalınlıklara uymayan parçalar atlanır. Katıdan dönüştürülen saclar da etkin dönüşüm ve sac unsurlarından bulunur. [Manuel atama kılavuzu](docs/manual-k-radius.md).

**Hesap yardımı**, malzeme ve takım verileriyle BA/BD hesabı veya üretim ölçümleriyle K kalibrasyonu için kullanılır. Bu hesapların sonucu SolidWorks atamasına gönderilmez; tarama ve uygulama her zaman manuel alanlara girilmiş K/R değerlerini kullanır.

**Montajı tara** değişiklik yapmadan önizleme üretir. **Montaja K/R uygula**, aktif montajın alt montajları dahil her dosya/referans konfigürasyonuna bir kez uygular. Girdiğiniz K ve R aynen yazılır, mevcut kalınlık korunur. Varsayılan bellekte değişikliktir; dosya kaydı ayrıca seçilir.

Tarama sürerken sıraya alınan K/R uygulaması, kontroldeki montajı, ana konfigürasyonu ve dosya/konfigürasyon adetlerini yeniden karşılaştırır. Bunlar değişmişse hiçbir parçaya yazmadan durur ve yeniden tarama ister.

Hesap yardımındaki genel tablo ve yaklaşık R hesabı havada büküm önerisidir. Manuel atama bu tahminleri kullanmaz. Sac parametreleri gauge/malzeme tablosuna bağlıysa bu bağ açıklamalı olarak bildirilir. [Algoritma, elle hesap örnekleri ve SolidWorks sınırları](docs/k-factor-radius.md).

## Geometrik toleranslar / GD&T

**GEOMETRİK TOL.** sekmesinde 12 güncel ASME özelliği ve iki kaldırılmış sembol için eğitim kartları; vektör semboller ve bölge şemaları, datum ilişkisi, ölçüm yöntemi ve üretim notları gösterilir. Türkçe/İngilizce arama, açık/koyu tema, örnek datum sırası, CSV/pano ve ASME Y14.5-2018 okuma rehberi vardır. Tasarımcı **toplam t** değerini girer; boyut veya f/m/c/v sınıfından geometrik değer üretilmez.

Silindiriklik **t=0,3 mm**, iki eş eksenli silindir arasındaki toplam radyal mesafedir; ±0,3 mm değildir. Konum **Ø0,3 mm** için radyal pay 0,15 mm'dir. İsteğe bağlı ölçülmüş toplam hata, hata ≤ t aritmetiğiyle karşılaştırılır; tek çap ölçüsü, CMM analizi veya belirsizlikli kalite kabulü veya tam ASME model/resim kontrolü değildir. Normal yüzey formunda ilgili boyut toleransı girilirse t < boyut toleransı koşulu kontrol edilir (8.4). CAD modeline tolerans yazılmaz.

[Kullanım, ASME belge bölümleri ve FreeCAD-GDT karşılaştırması](docs/geometric-tolerances.md). Gerçek ekranlar: [koyu](docs/reports/black-theme/screenshots/geometric_tolerances-black.png), [açık](docs/reports/geometric-tolerances/screenshots/gdt-light.png), [konum / A-B-C](docs/reports/geometric-tolerances/screenshots/gdt-position-dark.png).

## Sac metal açınımı

1. SolidWorks'te adetlerin hesaplanacağı **ana montajı aktif yapın** ve doğru montaj konfigürasyonunu seçin. Kullanacağınız parçanın sac metal/açınım unsurlarını kontrol edin.
2. Uygulamada **DXF / DWG** ekranına geçin.
3. Kaynak klasörü yazın veya **Gözat** ile bu klasördeki bir `.SLDPRT` dosyasını seçin. Seçim, klasörü belirler; aktarım klasördeki tüm parçalara uygulanır.
4. Çıktı klasörünü seçin. **Sac kalınlığına göre klasörle** seçeneği başlangıçta açıktır:
   çıktılar `1,5 mm`, `2 mm` gibi alt klasörlere ayrılır. **Alt klasörleri tara**
   açıksa kaynak alt klasör yapısı, kalınlık klasörünün içinde korunur. Kalınlığa
   göre klasörlemeyi kapatırsanız dosyalar doğrudan seçilen çıktı yapısına yazılır.
5. **DXF** veya **DWG** seçin; yalnız seçtiğiniz biçim kaydedilir. Eski **DXF + DWG** tercihi DXF'e dönüştürülür. Varsayılan çıktı DXF'tir; büküm çizgileri varsayılan olarak kapalıdır. İstenirse **Büküm çizgilerini ekle** seçeneğini açın.
6. **Klasörü tara** ile listeyi kontrol edin ve **Açınım aktarımını başlat** düğmesine basın.
7. Dosya bazındaki sonuçları ve **Günlük** sekmesini inceleyin. **Rapor kaydet**, Türkçe karakterleri destekleyen CSV raporu üretir.

Sol menüdeki **PDF** ve **DXF / DWG** sekmeleri bağımsızdır. Uygulama açıkken sekmeler arasında geçiş yaptığınızda dosya listesi, aktarım sonuçları, günlük ve rapor durumu korunur. Klasörler ve aktarım seçenekleri her ekran için ayrı kaydedilir.

Çıktı adı **PARÇAADI - Sac kalınlığı - Montajdaki toplam adet** biçimindedir. Örneğin `BRAKET - 2 mm - 12 adet.dxf` veya `BRAKET - 1.25 mm - 12 adet.dwg`. Kalınlık, aktif sac metal unsurundan okunur ve SolidWorks'ün metre biriminden milimetreye çevrilir; dosya adına tam sayı veya gerekli ondalık basamaklarla yazılır.

Kalınlığa göre klasörleme örneği: `Çıktı/1,5 mm/BRAKET - 1.5 mm - 12 adet.dxf`.
Ayar kaydedilir; DXF ve DWG için geçerlidir. Sonuç listesi ve CSV raporu gerçek
alt klasör yolunu gösterir. [Klasörleme ayrıntıları](dxf_dwg/README.md).

Adetler aktarım başlamadan önce **aktif montajın aktif konfigürasyonundan, alt montajlar dahil** hesaplanır. Aynı alt montaj birden fazla kullanılmışsa her kullanımındaki parçalar sayılır. Aynı dosya ve referans konfigürasyonu birlikte değerlendirilir; farklı geometrilere ait konfigürasyonlar birleştirilmez. Bastırılmış bileşenler sayılmaz; gizli veya malzeme listesinden (BOM) çıkarılmış bileşenler fiziksel adet hesabına dahildir. Kaynak klasördeki montaj dışı parçalar atlanır.

Hafif bileşenler adet hesabı öncesinde çözümlenir. Çözümlenmemiş/yüklenmemiş bileşen, SpeedPak ana montaj veya SpeedPak alt montaj varsa eksik adetle dosya oluşturulmaz; açık hata gösterilir. Kalınlık veya uygun konfigürasyon adedi okunamazsa tahmini değer kullanılmaz.

Sayaçlar parçaları sayar. Sonuç ve CSV çıktı yolunda yalnız kaydedilmiş veya mevcut olduğu için atlanmış dosyalar gösterilir. Dosya doğrulanıp kaydedildikten sonraki geçici dosya/COM bağlantısı temizleme sorunları uyarı olarak gösterilir; başarılı aktarımı hata sonucuna dönüştürmez. SolidWorks aktarım hatası ve geçersiz çıktı dosyası hata olarak kalır.

Mevcut çıktılar varsayılan olarak atlanır. **Mevcut çıktıların üzerine yaz** seçilirse yalnızca yeni çıktı doğrulandıktan sonra eski dosya değiştirilir. ASCII ve ikili DXF, `ezdxf==1.4.3` ile okunup denetlenir: dosya sonu eksik, okunamayan, yapısal hata/onarım gerektiren veya model alanı boş dosyalar reddedilir. DXF doğrulaması için `requirements.txt` bağımlılıklarının güncel kurulması gerekir. DWG'de boyut ve dosya başlığı kontrol edilir; tam DWG içeriği ayrıştırılmaz. Bu kontroller açınım ölçülerinin veya yönünün doğru olduğunu kanıtlamaz.

DXF/DWG sonuç satırları, okunabilen sac kalınlığı ve montaj adedini açıklamanın başında gösterir. Boş liste, klasör seçme ve tarama adımlarını gösterir; tarama sonrasında bu yönlendirme gizlenir. Hedef dosya yolu bir klasörse aktarım hata olarak raporlanır.

Bir parça montajda birden fazla konfigürasyonla kullanılıyorsa, etkin konfigürasyon dışındakiler adları ve adetleriyle sonuç açıklamasında ve CSV raporunda belirtilir. Bitiş özetinde de uyarı gösterilir. Bu uyarı diğer konfigürasyonların otomatik aktarıldığı anlamına gelmez. Farklı konfigürasyonları ayrı çıktı klasörlerine aktarın; aynı kalınlık ve adette dosya adları aynı olabilir.

**Durdur**, işlenen parça ve seçili çıktı biçimi tamamlandıktan sonra sonraki parçaya geçişi engeller. SolidWorks'ün devam eden COM çağrısı zorla kesilmez. Çalışma sırasında ekran ve seçenek değişiklikleri kilitlenir.

### Desteklenen parçalar ve sınırlar

- Yalnızca `.SLDPRT` dosyalarının **aktif konfigürasyonu** aktarılır. Açık parçada mevcut oturumun konfigürasyonu ve bellekteki hali; kapalı parçada SolidWorks'ün dosyayı açtığında etkinleştirdiği konfigürasyon kullanılır. Bu konfigürasyon aktif montajda referans alınmıyorsa parça hata olarak raporlanır; montajdaki konfigürasyonu parçada aktif yapıp ana montaja dönün ve yeniden aktarın. Konfigürasyon adı sonuç açıklamasına yazılır. Tüm konfigürasyonları dolaşmaz.
- Aktif konfigürasyonda **bir katı gövde** olmalı ve bu gövde sac metal olmalıdır. Çok gövdeli veya sac metal olmayan parçalar açık hata ile raporlanır. Çok gövdeli parçalar için gövdeleri ayrı `.SLDPRT` dosyalarına ayırın. Montajdan parça çıkarma kapsam dışındadır.
- Kaynak parçalarda kaydetme, konfigürasyon değiştirme veya unsur bastırma işlemi çağrılmaz. Uygulamanın açtığı belgeler kapatılır; önceden açık belgeler açık tutulur. Önceki aktif belgeye dönülür. SolidWorks'ün kendi açma/aktarma işlemleri belge durumunu etkileyebileceğinden ilk denemeyi bir kopyada yapın.
- SolidWorks `IPartDoc.ExportToDWG2` sac metal aktarımı kullanılır. Varsayılan yönlendirme ve oturumun çıktı ayarları kullanılır; koordinat yönü, sürüm ve ölçü birimleri için ilk örneği hedef CAD/CAM yazılımında doğrulayın.
- Teknik resimler PDF ekranında `.SLDDRW` olarak işlenir. DXF/DWG ekranı teknik resim sayfalarını aktarmak için değildir.

## Akşam yapılacak SolidWorks kontrolü

Linux'taki otomatik testler gerçek SolidWorks üretimini doğrulayamaz. Windows'ta:

1. Bilinen ölçülerde, tek gövdeli bir sac parçanın kopyasını montaja ekleyin ve ana montajı aktif yapın. Önce DXF, ardından DWG seçerek ayrı çalıştırmalarda üretin; her çalıştırmada yalnız seçilen uzantının oluştuğunu kontrol edin. Çıktıları CAD/CAM programında açıp açınım ölçülerini ve yönünü SolidWorks açınımıyla karşılaştırın.
2. Büküm çizgileri kapalı ve açık iki ayrı klasöre aktarın. İkinci çıktıda çizgilerin eklendiğini doğrulayın.
3. Aynı hedefe tekrar aktarın: mevcut dosyalar atlanmalı. Üzerine yaz seçeneğiyle yeniden aktarımı ayrıca kontrol edin.
4. Alt klasörlerde aynı isimli iki parça kullanın; ayrı çıktı yolları oluşmalı.
5. Sac olmayan/çok gövdeli bir parça ile hatanın raporda göründüğünü ve diğer parçaların işlenmeye devam ettiğini kontrol edin.
6. Önceden açık bir parçanın işlem sonunda açık kaldığını; uygulamanın açtığı parçanın kapandığını kontrol edin.
7. Birden fazla parçayla **Durdur** düğmesini deneyin ve CSV raporunu açın. PDF ekranının çalışmasını da kontrol edin.
8. Ana montajda parçayı bir kez ve iki kez kullanılan alt montajda ikişer kez yerleştirin: dosya adında toplam **5 adet** bulunmalı. Bir alt montajı bastırınca toplam **3 adet** olmalı. Farklı sac kalınlıklarını (örneğin 1.25 mm ve 2 mm) ve farklı referans konfigürasyonlarının ayrı sayıldığını kontrol edin.
9. PDF ekranında en az iki sayfalı bir `.SLDDRW` kullanın. PDF'in sayfa sayısını ve her sayfanın çizim içeriğini kontrol edin. Çizim açık fakat aktif değilken de aktarımı deneyin; işlem sonunda önceki belge aktif olmalı. Önceden açık çizim açık kalmalı, uygulamanın açtığı çizim kapanmalı.

## Otomatik testler

Harici test bağımlılığı gerekmez:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Linux bulut ortamındaki sanal ekranla:

```bash
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user XDG_CACHE_HOME=/workspace/.cache \
  /workspace/.cloud-setup/gui-venv/bin/python -m unittest discover -s tests -v
```

Son kapsamlı kontrolde **335 test geçti**; 133 gerçek GUI testi dahildir. [Son test çıktısı](docs/test-results/latest-tests.log), [güncel K/R, tek biçim ve menü akıcılığı](docs/gui-design.md#güncel-kr-alanı-ve-menü-geçişleri). Testler; COM çağrılarını temsil eden test nesneleriyle PDF sayfaları, seçenek bitleri, belge yaşam döngüsü, dosya koruma, kısmi başarısızlık, durdurma, montaj adetleri, konfigürasyon eşleştirme, kalınlık ve dosya adlarını; gerçek Tk arayüzüyle tarama, tercihler, rapor, küçük pencere, boş liste yönlendirmesi ve işlem sırasında kapanışı sınar. Tek biçim DXF/DWG üretimi, eski ayarın dönüşümü, hızlı menü geçişleri, çizim önbelleği, boşta sayfa ön yükleme ve 4000 dosyalık liste hazırlanırken Durdur erişimi ayrıca sınandı. 10.000 satırlık sonuç listesinde toplu filtreleme, seçim/veri korunması ve canlı sonuçların sırası kontrol edildi. ISO kesitinde çap okları, çapsal/tek taraflı fark, sıfır temas ve ara geçmenin farklı örnekleri doğrulandı. [Yeni kesit görünümü](docs/screenshots/iso-section-clearance-dark.png). DXF okuyucu dört gerçek R12/R2018 ASCII/ikili örnek ve bozuk dosyalarla çalıştırılır. Örnekler ezdxf ile üretilmiştir, SolidWorks çıktısı değildir. İşçi olaylarının toplu çiziminde sonuç/günlük sırası, son özetin korunması, her turdaki olay sınırı ve günlük kaydırma konumu da kontrol edildi. [GUI akıcılık ölçümleri](docs/test-results/gui-responsiveness.json). Ayarlar, bağlantı ve program giriş noktası da test edilir. Ekran olmayan Linux oturumunda arayüz testleri atlanır. Sanal ekranın başlatılması bulut ortamının kayıtlı başlangıç talimatlarında bulunur.

Sonuçlar, test kapsamı, bulunan sorunlar ve GitHub kıyaslaması [tüm programın doğrulama raporunda](docs/program-verification.md) kayıtlıdır. DXF/DWG referanslarının ayrıntıları ve geçmiş çalışma bildirimleri için [DXF/DWG doğrulama raporuna](docs/dxf-dwg-verification.md) bakın.

## GUI yeniden kontrolü ve Word raporu

K/R öncesi GUI denetiminde 140 testin tamamı geçti; 34'ü gerçek Tk GUI testidir. Ek kabul testleri gerçek düğme komutlarını, Ctrl+F/çift tıklama/Enter/Escape olaylarını, diyalog iptallerini, filtreli CSV raporunu ve 12 yerleşim alt senaryosunu kapsar. İlk yerleşim açıkça zamanlanarak açılışın Configure olayına bağımlılığı giderildi.

[Word raporu](docs/reports/GOKWORKS_GUI_Test_Raporu_2026-10-09.docx), [test kanıtları](docs/reports/README.md) ve [test bazlı JSON](docs/reports/gui-verification-results.json). Gerçek Windows/SolidWorks üretimi bu Linux denetiminin kapsamı dışındadır.

K/R eklenmesi sonrası üç ekranın açık/koyu görüntüleri ve elle hesap kontrolünü içeren [174 testlik sürümün Word raporu](docs/reports/k-radius/GOKWORKS_K_RADIUS_GUI_Raporu_2026-10-09.docx). Önceki 140 testlik GUI raporu tarihsel kayıt olarak korunur.

Manuel K/R eklenmesi sonrası [manuel eklemedeki 189 testlik kontrol](docs/reports/manual-k-radius/README.md) ve [manuel sekmenin görüntüsü](docs/screenshots/gui-manual-k-radius-light.png).

ISO eklemesi öncesindeki GitHub kaynak karşılaştırması, 112 yerleşim senaryosu, 144 menü seçimi ve güncel sekiz ekran görüntüsü: [199 testlik son kontrol](docs/reports/final-audit/README.md). [199 testlik Word raporu](docs/reports/final-audit/GOKWORKS_Son_Kontrol_2026-10-09.docx).

ISO eklemesinden sonra **216 test / 58 GUI testi** geçti; 3217 sayısal kaynak karşılaştırması yapıldı. [ISO doğrulama raporu](docs/reports/iso-fits/README.md) ve [güncel Word raporu](docs/reports/iso-fits/GOKWORKS_ISO_Gecme_Raporu_2026-10-09.docx).

Manuel ISO eklemesinden sonra **230 test / 64 GUI testi** geçti. Delik 50 +0,02/0 ve mil 50 0/−0,02 için 0–0,04 mm boşluk; kayar geçme adayı/sınırda temas sonucu verir. [Güncel manuel ISO raporu](docs/reports/manual-iso/README.md).

Montaj uyumu eklemesinden sonra **240 test / 68 GUI testi** geçti. Mil 50 ±0,1; delik 50 +0/−0,05 mm örneği −0,15…+0,10 mm ara geçme verir. [Güncel uyumluluk ekranı](docs/reports/fit-compatibility/screenshots/iso-compatibility-dark.png) ve [Word/test raporu](docs/reports/fit-compatibility/README.md).

Geometrik tolerans eklemesinden sonra **261 test / 79 GUI testi** geçti. [Son Word raporu ve yedi gerçek ekran](docs/reports/geometric-tolerances/README.md). Önceki raporlar tarihsel kayıt olarak korunur.

GD&T ölçü denetiminden sonra **270 test / 84 GUI testi** geçti. Açısallık 45° yönü, normal tolerans oku, konum çap oku, normal profil ofsetleri, ASME mm çerçeve yazımı ve uzun sayı görünümü düzeltildi. Özelliğe göre ölçüm açıklaması ve merkezlenmiş profil ±t/2 payı eklendi. [Word raporu ve gerçek ekranlar](docs/reports/gdt-dimension-audit/README.md).

## K/R, ISO ve çalışma alanları — 10.10.2026

PDF, DXF/DWG ve K/R formları solda; sonuçlar sağda tam yüksekliği kullanır. ISO ve GD&T bağımsız hesap/şema alanlarını korur. ISO örneklerinde **Tümü / Delik esaslı / Mil esaslı** filtresi vardır; H6/k6, H8/k6 ve JS7/h6, K7/h6, N7/h6, P7/h6 gibi farklı delik örnekleri seçilebilir. Geçme türü seçilen çaptaki limitlerden hesaplanır. Manuel girişte tam sınıf, yakın referans ve eşit uzaklıklar ayrılır.

K/R COM nesnesi okuma ve aktif büküm payı alanına yazma düzeltildi; hata metinleri artık aşama ve API üyesini içerir. [Güncel ekranlar, Word raporu ve test kanıtları](docs/reports/kr-workspace-fix/README.md). Gerçek SolidWorks 2025 kabul kontrolü [yerel kılavuzdadır](docs/local-solidworks-check.md); bu Linux ortamında gerçek CAD ataması çalıştırılmadı.

## Bulutta Türkçe karakterleri doğru görüntüleme

Linux arayüzü için Python 3.13 / Tk 8.6 ortamı hazırlanmıştır. Bazı Tk
kurulumları Türkçe harfleri çizmeyebilir; uygulama böyle bir durumda eksik
yazılar göstermek yerine açıklayıcı bir hata verir.

```bash
bash /workspace/.cloud-setup/start.sh
cd /workspace/gokworks
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user \
XDG_CACHE_HOME=/workspace/.cloud-setup/cache \
/workspace/.cloud-setup/gui-venv/bin/python main.py
```

Testleri de aynı yorumlayıcıyla `-m unittest discover -s tests -v` kullanarak
çalıştırın. Windows'ta yukarıdaki Python 3.12 kurulum adımları geçerlidir.
