# Nesting & Sac Maliyet Analizi

GOKWORKS → **Üretim → Nesting · Sac maliyeti**.
Mevcut PySide6 uygulamasının modülüdür; SolidWorks veya bulut bağlantısı gerekmez.

**GOKWORKS / Nesting** çalışma alanında solda parça ağacı ve sac listesi,
ortada geometri, sağda mevcut yerel **Özellikler** paneli bulunur.
Üst komut grupları **DOSYA / DÜZENLE / YERLEŞİM / GÖRÜNÜM / RAPOR**'dur.
Sol panel yaklaşık 240 px başlar; yatay/dikey ayırıcıları sürükleyin.
Sağ panelin genişliği ve görünürlüğü uygulamanın mevcut dock altyapısında
korunur. **GÖRÜNÜM** ile panelleri gizleyin veya genişliklerini sıfırlayın.
Proje adı üst satırda düzenlenir. Diğer modüllerin tasarımı değiştirilmez.

1. **DXF ekle**: birden fazla dosya seçin. Malzeme, kalınlık,
   adet ve eğri toleransını belirtin. `$INSUNITS` yoksa mm/cm/inch seçimini
   açıkça yapın. Yardımcı katmanları adlarıyla `;` kullanarak dışlayın.
   Seçilen her dosya hemen listede görünür; okunamayanlar hata açıklamasıyla
   kalır. Dosyaya çift tıklayıp ayarlarını düzeltip yeniden okuyabilirsiniz.
2. Parçalar gerçek malzeme ve kalınlığa göre gruplanır; grup adedi, altındaki
   kesilecek adetlerin toplamıdır. Yüklenemeyen/bekleyen dosyalar ayrı gruptadır.
   İçe aktarma sırası korunur; başlığa tıklayıp sıralayabilir, arayabilirsiniz.
   **Adet** hücresine çift tıklayıp sayıyı doğrudan yazın; **Enter** veya başka
   hücreye geçiş uygular, **Esc** vazgeçer. Adetler ve grup toplamı hemen
   güncellenir; eski yerleşim kapatılır. Yeni plan için **Yerleştir**'e basın.
   Parça adına çift tıklayarak kod, açıklama, kalınlık ve malzemeyi düzenleyin.
   Alan, sınır ölçüleri ve dış/iç çevreler aynı pencerede gösterilir. Ctrl/Shift
   ile birden fazla satırı seçip birlikte kaldırabilirsiniz. Dosya yolu ve
   hata açıklaması satır üzerinde bekleyince, bütün okuma kayıtları
   **… (DXF yükleme ayrıntıları)** içinde görünür. Yerleşimden önce seçilen
   parçanın gerçek konturu ve delikleri ortada gösterilir; bu görünüm açıkça
   **yerleşim sonucu değildir** diye işaretlenir. Boyut, alan, net ağırlık ve
   çevreler sağdaki **Seçili parça** bölümündedir.
3. **Sac listesi** tanımlanmış stokları gösterir. **+** ile yeni sac ekleyin.
   Sağdan malzeme, kalınlık, en/boy ve stok adedini düzenleyip **Uygula**'ya
   basın. Taslak varken eski plan/çıktılar kapatılır. Geçersiz değer gerçek
   proje verisine yazılmaz; **Geri al** mevcut sac değerlerini geri getirir.
   Yerleştir veya Kaydet'e basmak geçerli taslağı önce uygular; geçersiz
   taslakta hata gösterilir. Stok satırı yerleşimden önce sac sınırını açar.
   **Sac ve fiyatlar…** düğmesinde özel ölçü veya 1000×2000, 1250×2500,
   1500×3000, 2000×4000 şablonunu seçin. Stok adedini ve TL/kg ya da
   TL/levha fiyatını sac satırına çift tıklayarak girin. **Malzeme kütüphanesi**
   penceresinde özel malzeme ve yoğunluk eklenebilir.
