# Ağırlık hesabı

**Mühendislik hesapları → Ağırlık hesabı**. SolidWorks veya internet bağlantısı
gerektirmeyen, ölçü ve yoğunluktan kütle hesabı. Sonuçlar kg olarak gösterilir;
ekranda kullanılan “ağırlık” günlük kullanımdaki kütle anlamındadır, Newton
cinsinden yerçekimi kuvveti hesabı değildir.

## Kesit ve malzemeler

Kutu profil, sac levha, boru, köşebent, kare demir, T profil, U profil,
HEA, HP, HD, HL, IPN, UPE, altıköşe, HE, IPE, UPN, mil ve silme lama:
kullanıcının referans görselindeki 19 tür bulunur. Boyutlar kesite göre değişir.
H/I/U aile adları otomatik standart profil boyutu veya katalog ağırlığı seçmez;
girilen ölçüler esas alınır.

**39 kayıtlı malzeme** Genel, Sac / Yapı, Makine / Takım, Kalıp Çelikleri,
Paslanmaz ve Plastikler gruplarında sunulur. Yaygın S235JR/S275JR/S355JR/S355J2, DC01–DC04
DKP, DX51D+Z/DX52D+Z galvaniz, S355MC, P265GH, C45, C45E, 42CrMo4, 16MnCr5,
34CrNiMo6 ve 304/316/316L seçenekleri bulunur. Delrin ve Kestamit korunur.
Kalıp Çelikleri grubunda 1.2379 soğuk iş, 1.2344 sıcak iş ve 1.2311/1.2312
plastik kalıp çelikleri bulunur;
genel çelik yoğunluğu yerine her kalitenin kaynaklı yoğunluğu kullanılır.
Kalite adlarının yanında türleri de yazılır: **1.2344 · Sıcak iş takım çeliği**,
**1.2379 · Soğuk iş takım çeliği**, **1.2311 / 1.2312 · Plastik kalıp çeliği**.
Tür bilgisi seçim menüsünde, sonuç kartında ve kopyalanan raporda görünür.
[Tam yoğunluk tablosu ve kaynak bağlantıları](materials.md).

Yoğunluk **sabittir**: menüde g/cm³, yanında kg/m³ olarak gösterilir ve seçilen
malzemeden otomatik alınır. Yoğunluk giriş alanı, özel malzeme ve elle
değiştirme seçeneği yoktur. Eski `weight_density` tercihi okunmaz ve bir
sonraki kayıt sırasında silinir. Hesap API'si de farklı yoğunluk atamasını reddeder.
Kayıtlı değerler kaynaklardaki nominal ağırlık hesabı değerleridir; mekanik
dayanım veya malzeme sertifikası yerine geçmez. Aynı yoğunluğu paylaşan
çelik kalitelerinin ağırlığı aynı çıkabilir; dayanım özellikleri aynı değildir.

## Kullanım

1. Kesit ve malzemeyi seçin.
2. Ölçü birimini belirleyin; ilgili kesit ölçülerini ve boyu girin.
3. Adedi girin. Adet başına kg, kg/m, hacim, kesit alanı ve toplam kg canlı güncellenir.
4. **Hesabı kopyala** girdileri, birimleri, yöntemi ve sonuçları panoya alır.

mm/cm/m değişimi mevcut ölçüleri dönüştürerek fiziksel sonucu korur. Adet ve
katalog alanı bu dönüşüme dahil değildir. Katalog alanı her zaman cm²,
yoğunluk her zaman seçilen malzemenin kayıtlı değeridir. Seçimler sayfa değişiminde ve yeniden
açılışta korunur. Geçersiz girişte önceki sonuç kaldırılır.

Kesit görünümü düz, hafif dolgulu **2D ön kesittir**. Perspektif ve gölgeler
kaldırılmıştır; temel kesit ölçüleri, kısa kalınlık bilgisi ve boy gösterilir.

