# Dişli türleri · kapsam ve teknik sözleşme

Eski `GearPairSpecification` / `gokworks.gear_pair` v1 aynen korunur.
`MechanismSpecification` ayrı, değişmez ve tipli veridir. Hesaplar Qt/OCCT
yüklemez; CAD mevcut yerel, iptal edilebilir 120 saniyelik alt süreçte çalışır.
Yeni bağımlılık/backend eklenmedi. `models.py` tür yeteneklerinin tek kaynağıdır.

## Ortak çalışma ekranı

Düz dişli ve katalogdaki diğer on tür aynı `../workspace.py::GearWorkspace`
yerleşimini kullanır. Solda türe özgü geometri ve birincil güç/tork girdileri,
ortada hareket araçları ile 2D/gerçek katı 3D sekmeleri, sağda özet, sonuç tablosu
ve CAD hedefi bulunur. 1100 pikselden dar çalışma alanında bu üç kolon
`Parametreler`, `Görünüm`, `Sonuçlar / CAD` sekmelerine dönüşür; genişletilince
girdiler ve sonuçlar korunarak kolonlar geri gelir.

Bölüm/temel daireleri, kremayer bölüm hattı ve sikloid pim dairesi gerçek
parametrelerden çizilir. Parça seçimi 2D vurgusunu ve CAD hedefini günceller;
planetler tek tek dışa aktarılmadığından planet seçimi takım hedefini kullanır.
DXF bölüm dairesi kutusu mevcut `construction` seçeneğine bağlanır ve yalnız
bu aktarımı destekleyen helisel, çift helisel, iç ve planet türlerinde açılır. Tür
değişiminde her türün parametreleri korunur. Hesap kapsamındaki türlerde aynı
kolonlar görünür; hareket/3D/CAD kapalı ve gerekçesi görünürdür. Bu yerleşim
değişikliği hesap denklemlerini, JSON şemalarını veya CAD geometrisini değiştirmez.

[Geniş ekran](../../../docs/screenshots/gear-workspace.png) ·
[Dar ekran](../../../docs/screenshots/gear-workspace-compact.png) ·
[Görsel kontrol raporu](../../../design-qa.md)

## Gerçek durum

| Tür | Hesap | 2D / rijit hareket | Gerçek katı 3D / STEP | DXF |
| --- | --- | --- | --- | --- |
| Kremayer–pinyon | Düz kremayer, hareket/kuvvet | Var; sonlu kremayerde bir adımlık döngü | İki ayrı delikli/dolu prizma | Kapalı kontur |
| Helisel çift | Normal/alın dönüşümü, kuvvet/kavrama | Alın kesiti | Ters elli kesitlerin düzgün loft'u | Yalnız z=0 alın kesiti |
| Çift helisel | İki simetrik yarı, ideal eksenel dengeleme | Alın kesiti | Ortada boşluksuz V, iki yarı birleşir | Yalnız z=0 alın kesiti |
| İç dişli–pinyon | 20°, standart sıfır kaydırma | Var, aynı dönüş yönü | Halka ve pinyon ayrı | Halka dış/iç sınırları ayrı |
| Planet | Sabit halka, güneş giriş, taşıyıcı çıkış | Var, tam Willis kinematiği | Güneş/halka/planetler ayrı; taşıyıcı yok | Tüm dişli konturları |
| Sikloid pimli | N pim / N−1 lob, ideal kinematik | Analitik pim zarfı | Delikli disk ve N ayrı silindirik pim | Disk ve pimler |
| Zincir dişlisi | ISO B tek sıra; p/dᵣ, yük ve yaklaşık L/C | Aynı yönlü ortalama kinematik; statik zincir referansı | İki ayrı dişli; opsiyonel göbek/delik; zincir yok | Tam daire yaylı kapalı kontur |
| Düz konik ayna–mahruti | Bölüm konileri, dış/orta mesafe, nominal dış üst çap | **Yok** | **Yok** | **Yok** |
| Spiral konik ayna–mahruti | Sıfır ofset bölüm konileri ve ideal kinematik | **Yok** | **Yok** | **Yok** |
| Hipoid ayna–mahruti | Yalnız diş oranı ve ideal güç/tork kinematiği | **Yok** | **Yok** | **Yok** |
| Sonsuz vida–çark | Eksenel modül, ilerleme, bölüm çapları/eksen mesafesi | **Yok** | **Yok** | **Yok** |

