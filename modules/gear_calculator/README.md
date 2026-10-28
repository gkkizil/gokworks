# Dişli Hesaplama · GOKWORKS

Çevrimdışı dişli çalışma alanı. Varsayılan dış düz evolvent dişli çifti: hesap → gerçek eğri tanımı
→ 2D hareket / katıdan 3D önizleme → DXF / STEP aynı tip güvenli veriyi kullanır.
Menü: **Makine Elemanları → Dişli Hesaplama**. SOLIDWORKS kurulumu gerekmez.

Üstteki tür seçimi kremayer, helisel, çift helisel, iç dişli, planet ve pimli
sikloid hesap/2D/3D/DXF/STEP çalışma alanlarını açar. Konik, spiral konik,
hipoid ve sonsuz vida türleri henüz **yalnız sınırlı nominal hesap** sunar;
eşlenik CAD yüzeyleri tamamlanmadığından CAD/hareketleri kapalıdır.
Türlerin ayrı kapsamı ve kullanılan denklemler [families/README.md](families/README.md)
dosyasındadır. Türün menüde bulunması tüm mühendislik/CAD işlevlerinin tamamlandığı
anlamına gelmez. Aşağıdaki ilk API ve varsayımlar dış düz v1 çifti içindir.

## Mimari ve API

| Dosya | Görev |
| --- | --- |
| `models.py` | Değişmez `GearSpecification`, `GearPairSpecification`, `LoadSpecification`, sonuçlar ve ayrılmış ileri veri alanları |
| `calculation.py` | Saf, arayüzden bağımsız geometri / yük / kavrama oranı hesabı |
| `validation.py` | Sonlu sayılar, birimler, kaynak sınırları, modül/açı uyumu, delik eti, alttan kesilme ve kapsam |
| `geometry.py` | Analitik evolvent; hata sınırı belirli kübik Bézier yanaklar; gerçek daire yayları; kavraşma fazı / girişim taraması |
| `cad.py` | OCCT wire → delikli yüzey → prizmatik B-Rep katı; STEP yeniden okuma ve katıdan üçgenleme |
| `export.py` | Katmanlı DXF, gerçek STEP, yeniden okuma ve atomik dosya yayınlama |
| `serialization.py` | Sürümlü, alanları sıkı doğrulanan `gokworks.gear_pair` v1 / mm sözleşmesi |
| `worker.py`, `service.py` | Qt/COM yüklemeyen yerel CAD alt süreci; 120 s süre sınırı, durdurma, geçici dosyalar |
| `view.py`, `ui.py` | Ortak eğrilerin Qt çizimi, hareket, seçim, küçük ekran sekmeleri, sonuçlar ve aktarım |

`__init__.py` yalnız standart Python kitaplığına bağlı hesap API'sini sunar:

```python
from modules.gear_calculator import GearPairSpecification, calculate_pair
from modules.gear_calculator.export import export_cad

spec = GearPairSpecification()  # m=2, z1=20, z2=40, α=20°, b=15; delikler 8/12 mm
result = calculate_pair(spec)
assert abs(result.center_distance_mm - 60) < 1e-10
export_cad(spec, 'takim.step', target='pair')
export_cad(spec, 'pinyon.dxf', target='pinion', construction=True)
```

`target`: `pinion`, `wheel`, `pair`. Tekli parça kendi merkezinde ve diş merkezi
+X yönünde üretilir. Takımda pinyon (0,0,0), çark (a,0,0); genişlik +Z yönünde
0…b'dir. Ayrı iki katı gövde korunur. `overwrite=False` varsayılandır; mevcut dosya
sessizce ezilmez. GUI'nin kaydet diyaloğu dosya değiştirme onayını yönetir.

## Kapsam ve varsayımlar

- Metrik; mm, derece, kW, dev/dak, N·m, N. Basınç açısı varsayılan 20°.
- Dış düz silindirik dişli; paralel miller; standart merkez mesafesi; x₁=x₂=0,
  hₐ*=1, h𝒻*=1,25, β=0°, sıfır nominal diş boşluğu.
- Modül 0,1…20 mm; diş sayısı tam sayı 6…300; üst çap en çok 6000 mm;
  genişlik 0,1…500 mm; basınç açısı 14,5…30°. Bu sınırlar kaynak/geometri sınırıdır.
- Delik sıfır olabilir. Diş dibi altında en az max(0,2 mm; 0,1 m) radyal geometrik
  et bırakılır. Bu et kontrolü mukavemet onayı değildir.
- Birincil yük güç veya torktur. İkisinin aynı anda verilmesi reddedilir.
  Giriş devri işaretli olabilir; sıfır kabul edilmez. Tork ve kuvvetler büyüklüktür.
  Arayüz her iki birincil girişin son değerini ayrı saklar; yalnız seçili olan
  hesaba girer. Hesaplanan ikincil değer salt okunur gösterilir; giriş kutusunun
  sınırlarına kırpılmaz. Çok küçük/büyük sonuçlar bilimsel gösterim kullanır.
