# Makaralı zincir dişlisi

Mevcut **Makine Elemanları → Dişli Hesaplama → Zincir Dişlisi · Makaralı Zincir**
türüdür. Yeni uygulama, servis veya bağımlılık eklemez. Hesap, gerçek daire yaylı
2D, ortalama dişli kinematiği, B-Rep 3D, DXF/STEP ve JSON proje akışı çevrimdışıdır.
SOLIDWORKS gerektirmez.

## Gerçek destek

ISO 606 B serisi tek sıra **08B-1, 10B-1, 12B-1 ve 16B-1** katalog kayıtları
desteklenir. Her kayıtta adım, en büyük makara çapı ve en küçük iç genişlik
Tsubaki BS/DIN GT4 Winner tablosuyla doğrulanmıştır. 08B-1 referansı
p=12,70 / dᵣ=8,51 / b₁=7,75 mm'dir. Katalog salt okunur; standart/seri ile ölçüler
eşleşmiyorsa API de reddeder. ANSI #40 gibi eşit adımlı zincirler eşdeğer sayılmaz;
ANSI, çok sıralı ve özel ölçü zincirler henüz etkin değildir.

## Dosyalar ve sözleşme

| Dosya | Görev |
| --- | --- |
| `models.py` | Değişmez zincir, tek dişli, çift ve sayısal sonuç modelleri |
| `catalog.py` | Kaynağı belirtilmiş, salt okunur dört zincir kaydı |
| `calculation.py` | Giriş doğrulama, nominal boyut/yük ve yaklaşık montaj hesabı |
| `geometry.py` | Analitik daire yayları, teğet yanaklar, kontur ve makara giriş/çıkış taraması |
| `cad.py` | Gerçek OCCT daire kenarları, prizma, isteğe bağlı göbek ve boydan boya delik |
| `export.py` | STEP/DXF yeniden okuma, doğrulama ve atomik dosya yayını |
| `serialization.py` | Ayrı ve sıkı `gokworks.chain_sprocket` v1 / mm JSON |
| `worker.py` | Ortak `service.execute` / `--gear-worker` içinde check, mesh, DXF, STEP |
| `view.py` | Ortak Qt kanvasında iki ayrı dişli, referans güzergâh ve statik makara konumları |
| `ui.py` | `FamilyPanel` alt sınıfı; aynı `GearWorkspace`, katalog/montaj/JSON/CAD kontrolleri |

`SprocketSpecification`: zincir kimliği ve ölçüleri, diş sayısı, diş genişliği,
delik, isteğe bağlı göbek çapı/toplam boyu, açıklama niteliğinde malzeme ve profil
referansı içerir. `SprocketPairSpecification` iki tekli modeli, tek bir yük
girdisini ve montaj modunu taşır. Eski `MechanismSpecification` alanları değişmedi;
eski iki v1 şema aynen okunur. Zincir verileri eski mekanizma v1 içine sıkıştırılmaz.
Eski mekanizma modeliyle `kind=chain_sprocket` gönderilmesi açıkça reddedilir.

```python
from modules.gear_calculator.sprockets import SprocketPairSpecification, calculate
from modules.gear_calculator import service
from modules.gear_calculator.serialization import to_dict, from_dict

s = SprocketPairSpecification()  # 08B-1; 20/40 diş; C giriş=300 mm; genişlikler 7 mm
r = calculate(s)
assert abs(r.chain_speed_m_s - 6.35) < 1e-12
assert from_dict(to_dict(s)) == s
service.execute(s, 'step', path='chain-pair.step', target='pair')
```

Şema: `schema=gokworks.chain_sprocket`, `version=1`, `units=mm`.
`driver`, `driven`, `mounting_mode`, `center_distance_mm`, `link_count`, `load`
alanları zorunludur; iç nesneler de dataclass alanlarıyla tam eşleşir. Bilinmeyen,
eksik alan, farklı birim/sürüm ve çelişkili birincil girdiler reddedilir.
`material` ve yükün mevcut faktör/ömür alanları saklanır; dayanım hesabı yapılmaz.
GUI JSON açma/kaydetmeyi destekler, 32 kB dosya sınırı uygular.

## Hesaplar ve birimler

mm, derece, kW, dev/dak, N·m, N ve m/s kullanılır. İç trigonometrik açılar radyandır.

