# Görünüş, ölçü ve pafta kuralları

## Sınıf ve ana görünüş

Sac sınıfı için hem sac gövdesi hem SheetMetal / FlatPattern unsuru aranır.
Mil / döner sınıfı için döndürme unsuru ve silindirik yüzey birlikte
değerlendirilir. Plakada düzlemsel yüzey kanıtı dış ölçülerle desteklenir.
Belirsizlikte genel sınıf kullanılır; kullanıcı sınıfı / yönü değiştirebilir.

Standart yönlerin puanı ölçülmüş düzlemsel yüzey alanı, silindir ekseninin
yönü ve kutu projeksiyonuna dayanır. Mil için ekseni gösteren görünüş,
flanş için eksene bakan görünüş tercih edilir. Karşıt yönler arasında
geometri kanıtı yoksa deterministik sıra kullanılır.

Bu puan gerçek silhouette / hidden-line analizi değildir. Özel isimli
model yönleri oluşturulmaz, kaynak kameraya veya named-view listesine
yazılmaz. Serbest yönelim / inertia tabanlı ana görünüş ileriki aşamadır.

## Pafta

Varsayılan A3 yataydır. A4–A0 ve özel boyut desteklenir. ISO 5457’ye ait
boyutlar kullanılır; tek başına bu seçim bütün ISO kurallarının sağlandığı
anlamına gelmez.

Birinci açıda üst izdüşüm ana görünüşün altında, sağ yan izdüşüm soldadır.
Üçüncü açıda yerleşim tersidir. İzdüşümler CreateUnfoldedViewAt3 ile
ana görünüşe bağlı oluşturulur; bağ ve eksen hizası sonradan doğrulanır.

Kenar boşluğu, antet şeridi, görünüş aralığı ve anotasyon alanı önce
ayrılır. Kullanıcının ölçek listesi büyükten küçüğe denenir. Sabit manuel
ölçek sessizce değiştirilmez. İlişkili izdüşümler aynı paftada kalır;
sığmazsa bağımsız izometri ayrı sayfaya alınabilir. Sac açınımı ve BOM
için ayrıca native sayfa oluşturulur.

İlk kutu hesabı yeterli sayılmaz. Gerçek GetOutline ve anotasyon metin
sınırları okunup yerleşim tekrar yapılır. Geometri ölçeklenirken ölçü metni
yüksekliği küçültülmez. Okunamayan veya sığdırılamayan alanlar raporlanır.
Ölçü metniyle birleşik kutunun merkezi, native görünüş konumu yerine
kullanılmaz: kutular IView.Position'a göre hesaplanır ve izdüşümler bu
konumlarla hizalanır. Ölçek adayları native olarak uygulanıp tekrar ölçülür;
sabit boyutlu yazı kutuları ölçek oranıyla çarpılarak aday elenmez.
Taşıma sonrasında ölçü kutuları ve ayrılmış boşluk da yeniden kontrol edilir.

## Ölçüler

Öncelik resme işaretli model ölçüleridir; Hole Wizard profile / location
ölçüleri varsa aynı native import mekanizmasıyla alınır. Montajda bütün
parça ölçülerini doldurmak yerine assembly-only kaynağı kullanılır.

SolidWorks native tekrar eleme seçeneği etkinleştirilir. İlave tekrar
denetiminde model, konfigürasyon, gerçek ölçü kimliği ve türü kullanılır;
iki ayrı deliğin aynı çapta olması tekrar sebebi değildir. Modelden
aktarılmış ölçünün değeri veya toleransı yeniden yazılmaz.
Sayısal değer ve tekrar kimliği görünüşün kendi ReferencedConfiguration
bilgisini kullanır; farklı açınım konfigürasyonuna ana modelin konfigürasyonu
atanmaz. Ölçek, modeldeki nominal ölçü değerini değiştirmez.

AutoDimension isteğe bağlıdır ve ana görünüşle sınırlıdır. Bunlar native
referans ölçüleridir; datum / tolerans / işlevsel tasarım ölçüsü olarak
sunulmaz. Her döndürülmüş metin için gerçek display-data geometrisi okunur.
Genişlik API’den alınamıyorsa tahmin açıkça WARNING üretir.

Native AlignDimensions sonrası saf Python yerleşimi, metni görünüşün
dışındaki eşit aralıklı şeritlerde konumlandırır. Görünüş sınırları,
antet alanı, kayıtlı notlar, balonlar, delik bilgileri, kesit/detay
etiketleri, tablolar ve okunabilen lider parçaları engel olarak kullanılır.
SolidWorks'e yalnız konum değişimi uygulanır. Kayıttan sonra konumlar
yeniden okunur. Kopmuş bağlantı ve fiziksel pafta dışındaki ölçü FAIL,
kalan çakışma ve okunamayan anotasyon geometrisi WARNING üretir.