Son dört tür **tamamlanmış tasarım/CAD modülleri değildir**. Arayüz bunları
“hesap” etiketi ve ayrıntılı kapsam metniyle açar, CAD/hareket düğmelerini kapatır.
Bir konik blank'ı veya düz dişliyi spiral/hipoid diye sunan yedek yol yoktur.

Zincir dişlisi `CATALOG['chain_sprocket']` üzerinden aynı ekrana bağlanır, fakat
eski `MechanismSpecification` alanlarını kullanmaz. Ayrı `SprocketSpecification` /
`SprocketPairSpecification` ve `gokworks.chain_sprocket` v1 sözleşmesi vardır.
Eski iki v1 şema değişmedi. [Zincir mimarisi, denklemler, profil ve testler](../sprockets/README.md).

## Birimler ve denklemler

mm, derece, kW, dev/dak, N·m, N. Tek bir birincil güç/tork girdisi seçilir.
Giriş devri işaretlidir; kuvvet/tork sonuçları büyüklüktür. Yükler ideal ve
nominaldir; uygulama faktörü, ömür, malzeme ve verim dayanım hesabına dönüşmez.

- Helisel/çift helisel: `m=m_n`, `α=α_n`; `m_t=m_n/cosβ`,
  `α_t=atan(tanα_n/cosβ)`, `d=m_t z`. Baş/dip yükseklikleri **normal** modülden
  `m_n/1,25m_n` gelir. Yanaklar gerçek alın evolventidir. Her kesitte
  `Δθ=z_axial tanβ/r`; karşı eş ters ellidir. `Fr=Ft tanα_t`, `Fa=Ft tanβ`.
  `εβ=b sinβ/(πm_n)`. Çift helis için her yarının genişliği b/2 ve yükü Ft/2;
  eksenel kuvvetin net sıfır olması yalnız simetrik ideal yük varsayımıdır.
  Helisel alttan kesilme sınırı `z_min=2cosβ/sin²α_t` ile kontrol edilir.
- Kremayer: dairesel adım `πm`, bir pinyon turunda ilerleme `πmz`,
  doğrusal hız `πd n/60` mm/s. Düz yanaklar basınç açısıyla hesaplanır;
  bölüm hattındaki diş kalınlığı `πm/2`dir. Kremayer tabanı diş dibinin altında kalır.
- İç dişli: `a=m(z_r-z_p)/2`, `d_a=m(z_r-2)`, `d_f=m(z_r+2,5)`;
  pinyon ve halka aynı yönde döner. Diş boşluğu açısal yarı genişliği
  `π/(2z)+invα-invα_r`dir. 20° için iç uç temel daire üstünde,
  diş farkı >9 ve analitik evolvent girişim koşulu aranır. Takımla kesimde
  trimming/trokoid ve sökülebilirlik kontrolü tamamlanmadı; radyal imalat onayı yoktur.
- Planet: `z_r=z_s+2z_p`, eşit aralık için `(z_s+z_r)/N` tam sayı,
  komşular için `2a sin(π/N)>d_ap`. `n_c=n_s z_s/(z_s+z_r)`,
  `n_p=n_c-(n_s-n_c)z_s/z_p`; sabit halka. Planetlerin başlangıç fazları
  taşıyıcı açısına göre hesaplanır. Eşit yük paylaşımı/taşıyıcı dayanımı hesaplanmaz.