4. Sağdaki **Yerleşim** bölümünde kenar payı, parça aralığı, döndürme ve
   kaliteyi ayarlayın. Bu alanlar eski formun aynısını yönetir.
   Sığan küçük parçalar büyük parçaların deliklerine **otomatik** yerleştirilir;
   bunun için ayrı bir seçenek yoktur. Eski projeler de açılır; **Yerleştir**
   ile yeniden hesaplandığında delik içleri otomatik değerlendirilir.
   Kerf, açı/adım, hadde yönü ve **Deneme sırası kodu**
   (seed) sağdaki **Gelişmiş yerleşim** veya tam ayarlar penceresindeki
   **Gelişmiş ayarları göster** içindedir. Hesaplama süresini uygulama
   otomatik yönetir; saniye girmeniz gerekmez. Deneme sırası kodu varsayılan 42 olarak
   bırakılabilir; farklı yerleşimlerin denenme sırasını belirler.
   Operasyon giderleri, kâr ve KDV **Kesim ve ek maliyetler** içindedir.
   Bu bölümleri kapatmak girilen değerleri sıfırlamaz.
   Tam ayarlar penceresindeki değişiklikler hemen uygulanır; **Kapat** ile dönün.
   Pencereyi kapatıp açmak değerleri, seçimi veya sonucu sıfırlamaz.
5. **Yerleştir**: yerleşim hesabı arka planda çalışır; liste ve çizim aynı
   ekranda kalır. Eksik sac/stok veya geçersiz ayarda açıklama ile ayarlar açılır.
   Sac listesindeki gerçek **1. plaka / 2. plaka / 3. plaka** alt satırlarına
   veya ortadaki aynı plaka sekmelerine tıklayın;
   çok sayıda plaka varsa sekme çubuğunu kaydırın. Odak sekmedeyken
   klavyenin sol/sağ oklarıyla da geçilebilir.
   Tekerlek veya **GÖRÜNÜM → Yakınlaştır / Uzaklaştır** ile zoom,
   sürükleyerek pan, **Sığdır** ile tüm sac/parçayı gösterme kullanılabilir.
   Çizim odaktayken `+`, `−`, `Home` da çalışır. Izgara gerçek mm uzayında
   uyarlanır; koordinatlara yuvarlama veya yapışma uygulanmaz.
   **Durdur**, o ana kadar bulunan doğrulanmış sonucu korur.
   **Adlar** ile çizim üzerindeki adları açıp kapatın;
   adlar okunabilir piksel boyutundadır ve yalnız gerçek malzeme içinde
   yer varsa görünür; delikleri veya komşu parçaları kaplamaz.
   Tam ad ve koordinatlar, parça üzerinde bekleyince görünür.
   Ağaçtan seçilen parçanın görünür örnekleri belirginleşir. Başka bir
   plakadaysa ilgili plaka açılır. Hiç yerleşmemişse kaynak önizlemesi açılır.
   Çizimde parçaya tıklayınca listede seçilir; sürüklemek seçimi değiştirmez.
   Yerleşim özeti görünümün altındadır. Küçük pencerede özet kısalır;
   brüt/net/fire bilgisi ipucunda ve **Ayrıntılar** içinde korunur.
6. **RAPOR → Sonuç tablosunu göster** gerçek sac ve parça tablolarını açar:
   brüt/net/fire, verim, yerleşen/istenen adetler. Yerleşmeyen parça 0 adet
   ve **Yerleşmedi** olarak görünür. Küçük yükseklikte tekrarlanan özetler
   gizlenir; çizim ve tablo öncelikli kalır. **Ayrıntılar** maliyet dökümünü,
   **YERLEŞİM** yeniden doğrulamayı açar. **Dışa aktar / RAPOR**: DXF / Excel /
   PDF; tüm parçalar yerleşmeden açılmaz. **DOSYA**: kaydet, aç ve yeni proje.
   PDF'de parça bazlı geometri toleransları, uç hareketleri ve kaynak SHA256
   dökümü gösterilmez; bu bilgiler proje ve Excel kayıtlarında korunur.
   Kaydedilen analizler mevcut geometriyi kullanır. Şema değiştirilmedi.

[29 Ekim 2026: gerçek ekranlar, önce/sonra, mimari ve doğrulama raporu](../../docs/bugfixes/20261029-nesting-workspace/README.md).

Ekrandaki toplam, sac ve operasyon giderleri ile kâr/KDV'yi içerir.
Malzeme bedeli ayrıca gösterilir; kullanılan bir sacın fiyatı sıfırsa
**Sac fiyatı eksik** yazılır. Eksik yerleşimin maliyeti **Kısmi hesap** olarak
işaretlenir. Yalnız fiyat değişikliği aynı koordinatları yeniden kullanır ve
seçili fiziksel plakayı korur.

