# ISO geçme toleransları

Yan menüde **ISO GEÇMELERİ** ekranı bulunur. Nominal çapı yazın, delik ve mil sınıfını seçin veya soldaki delik/mil esaslı eşleşme örneklerinden birine tıklayın. Virgül ve nokta kabul edilir. Hesap SolidWorks bağlantısı olmadan çalışır; CAD parametrelerini değiştirmez.

Delik/mil alt ve üst ölçüleri, EI/ES ve ei/es sapmaları, boşluk veya sıkılık sınırları gösterilir. **mm / µm** seçimi sapma ve geçme sonuçlarının birimini değiştirir; nominal çap ve parça ölçüleri mm olarak kalır. **CSV kaydet** UTF-8 BOM, noktalı virgül ve ondalık virgülle Excel'e uygun rapor oluşturur. **Sonucu kopyala** bütün sayısal sonuçları panoya verir. Tema ve seçimler yeniden açılışta korunur.

**Montaj kesiti** şematiktir; sapmalar görünürlük için büyütülür. Üç örnek ölçü arasında büyütme oranı sabittir. **Tolerans bölgeleri** gerçek sapma değerlerine göre doğrusal eksen kullanır. *Orta değer* yalnızca limitlerin ortasıdır; üretimin olasılık dağılımını temsil etmez. Arama ve Ctrl+F yaygın eşleşmeleri bulur. Küçük pencerede iki liste kaydırılabilir.

Kesitte taralı gövde **deliği**, yeşil parça **mili** gösterir. **D** oku delik çapını, **d** oku mil çapını tam olarak boyutlandırır. Yeşil boşluk alanları `D > d`, kırmızı çakışma alanları `d > D` durumudur. Kırmızı alan, deformasyon öncesi boyutsal çakışmadır; montaj sonrası elastik şekli göstermez. `D = d` olduğunda **Sınırda temas** yazılır; boşluk veya çakışma alanı çizilmez.

**Çapsal boşluk** `D − d`, **çapsal sıkılık** `d − D` olarak hesaplanır. **g** oku üstte tek tarafı gösterir: eş merkezli kesitte boşluğun veya çakışmanın radyal büyüklüğü `|D − d| / 2`'dir. Bu, montaj kuvveti hesabı değildir. Çapsal ve tek taraflı değerler ayrı yazılır; raporlanan sayılar çizim büyütmesinden etkilenmez. Örneğin Ø50 H8/f7 orta değerinde D=50,019500 mm ve d=49,962500 mm: çapsal boşluk **0,057000 mm**, tek tarafta **0,028500 mm**.

**Seçilen örnek** ile **tolerans çiftinin türü** ayrı gösterilir. H7/k6 bir ara geçmedir: en az boşluk seçiminde sıkılık, en çok boşluk seçiminde boşluk gösterilebilir. Bu, çiftin ara geçme sınıfını değiştirmez. En az boşluk `Dmin/dmax`, en çok boşluk `Dmax/dmin`, orta değer ise her iki limit bandının ortasıdır. Kesit ve tolerans bölgeleri bağımsız yükseklik kullanır; küçük pencerede sağ alan kaydırılabilir.


## Delik esaslı / mil esaslı örnekler

Hazır liste artık **Tümü / Delik esaslı / Mil esaslı** filtresiyle 23 örnek sunar. Delik esasında H sınıfının alt sapması EI=0; mil esasında h sınıfının üst sapması es=0'dır. H7/js6, H7/k6, H7/m6 ve H7/n6 aynı deliği farklı mil bölgeleriyle eşleştirir; H7 tek başına bir geçme türü değildir. Örnekler bütün ISO kod sisteminin tamamını içermez; 11 delik × 18 mil menülerinden 198 çift seçilebilir.

H6/k6 ve H8/k6 farklı delik toleranslı örneklerdir. Ø50'de mil esaslı JS7/h6: −0,0125…+0,0285 mm; K7/h6: −0,018…+0,023 mm; N7/h6: −0,033…+0,008 mm ara geçme verir. P7/h6: −0,042…−0,001 mm sıkı geçmedir. Bu gruplar metin etiketinden değil, seçilen çapın EI/ES/ei/es değerlerinden hesaplanır. P7/h6 Ø3'te −0,016…0 mm sıkılık/sınırda temastır; pozitif boşluk bulunmadığı için ara geçme değildir.

