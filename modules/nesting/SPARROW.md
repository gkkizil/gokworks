# Sparrow tabanlı birleşik yerleşim

Sparrow ana başlangıç motorudur. Nesting ve Akıllı Parça Bölme otomatik olarak
aynı birleşik akışı kullanır; kullanıcıya motor seçtirilmez. Sol parça listesindeki
küçük kontur önizlemeleri korunur.

## Yerleşim nasıl geliştirilir?

1. **Sparrow başlangıcı:** gerçek dış konturlar ve izinli açılarla stok levhaları
   için ilk plan kurulur. Sonsuz şeritten yalnız fiziksel levhaya bütünüyle sığan
   parçalar alınır; sınırı geçen parçalar kesilmez. Malzeme ve kalınlık eşleşir.
2. **GOKWORKS kontur iyileştirmesi:** doğrulanmış Sparrow planı doğrudan başlangıç
   olarak alınır. Parçalar levha içinde sıkıştırılır; henüz yerleşmeyen parçalar
   uygun deliklere ve boşluklara eklenir. Az dolu levhaların parçaları diğer
   levhalara her iki yönde taşınır. Sabit yerleşimler engel olursa aynı parça
   örnekleri alan ve uzun kenar sıralarıyla yeniden dizilir; gerekirse gerçek
   NFP ile içbükey boşluklar denenir. Tamamen boşaltılan levhalar kaldırılır.
   Sonra aynı plan, stokta bulunan daha küçük uyumlu saclarda denenir.
   İşlemler taslak üzerinde yapılır; yalnız tamamı yerleşen değişiklik kabul edilir.
   Tamamlanmış iyileştirme sonraki taslakta süre dolsa veya iptal gelse de korunur.
   Henüz yerleşmeyen adet varsa pahalı stok onarımından önce bu adetler tamamlanır.
3. **NFP ayrıntı araması:** aynı plan en iyi aday olarak korunurken mevcut
   kontur, açı ve parça sırası aramaları diğer adayları dener. Yeni aday önceki
   iyi planı bozmaz. Ayrık MultiPolygon parçaları aynen bu katmanda işlenir;
   dışbükey kılıfa veya küçültülmüş geometriye dönüştürülmez.
4. **Bağımsız son kontrol:** kimlik, adet, dönüş açısı/hadde, malzeme/kalınlık,
   stok, kenar payı, gerçek mesafe ve çakışma özgün milimetre konturlarıyla
   doğrulanır. Delik içine giren parçaların kesim sırası mevcut kontur planıyla
   korunur. DXF'deki özgün eğriler ve alan/ağırlık hesapları değiştirilmez.

Sıralama ortak ve leksikografiktir: yerleşmeyen adet, levha sayısı, kullanılan
brüt levha alanı, kullanılan kenar şeridi alanı. Son gösterge her levhada yatay
ve dikey dolu şeritlerden küçüğünü kullanır; Sparrow'un dikey artığını da bizim
yatay sıkıştırmamızı da değerlendirir. Gerçek depolanabilir dikdörtgen artık
veya küresel optimum garantisi değildir. Sonuç bu sıralamada Sparrow başlangıcından
daha kötü olamaz; her geçerli aday bağımsız kontrolden geçer.

## Geometri ve süre

Kesim aralığı `max(gap,kerf) + kontur hata payları + f32 güvenlik payı` ile
korunur. Sparrow'a özel dış kontur kopyası bunun yarısıyla muhafazakâr mitre
ofseti alır. Özgün geometri korunur. Yerel orijin ve ortak ölçek dönüşümü
milimetreye geri çevrilir. Native motorun başlangıç şeridini de daraltan kendi
aralık seçeneği kapalıdır: çok büyük levhada birkaç küçük parça için bu
şerit yok olup jagua'da panic üretebiliyordu. Aralık bizim geometri katmanımızda
ve bağımsız doğrulayıcıda uygulanır; levha sınırı gevşetilmez.