## Hesap yöntemi

`A` mm² cinsinden kesit alanı, `L` mm cinsinden boy, `ρ` kg/m³ cinsinden yoğunluktur.

```text
Bir parçanın hacmi = A × L / 1.000.000.000   [m³]
Bir parçanın kütlesi = hacim × ρ            [kg]
Birim boy kütlesi = A × ρ / 1.000.000       [kg/m]
Toplam kütle = bir parçanın kütlesi × adet
```

| Kesit | Alan hesabı |
| --- | --- |
| Sac levha / silme lama | b × t |
| Kare demir | b² |
| Mil | πd²/4 |
| Boru | π/4 × (d² − (d−2t)²) |
| Kutu profil | bh − (b−2t)(h−2t) |
| Köşebent | t(b+h−t) |
| T profil | b·tf + (h−tf)·tw |
| U ve H/I aileleri | 2b·tf + (h−2tf)·tw |
| Altıköşe | √3/2 × s²; s anahtar ağzıdır |

Et kalınlığı, gövde/flanş çakışmaları, pozitif ölçüler, tam sayı adet ve sayısal
girdiler kontrol edilir. İçi boş kesitte iç boyut sıfır veya negatif olamaz.

**Ölçülerden** yönteminde kutu, köşebent, T, U ve H/I profiller keskin köşeli
geometriyle hesaplanır. Hadde köşe yarıçapı, flanş eğimi ve imalat toleransı
modellenmez; bu sonuçlar “yaklaşık” olarak belirtilir. **Katalog alanından**
yönteminde üretici katalog alanı cm² olarak girilir (`A = cm² × 100`). Böylece
gerçek nominal kesit alanı kullanılır; yoğunluk malzemeden, boy girişten alınır.
Bu moddaki çizim ölçülendirilmiş bir katalog çizimi değil, kesit türü şemasıdır.

Örnek: 1.000 × 2.000 × 10 mm çelik levha, 7.850 kg/m³ yoğunlukla **157 kg**;
aynı ölçülerde alüminyum 2.700 kg/m³ ile **54 kg**. 100 × 100 × 5 mm keskin
köşeli kutu profil alanı **1.900 mm²**, çelikte **14,915 kg/m** olur.

## Kaynak ve erişim durumu

