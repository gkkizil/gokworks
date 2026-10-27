# Parametrik mil

GOKWORKS içinde **Üretim → Parametrik mil**. Mevcut PySide6 `BasePage`, tema,
kalıcı navigasyon ve tek CAD işi çalıştıran `JobManager` kullanılır.

## Kullanım ve kapsam

- Kademe tablosunda çap/boy hücrelerini düzenleyin; birim mm'dir. Kademe
  ekleme, kopyalama, silme ve sıra değiştirme aynı model üzerinde çalışır.
- Üst görünüş ve boyuna kesit aynı ölçeği kullanır; tablo/görünüş kademe seçimi
  senkrondur. Her iki görünüşte operasyon seçilebilir. Üst görünüş kama kanalının
  gerçek genişliğini ve yarım daire uçlarını, kesit düz tabanını gösterir.
- Segman kanalı, **0° iki ucu yuvarlak kama kanalı**, **45° eş mesafeli pah**
  ve sabit radyüs desteklenen operasyonlardır. Ayrıca tek eksenli boydan boya
  veya soldan/sağdan kör iç delik ve kademelere metrik **kozmetik diş** eklenebilir.
  Gerçek helisel diş, iç diş, matkap uç konisi, merkez deliği, freze düzlüğü
  ve omuz boşaltması henüz desteklenmez.
- **Proje kaydet/aç** `.gokshaft.json` parametre dosyası içindir. Yeni dosya
  özel oluşturulur; mevcut JSON için açık üzerine yazma onayı istenir.
  Onaydan sonra içeriği değişmiş hedef reddedilir. Dış süreçlerle aynı dosyaya
  eşzamanlı kayıt yapılmamalıdır; portable dosya sisteminde compare-and-swap yoktur.
- **SOLIDWORKS'TE ÇİZ** yeni, kaydedilmemiş bir parça oluşturur.
  **SLDPRT oluştur ve kaydet** ayrıca yeni bir `.SLDPRT` yazar; mevcut CAD
  dosyası üzerine yazılmaz. JSON ve SLDPRT farklı dosyalardır.
- Kaydedilmemiş parametrelerle uygulama kapatılırken Kaydet/At/İptal sorulur.
- Pah/radyüs **Ekle** işleminden sonra form yeni kayıt modunda kalır. Sol
  kenarı ekleyip Sağ seçerek ikinci operasyonu ekleyebilirsiniz; ilk kayıt
  taşınmaz. Listede kenar ve ölçü görünür. Mevcut kaydı düzenlemek için onu
  listeden/önizlemeden seçin. Aynı kenara ikinci pah/radyüs eklenmez.

## Standart ölçü seçimi

Segman/kama sekmesinde hedef kademeyi seçin; hemen altındaki **Standart yuva**
veya **Standart kesit** listesinden DIN önerisini seçin. Genişlik ve milde
açılacak radyal derinlik birlikte doldurulur. Kama için **Boy önerisi** kalan
kademe boyuna (`kademe.length-offset`) sığan katalog boylarını listeler;
ilk seçim mevcut boya en yakın uygun öneriyi kullanır. Boy, uçtan uca toplamdır.
Elle girilen ölçüler korunur; farklı bir ölçü yazıldığında seçim **Özel ölçü**
olarak görünür. Aynı öneriyi yeniden seçmek ölçüleri tekrar uygular.

| Kanal | Kapsam | Doldurulan ölçüler |
| --- | --- | --- |
| DIN 471, normal tip dış segman | Ø3–100 mm içinde 76 yayımlanmış nominal çap | Yuva genişliği `m`, radyal derinlik `(d1-d2)/2` |
| DIN 6885-1, Form A kama | Ø6–500 mm, 26 çap aralığı | Genişlik `b`, **mil** kanal derinliği `t1`; uygun katalog boyu varsa toplam boy |

Örnek Ø30 mm: segman yuvası `m=1,6`, `d2=28,6`, radyal derinlik `0,7` mm;
kama kesiti `8×7`, mil kanal derinliği `4` mm. Segman kalınlığı `1,5` mm yuva
genişliği değildir; kama yüksekliği `7` mm de kesme derinliği değildir.
Arayüz, segman için katalogdaki en az kenar payını da gösterir; ofseti otomatik
değiştirmez. Kenar payı, yük/hız hesabı ve üretim toleransları bu nominal ölçü
yardımcısının dışında ayrıca değerlendirilir.

