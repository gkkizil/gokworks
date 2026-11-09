# Hidrolik Ünite Hesaplayıcı — hesap ve rapor altyapısı

Python 3.13 ile bağımsız çalışan HPU ön boyutlandırma motoru. Yeni bağımlılık
yoktur. Çekirdek Qt/CAD import etmez.

## Arayüz

GOKWORKS'te **Hesaplar → Hidrolik Ünite Hesaplayıcı** (`ui.py`, `HydraulicPage`).
Yedi sekme: Silindirler, Çevrim, Pompa ve motor, Hat ve yağ, Tank ve ısı,
Akümülatör, Sonuçlar ve rapor. Girdiler 300 ms sonra yalnız çekirdekle
hesaplanır; `InputError.field` ilgili alanı/hücreyi kırmızı işaretler, sonuçlar
ve rapor düğmeleri temizlenir. Proje `.gwhyd` olarak açılır/kaydedilir;
Excel/JSON arka plan işiyle, PDF ana iş parçacığında iptal edilebilir işle
yazılır. Arayüz testleri: `python -m pytest modules/hydraulic_unit/tests -q`.

## Çalıştırma

Repo kökünden, mevcut Python ortamıyla:

```sh
python -m modules.hydraulic_unit
python -m modules.hydraulic_unit examples/ornek_pres_unitesi.gwhyd --json sonuc.json --excel sonuc.xlsx
python -m modules.hydraulic_unit examples/ornek_pres_unitesi.gwhyd --pdf sonuc.pdf
python -m pytest tests/hydraulic_unit -q
```

Linux'ta ekran olmadan PDF/test için `QT_QPA_PLATFORM=offscreen` kullanılır.
Windows'ta bu değişken gerekmez. CLI'da `--save proje.gwhyd` proje kaydeder.
PDF'de üç statik basamak grafik otomatik oluşturulur. Excel kurulu Microsoft
Office gerektirmez. JSON ve Excel işlemleri Qt gerektirmez.

```python
from modules.hydraulic_unit.core import Project, calculate_project
from modules.hydraulic_unit.core.models import Cylinder, CylinderOperatingPoint
from modules.hydraulic_unit.core.cylinder import calculate_cylinder
from modules.hydraulic_unit.service import describe, calculate

project = Project()
result = calculate_project(project)
point = calculate_cylinder(Cylinder(), CylinderOperatingPoint())
metadata = describe()          # arayüz için SI alan şemaları ve nominal seriler
payload = calculate(project)  # JSON'a çevrilebilir sonuç ve formül açıklamaları
```

## Birimler ve veri akışı

Modellerde uzunluk m, alan m², basınç Pa (akümülatör girdisi gösterge),
kuvvet N, hacim m³, debi m³/s, açısal hız rad/s, güç W, sıcaklık K,
viskozite m²/s, pompa deplasmanı m³/dev ve zaman s kullanılır.
`units.convert` bar/MPa/psi, L/min/ABD gpm, mm/in, rpm, kW, °C ve diğer
desteklenen görüntüleme birimleri arasında dönüşüm yapar. `display_units`
yalnız sonuç tablosunu değiştirir; SI sonuçlarını değiştirmez.

Silindirler → ardışık faz ihtiyacı → hat kaybı → pompa/regülatör sınırı →
motor tepe/RMS → enerji bilançosu → tank/soğutucu. Akümülatör bağımsız bir
ön boyutlandırma hesabıdır; çevrimdeki pompa boyutunu kendiliğinden küçültmez.

Silindir ve faz kimlikleri ayrıdır. Her silindirin başlangıç konumu vardır;
hareketler konumu günceller, strok dışına çıkmak reddedilir. Başlangıç konumuna
dönmeyen çevrim ayrıca uyarılır. `speed` ve `duration` hareket fazında karşılıklı
dışlayıcıdır; bekleme/boşta fazında `speed=None`, `duration>0` gerekir.

## Mühendislik yöntemleri

- Alanlar πD²/4, π(D²−d²)/4; itme/çekme kuvveti η(pA−pkarşıAkarşı).
  Rejeneratif modelde odalar eş basınçlı, dış besleme debisi mil alanı × hızdır.
  Bu model ayrı karşı basınç veya geçici basınç farkı kabul etmez.
