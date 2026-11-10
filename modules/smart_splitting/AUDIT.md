# Akıllı Parça Bölme — A'dan Z'ye denetim

9 Kasım 2026. Bu belge `DELIVERY.md` içindeki ilk teslim kaydını tamamlar;
ilk teslimdeki sayılar ve ölçümler tarihsel kanıttır. Güncel başlığın Windows
ve birleşme durumu [PR #48](https://github.com/gkkizil/gokworks/pull/48) üzerinden izlenir.

## Bulunan ve düzeltilen sorunlar

1. **Alan kontrolünden kaçan sayısal yarık:** bitişik sektörlerin uçları ayrı
   trigonometrik hesaplanıyordu. Alan/simetrik fark çok küçük olsa da birleşik
   konturda merkeze uzanan, sayısal genişlikte bir yarık kalabiliyordu. Sektörler
   artık aynı sınır koordinatlarını paylaşır. Bağlantı, delik sayısı ve sınır
   Hausdorff uzaklığı alan kontrollerinden bağımsız doğrulanır. Kontrol eşiği
   `max(1e-7 mm, en büyük ölçü × 1e-10)`; nominal geometri sessizce onarılmaz.
2. **Kaynak boşluğunda kopuk kırıntılar:** kırpılmış ve uçları kısaltılmış
   birleştirme kenarını offsetlemek, kaynak dış sınırında ince adalar
   bırakabiliyordu. Boşluk/pay tam radyal kesim doğruları üzerinde uygulanır;
   imalat geometrisi kaynak malzemeye kırpılır, boş/kopuk sonuç reddedilir.
3. **Eğri toleransı/birim değişikliği eski geometriyi kullanıyordu:** artık
   bölme kapatılır ve Yeniden Oku gerekir. Gerçek yeniden okuma, yeni örnekleme
   ve birim ölçeğiyle doğrulandı. Nesting kopyasında bu alanlar pasiftir.
4. **Yeniden okunan kaynak ikinci kez ekleniyordu:** kaynak iş kimliği artık
   tessellasyon/byte revizyonundan bağımsızdır. Dosya yolu + parça kodu,
   dosyasız Nesting parçasında kalıcı Part ID kullanılır. Aynı kaynak yeniden
   okununca yalnız önceki segmentleri yenilenir. Farklı kaynak/parçalar korunur;
   önceki kimlikli projeler için kaynak/segment notlarıyla geçiş yolu vardır.
5. **Geçersiz saf API girdileri:** yanlış tür, sonlu olmayan değer, geçersiz
   bölge ve taşan merkez/levha alanı artık açık ValueError ile reddedilir.
6. **Windows UI testinin koordinat varsayımı:** QLayout.geometry() native
   Windows'ta geçici olarak boş olabiliyordu. Kontrol gerçek düğmenin sayfa
   içindeki üst/alt köşelerine taşındı; görünürlük/kırpılmama şartı korunur.
7. **Özel malzemeyi sessizce varsayılana çevirme:** Nesting'den özel malzeme
   kopyalanınca eski katalog seçimi kalabiliyordu. Kaynak malzeme artık adıyla
   gösterilir ve desteklenen katalog malzemesi açıkça seçilmeden hesap kapatılır.
   Özel malzemenin farklı bir yoğunlukla hesaplanması önlenir; mevcut Nesting
   kaynağının malzeme kaydı değiştirilmez.

## Denetim kapsamı

- Daire, halka, elips ve genel dışbükey kontur × 11 farklı segment sayısı
  (2–64) × 5 başlangıç açısı = **220 üretilmiş geometri durumu**. Bunlar dört
  parametrik testin içindeki durum sayısıdır; ayrı pytest test sayısı değildir.
- Her durumda bağımsız birleşim sınırı/topoloji, alan, simetrik fark, komşuluk
  simetrisi ve birleşim uzunluğu denetlenir. 2, 7 ve 64 segment için ayrıca
  adaptör ve ayrı/birleşik DXF yeniden okuma çalıştırılır.
- Kaynak boşluğu, işleme payı, delik/slot yaklaşması, yasaklı bölgeler, et/
  genişlik, birimler, bozuk/açık geometri, dönüşümler ve geçersiz girdiler.
- Gerçek NFP adayları; kısmi/bozuk aday reddi, iptal, bütçe ve aynı ayarlarda
  başlangıç/alternatif karşılaştırması. GEOS hatalı adaylar başarı sayılmaz.
- Gerçek Qt iş parçacıklarıyla dosya seç/iptal/yeniden oku, çok parçalı DXF
  seçimi, iki yönlü Nesting aktarımı, tekrarlama, 10000 sınırında işlemsellik,
  kaynak/dosya revizyonu, kaydet/aç, zoom, orijinal görünüm, sıfırla ve çıktı.
- Unicode dosya/klasör adları; ayrı/birleşik DXF ve atomik başarısız/iptal
  çıktı; kaynak dosyası ve önceki Nesting parçalarının korunması.
- Kompakt ekranlar ve temalar; gerçek düğme sınırları ve Qt çalışma akışı.
- Kaynak/branch coverage ölçümü, Ruff hata/undefined/unused kontrolü ve Git diff.

## Windows ve doğrulama kaydı

Önceki `d526467` Windows koşusunda rapor: **4305 vaka, 1 başarısızlık, 54 atlanan**.
Tek başarısızlık yukarıda açıklanan arayüz testinin QLayout.geometry() kontrolüdür;
başarısızlık atlanmadı ve birleşme koruması aşılmadı.

Düzeltilmiş **9922966**, sabit **934fca0** main ile Windows'ta yeniden test edildi:
**4340 vaka, 0 başarısızlık/hata, 54 atlanan**; uygulama açılış kontrolü de geçti.
[Windows kanıtı, 42599520773](https://github.com/gkkizil/gokworks/actions/runs/42599520773).
PR #48, 9 Kasım 2026 10:54 UTC'de **c743c8c** ile otomatik birleşti.
Aynı birleşim ağacının Linux'taki tam süreçli koşusunda 4340 node kimliği,
XML'de alt testlerle birlikte **5163 kayıt, 0 hata/başarısızlık, 71 atlanan** görüldü.
Bu platformların sayıları veya örtüşen test kümeleri toplanmaz.

Son yerel/geçici birleşim test sayıları, coverage ve yeni Windows durumu PR
açıklamasında kaydedilir; örtüşen test kümeleri toplanmaz. Kapsama oranı test
kalitesi veya fiziksel üretim garantisi değildir. Gerçek kullanıcı CAD dosyası,
tezgâh, kaynak mukavemeti ve canlı SolidWorks kabulü bu denetime dahil değildir.
