# GOKWORKS

SolidWorks teknik resimlerini PDF'e, sac açınımlarını DXF/DWG'ye aktarır; montajdaki sac parçalara malzeme ve takım seçimiyle K faktörü/iç yarıçap uygular. ISO delik/mil geçmelerini bağımsız bir hesap ekranında gösterir.

## Windows'ta çalıştırma

Python 3.12, kurulu SolidWorks ve aynı Windows kullanıcı oturumunda açık SolidWorks gerekir. Proje klasöründe:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

Mevcut kurulumu güncellerken de `pip install -r requirements.txt` komutunu çalıştırın. Arayüz için `customtkinter==6.0.0` ve ölçeklenebilir ikonlar için `Pillow==12.1.0` kullanılır.

## Arayüz ve temalar

Paylaşılan tasarım örneğine uygun sade yan menü, birleşik ayar paneli, durum kartları ve sonuç alanı kullanılır. Yan menüdeki **Açık / Koyu** seçimi dört ekranı ve ayrıntı penceresini değiştirir. Seçim `appearance` ayarıyla kaydedilir; yeniden açılışta geri gelir. İlk açılış açık temadır.

- Sonuç listesinde **Ara** alanıyla dosya adı veya açıklamaya göre arayın. **Ctrl+F** dosya sekmesini açıp aramaya odaklanır.
- **Tüm durumlar** menüsüyle bekleyen, işlenen, başarılı, atlanan veya hatalı dosyaları gösterin. **Temizle** yalnızca liste filtrelerini kaldırır. Tarama/aktarım yeniden başlatıldığında filtreler sıfırlanır.
- Filtreler aktarılacak dosyaları, toplam sayaçları veya CSV raporunu değiştirmez. PDF ve DXF/DWG ekranları kendi arama/filtre durumunu korur.
- Dosyaya çift tıklayarak veya seçili dosyada **Enter** ile tam kaynak/çıktı yollarını ve açıklamayı açın. **Ayrıntıları kopyala** bilgileri panoya kopyalar. **Escape** ayrıntı penceresini kapatır.
- Küçük pencerede ayar alanı kaydırılabilir; sonuç listesi görünür kalır. İkonlar ve tablo yazıları ekran ölçeklemesine uyum sağlar. %125 widget ölçeklemesi test edildi; tüm Windows monitör/DPI kombinasyonları bu bulut testinin kapsamında değildir.

[Açık tema](docs/screenshots/gui-dxf-dwg-light.png), [koyu tema](docs/screenshots/gui-dxf-dwg-dark.png) ve [GUI tasarım/doğrulama notları](docs/gui-design.md).

## ISO GEÇMELERİ

Nominal çapı yazın; delik/mil sınıfı veya yaygın eşleşme seçin. **1–400 mm**, 11 delik ve 18 mil sınıfı için ölçü/sapma limitleri, boşluk/sıkılık, şematik kesit ve doğrusal tolerans bölgeleri gösterilir. Üç örnek ölçü, mm/µm, arama, CSV ve pano desteklenir. SolidWorks bağlantısı gerektirmez.

Ø50 H8/f7: **0,025–0,089 mm boşluk**. H7/h6 minimum sıfır boşlukla boşluklu; H7/k6 ara; H7/p6 sıkı geçmedir. Tür çapa göre hesaplanır. ISO 286-1/-2:2010 standart temeli, GitHub tablolarının karşılaştırması, resmî metne erişim sınırı ve elle kontrol [ISO kılavuzundadır](docs/iso-fits.md). [Açık](docs/reports/iso-fits/screenshots/iso-light.png) / [koyu](docs/reports/iso-fits/screenshots/iso-dark.png) gerçek ekranlar.

## K FAKTÖR - RADIUS

**Manuel K / R** alt sekmesinde kalınlık, K ve iç R değerlerini doğrudan girebilirsiniz. Örneğin `2 mm → K=0,274, R=2 mm`: aktif montaj ve alt montajlarda yalnızca 2 mm saclar güncellenir, diğer kalınlıklar atlanır. [Manuel atama kılavuzu](docs/manual-k-radius.md).