Çap değişikliği veya operasyon seçimi mevcut kanalı otomatik yeniden
ölçülendirmez. Öneri güncellenir; uygulamak için kullanıcı seçer. DIN 471'de
yuvarlama/enterpolasyon yoktur: örneğin Ø30,2 için Ø30 segmanı önerilmez.
Katalog dışı çaplarda özel ölçü kullanılabilir. Kama boy listesi yayımlanan
nominal serinin bir alt kümesidir; çap aralığına ait min/max boy ve kalan
kademe boyuyla filtrelenir. Büyük kesitlerde kaynakta boy aralığı verilmemişse
boy önerisi uydurulmaz; elle girilir. Liste tedarikçi stok garantisi değildir.

Ölçüler `standards.py` içinde çevrimdışı tutulur; uygulama açılırken ağ isteği
yapılmaz. `standard_picker.py` yalnız açık kullanıcı seçiminde ölçü sinyali
gönderir; `ui.py` ilgili alanları tek işlem olarak uygular. Yeni operasyon
eklenene kadar yalnız form değişir; seçili aynı türde operasyon varsa o
operasyon güncellenir. JSON/COM sözleşmesine standart, kama yüksekliği veya
segman kalınlığı alanı eklenmez. v1 dosyası tekrar açıldığında listede görülen
standart, saklanmış bir uygunluk sertifikası değil, nominal ölçü eşleşmesidir.

Kaynaklar (kontrol: 26 Ekim 2026):