[Mil esaslı gerçek ekran](reports/kr-workspace-fix/screenshots/iso-fits-shaft-basis-dark.png) · [Son test/Word raporu](reports/kr-workspace-fix/README.md).

## Manuel tolerans kontrolü

Sol panelde **Manuel kontrol** seçin. Nominal çap delik ve mil için ortaktır. Delik/mil **üst ve alt sapmaları mm olarak** ayrı girilir; sonuç birimi mm/µm seçilebilir. Sapmalar canlı hesaplanır; ters limit, eksik sayı, geçersiz çap veya fiziksel olarak sıfır/negatif ölçü varsa eski sonuç temizlenir ve rapor/kopyalama kapanır. Girişler, ISO seçimi ve tema yeniden açılışta korunur.

| Ø50 mm örneği | Delik alt / üst (mm) | Mil alt / üst (mm) | Sonuç |
| --- | --- | --- | --- |
| Delik 50 +0,02; mil 50 −0,02 | 0 / +0,02 | −0,02 / 0 | Boşluk 0–0,04 mm; boşluklu, kayar geçme adayı; sınırda temas |
| İki parça da 50 ±0,02 | −0,02 / +0,02 | −0,02 / +0,02 | −0,04…+0,04 mm; ara geçme |
| Gerçek ölçü 50,02 delik ve 49,98 mil | +0,02 / +0,02 | −0,02 / −0,02 | Sabit 0,04 mm boşluk; bu bir ölçüm örneği |
| H7/p6 limitlerinin elle girişi | 0 / +0,025 | +0,026 / +0,042 | Sıkılık 0,001–0,042 mm; tam H7/p6 eşleşmesi |

**Tam ISO eşleşmesi** için hem alt hem üst sapma tabloya tam eşit olmalıdır. Tam eşleşme yoksa mevcut 11 delik ve 18 mil sınıfı içindeki en yakın sınıflar ve farklar gösterilir. Yakınlık ölçütü `|girilen alt − ISO alt| + |girilen üst − ISO üst|`; eşit yakınlıkta bütün en yakın sınıflar gösterilir; sınıf adı sırası bir tercih veya tekil eşleşme değildir. Bu ölçüt ISO'nun yeni bir sınıf atama kuralı değildir. Girilen toleranslar otomatik ISO değerine yuvarlanmaz; geçme hesabı daima kullanıcı limitlerinden yapılır. Yakınlık, başka çap/sınıflara kapsam genişletmesi veya geometrik uygunluk kararı değildir.

İlk örnekte delik 0…+20 µm: en yakın **H6 (0…+16)**, alt fark 0, üst fark +4 µm. Mil −20…0 µm: en yakın **h6 (−16…0)**, alt fark −4, üst fark 0 µm. Bunlar tam eşleşme değildir. Ölçü limitleri 50,000–50,020 ve 49,980–50,000 mm olarak korunur; hesap `50,000−50,000=0` ve `50,020−49,980=0,040 mm` verir.

“Sıkı” ve “ara” sınıfları boyut limitlerinden hesaplanır. “Kayar”, “bol/serbest” ve “hareketli/yağlı çalışma adayı” pratik kullanım yorumlarıdır. Minimum boşluk sıfırsa kayar/sınırda temas adayı; pozitif boşlukta en yakın doğrulanmış boşluklu yaygın eşleşmenin kullanım ailesi gösterilir. H11/c11 ve H9/d9 bol/serbest; H8/e8, H8/f7 ve H7/g6 hareketli/yağlı çalışma adaylarıdır. **Yağlama ihtiyacı veya montaj kuvveti**, yalnız toleranslardan kesin belirlenmez; malzeme, yüzey, hız, yük ve sıcaklık gerekir.

[Manuel menünün gerçek görüntüsü](reports/manual-iso/screenshots/iso-manual-dark.png), [ISO karşılaştırma alanı](reports/manual-iso/screenshots/iso-manual-comparison-dark.png) ve [güncel test/Word raporu](reports/manual-iso/README.md).

