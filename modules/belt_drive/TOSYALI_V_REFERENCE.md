# Tosyalı dar V kasnak ve kanal hesabı

12 Kasım 2026. Otomatik Tasarım → **Tosyalı dar V · Optibelt SK referansı · kanal hesabı**.
SPZ, SPA, SPB ve SPC desteklenir. STB bu katalogda bir profil değildir.
Servis faktörü açıkça girilir; boş değer 1 kabul edilmez.

## Kaynaklar ve kapsam

- Kullanıcının Tosyalı Teknik Bilgi Kataloğu: SHA-256
  `8399b6b5a123573e99e8a982afd6c7c1504e160edc845d6fc6218812461d689c`.
  PDF 48–74 / basılı 46–72: 708 kasnak (181 SPZ, 189 SPA, 198 SPB, 140 SPC).
  P datum çapı, O dış çapı, kanal sayısı ve kod alınır. Toplam gövde genişliği,
  burç/mil deliği, F/L konumu tahmin edilmez.
  `T SPB 565-2` kodunda 565, P hücresinde 560 yazdığı için satır karantinadadır.
  Gerçek kanal sayıları: 1, 2, 3, 4, 5, 6, 8, 10; her profil/çapta hepsi yoktur.
- Tosyalı PDF 47 / basılı 45: çevresel hız sınırı **35 m/s**.
  PDF 78 / basılı 76 ile kayış üreticisinin tavsiyesi aynı minimum datumları
  verir: SPZ 63, SPA 90, SPB 140, SPC 224 mm.
- Tosyalı basılı 44'teki güç/devir grafiği yaklaşık sayısallaştırılmış ön
  tavsiyedir. Grafik tek kayış gücü veya kanal sayısı vermez. Sınırlarından
  güvenlik kararı üretilmez; bütün kesitler ayrıca güç hesabına girer ve grafik
  yalnız eşit sıralama koşullarında yardımcı ölçüttür. Grafikte motor gücü
  yazmasına karşılık ön tavsiyede muhafazakâr tasarım gücü kullanılır.