Fiyat/yoğunluk/operasyon gideri değişikliği aynı koordinatları arka planda
yeniden doğrulayarak maliyeti günceller. Kontur, adet, kalınlık, stok/ölçü veya
yerleşim payları değişirse eski sonuç kapatılır ve yeniden yerleşim istenir.

## Hesap ve algoritma

Motor adı **GOKWORKS NFP 1.4**. Önce hızlı ve doğrulanmış bir başlangıç
yerleşimi oluşturulur; kalan sürede NFP aramasıyla iyileştirilir. Ayrıntılı
konturun hesabı süreyi tüketirse önceki en iyi yerleşim korunur. Kenar ve
köşe adayları gerçek konturlar, aralıklar ve kenar paylarıyla denetlenir;
parça geometrisi sınır dikdörtgeniyle değiştirilmez.

Süre bütçesi parça adedi, gerçek kontur köşe sayısı, izinli dönüş açıları ve
kalite seviyesine göre başlatılır. Ölçülen deneme maliyeti sonraki aramaya
ayrılan süreyi uyarlar; art arda anlamlı iyileşme gelmezse erken bitirilir.
İlk bütçe tahmini başlangıç planı için yetersizse otomatik genişletilir.
Yoğun açı listelerinde önce izinli açıların küçük bir alt kümesiyle tam plan
aranır; parça sığmazsa diğer izinli açılar da denenir. Ayrıntılı denemelerde
açı kapsamı kademeli büyür. Tam plan bulunduğunda, sonraki kısmi deneme onu
silmez. Pahalı ayrıntı hesabı diğer parçaları bekletmez; geçerli hızlı adaya
dönülür veya parça başka plaka/denemede değerlendirilir. Sonraki denemelerde
aday aramasının bütçesi genişler. Eş alanlı stoklarda malzeme alanından çıkan plaka alt sınırına
ulaşılmışsa gereksiz denemeler durdurulur; farklı stok alanlarında bu kısa
yol uygulanmaz.

Kontur dönüşümleri ve yerleşmiş geometriler yeniden kullanılır. Dışbükey
ayrıştırmada yalnız ortak kenarlı komşular birleştirilir; her birleşimin
gerçek geometriye eşit ve dışbükey olması gerekir. Delikler ve konturlar
basitleştirilmez; son çakışma/mesafe/kenar doğrulaması aynen uygulanır.
Kaliteye göre otomatik üst sınırlar Hızlı 15, Dengeli 45, Yüksek 90 saniyedir;
bunlar bekleme hedefi değildir. Geometri işlemleri işbirlikli kontrol
noktalarında durur; bağımsız sonuç doğrulaması ayrıca tamamlanır.
Matematiksel optimum garantisi verilmez. Durdur düğmesi ve eksik sonuçta
üretim çıktısı koruması geçerlidir.

Eski projelerdeki sayısal `options.seconds` değerleri okunur. Arayüzde yeni
yerleşim başlatıldığında otomatik yönetim (`seconds: null`) kullanılır.
Doğrudan Python API çağrılarındaki sayısal bütçe desteği korunur; proje biçimi
sürümü 1'dir. Kaydet/aç, eski sonuçlar ve kaynak geometri kayıtları korunur.

[Boş levhaya rağmen eksik yerleşim düzeltmesi ve tekrar üretim](../../docs/nesting-contour-fill/README.md).

[Delik içi yerleşim, GitHub kaynakları ve önce/sonra örneği](../../docs/nesting-hole-placement/README.md).
Çarpışmalar gerçek malzeme poligonlarıyla hesaplanır;
delikler doldurulmaz. Büyük çerçeveler dış alanlarına göre önce yerleşir.
Delik içi adaylar da kerf, parça aralığı ve iki parçanın kontur hata paylarından
geçer. Dairesel/içbükey deliklerin sınır dikdörtgeni yerleşim onayı değildir.

