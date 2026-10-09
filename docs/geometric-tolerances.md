# Geometrik toleranslar / ASME GD&T

**GEOMETRİK TOL.**, CAD aktarımından bağımsız beşinci çalışma alanıdır. Kullanıcının sağladığı ASME Y14.5-2018 belgesindeki kurallara göre 12 güncel özelliği açıklar; kaldırılmış iki sembolü eski çizimler için ayrı gösterir. Bölüm referansı, sembol, örnek çerçeve, bölge, datum ilişkisi, ölçüm yöntemi ve üretim notu vardır. Türkçe/İngilizce arama, açık/koyu tema, CSV/pano ve okuma rehberi desteklenir.

## Birincil belge

Kullanıcının sağladığı `ASME-Y14.5-2018-R2024-Dimensioning-and-Tolerancing.pdf`, 347 sayfadır. Kapak/ana metin **ASME Y14.5-2018** olarak kontrol edildi. Dosya adında R2024 var; yeniden onay bilgisi içerikte teyit edilmedi. PDF metadata başlığı farklı bir standart adı içerdiği için baskı kanıtı olarak kullanılmadı. Kurallar kapak ve bölüm içeriğinden incelendi.

SHA-256, boyut, bölüm eşleştirmeleri ve PDF sayfa indeksleri [kaynak kanıtındadır](reports/geometric-tolerances/source-comparison.json). PDF veya standart figürleri GitHub'a kopyalanmadı. Açıklamalar ve Tk vektörleri özgündür. İlgili bölümlerin incelenmesi bütün 347 sayfanın doğrulandığı veya resmî yeniden onay kaydının sertifikalandırıldığı anlamına gelmez.

## Kullanım

1. Türü soldan seçin. 12 güncel tür ve **Eski işaretler** grubu vardır; seçim görünür tutulur.
2. Gösterim boyutunu ve **toplam t (mm)** değerini girin. Gösterim boyutu örnek bağlamıdır; basic konum ölçüsü değildir ve otomatik tolerans üretmez.
3. Gerekiyorsa örnek datum sırasını seçin: A, A | B, A | B | C. Şekilde **Gerekmez** gösterilir. Yön ve bu RFS delik konumu referans ister; profil datumsuz da kullanılabilir.
4. Bölgeyi ve kaydırarak ölçüm/üretim açıklamalarını okuyun. İngilizce adın yanında belge bölüm numarası vardır.
5. Normal, boyutla ilişkili yüzey şekli için istenirse **ilgili boyut toleransını** girin: üst boyut limiti − alt boyut limiti. `t < boyut toleransı` kontrol edilir.
6. İstenirse **ölçülmüş toplam geometrik hata** girin. Doğru özellik/datum/bölgeyle değerlendirilmiş hata olmalıdır; tek çap/nokta sapması değildir.
7. CSV/pano ile belirtimi alın; **Rehber** ASME kurallarını açıklar.

Tür değişince ölçüm ve ilgili boyut toleransı temizlenir. Sayfa geçişi oturum değerlerini korur. Yeniden açılış ölçümü geri yüklemez; tür, boyut, t, datum, boyut toleransı ve tema kaydedilir. Geçersiz değer/kaldırılmış sembolde çerçeve, bölge ve CSV/pano engellenir.

## Basit belirtim örnekleri

| Tür | Bölge / kontrol edilen özellik | Bölüm |
| --- | --- | --- |
| Doğrusallık | Yüzey çizgisi: iki paralel doğru, uzaklık t | 8.4.1.1 |
| Düzlemsellik | Yüzey: iki paralel düzlem, uzaklık t | 8.4.2 |
| Dairesellik | Her kesitte eş merkezli çemberler, radyal uzaklık t | 8.4.3 |
| Silindiriklik | Eş eksenli silindirler, radyal uzaklık t; bütün yüzey | 8.4.4 |
| Paralellik | Datuma paralel iki düzlem | 9.3–9.3.2 |
| Diklik | Datuma dik iki düzlem | 9.3–9.3.2 |
| Açısallık | Datuma basic açıda iki düzlem; t mm, derece değil | 9.3–9.3.2 |
| Konum | RFS delik ekseni: true position çevresinde çapı t olan silindir | 10.2–10.3.2 |
| Çizgi profili | True profile çevresinde uniform/eşit dağılımlı, normal yönde toplam genişlik t | 11.2.1.2 / 11.3.1 |
| Yüzey profili | Aynı profil ilkesiyle üç boyutlu bölge | 11.2.1.1 / 11.3.1 |
| Dairesel salgı | Radyal örnekte her kesitte datum eksenine eş merkezli çemberler | 12.4.1.1 |
| Toplam salgı | Radyal örnekte bütün yüzey için datum eksenine eş eksenli silindirler | 12.4.2.1 |