- Sikloid: pim dairesi `R=mN/2`, `p(u)=R exp(iu)-e exp(iNu)`.
  Disk konturu `p(u)-r_pin[-i p'(u)/|p'(u)|]` analitik iç ofset zarfıdır.
  `eN<R`, pimler arası açıklık ve disk deliği eti zorunludur. Oran N−1,
  disk devri `-n_in/(N−1)`; eksantrik merkez hareketi eşzamanlı uygulanır.
  Bu model episikloid saat dişlisi veya tamamlanmış ticari redüktör değildir;
  çıkış pimleri, rulmanlar, çift disk ve yük dağılımı yoktur.
- Düz konik: dış alın modülü; `δ1=atan2(sinΣ,z2/z1+cosΣ)`, `δ2=Σ-δ1`,
  `R=d1/(2sinδ1)`, genişlik ≤R/3, `d_ai=d_i+2mcosδi`.
  Spiral konik bu genel bölüm konilerini paylaşır; kesici sistemine bağlı
  diş üst/dip payları ve yüzeyleri bununla belirlenmez.
- Hipoid: modülden bölüm çapı veya düz konik formülüyle ofsetli yüzey çıkarılmaz.
  Gleason/Klingelnberg yöntemi, ofset/spiral açı/diş kalınlığı ve üretim parametreleri
  ile eşlenik yüzey çözücüsü ve bağımsız referans gerekir. Mevcut çıktı yalnız i=z2/z1.
- Sonsuz vida: `m=m_x`, `d1=q m_x`, `d2=z2 m_x`, `tanγ=z_starts/q`,
  ilerleme `πm_x z_starts`, `m_n=m_x cosγ`, `a=(d1+d2)/2`.
  ZA/ZN/ZI/ZK/ZH profil seçimi, kesici ve zarflanmış çark yüzeyi tamamlanmadı.
  Çıkış yönü eksen/sağ-sol ağız seçimine bağlıdır; burada yalnız devir büyüklüğü verilir.

## Eğri, katı ve doğrulama sınırları

Evolvent yanaklar önceki Bézier hata bütçesini (`min(0,001; m/2000)` mm) kullanır.
Düz geçişler kesici trokoidi olarak etiketlenmez. Sikloid eğri analitik zarfından
adaptif kübik Hermite segmentlerine yaklaşılır; çeyrek/orta noktalar hedef
toleransın dörtte biriyle ve her lobda en az sekiz segmentle sınanır. Bu sikloid
yaklaşımı için küresel analitik hata üst sınırı ispatı verilmemiştir.

Helisel katı üçgen ağdan yapılmaz: aynı profilden en çok 3° aralıklı, en az beş
kesit kullanılarak düzgün OCCT B-Rep loft üretilir. En fazla 81 kesit kabul edilir;
aşırı genişlik/açı için kaynak sınırı hatası verilir. Bu bir loft yaklaşımıdır;
doğrudan analitik helikoid yüzeyi veya imalat toleransı sertifikası değildir.
Hacim, sabit alın alanı × genişlikle bağımsız olarak karşılaştırılır.

İhracat öncesi bir tam diş adımı 48 konumda, planet/sikloid ise bir giriş turu
48 konumda çokgen kesişimiyle kontrol edilir. Alan toleransı `2e-5 m²` mm²'dir
(m sayısal modül). Bu örneklenmiş tarama yük altında sürekli temasın ispatı değildir.
STEP dosyası yeniden okunarak geçerli/pozitif hacim, gövde sayısı ve sınır
koordinatları karşılaştırılır. DXF R2010/mm kapalı profil, delik ve ayrı yardımcı
katmanlar içerir. Helisel DXF yalnız alın kesitidir; helis yüzeyi olarak kullanılamaz.

## API ve testler