## Montaj uyumu ve en yakın geçme

**Montaj hedefi** menüsüyle Genel kontrol, Serbest/kayar, Ara/konumlandırma veya Sıkı/pres seçilir. Yeni **MONTAJ UYUMU / EN YAKIN GEÇME** kartı, girilen delik/mil limitlerinin bu hedefi bütün izin verilen ölçü kombinasyonlarında sağlayıp sağlamadığını açıklar.

| Hedef | Boyutsal koşul | Sınır durumu |
| --- | --- | --- |
| Serbest / kayar | `Cmin > 0`: bütün limitlerde pozitif boşluk | `Cmin = 0`: sınırda temas; serbest montaj garanti değil. Negatif Cmin: sıkılık oluşabilir. |
| Ara / konumlandırma | `Cmin < 0 < Cmax`: ölçüye bağlı boşluk veya sıkılık | Tek taraflı veya yalnız temas aralığı, ara geçme koşulunu sağlamaz. |
| Sıkı / pres | `Cmax < 0`: bütün limitlerde pozitif sıkılık | `Cmax = 0, Cmin < 0`: sınırda temas; her parçada sıkılık garanti değil. |

Uyumluluk boyutsal bir kontroldür. Pres kuvveti, malzeme, şekil hataları, yüzey, yük ve çalışma koşulları için üretim değerlendirmesi gerekir. Genel kontrolde “her ölçüde boşluk”, “sınırda temas” veya “bazı parçalar boşluklu, bazıları sıkı” açıklaması verilir; bilinmeyen üretim dağılımından geçme olasılığı üretilmez.

**En yakın ISO çift**, mevcut delik/mil sınıflarından toplam dört limit farkı en küçük olan çifttir. Ayrı delik/mil en yakınlarının birleşimi bu toplamı en aza indirir. Manuel sonuçta H7 ağırlıklı ayrı hazır örnek önerisi gösterilmez. Eşit farkta bütün en yakın delik/mil sınıfları açıkça verilir; gösterilen referans çift bunlardan bir temsilcidir. Toplam fark nm hassasiyetle hesaplanıp mm gösterilir; girilen toleranslar değiştirilmez.

Referansın türü gerçek hesabın türünden farklıysa kartta açık not verilir. En az bir limit farkı ilgili parçanın referans tolerans genişliğinden büyükse uzaklık açıklanır. Bu genişlik karşılaştırması uygulamanın açıklayıcı kontrolüdür; ISO'nun ayrı bir kabul/ret kuralı değildir. “En yakın” etiketi, tam ISO eşleşmesi veya üretime uygunluk kararı yerine geçmez.

**Kullanıcı örneği:** nominal 50 mm, mil alt −0,1/üst +0,1 mm; delik alt −0,05/üst 0 mm. Delik **49,950–50,000**, mil **49,900–50,100 mm**. En sıkı durum `49,950−50,100=−0,150 mm`, en boşluklu durum `50,000−49,900=+0,100 mm`: **ara geçme**. Serbest/kayar veya her parçada sıkı/pres hedefi garanti edilmez; ara geçme hedefi boyutsal olarak oluşur.

Bu örnekte en küçük toplam fark 0,163 mm'dir: delikte N7 ve P7 eşit uzaklıktadır; milde h9 en yakındır. N7/h9 gösterilen referanslardan biridir; tek bir ISO sınıfına atama yapılmaz. N7/h9 için alt/üst farkları delikte −17/+8 µm, milde −38/+100 µm; mutlak toplam 163 µm. Girilen ölçüler bu referanslara dönüştürülmez ve sonuç ara geçme olarak kalır.

[Yeni uyumluluk ekranı](reports/fit-compatibility/screenshots/iso-compatibility-dark.png) ve [güncel test/Word raporu](reports/fit-compatibility/README.md).

## Standart temeli ve kapsam