İstenen [ESN Metal sayfasına](https://www.esnmetal.com/sac-agirlik-hesaplama/)
15 Ekim 2026 tarihinde normal ve yetkili ağ erişimiyle yapılan istekler HTTP403
döndürdü. Bu nedenle sayfanın malzeme listesi veya algoritması okunmuş ya da
birebir aktarılmış olarak sunulmaz. Kullanıcının belirttiği malzemeler ve
görseldeki kesitler esas alınmıştır.

Delrin ile genel POM değerini karıştırmamak için FreeCAD malzeme kartları
karşılaştırıldı: [POM-H](https://github.com/FreeCAD/FreeCAD/blob/384314776045a67fcdf09d49aa29306243578d4f/src/Mod/Material/Resources/Materials/Standard/Thermoplast/POM-Homopolymer-Generic.FCMat)
**1.420 kg/m³**, POM-C **1.410 kg/m³**; [genel PA6](https://github.com/FreeCAD/FreeCAD/blob/384314776045a67fcdf09d49aa29306243578d4f/src/Mod/Material/Resources/Materials/Standard/Thermoplast/PA6-Generic.FCMat)
**1.150 kg/m³**. Kestamit/PA6G değeri tipik yaklaşık başlangıç değeridir;
bu genel PA6 kartı özel bir üreticinin döküm PA6G ürününü doğrulamaz.

Alüminyum **2.700 kg/m³** ve bakır **8.960 kg/m³** değerleri de aynı FreeCAD
sürümündeki `Metal/Aluminum/Aluminum-Generic.FCMat` ve
`Metal/Copper/Copper-Generic.FCMat` kartlarıyla karşılaştırıldı. Genel çelik
**7.850 kg/m³** için [section-properties örneği](https://github.com/robbievanleeuwen/section-properties/blob/1e12d48b3ccb9ee1b7df8e2ac357c633cc004bdf/docs/user_guide/overview.rst)
`7,85 × 10⁻⁶ kg/mm³` değerini kullanır. Bu değer saf demirin yoğunluğu değildir.
Diğer sabit kayıtlar ve nominal kaynakları [yoğunluk tablosundadır](materials.md).
Kalıp çeliklerinde 1.2379 **7.700**, 1.2344 **7.800**, 1.2311/1.2312
**7.850 kg/m³** kullanılır. Değerler bağlantılı GitHub malzeme kartı ve
ağırlık hesabı kataloğundan alınmıştır; üretici föyü doğrulaması değildir.
304 için MMPDS referansı taşıyan GitHub kartı 7.916 kg/m³, 316/316L kartları
8.000 kg/m³ kullanır; özgün MMPDS/MatWeb/AZoM yayınlarının bu oturumda ayrıca
okunduğu iddia edilmez. PP 916, PTFE 2.070 ve PVC 1.380 kg/m³ olarak kaynak
kartlarına göre güncellendi. Kaynağı bu ortamda doğrulanamayan eski PE-HD
seçeneği çıkarıldı; başka bir polietilen türüne eşlenmedi.
Kesit alanının köşe/eğimlerden etkilenmesi
[I profil geometri örneğinde](https://github.com/robbievanleeuwen/section-properties/blob/1e12d48b3ccb9ee1b7df8e2ac357c633cc004bdf/src/sectionproperties/pre/library/steel_sections.py)
ayrıca incelendi. Bu projelerden kod veya katalog tablosu aktarılmadı.

Üçüncü taraf kod veya bağımlılık eklenmez. Windows EXE yalnız kullanıcı istediğinde oluşturulur.

## Doğrulama ve ekranlar

Sabit katalog ve sade çizim revizyonunda **18 ilgili kontrol geçti**:
13 hesap, 4 gerçek Tk ve 1 menü ön yükleme kontrolü. Malzeme grupları,
gerçek menü seçimi, eski yoğunluk tercihlerinin etkisiz olması, backend'de
yoğunluk değiştirme girişiminin reddi ve galvaniz kaplama açıklaması kontrol edildi.

Galvanizli DX51D+Z / DX52D+Z hesapları **çelik taban** içindir;
çinko kaplamasının ilave kütlesi hesaplanmaz ve sonuçta açıkça belirtilir.

15 Ekim 2026: 19 kesit, malzeme seçimi, sabit yoğunluk, adet, mm/cm/m,
katalog alanı, geçersiz girişler, tercihler, açık/koyu tema, küçük pencere ve
%125 ölçek kontrol edildi. Windows/SolidWorks veya
EXE derlemesi çalıştırılmadı.

Kalıp çeliği eklemesinde 13 mevcut hesap/katalog kontrolü geçti. Uygulama açılarak
200 × 300 × 40 mm levhada 1.2379 için **18,480 kg**, 1.2344 için **18,720 kg**
sonucu ve sabit yoğunluk gösterimi gerçek ekranlarda doğrulandı.

[Çelik kutu profil, koyu tema](examples/weight-steel-dark.png) ·
[Delrin mil, açık tema](examples/weight-delrin-light.png) ·
[1.2379 kalıp çeliği](examples/weight-2379-dark.png) ·
[1.2344 kalıp çeliği](examples/weight-2344-dark.png).
Gerçek Tk görüntülerini yeniden almak için `modules/weight/examples/capture.py` kullanılır.
Yalnız kalıp çeliği ekranları için dosya adlarını uzantısız verin:
`python modules/weight/examples/capture.py weight-2379-dark weight-2344-dark`.
