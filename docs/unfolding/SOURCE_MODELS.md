# Unfoldo kaynak modellerinin bağımsız GOKWORKS karşılıkları

7 Kasım 2026 canlı kaynak karşılaştırması ve katı STEP güncellemesi:
[COMPLETENESS_RECHECK.md](COMPLETENESS_RECHECK.md). Güncel kabul örnekleri
ve kısıtlar [source_coverage.csv](source_coverage.csv) içindedir.

Bu genişleme mevcut `core/unfolding` motorunu ve Claude arayüzünün servis
adaptörünü kullanır. İkinci bir açınım modülü, ağdan çağrılan hesap motoru veya
kopyalanmış Unfoldo hesap kodu yoktur. Kaynak envanteri kullanıcı tarafından
5 Kasım 2026'da sağlanmıştır: 191 kimlik, 51 aile, 11 kategori, 1136 ölçü alanı,
53 kesim kümesi. HTTP/canonical/h1/sitemap kontrolü kullanıcının kanıtıdır;
bu ortamda yeniden yapılmış bir ağ doğrulaması değildir. Kaynağın 184 referans
sayısı uygulanan veya doğrulanan GOKWORKS model sayısı değildir.

## Dosyalar ve tekrar üretim

- `unfoldo_inventory.json`: kaynak alanları, varsayılanları, işaretli/ayrık
  türleri, kesim seçenekleri ve kaynak → iç kimlik eşlemesi. Kaynak varsayılanı
  değiştirilmez; GOKWORKS sınırları ayrı tutulur.
- `examples/source_models.json`: her kaynak kimliği için ayrı çalıştırılabilir
  istek. Gereken varsayılan değişiklikleri `source_default_overrides` ile açıkça
  kaydedilir. Katalog varsayılanı fiziksel geçerlilik garantisi değildir.
- `source_validation.json` ve `source_coverage.csv`: gerçek doğrulama sonuçları;
  yalnız kayıtlı olmak başarı değildir. Her çıktı için hash ve geri okuma
  durumu bulunur. Kaynak sayısı, hesap örneği sayısı, doğrulanmış çıktı sayısı
  birbirinden ayrıdır.
- Testler: `python -m pytest tests/unfolding`; çıktı kanıtı üretimi:
  `python -m tests.unfolding.verify_source_outputs --output <klasör>`.
  Qt PDF testi için grafik oturumu yoksa `QT_QPA_PLATFORM=offscreen` kullanılır.

## Hesap yöntemleri

Silindir ve gerçek oval boruda açınımın yatay koordinatı profilin yay boyudur;
üst/alt kesimlerin yükseklikleri gerçek düzlem veya çatı/yay kesiminden gelir.
Oval, iki yarım daire ve iki doğrudur. Elips ayrı parametrik kesittir.
`D=200,H=300,t=0,mid` silindir genişliği `pi*200` ve boyu 300 mm'dir.
İç çap 200 ve t=2 için orta çap 202; dış çap 200 için 198 mm'dir.
Prizmada yay çevresi kullanılmaz: düzgün çokgenin gerçek kenarları açılır.

Dik konsantrik koniler analitik halka/daire dilimidir. Tepe yüksekliği ve tam
tepe açısı alternatifleri önce aynı iki çap/dik yükseklik çözümüne dönüştürülür.
Katlar gerçekten ayrı bantlardır. İç/dış çap dönüşümü sabit ölçü düzlemlerinde
koni normalini korur. Düzlemle kesilen koninin her üreteci düzlemle analitik
kesiştirilir. Yağmur haznesinde koni gerçek duvar düzlemiyle kırpılır; arka sac
aynı kesişimin düzlemdeki ayrı parçasıdır. Koni/arka sac seçimi parça listesini
ve alanı gerçekten değiştirir.