- [Optibelt Technical Manual V-Belt Drives](https://www.mmintercom.com/upload/publish/347/optibelt-v-belt-drives_68ad71e7ae502.pdf),
  Optibelt GmbH tarafından hazırlanmış 2018 kılavuzu, distribütör kopyası
  (basılı 184'te `Print: 1018`).
  SHA-256 `0b9f72c3bbf216602fa88f3feab5268d0a43f03fa1f2a2edbc581a1c807f1ad0`.
  Basılı 27: listelenen SK boyları; 8: minimum çap/hız/bükülme;
  74 tablo 22: sarılma c₁; 76 tablo 24: boy c₃;
  98–101 tablolar 41–44: SK güç ve oran ilavesi; 87: hesap örneği.
  Bu veriler **yalnız Optibelt SK** serisinin tarihli referansıdır. Tosyalı'nın
  güç verisi veya tüm SPB marka/serilerine geçerli genel bir kapasite değildir.
  Güncel stok/ömür veya üreticinin montaj onayı olarak sunulmaz.
- Güncel standart kapsamları ISO'nun yayın sayfalarından kontrol edildi:
  [ISO 4183:2026](https://www.iso.org/standard/88705.html) kasnak datum sistemi;
  [ISO 4184:2025](https://www.iso.org/standard/88704.html) kayış datum boyları.
  Tam standart satın alınmadı; güncel tolerans/imalat uygunluğu onayı verilmez.
  Eski katalog listeleri güncel standardın bütün boyları olarak gösterilmez.

## Hesap ve seçim

`Ptasarım = P × servis faktörü`

`Pkayış = (Ptemel + ΔPoran) × c₁ × c₃`

`gerekli adet = ceil(Ptasarım / Pkayış)`

Güç tablosu küçük kasnağın datum çapı ve **kendi devri** ile sorgulanır;
devir yükselten aktarımda bu, sürülen kasnaktır. Tablo içinde iki doğrultuda
doğrusal enterpolasyon yapılır. Boş hücre, kapsam dışı çap/devir/boy/sarılma
kapasiteye çevrilmez. Oran ilaveleri kılavuzun basamaklı sütunlarını kullanır;
basılı iki ondalık oran aralıkları arasındaki boşluklarda düşük ilave korunur.
Eş çapta oran ilavesi sıfırdır. SK 42 m/s ve 100 s⁻¹ sınırlarının yanında
Tosyalı'nın daha düşük 35 m/s kasnak sınırı ve kullanıcının sınırları uygulanır.

Her çap çifti için iki kasnakta ortak en küçük yeterli kanal sayısı bulunur.
7 kayış gerekirse 7 kanallı kod uydurulmaz: ortak 8 kanallı iki ürün varsa
**8 eşlenmiş kayış** seçilir. Adet sınırı 7 ise bu takım elenir.

Tercihli boyda gerçek SK listesinde hedef C'nin iki komşusu incelenir,
seçilen Ld için C tam teğet geometrisiyle yeniden çözülür. C ve sarılma
sınırları tekrar kontrol edilir. Bütün kayış boylarını kapsayan küresel
optimizasyon iddiası yoktur. Teorik boy seçeneğinde stok kayış seçilmediği
belirtilir. Kasnak dış gövdeleri için `C > (O₁+O₂)/2` aranır.

Gövde genişliği ve kurulum/germe payı filtreleri, bu veri kümesinde bilgi
olmadığı için sessizce geçilmez; API açıkça reddeder, arayüz göstermez.
Kayış takımı eşleme, mil deliği/burç, balans, germe, yatak yükü, kayma ve
güncel ürün uygunluğu ayrıca incelenmelidir. Geometrik motor değişmedi.

## Veri çıkarma denetimi

PDF'ler ve sayfa görselleri depoya eklenmedi; yalnız sayısal alt kümeler ve
kaynak kimlikleri tutulur. PDF okuyucu yeni çalışma zamanı bağımlılığı değildir.
Tablo 24'te basılı `0 89` ve `0 96`, görselden kontrol edilerek 0.89 ve 0.96
olarak kaydedildi. SPC 2850 dev/dak satırı özet satırında daha çok hücre
içerir; ayrıntılı satırdaki boş hücreler korunarak ortak güvenli alt küme alındı.
Diğer tekrarlanan satırlar karşılaştırılarak çelişki olmadığı doğrulandı.

Kılavuz basılı 87'deki 132 kW, 1485 dev/dak, 280/500 mm,
SPB Ld 4000, servis 1.3 örneği **8 kayış** sonucuyla doğrulandı.
Kılavuz C, c₁ ve PN değerlerini yuvarlar; motor tam geometri ve ara tablo
düğümlerini kullanır: C≈1383.012614 mm, Ptemel=20.636 kW,
ΔP=1.228 kW, c₁≈0.998185, c₃=1.02, Pkayış≈22.260812 kW.
Farklı kesitler, hızlı sürülen kasnak, boş tablo hücreleri, 7→8 kanal,
sınırlar, iptal, proje ve arayüz akışı regresyon testleriyle kapsanır.

Boy katsayısında seçilen katalog Ld'si kullanılır. Geometrik çözümün çok küçük
boy kalıntısı, tablonun ilk/son geçerli boyunu kapsam dışına itemez;
gerçek kapsam dışı boylar yine reddedilir. Sekiz uç nokta regresyonla kapsanır.

Yerel doğrulama: kayış modülünün 312 testi geçti (277 mevcut + 35 yeni;
sekizi boy tablosunun uç noktalarını kontrol eder).
Paket verisi/yapı ve arayüz kontrolleri ayrıca çalıştırıldı. Ruff F ve
`git diff --check` temiz. Windows entegrasyonu PR üzerindeki sabit head/main
doğrulamasıyla takip edilir; yerel Qt kontrolü canlı SolidWorks testi değildir.
