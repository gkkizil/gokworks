# Akıllı Parça Bölme

[Teslim/test/performans raporu ve örnek paket](DELIVERY.md).
[Son kapsamlı denetim ve düzeltmeler](AUDIT.md).

GOKWORKS sol menüsünde **Üretim → Nesting · Sac maliyeti → Akıllı Parça Bölme**.
İki ayrı ekran aynı kalıcı sayfa kayıt sistemini kullanır. Yeni modül Nesting
motorunu değiştirmez; SolidWorks veya DWG dönüştürücü gerektirmez.

## Kullanım

1. **DXF/DWG ekle…** ile bir veya birden çok DXF/DWG seçin; eklenen her dosyadaki
   her parça **Bölünecek parçalar** listesine girer (önceki parçalar korunur, aynı
   kaynak iki kez eklenmez). Adet ve kalınlık Nesting'deki dosya adı kurallarıyla
   okunur (ör. `Flanş - 3 mm - 5 adet.dwg` → parça `Flanş`, 5 adet, 3 mm); listede
   çift tıklayıp düzeltilebilir. Dosya adında yoksa **Adet/Kalınlık (dosya adında
   yoksa)** alanları kullanılır. Okunamayan dosya durum satırında gerekçesiyle
   bildirilir, diğerleri yüklenir. DWG, Nesting ile aynı dönüştürücüyle okunur:
   kuruluysa ODA File Converter, yoksa uygulama paketindeki LibreDWG (ek indirme
   yok). Birimsiz DXF için mm/cm/inch seçin.
   Alternatif olarak Nesting'de tek parça seçip **Nesting’den seçili parçayı al**
   ile geometri, adedi ve kalınlığı kopyalayın. Özel malzemeler için bu sürümde
   bölme ekranındaki mevcut malzeme kataloğundan malzeme seçilmelidir.
2. Segment sayısı (2–64), orijinal parça adedi, merkez ve başlangıç açısını girin.
   DXF okuyucu parçayı sol alt sınırı (0,0) olacak şekilde mm'ye normalleştirir;
   özel merkez ve yasaklı bölgeler bu koordinat sistemindedir. Sınır kutusu
   merkezi ve alan ağırlık merkezi ayrı seçeneklerdir.
   Birim veya eğri toleransı sonradan değişirse **Yeniden Oku** ile gerçek
   geometri güncellenmeden bölme başlatılmaz. Yeniden okuma listedeki bütün
   dosyaları okur; seçili parça korunur. Nesting'den alınan geometri mevcut
   hassasiyetindedir; bu kaynakta DXF birim/tolerans alanları pasiftir.
3. **Parçayı Böl** seçili parçayı, **Tümünü Böl** listedeki bütün parçaları aynı
   ayarlarla tek işte böler (her parçanın sonucu/hatası listede görünür; bir
   parçanın hatası diğerlerini durdurmaz). Bölme hesabı eşit açısal veya kontur duyarlıdır. **Fireyi
   Optimize Et** farklı segmentasyonları gerçek NFP yerleşiminde karşılaştırır.
   Sabit segment sayısı değiştirilmez; kısmi yerleşim başarı sayılmaz.
4. Segment tablosunda nominal/imalat alanı, dış ölçüler, geometrik genişlik,
   birleştirme uzunluğu ve komşular görünür. **Orijinal konturu göster**, zoom,
   sürükleyerek pan ve **Sığdır** çizimi kontrol etmeyi sağlar.
5. **DXF Dışa Aktar** için yeni bir klasör adı verin. Her segment için ayrı
   DXF, bütün segmentlerin yan yana bulunduğu birleşik DXF ve `BOLME_RAPORU.json`
   üretilir. Çıktılar yeniden okunup doğrulanmadan klasör yayımlanmaz.