## İmalat ayrıntıları

Merkez işaretleri native IView API’siyle oluşturulur. Geometriden diş
adı, H7, K faktörü, genel tolerans veya GD&T uydurulmaz.

### Delikler

Hole Wizard tipi ve geçerli parametreleri unsur tanımından okunur.
Silindir yüzü içe bakmalı, iki dairesel sınırı aynı eksende olmalı ve
alanı `2πrL` değerinden en çok %2 sapmalıdır. Hole Wizard bilgisi o yüzün
unsuruyla eşleştirilir. Aynı Wizard unsurunun eş eksenli çap kademeleri
tek delik konumu olarak sayılır.

Delik ekseni görünüş normaline paralel olmalı (`|dot| ≥ 0,9999`) ve o
görünüşte gerçek bir çembersel sınır eşleşmelidir. Önce native delik
bilgisi içe aktarılır. Aynı görünüşte içe aktarılamayan en az sekiz Wizard
deliğinde, doğrulanmış orijin köşesi ve yeterli boşluk varsa tablo denenir.
Kalan Wizard delikleri aynı model parametrelerine göre bir notta
gruplanır. Salt geometriden eşleştirilen deliğe yalnız çap ölçüsü eklenir.
JSON her grubun kaynağını, görünüşünü ve kullanılan yöntemi kaydeder.

### Kesit ve detay

Kesit A-A şu kanıtlardan biriyle seçilir. Modelde kör olarak tanımlanmış
bir delik, dairesel dip yüzü doğrulanmış bir kör silindir, karşı havşa veya
ortak eksende bitişen farklı çaplı iki iç silindir. Kademeler arasında
en az 0,1 mm çap farkı ve en çok 0,02 mm ortak eksen/uç sapması aranır.
Eksen standart doğrultudaysa çizgi delik merkezinden geçer. Eksen ana
görünüşe dikse kesit çizgisi görünüşün uzun doğrultusunda delik
merkezinden geçer. Kesit birinci/üçüncü açıya göre hizalanır.

Ölçülen radyüs, pah veya Hole Wizard kanal genişliği ana görünüşte
3 mm'nin altına düştüğünde, ayrıntıyı kâğıt üzerinde en az 3 mm yapan ve
ana görünüş ölçeğini aşan ilk 2:1, 5:1 veya 10:1 oranı seçilir. Her resim
için bir kesit ve bir detay planlanabilir. Ana paftanın ölçeği korunur.
Ayrıntı sığmadığında kaynak görünüşün bir kopyasıyla aynı ek paftaya
alınır. Pafta planı taslak önizleme ve üretimde ortaktır.

### Sac ve montaj

Sac gövdeleri kalıcı API kimlikleriyle sıralanır; görüntülenen ad veya
GetBodies2 sırası üretim kimliği sayılmaz. Cut List üyeliği ve FlatPattern
sabit yüzünün gövdesi aynı kimlikle eşleştirilir. Tanım erişimi geçici
rollback gerektirirse ReleaseSelectionAccess sonrasında gövdeler yeniden
okunur.

Her gövde için kaynak konfigürasyona bağlı, FlatPattern’in bastırılmadığı
tek bir mevcut konfigürasyon aranır. İngilizce konfigürasyon adı zorunlu
değildir. Belirsiz / eksik aday atlanır. Aynı SLDDRW içinde her doğrulanmış
gövdeye ayrı pafta açılır; ORHAN-01 gibi kimlik ve doğrulanmışsa gövde
kalınlığı / malzemesi görünüşten ayrı başlık alanına yazılır.

Kayıtlı açınımın sabit yüzüne dik standart model görünüşü kullanılır.
IView.Bodies ile yalnız hedef gövde gösterilir. Kayıt sonrası gerçek
gövde kimliği, gövde sayısı, konfigürasyon ve pafta başlığı tekrar okunur;
Cut List üyeliği, kalınlık veya malzeme değişmişse çıktı başarılı sayılmaz.
Yeni kaynak konfigürasyonu oluşursa kuyruk durdurulur. Gövde kalınlığı
için bağlı SheetMetal tanımı ve o gövdenin Cut List’i kullanılır; ortak
model kalınlığıyla boşluk doldurulmaz.

BOM’da örnek sayısı ile benzersiz çizim sayısı farklıdır: 12 aynı cıvata
bir teknik resim, BOM satırında 12 adet demektir. Adet sütunu başlığı dile
göre tahmin edilmez; sütun tipi API’den okunur. Görünen adet, gerçek bileşen
sayısıyla karşılaştırılır. Özel birim / override belirsizliği PASS sayılmaz.