```python
from modules.gear_calculator.families import MechanismSpecification, calculate
from modules.gear_calculator import service
s = MechanismSpecification(kind='helical', module_mm=2, helix_deg=20)
r = calculate(s)
service.execute(s, 'step', path='helical.step', target='pair')
```

Yeni JSON: `schema=gokworks.gear_mechanism`, `version=1`, `units=mm`;
alanlar dataclass alanlarıyla tam eşleşir, yük iç nesnedir. Bilinmeyen/eksik
alanlar ve farklı sürüm/birimler reddedilir. Eski v1 şeması otomatik dönüştürülmez.
`target=pinion/wheel/pair`; planet için ilk güneş, ikinci halka; sikloid için
ilk disk, ikinci pimler. Tekli parçalar kendi merkezinde; takım ortak koordinatta.

```sh
QT_QPA_PLATFORM=offscreen python -m pytest -q modules/gear_calculator/tests
```

Yeni testler: normal/alın referans ölçüleri, enerji korunumu, helis el/fazı,
orta V sürekliliği, Willis denklemi, kremayer stroku/hızı, iç dişli çap sırası,
analitik pim zarfının teğetliği, profil/kavraşma, gerçek STEP/DXF ve GUI/alt süreç.
Tüm testler mevcut bağımlılıklarla çalışır; gerçek SOLIDWORKS import testi yapılmadı.

## Araştırma ve lisanslar

- [KHK boyut hesapları](https://khkgears.net/new/gear_knowledge/gear_technical_reference/calculation_gear_dimensions.html):
  kremayer, iç dişli girişimleri, konik/sonsuz vida nominal boyutları.
- [DrivetrainHub helisel geometri](https://drivetrainhub.com/notebooks/gears/geometry/Chapter%203%20-%20Helical%20Gears.html):
  normal/alın ayrımı, ters el, kuvvet/kavrama ve alttan kesilme koşulları.
  m_n=1, α_n=20°, β=15°, z=17 için d=17,599695 mm / α_t=20,646896°
  sayısal referansı testte kullanılır; kaydırmalı örneğin yalnız kaydırmadan
  etkilenmeyen bölüm büyüklükleri karşılaştırılır.
- [DrivetrainHub planet geometrisi](https://drivetrainhub.com/notebooks/gears/geometry/Chapter%204%20-%20Planetary%20Gears.html):
  eşit planet montaj koşulu; kaynakta iç halka diş sayısı işaretlidir,
  uygulamadaki pozitif sayılara çevrildiğinde toplam koşulu elde edilir.
- [GWJ GearEngineer el kitabı](https://www.gwj.de/fileadmin/dokumente_web/gwj/GearEngineerHandb_en.pdf):
  spiral konik/hipoid ayrımı ve sıfır/sıfırdan farklı ofset.
- [py_gearworks](https://github.com/GarryBGoode/py_gearworks): Apache-2.0;
  helisel/konik/sikloid/iç dişli seçenekleri araştırıldı. Kendi belgelerinde
  hipoid ve sonsuz vida desteklenmiyor. build123d bağımlılığı mevcut OCCT8
  paketleme zincirine eklenmedi; kaynak kod kopyalanmadı.

Yeni üçüncü taraf kaynak/çalışma bağımlılığı yok. Önceki modülün Qt/OCCT/GEOS
lisans bildirimleri geçerlidir. Bu çalışma ISO 23509, ISO 10828 veya ISO 6336
uygunluk sertifikası değildir; kaynakların ilgili açık teknik bölümleri kullanıldı.

## Tamamlanması gerekenler

Öncelik eşlenik düz konik yüzey ve bağımsız CAD karşılaştırması; ardından üretim
yöntemi seçilmiş spiral konik/hipoid çözücü. Sonsuz vidada önce profil/kesici
seçimi ve zarflanmış çark, sonra yük/verim/ısıl kontroller. Tüm türlerde gerçek
kesici dibi, boşluk/tolerans ve dayanım kontrolleri ayrı doğrulama gerektirir.