6. **Nesting’e Aktar** segmentleri bağımsız parça türleri olarak ekler ve
   Nesting'i açar. Örneğin 5 orijinal × 6 segment = 30 kesim parçası.
   Adet, kalınlık, malzeme, segment kimliği, geometri, levha ölçüleri ve aralık/
   kenar/kerf/rotasyon ayarları aktarılır. Diğer parçalar, dosya geçmişi, stoklar,
   fiyatlar ve maliyet ayarları korunur. Aynı kaynak tekrar aktarıldığında
   yalnız o kaynağın önceki segmentleri değiştirilir; çift ekleme yapılmaz.
   Kaynak kimliği parça notlarıyla `.goknest.json` içinde de saklanır.

Ekranlar arası geçiş veriyi silmez. **Sıfırla** bölme kaynağını ve sonuçlarını
temizler, Nesting projesini değiştirmez. Parametre değişikliği eski sonucu ve
eski sonuçla aktarım/dışa aktarımı anında kapatır. Hesaplar, DXF okuma ve
dışa aktarma mevcut JobManager üzerinde arka planda çalışır. **Durdur** aramayı
iptal eder; varsa yalnız daha önce doğrulanmış tam yerleşim korunur.

## Algoritmalar ve ölçümler

- **Eşit açısal:** her dilim 360/n derecedir. Yeterince büyük radyal kırpma
  poligonlarıyla kaynak Polygon kesiştirilir. Daire, halka, delikli/slotlu ve
  genel/asimetrik konturlar desteklenir; merkez dışarıdaysa bazı dilimler boş
  veya bağlantısız olabilir ve istenen sayı sağlanamadığı için işlem reddedilir.
- **Kontur duyarlı:** her nominal ışın çevresinde deterministik yerel açı
  taraması yapılır; en fazla ±%33 dilim açısı değişebilir. Kritik delikler,
  slotlar ve kullanıcı yasaklı poligonlarıyla kesişen/yetersiz mesafeli ışınlar
  elenir. Açılar farklı olabilir. Bölme merkezini içeren merkezi delik/bore
  birleştirme sınırıdır; bağlantı deliği yaklaşma kısıtına dahil edilmez.
  Diğer bütün iç konturlar kritik kabul edilir. Eşit açısal modda yaklaşma=0
  ise delik açılabilir; bu durum uyarı olarak gösterilir. Pozitif yaklaşma
  mesafesi her iki modda da sert kısıttır.
- **Fire optimizasyonu:** eşit açısal başlangıç, açısal tarama ve kontur duyarlı
  asimetrik adaylar kullanılır. Detaylı profilde otomatik merkezin X yönünde
  ±%2 sınır genişliği kadar değişmesi de denenir; özel merkez sabittir.
  Geometrik geçersizlik, levhaya sığmama, yinelenme ve yerleşmeyen adetler
  aday tablosunda belirtilir. Gerçek NFP motorunda adaylar aynı stok, adet,
  rotasyon, tolerans, aralık ve süre ayarlarıyla değerlendirilir.

Sıralama: geçerli/bağlantılı geometri ve üretilebilirlik ön kontrolleri;
tam yerleşim; levha sayısı; brüt alan; en büyük bağlantılı kullanılmayan
bölge toplamı; fire; birleştirme uzunluğu. Kullanılabilir artık göstergesi
kenar payı ve kesim aralığı düşülmüş en büyük bağlantılı serbest bölgedir;
dikdörtgen veya depoya kaydedilecek gerçek artık sac garantisi değildir.
Fire = (brüt levha alanı − adetli imalat konturları alanı) / brüt alan.
Birleştirme uzunluğu kaynak parça başınadır. Sonuç **bulunan en iyi çözüm**dür;
global optimum iddiası yoktur. Aynı fireyi veren sonuç iyileşme gibi sunulmaz.

| Profil | Azami aday | Her aday için NFP süresi |
| --- | ---: | ---: |
| Hızlı | 3 | 2 saniye |
| Dengeli | 7 | 3 saniye |
| Detaylı | 13 | 5 saniye |