Gerçek kontur çarpışma alanı,
`A ⊕ (−B)` Minkowski toplamıdır. İçbükey poligonlar kısıtlı Delaunay
üçgenlemesine ayrılır; yalnız dışbükey kalan birleşimler birleştirilir.
Dışbükey parçaların Minkowski toplamları birleştirilerek No-Fit Polygon
elde edilir. Bu işlem parçayı sınır dikdörtgeniyle değiştirmez.
NFP engellerinin levha içi uygun öteleme bölgesinden çıkarılmasıyla
aday koordinatlar bulunur; her aday ayrıca gerçek konturla kontrol edilir.

Alan/boyut sıralamaları, tekrarlanabilir rastgele sıra değişimleri,
izinli dönüşler ve farklı levha boyutu seçimleri denenir.
Her fiziksel plaka, kalan uygun parçalarla doldurulduktan sonra sonraki
plaka açılır. Ekrandaki ve rapordaki numaralar 1 → 2 → 3 olarak ilerler.
Skor sırasıyla yerleşmeyen adet, kullanılan levha adedi, satın alınan alan
ve yerleşimin yüksekliğidir. Başlangıç yerleşimine ek olarak Hızlı/Dengeli/Yüksek
en fazla 3/12/40 iyileştirme denemesi yapar; zaman sınırı daha erken durdurabilir. Genetik algoritma
veya kanıtlanmış matematiksel optimum olduğu iddia edilmez.

Bağımsız doğrulayıcı, NFP önbelleğini kullanmadan gerçek dönüşümler,
STRtree komşu araması, kesişim alanı, Öklid mesafesi, levha sınırı,
malzeme/kalınlık, stok, izinli açılar ve örnek/adet tutarlılığını kontrol eder.
İptal, süre sınırı veya stok yetersizliğinde eksik yerleşim gösterilir;
eksik proje üretim DXF/PDF/Excel çıktısına gönderilemez, JSON kaydedilebilir.

`kg = net alan (mm²) × t (mm) × yoğunluk (kg/m³) / 10⁹`.
Delikler ana parçanın net alanından düşülür; içlerine yerleşen küçük parçalar
net alana eklenir. Yalnız kullanılmayan alan fire/kalan alandır. `1250×2500×2×7850/10⁹`
sonucu **49,0625 kg**'dır. Fire = brüt − net; verim = net/brüt alan × 100.
Levha maliyeti TL/kg × brüt kg veya doğrudan TL/levhadır.
Her levhanın maliyeti kendi parçalarının net alanlarına dağıtılır; kuruş
yuvarlama kalanı son örnekte dengelenir. Malzeme/operasyon/kâr/KDV ayrıdır.
Kesim bedeli nominal dış+iç çevreden; piercing bedeli kapalı kontur
adedinden gelir. Tezgâh süresi, giriş/çıkış yolu ve ortak kesim uydurulmaz.

## Geometri ve üretim sınırları

- LINE, ARC, CIRCLE, LWPOLYLINE/POLYLINE (bulge dahil), SPLINE,
  ELLIPSE, döndürülmüş/ölçeklenmiş ve iç içe INSERT desteklenir.
- ARC/CIRCLE doğrudan dairesel değerlendiriciyle düzleştirilir;
  ara Bezier yaklaşımının ek hatası kullanılmaz. Kontur hesabı kullanıcı
  toleransına göre yaklaşık poligonaldir. Eğri toleransı ve uç birleştirme
  toleransı projede/raporda saklanır. Varsayılanlar 0,02 / 0,001 mm.
- Açık, dallanan, kendi kendini kesen, üst üste binen, 3B veya tanımsız
  kesim nesneleri reddedilir. Kritik geometriler `buffer(0)` ile onarılmaz.
  Kapalı/dondurulmuş katmanlar ve metin/ölçülendirme/tarama dışlanır.
- Düz konturlarda başlangıç birleştirme toleransı ayrıca belgelidir.
  Eğri çarpışma güvenliği iki parçanın kiriş hata paylarını mesafeye ekler.
  Kapalı konturların koordinatları ızgaraya yuvarlanmaz. Yakın açık uçlar
  birleştirildiyse gerçekleşen en büyük hareket ayrıca kaydedilir ve hem
  parça aralığına hem kenar payına eklenir.
