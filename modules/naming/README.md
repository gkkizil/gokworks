# İsimlendirme aracı

**25 Ekim 2026 — Qt önizleme düzeltmesi:** Hedef klasör dolu, seçilmemiş veya
geçersiz olduğunda okunan montaj/parça listesi artık kaybolmaz. Ön/son ek ve
**Adı düzenle** ile adları hazırlayabilirsiniz. **Paketi oluştur**, adlar
geçerliyken ve boş/yeni bir hedef klasör seçildiğinde açılır. Yeni tarama
başarısızsa önceki montajın paketi kaydedilebilir durumda bırakılmaz.
[API incelemesi ve doğrulama kaydı](../../docs/cad-package-fixes-2026-10-25/README.md).

**19 Ekim 2026:** `GetPackAndGo` parametre bağlama hatası için uygulamaya gömülü
[güçlü türlenmiş .NET interop yolu](interop/README.md) eklendi. Güncel Qt
arayüzü, kaynak sahipliği ve dosya referansı doğrulamaları korunur. Aşağıdaki
eski Tk ekranları tarihsel kayıttır; güncel arayüz `modules/naming/ui.py` içindedir.

SolidWorks dosyalarını yeni adlarla **ayrı bir Pack and Go paketine** aktarır. Montaj, parça, alt montaj, türetilmiş parça ve bulunan teknik resim dosyalarının yolları aynı eşleştirmeyle güncellenir. Kaynak dosyalarda yerinde yeniden adlandırma yapılmaz; mevcut proje ve ona dışarıdan bağlı dosyalar kendi adlarıyla kullanılmaya devam eder. Yeni proje, çıktı klasöründeki montaj/teknik resim üzerinden açılır.

## Kullanım

1. **Montaj → İsimlendirme aracı** ekranında **Montaj klasörü** ile kaynak klasörü seçin. Bir montaj bulunursa otomatik seçilir; birden çok montaj varsa **Kaynak montaj** listesinden seçin. **Montajları bul** ile listeyi yenileyebilirsiniz. Önce seçilen klasörün içindeki montajlar aranır; doğrudan montaj yoksa alt klasörler de taranır. **Dosya / aktif montaj** bölümünden doğrudan dosya veya açık montaj da kullanılabilir.
2. **Yeni paket klasörü** ile boş veya yeni bir hedef seçin. Çıktı doğrudan bu klasöre yazılır. Dolu klasörlere veya kaynak dosyaların bulunduğu konuma kayıt engellenir; bu uyarı okunan dosya listesini gizlemez.
3. **Dosyaları oku** düğmesine basın. Kaynak montaj önceden açık olmak zorunda değildir; SolidWorks oturumu açık olmalıdır. Seçilen ana montajın Pack and Go referansları alınır. Kaynağı değiştirmek eski önizlemeyi temizler.
4. Ön/son ek, bul–değiştir veya numaralı isimlendirme seçin. Numaralı modda başlangıç ve basamak sayısı ayarlanır. Dosya uzantıları korunur.
5. Eski–yeni adları kontrol edin. Tek bir dosya için satırı seçip **Adı düzenle** kullanın. Aynı klasördeki aynı adlı model/teknik resim çifti, modelin yeni adını paylaşır; bağlantılar ayrıca dosya yolu üzerinden eşlenir.
6. **Paketi oluştur** seçin. Başarıda bütün dosya referansları kontrol edilmiş olur. Hedefteki `GOKWORKS-isimlendirme.json` eski/yeni yolları ve yeni kök dosyayı gösterir.

Önizleme montaj ağacı olarak gösterilir: parçalar ve alt montajlar bağlı oldukları montajın altında, teknik resimler ilgili modelin altında görünür. Dalları oklarla açıp kapatabilirsiniz. Birden fazla yerde kullanılan dosya **Ortak dosya** olarak işaretlenir; içeriği ilk dalda açılır ve adını herhangi bir satırdan değiştirmek bütün tekrarları günceller. Parçaya bağlı türetilmiş dosyalar **Referans** olarak gösterilir. Bu ağaç dosya bağlantılarını gösterir; bileşen adetleri veya konfigürasyon bazlı BOM değildir. Numaralar farklı dosyalara verilmeye devam eder ve Pack and Go belge sırası korunur. Adları düzenlerken kapalı dallar, seçili satır ve kaydırma konumu korunur.

