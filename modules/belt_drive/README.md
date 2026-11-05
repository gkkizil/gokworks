# Belt Drive Designer — Matematik ve katalog altyapısı

GOKWORKS için arayüzden, SolidWorks'ten ve CAD çekirdeğinden bağımsız, iki
kasnaklı **açık kayış nominal hesap motoru**. Yalnız Python standart
kütüphanesini kullanır. Aşama 1 nominal motorunun üzerine otomatik tasarım,
yerel ürün katalogları ve beyan edilen tablo değerlendirmesi eklendi.
5 Kasım talimatı doğrultusunda GUI/menü geliştirilmedi. Çizim ekranı,
animasyon, STEP/DXF, PDF/Excel ve SolidWorks üretimi henüz eklenmedi.

Yeni backend kullanımına aşağıdaki **Otomatik tasarım** bölümünden;
kaynak, kapsam ve test kanıtlarına [AUTOMATIC_DESIGN_REPORT.md](AUTOMATIC_DESIGN_REPORT.md)
belgesinden ulaşabilirsiniz.

## Gerçekte desteklenenler

| Aile/profil | Hesap referansı | Kapsam |
| --- | --- | --- |
| Z, A, B, C, D | Datum çapı / datum uzunluğu | İdeal kinematik ve geometri |
| SPZ, SPA, SPB, SPC | Datum çapı / datum uzunluğu | İdeal kinematik ve geometri |
| HTD_3M, HTD_5M, HTD_8M | Diş sayısı ve 3/5/8 mm adım; bölüm çizgisi | İdeal kinematik, geometri, kesirli kavrama dişi tahmini |
| T5, T10, AT5, AT10 | Diş sayısı ve 5/10 mm adım; bölüm çizgisi | Aynı nominal hesaplar; profiller birbirinin yerine geçmez |
| GT2, GT3 | Tanımlanmadı | Nesil adı tek başına adım/ürün tanımlamaz; hesap reddedilir |
| PJ, PK, PL | Tanımlanmadı | Aşama 1'de desteklenmez |

Profil kaydı kanal ölçüsü, doğru diş boşluğu, üretici katalog uygunluğu veya
güç kapasitesi sağladığı anlamına gelmez. Bütün sonuçlarda
`power_capacity_verified=False`, `production_approved=False` ve
`cad_available=False` kalır. `geometry_valid=True` yalnız nominal referans
çizgisi geometrisinin oluştuğunu gösterir.

## Çalıştırma

Depo kökünden Python 3.13 ile:

```sh
python -m modules.belt_drive --example > reference.json
python -m modules.belt_drive reference.json
python -m modules.belt_drive modules/belt_drive/examples/timing_110.json --catalog modules/belt_drive/examples/dimension_list.example.json
python -m pytest -q modules/belt_drive/tests
```

Üçüncü komuttaki boyut listesi sentetiktir; gerçek üretici ürün listesi değildir.
Geçersiz proje, eksik dosya veya bozuk JSON için CLI hata iletisi ve çıkış
kodu 2 döndürür. Mevcut bir dosyayı kendiliğinden değiştirmez. `--example`
çıktısını PowerShell'de kaydederken UTF-8 kullanın:

```powershell
python -m modules.belt_drive --example | Out-File reference.json -Encoding utf8
python -m modules.belt_drive reference.json
```

Python API'si:

```python
from modules.belt_drive import calculate, BeltDriveSpecification

result = calculate(BeltDriveSpecification())
print(result.ratio, result.nominal_output_rpm)  # 2.0, 725.0
print(result.length_exact_mm)                  # 1277.4970744746527
for check in result.checks:
    print(check.severity, check.code, check.message)
```

Triger-senkron kayış ve belirli diş adedinden eksen mesafesi:

```python
from modules.belt_drive import (
    calculate, BeltDriveSpecification, BeltSpecification,
    PulleySpecification, LoadSpecification, CenterSpecification,
)

spec = BeltDriveSpecification(
    belt=BeltSpecification(family='timing', profile='HTD_5M'),
    driver=PulleySpecification(datum_diameter_mm=None, teeth=20),
    driven=PulleySpecification(datum_diameter_mm=None, teeth=40),
    load=LoadSpecification(input_rpm=1500., power_kw=1.5),
    center=CenterSpecification(mode='length', distance_mm=None, belt_teeth=110),
)
result = calculate(spec)  # Bölüm uzunluğu 550 mm; C sayısal olarak çözülür.
```