Eğik koni ve farklı kesitli geçişlerde iki gerçek 3D kesit arasında açıkça
belirlenmiş üreteç eşlemesi ve gerçek uzunluk üçgenlemesi kullanılır. Ortak dış normal ve düz yüz eşlemesi köşeleri korur; çevre yüzdesiyle
kaydırma yapılmaz. Bir kesitteki düz kenar diğerinde tek noktaysa gerçek
üçgen fan üretilir. Offset,
üst/taban eğimi, köşe yarıçapı, çokgen köşeleri ve köşegen seçimi geometriye
katılır. Üçgenlerin kenar boyları korunur; bu, her düzgün loftun gerinimsiz
tek sac olarak açılabileceği iddiası değildir. Böyle sonuçlar fasetli yüzey
olarak etiketlenir. Düzgün yüzey şekillendirmesi ayrıca doğrulanmalıdır.

Segmentli dirsekte iki uç yarım segmenttir; n−1 ortak ek düzlemi bulunur.
Oval/yatık oval farklı kesit yönleridir. Dikiş seçimi iç/dış/yan yerini ve iki
parça seçimi gerçek parça adedini değiştirir. Redüksiyonlu segmentler sabit
çaplı boru kopyaları değildir: konik üreteçleri ve ortak düzlemsel konik
kesişim şartını kullanırlar. Gönye dirsekler ayrı iki/üç kol çözümüdür.
Boru–koni geçişinde ortak eliptik düzlem için kuadrik farkının dejenere olma
şartı çözülür; keyfî bir boru kesimi koniye yapıştırılmaz.

Branşmanda kol üreteci ana silindir/koni kuadriğine yerleştirilip ikinci derece
kesişim çözülür. Kol kurtağzı ve ana gövde deliği aynı 3D noktalar üzerinden
ayrı açılır. Delik dikişi veya gövde açık ucunu geçerse hata döner. Sonlu ana
boru yüksekliği kol parçasında da denetlenir; bu bağlam alanı kol konturunu
her küçük değişimde değiştirmek zorunda değildir. Birçoklu kol ve boru
pantolonunda her kol komşu yüzeylerle ayrıca kırpılır. Gövdeli pantolonda
uyumlu gövde–koni elipsleri ve iki koninin etkin kesişimi birlikte kullanılır.
Uyumlu konilerde F=|P|²−R²−β²; β=√(1+k²)·eksen·P+Rk bağıntısıyla
ortak kesişimler ağırlıklı doğrusal ayırıcı düzlemlere indirgenir. Her gerçek
parça en büyük β bölgesinde tutulur; komşu 3D dikişler ayrıca karşılaştırılır.

Dikdörtgen kanalların iki kapak ve gerçek duvar yolları vardır. Y/branşman
beş, ayırıcı altı levhadır. Y parçasında dış birleşim köşeleri yuvarlatılır;
kol ayıran iç köşe aynı radyüsle körlemesine doldurulmaz. Duvar `lap_top`
iki uzun kenardaki flanşı, `lap_left` iki duvar ucundaki bindirmeyi belirtir.
Kapaklar genel bir dikdörtgen büyütmesiyle şişirilmez.

Bombede yarım küre, elipsoid ve tepe+knuckle+etek torisferik meridyenleri
ayrıdır. Bir dilim hesaplanır, adedi n'dir. Meridyen örnekleme artığı, çevresel
kiriş sapması ve çevresel boy eksilmesi raporlanır. Helezonda üçgenlemeli,
eğik, konik ve halka şekillendirme çözümleri ayrıdır. Halka yöntemi dış kenar
boyunu eşleştirir; gerekli iç kenar mühendislik uzaması ayrıca verilir.
Bu çıktılar pres/çekme/yaylanma çözümü değildir.

## Birim, pay ve çıktı sözleşmesi

Uzunluk girdileri mm/inch olabilir; açı, adet ve ayrık seçenek değerleri
ölçeklenmez. Alan adları büyük/küçük harfe duyarlıdır. İç hesap ve tüm DXF/STEP
çıktısı mm'dir. `meanOnly` modeller yalnız mid kabul eder. Doğrulanmamış normal
offset ailelerinde iç/dış ölçü seçimi reddedilir; kalınlık yalnız kütlede
kullanılır. Branşmanda ana gövde ve kol aynı geometrik orta yüzey tanımını
kullanır. Bağımsız iki cidar/ölçü yüzeyi henüz yoktur.