İki aşama aynı proje/hash ve ortak bütçeyi kullanır. Otomatik bütçe gerçek
kontur, adet ve açılara göre hesaplanır; Hızlı/Dengeli/Yüksek üst sınırları
15/45/90 saniyedir. İlk tahminin en fazla %70'i Sparrow'a verilir; aşama üst
sınırları 3/12/30 saniyedir. Bu süre kalan fiziksel levhalar ve malzeme/kalınlık
grupları arasında paylaştırılır. Uzun ve kısa eksende sıkıştırma denenir;
serbest dönüş ve kayıtlı ayrık açılar ayrı sözleşmelerle korunur.
Kalan süre kontur iyileştirmesine ayrılır. Sayısal
`seconds` sınırı olan eski projeler ve Akıllı Parça Bölme'nin 2/3/5 saniyelik
aday bütçeleri iki aşama arasında paylaşılır; iki kez uygulanmaz. Tek GEOS
çağrısı, veri doğrulama ve süreç temizliği ek duvar saati alabilir.

Native motor Qt/COM yüklemeyen özel alt süreçtedir. İptal/süre sonunda kendi
süreci sonlandırılır ve toplanır; yalnız uygun ara çözümler tekrar doğrulanır.
Native hata başarı diye gizlenmez. Refinement iptali geçerli Sparrow başlangıcını
kaybettirmez. Yerleşmeyen adetler açık kalır; tam sonuç gerektiren çıktılar kapanır.

## Uyumluluk, sürüm ve dağıtım

Eski `GOKWORKS NFP` ve `Sparrow` engine kayıtları dosya/hash uyumluluğu için
okunur; yeni hesap her zaman birleşik akışı kullanır. Engine alanı eksik eski
NFP dosyaları eski hash ile doğrulanır. Kullanıcıya seçim veya veri geçişi
sorulmaz. Sonuç motoru `Sparrow + GOKWORKS`; metadata'sı kullanılan Sparrow,
NFP ve native deneme bilgisini taşır.

`spyrrow 0.10.0`, `f6345979e5f6cf88e9e2e3775750fcce899334fd` açık kaynak
revizyonundan özgün `Cargo.lock` ile derlenir. Bağlı çekirdek Sparrow **0.3.0** /
`3be915856b543d18c9cb7d4664fe7c53901fe1fd`, jagua-rs **1.0.0**'dır.
Rust hesabı Python'a taşınmaz; Python fiziksel stok ve doğrulanmış planın
iyileştirmesini yönetir. Derleme ortamında Rust 1.90+ gerekir; son kullanıcıya
Rust/Cargo, Node veya ek servis kurulmaz. PyInstaller native uzantı/metadata toplar;
Windows build adımı gerçek paketlenmiş EXE'nin headless worker'ını sınar.
Bu adım çalışmadan Linux testi Windows EXE başarısı olarak sunulmaz.

MIT/MPL bildirimleri, SBOM'lar, kilitli Rust bileşenlerinin özgün
bildirimleri ve değiştirilmemiş jagua-rs 1.0.0 kaynak arşivi
`packaging/licenses/nesting/sparrow/` altında dağıtılır; Lisanslar'dan dışa aktarılır.

## Üretim stoku iyileştirmesi · 11 Kasım 2026

GOKWORKS NFP 1.7, Sparrow başlangıcını fiziksel stokla iyileştirir.
Sparrow'un güncel `main` kaynağı da incelendi: 7 Kasım'daki `ca4ee65` değişikliği
jagua-rs 2.0.0'a geçmiştir. Python bağlantısının yayımlanmış kaynağı hâlâ
1.0.0'ı sabitler; bu çalışmada bu çekirdekler yükseltilmedi.
Python iyileştirmesinde 64 ve üstü sabit parça için muhafazakâr sınır kutusu
filtrelemesi kullanılır; kesin malzeme kesişimi ve mesafe kontrolü aynen sürer.
Hız kazanımı işin geometrisine bağlıdır; evrensel hızlanma iddiası yoktur.

Aynı geçerli başlangıç ve tek iyileştirme turunda sentetik ölçümler:

| Örnek | NFP 1.6 | NFP 1.7 |
| --- | --- | --- |
| Önce küçük artık, sonra büyük levha | 2 levha, 13.000 mm² | 1 levha, 10.000 mm² |
| İçbükey C parçası ve iç parça | 2 levha, 20.000 mm² | 1 levha, 10.000 mm² |
| Gerçek Sparrow başlangıcı: çerçeve ve 4 iç parça | 1 levha, 40.000 mm² | 1 levha, 10.000 mm² |