Güç ve torktan **yalnız biri** birincil giriş olabilir. Tork kullanırken
`LoadSpecification(power_kw=None, torque_nm=...)` verin. V kasnakta çap
datum çapıdır; triger-senkron kasnakta `datum_diameter_mm=None` ve tam diş sayısı
gerekir. Çap türleri otomatik dönüştürülmez.

## Hesap yöntemleri ve sınırlar

Birimler: çap/mesafe/uzunluk **mm**, güç **kW**, devir **dev/dak**, hız
**m/s**, tork **N·m**, kuvvet **N**. İç açılar radyan, kullanıcı sonuçları
derecedir. `D₁` sürücü, `D₂` sürülen referans çapıdır.

- `i=D₂/D₁`; triger-senkron kayışta doğrudan `i=z₂/z₁`, `Dₚ=z·p/π`.
- `n₂=n₁/i`; V kayışında kayma/sürünme bilinmediğinden yalnız ideal devirdir.
- `v=π·D₁·n₁/60000`.
- `T=60000·P/(2π·n)`; yuvarlatılmış 9550 katsayısı kullanılmaz.
- İdeal `T₂=T₁·i`. Verim **yalnız verilirse** `P₂=ηP₁`, `T₂,η=ηT₂`;
  bu tork nominal kaymasız çıkış devri içindir.
- Tasarım gücü **yalnız servis faktörü verilirse** `P_d=P·K_s`.

`R₁=D₁/2`, `R₂=D₂/2`, `δ=R₂−R₁`, `α=asin(δ/C)` için:

```text
S = sqrt(C² − δ²)
L = 2S + R₁(π − 2α) + R₂(π + 2α)
L_approx = 2C + π(D₁+D₂)/2 + (D₂−D₁)²/(4C)
β_driver = π − 2α
β_driven = π + 2α
```

İşaretli `δ` kullanılır; sürücü daha büyük olduğunda da etiketler doğrudur.
`approximation_minus_exact_mm=L_approx−L` işaretli farktır.

Düşük seviyeli `length_metrics` formülü `C>|R₂−R₁|` gerektirir. Tasarım
hesabı, yol oluşturucu ve ters çözüm ayrıca **ayrık referans çemberleri**
için `C>R₁+R₂` ister. Bu ek sınır gerçek dış çap/flanş boşluğunun
doğrulandığı anlamına gelmez. Fiziksel kasnak ölçüleri henüz bilinmez.

`center` modunda C'den teorik L bulunur. `length` modunda V kayışında
datum uzunluğu, triger-senkron kayışta tam `N` girilir (`Lₚ=N·p`). Ters çözüm,
monoton `dL/dC=2sqrt(1−(δ/C)²)>0` bağıntısına dayanan sınırlandırılmış
bisection kullanır. Varsayılan eksen toleransı `max(1e−10 mm, 1e−13·C)`,
en çok 128 iterasyondur. Çözüm yuvarlanmaz; uzunluk kalanı ayrıca döndürülür.
Eşit çaplarda analitik çözüm kullanılır. Sayısal taşma ve yakınsamama hatadır.

Triger-senkron kavrama tahmini `z·β/(2π)` kesirli bırakılır; kesin yük taşıyan diş
adedi değildir. `center` modundaki teorik `L/p` kendiliğinden yuvarlanmaz ve
katalog ürünü sayılmaz.

## Kuvvetler

`Ft=1000P/v`, nominal güçteki **toplam etkin kol kuvveti farkıdır**.
Ön germe veya yatak yükü değildir. F₀ yoksa `shaft_forces=None` ve
`SHAFT_FORCE: NOT_EVALUATED` döner.

İsteğe bağlı `pretension_per_belt_n=F₀` ile basitleştirilmiş model:

```text
ΔF_per = Ft / count
F₁ = F₀ + ΔF_per/2
F₂ = F₀ − ΔF_per/2 > 0
Fr_vector = count · (F_upper · u_upper + F_lower · u_lower)
```

`count` kullanıcının seçtiği adettir; gerekli kayış adedi hesaplanmaz.
Eşit yük paylaşımı, sabit ortalama germe ve kütlesiz kayış varsayılır;
merkezkaç kuvveti, rijitlik, üretici germe prosedürü ve kapasite sınırları
uygulanmaz. Gergin kol dönüş yönüne göre seçilir. İki mil üzerindeki kuvvetler
eşit ve zıttır; bileşke gerçek teğet yönlerinden bulunur. `F₁+F₂` yalnız
paralel kollar gibi özel durumda bileşkeye eşittir. Yatak yerleri ve diğer
yükler bulunmadığından yatak reaksiyonu bu modelin kapsamı dışındadır.

## Katalog ve kayıt sözleşmeleri