**Silindiriklik t=0,3 mm, ±0,3 değildir:** iki silindir arasındaki toplam radyal uzaklık. Dairesellik/koniklik/boyuna hataları birlikte sınırlar; ayrı hataların aritmetik toplamı değildir. Konum **Ø0,3** için radyal pay 0,15 mm'dir.

Yüzey çizgisi ile türetilmiş medyan çizgi, yüzey düzlemselliği ile medyan düzlem farklı uygulamalardır; burada yüzey örnekleri vardır. RFS konum **unrelated AME ekseni** içindir; türetilmiş medyan çizgiyle karıştırılmaz. Açısallıktaki 45° örnektir. Şemalar ölçekli değildir; 3B bölgeler kesit/izdüşümle gösterilir, çember oranı korunur.

## Temel ASME kuralları

- **5.8.1 Rule #1:** Düzenli boyut özelliğinin yüzeyi MMC kusursuz şekil zarfını aşamaz. Boyut/şekil bağımsızlığı varsayılan değildir. İstisnalar 5.8.2 ve ilgili uygulamalardadır: as-furnished stok, free state, independency, AVG, medyan çizgi/düzlem ayrıca okunur.
- **8.4:** Normal, ilgili boyutla ilişkili yüzey şekil t değeri boyut toleransından küçük olmalıdır. İsteğe bağlı alan bu sayısal ilişkiyi kontrol eder; MMC zarfını ölçmez. Özel istisna/medyan uygulamaları burada üretilmez.
- **5.9.1 Rule #2:** Değiştiricisiz boyut özelliği toleransı **RFS**, datum boyut özelliği referansı **RMB**. RFS/RMB ve MMC/MMB aynı kavram değildir. Yüzey daireselliği/silindirikliği, yüzey yön/profil ve salgıya MMC/LMC eklenmez. M/L veya eski RFS sembolü üretilmez.
- **Bölüm 7:** Datum, datum unsurunun true geometric counterpart'ından kurulan teorik referanstır. A/B/C sırası önceliktir. Ortogonal düzlem–düzlem–düzlem örneğindeki 3-2-1 her geometriye uygulanamaz. Örnek harfler gerçek datum unsurlarını/modelini tanımlamaz.
- **5.1.1.2 / 10.2.1.1:** Basic ölçü teorik tam konumu/profili belirler; dikdörtgen çerçevelidir. Gösterim boyutu basic konum ölçüsü değildir.
- **10.3.2 / 5.9.2:** RFS konum AME ekseniyle değerlendirilir; MMC/LMC'de surface method varsayımı, virtual condition ve bonus burada hesaplanmaz.

Datumsuz konum tamamen yasak değildir; 10.6.2.3 özellikler arası koaksiyelliği açıklar. Bu delik konumu örneği o özel uygulamayı üretmediğinden datum ister. Profil datumla/datumsuz kullanılabilir; eşit dağılmayan bölge için ayrı işaret gerekir ve burada üretilmez.

## Kaldırılmış işaretler

Önsöz ve **Nonmandatory Appendix D, D.2–D.4**, concentricity ve symmetry tanım/sembollerinin 2018'de kaldırıldığını açıklar. Eski kartlarda sayısal giriş, güncel çerçeve/bölge ve CSV/pano kapalıdır.