Net geometrik alan, paylı kesim alanı, çevreleyen dikdörtgen, kesim boyu ve
kullanıcı malzemesi/fiyatıyla kütle/maliyet ayrıdır. Delikler düşülür. Parça,
öğe ve proje adetleri kendi katmanlarında birer kez uygulanır. Kenar payları
nominal kenar çizgilerine eklenir; dikiş/fold çizgileri korunur.

Adaptif eğri testi çeyrek/orta nokta artıklarını denetler; yardımcı 12/24/36/
48/72/96 çizgi seçimi ayrı bir kavramdır. Bu ölçülen artık küresel bir türev
hatası sertifikası değildir. 0.005 mm üretim doğruluğu iddiası yapılmaz.
Faset geometrisinin gerçek katlama kenarları yardımcı G çizgilerinden ayrıdır.
Büküm yönü hesaplanmadığından yeni katlama çizgileri nötr BEND
katmanındadır; BEND_UP/DOWN yönü uydurulmaz. DXF 1:1, birimli ve kapalıdır; analitik yaylar bulge olarak korunur. Pay eklenen
karma kenarlar gerektiğinde toleranslı polylinedır. PDF sayfaya sığdırılır ve
1:1 olmadığı üzerinde yazılıdır. Türkçe metin geri okunur ve sayfa render edilir.

STEP gerçek OCCT orta yüzey B-Rep'idir; solid değildir. Analitik yüzey veya
açıkça faset olarak tanımlanmış üçgen yüzeyler kullanılır; önizleme STL'sinden
sahte katı oluşturulmaz. Eğri kırpmalı analitik yüzeylerde doğrulanmış B-Rep
bulunmadığında STEP kapalıdır. İptal/süre aşımı ayrı CAD hostunda işler;
başarı ancak dosya geri okuma/alan/sınır/yüzey kontrolünden sonra bildirilir.

## Açık sınırlar

- `pipe-to-pipe-angle-branch` için kaynak `heel=true` yalnız özelliğin varlığını
  bildirir; sayısal topuk tanımı verilmemiştir. GOKWORKS `heel=true` isteğini
  açık hatayla reddeder. Uydurma topuk düzeltmesi uygulanmaz.
- Borudan dirseğe üç modelin E/Z/X ve yön tanımı için kaynak teknik çizimi
  gerekir. Mevcut bağımsız torus modeli: eksen Y, XZ düzleminde 0..90°,
  nominal kol yönü radyal 45°, A bunun Z etrafında dönüşü; E/Z/X dünya
  ötelenmeleridir. Kesişim fiziksel olarak denetlenir fakat Unfoldo ölçü
  yorumuyla birebir eşdeğerlik doğrulanmış değildir.
- Çift gönye dış ölçü varyantında H/X dış sınırdan bir çap çıkarılarak eksen
  kaymasına dönüştürülür. Kaynak ölçü çizimiyle doğrulama ayrıca gerekir.
- Tüm modellerde imalat süreci, kaynak toleransı, şekillendirme gerinimi,
  yaylanma, takım/abkant ve malzeme davranışı onayı verilmez.
- Claude ekranında yeni kaynak kesim/pay/bölme seçicileri ayrıca
  tamamlanmalıdır. Servis DTO'su ve mevcut formun proje/birim değişimi bütün
  seçenekleri korur; bu yeni seçicilerin görsel uygulaması değildir. `CLAUDE_HANDOFF.md` somut alanları listeler. Yeni 191 kaynak varyantın
  yanında mevcut projeleri açmak için yedi eski API varyantı korunmuştur.
- Canlı Windows/SolidWorks/ODA ve paketlenmiş Windows EXE testi bu Linux
  ortamında yapılmış sayılmaz.

Bu sınırlar nedeniyle katalogdaki 191 kimliğin hesaplanabilir olması, kaynağın
bütün üretim özellikleriyle eksiksiz eşdeğerlik veya imalat onayı anlamına gelmez.