Montaj ağacı güncellemesinde 8 ilgili kontrol geçti: ortak dosyanın bütün satırlardan düzenlenmesi, montaj/alt montaj/resim yerleşimi, döngülü ve 1.200 seviyeli referans grafikleri, Pack and Go sırasının korunması, ad çakışmaları, sayfa önbelleği, tema/ölçek, kayıt ve iptal. Açık/koyu tema örnekleri bu görünümle yenilendi; gerçek SolidWorks doğrulaması yapılmadı.

Teknik resimler, bastırılmış bileşenler ve Toolbox dosyaları dahil edilir. Teknik resim sayısı önizlemede görünür. SolidWorks Pack and Go'nun bulmadığı, başka klasörlerdeki resimlerin bu pakete otomatik eklendiği iddia edilmez; kaynak proje korunduğu için bu dosyaların mevcut modele olan bağlantıları yerinde kalır. Simülasyon sonuçları bu araçta paketlenmez.

Küçük ekranda ayarlar ayrı kaydırılır; önizleme tablosu ve paket düğmesi yerini korur. Açık/koyu tema, %125 ölçek, sayfa önbelleği ve kuralların kaydedilmesi desteklenir. Katı isim çakışmalarında tablo silinmez: dosyalar elle düzeltilebilir, aktarım adlar benzersiz olana kadar kapalıdır.

## Klasörden montaj seçimi — 15 Ekim 2026

Kaynak ve hedef seçimi iki klasör alanında toplanmıştır. Klasördeki montajların keşfi ve hedefin boşluk/erişim kontrolü arka planda yapılır. Ön/son ek düzenleme veya menü değiştirme sırasında hedef klasör yeniden taranmaz. Hedef tekrar seçildiğinde kontrol yenilenir; kaydetme başlamadan önce arka uç klasörü tekrar doğrular. Eski üst klasör/paket adı ayarları tek hedef yoluna dönüştürülür.

`GetPackAndGo` için önce resmi `IModelDocExtension` GUID'siyle
`QueryInterface` uygulanır. pywin32'nin ikinci `IID_IDispatch` argümanı
yalnız Python sarmalayıcısının türünü belirler; istenen dual arayüzün
adresini nesnenin varsayılan `IDispatch` arayüzüne geri çevirmez.
Çalışan nesnenin `ITypeComp.Bind` üyesi sadece `GetPackAndGo` için okunur;
başka üyelerin veya alternate dual görünümün `Geçersiz dizin` vermesi bu
yolu engellemez. Metot veya property-get olarak bulunan gerçek çağrı türü
korunur; yerel HRESULT/`[out, retval]` imzası Automation dönüşüne çevrilir.
`ITypeComp` yoksa eski tür tablosu yolu; tür bilgisi de yoksa belgelenmiş
sıfır girişli imza kullanılır. Dönüş, resmi `IPackAndGo` GUID'siyle aynı
şekilde sarılır. Otomatik makepy üretimi çalıştırılmaz.
`SavePackAndGo` ve gerekli liste çağrıları da metot olarak işaretlenir.

`ModelDocExtension` erişimi, gerçek API çağrısı ve dönen nesnenin hazırlanması
ayrı hata aşamalarıdır. Hata, kullanılan DISPID ve parametre imzasını içerir.
Arayüzde **Hatayı kopyala** düğmesi seçilen kaynakla birlikte tam metni
kopyalar; uzun teknik ayrıntılar durum etiketini büyütmez.

SolidWorks 32.1.0 interop DLL'inde `IModelDocExtension.GetPackAndGo`
DISPID **207**, sıfır giriş ve `PackAndGo` arayüz dönüşü olarak doğrulandı.
16 Ekim'deki canlı günlük, önceki genel çağrının `-2147352561` ve tür
bilgisinin `-2147352565` verdiğini doğruladı. Genel IDispatch yerine açık
dual arayüz seçimi ve tek üye bağlama bu hatalı yolu değiştirir; canlı
SolidWorks'te sorunun giderildiği henüz doğrulanmadı.