- `K_A` ve tasarım ömrü veri modelinde saklanabilir; nominal kuvvetlere uygulanmaz.
  ISO/AGMA dayanım ve ömür sonucu gösterilmez. İleri normal düzlem, malzeme,
  kalite, helis, profil kaydırma ve diş boşluğu alanlarının etkin kullanımı reddedilir.

## Hesaplanan büyüklükler

Her dişli için bölüm / üst / dip / temel çap ve yarıçapları, dairesel/temel adım,
nominal diş kalınlığı, baş/dip/toplam yükseklik ve dip boşluğu hesaplanır.
Çift için oran, standart/çalışma merkez mesafesi, ters işaretli çıkış devri,
ideal çıkış torku, nominal çevresel/radyal kuvvet ve temas yolu hesaplanır.

Güç dönüşümü yuvarlanmış 9550 yerine `60000/(2π)` kullanır. Dış düz çift için:

```
εα = [√(ra1²-rb1²) + √(ra2²-rb2²) - a sin(α)] / [π m cos(α)]
```

Yaklaşma ve uzaklaşma uzunluklarının temel dairenin izin verdiği aktif evolvent
sınırlarını aşması ayrıca uyarılır. εα<1 için sürekli kavraşma desteklenmez.
1≤εα<1,2 için düşük temas payı uyarısı gösterilir; bu öneri CAD'yi kapatmaz.
Bu kontrol imalat toleranslarının en kötü durum hesabı veya dayanım onayı değildir.

Referans: m=2, z₁=20, z₂=40, α=20°, b=15, P=1,5 kW, n₁=1500:
d₁/d₂=40/80; da₁/da₂=44/84; df₁/df₂=35/75 mm; a=60 mm; i=2;
n₂=-750 dev/dak; T₁=9,5492966 N·m; Ft=477,4648293 N; εα=1,635186.

## Eğri hassasiyeti, dip ve kavraşma

Yanaklar `x=rb(cos t+t sin t)`, `y=rb(sin t-t cos t)` evolventinden gelir.
Her yanağın bölüm dairesindeki kalınlığı πm/2 olacak şekilde açısal yerleşim
yapılır. Diş üstü ve dip kenarları gerçek daire yaylarıdır.

Analitik eğri CAD'de kübik Hermite/Bézier segmentleriyle yaklaşılır. Aralık h için
vektörel hata üst sınırı `h⁴ rb √(9+t_max²)/384` kullanılarak bölüm sayısı seçilir.
Hedef `min(0,001 mm, m/2000)`; ayrıca yoğun sayısal test yapılır. 2D çizim de aynı
Bézier segmentlerini kullanır. DXF bunları ek kiriş hatası
`min(0,005 mm, 0,0025 m)` ile kapalı poliline dönüştürür; iki hata bütçesi ayrıdır.
STL üçgenlerini STEP diye yeniden adlandırma veya mesh'ten katı türetme yoktur.

**Dip geçişi:** rf<rb ise radyal düz bağlantı kullanılır. Gerçek kesici trokoidi,
azdırma dip radyüsü veya alttan kesilmiş üretim profili modellenmez. Bu kontur
özellikle diş dibi yorulma/gerilme değerlendirmesine uygunluk iddiası taşımaz.

Alttan kesilme riski x=0 tam yükseklik için `z < 2/sin²α` ile değerlendirilir:
20° için sınır yaklaşık 17,097'dir. Riskli çiftlerde sayısal hesaplar ve uyarı
görülebilir, fakat CAD ve hareket kapatılır; uydurma bir imalat profili verilmez.
Gelecekte profil kaydırma eklendiğinde bu ölçüt yeniden ele alınmalıdır.

Faz: θ₁=θ, θ₂=π-π/z₂-θ·z₁/z₂. Çark boşluğu pinyon dişinin karşısındadır.
Bir tam diş adımı 48 konumda Shapely kesişim alanıyla taranır; örnekleme/eğri
hataları için alan sınırı `2e-5 m²` (buradaki m: sayısal modül, uzunluk mm) kullanılır.
Bu sayısal tarama, sürekli temasın matematiksel ispatı veya yük altında temas
analizi olarak sunulmaz. Analitik temas yolu kontrolleriyle birlikte kullanılır.

## Görünüm ve CAD

- 2D: pinyon/çark seçimi, yakınlaştırma, sürükleme, bölüm/temel daireleri,
  merkez mesafesi, başlat/duraklat/sıfırla. Gizlenen sayfada hareket durur.
- Hız yüzdesi gerçek giriş devrini ölçekler; varsayılan %2. Yüksek devirde
  ekran örneklemesi hareketi alias edebilir; daha düşük yüzde seçilebilir.
- 3D: statik gerçek delikli OCCT katısından üçgenleme. Mevcut Qt mesh görüntüleyici
  kullanılır; OpenGL çalışmazsa arka planda CPU/depth-buffer yolu vardır.
