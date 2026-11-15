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

Sac açınımı yalnız tek sac gövdesi ve doğru üst konfigürasyona bağlı mevcut
tek açınım konfigürasyonuyla denenir. Yeni kaynak konfigürasyonu
oluşursa veya native FlatPattern kimliği eşleşmezse işlem başarılı sayılmaz.

BOM’da örnek sayısı ile benzersiz çizim sayısı farklıdır: 12 aynı cıvata
bir teknik resim, BOM satırında 12 adet demektir. Adet sütunu başlığı dile
göre tahmin edilmez; sütun tipi API’den okunur. Görünen adet, gerçek bileşen
sayısıyla karşılaştırılır. Özel birim / override belirsizliği PASS sayılmaz.