Klasörden seçilen kaynak, başka bir pencerenin arkasında görünür olsa bile
etkinleştirilir ve API'nin döndürdüğü güncel belge nesnesi kullanılır. İşlem
sonunda önceki aktif belge, görünürlük ve konfigürasyon korunur. Kaynağı
açık olduğu için gereksiz yere kapatma veya kaynak dosyayı yeniden adlandırma
yapılmaz. COM çağrıları [pywin32 b312](https://github.com/mhammond/pywin32/tree/2a277cb5552756c2b4d42b524dc36d25e0bb6354/com/win32com/client)
üzerinden incelendi; gerçek SolidWorks oturumunda doğrulama hâlâ gereklidir.

Bu değişiklik için 36 adlandırma/COM/referans koruma kontrolü geçti. Açık
arayüz seçimi, bozuk alternate dual görünümden bağımsız üye bağlama ve
yerel retval/Automation dönüşü ve geçersiz dokümantasyon dizininden bağımsız
çağrı bunlara dahildir. Model–teknik resim yeniden adlandırma/kaydetme arayüz
kontrolü de tekrar geçti. Önceki sürümde iki arayüz
kontrolü geçti: model–teknik resim çiftini yeniden adlandırıp kaydetme ve
tam hata metnini küçük pencerede kopyalama. COM sınırı test nesneleriyle temsil edildi; bu kontroller
canlı SolidWorks'te montaj ilişkilerinin denendiği anlamına gelmez.

İlgili doğrulama: 16 isimlendirme/kayıt, 9 COM/kaynak oturumu, 5 klasör keşfi, 12 isimlendirme arayüzü ve 27 menü/sekme/ayar kontrolü. Son iki isimlendirme arayüzü sorunu — küçük ekranda tablo yüksekliği ve ad çakışması giderildikten sonra kayıt düğmesinin açılması — düzeltildikten sonra ilgili kontroller yeniden geçti. Canlı SolidWorks oturumuna bağlanılmadı; bu güncellemede EXE üretilmedi.

[Yeni klasör seçimi ekranı](examples/naming-folders-dark.png), [yeniden çekim betiği](examples/capture.py). Görsel, örnek dosya kayıtlarıyla çalışan gerçek Tk arayüzünden alındı; gerçek CAD dosyası okunduğu anlamına gelmez.

## Referans koruma

- Windows ad kuralları, dosya yolu uzunluğu, uzantılar ve büyük/küçük harften bağımsız ad çakışmaları doğrulanır.
- Kaydedilmemiş değişiklik, eksik kaynak, paket dışında kalan referans veya sanal/bilinmeyen Pack and Go belgesi aktarımı engeller. Sanal parçaların adları bu API ile değiştirilemediğinden önce dış dosyaya kaydedilmesi gerekir.
- Paketleme, sonradan aktif olan belge yerine seçilmiş ana montajı kullanır. Kaynak boyutu/tarihi veya referans listesi değişirse yeniden okuma gerekir.
- Araç, kendisinin açtığı temiz kaynak belgeyi işlem sonunda kapatır; önceden açık belgeler açık tutulur. Önceki aktif belge, geçici görünürlük ve kaynak konfigürasyonu geri yüklenir. Kaynakta kaydedilmemiş değişiklik oluşmuşsa belge veri kaybını önlemek için açık bırakılır ve açıklama gösterilir.
- `SetDocumentSaveToNames` dizisi, Pack and Go'nun **kendi belge sırasıyla** verilir. Önizlemedeki numaralandırma sırası bu API sırasını değiştirmez. Adlar geri okunup planla karşılaştırılır. `SetSaveToName` için `Override=False` kullanılır; `True` özel dosya eşleştirmesini geçersiz kılabilir.
- Kaydetme her dosya için başarı kodu dönmelidir. Dosyaların varlığı/boyutu ve `GetDocumentDependencies2` ile diskte kayıtlı referansları denetlenir. Montaj ve resim referanslarının beklenen yeni dosyalara tam olarak eşleşmesi gerekir. Arama klasörleri veya kullanıcı konfigürasyonları değiştirilmez.
- Çıktı en baştan **nihai klasörüne** yazılır. Bir geçici klasörü sonradan taşımak, dosyalara yazılmış mutlak referansları bozabileceğinden böyle bir taşıma yapılmaz.
- Hata/iptalde sadece bu işlem için planlanan yeni çıktı dosyaları temizlenir; mevcut paket ve kaynakların üzerine yazılmaz. İşletim sistemi silmeyi engellerse yarım dosyalar kalabilir; hata verilen paket başarılı çıktı olarak kullanılmamalıdır. Pack and Go'nun tek COM çağrısı çalışırken iptal, çağrı tamamlandıktan sonra uygulanır.
- Önceden seçilmiş boş hedef klasör, işlem başarısız olsa da korunur. Klasörün boşluğu kayıttan önce yeniden kontrol edilir; önizlemeden sonra içine dosya eklendiyse kayıt başlamaz.

Bu kontrol kayıtlı **dosya yolu referanslarını** doğrular. Canlı SolidWorks ortamında mate çözümü, rebuild sonucu ve teknik resim görünüşleri bu bulutta doğrulanmadı. Pack and Go, modelin iç unsur/konfigürasyon bilgilerini taşır; araç bu adları veya geometriyi ayrı ayrı düzenlemez.

## İncelenen kaynaklar ve kontroller

[AngelSix / SolidDna PackAndGo](https://github.com/angelsix/solidworks-api/blob/85a773aedc87b49afda3a65c8bb650f5ba771092/SolidDna/AngelSix.SolidDna/SolidWorks/Models/Model.cs#L271): Pack and Go oluşturma, teknik resimleri dahil etme ve her dosyanın durum kodunu kontrol etme akışı referans alındı. Bizde tek ön ek yerine dosya başına ad eşleştirmesi ve çıktı referans doğrulaması kullanılır.

[xCAD kaydetme işlemi](https://github.com/xarial/xcad/blob/f9feb293f74576a6a5dbb3ffcca99502e0a257ed/src/SolidWorks/Documents/SwSaveOperation.cs): Save As hata ve referans gereksinimleri incelendi. Araç, dosyaları tek tek Save As veya dosya sistemi yeniden adlandırmasıyla taşımaz.

[API imza kaydı](examples/api-contract.json), [çevrimdışı SolidWorks dokümantasyon aynasından](https://github.com/pedropaulovc/offline-solidworks-api-docs/tree/b586c9f0c993ae7791e1b8aea79dab2a341a0147) doğrulandı. Kaynak kodu bu projelerden kopyalanmadı; GOKWORKS için bağımsız Python/Tk uygulaması yazıldı.

**20 ilgili kontrol geçti:** referans grafiği, türetilmiş parça ve resim yolları, ad kuralları, model/resim eşleştirmesi, çıktı çakışmaları, kaynak değişimi, kayıt/iptal/hata temizliği, pywin32 dizi ve byref dönüşleri, COM yaşam döngüsü, gerçek Tk tarama/önizleme/elle düzeltme/kaydetme, tema/DPI/küçük ekran, ön yükleme ve hızlı menü geçişleri. İlk kontrollerde bulunan Linux mutlak yol ayrımı ve küçük ekrandaki yerleşim sorunları giderildi; ilgili kontroller tekrar geçti. Tüm test paketi çalıştırılmadı. [Kontrol kaydı](examples/checks.json).

[Açık tema](examples/naming-light.png) · [Koyu tema](examples/naming-dark.png). Ekranlar örnek dosya bilgileriyle çalışan Tk uygulamasından alındı. Testlerde SolidWorks sınırı test nesneleriyle temsil edildi; gerçek `.sldasm/.sldprt/.slddrw` dosyaları üzerinde native Windows kabul testi henüz yapılmadı.

## Kaynak seçimi ve dosya okuma düzeltmesi — 14 Ekim 2026

Kaynak klasör/dosya seçimi ve **Aktif montajı kullan** kontrolleri eklendi.
`GetDocumentNames` ve `GetDocumentSaveToNames` çıkış parametreleri, tür bilgili
COM sarmalayıcısı `-2147352561` (zorunlu parametre eksik) döndürürse gerçek
Pack and Go alt nesnesi üzerinde late-bound/BYREF olarak yeniden çağrılır.
İlk getter erişiminde oluşan hata da bu yola alınır. Başarısız çağrılar artık
ilgili API üyesini gösterir; kullanıcının canlı oturumundaki hata bu ortamda
yeniden çalıştırılmadı.

Bu güncellemede **29 ilgili kontrol geçti**: 19 arka plan/COM/referans kontrolü
ve 10 gerçek Tk kaynak seçimi, iptal, montaj ağacı, önizleme, kayıt ve
tema/ölçek kontrolü. Açık/koyu tema örnekleri yeni kaynak alanlarını gösterir.
