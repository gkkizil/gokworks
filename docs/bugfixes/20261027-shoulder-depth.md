# Ortak omuzdaki pahlar ve kama derinliği

Kaynak: `70eac87a4ce47b5af9fa9556be3c0460d91cd3ca`, dal `main`, dizin `/workspace/gokworks`.

## Kullanıcıdaki üç hata

1. 1. kademenin sağ pahı ile 2. kademenin sol pahı, ortak omzun farklı
   çaplardaki ayrı kenarlarıdır. Eski doğrulama her işleme komşu kademede de
   tam bir boy aralığı ayırdığı için bu iki kenarı yanlışlıkla çakıştırıyordu.
2. Kama native kesmesi oluştuktan sonra `Tek sürücü ölçü bekleniyor:
   KAMA_KANALI_01` hatası alındı; kullanıcı katı derinliğinin de yanlış olduğunu
   belirtti. Kesme unsurunun tek görüntüleme ölçüsü döndüreceği varsayımı
   geçerli değildir. Kullanıcının gerçek katısındaki ölçüm burada yapılmadı.
3. Son ekran Ø40×100 + Ø60×50 için `Kademe 2/2: Dimension is reference-only:
   BASLANGIC` gösterdi. Bu, operasyonlardan önce konum ölçüsü aşamasıdır.

## Değişiklikler

- Uç işlemleri kendi kademelerindeki boy aralığıyla kontrol edilir. Ortak
  omuzun iki çap kenarı ayrı tutulur; iki pah/radyüsün toplamı omuz yüksekliği
  ile ayrıca karşılaştırılır. Aynı fiziksel kenarda tekrar, gerçek kanal
  çakışması, et kalınlığı ve kademe sınırları korunur.
- Ortak omuzda tam buluşan iki işlemin önizleme uçları tek noktadır;
  sıfır uzunlukta bir kenar üretilmez.
- Hata metinleri `chamfer` yerine `Pah · Sol/Sağ`, `Radyüs`, `Segman kanalı`,
  `Kama kanalı` kullanır. Omuz yetersizliğinde toplam boyut ve omuz yüksekliği
  ayrı ayrı yazılır.
- Yeni eskizde önceki unsurun kontur seçim modu kapatılır. `BASLANGIC`
  datumu profil dikdörtgeninden önce ölçülür; profil bu datuma bağlanır.
  Referans dönen yeni ölçü `DrivenState=swDimensionDriving` yapılır;
  değer geri okunur. Reddedilen dönüşüm, uygulanmayan değer ve aşırı tanımlı
  eskiz başarı sayılmaz. İlişkiler veya kalıcı kullanıcı ayarları silinmez.
- Kama kesme derinliği, native `IFeature.Parameter("D1")` üzerinden seçilir;
  `IExtrudeFeatureData2.GetDepth(true)` ve kör kesme türü ile doğrulanır.
  Görüntüleme ölçülerinin sayısına/sırasına bağlı değildir. Ardından
  `KESME_BOYU` denklemi bağlanır.
- Katı-model tabanı ayrıca gerçek değerlendirilen BREP yüzeylerinden okunur.
  `ISurface.PlaneParams` normal ve SI kök noktası, profilin orijin/radyal
  vektörüyle karşılaştırılır. İstenen tabana ulaşmamış bir kesme başarı
  sayılmaz. Eş düzlemde bölünmüş tabanlar kabul edilir; farklı taban
  yükseklikleri reddedilir.
- Dış düzlemdeki 1 mm hava payı **kesici hareketine** aittir. 3 mm gerçek
  kanal için yardımcı kesme hareketi 4 mm, gerçek taban `R-3mm` olur.
  Bu aritmetik, gerçek yüzey ölçümüyle ayrıca doğrulanır. Kullanıcının
  yanlış derinlik gözleminin yalnız bu farktan kaynaklandığı iddia edilmez.
- JSON v1, stage/operation kimlikleri, native yapım sırası, segman API'si,
  UI signal-slot ve kaynak CAD dosyalarını koruma sözleşmeleri değişmedi.

## Doğrulama

- Yeni 29 regresyon senaryosu eski kodda başarısızdı: 27 geometri/akış
  senaryosu, 2 anlaşılır çakışma mesajı denetimi.
  [Arşiv: Önceki sonuç](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261027-shoulder-before.xml).
- Mil paketinin yerel sonucu: **205 kayıt, 172 geçti, 33 atlandı, 0 hata**.
  Atlamalar 27 lisanslı CAD senaryosu ve 6 Windows testidir.
  [Arşiv: JUnit](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261027-shoulder-depth-tests.xml).
- Ortak kenarlar her iki çap sırası, işlem sırası, pah/radyüs kombinasyonu,
  fazla toplam boyut ve tam temas için sınandı. Kullanıcının altı işlemli
  listesinin gerçek Qt formu üzerinden eklenmesi, önizleme ve 10 satırlık
  native plana geçişi doğrulandı.
- C# 5 / warnings-as-errors, gerçek 2023 interop + .NET 4.8 referanslarıyla
  shipping host ve probe birlikte derlendi. Ruff F821/F822/F823 geçti.
- [Windows STA/API](https://github.com/gkkizil/gokworks/actions/runs/40450691945)
  başarılı. Proxy denetimleri: semantic D1, yanlış/referans/kayıp ölçü,
  farklı native kesme boyu/türü; doğru 3 mm ve yanlış 2/4 mm BREP kök
  noktaları; döndürülmüş/ötelenmiş radyal eksen; kayıp, farklı seviyeli ve
  bölünmüş eş düzlemli taban. Proxy bir CAD unsuru oluşturmuş gibi
  sahte başarı döndürmez. Yeni referans ölçünün sürücüye çevrilmesi ve
  kilitli/dönüşümü reddedilen veya değeri uygulanmayan ölçülerin reddi de sınanır.

Gerçek SOLIDWORKS/Parasolid çalıştırılmadı. Ortak omuzda iki pah, tam buluşan
pahlar ve segman+kama+dört pah listesi opt-in canlı kabulüne eklendi.
Yeni modelde doğru taban, native özellikler, bağımsız hacim, yeniden açma ve
ölçü düzenleme kabulü lisanslı Windows ortamında çalıştırılmalıdır.
11 korunan ortak dosya aynı; yedek depo ve `release` dalı kullanılmadı.
[Makine özeti](20261027-shoulder-depth-checks.json).

Son Ø40×100 + Ø60×50 örneği iki 4 mm pah, ikinci kademede segman ve
1 mm sağ radyüsle `reported_two_stages_driving` canlı kabulüne eklendi.
Bu gerçek CAD testi burada çalıştırılmadı.

[Windows BOM/Qt](https://github.com/gkkizil/gokworks/actions/runs/40450692022):
95 kayıt, 0 hata/başarısızlık, 1 lisanslı CAD atlaması. Son kaynak başarılı.