- Hadde yönü kaynak DXF'in X doğrultusudur; kilit yalnız 0°/180° kabul eder.
  Aynalama kapalıdır. Delik içine yerleşim otomatiktir. İç içe adalar ayrı
  parçalar ya da dosya bazında rijit bir grup olarak içe alınabilir.
- Kerf ve bitmiş parça mesafesi farklı ayarlardır. Çarpışma aralığı
  `max(mesafe, kerf) + eğri hata payları`; kenar güvenliği
  `kenar payı + kerf/2 + eğri hata payı`dır. Mitre engel genişletmesi
  bazı dar köşelerde konservatif yer kaybına neden olabilir.
- DXF **nominal bitmiş parça konturudur**, telafili CAM takım yolu değildir.
  Makinede kerf telafisi uygulanmalıdır. Özgün ARC/CIRCLE korunur;
  `PART_OUTER/PART_INNER` kesim, diğer üç katman operatör bilgisidir.
  Çıkışla birlikte `KESIM-NOTLARI.txt` ve `KESIM-SIRASI.csv` yazılır.
  Küçük parçaların konturları onları çevreleyen deliklerden, iç konturlar kendi
  dış konturlarından önce önerilir; özgün ARC/CIRCLE bu sıra ile korunur.
  Kontur sırası DXF nesnelerine plaka/sıra XDATA bilgisiyle de eklenir.
  CAM yazılımı DXF nesnelerini yeniden sıralayabilir: CSV'deki öncelikler CAM
  içinde uygulanmalıdır. Bu çıktı telafili CAM yolu değildir.
  Kaynak dosyaya dokunulmaz.
- Büyük tekrar kullanılabilir kalıntı sınıflandırması/hurda kredisi bu
  sürümde yoktur. Bütün artık alan raporlanır, maliyetten düşülmez.
- En fazla 100 MB giriş/proje, 20.000 içe aktarılmış kontur noktası,
  10.000 parça örneği ve 600 saniye hesaplama sınırı vardır. Karmaşık konturlarda
  GEOS işlemi tamamlanana kadar iptal isteği kısa süre bekleyebilir.

## Proje ve katmanlar

`.goknest.json`, sürümlü mm geometriyi, normalize özgün DXF nesnelerini,
kaynak yol/SHA256 bilgilerini, malzemeleri, levhaları, stok/fiyatları,
ayarları, motor sürümünü, koordinatları ve hesaplanan maliyetleri içerir.
Kaynak DXF taşınsa da açılabilir. Kaynak dosyanın sonraki değişiklikleri
projeye otomatik aktarılmaz; yeniden içe alınmalıdır. Girdi imzası değişmiş
bir sonuç güncel kabul edilmez. Bozuk proje/yerleşim reddedilir.
JSON/Excel/PDF atomik; çok levhalı DXF klasörü tüm levhalar hazır olunca
yayımlanır. Mevcut DXF klasörünün üstüne yazılmaz.

Paketler: `models`, `materials`, `geometry`, `dxf_import`, `engine`, `cutting`,
`validation`, `accounting`, `dxf_export`, `storage`, `report`, `pdf_report`, `render`.
Qt sayfası `modules/nesting/ui.py`; editör/kanvas `nesting_widgets.py`.
Mevcut JobManager, tablo modeli, tema, lisans ve atomik dosya altyapısı kullanılır.

## Çalıştırma ve doğrulama

Python 3.13: `python -m pip install -r requirements-dev.txt`, ardından
`python main.py`. Testler: `QT_QPA_PLATFORM=offscreen python -m pytest
modules/nesting/tests/test_nesting.py modules/nesting/tests/test_nesting_gui.py -q` (Windows'ta ortam değişkenini
PowerShell üzerinden ayarlayın veya standart Qt platformunu kullanın).
`packaging/build_windows.py` Shapely ve GEOS DLL'lerini toplar; mevcut tek
EXE dağıtımı korunur. Paket açılış kontrolünde gerçek DXF içe alma/NFP/
ağırlık/Excel/PDF/DXF denemesi eklendi. Bu değişiklik için EXE üretilmedi;
gerçek Windows paket kontrolü sonraki istenen EXE derlemesinde çalışacak.