- DXF R2010/mm: kapalı dış kontur, gerçek delik, merkez; `GEAR_PROFILE`, `BORE`,
  `PITCH_CIRCLE`, `BASE_CIRCLE`, `CONSTRUCTION`. Yardımcılar üretim katmanına karışmaz.
- STEP AP214/mm: tekli veya iki ayrı katı; geçerlilik, pozitif hacim, gövde sayısı
  ve boyutlar dosya yeniden okunarak denetlenir.
- CAD yalnız komutla hesaplanır. Uzun iş yerel alt süreçte sınırlandırılır ve
  durdurulabilir. Hata/durdurma öncesi mevcut çıktı dosyası korunur.

## Kurulum ve test

Python 3.13 x64 Windows dağıtımı; Linux geliştirme/test için Python 3.12 kullanıldı.

```sh
python -m pip install -r requirements-dev.txt
python main.py
python -m modules.gear_calculator  # yalnız bağımsız dişli ekranı
python -m modules.gear_calculator --output takim.step --module 2 --z1 20 --z2 40
python -m pytest -q modules/gear_calculator/tests
# Linux CI/başsız Qt:
QT_QPA_PLATFORM=offscreen python -m pytest -q modules/gear_calculator/tests
```

Gerçek OCCT testleri atlanmaz: STEP yeniden okuma, delik içi/dışı nokta sınıflaması,
katı hacmi, B-Rep eğrileri ve üçgenleme sınanır. SOLIDWORKS gerekmez.
`windows-gears.yml` Python 3.13 üzerinde kaynak testlerini ve gerçek paketlenmiş
programın üç DPI ölçeğinde açılışını/CAD alt süreç aktarımını çalıştırır.
Eski Windows EXE yayınlama isteği bu modül eklenirken değiştirilmez.

Matematik denetimi: 9.408 parametre kombinasyonu, üretim hesabını çağırmayan
60 basamaklı Decimal referansı, üretici tablosu, temas/enerji/ölçek kontrolleri
ve analitik hacimle karşılaştırılan gerçek STEP dosyalarıyla sınanır.
Yöntem, kaynaklar, toleranslar ve bulunan düzeltmeler
[matematik doğrulama raporundadır](research/math-validation.md).
Parametriklik GOKWORKS verisi değiştiğinde hesap ve CAD'nin yeniden üretilmesidir;
STEP aktarımı SOLIDWORKS'e yerel bir parametrik unsur geçmişi sağlamaz.

## Bağımlılıklar ve lisanslar

Hesap API'si standart Python ile çalışır. Qt/PySide6 6.10.3 (LGPL-3), ezdxf 1.4.3
(MIT), Shapely 2.1.2 (BSD-3) / GEOS (LGPL-2.1) mevcut altyapıdır.
Yeni bağımlılık `cadquery-ocp-novtk==8.0.1.1.0` ve aynı sürümdeki proxy'dir.
Bağlayıcı Apache-2.0; OCCT 8.0.1 çekirdeği **LGPL-2.1 + OCCT istisnası**dır.
VTK/build123d/SciPy veya yeni backend servisi eklenmez. Çekirdek ağırdır;
CPython 3.13 Windows wheel'i yaklaşık 47,8 MB indirmedir, son paket büyür.

Tam metinler `packaging/licenses/gears/` altındadır; yerel görüntü kodekleri ve
ilgili bildirimler de korunur. Apache etiketi tüm DLL'leri Apache yapmaz.
FreeImage için FIPL, LibRaw için LGPL yolu belgelenir. Bunların ayrıca kaynak,
bildirim ve kitaplık değiştirme yükümlülükleri vardır; GPL ile karıştırılmaz.
Microsoft çalışma zamanı DLL'leri Microsoft yeniden dağıtım koşullarına tabidir.

`GOKWORKS_CAD_DIR`, uyumlu `OCP/`, `cadquery_ocp_proxy/` ve
`cadquery_ocp_novtk.libs/` içeren harici site-packages dizinini seçebilir.
Normal kullanıcı için zorunlu değildir; LGPL dinamik kitaplık değiştirme yoludur.
Kaynak/provenans bağlantıları [araştırma kaydında](research/README.md), lisans
metinlerinin kaynakları ve SHA256 değerleri [envanterdedir](research/native-notices.json).

## Sonraki fazlar

Önce gerçek kesici trokoidi ve bağımsız referans CAD karşılaştırması; ardından
profil kaydırma ve diş boşluğu; helisel geometride normal/alın düzlemi dönüşümleri.
Daha sonra doğrulanmış baskı/faktör/malzeme verileriyle ISO 6336/AGMA mukavemet;
planet/çok kademe ve teknik raporlar ayrı fazlardır. İç/konik/sonsuz vida, FEM,
verim, yağ filmi, yük dağılımı ve ömür bu MVP'de etkin değildir.
