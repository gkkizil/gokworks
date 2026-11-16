# Formül doğrulaması — 16 Kasım 2026

İncelenen hesaplarda iki sınır hatası düzeltildi: akümülatör hacmindeki sayısal
hassasiyet kaybı ve köşebent alan formülünün geometrik geçerlilik sınırları.
**1.581 farklı test ve 237 alt kontrol başarılı; son doğrulama gruplarında hata
ve atlanan test yok.** Test sayısına, bir testin içinde dolaşılan binlerce
parametre ayrıca eklenmedi.

Başlangıç kaynak revizyonu: `c724bae8fa05e9fd0773eb16b54ffac140e3f0c3`, dal:
`agent/codex`. Ortam: Linux, Python 3.12, pytest 9.0.2, Qt offscreen,
Shapely 2.1.2. Kaynaklara erişim tarihi: 16 Kasım 2026, Europe/Istanbul.

## Düzeltilen hatalar

### Akümülatör: yakın basınçlarda iki hacmin çıkarılması

İdeal politropik modelde `p Vⁿ = sabit`; tüm gaz basınçları mutlak alınır.
Teslim edilen yağ hacmi iki gaz durumunun farkıdır. Bu temel bağıntı
[HYDAC, Sizing Accumulators, basılı s. 94](https://betterfit-us.hydac.com/wp-content/uploads/AOSS-%20accumulators.pdf)
ile uyumludur.

Önceki ifade:

```text
V₀ = ΔV / [(p₀/p₁)^(1/n) − (p₀/p₂)^(1/n)]
```

`p₂` ile `p₁` çok yakın olduğunda iki yaklaşık eşit sayı çıkarılıyor,
basınç aralığının taşıdığı hassasiyet kayboluyordu. Aynı denklem şimdi:

```text
x = (p₂ − p₁) / p₁
V₀ = ΔV / [(p₀/p₁)^(1/n) × −expm1(−log1p(x)/n)]
```

Göstergede `p₁=10⁷ Pa`, `p₀=8×10⁶ Pa`, atmosfer `101325 Pa`, `n=1,4`,
`ΔV=0,001 m³` için:

| Basınç artışı | Önceki bağıl hata | Düzeltilmiş bağıl hata |
| --- | ---: | ---: |
| Yaklaşık 0,001 Pa | 3,55×10⁻⁷ | Çift duyarlıkta referansla aynı |
| 10⁷ Pa'nın bir sonraki temsil edilebilir değeri | %1,34 | 2,22×10⁻¹⁶ |

Bunlar sayısal sınır örnekleridir; olağan bir tesisin basınç çözünürlüğünü veya
pratik bir akümülatör kapasitesini temsil etmez. Referans, 70 basamaklı Decimal
aritmetiğiyle iki gaz durumu ayrı çözülerek hesaplandı. `n=1 / 1,1 / 1,4` ve
dört basınç aralığı için 12 regresyon testi eklendi.

Değişiklik: `modules/hydraulic_unit/core/accumulator.py`.

### Köşebent: kesite sığmayan kök ve uç yarıçapları

Mevcut alan modeli `r₂=r₁/2` kabul ediyor. Çeyrek dairelerden oluşan bu modelin
geçerli olması için `r₂ ≤ t` ve `r₁+r₂ ≤ min(b,h)−t` gerekir. Önceden yalnız
kök yarıçapı tek başına kontrol ediliyordu.

Örneğin `50×50×2 mm`, `r₁=15 mm` girişinde uç yayı 2 mm kalınlığa sığmadığı
halde `220,143 mm²` sonuç üretiliyordu. `b=10, h=50, t=5, r₁=5 mm` girişinde
ise kök ve uç yayları aynı kenarda çakışıyordu. İki durum da artık hata verir.

Geçerli eşitlik sınırları korunur. Alan formülü, dikdörtgenlerden bağımsız
olarak eklenip çıkarılan dairesel bölgelerle karşılaştırıldı; geometri
referansının çokgenleştirme hatası için `10⁻⁵ mm²` mutlak tolerans kullanıldı.
Altı regresyon testi eklendi. Mevcut 175 standart profilin alan/kütle denetimi
de başarılıdır.

Değişiklik: `modules/weight/sections.py`. Arayüz ve fonksiyon imzaları değişmedi.

## İncelenen bağıntılar ve karşılaştırmalar

| Alan | Kontrol edilen hesap | Kanıt / kapsam |
| --- | --- | --- |
| Hidrolik silindir | `F=(pA−pᵦAᵦ)η`, `Q=Av`, rejenerasyonda etkin alanın mil alanı olması, ters çap hesabı | Karşı basınç, hacim korunumu, ileri/geri ve rejeneratif hareket testleri |
| Pompa ve motor | `Q=Vg·ω·ηᵥ/(2π)`, `T=pVg/(2πηₘ)`, `P=pQ/(ηᵥηₘ)` | `Tω=P`, güç sınırı, çevrim işi ve RMS; [Parker P1/PD servis bağıntıları](https://www.parker.com/content/dam/Parker-com/Literature/Hydraulic-Pump-Division/P1---PD-Files/P1_PD-B-mod-Service-Manual.pdf) |
| Hidrolik birimler | Pa/bar/psi, m³/s/L/min/ABD gpm, mm/m ve rpm/rad/s | [Parker Basic Hydraulic Formulas, basılı s. 41](https://www.parker.com/content/dam/Parker-com/Literature/Accumulator---Cooler-Division---Americas/Catalogs---Bulletins/GAD-HY10-1630-5-2012/ACD_CoolerCatalog_HY10_1700.pdf): 300 psi düşüm ve 10 ABD gpm için yaklaşık 1305 W örneği bağımsız testte doğrulandı |
| Boru ve yağ | Darcy basınç kaybı, laminer `64/Re`, Blasius, Walther viskozite interpolasyonu | Hagen–Poiseuille bağımsız çözümü, viskozite uç değerleri; [NIST laminer/türbülanslı bağıntı ve geçerlilik aralıkları](https://nehrpsearch.nist.gov/static/files/NSF/PB2009105545.pdf) |
| Tank ve ısı | Çevrimde enerji/dönüş debisi, `Q·bekleme süresi`, `ısı/(kA)`, soğutma farkı | Süre ağırlıklı enerji ve yüzey alanı denetimi; tankta taban hariç üst ve yan yüzeyler kullanılıyor |
| Burkulma | Euler `π²EI/(KL)²`, dairesel mil `I=πd⁴/64` | Mesnet katsayıları ve bağımsız kolon hesabı; elastik kolon modeli |
| Cıvata | Çekme alanı, diş kökü/gövde kesmesi, `√(σ²+3τ²)`, adet ve güvenlik payı | Elle hesap, birleşik yük sınırı, birim dönüşümleri ve bir eksik cıvatanın yetersizliği |
| Sıkma torku | `T=KFd`, çapın mm'den metreye çevrilmesi, ön yük | M10 örneği; [NASA Fastener Design Manual, alternatif tork bağıntısı](https://ntrs.nasa.gov/api/citations/19900009424/downloads/19900009424.pdf) |
| Kayış-kasnak | İdeal hız/oran, açısal güç, dış ortak teğetlerden tam kayış boyu ve ters eksen mesafesi | 60 basamaklı referans, ayrı geometrik kurulum, profil ve sarılma testleri |
| Kayış adedi | Düzeltilmiş kayış gücü, servis katsayısı ve yeterli ortak kanal adedine yukarı seçim | Tosyalı kasnak çiftleri / mevcut Optibelt 2018 referans veri testleri; [Autodesk üretici düzeltme katsayılarının anlamı](https://help.autodesk.com/cloudhelp/2024/ENU/Inventor-Help/files/GUID-3DB83F43-A865-4DD4-AE34-1860CFE68F79.htm) |
| Dişli ve zincir | Bölüm/temel/tepe/kök çapları, merkez, kuvvet/tork, helisel dönüşümler, planet Willis ilişkisi, zincir adımı | 9.408 dişli parametre birleşimi 60 basamaklı bağımsız referansla; [KHK tablo 4.1](https://khkgears.net/new/gear_knowledge/gear_technical_reference/calculation_gear_dimensions.html) örneğinde `m=3, z=12/24`: merkez 54, bölüm 36/72, tepe 42/78, kök 28,5/64,5 mm |
| Büküm ve K | `BA=θ(R+Kt)`, dış geri çekilme, BD ve ölçümden K | [SOLIDWORKS K-Factor tanımı](https://help.solidworks.com/2013/english/SolidWorks/sldworks/c_K_Factor.htm): açı malzemenin düz halden dönüş açısıdır; 90°/R2/t2/K0,4 için BA 4,398229715 mm |
| Açınım ve geri esneme | Silindir/koni yüzeyleri, panel gerçek boyları, büküm bölgeleri, bilineer kesit momenti ve elastik boşalma | Alan/kenar korunumu, bağımsız gerilme integrasyonu, ölçülmüş tablo interpolasyonu, işaret ve birim testleri |
| Kesit ve kütle | Dolu/boş/yuvarlatılmış kesitler, `A·L·ρ/10⁹`, katalog kg/m, fire ve KDV | Tüm kesit türleri, mm/cm/m eşdeğerliği, 175 katalog satırı ve raporlar |
| ISO geçmeler | Tam sayı nm sapmaları, çap aralığı seçimi, boşluk/sıkılık limitleri | [SKF Cooper tablo 4](https://www.cooperbearings.com/ebrochure/UK_2022/14/): 50–400 mm aralığında yedi çap sınırında h6/h7/h9 için 21 bağımsız kaynak kontrolü |
| Tolerans zinciri | İşaretli en kötü durum, bağımsız terimlerin varyans toplamı, dar aralıklı kesilmiş normal dağılım | Decimal limitler, yüksek duyarlıklı integraller, Monte Carlo ve dağılım sınırları |
| Geometrik tolerans | Girilmiş toplam geometrik hatanın toleransla karşılaştırılması | Eşitlik, çap/radyal hata ve sınır testleri; modülün verilen toplam hatayı değerlendirme sözleşmesi |
| Nesting maliyeti | Net/brüt/fire alan-kütle, delikler ve kesim çevreleri, delme adedi, kuruş bazında maliyet dağılımı | Alan/kütle ve para toplamı korunumu; bunlar yerleşimin küresel optimum olduğunu kanıtlamaz |
| Profil kesim | Eksen doğrultusunda gerçek boy, `stok−2·baş kesme`, parça+kesim payı | Dönmüş profil geometrisi; 150 küçük kesim listesinde bağımsız tam arama ile çubuk adedi karşılaştırması |

## Doğrulama kayıtları

Çalıştırılan dosya listeleri ve grupların sonuçları
[`formula-audit-results.json`](formula-audit-results.json) içindedir.
Tekrar çalıştırmak için bu listeler `python -m pytest <test_paths...> -q` ile
kullanılabilir. Qt gerektiren örneklerde `QT_QPA_PLATFORM=offscreen` ayarlandı.

| Grup | Geçen test | Alt kontrol | Not |
| --- | ---: | ---: | --- |
| Mühendislik hesapları başlangıç taraması | 563 | 124 | Dişli/kayış/hidrolik/cıvata/K/kütle/ISO/zincir |
| Açınım ve şekillendirme | 891 | 0 | Hesap, profil, mekanik, entegrasyon ve kaynak geometrileri |
| Düzeltmeler ve etkilenen çekirdekler | 179 | 0 | İlk gruptan 161 tekrar; 18 yeni test |
| Ek hesap/rapor/geometri denetimleri | 87 | 113 | Tolerans dağılımı, GD&T, hidrolik adaptörler, kesim ve maliyet |
| Yeni üretici örnekleri | 22 | 0 | SKF 21 + Parker 1 |
| **Tekrarsız toplam** | **1581** | **237** | **40 yeni test** |

Düzeltme öncesinde yeni sınır testleri **13 hata / 5 başarılı** sonucu verdi;
aynı testler düzeltmeden sonra geçti. İlk komutta bulunmayan test dosyası
belirtildiği için koleksiyon başlamadı; dosya listesi düzeltilerek grup
çalıştırıldı. Başarısız girişim başarı sayısına katılmadı.

Yeni test dosyalarında Ruff, değişen Python dosyalarında derleme ve fatal
hata kontrolleri, ayrıca `git diff --check` başarılı. ezdxf/pyparsing kaynaklı
kullanımdan kaldırma uyarıları görüldü; test hatası değildi.

## Sonucun sınırları

Bu çalışma matematik, birimler, sayısal kararlılık ve belirtilen kaynak
örneklerini doğrular. Tüm ISO/EN/ASME standartlarının tam uygunluk denetimi
veya üretici ürün onayı değildir. SKF karşılaştırması seçilmiş 21 tablo
hücresini kapsar; bütün geçme sınıfları için bağımsız standart tablosu değildir.

K faktörü başlangıç önerileri, somun katsayısı, motor aşırı yük izni, ısı geçiş
katsayısı ve yağ verileri işletme/malzeme girdileridir. Kayışın tarihli referans
güç tablosu bütün markaların güncel kapasitesini doğrulamaz. Dişli geometrisi
ve nominal kuvvetlerin doğrulanması ISO 6336 yorulma hesabı yerine geçmez.
Akümülatör modeli ideal gaz kabul eder; HYDAC'ın gerçek gaz ve sıcaklık
düzeltmelerinin tümünü çözmez. Geri esneme modeli saf eğilme/elastik boşalma
tahminidir; temas, anizotropi veya incelmeyi çözen bir FEA modeli değildir.

Canlı Windows/SolidWorks oturumunda üretim doğrulaması ve tam uygulama test
paketi bu görevin kapsamında çalıştırılmadı. Değişen iki hesap çekirdeği
`origin/main` ile karşılaştırıldı; incelenen anda aynı dosyalarda örtüşen
Claude değişikliği yoktu. API, UI, CAD bağlantısı ve paketleme değişmedi.
