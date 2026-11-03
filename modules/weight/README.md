# Ağırlık hesabı

**Hesaplar → Ağırlık hesabı.** Kesit ölçülerinden, doğrulanmış standart profil
kütüphanesinden veya açık SOLIDWORKS modelinden kütle; birden çok parçayı bir
listede toplayıp malzeme maliyeti ve rapor üretme. SOLIDWORKS ve internet
olmadan da tam çalışır. “Ağırlık” günlük kullanımdaki kütle anlamındadır (kg).

## Kesit türleri

| Kategori | Türler | Ölçüler |
| --- | --- | --- |
| Dolu malzeme | Mil, kare dolu çubuk, lama / dikdörtgen çubuk, altıköşe çubuk, sac levha | d · b · b×t · s (anahtar ağzı) · en×kalınlık (boy = sac boyu) |
| İçi boş kesit | Boru, kare kutu profil, dikdörtgen kutu profil | D, t · b, t · b, h, t; köşe biçimi |
| Açık profil | Eşit / farklı kollu köşebent, U (hadde), bükme U (sac), T, I profil | kollar, t, kök yarıçapı r₁ · h, b, tw, tf, r · A, B, t, iç büküm r |
| Standart profil | IPE, HEA, HEB, HEM, HP, HD, UPE, UPN (NPU), eşit ve farklı kollu köşebent (EN 10056-1) | listeden seçilir |

Her kesit türü `sections.py` içinde tek bir kayıt (alanlar + alan fonksiyonu +
çizim) olarak tanımlıdır; yeni bir aile bu kayda eklenerek genişletilir. Her
tür kendi ölçülerini ayrıca hatırlar (sac için b = 1000 mm, kutu için 100 mm).

## Hesap yöntemleri

`A` mm², `L` mm, `ρ` kg/m³:

```text
kg/m      = A × ρ / 1.000.000
parça kg  = kg/m × L / 1000
toplam kg = parça kg × adet
hacim m³  = A × L / 10⁹
```

| Kesit | Alan |
| --- | --- |
| Mil | πD²/4 |
| Boru | π(D² − d²)/4, d = D − 2t |
| Kare / lama / sac | a² · a×b |
| Altıköşe | √3·s²/2 |
| Kutu, keskin köşe | BH − (B−2t)(H−2t) |
| Kutu, köşe yarıçaplı | 2t(B+H−2t) − (4−π)(rₒ² − rᵢ²) |
| Köşebent (EN 10056-1) | t(a+b−t) + (1−π/4)(r₁² − 2r₂²), r₂ = r₁/2 |
| U (paralel başlık) | 2b·tf + (h−2tf)·tw + (4−π)/2·r² |
| Bükme U (sac) | t·[(A − 2(r+t)) + 2(B − (r+t))] + 2·π/4·((r+t)² − r²) |
| T | b·tf + (h−tf)·tw |
| I / H (EN 10365) | 2b·tf + (h−2tf)·tw + (4−π)·r² |

Kutu profilde **Soğuk şekillendirilmiş · EN 10219-2** (varsayılan) seçeneği
rₒ = 2t (t ≤ 6), 2,5t (6 < t ≤ 10), 3t (t > 10) ve rᵢ = rₒ − t kullanır. Bu
değerler EN 10219-2 dış köşe tolerans bantlarının (1,6–2,4t, 2,0–3,0t,
2,4–3,6t; Tata Steel Hybox veri sayfası) ortasıdır. **Elle yarıçap** rₒ ve rᵢ
girer, **Keskin köşe** yaklaşık modeldir. Sıcak bitirilmiş (EN 10210-2) için
yarıçaplar doğrulanmış bir kaynaktan teyit edilemediği için otomatik seçenek
yoktur; elle girin.

Köşebent, U ve I profilde kök yarıçapı 0 bırakılırsa sonuç **yaklaşık** olarak
işaretlenir. T profil ve eğimli başlıklı profiller (IPN, UPN elle girilirse)
geometrik modelde yaklaşıktır.

## Standart profil kütüphanesi

`data/sections.json`: 175 kesit. Değerler üretici veri sayfalarından
`data/extract_catalogue.py` ile **programla** çıkarıldı, elle yazılmadı:

| Aile | Kaynak |
| --- | --- |
| IPE, IPE A, IPE O, HEA/HEB/HEM | Stahlwerk Thüringen (EN 10365:2017), eksik boylar British Steel |
| HP, HD, UPE | Stahlwerk Thüringen (EN 10365:2017) |
| UPN | Stahlwerk Thüringen (EN 10365:2017) + Kocaer Çelik (DIN 1026-1) |
| Köşebent 120–200, 200×100, 200×150 | British Steel (EN 10056-1) |

Her satır yazılmadan önce iki kontrolden geçer: ölçülerden yeniden hesaplanan
alan tablo alanıyla, alan × 7850 de tablodaki kg/m ile eşleşmelidir. İki
üretici aynı kesiti veriyorsa ölçüler karşılaştırılır. Kendi içinde tutarsız
19 satır reddedildi (ör. British Steel IPE 330: r = 20 mm ile verilen alan,
kg/m sütunundaki r = 18 mm değeriyle uyuşmuyor). Üreticiler arasında farklı
olan 8 kesitte EN 10365 değeri kullanılır, diğer değer sonuçta not olarak
gösterilir.