`catalog.profiles.PROFILES` yalnız profil kimliği/adım/referans çizgisi
katmanıdır. **Yerleşik üretici stok uzunluk veya güç tablosu yoktur.**
`LengthCatalog` kullanıcı tarafından beyan edilen sonlu bir boyut listesidir:

```python
from modules.belt_drive.catalog.models import CatalogSource, LengthCatalog
from modules.belt_drive.engineering.belt_selection import nearest_catalog_candidates

catalog = LengthCatalog(
    identifier='my-documented-list', profile='HTD_5M', reference_line='pitch',
    source=CatalogSource(name='Kendi boyut listem', manufacturer='...',
                         series='...', revision='...', reference='belge/sayfa'),
    tooth_counts=(110, 112),  # Yalnız örnek; gerçek standart ürün iddiası yok.
)
candidates = nearest_catalog_candidates(spec, catalog, limit=2)
```

V katalogda `lengths_mm`, triger-senkron katalogda tam `tooth_counts` verilir.
Boyutlar tekrarlanamaz. Adaylar hedef teorik uzunluğa yakınlıkla sıralanır.
Her aday için gerçek C, hedef C farkı, küçük sarılma açısı ve gerekiyorsa
kesirli kavrama tahmini hesaplanır. Geometri çözülemeyen aday `UNSUITABLE`,
çözülen aday `GEOMETRICALLY_SUITABLE` olur. `dimension_listed` yalnız beyan
edilen listede bulunmayı gösterir. Üretici, bulunabilirlik, güç ve ömür onayı
verilmez. Aynı adımda HTD/T/AT katalogları birbirine karıştırılmaz.

`serialization.dumps/loads`, `to_dict/from_dict` sürümlü
`gokworks.belt_drive` v1 giriş sözleşmesidir. Katalog sözleşmesi
`gokworks.belt_drive.length_catalog` v1; hesap çıktısı ayrı
`gokworks.belt_drive.result` şemasıdır. Girdiler açılırken tekrar hesaplanır;
kaydedilmiş sonuçlara güvenilmez. Bilinmeyen/eksik alan, birim, sürüm,
tekrarlanan anahtar, bool sayı, NaN/inf ve bozuk JSON reddedilir. Dosya
okuması 2 MiB ile sınırlıdır. Gelecek sürümler için açık migrasyon gerekir;
v1 bugün sessiz varsayılan alan eklemez. Katalog ayrı belgedir; kalıcı
GUI seçim kimliği ve CAD ayarları sonraki şema sürümünün konusudur.

Sonuçlarda hata `SpecificationError.issues` üzerinden `ERROR`, destek
sınırları `checks` üzerinden `WARNING/INFO/NOT_EVALUATED` olarak taşınır.
Doğrulanmamış hız, küçük kasnak, sarılma düzeltmesi, ömür, malzeme,
kapasite, germe ve servis koşulları için uydurma eşik kullanılmaz.

## Sonraki geliştirmeler

Mevcut iş yöneticisine uygun Qt'siz `controller.calculation_job(...)`
fabrikası hazırdır; sayfa henüz bağlanmadı. Geometri `Line`/`Arc` parçaları,
tam teğetler ve `point_at_distance()` ile çizim/kinematik animasyona hazırdır.
Yol pozitif yönde saat yönünde dolaşır; CCW animasyonda yol mesafesi azalır.
Arayüz geliştirmesi aynı hesap yolunu kullanmalıdır.

Uygulama planı ve sınırlar: [ARCHITECTURE.md](ARCHITECTURE.md).
Kaynak/lisans araştırması: [RESEARCH.md](RESEARCH.md).
İnceleme ve doğrulama raporu: [STAGE1_REPORT.md](STAGE1_REPORT.md).

## Otomatik tasarım

```python
from modules.belt_drive.design_models import DesignRequest
from modules.belt_drive.design_search import search_drives
from modules.belt_drive.catalog.importers import load_catalog

catalog = load_catalog('modules/belt_drive/examples/automatic-synthetic-catalog.json')
request = DesignRequest(
    power_kw=1.5, input_rpm=1450., target_rpm=700., family='timing',
    mode='range', center_min_mm=200., center_max_mm=400.,
    rpm_error_max_percent=1., service_factor=1.2, include_unverified=True,
)
report = search_drives(request, catalog)
for candidate in report.unverified:
    print(candidate.driver.code, candidate.driven.code, candidate.belt.code,
          candidate.result.nominal_output_rpm, candidate.result.center_mm,
          candidate.capacity.status)
```

Bu örnekteki katalog **sentetiktir**; Gates, Optibelt veya Tosyalı ürünü değildir.
Komut satırı aynı motoru kullanır:

```sh
python -m modules.belt_drive.design_cli modules/belt_drive/examples/automatic-request.json --catalog modules/belt_drive/examples/automatic-synthetic-catalog.json
python -m modules.belt_drive.design_cli --example
```

Modlar `auto` (katalogdaki bütün sonlu seçenekler), `fixed` (açık C hedefi ve
`center_tolerance_mm`) ve `range` (açık C min/max) şeklindedir. Boş fiziksel
sınır gizli bir varsayılanla doldurulmaz. Çap sınırları datum/bölüm çapına,
`outside_diameter_max_mm` bilinen gerçek dış zarfa uygulanır. Toplam genişlik,
diş/yüz genişliği ve nominal kayış genişliği ayrı tutulur. Kısmen bilinen
ölçü bir sınırın kesin aşıldığını gösteriyorsa diğer ölçünün bilinmemesi bu
ihlali gizlemez.

`system_width_lower_bound_mm` bilinen parça/kayış genişliklerinin alt sınırıdır.
Gerçek toplam `system_width_mm`, ancak iki kasnağın ortak kayış orta düzlemine
göre `axial_min_mm/axial_max_mm` zarfı biliniyorsa bulunur. Sadece `max(L₁,L₂)`
toplam sistem genişliği sayılmaz. Bilinmeyen toplam genişlik uygun kabul edilmez.

Yalnız aynı üretici/seri/profil/uyumluluk kimliği içindeki kayıtlar eşleştirilir.
Aynı adım farklı ürün ailelerinin veya üreticilerin uyumluluğunu kanıtlamaz.
Çap, diş, devir, C, boyut, bilinen gövde boşluğu ve beyan edilen kapasite
yetersizliği sıralamadan önce elenir. Uygunsuz aday iyi puanla geri getirilemez.

Öncelikler `speed`, `compact`, `fewest_belts`, `capacity`, `center`, `balanced`.
`balanced` için açık, negatif olmayan ağırlıklar verilebilir. Eksik ölçüt
sıfır maliyet sayılmaz; eksik ağırlık toplamı önce sıralanır. Normalizasyon:
devir hatası / verilen tolerans (yoksa 1 yüzde puanı); C farkı / C hedefi;
referans alanı / çap üst sınırının karesi (yoksa 1 m²); adet / adet sınırı
(yoksa 1); genişlik / genişlik sınırı (yoksa 1 m); kapasite için `1/margin`.
Fiyat, stok ve gerçek mil yükü verisi yoktur; bu ölçütler puana eklenmez.
`reference_area_mm2` referans çemberi zarfıdır, imalat gövdesinin gerçek alanı değildir.

Arama sonucu `pairs_visited`, `lengths_evaluated`, elenme nedenleri, bulunan
grup adetleri, `search_complete`, `results_limited`, `cancelled`, katalog
revizyonu ve içerik SHA-256 bilgisini taşır. Sonuç sınırı, aramanın tamamlanma
durumundan ayrıdır. `work_limit` fiziksel sınır değildir; hesap bütçesidir.
İptalde kısmi rapor açıkça tamamlanmamış olur. Dönen örnek ret kayıtları
sınırlı olabilir; toplam ret sayıları korunur.

## Ürün kataloğu ve kapasite

Eski `LengthCatalog` ve `nearest_catalog_candidates()` değişmedi. Yeni
`ProductCatalog`, kayış/pulley ürünleri, kaynaklar ve rating tablolarını ayrı
tutar. `catalog.importers` normalize JSON ve ürünler için CSV okur/yazar;
birim mm olmalıdır. CSV güç tablosu taşımaz; tablolar için JSON kullanılır.
Kaynak ve ürün kimlikleri, tekrarlar, seri/üretici uyuşmazlığı ve sayılar
doğrulanır. `GATES`, `OPTIBELT`, `TOSYALI` adaptörleri bu **yerel normalize
sözleşmeyi** ve beyan edilen kaynak kimliğini kontrol eder; kapalı üretici
yazılımı veya üreticinin özel dosya biçimini çözmez.

`declared_additive_corrected_v1` yalnız açıkça beyan edilen deneysel yöntemdir:
V'de `(base + additional) × wrap × length`; triger-senkron kayışta
`(base + additional) × mesh × length × width`. Bu formül **Gates/Optibelt
yöntemi olarak doğrulanmış değildir**. Ek güç terimi, yöntem referansı,
gerekli düzeltme, servis faktörü veya tablo alanı yoksa sonuç `NOT_EVALUATED`
olur. Eksik değerler sıfır/1.0 ile tamamlanmaz. İzin açıkça verilmişse
tablo içinde doğrusal/bilinear enterpolasyon yapılır; ekstrapolasyon yoktur.
Küçük kasnağın kendi devri kullanılır; her zaman motor devri kullanılmaz.

