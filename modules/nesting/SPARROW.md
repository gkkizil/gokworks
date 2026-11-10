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
   uygun deliklere ve boşluklara eklenir. Sonraki levhanın bütün parçaları önceki
   levhalara taşınabiliyorsa o levha kaldırılır. Taşıma işlemseldir; başarısızlık
   veya iptalde kaynak parçalar ve stok kaybolmaz.
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
15/45/90 saniyedir. İlk tahminin en fazla %45'i Sparrow'a verilir; aşama üst
sınırları 2/6/12 saniyedir. Kalan süre kontur iyileştirmesine ayrılır. Sayısal
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

Resmî `spyrrow==0.9.0` Python bağlantısının Linux ve CPython 3.13 Windows x64
hazır wheel'leri kullanılır. Özgün SBOM'lar Sparrow **0.1.0** /
`881cdcbdf492ca42ba5413954ea6e41889a3becd`, jagua-rs **0.7.0** bildirir.
Güncel Sparrow 0.3.0 kullanıldığı iddia edilmez. Son kullanıcıya Rust/Cargo,
Node veya ek servis kurulmaz. PyInstaller native uzantı/metadata toplar;
Windows build adımı gerçek paketlenmiş EXE'nin headless worker'ını sınar.
Bu adım çalışmadan Linux testi Windows EXE başarısı olarak sunulmaz.

MIT/MPL bildirimleri, iki wheel'in SBOM'ları, 108 Linux/Windows Rust bileşeninin
bildirimleri ve değiştirilmemiş jagua-rs kaynak arşivi
`packaging/licenses/nesting/sparrow/` altında dağıtılır; Lisanslar'dan dışa aktarılır.

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