- [BENERI DIN 471 teknik tablosu](https://www.beneri.com/en/prodotto/din-471): `d1`, `S`, `d2`, `m`, `n`. Yalnız normal tipin Ø3–100 mm alt kümesi alınır.
- [SOMP kama tablosu](https://www.somp.com.lb/engineering/Keyways.shtml): çap aralıkları, `b`, `h`, **mil** `t1`, göbek `t2` ve yayımlanmış boy sınırları.
- [Elesa+Ganter DIN 6885/1](https://www.elesa-ganter.com/static/technicaldata/files/DIN6885_Keyways_EN.pdf): Ø6–50 mm kesit/derinlik ve ilk aralığın Ø6'yı kapsaması için çapraz kontrol.
- [Böllhoff Form A kataloğu](https://eshop.boellhoff.de/out/media/pdf/DIN_6885_Stahl___en.pdf): yayımlanan nominal boy serisi; SOMP tablosundaki 6 mm alt sınırı da eklenir.
- [DIN 6885-1:2021-11](https://www.dinmedia.de/en/standard/din-6885-1/346315269): güncel standardın kimliği. Tablolar açık tedarikçi/üretici kaynaklarından alınan nominal ölçülerdir; standardın tüm tolerans/uygunluk kuralları uygulanmış sayılmaz.
- [ISO/R 773:1969 durumu](https://www.iso.org/standard/5056.html): ISO tarafından geri çekilmiştir; güncel bir ISO seçeneği olarak sunulmaz veya DIN ile koşulsuz eşdeğer gösterilmez.

LinkedIn referansının video kareleri bu ortamda görüntülenemedi. Yerleşim
kullanıcının sol parametre paneli / sağ çift görünüş / alt komut tarifinden
alındı. Videoya birebir sadakat veya karşılaştırma tamamlandı iddiası yoktur.

## Model ve taşıma sözleşmesi

`Stage(id, diameter, length)`; operasyonlar kalıcı `stage_id` kullanır.
Silinen kademenin operasyonları da silinir; sıralama kimlikleri değiştirmez.
JSON: `schema="gokworks.shaft"`, `units="mm"`, `name`, `stages`,
`operations`, `minimum_wall`. Eski özelliklerle sınırlı projeler `version=1`
biçimini aynen korur. İç delik veya kozmetik diş varsa `version=2` ve ayrıca
`bore` (nesne veya null) yazılır. İki sürüm de okunur; v1'e yeni operasyon
sıkıştırılmaz. Ölçüler mm,
açılar derece; API sınırında metre/radyan kullanılır. 100 kademe, 200 operasyon
üst sınırı vardır. Sonlu pozitif ölçü, et kalınlığı, kademe sınırları ve
muhafazakâr operasyon çakışması doğrulanır; bu kontrol CAD kernelinin yerini tutmaz.

Aynı kademede segman, kama ve iki uçta pah/radyüs birlikte kullanılabilir.
Komşu kademelerin ortak omzunda iç ve dış çap kenarları ayrı değerlendirilir;
her pah/radyüs kendi kademesindeki boyu kullanır. Komşu kademeyi bütünüyle
işgal ettiği varsayılmaz. İki kenar işleminin toplam boyutu omuz yüksekliğini
aşarsa, aynı fiziksel kenara ikinci işlem eklenirse veya kesim bölgeleri
gerçekten çakışırsa ilgili işlemler anlaşılır adlarla belirtilir. Tam omuz
yüksekliğinde buluşan işlemler önizlemede tek ortak nokta kullanır.

Kama için `length` uçtan uca toplam boy, `width` freze çapı/kanal genişliği,
`depth` silindirin tepesinden düz tabana radyal derinliktir. Her iki uçta
`R=width/2`; merkezler arası mesafe `length-width` olur. Toplam boy genişlikten
en az 0,00001 mm büyük olmalıdır; daireye dönüşen sıfır düz boy desteklenmez.
Kama alanları değişmedi: eski v1 JSON dosyalarındaki kama artık bu yuvarlak profil
ile yeniden üretilir. Daha kısa/eski geçersiz ölçüler açık hata verir.
Mevcut SLDPRT dosyaları bu değişiklikle kendiliğinden dönüştürülmez.

`controller.request()` → `{operation:"create_shaft", project, plan,
output_path, verify_edit}`. Köprü doğrulanmış `process_id` ekler.
Windows PowerShell 5.1 `-STA` süreci, çalışan SOLIDWORKS kurulumundan bulunan
`SolidWorks.Interop.sldworks.dll` ve `swconst.dll` ile `ShaftHost.cs` derler.
DLL'ler uygulamayla dağıtılmaz. Mevcut `_installed_interop(process_id)` ve
bağlantı yordamları değiştirilmeden kullanılır.

Çalışan COM nesnesi `SldWorks.Application` ProgID'sinin Windows'ta kayıtlı
uygulama CLSID'siyle alınır. `typeof(SldWorks).GUID` kullanılmaz: bu tür bir
interop arayüzüdür ve GUID'si uygulama sınıfı yerine arayüz IID'sidir.
İşlem kimliği doğrulaması yine yapılır; farklı bir oturumda parça oluşturulmaz.
Bir olay grubunda hem ilerleme hem hata varsa arayüz hatayı gösterir;
eski hazırlık yazısı hata ayrıntısını örtemez.

Host önce `{event:"shaft_ready", protocol:1}` gönderir. CAD isteği ancak bu
mesajdan sonra gönderilir. Başlangıç 60 saniyede tamamlanmazsa yalnız komut
almamış yardımcı süreç sonlandırılır. CAD başladıktan sonra 180 saniye eşiği
ve 15 saniyelik durum bildirimleri vardır; devam eden COM çağrısı öldürülmez,
CAD kilidi güvenli sonuç gelene kadar tutulur. `shaft_phase` mesajlarından
sonra tek sonuç JSON'u gelir. Sonuç `success`, `process_id`, `document`,
`features`, `feature_count`, `fully_defined`, `single_body`, `rebuild_success`,
`volume_m3`, `edit_verified`, `errors` alanlarını içerir.
Başarısız sonuçta `partial_document` isteğe bağlı ek alandır. Yeni parçada
bir eskiz/kesme başarısız olduğunda belge otomatik kapatılmaz veya kaydedilmez;
son başarılı özellikler ve hatalı eskiz inceleme için açık kalır. Sonuç yine
başarısızdır; eksik parça tamamlanmış olarak raporlanmaz.

## Yerel FeatureManager hedefi

Her kademe ayrı native Revolve ve tam tanımlı dikdörtgen eskiz kullanır:

```text
MIL_ANA_GEOMETRI_01
  MIL_PROFIL_01
MIL_ANA_GEOMETRI_02
  MIL_PROFIL_02
IC_DELIK_01           (opsiyonel Cut-Revolve)
  IC_DELIK_01_ESKIZI
PAH_01                (Chamfer)
RADYUS_01             (native simple constant-radius Fillet)
SEGMAN_KANALI_01       (Cut-Revolve)
  SEGMAN_KANALI_01_ESKIZI
KAMA_KANALI_01         (Cut-Extrude)
  KAMA_KANALI_01_ESKIZI
KAMA_KANALI_01_KESME_DUZLEMI (native, milin 1 mm dışında gizli yardımcı düzlem)
KOZMETIK_DIS_01       (opsiyonel CosmeticThread; katı kesmez)
```

Bu ağaç canlı ortamda doğrulanana kadar hedef davranıştır.
Çaplar `CAP_01@MIL_PROFIL_01` adlı construction circle driving ölçüleridir;
çember merkezi kademenin sol alt köşesine, profilin sol üst köşesi çembere
geometrik olarak bağlanır. Profil yüksekliği doğrudan çapı izler; kırılgan
`YARICAP = CAP/2` denklemi gerekmez. Boylar
`BOY_01@MIL_PROFIL_01`; sonraki başlangıçlar önceki boylara bağlıdır.
Yalnız referans datum noktaları sabittir; profil topluca sabitlenmez.
Eksik tam tanımlılıkta host başarı bildirmez.
Yeni ölçü `AddDimension2` tarafından referans verilirse `DrivenState`
açıkça sürücü yapılır; atanan SI değerinin gerçekten uygulanması okunarak
doğrulanır. SOLIDWORKS bu dönüşümü reddederse referans ölçüyle devam edilmez.
Konum datumu `BASLANGIC`, dikdörtgen profilin ilişkilerinden önce ölçülür;
profil bu sürücü datuma bağlanır. Her yeni eskizde önceki unsurun kontur seçim
modu kapatılır. Kalıcı kullanıcı ayarları değiştirilmez, ilişkiler silinmez.
Eskiz kapatılıp yeniden oluşturulduktan sonra kalan denklemler çözülmeden
eklenir ve tamamı bir kez değerlendirilir; yeniden adlandırılmış ölçüler
kaydedilmeden tek tek denklem çözdürülmez.

Segman eskizleri kendi tam tanımlı construction eksenini taşır; ilk kademe
eskizinin tüketilmiş çizgisine bağımlı değildir. Her yeni özellik seçilmeden
önce kontur seçim modu kapatılır. Kanal kesmeleri tek katı gövdeyi doğrular ve
önceki özelliğin gövde kapsamını devralmadan çalışır.
Segman için eskiz `IFeature.Select2` ile işaret 0, oluşturulan gerçek eksen
`ISketchSegment.Select4` ile işaret 4 kullanılarak seçilir. İki işaretin
seçim adetleri kesme çağrısından önce doğrulanır; eksen adı çözümlemesine veya
bir önceki seçime güvenilmez.

Kullanıcı oturumunda `FeatureRevolve2` doğru seçimden sonra yine null
döndürdüğü için segman, kurulu interop'ta bulunan doğrudan
`FeatureRevolveCut2` ile oluşturulur. Tam 360° tek yön, eskizi otomatik
kapatma ve tek gövdeyi otomatik kapsam seçimi açıkça ayarlanır. Bu API
eski/uyumluluk arayüzüdür; ASLA mesh/ithal gövde veya üretim dışı görsel kesme
üretmez. Native `RevCut`, tam tanımlı eskiz ve talaş hacmi denetimi korunur.

Yapım sırası kademeler → varsa iç delik → pah → radyüs → segman → kama →
kozmetik diş şeklindedir. Böylece
uç kenarları, kanal kesimlerinin topolojiyi değiştirmesinden önce işlenir.
Python planı ile C# sırası aynıdır; eski v1 proje alanları ve operasyon kimlikleri
korunur. Mevcut geometrik çakışma denetimi korunur. Kenar merkezi ve normali
profil düzleminden model koordinatlarına çevrilir; global X varsayılmaz.
Sabit radyüs, SW 2020'den beri bu işlem için eski sayılan `FeatureFillet3`
yerine `CreateDefinition(swFmFillet)` / `ISimpleFilletFeatureData2.Initialize`
/ `CreateFeature` ile oluşturulur. Yalnız seçilen kenara simetrik dairesel
sabit yarıçap atanır; komşu teğet kenarlara otomatik yayılmaz.

Kama eskizi boyuna profil düzleminde değildir. Mil eksenini içeren, normali
radyal yönde olan referans düzlemi yerelleştirilmiş adlara bakmadan dönüşümünden
bulunur. Dış kesme düzlemi `CAP/2+1mm` konumuna taşınır. Bu düzlemde native
`CreateSketchSlot` iki teğet doğru ve iki yarım daire oluşturur. API'ye verilen
noktalar uç yaylarının merkezleridir; toplam boydan genişlik çıkarılır.
Yalnız konum datumu sabittir; slotun konumu, eksen yönü, merkez mesafesi ve uç
çapı sürücü ölçü/ilişkilerle tam tanımlanır. Eskiz, mil yüzeyinin 1 mm dışındaki
`CAP/2+1mm` yardımcı düzleminde açılır. Cut-Extrude milin içine doğru
`DERINLIK+1mm` kör kesmeyle tam `CAP/2-DERINLIK` tabanına ulaşır. API'nin
varsayılan kesme yönü eskiz normalinin tersidir; iki düzlem yönelimi de bu
kurala göre hesaplanır. Düzlem ve kesme boyu denklemleri çap/derinlik
düzenlenince güncellenir. Önce `CheckFeatureUse(CUTEXTRUDE)` ile tek kapalı,
sıfır açık kontur denetlenir; gerçek eskiz nesnesi tek başına 0 işaretiyle
seçilir. Tek katı gövde üzerinde kesme kapsamı ve otomatik seçim açıktır. Sac parça
`NormalCut` / `OptimizeGeometry` seçenekleri kapalıdır.
Kama kesme düzleminin konumu `MathPoint/MathTransform` sınırına **metre**
olarak verilir. JSON ve arayüz birimleri mm olarak korunur. Eski tabandan
dışarı kesme yolu kullanılmaz; null API dönüşünde ters yöne kör deneme
yapılmaz. Hata metni kesme API'sini ve kullanılan ölçüleri içerir.

Cut-Extrude birden fazla görüntüleme ölçüsü döndürebilir. Derinlik için ilk
ölçü veya tek ölçü varsayımı kullanılmaz: native `D1` parametresi,
`IExtrudeFeatureData2.GetDepth(true)` kör kesme boyuyla karşılaştırılır;
sonra `KESME_BOYU` adıyla denkleme bağlanır. Bu yardımcı kesici hareketi
1 mm hava payını da içerir: istenen 3 mm kanal için 4 mm harekettir.
**Gerçek kanal derinliği** ayrıca oluşan BREP taban yüzeyinin düzleminden
ölçülür. `ISurface.PlaneParams` normal ve kök noktası profil koordinatlarıyla
karşılaştırılır; taban `CAP/2-DERINLIK` konumunda değilse işlem başarı sayılmaz.
Yalnız ekranda yazan kesme ölçüsünün doğru olması yeterli değildir.

Her segman/kama kesmesinden sonra gerçek SI hacim farkı beklenen
talaş hacmiyle karşılaştırılır. Segman analitiktir; kama için kapsül ayak izi
ile silindir yüzeyi arasındaki hacim sayısal entegre edilir. Test referansı
ayrı eksende dilim entegrasyonu kullanır. Yalnız eskiz oluşması, sıfır talaş veya yanlış
tarafın kesilmesi başarı olarak raporlanmaz. Bu kontrol canlı SOLIDWORKS'te
çalışır; Windows API argüman testleri CAD çekirdeği doğrulaması olarak sunulmaz.

Segman başlangıç ve derinliği `SEGMAN_KANALI_01_KONUM`,
`SEGMAN_KANALI_01_DERINLIK` gibi global değişkenlerdir. Kanal datumunun
(-1,-1) mm konumu sayesinde `offset=0` için de konum ölçüsü pozitiftir:
`BASLANGIC = önceki boylar + KONUM + 1mm`; `KONUM_Y = CAP/2 - DERINLIK + 1mm`.
Bu yardımcı ölçüler datum payını içerir; kullanıcı gerçek ofseti global
`*_KONUM` değişkeninden düzenler. Segman genişliği `GENISLIK@..._ESKIZI`.

Kama global değişkenleri `KAMA_KANALI_01_KONUM`, `..._DERINLIK`, `..._BOY`
(toplam boy); eskiz sürücü ölçüleri `GENISLIK`, `MERKEZLER_ARASI`, `BASLANGIC`.
`GENISLIK` uç yayının çapıdır, `MERKEZLER_ARASI = BOY-GENISLIK`,
`BASLANGIC = önceki boylar + KONUM + GENISLIK/2 + 1mm`.
Sonuncusu ilk yay merkezine (-1,0) mm datumundan olan mesafedir; ters yerel
X yönünde datum (+1,0) mm olur. `KESME_Y@..._KESME_DUZLEMI` ve
`KESME_BOYU@KAMA_KANALI_01` yardımcı sürücü ölçülerdir.

## API kaynakları ve derleme

- [FeatureRevolve2 / seçim işaretleri](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.ifeaturemanager~featurerevolve2.html): eskiz 0, eksen 4 veya 16; ana boss için 16, segman kesmesi için 4 kullanılır.
- [FeatureRevolveCut2](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~FeatureRevolveCut2.html): uyumluluk kesme sözleşmesi; tam 360° ve `swAutoCloseSketch`.
- [GetLastFeatureAdded](https://help.solidworks.com/2023/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~GetLastFeatureAdded.html)
- [IPartDoc.FeatureByName](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IPartDoc~FeatureByName.html)
- [FeatureCut4](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.ifeaturemanager~featurecut4.html)
- [CheckFeatureUse](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISketch~CheckFeatureUse.html): kesmeden önce kapalı profil denetimi.
- [IFeature.Parameter](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature~Parameter.html): native `D1` derinlik parametresi.
- [ISurface.PlaneParams](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISurface~PlaneParams.html): BREP düzlem normali ve metre cinsinden kök noktası.
- [Slot boy ölçüsünün anlamı](https://help.solidworks.com/2021/english/SolidWorks/sldworks/hidd_dve_sketch_slot.htm)
- [Referans düzlem dönüşümü](https://help.solidworks.com/2022/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IRefPlane~Transform.html)
- [InsertFeatureChamfer](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~InsertFeatureChamfer.html)
- [FeatureFillet3](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.ifeaturemanager~featurefillet3.html)
- [ISimpleFilletFeatureData2](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISimpleFilletFeatureData2.html): güncel sabit radyüs tanımı.
- [EquationMgr.EvaluateAll](https://help.solidworks.com/2022/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IEquationMgr~EvaluateAll.html): dönüş değeri başarıda ve hatada -1; kod başarı kararı için denklemleri `Value`/`Status` üzerinden ayrıca okur.

`interop/check_compile.py` mevcut .NET SDK, .NET Framework 4.8 referans
klasörü ve interop DLL klasörleriyle C# 5 / warnings-as-errors derlemesi yapar:

```text
python modules/shaft_generator/interop/check_compile.py --dotnet <dotnet-yolu> --framework-references <net48-ref> --interop-dir <sldworks-dll-klasoru> --constants-dir <swconst-dll-klasoru> --output <depo-disinda/ShaftHost.dll>
```

Bu kontrol COM çalıştırmaz; kurulu sürümdeki runtime derlemesi ve canlı CAD
kabulünün yerine geçmez. API sürüm uyumluluğu hedef Windows ortamında ayrıca sınanmalıdır.

## Testler ve manuel kabul

```powershell
python -m pytest modules/shaft_generator/tests -q
# Windows PowerShell taşıması: SOLIDWORKS gerekmez, gerçek STA/pipes kullanılır.
python -m pytest modules/shaft_generator/tests/test_windows_transport.py -v
# Yalnız Windows, açık/lisanslı SOLIDWORKS ve geçerli varsayılan Part şablonuyla:
$env:GOKWORKS_SHAFT_LIVE = '1'
python -m pytest modules/shaft_generator/tests/test_live.py -v
```

Canlı testler açıkça etkinleştirilmeden atlanır. Testler yeni parçalar üretir;
oluşan test parçaları başarıda açık bırakılır. Çalışma kopyası/parametre
projesi yerine gerçek kullanıcı parçasında düzenleme yapılmaz.

Windows CI ayrıca gerçek C# hostunu geçici interop referanslarıyla derler ve
benzersiz, test amaçlı bir ProgID/ROT nesnesi üzerinden uygulama sınıfı
çözümlemesini sınar. Test kaydı sonunda silinir; SOLIDWORKS başlatılmaz ve CAD
belgesi açılmaz. `GOKWORKS_SHAFT_TEST_INTEROP` yalnız bu test referansını seçer;
referans DLL'leri EXE'ye eklenmez. Bu test canlı geometri kabulünün yerine geçmez.
Kesme API testi, gerçek interop arayüzündeki çağrı argümanlarını yakalar;
bir CAD özelliği veya katı model üretmiş gibi sahte başarı döndürmez. Aynı test
slot merkezlerini/genişliğini, iki radyal kesme yönünü, beklenen talaş hacmini ve
sıfır/ters/aşırı kesme reddini çalışan C# koduyla doğrular.
Canlı kabul listesinde tek kademede segman/kama ile birinci ve ikinci kademede
ardışık iki segman, ayrıca bu ikisinin üçüncü kademede kama ile birleşimi bulunur.
Geniş/kısa kapsül ve farklı kademelerde iki kama senaryoları da bulunur.
Son hata ekranındaki Ø30×80, Ø45×65, Ø35×50, Ø25×35 mil; birinci kademede
segman ve ikinci kademede başlangıç 5, toplam boy 60, genişlik 14, derinlik
5,5 mm kama `reported_groove_keyway` canlı kabul senaryosudur. Boy sessizce
kısaltılmaz; bu gerçek CAD testi bu ortamda çalıştırılmamıştır.
Aynı omzun iç/dış kenarlarında pah, omuzda tam buluşan pahlar ve kullanıcının
segman + kama + dört pah listesi ayrıca canlı kabul senaryolarıdır. Bunlar
burada çalıştırılmamıştır. Mock yüzey testleri yanlış katı derinliğini, yanlış
`D1` bağını, kayıp tabanı ve farklı yükseklikte taban yüzeylerini reddeder;
ötelenmiş/döndürülmüş eksen ve bölünmüş eş düzlemli tabanları da kapsar.
Ø40×100 + Ø60×50, ilk kademede iki adet 4 mm pah, ikinci kademede segman
ve sağ uçta 1 mm radyüs, `reported_two_stages_driving` canlı senaryosudur.
Referans ölçünün sürücü yapılması, reddedilen dönüşüm ve uygulanmayan değer
Windows API fixture'larıyla sınanır; bu fixture CAD çözümleyicisi değildir.
Bu ortamda canlı SOLIDWORKS geometri kabulü çalıştırılmamıştır.

Windows kabul sırası:

1. Tek kademe, çok kademe ve eş çaplı komşu kademeleri ayrı ayrı üretin.
2. Segman, sıfır başlangıçlı kanal, kama, pah ve radyüsü ayrı ayrı doğrulayın.
3. FeatureManager'da native türleri, isimleri, tek gövdeyi ve eskiz tam
   tanımlılığını kontrol edin; Imported/mesh sonucu kabul etmeyin.
4. `CAP_01` ve `BOY_01` ölçülerini değiştirip Ctrl+B/Ctrl+Q uygulayın;
   sonraki kademelerin başlangıcının güncellendiğini ölçün.
5. Kanal genişliğini, derinlik globalini ve başlangıçta sıfır olan KONUM
   globalini değiştirin; rebuild ve gerçek geometrik konumu kontrol edin.
6. Yeni SLDPRT kaydedin ve yeniden açın; ölçüleri tekrar düzenleyin.
7. Önceden açık kullanıcı belgelerinin açık kaldığını, değişiklik/kayıt
   durumlarının korunmasını ve hatada yeni parçanın inceleme için açık
   bırakıldığını, mevcut CAD dosyalarının kaydedilmediğini kontrol edin.
8. 100%, 125%, 150% Windows ölçeklerinde 820×560 ve geniş pencereyi deneyin.

Gerçek SOLIDWORKS testi bu Linux ortamında yapılamaz. Qt offscreen ölçek
kontrolü de gerçek Windows monitör/DPI kabulü olarak raporlanmamalıdır.

## 25 Ekim 2026 bulut doğrulaması ve devir

- Geliştirme dalı: `codex/parametric-shaft`; ilk doğrulama tabanı:
  `ec444776ab18da9297e310098e536abf6de3c88d`. Aşağıdaki sayılar ilk kaynak
  doğrulamasının kaydıdır; ana dal entegrasyonunun sonuçları ayrıca belirtilir.
- İlk 19 değiştirilmiş/yeni kaynak dosyası düzenleme öncesi dışarıda arşivlendi;
  mevcut modül korunarak düzeltildi. Başka modüllerin kodları değiştirilmedi.
- Modül: **78 geçti, 10 gerçek CAD testi atlandı**. Model/geometri/JSON,
  Qt seçim/düzenleme, kaydetme/kapatma, subprocess taşıması ve Qt ölçek testleri.
- Tam depo: **1.291 pytest öğesi**, unittest alt kontrolleriyle **2.169 JUnit
  kontrolü; 0 başarısızlık, 0 hata, 19 atlama**. 78 ayrı süreç, otomatik
  başarısız-test tekrarı yok. Ortak depodaki batch/timeout yordamları kullanıldı.
- Önceki uzun tek-süreç koşusunda 448 geçti, 6 atlandı, 2 kontrol başarısızdı:
  eksik pytest-timeout ve önceki Qt nesnesinin ertelenmiş silinmesi yüzünden
  widget sayımının 1'den 0'a düşmesi. Eksik test bağımlılığı kuruldu; widget
  sayımı kontrolü temiz QApplication sürecinde ayrıldı. İlk hata kayıtları
  korunur; nihai ayrık koşuda tüm test süreçleri 0 ile çıktı.
- Ortam: Linux, Python **3.12.14**, PySide6/Qt **6.10.3**, pytest **9.0.2**,
  pytest-qt **4.5.0**, pytest-timeout **2.4.0**. Bu ortamda Pillow **12.1.0**
  vardı; kaynak Windows gereksinimi Python 3.13 / Pillow 13.0.0'dır. Bu nedenle
  hedef Windows ortamıyla birebir bağımlılık eşitliği iddia edilmez.
- C#: .NET SDK 8.0.408 Roslyn, .NET Framework 4.8 referansları ve geçici
  SOLIDWORKS 2024 interop 32.1.0 referanslarıyla **C# 5, warnings-as-errors**
  derlemesi geçti. Referanslar/değiştirilmiş DLL uygulama paketine eklenmedi.
- Uygulama öz denetimi **15 modül**, iki tema ve dört çözünürlükte geçti.
  Mil sayfası ayrıca Qt offscreen 1 / 1.25 / 1.5 ölçeklerinde dar/geniş
  pencerelerde sınandı. Windows EXE veya gerçek Windows DPI testi yapılmadı.
- GitHub `main` için incelenen `2b3cfbf3c627b121e9bfae5d64e34e0d33ec47b0`,
  bu dalın tabanının doğrudan sonraki commit'idir. Pack and Go/dönüştürücü ve
  ilgili test/belge dosyaları değişmiştir; mil modülünün dört ortak dosyasıyla
  dosya örtüşmesi yoktur. İlk kaynak doğrulaması bu commit'in kodu alınmadan
  yapıldığından entegrasyon sırasında birleşik sürüm ayrıca sınanır.
- **Gerçek FeatureManager, tam tanımlı eskiz, CAD içinde ölçü düzenleme/rebuild,
  SLDPRT kaydet/aç kabulü henüz yapılmadı.** Canlı testler ve yukarıdaki manuel
  liste bu son doğrulama içindir. Windows/SOLIDWORKS kabulü ayrıca tamamlanmalıdır.

## Ana dal ile birleşik doğrulama

`2b3cfbf3c627b121e9bfae5d64e34e0d33ec47b0` ana dalı geliştirme dalına
çakışmasız alındı. Pack and Go/dönüştürücü düzeltmeleri aynen korundu.
Birleşik kaynakta mil, isimlendirme, CAD dönüştürücü, Qt iş akışları,
navigasyon, bağlantı, süreç yaşam döngüsü ve paketleme için **508 pytest
öğesi** çalıştırıldı: alt kontroller dahil **536 JUnit kontrolü, 0 başarısızlık,
0 hata, 16 ortam/canlı test atlaması**. Ana dalın yeni 35 regresyonu da geçti.
Uygulama öz denetimi 15 modül, iki tema ve çözünürlük matrisiyle tekrar geçti.

Bu kaynak entegrasyonu mevcut Windows EXE'sini yeniden üretmez. Gerçek
SOLIDWORKS özellik ağacı, eskiz çözücüsü ve Windows CAD kabulü hâlâ beklemektedir.
