# Sparrow ve parça önizlemeleri

9 Kasım 2026. Nesting → sağ **Özellikler → Yerleşim → Motor → Sparrow**.
Eski projelerde varsayılan GOKWORKS NFP korunur. Motor seçimi kayıtla taşınır;
motor değişince eski sonuç geçersizleşir. Eski NFP proje/sonuç hash sözleşmesi
korunur. Akıllı Parça Bölme kendi mevcut NFP optimizasyonunu kullanır; Nesting'e
aktarılan segmentler burada Sparrow ile yeniden yerleştirilebilir.

Sparrow, deponun önerdiği resmî `spyrrow==0.9.0` bağlantısıyla çalışır.
Linux ve CPython 3.13 Windows x64 hazır wheel'leri kullanılır; son kullanıcıya
Rust, Cargo, Node veya ek servis kurulmaz. Bu wheel'in özgün SBOM'u Sparrow
**0.1.0 / 881cdcbdf492ca42ba5413954ea6e41889a3becd**, jagua-rs **0.7.0** bildirir.
Güncel Sparrow 0.3.0 bağlandığı iddia edilmez. Pin, derleyicisiz Windows dağıtımı
ve tekrar üretilebilir bağımlılık için seçilmiştir.

## Fiziksel levhalara uyarlama

Sparrow sabit yükseklikte sınırsız şerit enini azaltır. Adaptör, uygun malzeme/
kalınlıktaki kalan adetlerle şeridi çözer; yalnız bütünüyle fiziksel levhaya
sığan parçaları alır. Sınırı geçen parça kırpılmaz; sonraki stok levhasında
tekrar denenir. Levha seçenekleri ve stok korunur; bu uyarlama global çoklu
levha optimumu veya mevcut NFP'den her işte daha az fire garantisi vermez.

İzinli açılar ve hadde kilidi native girdiye taşınır. Yerel orijine ve ortak
ölçeğe dönüşüm, milimetreye geri çevrilir; f32 için muhafazakâr hata payı
kullanılır. Son yerleşimler özgün çift hassasiyetli konturlarla mevcut bağımsız
`validate_result` denetimini geçmeden kullanıcıya sunulmaz. Kimlik/adet,
sonlu koordinatlar, malzeme, kalınlık, açılar, stok, kenar payı, kerf ve parça
aralıkları denetlenir. Hatalı native sonuçta motor sessizce değiştirilmez.

Sparrow yalnız tek bağlı dış konturu kabul eder. Delikler girdide çarpışma
alanı olarak dolu kabul edilir; özgün delikler, alan/ağırlık ve DXF iç konturları
korunur. Delik içine başka parça yerleştirmek için GOKWORKS NFP seçilir.
Ayrık MultiPolygon grupları açık mesajla reddedilir; dışbükey kılıfa çevrilmez.

Native motor Qt/COM yüklemeyen özel alt süreçte çalışır. İptal ve süre sınırında
bu süreç sonlandırılır ve toplanır; son uygun ara sonuç varsa yeniden doğrulanır.
Proje genelinde otomatik süreler Hızlı 5, Dengeli 15, Yüksek 45 saniyedir;
eski sayısal `seconds` sınırı da okunur. Başlatma, geometri hazırlığı ve bağımsız
son kontrol için küçük ek süre olabilir. Süre/stok nedeniyle yerleşmeyen adetler
sonuçta açıkça kalır; mevcut tam sonuç gerektiren aktarım denetimleri korunur.

## Küçük 2D önizlemeler

Sol parça ağacında adın yanında 36 × 28 mantıksal piksel kontur çizilir.
Oran ve delikler korunur; renkler ana çizimle eşleşir. Açık/koyu tema ve yüksek
DPI desteklenir. Yalnız istenen satırlar çizilir; QIcon önbelleği 256 ile sınırlıdır.
Adet düzenleme ve filtreleme CAD geometrisini değiştirmez.

## Dağıtım ve lisanslar

`requirements.txt` pinlidir; PyInstaller native uzantıyı ve paket metadata'sını
toplar. Windows oluşturma betiği paketlenmiş EXE'nin özel worker girişini gerçek
iki parça yerleşimiyle kontrol eder. Bu kontrol ancak gerçek Windows derlemesi
çalıştırıldığında kanıttır; Linux testi EXE testi diye sunulmaz.

Sparrow/spyrrow MIT, jagua-rs MPL-2.0 bildirimleri, iki wheel'in özgün SBOM'ları,
Rust bağımlılık bildirimleri ve jagua-rs'nin değiştirilmemiş kaynak arşivi
`packaging/licenses/nesting/sparrow/` altındadır. Lisanslar ekranından dışa aktarılır.

## Yerel doğrulama kaydı

- Nesting, Akıllı Parça Bölme ve paketleme girişleri: **427 vaka, 0 hata,
  1 atlanan**; sınırlı büyüklükte ayrı Linux/Qt süreçleri. Atlanan vaka yerel
  ODA ve kullanıcı DWG dosyası gerektiren mevcut canlı dönüşüm testidir.
- Son arayüz düzenlemelerinden sonra önizleme/motor testleri tekrar geçti
  (**5 vaka**); özgün 427 kümesinin içindedir, sayılar toplanmaz.
- Gerçek Sparrow: 6 farklı kontur tipi / 21 adet, 1 levha, yaklaşık 1.2–1.3 s.
  Delikli, içbükey ve negatif orijinli konturlar; stok/çoklu levha, hadde ve
  90°/270° sınırları, büyük parça, yerel süreç iptali/süre sonu, hatalı native
  kimlik/adet/açı/NaN reddi, kayıt ve DXF yeniden kullanımı test edildi.
- 9922966 sürümünde gerçekten kaydedilmiş NFP proje + iki yerleşim, yeni
  sürümde aynı hash ile açılıp doğrulandı.
- 1366/1024/820 genişlikleri × açık/koyu tema: kontur ikonları görünür,
  listede yatay kaydırma yok. [Koyu görünüm](examples/sparrow/koyu-1366.png),
  [açık görünüm](examples/sparrow/acik-1024.png),
  [ölçüm kaydı](examples/sparrow/gorunum-dogrulama.json).
- Uygulamanın 21 modül / iki tema / çözünürlük matrisi kaynak açılış
  özdenetimi geçti. Yeni ve değişen Python dosyalarında Ruff hata/undefined/
  kullanılmayan import kontrolü ve Git whitespace denetimi geçti.
- Yeni Sparrow sürümünün Windows CI sonucu ve otomatik birleşmesi PR'da
  izlenir. Yukarıdaki kaynak/Linux kontrolleri yeni Windows EXE kanıtı değildir.
  Önceki akıllı bölme sürümünün tamamlanmış Windows kanıtı [AUDIT](../smart_splitting/AUDIT.md)
  içindedir; yeni başlığa aktarılmaz.