Standart profilde **katalog kg/m esastır** (çelik, 7850 kg/m³). Başka bir
yoğunluk seçilirse kg/m = katalog alanı × ρ hesaplanır ve bu ayrıca yazılır.
Ölçülerden hesaplanan geometrik alan ve katalogdan farkı rapor satırında
gösterilir. **IPN, HL ve 120 mm altı köşebentler** için erişilebilir doğrulanmış
kaynak bulunamadı; bunlar kütüphanede yoktur, Açık profil türleriyle ölçü
girerek hesaplanır.

## Malzemeler

58 kayıtlı malzeme (Genel, Sac / Yapı, Makine / Takım, Kalıp çelikleri,
Paslanmaz, Alüminyum alaşımları, Saf metaller, Plastikler) ve **Özel malzeme**. Kayıtlı
malzemelerde yoğunluk sabittir; farklı bir değer için Özel malzeme seçilip ad
ve yoğunluk (100–25.000 kg/m³) girilir. Kaynaklar [materials.md](materials.md)
ve `materials.py` içindedir. Yoğunluk alaşıma ve ürüne göre değişebilir; aynı
malzeme için kaynaklar farklı değer verebilir (ör. FreeCAD S235JR 7800,
nominal yapı çeliği 7850 kg/m³).

## ESN Metal karşılaştırması

[ESN Metal ağırlık hesaplama](https://www.esnmetal.com/agirlik-hesaplama/) 12
ayrı hesaplayıcı sunar: altıköşe, boru, HEA, IPE, kare demir, köşebent, kutu
profil (köşe radyüsü dahil), mil, sac, silme lama, T demir ve bükme U profil
(büküm radyüsü). Tamamı burada karşılanır; ek olarak HEB, HEM, HP, HD, UPE,
UPN, standart köşebentler, I ve hadde U profil, keskin/EN köşe seçimi vardır.
ESN’in hesabı sunucuda yapılır (formül sayfada yoktur); malzeme listesindeki
bazı değerler hatalıdır (ör. Nikel 1,74 g/cm³, Polietilen 1,2 g/cm³), bu
yüzden veri kaynağı olarak kullanılmadı. ESN’de serbest yoğunluk girişi ve
toplam ağırlıklı hesap geçmişi vardır; burada Özel malzeme ve maliyetli
hesaplama listesi karşılığıdır. IPE 80, IPE 600 ve IPE 750 serisi ESN’de olup
burada yoktur: erişilen kaynaklarda bu satırlar kendi içinde tutarlı değildi.

## Hesaplama listesi ve maliyet

**Hesaplamaya ekle** geçerli hesabı parça adı ve isteğe bağlı TL/kg fiyatla
listeye ekler. Tabloda parça adı, boy, adet ve fiyat çift tıklanarak
düzenlenir; satır çoğaltılır veya silinir. Fire % malzeme ağırlığına ve
tutara eklenir, KDV % tutara uygulanır; ikisi de kullanıcı tarafından
değiştirilir. **Tutar yalnız malzeme bedelidir; işçilik, kesim, nakliye ve diğer
üretim giderleri dahil değildir.** Liste kapatıp açınca korunur.

**Dışa aktar**: Excel (.xlsx; sayılar sayı hücresi ve sayı biçimiyle), PDF
(seçili hesap, kesit çizimi, liste ve toplamlar), CSV (`;` ve ondalık virgül).

## Kesit çizimi

Kesit hesapta kullanılan ölçülerle **gerçek oranında** çizilir: köşe ve kök
yarıçapları dahil, ölçü çizgileri ve okları otomatik yerleşir, çizim ortalanır
ve panele sığdırılır. Fare tekerleği yakınlaştırır, sürükleme kaydırır,
**Sığdır** görünümü sıfırlar. 2 pikselden ince kalan kalınlık (ör. sac) okunur
olsun diye büyütülür ve çizimde bu yazılır.

## Aktif CAD modelinden hesap

**Aktif CAD modelinden hesapla** SOLIDWORKS’te açık parça veya montajın
hacmini, malzemesini, yoğunluğunu ve kütlesini mevcut bağlantıyla okur
(`IModelDocExtension.CreateMassProperty2`, sistem birimleri). Bu ayrı bir
yöntemdir: delik, pah ve boşaltmalar model hacmine dahildir. Tek adetli
formül hesabıyla yüzde farkı gösterilir. Parçada malzeme yoksa (SOLIDWORKS
1000 kg/m³ varsayar) veya etkin belge teknik resimse anlamlı hata verilir.
Canlı SOLIDWORKS oturumunda henüz denenmedi; okuma mantığı sahte nesnelerle test edilir.

## Giriş kuralları

Ondalık virgül veya nokta kabul edilir; `1.234,5` binlik ayırıcılı yazımdır.
`1.000` gibi belirsiz yazım (bin mi, bir mi?) reddedilir; sessizce 1 olarak
okunmaz. Sıfır, negatif, sonsuz ve geometriyi geçersiz kılan değerler (et
kalınlığı, sığmayan yarıçap) hata verir. Ara hesaplarda yuvarlama yapılmaz;
sonuç birimi (kg, g, t) ve ondalık hassasiyet (0–4) seçilir.

## Testler

`python -m pytest modules/weight` — kabul değerleri (Ø220×200 mil 59,681 kg;
1000×2000×2 sac 31,4 kg; 20×20×1000 kare 3,14 kg; Ø60×3×1000 boru 4,217 kg),
her kesit için bağımsız el formülü, katalog karşılaştırmaları, birimler, adet,
yoğunluk, geçersiz/aşırı değerler, ondalık biçimleri, liste toplamları,
CSV/XLSX/PDF ve SOLIDWORKS okuma (sahte nesnelerle).