- Bölüm çapı `Dp=p/sin(π/z)`; bölüm yarıçapı Dp/2; diş adımı 360°/z.
- Nominal dip referansı `Df_nom=Dp-dᵣ`. Gerçek çizilen profilin dip çapı,
  oturma boşluğu nedeniyle `Df_profile=Dp-2rᵢ`dir; sonuç tablosunda ikisi ayrıdır.
- Açık zincirde `i=z₂/z₁`, `n₂=n₁/i`: dönüş yönü aynıdır.
- Ortalama zincir hızı `v=p z₁ |n₁|/60000` m/s.
- `T₁=60000P/(2π|n₁|)`; alternatif tork girdisinden P ters bağıntıyla bulunur.
- `Ft=1000P/v` nominal etkin kuvvet farkıdır. Gergin ve gevşek kol gerilmelerini
  ayrı ayrı vermez; poligonal aktarımda anlık `T/r` kuvveti olarak sunulmaz.
- `T₂=T₁ i` ideal, kayıpsız çıkış torkudur.

08B-1 / 20–40 / 1500 dev/dak / 1,5 kW referansı:
Dp₁=81,184155913 mm, Dp₂=161,867784508 mm, nominal Df₁=72,674155913 mm;
n₂=750 dev/dak, v=6,35 m/s, Ft=236,220472441 N, T₁=9,549296586 N·m.

## Zincir uzunluğu ve montaj

`x=C/p`, `L≈2x+(z₁+z₂)/2+(z₂-z₁)²/(4π²x)` kullanılır. Bu **yaklaşık** açık zincir
bağıntısıdır; tam bir ayrık bakla/temas çözücüsü değildir.

- `mounting_mode=center`: C girilir, `link_count=None`. L bir sonraki çift tam
  baklaya yuvarlanır; aynı yaklaşık bağıntının fiziksel büyük kökü 80 adımlık
  bisection ile yeniden çözülür.
- `mounting_mode=links`: tam bakla sayısı girilir, `center_distance_mm=None`.
  Sayı değiştirilmez; tek sayı için offset bağlantı uyarısı çıkar.
- Tabloda giriş C, teorik L, seçilen bakla, düzeltilmiş yaklaşık C, L·p uzunluğu
  ve sürekli bölüm dairesi teğetlerinden küçük/büyük sarılma açıları bulunur.
- Varsayılan 300 mm için L≈77,673020832 adım → 78 bakla, C≈302,095208055 mm,
  uzunluk 990,6 mm'dir. CAD ve görünüm bu **düzeltilmiş** C'yi kullanır.

Gergi, montaj/uzama payı ve zincir sehim hesabı yoktur. 30–50 adımlık merkez
mesafesi dışındaki durumlar ve düşük diş sayısı tavsiye uyarılarıdır; dayanım
veya uygunluk kararı değildir. Sabit küçük/büyük isimleri tahrik yönüyle karışmaz:
sarılma sonuçları gerçek çap sırasına göre hesaplanır.

## Diş profili

Profil kimliği `iso606_public_arcs_v1`. Yayınlanmış ISO tipi dairesel oturma/yanak
geometrisine dayanan **nominal düzlemsel** profildir; tam ISO 606:2015 imalat
sertifikası veya belirli bir üreticinin kesici/ürün modeli değildir.

Seçilen değerler: `rᵢ=0,505dᵣ`, oturma yayı açısı `130°−90°/z`,
yanak radyüsü `rₑ=0,12dᵣ(z+2)`. Oturma daire merkezleri bölüm dairesinde,
aralarındaki kiriş tam p'dir. Her oturma yayının ucunda dıştan teğet bir
yanak dairesi kurulur; diş üstü dairesiyle analitik kesişim hesaplanır.
Karşı yanak simetriyle elde edilir. Bir adım dört daire yayı içerir ve z kez döner.
Oturma/yanak bağlantısı G1 teğettir; diş tepesi dış çapa kırpılmış yaydır.
Evolvent, üçgen diş, sinüs veya görsel çokgen kullanılmaz.

Diş üstü dairesi için yayımlanan alt sınır
`Do=Dp+(1−1,6/z)p−dᵣ` seçilir; üst referans `Dp+1,25p−dᵣ`dir.
Gerçek en büyük profil yarıçapı Do/2'dir. Tsubaki'nin
`p(0,6+cot(π/z))` bağıntısı JIS S/U ailesi bağlamındadır; ISO için evrensel dış
çap olarak kullanılmaz. Bu yüzden farklı katalog ürünlerinin dış çaplarıyla
birebir eşitlik iddia edilmez. Nominal ve boşluk içeren dip çapları karıştırılmaz.

