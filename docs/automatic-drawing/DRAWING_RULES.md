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

## Ölçüler

Öncelik resme işaretli model ölçüleridir; Hole Wizard profile / location
ölçüleri varsa aynı native import mekanizmasıyla alınır. Montajda bütün
parça ölçülerini doldurmak yerine assembly-only kaynağı kullanılır.

SolidWorks native tekrar eleme seçeneği etkinleştirilir. İlave tekrar
denetiminde model, konfigürasyon, gerçek ölçü kimliği ve türü kullanılır;
iki ayrı deliğin aynı çapta olması tekrar sebebi değildir. Modelden
aktarılmış ölçünün değeri veya toleransı yeniden yazılmaz.

AutoDimension isteğe bağlıdır ve ana görünüşle sınırlıdır. Bunlar native
referans ölçüleridir; datum / tolerans / işlevsel tasarım ölçüsü olarak
sunulmaz. Her döndürülmüş metin için gerçek display-data geometrisi okunur.
Genişlik API’den alınamıyorsa tahmin açıkça WARNING üretir.

Native AlignDimensions sonrası sınırlı, deterministik dış şerit araması
metni boş alana taşımayı dener. Son konum tekrar native API’den okunur.
Kopuk ölçü ve pafta dışına taşma FAIL, çözülemeyen metin çakışması WARNING
üretir. Lider / ölçü çizgilerinin bütün kesişimleri henüz denetlenmez.

## İmalat ayrıntıları

Merkez işaretleri native IView API’siyle oluşturulur. Geometriden diş
adı, H7, K faktörü, genel tolerans veya GD&T uydurulmaz.

Delik / iç boşluk / küçük pah ve radyüs bilgileri kesit / detay kontrol
önerisi doğurabilir. Kesit çizgisi ve kesit / detay görünüşünün otomatik
oluşturulması bu sürümün tamamlanmış özelliği değildir.

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