Sayısal hesap yapılabilirse `PROVISIONAL` kapasite, V için gerekli adet ve
`P_available/P_design` oranı döner. Bu oran bütün tasarımın emniyet katsayısı
değildir. Gerçek üretici veri seti ve yöntemi bağımsız doğrulanmadığı için
`manufacturer_verified=False`; `OFFICIAL_VERIFIED` yazılmış kullanıcı JSON'u
bile kendine resmî onay veremez. Bu sürümde resmî doğrulama kaydı yoktur ve
`capacity_verified` grubu boş kalır. Tüm adaylarda `engineering_approved=False`.
Doğrulanmamış adaylar yalnız `include_unverified=True` ile ayrı grupta görünür.

## Tosyalı PDF verileri

Kullanıcının sağladığı 151 sayfalık PDF'den yalnız sayısal ürün bilgileri
çıkarıldı; PDF, logo, resimler ve tam metin dağıtıma eklenmedi.

- [342 gerçek kasnak kaydı](catalog/data/tosyali-user-pdf.json): HTD_3M (60),
  HTD_5M (108), HTD_8M (67), AT5 (41), AT10 (66).
- [İçe aktarma/karantina raporu](catalog/data/tosyali-import-audit.json):
  522 tanınan satır; 146 karantina, 34 desteklenmeyen burçlu tablo satırı.
- Çelişen T5/T10 ve bazı HTD 5M Dp değerleri otomatik düzeltilmedi. İki
  eksik hücreli satır tahmin edilmedi. Basılı Dp için 0.01 mm yuvarlama
  denetiminin eşiği 0.006 mm'dir; gerçek üretim toleransı değildir.
- Dp ve `z×p/π`, diş dış çapı, flanş çapı, nominal kayış genişliği, F, L
  ve pilot delik ayrı saklanır. Pilot delik bitmiş mil deliği sayılmaz.
- Revizyon belirtilmemiştir; PDF metadata 2013/2023 tarihleri güncel katalog
  revizyonu değildir. Statü `USER_SUPPLIED`; üretim menşei ve güncellik
  bağımsız doğrulanmış değildir.

Kayış SKU/standart uzunluk ve güç tabloları bu veriye eklenmedi. Tam aktarım
araması bunları uydurmaz. Kayış verisi yokken yalnız kasnak alternatifleri:

```python
from modules.belt_drive.design_pairs import search_pulley_pairs

catalog = load_catalog('modules/belt_drive/catalog/data/tosyali-user-pdf.json')
request = DesignRequest(1.5, 1450., 700., family='timing',
                       rpm_error_max_percent=2., include_unverified=True)
pairs = search_pulley_pairs(request, catalog)
# 32 kayıtlı kasnak çifti; ilk seçenek 12/25 diş → 696 rpm.
# complete_drive=False; gerçek kayış/C/kapasite onayı yoktur.
```

Yerel PDF adaptörü `catalog.tosyali.import_tosyali_pdf(path)` için isteğe
bağlı Poppler `pdftotext` gerekir. Motor, JSON ve CSV buna bağımlı değildir.
`parse_tosyali_layout` metin üzerinden standart kütüphaneyle çalışır; belirsiz
satırlar karantinaya alınır. `strict=True` varsa tek belirsiz kayıt bile
kontrollü hata üretir. Diğer PDF düzenleri için genel OCR varsayılmaz.

## Proje, karşılaştırma ve iş yöneticisi

`design_serialization.DesignProject` v2; otomatik istek, tam katalog snapshot,
içerik özeti, isteğe bağlı nominal tasarım ve seçim kimliklerini saklar.
`project_loads` eski Aşama 1 v1 dosyalarını da açar. Eski nominal JSON/API
sözleşmesi değişmedi. `recalculate_project` güncel sonuçları yeniden üretir;
eski seçim kimlikleri sonuç yaratamaz. Katalog özeti uyuşmazsa açılış reddedilir.

`report_to_dict(report, selected_ids=...)` seçilmiş adayların girdilerini,
sonuçlarını, uyarılarını ve arama kapsamını koruyan JSON karşılaştırması
üretir. GUI/PDF/Excel sunumu bu backend tesliminin dışındadır.

`controller.automatic_design_job` ortak JobManager'ın `(events, stop)`
sözleşmesini kullanır; kendi thread havuzunu veya Qt nesnesini oluşturmaz.
İlerleme, tamamlanmış/eksik rapor ve iptal ayrı olaylarla iletilir.