Yeni sekme etkin: malzeme ailesi, üst bıçak uç R/açı ve alt kalıp V/açı seçilir. Katalogda nominal ölçüler ve özel giriş vardır. Otomatik V her parçanın kalınlığına göre seçilir. **Hesapla / kontrol et**, BA/BD formüllerini gösterir; bağımsız BA + ölçülmüş iç R veya dış A/B/düz boy ölçümüyle K kalibre edilebilir.

**Montajı tara** değişiklik yapmadan önizleme üretir. **Montaja K/R uygula**, aktif montajın alt montajları dahil her dosya/referans konfigürasyonuna bir kez uygular. Varsayılan bellekte değişikliktir; dosya kaydı ayrıca seçilir. Seçilen malzeme bütün saclar için varsayılır; CAD malzemesi değişmez.

Genel tablo ve yaklaşık R hesabı üretim kalibrasyonu değildir. Bu sürüm havada büküm içindir; gauge/malzeme tablosuna bağlı veya özel büküm override'ı olan parçalar açıklamalı hata alır. [Algoritma, elle hesap örnekleri ve SolidWorks sınırları](docs/k-factor-radius.md).

## Sac metal açınımı

1. SolidWorks'te adetlerin hesaplanacağı **ana montajı aktif yapın** ve doğru montaj konfigürasyonunu seçin. Kullanacağınız parçanın sac metal/açınım unsurlarını kontrol edin.
2. Uygulamada **DXF / DWG** ekranına geçin.
3. Kaynak klasörü yazın veya **Gözat** ile bu klasördeki bir `.SLDPRT` dosyasını seçin. Seçim, klasörü belirler; aktarım klasördeki tüm parçalara uygulanır.
4. Çıktı klasörünü seçin. **Alt klasörleri de tara** açıksa çıktı klasöründe aynı alt klasör yapısı korunur.
5. **DXF**, **DWG** veya **DXF + DWG** seçin. Varsayılan çıktı DXF'tir; büküm çizgileri varsayılan olarak kapalıdır. İstenirse **Büküm çizgilerini ekle** seçeneğini açın.
6. **Klasörü tara** ile listeyi kontrol edin ve **Açınım aktarımını başlat** düğmesine basın.
7. Dosya bazındaki sonuçları ve **Günlük** sekmesini inceleyin. **Rapor kaydet**, Türkçe karakterleri destekleyen CSV raporu üretir.

Sol menüdeki **PDF** ve **DXF / DWG** sekmeleri bağımsızdır. Uygulama açıkken sekmeler arasında geçiş yaptığınızda dosya listesi, aktarım sonuçları, günlük ve rapor durumu korunur. Klasörler ve aktarım seçenekleri her ekran için ayrı kaydedilir.

Çıktı adı **PARÇAADI - Sac kalınlığı - Montajdaki toplam adet** biçimindedir. Örneğin `BRAKET - 2 mm - 12 adet.dxf` veya `BRAKET - 1.25 mm - 12 adet.dwg`. Kalınlık, aktif sac metal unsurundan okunur ve SolidWorks'ün metre biriminden milimetreye çevrilir; dosya adına tam sayı veya gerekli ondalık basamaklarla yazılır.

Adetler aktarım başlamadan önce **aktif montajın aktif konfigürasyonundan, alt montajlar dahil** hesaplanır. Aynı alt montaj birden fazla kullanılmışsa her kullanımındaki parçalar sayılır. Aynı dosya ve referans konfigürasyonu birlikte değerlendirilir; farklı geometrilere ait konfigürasyonlar birleştirilmez. Bastırılmış bileşenler sayılmaz; gizli veya malzeme listesinden (BOM) çıkarılmış bileşenler fiziksel adet hesabına dahildir. Kaynak klasördeki montaj dışı parçalar atlanır.

