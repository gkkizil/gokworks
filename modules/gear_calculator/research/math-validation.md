# Parametrik ve matematiksel doğrulama · 27 Ekim 2026

## Denetlenen kapsam

Dıştan kavraşan, standart tam yükseklikte düz evolvent dişli çifti; x₁=x₂=0,
hₐ*=1, h𝒻*=1,25, β=0°, sıfır nominal diş boşluğu, standart eksen mesafesi.
Hesap motoru, önizleme ve CAD aynı `GearPairSpecification` verisini kullanır.
Modül/diş sayısı/açı değişince profil yeniden hesaplanır; genişlik ve delik
değişince gerçek katı yeniden üretilir. Bu, STEP içinde yerel CAD unsur geçmişi
veya yük altında elastik temas modeli bulunduğu anlamına gelmez.

## Kaynak karşılaştırması

- [KHK, standart düz dişli boyut hesabı, Tablo 4.1](https://khkgears.net/new/gear_knowledge/gear_technical_reference/calculation_gear_dimensions.html):
  m=3, α=20°, z=12/24 örneği otomatik teste sabit referans olarak eklendi.
  a=54; d=36/72; da=42/78; df=28,5/64,5; db=33,829/67,658 mm.
  Son temel çaplar tablonun üç ondalık basamak hassasiyetinde karşılaştırılır.
  [Üreticinin Japonca eş tablosu](https://www.khkgears.co.jp/gear_technology/basic_guide/khk357_2/)
  ve [teknik kılavuzun Tablo 4.1 bölümü](https://dev-khknew.avatarsyn.com/media/izojpong/gear_guide1.pdf)
  aynı sayısal referansı verir. z=12 pinyonunun nominal ölçü hesabı geçerlidir;
  alttan kesilmesiz üretilebilirlik iddiası değildir.
- [SDP/SI, Elements of Metric Gear Technology, §3.2 ve §3.2.1](https://sdp-si.com/resources/elements-of-metric-gear-technology/page2.php):
  aynı modül/basınç açısı, temas yolunun temel adıma oranı ve εα≥1,2 önerisi.
  1,2 bir tasarım önerisidir; ISO sertifikasyon sınırı olarak kullanılmadı.
- [SDP/SI, §16.1, düz dişli kuvvetleri](https://sdp-si.com/resources/elements-of-metric-gear-technology/page8.php):
  normal kuvvetin çevresel ve radyal bileşenleriyle Ft=2000T/d ve Fr=Ft·tanα
  bağıntılarının birim/bileşen kontrolü.
- KHK kılavuzunun §3.5 alttan kesilme koşulu m≤(mz/2)sin²α,
  z sınırı=2/sin²α olarak uygulanır. 20° için yaklaşık 17,097 bulunur;
  tam kesilmesiz profil için muhafazakâr tam sayı sınırı 18'dir.

Erişim notu: bu denetimde üretici sayfalarının ilgili arama dizini bölümleri
incelendi. Doğrudan bazı sayfalar 403/zaman aşımı verdi; büyük PDF'nin tamamı
okunmuş veya bir standart baskısı satın alınıp doğrulanmış kabul edilmedi.
Kaynak kod kopyalanmadı; uygulamanın mevcut formülleri ve aşağıdaki bağımsız
hesaplar karşılaştırıldı.

## Bağımsız hesap ve parametrik tarama

`tests/independent_reference.py` yalnız testlerde kullanılan 60 basamaklı Decimal
referansıdır. Uygulamanın hesap/geometri/CAD fonksiyonlarını çağırmaz.
Sinüs/kosinüs Taylor serileriyle hesaplanır. Yük kontrolü üretim kodundaki tork
katsayısı yerine bölüm çevresindeki hız ve P=F·v üzerinden yürütülür.
Radyal kuvvet √(Fn²−Ft²) ile, kavrama oranı her dişlinin boyutsuz evolvent
yuvarlanma katkısı z·(tₐ−tanα)/(2π) toplanarak bulunur.

`tests/test_math_audit.py` şu 9.408 kombinasyonu doğrular:

- m: 0,1; 0,15; 0,5; 1,25; 2; 3; 8; 19 mm.
- z₁ ve z₂ ayrı ayrı: 8; 12; 18; 20; 37; 100; 300.
- α: 14,5°; 20°; 25°; 30°.
- Altı güç/tork/devir senaryosu: iki yük modu, ters dönüş, küçük/büyük girdiler;
  P=0,0001…10⁷ kW, T=0,0001…10⁷ N·m, |n|=0,001…100.000 dev/dak.

Nominal geometrik büyüklükler, yükler, yaklaşma/uzaklaşma, temas yolu, oran ve
çıkış yönü karşılaştırılır. CAD'ye uygun olmayan düşük diş sayıları da nominal
hesap testi içindedir; bunların üretim/hareket engelleri ayrıca sınanır.
Çift sonuçlarında bağıl tolerans 2×10⁻¹¹, mutlak tolerans 10⁻²² kullanılır.
Tek dişli sonuçlarında bağıl 2×10⁻¹² / sonuç biriminde mutlak 10⁻¹¹ toleransı uygulanır.
Bu sayısal test toleransları imalat toleransı değildir.

27 Ekim Linux çalıştırmasında çift sonuçlarının 60 basamaklı referansa göre
en büyük bağıl farkı **2,5282×10⁻¹⁴** altında kaldı; en büyük fark kavrama
oranındaydı (m=0,15, z₁=z₂=300, α=20°). Bu gözlenen bir tarama sonucudur;
tüm sürekli parametre uzayı için hata üst sınırı ispatı değildir.

Ek kontroller: modülle uzunluğun doğrusal ölçeklenmesi, Ft'nin modülle ters
ölçeklenmesi, ideal güç korunumu, güç/tork modu dönüşümü, delik eti ve teorik
alttan kesilme sınırı. Üretim hesabındaki güç/tork dönüşümü yuvarlanmış 9550
yerine tam birim dönüşümü 60000/(2π) kullanır.

## Geometri ve gerçek CAD doğrulaması

Beş çift, bir diş adımında 96 ayrı fazda hem kesişim hem temas uzaklığı açısından
sınanır: z=8/8, 18/300, 20/40, 37/61, 64/32; ilgili açılar 30/20/20/25/14,5°.
Örnekleme toleransıyla yalnız çarpışmamak değil, temasın kaybolmaması da aranır.
Ek bir keşif taramasında 216 çiftin 48'er fazı (10.368 konum) hata vermedi;
bu keşif taraması sürekli temasın matematiksel ispatı olarak sunulmaz.

`tests/test_parametric_cad_audit.py` beş çiftin STEP dosyasını gerçek OCCT ile
üretip yeniden okur: m=0,1…19 mm, z=8…300, α=14,5…30°, b=0,1…50 mm,
sıfır/sıfırdan büyük delikler ve tam minimum et sınırı. İki geçerli katı,
mm birimi, Z genişliği ve pozitif hacim doğrulanır.

Hacmin bağımsız referansı örneklenmiş CAD poligonundan çıkarılmaz.
Green teoremiyle analitik evolventler, gerçek üst/dip yayları ve radyal dip
bağlantıları üzerinden kapalı alan integrali alınır; delik alanı π·r² çıkarılıp
genişlikle çarpılır. STEP hacmi bu integralle 10⁻⁴ bağıl toleransta karşılaştırılır.
Genişliği ikiye katlamak hacmi ikiye katlar; deliği 8'den 12 mm'ye çıkarmak
tam π·(6²−4²)·b hacmini çıkarır. Tüm uzunlukları dört katına çıkarmak sınır
koordinatlarını dört, hacmi 64 katına çıkarır. Bu kontroller gerçek B-Rep'e uygulanır.

Mevcut testler ayrıca kapalı DXF, diş sayısı, eş açısal dağılım, Bézier hata bütçesi,
yaylar, STEP gövde sayısı, delik içi/dışı nokta sınıflaması ve gerçek alt süreçte
en son UI değerleriyle CAD aktarımını doğrular.

## Düzeltilen hatalar

1. 30°/8 diş tam teorik sınırı ikili sinüs yuvarlamasıyla yanlış reddediliyordu
   (kritik değer 8,000000000000002). 10⁻¹² düzeyinde eşitlik kontrolü eklendi;
   7 diş veya 29,9999° örnekleri hâlâ risk olarak işaretlenir.
2. m=0,15/z=20/delik=2,225 mm tam minimum et sınırı çıkarma yuvarlamasıyla
   reddediliyordu. Çap farkında 10⁻⁹ mm sayısal eşitlik toleransı eklendi;
   gerçek 10⁻⁶ mm malzeme kaybı hâlâ reddedilir.
3. Hesaplanan tork, birincil giriş kutusunun sınırlarına kırpılıyordu ve çok
   küçük sonuçlar tabloda sıfır görünüyordu. İkincil sonuç salt okunur alana
   taşındı; gerekli büyüklüklerde bilimsel gösterim eklendi. Güç/tork modlarının
   kullanıcı girişleri artık birbirini ezmez. Matematik motoru bu değerleri
   önceden de doğru hesaplıyordu; hata gösterim/girdi durumundaydı.
4. Python API'sine aşırı büyük tamsayı verildiğinde denetimsiz float taşması
   oluşabiliyordu. Artık normal parametre doğrulama hatasıyla reddedilir.

## Tekrarlama ve sınırlar

```sh
QT_QPA_PLATFORM=offscreen python -m pytest -q modules/gear_calculator/tests
QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_fusion_workbench.py tests/test_repository_structure.py tests/test_single_file_distribution.py
```

Linux/Python 3.12/OCCT 8.0.1 çalıştırmasında modülün **110 testi geçti, hiçbiri
atlanmadı**; uygulama entegrasyonu/dağıtım/yapı kontrollerinde ayrıca **21 test
geçti**. Windows/Python 3.13 doğrulaması `windows-gears.yml` iş akışındadır;
her PR için kaynak testleri ve gerçek paketlenmiş uygulamanın CAD alt süreci sınanır.

Doğrulama nominal formüller ve tanımlanan geometrik kapsam içindir. Gerçek kesici
trokoidi, üretim tolerans yığılması, malzeme/mukavemet/ömür, sürtünme/verim ve
yük altındaki deformasyon bu modelin dışında kalır. Parametrik tarama ve STEP
yeniden okuma, gerçek SOLIDWORKS üzerinde elle açma testi veya tam ISO 6336/AGMA
uygunluğu olarak sunulmaz.