Bunlar NFP arama bütçeleridir; DXF, geometri, dışa aktarma ve tek GEOS işlemi
ek süre alabilir. 10000 toplam segment örneği sınırı korunur. Sınır ölçüsüyle
erken eleme ve aday geometri imzası tekrar hesabı azaltır. Ayrı genetik motor
veya paralel CAD süreci eklenmez; mevcut NFP'nin kendi önbellekleri kullanılır.

GEOS/NFP sayısal topoloji hatası üreten aday gerekçesiyle listelenip reddedilir;
başka doğrulanmış tam aday varsa arama devam eder. Hiç tam aday yoksa sonuç
üretilmez. İyileşme bulunamazsa eşit açısal başlangıç korunabilir.

## Doğrulama ve imalat kapsamı

Her nominal segment tek ve geçerli Polygon olmalıdır. Segment sayısı, alan
farkı, orijinalle birleşimin simetrik farkı ve çiftler arası çakışma bağımsız
olarak kontrol edilir. Alan toleransı `max(1e-6 mm², kaynak alanı × 1e-9)`.
Birleşmiş geometrinin tek bağlantısı, iç kontur sayısı ve dış/iç sınırların
Hausdorff uzaklığı da denetlenir; sınır eşiği `max(1e-7 mm, en büyük ölçü × 1e-10)`.
Paylaşılan radyal kenarlar, 360° kapanışı dahil aynı koordinatları kullanır.
Bu kontrol alanı çok küçük olduğu halde uzun bir sayısal yarık oluşturan
geometrinin alan testinden geçmesini önler.
Özgün eğriden poligona yaklaşım sapması bu sayısal korunum toleransından
ayrıdır; DXF eğri sapması varsayılan 0,05 mm'dir ve Nesting çarpışma payında
mevcut `Part.geometry_error` sözleşmesiyle korunur.

**Minimum segment genişliği**, minimum döndürülmüş dikdörtgenin kısa kenarıdır.
**Minimum et ön kontrolü**, yarım eşik kadar erozyonda tek bağlantı kalması
ve delik–dış kenar / delikler arası mesafelerdir. Bunlar her uçtaki yerel
kalınlığı veya yapısal üretilebilirliği kanıtlamaz. Keskin dilim uçları sıfıra
daralabilir; bu ölçüm böyle uçlara garantili minimum et anlamına gelmez.
Yasaklı bölgeler GUI'de `x,y,en,boy;...` kutuları, Python API'sinde geçerli
GeoJSON poligonlarıyla girilebilir. Slotlar iç kontur olarak korunur.

Kaynak boşluğu seçilirse birleştirme çizgilerinin iki yanından boşluğun yarısı
kadar malzeme çıkarılır. İşleme payı seçilirse segment o kenarlar boyunca
komşu nominal malzemeye doğru genişler; dış parça sınırını aşmaz. İkisi aynı
anda bu sürümde uygulanmaz. Boş/bağlantısız imalat konturu reddedilir. Nominal
alan korunumu bu imalat konturlarına uygulanmaz; her iki alan ayrı raporlanır.
Kerf DXF konturuna uygulanmaz. JSON'daki `kerf_loss_estimate` nominal ortak
birleştirme hattı fiziksel olarak kesilirse `hat uzunluğu × kerf` alanı için
ön tahmindir; ayrı levha kesimlerinin toplam gerçek kerf kaybı değildir.
Kaynak/Cıvata/Diğer seçimi metadata'dır; kaynak ağzı, bağlantı elemanı, kaynak
mukavemeti, yorulma veya montaj dayanımı tasarlanmaz/onaylanmaz.

## DXF doğruluğu ve sınırlar