Referanslar ve lisans değerlendirmesi: [teknik rapor](../../docs/nesting.md).
[Toplu yükleme ve plaka sırası düzeltmesi](../../docs/nesting-bulk/README.md).
[Sade arayüz incelemesi ve plaka sekmeleri](../../docs/nesting-usability/README.md).
[Birleşik çalışma alanı ve güncel ekranlar](../../docs/nesting-workspace/README.md).
[Okunabilir PDF ve örnek rapor](../../docs/nesting-pdf-readability/README.md).

## Dosya adından kalınlık ve adet

`DXF ekle`, geometrileri okumadan önce seçilen dosyaları düzenlenebilir bir
önizlemede gösterir. **Dosya adından kalınlık ve adet oku** başlangıçta açıktır.
Kalınlık ve adet hücreleri doğrudan düzenlenir. Ctrl/Shift ile birden fazla
satır seçip **Seçili satırlara → Uygula** ile kalınlık, adet veya ikisi birlikte
atanabilir; seçilmeyen dosyalar etkilenmez. **Seçili dosyanın diğer seçenekleri**
malzeme, birim, toleranslar, katmanlar ve gruplamayı yalnız o dosyada değiştirir.
Ortak seçenekler diğer dosyaların varsayılanlarıdır. Hücrede veya dosya
seçeneklerinde elle girilmiş değerler otomatik algılamanın önündedir.

Kalınlık: `2mm`, `2 mm`, `1,2mm`, `0.6 mm`, `T2`, `T 2mm`, `T=2 mm`,
`T1.25`, `THK2`, `THK 1,2 mm`, `KALINLIK=3`, `t_2_mm` biçimleri desteklenir.
Adet: `12AD`, `12 ADET`, `AD12`, `ADET=12`, `QTY 12`, `QTY=12`,
`QUANTITY 12`, `A_12_AD` biçimleri desteklenir. Harf büyüklüğü, Türkçe
karakterler, boşluk/tab, alt çizgi ve ifadeler arasındaki tireler desteklenir.
Nokta/virgül ondalık ayırıcıdır; adet ise 1–10000 arasında tam sayıdır.
`T=-2`, `T-2`, sıfır, sonlu olmayan değer ve ondalıklı adet inceleme gerektirir.
`x12`, parça kodları, tarih/revizyon, `500x300mm` ve çap/delik ifadelerinden
kalınlık veya adet tahmin edilmez. Açık kalınlık/adet belirteci gerekir.

Örneğin aynı seçimde `GOVDE 1,2 mm 12 adet.dxf`, `KAPAK T 2mm 5 adet.dxf`,
`FLANS_T0,8_QTY20.dxf` sırasıyla **1,2 mm / 12**, **2 mm / 5**,
**0,8 mm / 20** olarak hazırlanır. Ayrıştırıcı, eşleşen ifadeleri parça
kodundan çıkarır; kaynak DXF dosyasının adını veya içeriğini değiştirmez.
Otomatik okuma kapatılırsa dosya adı kod olarak korunur ve mevcut manuel
ortak seçenekler kullanılır; elle düzenlenmiş hücreler korunur.

Durumlar: **Algılandı**, **Kısmen algılandı**, **Varsayılan değer**,
**Kontrol gerekli**. Eksik alanlarda görünen varsayılanlar kullanılabilir.
Farklı iki kalınlık/adet bulunursa ilgili alan otomatik seçilmez; kullanıcı
hücreyi açıkça düzeltmeden içe aktarma onaylanmaz. Aynı değerin tekrar yazılması
çelişki sayılmaz. Kural/hata ayrıntıları satırın ipucundadır.

### Bağımsız konturlar ve yeniden okuma

Bir DXF'te üç bağımsız parça ve 8 adet varsa sonuç **her parçadan 8, toplam
24 kesim parçası** olur. Geometri okunduktan sonra dosya **Kontrol gerekli**
durumuna alınır; parçalar projeye eklenmez ve Yerleştir çalışmaz. Dosyaya
çift tıklayıp adet dağılımı açıkça onaylanabilir veya **tek grup** seçilebilir.
Tek grup, mevcut MultiPolygon davranışıyla birlikte taşınan 8 set oluşturur.
İç delikler bağımsız parça değildir; delik içindeki bağımsız adalar ise parçadır.
Onay kaynak SHA256'sına, bulunan parça sayısına ve uygulanacak adede bağlıdır;
bunlar değişirse tekrar kontrol gerekir. Onay bütünlük kaydıdır, güvenlik imzası
değildir. Onaylanmış parçaların normal özellikleri sonradan düzenlenebilir.

