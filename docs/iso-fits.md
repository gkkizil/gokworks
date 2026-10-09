# ISO geçme toleransları

Yan menüde **ISO GEÇMELERİ** ekranı bulunur. Nominal çapı yazın, delik ve mil sınıfını seçin veya soldaki yaygın eşleşmelerden birine tıklayın. Virgül ve nokta kabul edilir. Hesap SolidWorks bağlantısı olmadan çalışır; CAD parametrelerini değiştirmez.

Delik/mil alt ve üst ölçüleri, EI/ES ve ei/es sapmaları, boşluk veya sıkılık sınırları gösterilir. **mm / µm** seçimi sapma ve geçme sonuçlarının birimini değiştirir; nominal çap ve parça ölçüleri mm olarak kalır. **CSV kaydet** UTF-8 BOM, noktalı virgül ve ondalık virgülle Excel'e uygun rapor oluşturur. **Sonucu kopyala** bütün sayısal sonuçları panoya verir. Tema ve seçimler yeniden açılışta korunur.

**Montaj kesiti** şematiktir; sapmalar görünürlük için büyütülür. Üç örnek ölçü arasında büyütme oranı sabittir. **Tolerans bölgeleri** gerçek sapma değerlerine göre doğrusal eksen kullanır. *Orta değer* yalnızca limitlerin ortasıdır; üretimin olasılık dağılımını temsil etmez. Arama ve Ctrl+F yaygın eşleşmeleri bulur. Küçük pencerede iki liste kaydırılabilir.

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

[ISO eklemesinin test raporu ve gerçek ekran görüntüleri](reports/iso-fits/README.md).