Kontur birleşimleri, kapalı/pozitif ve kendini kesmeyen alan, delik eti, her
makaranın statik yerleşimi ve bir komşu baklanın giriş/çıkışında 65 örnekte
yaylara tam uzaklık kontrol edilir. Sağ/sol simetri ve açısal tekrar kullanılır.
Örneklenmiş tarama sürekli dinamik temas ispatı değildir. Testlerde bağımsız
Shapely makara diskleriyle de kesişim kontrolü yapılır.

## Görünüm ve CAD

Geniş ekranda mevcut üç kolon, dar alanda üç ana sekme korunur. Modül/basınç
açısı yerine zincir kataloğu, p/dᵣ/b₁, diş sayıları, genişlik/delik/göbek ve montaj
girdileri bulunur. İki parça seçimi CAD hedefini günceller. Türe dönünce girdiler
korunur; geçersiz düzenlemede eski CAD/görüntü sonuçları temizlenir.

Animasyon `θ₂=θ₁ z₁/z₂` ortalama kinematiğidir. Poligonal etki, makaralı zincirin
gerçek hareketi ve gergin/gevşek kol fiziği çözülmez. Kesikli güzergâh sürekli
bölüm dairesi referansıdır; statik makara işaretleri hareket başlatılınca gizlenir,
yalnız sıfır konumuna dönünce yeniden görünür.

STEP: gerçek OCCT daire kenarları → kapalı yüzey → diş genişliğinde prizma.
İsteğe bağlı göbek aynı gövdede birleşir, delik bütün göbekten geçer. Göbek boyu
**toplam** boydur. Tekli hedef kendi merkezinde; takım iki ayrı katı olarak C
aralığında +X ekseninde yerleşir. **Zincir dosyada yoktur.**

DXF R2010/mm: tam daire yaylarını koruyan kapalı bulge polylinelar kullanılır.
Katmanlar `SPROCKET_PROFILE`, `BORE`, `PITCH_CIRCLE`, `ROLLER_CENTERS`, `CONSTRUCTION`.
Yardımcı daire/merkezler ayrı katmandadır ve isteğe bağlıdır; parça merkez noktası
CONSTRUCTION'da kalır. Göbek, istenirse yalnız yardımcı merkez dairesi olarak
görünür; DXF dişli plakasının z=0 kesitidir.

STEP geri okunarak geçerli katı, gövde sayısı, pozitif hacim ve sınır koordinatları
karşılaştırılır. DXF geri okunarak birim, kapalı kontur ve kendini kesmeme kontrol
edilir. 3D ağ aynı B-Rep'ten türetilir. STL'den STEP oluşturulmaz.
Mevcut 120 saniyelik (en çok 300 s) iptal edilebilir `service.execute` kullanılır;
dosyalar geçici klasörde doğrulanıp atomik yayımlanır. API'de varsayılan
`overwrite=False`; GUI açık onay olmadan mevcut dosyayı değiştirmez.

## Giriş/kaynak sınırları

9–120 tam diş; en çok 2000 bakla; C en çok 10000 mm. Diş genişliği
0,5 mm ile üretici geometrik genişlik önerisi arasında (`0,93b₁` p≤12,7 mm;
`0,95b₁` daha büyük p). Delik 0 (dolu) veya ≥1 mm; dip altında en az
max(1 mm; 0,05p) geometrik et kalır. Göbek diş dibinin altında aynı eti bırakır,
boyu plaka genişliği–500 mm arasındadır. Zarf çapları arasında en az 1 mm
mesafe aranır. Bu alt sınırlar kaynak/geometri korumalarıdır; mukavemet veya
standart imalat toleransı olarak yorumlanmaz.

## Doğrulama ve çalıştırma

Mevcut `requirements-dev.txt` yeterlidir; yeni paket eklenmedi.

```sh
python main.py
QT_QPA_PLATFORM=offscreen python -m pytest -q modules/gear_calculator/tests/test_sprockets*.py
QT_QPA_PLATFORM=offscreen python -m pytest -q modules/gear_calculator/tests
QT_QPA_PLATFORM=offscreen python main.py --self-check /tmp/gokworks-smoke.json
```

