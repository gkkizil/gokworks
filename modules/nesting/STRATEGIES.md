# Nesting 1.8 · kurucu adaylar ve küçük parça takası

Referans: kullanıcının sağladığı **Nestra-Nesting-Algoritmalari.md**, Nestra
0.2.56 hakkındaki analiz. Belge kendi gözlemlerini ve motor günlüklerinden
çıkarımlarını ayırır. Bu çalışma özel Nestra kaynak kodunu doğrulamış veya
taşımış değildir; standart MaxRects ve yerel yer değiştirme fikirlerinin
GOKWORKS veri sözleşmesiyle bağımsız Python uygulamasıdır.

## Referansın mevcut motora eşlenmesi

| Belgede anlatılan fikir | GOKWORKS karşılığı |
| --- | --- |
| Sparrow keşif, ayırma, sıkıştırma | Mevcut kilitli Sparrow 0.3.0 / spyrrow 0.10.0 / jagua-rs 1.0.0 korunur. |
| İki eksen, en dar dikdörtgen yönleri | Mevcut native iki eksen araması ve serbest dönüşte kontur/minimum dikdörtgen açı adayları korunur. |
| MaxRects hızlı rakip | Yeni `constructive.py`: en kısa kalan kenar, en az boş alan, alt köşe ve değişik parça/stok sıraları. |
| Birçok kurucu taslak | Kaliteye göre 4/6/8 deterministik aday; sabit proje tohumu kullanılır. Süreye bağlı kısmi aday daha iyi doğrulanmış planı silemez. |
| Küçükleri çıkar, büyükleri koy, küçükleri geri al | `stock_refinement.py`: bir veya birkaç küçük engelleyiciyi taşıyan sınırlı takas. Bütün örnekler yerleştirilmeden kabul edilmez. |
| Geri doldurma, plaka birleştirme, küçük stoğa geçme | Mevcut stok iyileştirmesi devam eder; takas, tam yeniden dizmeden önce başka bir arama başlangıcı sağlar. |
| Tekrarlı parça/blok | Dönüş ve dikdörtgen ölçüleri tür başına önbelleğe alınır. Yeni rijit blok/kafes oluşturulmaz; adet ve tekil örnekler korunur. |
| Deliklere yerleştirme | Kesin kontur/NFP katmanında sürer. MaxRects delik alanını muhafazakâr ayırır; daha iyi delik içi başlangıcın üstüne yazamaz. |
| Süre sonu ve kazançsız turda bitirme | Mevcut ortak `SearchBudget` ve plato kuralı korunur; MaxRects ayrıca kalan başlangıç zamanının en fazla dörtte birini kullanır. |
| Büyük parçalar ve gereksiz turun elenmesi | Kullanılabilir malzeme alanı ve yarım kullanılabilir alandan büyük parça sayısı güvenli alt sınır verir; olanaksız plaka boşaltma denemeleri başlamadan elenir. |

## Fiziksel sözleşme

- Kazanan önce yerleşmeyen adet, sonra plaka sayısı, toplam brüt stok alanı ve
  iki eksendeki kullanılan şerit alanıyla seçilir. Farklı fiziksel stokların
  alanını yalnız son şerit boyu uğruna büyütmeyiz.
- Her dikdörtgen, `max(gap, kerf)/2 + geometry_error` kadar genişletilir.
  Plaka sınırında yarım aralık geri verilir; gerçek kenar payı, yarım kerf ve
  parçanın kendi geometri hatası kalır. Gerçek parça geometrisi değiştirilmez.
- İzinli ayrık dönüşlere yeni açı eklenmez. Hadde kilidinde yalnız izinli
  0/180 kullanılır; serbest moddaki kontur hizalama açısı gerçek yerleşim
  açısı olarak kaydedilir. Aynalama yoktur.
- `validate_result` özgün malzeme geometrisini, Euclidean aralıkları, kenar
  payını, malzeme/kalınlığı, sınırlı stoğu ve tekil örnek/adetleri bağımsız sınar.
- Takas taslakları yerleşim listelerini kopyalar. Global iptal/süre hataları
  yakalanıp gizlenmez; yerel süre bitince tam yeniden dizme yolu devam edebilir.
- Net alan alt sınırı kenar payı/yarım kerf sonrası kullanılabilir alanı alır.
  Bu alanın yarısından büyük her parça ayrı plaka gerektirir. Hesap gerçek net
  malzemeyi kullanır: çerçevelerin deliklerini dolu varsaymaz. Farklı stok
  alanları ve belirsiz yakın kalınlık grupları için genel optimalite kısa yolu
  açılmaz. Çok plakalı onarımda aynı alan/count koşulu ayrı ayrı kontrol edilir.

Belgedeki bozuk konturu dışbükey zarf/kutuya değiştirme, payı geçici azaltma,
ortak kesimde aralığı sıfırlama ve sabit üretici sürelerini birebir alma yolları
eklenmedi. Özgün kontur ve kullanıcının kesim payları esas kalır. Kesim sırası,
lead-in, mikro bağlantı ve fire çizgisi ayrı imalat işlemleridir; bu değişiklik
yerleşim motoruyla sınırlıdır. Arayüz/ayar şeması veya bağımlılık değişmez.

## Yeniden üretilebilir kalite örnekleri

| Kontrollü örnek | Önceki hızlı yol | Yeni aday |
| --- | --- | --- |
| 10×10 stok, (5×2, 5×6, 4×5, 6×4, 7×7, 5×5), sabit açı, sıfır pay | Tek kurucu tur 3 plaka | MaxRects 2 plaka; net alan 158 olduğu için alan alt sınırı da 2. |
| 10×10 stok, (6×4, 3×6, 2×5, 6×2, 4×2), iki plakalı geçerli başlangıç | NFP 1.7 stok onarımı 2 plaka | Küçük engelleyici takası 1 plaka; büyük iki parçanın konumu korunur. |

Bunlar sentetik karşılaştırmalardır; her müşteri işinde aynı kazanım veya
matematiksel genel optimum iddiası değildir. Regresyonlar ayrıca gerçek
boşluk/kerf/geometri hata payı, karma stoklar, delikler, izinli dönüşler,
iptal/süre, başarısız yeniden yerleştirme ve girdi değişmezliğini kapsar.