Hafif bileşenler adet hesabı öncesinde çözümlenir. Çözümlenmemiş/yüklenmemiş bileşen, SpeedPak ana montaj veya SpeedPak alt montaj varsa eksik adetle dosya oluşturulmaz; açık hata gösterilir. Kalınlık veya uygun konfigürasyon adedi okunamazsa tahmini değer kullanılmaz.

Sayaçlar parçaları sayar. İki biçim seçildiğinde bir biçim başarısız olursa parça **Hata** olarak raporlanır; başarılı biçimin çıktısı korunur ve açıklamada belirtilir. Sonraki çalıştırma mevcut başarılı çıktıyı atlayıp eksik biçimi tekrar deneyebilir.

Mevcut çıktılar varsayılan olarak atlanır. **Mevcut çıktıların üzerine yaz** seçilirse yalnızca yeni çıktı doğrulandıktan sonra eski dosya değiştirilir. ASCII ve ikili DXF, `ezdxf==1.4.3` ile okunup denetlenir: dosya sonu eksik, okunamayan, yapısal hata/onarım gerektiren veya model alanı boş dosyalar reddedilir. DXF doğrulaması için `requirements.txt` bağımlılıklarının güncel kurulması gerekir. DWG'de boyut ve dosya başlığı kontrol edilir; tam DWG içeriği ayrıştırılmaz. Bu kontroller açınım ölçülerinin veya yönünün doğru olduğunu kanıtlamaz.

DXF/DWG sonuç satırları, okunabilen sac kalınlığı ve montaj adedini açıklamanın başında gösterir. Boş liste, klasör seçme ve tarama adımlarını gösterir; tarama sonrasında bu yönlendirme gizlenir. Hedef dosya yolu bir klasörse aktarım hata olarak raporlanır.

**Durdur**, işlenen parça ve seçili çıktı biçimleri tamamlandıktan sonra sonraki parçaya geçişi engeller. SolidWorks'ün devam eden COM çağrısı zorla kesilmez. Çalışma sırasında ekran ve seçenek değişiklikleri kilitlenir.

### Desteklenen parçalar ve sınırlar

- Yalnızca `.SLDPRT` dosyalarının **aktif konfigürasyonu** aktarılır. Açık parçada mevcut oturumun konfigürasyonu ve bellekteki hali; kapalı parçada SolidWorks'ün dosyayı açtığında etkinleştirdiği konfigürasyon kullanılır. Bu konfigürasyon aktif montajda referans alınmıyorsa parça hata olarak raporlanır; montajdaki konfigürasyonu parçada aktif yapıp ana montaja dönün ve yeniden aktarın. Konfigürasyon adı sonuç açıklamasına yazılır. Tüm konfigürasyonları dolaşmaz.
- Aktif konfigürasyonda **bir katı gövde** olmalı ve bu gövde sac metal olmalıdır. Çok gövdeli veya sac metal olmayan parçalar açık hata ile raporlanır. Çok gövdeli parçalar için gövdeleri ayrı `.SLDPRT` dosyalarına ayırın. Montajdan parça çıkarma kapsam dışındadır.
- Kaynak parçalarda kaydetme, konfigürasyon değiştirme veya unsur bastırma işlemi çağrılmaz. Uygulamanın açtığı belgeler kapatılır; önceden açık belgeler açık tutulur. Önceki aktif belgeye dönülür. SolidWorks'ün kendi açma/aktarma işlemleri belge durumunu etkileyebileceğinden ilk denemeyi bir kopyada yapın.
- SolidWorks `IPartDoc.ExportToDWG2` sac metal aktarımı kullanılır. Varsayılan yönlendirme ve oturumun çıktı ayarları kullanılır; koordinat yönü, sürüm ve ölçü birimleri için ilk örneği hedef CAD/CAM yazılımında doğrulayın.
- Teknik resimler PDF ekranında `.SLDDRW` olarak işlenir. DXF/DWG ekranı teknik resim sayfalarını aktarmak için değildir.

## Akşam yapılacak SolidWorks kontrolü

Linux'taki otomatik testler gerçek SolidWorks üretimini doğrulayamaz. Windows'ta:

1. Bilinen ölçülerde, tek gövdeli bir sac parçanın kopyasını montaja ekleyin ve ana montajı aktif yapın. DXF ve DWG'yi birlikte üretin; iki çıktıyı CAD/CAM programında açıp açınım ölçülerini ve yönünü SolidWorks açınımıyla karşılaştırın.
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
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user .venv/bin/python -m unittest discover -s tests -v
```

Son kapsamlı kontrolde **216 test geçti**; 58 gerçek GUI testi dahildir. [Güncel test kanıtları ve Word raporu](docs/reports/iso-fits/README.md). Testler; COM çağrılarını temsil eden test nesneleriyle PDF sayfaları, seçenek bitleri, belge yaşam döngüsü, dosya koruma, kısmi başarısızlık, durdurma, montaj adetleri, konfigürasyon eşleştirme, kalınlık ve dosya adlarını; gerçek Tk arayüzüyle tarama, tercihler, rapor, küçük pencere, boş liste yönlendirmesi ve işlem sırasında kapanışı sınar. DXF okuyucu dört gerçek R12/R2018 ASCII/ikili örnek ve bozuk dosyalarla çalıştırılır. Örnekler ezdxf ile üretilmiştir, SolidWorks çıktısı değildir. Ayarlar, bağlantı ve program giriş noktası da test edilir. Ekran olmayan Linux oturumunda arayüz testleri atlanır. Sanal ekranın başlatılması bulut ortamının kayıtlı başlangıç talimatlarında bulunur.

Sonuçlar, test kapsamı, bulunan sorunlar ve GitHub kıyaslaması [tüm programın doğrulama raporunda](docs/program-verification.md) kayıtlıdır. DXF/DWG referanslarının ayrıntıları ve geçmiş çalışma bildirimleri için [DXF/DWG doğrulama raporuna](docs/dxf-dwg-verification.md) bakın.

## GUI yeniden kontrolü ve Word raporu

K/R öncesi GUI denetiminde 140 testin tamamı geçti; 34'ü gerçek Tk GUI testidir. Ek kabul testleri gerçek düğme komutlarını, Ctrl+F/çift tıklama/Enter/Escape olaylarını, diyalog iptallerini, filtreli CSV raporunu ve 12 yerleşim alt senaryosunu kapsar. İlk yerleşim açıkça zamanlanarak açılışın Configure olayına bağımlılığı giderildi.

[Word raporu](docs/reports/GOKWORKS_GUI_Test_Raporu_2026-10-09.docx), [test kanıtları](docs/reports/README.md) ve [test bazlı JSON](docs/reports/gui-verification-results.json). Gerçek Windows/SolidWorks üretimi bu Linux denetiminin kapsamı dışındadır.

K/R eklenmesi sonrası üç ekranın açık/koyu görüntüleri ve elle hesap kontrolünü içeren [174 testlik sürümün Word raporu](docs/reports/k-radius/GOKWORKS_K_RADIUS_GUI_Raporu_2026-10-09.docx). Önceki 140 testlik GUI raporu tarihsel kayıt olarak korunur.

Manuel K/R eklenmesi sonrası [manuel eklemedeki 189 testlik kontrol](docs/reports/manual-k-radius/README.md) ve [manuel sekmenin görüntüsü](docs/screenshots/gui-manual-k-radius-light.png).

ISO eklemesi öncesindeki GitHub kaynak karşılaştırması, 112 yerleşim senaryosu, 144 menü seçimi ve güncel sekiz ekran görüntüsü: [199 testlik son kontrol](docs/reports/final-audit/README.md). [199 testlik Word raporu](docs/reports/final-audit/GOKWORKS_Son_Kontrol_2026-10-09.docx).

ISO eklemesinden sonra **216 test / 58 GUI testi** geçti; 3217 sayısal kaynak karşılaştırması yapıldı. [ISO doğrulama raporu](docs/reports/iso-fits/README.md) ve [güncel Word raporu](docs/reports/iso-fits/GOKWORKS_ISO_Gecme_Raporu_2026-10-09.docx).