Mevcut sıkı Nesting okuyucusu LINE, ARC, CIRCLE, LWPOLYLINE/bulge, POLYLINE,
SPLINE ve ELLIPSE, blok dönüşümleri ve tanımlı birimleri işler. Açık,
yinelenmiş, kesişen veya 3B kesim konturları aynı kontrollerden geçer.
Kaynak dosya değiştirilmez; orijinal kaynak geometrisi bellekte korunur.
Tam kalan doğal CIRCLE konturları çıktıda CIRCLE olarak korunur. Bölünmüş
yaylar, splineler ve elipsler girişteki kontrollü kiriş toleransıyla kapalı
LWPOLYLINE olarak çıkar; genel analitik ARC/bulge geri kurma bu sürümde yoktur.
Toleranstan bağımsız analitik kesim doğruluğu iddia edilmez.

OUTER_CONTOUR ve INNER_CONTOUR gerçek kesim geometrisidir. Birleştirme
kenarları dış konturun parçasıdır; SPLIT_EDGE katmanında aynı çizgiler tekrar
üretilmez (çift kesim önlenir). REFERENCE kesim dışı katmandır. Birleşik DXF
segmentleri yan yana koyar; optimize edilmiş plaka çıktısı için Nesting'in
mevcut DXF dışa aktarması kullanılır. Rapor kimlik/adet/komşuluk/merkez/açı ve
kontrol bilgilerini taşır. Başarısız veya iptal edilmiş dışa aktarma mevcut
klasörü değiştirmez.

Bu sürüm radyal segmentasyon yapar; rastgele serbest çizgi ağı, genel levhaya
sığdırma için otomatik segment sayısı, kaynak ağzı, otomatik slot/bağlantı
tasarımı, adacıklı MultiPolygon kaynaklar ve üretim onayı kapsam dışıdır.
Uygulanabilir geometri veya tam yerleşim bulunamazsa sayı değiştirilmez ve
sonuç uydurulmaz. DXF doğrudan, DWG Nesting'in `dwg_import` dönüştürücüsüyle okunur.
Birden çok parça bölündüyse **DXF Dışa Aktar** yeni klasörün içinde her parça için
ayrı alt klasör üretir; **Nesting’e Aktar** bütün bölünmüş parçaları tek seferde
ekler (biri başarısız olursa Nesting projesi değişmez). **Fireyi Optimize Et**
seçili parçaya uygulanır.

## Kod ve test haritası

`models.py`: parametreler ve sonuçlar; `analysis.py`: DXF/kontur analizi;
`splitter.py`: radyal bölme ve adaylar; `validation.py`: bağımsız kontroller;
`optimizer.py`: gerçek NFP karşılaştırması; `adapter.py`: adetli parça/levha
adaptörü ve korumalı aktarım; `dxf_export.py`: atomik/doğrulanan DXF ve JSON;
`canvas.py`: teknik 2D önizleme; `ui.py`: native ekran ve worker bağlantıları.

Yeni bağımlılık yok: mevcut Shapely/GEOS, ezdxf ve PySide6 kullanılır. Saf
hesap katmanı Qt/CAD olmadan çağrılabilir. Araştırma ve lisans kararları:
[RESEARCH.md](RESEARCH.md).

```bash
QT_QPA_PLATFORM=offscreen python -m pytest modules/smart_splitting/tests -q
```

`test_geometry.py`: istenen daire/halka/asimetri/delik, alan/komşuluk, birim,
bozuk geometri, altı kaynak entity türü, min genişlik/et, yasaklı bölge,
adet, kaynak boşluğu/pay, DXF tekrar okuma. `test_optimizer.py`: gerçek NFP
başlangıç/aday karşılaştırması, iptal ve uygulanamazlık. `test_workbench.py`:
menü sırası, kalıcı sayfalar, iki yönlü aktarım, mevcut Nesting verisi,
çift ekleme koruması, iki tema ve Ø1800/6 delik/6 segment/1500×3000 uçtan uca
optimizasyon → DXF → aktarım → normal Nesting yeniden hesabı.