- İtme/çekme ters çap hesabı karşı basıncı içerir. Rejeneratif kuvvet için
  piston çapı değil gerekli **mil çapı** hesaplanır; nominal milin gövdeye
  uygunluğu ayrıca kontrol edilmelidir. Euler π²EI/(KL)², I=πd⁴/64;
  başlangıç bağlantı katsayıları 2, 1, 0.699, 0.5, hedef emniyet 3.5'tir.
  Boy L kullanıcı girdisidir; silindirin strokundan otomatik tahmin edilmez.
- Pompa Q=Vg·ω·ηv/(2π), M=Vg·Δp/(2πηhm), Pmil=pQ/(ηvηhm).
  Motorun elektriksel verimi ve şebeke gücü hesaplanmaz. 50 Hz kutup/devir
  seçenekleri yaklaşık katalog yönlendirmesidir; gerçek rpm ayrıca girilir.
- Motor adayı max(Prms, Ptepe/(1+aşırı yük)) üzerindeki nominal değerdir.
  RMS=√(ΣP²t/Σt). Üretici görev sınıfı/başlatma ve aşırı yük onayı değildir.
- Sabit pompada hareket debisi kapasiteden düşükse fazla debi emniyet valfine
  gider; basınçta beklemede tüm pompa debisi valfe gider. Bu, seçilmiş açıkça
  tanımlı kısılma senaryosudur; bütün devre mimarilerini temsil etmez.
  Boşta fazında kullanıcı `idle_pressure` değerinde tam debi tahliyesi kabul edilir.
- Değişken pompada basınç kompansatörü veya sabit **mil gücü** zarfı uygulanır.
  Kompansatörlü pompanın otomatik valf ayarı max(p ihtiyaç, p kompansatör) ×
  katsayıdır. Ayar pompa basınç sınırını aşarsa kritik uyarı üretilir.
- İhtiyaç karşılanmazsa hız otomatik azaltılmaz. `PhaseResult.feasible=False`,
  `cycle.demand_met=False` ve ısı sonucu `scenario_only` olur. Konumu kapalı
  olmayan çevrimin tekrarlı ısı hesabı da `scenario_only` olarak işaretlenir.
- Boru d=√(4Q/πv); Re=vd/ν; Darcy λ=64/Re (hortum seçeneği 75/Re),
  düzgün boruda Blasius λ=0.3164/Re^0.25. Re 2300–4000 geçişinde iki
  tahminin büyüğü kullanılır; 100000 üzeri Blasius dışı kabul edilir. Bu iki
  bölgede kayıp yaklaşık tahmindir ve uyarılır; pürüzlülük modeli yoktur.
  Σζ kullanıcı girdisidir; hazır dirsek/valf katalog katsayısı uydurulmaz.
- Seçili basınç hattı **valf-sonrası silindir hattıdır**. Çevrime bu hattın kaybı
  eklenir. Ortak tank dönüşü silindir dönüşüne ek olarak valf/by-pass fazla
  debisini içerir. Diğer bütün hat/valf kayıplarının çözüldüğü iddia edilmez.
- Yağ eğrisi Walther iki noktalı ν40/ν100 yaklaşımıdır: log(log(νcSt+0.7))
  sıcaklık logaritmasıyla doğrusaldır. Buradaki basitleştirme ν>2 cSt içindir.
  40–100 °C dışı ekstrapolasyon uyarılır. ISO VG sınıfı tek başına eğri değildir;
  örnek 32/46/68 eğrileri üretici ürünü olarak sunulmaz.
- Kayıp enerji Σ(Pmil−Fv)t, tank ortalaması E/Σt; kayıplar tekrar eklenmez.
  Tank hacmi Q × kalma süresi (sabit 180–300 s, mobil 60–120 s ön aralığı).
  Kullanılabilir hacim dış ölçü hacmi × doluluktur; üst ve dört yan yüz açık,
  alt kapalı kabul edilir. Soğutucu=max(0, Pkayıp−kAΔT). Yüksek denge
  sıcaklığı doğrusal modelin ekstrapolasyonudur; gerçek çalışma sıcaklığı garantisi değildir.
- Akümülatörde gaz basınçları mutlaktır. Varsayılan p0=0.9p1 **mutlak**,
  V0=ΔV/[(p0/p1)^(1/n)−(p0/p2)^(1/n)]. Seçilen akümülatör çevrim kontrolü,
  gaz permeasyonu veya emniyet donanımı hesabı değildir.

## Kaynak ve kapsam sınırları

