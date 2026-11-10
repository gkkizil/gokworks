# Çerçeveli CAD çizimi okuma düzeltmesi

9 Kasım 2026. Çerçeve ile kesim konturu ayrı değerlendirilir. Normal DXF
okuyucusunun açık/çakışan kontur denetimleri ve adet onayı korunur.

## Düzeltilen sınır durumları

- Dört ayrı LINE ile gelen çerçevede yaklaşık 2,9e-11 mm köşe farkı,
  tam eşit koordinat isteyen polygonize adımında çerçeveyi açık bırakıyordu.
  Yalnız çerçeve tespit kopyasının uçları mevcut birleştirme toleransı içinde
  eşlenir. Kesim kaynakları değiştirilmez; çizgi kesişimleri düğümlenerek
  olmayan çerçeve oluşturulmaz. Eşik karşılaştırması birim dönüşümünün çok
  küçük kayan nokta farklarını tolere eder.
- Hafif paralelkenar biçimindeki çizim çerçevesi kusursuz dikdörtgen
  olmadığı için tanınmıyordu. Her köşesi 89–91° olan kapalı, dışbükey
  dörtgen de metaveri çerçevesi sayılır. Gerçek sınır kullanılır; kesim
  parçası dikleştirilmez. Daha büyük sapma, içbükey/çok kenarlı sınır ve
  toleransı aşan açık uç otomatik kabul edilmez.
- Standart görünüş başlığının alt çizgisi açık kesim geometrisine giriyordu.
  Yalnız sabit VIEW/DETAIL/SCALE yazısı, LETTER/SCALE özniteliği, açıklama
  varlıkları ve en fazla tek LINE içeren başlık bloklarının alt çizgisi
  dışlanır. Blok adına, katman adına veya renge bağlı değildir. Genel metinli
  blok, farklı etiket, birden çok çizgi veya kapalı kesim varlığı bu kuralla
  kaybolmaz; normal katman/kapalı kontur denetimine gider.

## Doğrulama

Yüklenen gerçek DXF kod deposuna eklenmeden yerel olarak doğrulandı:
14 parça türü, toplam 56 adet, 5 mm. Dosya adındaki 2 adet, çizim adetlerini
çarpmadı. İçe aktarma önce parça/adet listesi onayına geldi. Gerçek Qt
penceresinde açık/koyu temada 14 satır ve 56 adet görüldü; onaysız aktarım
olmadı. Önceki 3 adetlik bağımsız parça korundu; 14 kontur önizlemesi çizildi.
Kaynak dosyanın SHA256 değeri değişmedi.

Sparrow + GOKWORKS ile 56 parçanın tamamı 1250 × 2500 × 5 mm stokta
3 levhaya yerleşti. Hızlı profil yaklaşık 15 saniyelik sınırda en iyi
geçerli tam planı korudu; optimum levha/fire iddiası yoktur. Taşınabilir
proje yeniden açılıp bağımsız geometri kontrolünden geçti. Dışa aktarılan
kesim varlıkları, her özgün varlığın parça adediyle çarpımına tam eşleşti:
136 CIRCLE, 15 ARC, 407 LINE, 2 LWPOLYLINE, 1 POLYLINE. Çerçeve,
sayfa sınırı, başlık alt çizgisi ve açıklama yazısı kesime karışmadı.

`test_drawing_frame_compat.py` içinde müşteri çizimini kopyalamayan 27 küçük
sentetik durum vardır: ayrı uçlar, mm/cm/inch, kayık ve döndürülmüş çerçeveler,
kapalı kontur/delik koruma, görünüş alt çizgileri, iç içe ölçekli/döndürülmüş
bloklar, yanlış blok elemesini reddetme, sayfa çerçevesi ve adet onayı.
Çerçeve/aktarım GUI regresyonu ve geniş Nesting/Akıllı Parça Bölme kümesi
ayrıca çalıştırıldı. Örtüşen test kümeleri toplanmaz; son sayı ve Windows
CI durumu PR açıklamasında tutulur. Yerel kontroller Windows EXE kanıtı değildir.