- **ISO 286-1:2010**: doğrusal boyut toleransları için ISO kod sistemi, tolerans/sapma/geçme kuralları. [ISO çevrimiçi katalog kaydı](https://www.iso.org/obp/ui/#iso:std:iso:286:-1:ed-2:v1:en).
- **ISO 286-2:2010**: delik ve millerin standart tolerans sınıfları ve sınır sapma tabloları. [ISO çevrimiçi katalog kaydı](https://www.iso.org/obp/ui/#iso:std:iso:286:-2:ed-2:v1:en).

Bu oturumda resmî ISO ve üretici sitelerine erişim bulutun ağ politikası tarafından engellendi. Tam ISO metni indirilmedi, uygulamaya gömülmedi veya bu oturumda incelenmiş sayılmadı. Güncel baskı/düzeltme durumu resmî katalogdan ayrıca kontrol edilmelidir. Aşağıdaki açık GitHub kaynakları resmî ISO onayı veya sertifikası değildir; tabloları karşılaştırılabilir, sabit sürümlü sayısal referanslardır.

Doğrulanan nominal çap aralığı **1 ≤ D ≤ 400 mm**. Delik sınıfları:

`H6 H7 H8 H9 H11 F8 G7 JS7 K7 N7 P7`

Mil sınıfları:

`c11 d9 e8 f7 g6 h5 h6 h7 h8 h9 h11 js6 k6 m6 n6 p6 r6 s6`

Delikler büyük, miller küçük harfle gösterilir. Kapsam dışı çap/sınıf için tahmin yapılmaz. Çap aralığının üst sınırı dahildir: **D=50 mm** için 30–50 ana IT aralığı kullanılır; **D>50 mm** sonraki aralığa girer. Bazı temel sapmalar daha küçük alt aralıklar kullanır; veri dosyası bunların birleşimini içerir. 3, 6, 10, 14, 18, 24, 30, 40, 50, 65, 80, 100, 120, 140, 160, 180, 200, 225, 250, 280, 315, 355 ve 400 mm sınırları kapsanır. İlk veri aralığı 0<D≤3 olsa da uygulamanın doğrulanan alt sınırı 1 mm'dir.

Bu ekran çap geçmeleri içindir. Genel ölçü toleransları, ISO 1101 geometrik toleransları, yüzey kalitesi veya GD&T hesaplayıcısı değildir. Montaj kuvveti, ısıl genleşme ve pres kapasitesi için malzeme, yüzey, temas uzunluğu ve sıcaklık gibi ek bilgiler gerekir. Uygulama çap limitlerinden “yağlı/elle montaj” veya pres kuvveti sonucu üretmez.

## Hesap ve elle kontrol

Sapmalar veri dosyasında **tam sayı nanometre** tutulur. Çap ve ölçüler Python `Decimal` ile hesaplanır; yaklaşık IT formülü veya kayan nokta yuvarlaması kullanılmaz. Grafik koordinatlarında kullanılan kayan nokta, raporlanan hesap değerlerini değiştirmez. JS/js yarım mikrometre değerleri korunur.

```text
Dmin = D + EI              Dmax = D + ES
dmin = D + ei              dmax = D + es
Cmin = Dmin − dmax = EI − es
Cmax = Dmax − dmin = ES − ei
```

`Cmin ≥ 0`: boşluklu geçme, sıfır boşluk sınırda temas demektir. `Cmax ≤ 0`: sıkı geçme. Diğer durum: ara geçme. Sıkı geçmede pozitif sıkılık aralığı `−Cmax … −Cmin` olarak gösterilir. Ara geçmede en büyük sıkılık ve en büyük boşluk ayrı gösterilir. Yaygın eşleşmelerin grubu girilen çapa göre yeniden hesaplanır; örneğin H7/p6, 3 mm'de ara geçme, 50 mm'de sıkı geçmedir.

| Ø50 mm eşleşme | Delik ölçüsü (mm) | Mil ölçüsü (mm) | Delik − mil aralığı (mm) | Tür |
| --- | --- | --- | --- | --- |
| H8/f7 | 50,000–50,039 | 49,950–49,975 | +0,025 … +0,089 | Boşluklu |
| H7/h6 | 50,000–50,025 | 49,984–50,000 | 0 … +0,041 | Boşluklu; sınırda temas |
| H7/k6 | 50,000–50,025 | 50,002–50,018 | −0,018 … +0,023 | Ara |
| H7/p6 | 50,000–50,025 | 50,026–50,042 | −0,042 … −0,001 | Sıkı; 0,001–0,042 mm |

H8/f7 elle kontrol: `EI=0`, `ES=+39 µm`, `es=−25 µm`, `ei=−50 µm`. Dolayısıyla `Cmin=0−(−25)=25 µm`, `Cmax=39−(−50)=89 µm`. Paylaşılan tasarım görselindeki 0,074–0,161 mm sonuç bu eşleşme için kullanılmadı.

## Sayısal kaynaklar ve farkların çözümü

| Kaynak | Sabit commit | Kullanım |
| --- | --- | --- |
| [parkergreene/isofits](https://github.com/parkergreene/isofits/tree/d3083a941e8071bb12114a28a25274bf99c30ac0) | `d3083a9` | Delik/mil tablosu; `isotol` Python fonksiyonu gerçekten yürütülerek D>3 mm karşılaştırıldı. MIT bildirimi [saklandı](../iso_fits/ISOFITS-LICENSE.txt). |
| [lachr/Passungsrechner](https://github.com/lachr/Passungsrechner/tree/0289439b1883db363d92e38f1ab352817b4d5a47) | `0289439` | İkinci delik/mil sınır sapma tablosu, 1–400 mm. JavaScript arayüzü çalıştırılmadı; JSON sayıları karşılaştırıldı. |
| [bell-jamie/iso-286](https://github.com/bell-jamie/iso-286/tree/6580fbecaf167249024c60e35c4b8fbbddb540f4) | `6580fbe` | IT, temel sapma ve delta tablolarından seçili sayısal veriler çıkarıldı. Rust kodu bu ortamda çalıştırılmadı. |
| [saucecode/ISO286](https://github.com/saucecode/ISO286/tree/f455cecdfc6659f35002bc112e3667f4316eb086) | `f455cec` | Bağımsız IT genişlikleri ve C–H temel sapmaları; eksik sınıf uygulama kodu referans alınmadı. |

Veri oluştururken IT tablosunun 0,1 µm değerleri 100 ile, temel sapmaların µm değerleri 1000 ile çarpılarak nm'ye çevrildi. H/h sıfır temel sapma, JS/js ±IT/2 kullanır. K7/N7/P7 delikleri için 3 mm üzerindeki delta `IT7−IT6`, ilk aralıkta sıfırdır. K–S mil sınıfları için seçili IT6 ve tablodaki alt sapmalar kullanıldı. Aralıklar bağımsız kaynaklarla karşılaştırıldı; dış uygulama kodu projeye kopyalanmadı.

**F8, D≤3 mm:** Passungsrechner satırı ES=+20, EI=+10 µm veriyor; genişliği 10 µm oluyor. IT8 ise 14 µm ve F temel sapması +6 µm. Uygulamadaki doğru satır **ES=+20, EI=+6 µm**; yanlış satır kullanılmadı. Karşılaştırma 1,5 ve 3 mm'de bu iki farkı açıkça kaydeder. `isofits` API'sinin D=3 mm sınırında indeks hatası bulunduğu için o API yalnız D>3 mm'de yürütüldü.

[Kaynak karşılaştırma kanıtı](reports/iso-fits/source-comparison.json): **3217 kontrol**, 3215 eşleşme, bilinen hatalı kaynak satırından 2 fark, 0 beklenmeyen fark. Bunun 1100'ü dış Python API'sinin gerçek yürütülmesi, 1288'i ikinci sınır tablosu, 667'si IT genişliği, 162'si temel sapma kontrolüdür. Kaynak commitleri/dosya SHA-256 değerleri ve uygulama tablosunun hash'i kanıtta kayıtlıdır.

Yeniden üretmek için dört kaynağı tablodaki commitlere checkout edip klasörleri `isofits`, `passungsrechner`, `iso-286-rust`, `ISO286` olarak aynı dizine koyun:

```bash
.venv/bin/python docs/report-tools/compare_iso_sources.py --sources /tmp/gokworks-iso-sources
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user .venv/bin/python -m unittest discover -s tests -v
```

[ISO eklemesinin 216 testlik tarihsel raporu](reports/iso-fits/README.md); [manuel kontrolün 230 testlik raporu](reports/manual-iso/README.md); [montaj uyumu sonrası güncel rapor](reports/fit-compatibility/README.md).