Formüller hidrostatik/süreklilik, klasik Euler kolon ve Darcy–Weisbach
bağıntılarına dayanır. İlgili teknik referans başlıkları: ISO 3320 (silindir
boyut serileri), ISO 3448 (viskozite sınıfları), ASTM D341 (yağ viskozitesi),
IEC 60034-1 (motor görev/ısıl sınıflar), ISO 4413 (hidrolik sistem güvenliği).
Bu standartların tam metinleri projeye alınmadı ve tam uygunluk onayı verilmez.
Nominal çap/güç/hacim serileri kullanıcı görev tanımından gelir; basınç ve
verim varsayımları üretici eğrisi değildir. Bosch Rexroth el kitabından doğrulanmamış
tablo veya ürün verisi aktarılmadı. Varsayımlar ve kaynak durumu her raporda bulunur.

Henüz değerlendirilmeyenler: eşzamanlı hareket, sürükleyen yük, transient/servo
cevabı, motor kalkışı/görev sınıfı, tam devre valf modeli, NPSH/kavitasyon onayı,
boru et kalınlığı/basınç dayanımı, gerçek ürün seçimi, termal geçici rejim,
akümülatörün çevrime enerji desteği ve CAD. Euler için plastik burkulma ve
komple silindir üretici stabilite modeli de kapsam dışıdır.

## Doğrulama ve entegrasyon

Referans testleri: 16 cm³/dev ×1450 rpm ×0.95 =22.04 L/min;
160 bar ×22 L/min / (600×0.85)=6.9019608 kW →7.5 kW;
22 L/min ve 4 m/s için d=10.803408 mm; D63 ve 160 bar, η=1 için
F=49.875925 kN. Testler ayrıca bağımsız Poiseuille, Euler ve Boyle
limitlerini, kütle/enerji dengelerini, strok sürekliliğini, regülatör sınırlarını,
JSON/Excel geri okumayı, PDF metnini ve iptal sırasında dosya korumasını denetler.

Claude entegrasyonu için [CLAUDE_HANDOFF.md](CLAUDE_HANDOFF.md) kullanılmalıdır.
`feasible` yalnız hesapta kritik uyarı olmamasıdır; imalat/üretici onayı değildir.

## Ekranda ilerleme

İlk kullanımda **Kolay kullanım** görünümü açılır. Teknik bilgi gerektiren
ayarlarla başlamadan **Ölçüler → Hareketler → Sonuç ve rapor** adımlarını izleyin.
Ölçü çizimi piston/mil/strok farkını gösterir. Hareketlerde mesafe, süre ve
kuvvet girilir; süreyle tanımlanan hareketin hızı çekirdekte hesaplanır.
Kuvvet kN veya ton-kuvvet olarak gösterilebilir; ton-kuvvet kütle değildir.

Sonuçlar motor, pompa debisi, basınç, hat iç çapı, tank ve soğutma ihtiyacını
günlük dilde açıklar. Kritik uyarılar bu görünümde de gösterilir. İleri–bekle–geri
örneği geri alınabilir; pompa önerisi yalnız açık düğmeyle uygulanır.
Mevcut pompa verimi, yağ, tank ve emniyet ayarları sessizce değiştirilmez.

**Ayrıntılı ayarlar** seçeneği mevcut yedi sekmeli ekranı açar. Görünümler
arasında proje ve bağımsız silindir kontrolü değerleri korunur. Birden fazla
silindir veya 12'den fazla faz içeren dosyalar veri kaybı olmaması için
ayrıntılı görünümde açılır. Geçersiz sayı yazılıyken görünüm değişimi girdiyi
silmez; önce o alanın düzeltilmesini ister.

### Ayrıntılı görünüm

Sekmelerin üstündeki adım açıklamalarını izleyin. Önce silindir ölçülerini,
sonra çevrim hareketlerini girin. Hız veya süre girişini seçili fazın üstündeki
menüden seçebilirsiniz. Gelişmiş ayarlar değerlerini koruyarak açılıp kapanır.
Motor, valf ve boru çapı için “Otomatik” alanını boş bırakın. Sağdaki uyarıya
veya “İlgili ayara git” düğmesine tıklayarak düzeltilecek bölümü açın.
Akümülatör kullanmıyorsanız kapalı bırakabilirsiniz.

[Ekran kontrolleri ve değişiklikler](USABILITY.md).