Testler referans hesabı, dört katalog, negatif devir/güç/tork, bağımsız ikinci
derece denklemle montaj kontrolü, tek/çift bakla, invalid girdiler, yay teğetliği,
makara giriş/çıkışı, gerçek DXF/STEP, göbek/delik hacimleri, worker
iptal/zaman aşımı, üç şema uyumluluğu ve yerel Qt ekranını kapsar. Paket self-check
de zincir çifti STEP ve tekli DXF işlemini gerçek alt süreçte yürütür.

Yerel doğrulama: dişli ve ilgili entegrasyon/yapı paketinde 267 test başarılı;
son yarıçap/arayüz düzenlemesinden sonra hesap/arayüz paketindeki 69 test ve
gerçek 3D kareyi bekleyen ek UI kontrolü başarılı. 16 modüllük kaynak açılış
kontrolü geçti. Tüm uygulamanın test paketi çalıştırılmadı.
[Sayısal kayıt](../../../docs/test-results/sprockets-validation.json) ·
[2D ekran](../../../docs/screenshots/chain-sprocket.png) ·
[Gerçek katı 3D ekran](../../../docs/screenshots/chain-sprocket-3d.png).
3D örnekte tahrik göbeği Ø30 / toplam boy 20 mm; 2D örnekte göbek yoktur.

## Kaynaklar ve lisans

- [Tsubaki BS/DIN GT4 Winner](https://tsubaki.eu/products/chain/drive-chain/standard-roller-chain/bs-din-gt4-winner/):
  dört tek sıra kaydının p/dᵣ/b₁ ölçüleri; 28 Ekim 2026'da kontrol edildi.
- [Autodesk: Roller-chain geometry](https://help.autodesk.com/cloudhelp/2026/ENU/Inventor-Help/files/GUID-DCB5BD38-6092-4ADA-86E0-8D1B3DBC74F6.htm):
  ISO minimum/maksimum diş boşluğu yaklaşımı, teğet oturma ve gerçek Df=Dp−2rᵢ ayrımı.
- [HZPT Euro sprocket catalogue](https://www.hzpt.com/Eurospkt.pdf), sayfa 1:
  ISO/DIN profil çap aralığı, oturma/yanak ve genişlik bağıntıları.
- [Algotopia: OCCT sprocket construction](https://www.algotopia.com/contents/opencascade/opencascade_sprocket):
  aynı kamuya açık oturma/yanak boyutlarının bağımsız teknik karşılaştırması.
  Kaynak kod alınmadı; daire kesişimi/teğetlik çözümü bu modülde bağımsız yazıldı.
- [Tsubaki sprocket dimensions](https://en.tt-net.tsubakimoto.co.jp/tecs/engd/spr/engd_spr_sun_spcd.asp?lang=jp):
  bölüm/dip ve JIS S/U profili bağlamındaki dış çap ayrımı.
- [Tsubaki selection formulae](https://tt-net.tsubakimoto.co.jp/tecs/engd/cdc/engd_cdc_sen_ksn.asp?lang=en):
  yaklaşık L/C hesabı, tek bakla/offset ve çift bakla seçimi.
- [Renold transmission catalogue](https://www.renold.com/media/4092276/transmission-chain-catalogue-renold-uk.pdf),
  merkez mesafesi önerisi ve montaj kısıtları.
- [ISO 606:2015 kapsamı](https://www.iso.org/standard/61232.html):
  tolerans, deney, dayanım ve imalat koşullarının bu nominal modülün ötesinde olduğu kapsam.

Standart tabloları, katalog çizimleri ve üçüncü taraf kaynak kodu projeye
kopyalanmadı. Yeni çalışma zamanı bağımlılığı/lisansı yoktur; mevcut Qt, OCCT,
ezdxf ve Shapely bildirimleri geçerlidir. Kamuya açık profil karşılaştırmaları
2015 baskısının bütün maddelerinin doğrulandığı anlamına gelmez.

## Eksikler ve sonraki aşama

Üretici kesicisiyle bağımsız ölçüm/CAD karşılaştırması, ISO toleransları ve yan
rölyef/pah; ardından ayrık zincir yerleşimi ve poligonal hareket çözümü önceliklidir.
Zincir gergisi, yük/ömür/yorulma/kopma/verim/yağlama hesabı yoktur. ANSI ve çok
sıralı seriler yalnız katalog eklenerek etkinleştirilmemeli; kendi profil ve
montaj doğrulamaları tamamlanmalıdır. Gerçek SOLIDWORKS import testi yapılmadı.