Hatalı/iptal edilen kaynak tekrar okunurken önceki dosya seçenekleri korunur.
Başarılı kaynak tekrar seçilirse yeniden eklenmez. Başarılı kaynağın açık bir
`retry_id` ile okunması, geometri başarıyla doğrulandığında eski `part_ids`
parçalarını değiştirir; hata/iptal durumunda eski geometri korunur ve dosya
sorunu çözülene kadar üretim engellenir. Dosyanın bütün parçaları kaldırılırsa
kaynak da listeden çıkar ve yeniden seçilebilir. Proje toplamında 10000 örnek
sınırı, çok konturlu dosyaların gerçek toplamı dahil uygulanır.

### Entegrasyon ve kayıt sözleşmeleri

- `filename_parser.py`: Qt/DXF/GEOS bağımlılığı olmayan `parse_filename(path)`;
  `FilenameInfo` özgün dosya adı, kod, `float | None` kalınlık, `int | None` adet,
  durum, kural adları ve alan bazlı hata açıklamalarını döndürür. `RULES` açık
  belirteç kuralları ileride yeni şablonlar için genişletilebilir.
- `import_plan.py`: `normalize_options()` ve `ImportDraft`; varsayılan → algılanan
  → manuel önceliğini yönetir. Üretim sınırlarını geometri okumadan denetler.
- `import_ui.py`: `ImportDialog` ve `ImportPreviewModel`; yerel Qt model/view,
  hücre düzenleme, seçili satırlara toplu atama ve kontur onayı.
- `import_files(files, *, retry_id=None, per_file=None, **options)` eski ortak
  seçenek çağrılarını korur. `per_file`, `source` ve `options` sözlükleri listesidir.
  Seçenekler: `material`, `thickness`, `quantity`, `unit`, `tolerance`,
  `join_tolerance`, `excluded_layers`, `grouped`.
- `import_batch(entries, options, sink, stop, *, existing_quantity=0)` ortak
  seçenekleri her kaydın `options` alanıyla birleştirip `read_dxf()` çağırır.
  `nest_file` durumlarına `review`, bu olayın isteğe bağlı `contour_review`
  alanına `{sha256, count, quantity}`, özete `reviews` eklenmiştir. Qt nesneleri
  işçi threade geçmez; geometri okuma mevcut JobManager üzerinden sürer.
- `.goknest.json` **version 1** korunur. `Part` alanları değişmez. Dosyaya özel
  seçenekler mevcut `import_sources[].options` içinde saklanır. İsteğe bağlı
  `part_code`, `part_ids`, `contour_review`, `contour_approval` eklenmiştir.
  Eski projelerde bu alanlar aranmaz. Algılama durumu yeniden üretilebilir;
  onaylanmış sayısal seçenekler ve manuel `Part` değişiklikleri kalıcıdır.
- Kalınlık ve adet mevcut `Part` alanlarına aktarılır; stok eşleştirme, ağırlık,
  maliyet, yerleşim ve bütün raporlar bu alanları kullanır. NFP/geometri motoru,
  `read_dxf()` algoritması ve diğer GOKWORKS modülleri değiştirilmemiştir.

Yeni testler: `test_filename_parser.py`, `test_filename_import.py`,
`test_filename_import_gui.py`. Gerçek DXF'lerle farklı kalınlık/adetler,
100 dosyalık yükleme, manuel/toplu düzenleme, hatalı dosya/yeniden deneme,
çok kontur/delik/grup onayı, kaynak değişikliği, toplam limit, proje uyumluluğu,
nesting/ağırlık/maliyet ve Excel/PDF/DXF çıktıları doğrulanır.
Tam regresyon: `python packaging/run_windows_tests.py modules/nesting/tests
 tests/test_fusion_workbench.py tests/test_repository_structure.py`.
Linux'ta `QT_QPA_PLATFORM=offscreen` kullanılabilir. Yerel ekran görüntüleri ve
üretilen örnek raporlar depoya eklenmez; Windows CI aynı testleri yerel Qt
platformunda çalıştırır. SolidWorks bu özellik için gerekli değildir.