Üç örnekte de tüm adetler yerleşmiştir. Son örnekte net malzeme 5.700 mm²
korunur; fire 34.300 → 4.300 mm² olur. İlk iki başlangıç kontrollü geçerli
yerleşimlerdir; üçüncüsü gerçek native Sparrow çıktısıdır. Aynı çıktı eski ve
yeni katmana verilmiştir. Bunlar müşteri DXF'leri veya tezgâh kabulü değildir.
[Stok regresyonları](tests/test_stock_refinement.py) küçük stok, boş hedef
levha rezervasyonu, adet/kimlik koruma, iptal/süre ve gerçek boşlukları kapsar.

## Küçük 2D önizlemeler

Sol listede adların yanında 36 × 28 mantıksal piksel gerçek konturlar çizilir.
Oran, delikler, ana çizim renkleri, iki tema ve yüksek DPI korunur. Yalnız
istenen satırlar çizilir; QIcon önbelleği 256 ile sınırlıdır. CAD verisi değişmez.

## Doğrulama · 9 Kasım 2026

Birleşik sürümün Nesting, Akıllı Parça Bölme ve paketleme giriş regresyonu:
**443 vaka, 442 geçti, 1 atlandı, 0 hata**. Linux/Qt'de sınırlı ayrı süreçler
kullanıldı. Atlanan mevcut vaka kullanıcı DWG dosyası ve kurulu yerel ODA
ister. Native süreç iptali, süre sonu, kaynak/adet koruma, hatalı native
kimlik/koordinat, eski kayıt hash'i, iki tema, yeniden fiyatlandırma, kesim
sırası, DXF/Excel/PDF ve segment aday optimizasyonu kapsanır.

Sparrow'un gerçek planının yalnız tek GOKWORKS iyileştirme turuyla 2 levhadan
1'e indiği ayrıca test edilir; iki bağımsız sonucun karşılaştırılmasıyla
sınırlı değildir. Başarısız/iptal edilen levha boşaltması parçaları silmez.
Ana akış, eski engine metadata değeri ne olursa olsun Sparrow başlangıcı
çağırır; seçim alanı bulunmadığı gerçek Qt testinde doğrulanır.

Aynı 6 saniyelik proje sınırında örnek ölçümler:

| Örnek | Yalnız Sparrow | Birleşik akış |
| --- | --- | --- |
| Çerçeve + 4 iç parça | 2 levha | 1 levha |
| Dairesel delik + 4 iç parça | 2 levha | 1 levha |
| Döndürülerek sığan iç parça | 1 levha, 1 eksik | 1 levha, tam |
| 2 çerçeve + 8 iç parça | 3 levha | 2 levha |
| 2 dolu parça | 1 levha | 1 levha |

İlk örnekte net alan her iki tam planda 5700 mm²; brüt alan 24200 → 12100 mm²,
fire %76,45 → %52,89 oldu. Bunlar sentetik örnek ölçümleridir; her müşteri işi
veya süre için aynı iyileşme iddia edilmez. Kısmi native planın fire yüzdesi
aynı adet tamamlanmış planla başarı kıyası olarak kullanılmaz.
[Ham ölçümler](examples/sparrow/birlesik-olcumler.json).

Gerçek Qt 1 çerçeve/4 iç parça akışı, 1366/1024/820 genişlikleri × açık/koyu
temada çalıştı; ikonlar görünür, yatay liste kaydırması yok. [Koyu görünüm](examples/sparrow/koyu-1366.png),
[açık görünüm](examples/sparrow/acik-1024.png),
[görünüm kaydı](examples/sparrow/gorunum-dogrulama.json).
21 modül/iki tema/çözünürlük matrisi kaynak açılış özdenetimi geçti.

Yeni başlığın Windows CI ve otomatik birleşme durumu PR'da izlenir. Önceki
0d92465'in 427 vakalık kaydı tarihsel kalır; yeni birleşik algoritmanın Windows
kanıtı değildir. Canlı SolidWorks/tezgâh kabulü ve yeni EXE derlemesi yapılmadı.