Koaksiyellik için **10.6**, simetrik ilişkiler için **10.7**, position/profile/uygun runout seçeneklerini açıklar. Kontrol edilen eksen/merkez düzlemi/yüzey ve işlev belirlenmeden eski sembol değiştirilemez. Alternatifler eski medyan nokta kontrolüne otomatik/eşdeğer dönüşüm değildir.

## Sayısal kapsam

Virgül/nokta, en çok altı ondalık basamak ve `Decimal` kullanılır. `hata <= t`, `pay = t − hata`: t=0,05 için hata 0,050000 sınırda, 0,050001 sınır dışında; pay −0,000001 mm. 1 nm aşım yuvarlanmaz. Normal yüzeyde t=0,05 / boyut toleransı 0,05 reddedilir; 0,050001 boyut toleransı ilişkiyi sağlar.

Gösterim boyutu `0 < D ≤ 10000`, t/boyut toleransı `0 < değer ≤ 1000`, hata `0 ≤ e ≤ 1000` mm: arayüz sınırlarıdır, normatif ASME aralığı/üretim önerisi değildir. Sıfır MMC konum, bonus, datum mobility, kompozit/ortak bölge, tangent plane, projected zone, free state ve profil değiştiricileri üretilmez.

Bu aritmetik kontrol CMM hesabı, ölçüm belirsizliğiyle kalite kabulü veya tam ASME resim/model doğrulaması değildir. Basic ölçüler, boyut limitleri, datum geometrisi, Rule #1 zarfı, fikstür/ilişkilendirme/belirsizlik ayrıca değerlendirilir. CAD'e tolerans yazılmaz. Desteklenen basit örneklerin kuralları belgeden kontrol edildi; bütün standart belirtimlerini kapsayan editör değildir. ISO 286 geçmeleri ayrı çalışma alanıdır.

## GitHub yardımcı karşılaştırması

[FreeCAD-GDT](https://github.com/juanvanyo/FreeCAD-GDT), [FreeCAD eklenti kataloğundan](https://github.com/FreeCAD/FreeCAD-addons/blob/master/.gitmodules) bulundu. Commit **841518cdd74f6a7dad3321d29937c49dc7dc4b1f**: `geometricTolerance.py`/`GDT.py` ad ve çerçeve yapısı incelendi. 14 eski ad eşleşti; 14 SVG hash'i kaydedildi. Silindiriklik/toplam salgı sembolleri yapısal olarak incelendi. Kod/SVG kopyalanmadı.

Eski kaynak kaldırılmış iki işareti içerir; uygulama bunları birincil ASME belgesine göre engeller. FreeCAD çalıştırılmadı ve sayısal/normatif doğrulayıcı kabul edilmedi. Standart kuralları yüklenen belgeden kontrol edildi. Kanıtta 12 aktif/2 engellenen ayrımı ve sekiz bölüm çıpası vardır.

```bash
.venv/bin/python docs/report-tools/verify_gdt_reference.py \
  --reference /tmp/gokworks-gdt-reference \
  --standard /path/to/ASME-Y14.5-2018-R2024-Dimensioning-and-Tolerancing.pdf
```

Checkout sabit commit'te olmalıdır. Belge yardımcısı `pdftotext`/`pdfinfo` ister; bunlar uygulama bağımlılığı değildir.

## Testler ve rapor

10 hesap/içerik ve 11 gerçek GUI testi eklendi. 12 güncel/2 eski tür iki temada seçildi. Datum/çerçeve, Rule #1 hata engeli, 1 nm eşik, geçersizlik, arama/Ctrl+F, CSV/pano/iptal/kayıt hatası, tercihler/rehber ve ölçüm temizliği sınandı.

İki tema × 1000×690, 1240×860, 1366×768, 1400×900 (%125), 1920×1080 (%150): gerçek boyutlar ve bütün alan/düğmelere kaydırarak erişim kontrol edildi. Gerçek Windows DPI/SolidWorks üretimi Linux denetiminde çalıştırılmadı. [Testler, ekranlar ve Word raporu](reports/geometric-tolerances/README.md).
