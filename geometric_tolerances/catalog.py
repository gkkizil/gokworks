"""Geometrik özelliklerin eğitim amaçlı, açık kapsamlı açıklamaları.

Bir genel hassasiyet sınıfından geometrik tolerans türetilmez. Bölge
tanımları bu arayüzün gösterdiği basit ASME Y14.5-2018 örnekleri içindir.
"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Characteristic:
    key: str
    name: str
    english: str
    group: str
    description: str
    zone: str
    datum: str
    measurement: str
    note: str
    example: str
    diametrical: bool = False
    active: bool = True
    reference: str = ''


CATALOG = (
    Characteristic('straightness', 'Doğrusallık', 'Straightness', 'Şekil',
        'Seçilen yüzey çizgisinin ideal bir doğrudan ne kadar ayrılabileceğini sınırlar.',
        'Bu örnekte, aynı düzlemde iki paralel doğru arasındaki toplam mesafe t. Türetilmiş eksen için silindirik bölge ayrı bir belirtimdir.',
        'none', 'Belirtilen yönde çizgi taraması; CMM veya uygun doğrusal ölçüm düzeni. Tek noktadan ölçüm yeterli değildir.',
        'Uzun yüzeylerde işleme, fikstür ve gerilme kaynaklı eğilmeyi kontrol eder. Yüzey çizgisi ile eksen doğrusallığını ayırın.',
        'Kılavuz yüzey üzerindeki bir çizgi.'),
    Characteristic('flatness', 'Düzlemsellik', 'Flatness', 'Şekil',
        'Bir yüzeyin kendi içinde düz olmasını kontrol eder; başka bir yüzeye göre yönünü belirlemez.',
        'İki paralel düzlem arasındaki toplam uzaklık t. Bütün belirtilen yüzey bu bölge içinde kalır.',
        'none', 'Yüzey taraması veya uygun referans üzerinde çok noktalı yükseklik ölçümü; destekleme ve düzlem ilişkilendirme yöntemi önemlidir.',
        'Sızdırmazlık ve oturma yüzeylerinde kullanılır. Birkaç noktadan ölçüm, aradaki yüzey hatalarını kaçırabilir.',
        'Flanşın conta oturma yüzeyi.'),
    Characteristic('circularity', 'Dairesellik', 'Circularity', 'Şekil',
        'Bir dairesel kesitin ideal çember biçiminden sapmasını kontrol eder.',
        'Bir kesitte iki eş merkezli çember arasındaki radyal mesafe t. Kesitler ayrı değerlendirilir.',
        'none', 'Dairesellik cihazında kesit taraması; birden fazla kesit ve uygun filtreleme. İki noktalı çap ölçümü tam daireselliği kanıtlamaz.',
        'Rule #1 boyut limitleriyle şekli de sınırlar. Normal durumda ayrı yüzey dairesellik toleransı boyut toleransından küçük olmalıdır. Loblu kesit iki noktalı mikrometrede gözden kaçabilir.',
        'Rulman yuvasının bir kesiti.'),
    Characteristic('cylindricity', 'Silindiriklik', 'Cylindricity', 'Şekil',
        'Silindirik yüzeyin tamamının ideal silindir biçimine uygunluğunu kontrol eder.',
        'İki eş eksenli silindir arasındaki radyal mesafe t. Belirtilen yüzeyin tamamı bölge içinde kalır.',
        'none', 'Silindiriklik cihazı veya yeterli kesit ve boyuna tarama yapan CMM. Tek kesit yalnızca dairesellik hakkında bilgi verir.',
        'Dairesellik, koniklik ve boyuna şekil hatalarını birlikte sınırlar; bu hataların basit toplamı değildir. Datum yoktur. Normal durumda t ilgili boyut toleransından küçük olmalıdır (8.4.4).',
        'Hidrolik pistonun çalışan silindirik yüzeyi.'),
    Characteristic('line_profile', 'Çizgi Profili', 'Profile of a Line', 'Profil',
        'Belirtilen kesitteki gerçek çizginin teorik doğru profile uygunluğunu kontrol eder.',
        'Bu örnekte teorik profil çevresinde simetrik, toplam genişliği t olan iki sınır çizgisi. Tek taraflı veya kaydırılmış bölgeler ayrıca belirtilir.',
        'optional', 'CMM, optik profil ölçümü veya uygun kesit taraması; teorik profil ve kesit yönü bilinmelidir.',
        'Datum verilirse profilin referansa göre yönü/konumu da sınırlandırılır. Teorik profil tanımı olmadan çerçeve tek başına yeterli değildir.',
        'Kam profilinin tanımlanan kesiti.'),
    Characteristic('surface_profile', 'Yüzey Profili', 'Profile of a Surface', 'Profil',
        'Üç boyutlu gerçek yüzeyin teorik doğru yüzeye uygunluğunu kontrol eder.',
        'Bu örnekte teorik yüzey çevresinde simetrik, toplam genişliği t olan iki sınır yüzeyi. Çizimdeki kesit, 3B bölgenin bir temsilidir.',
        'optional', 'CMM veya doğrulanmış 3B tarama ile teorik CAD yüzeyine göre değerlendirme; datum ve ilişkilendirme yöntemi korunur.',
        'Serbest biçimli yüzeylerde kullanılır. Veri hizalaması hatayı yapay olarak küçültmemelidir; profilin yön/konum bağı çizimden okunur.',
        'Kalıp boşluğu veya kanat yüzeyi.'),
    Characteristic('parallelism', 'Paralellik', 'Parallelism', 'Yön',
        'Bir yüzeyin datum düzlemine göre paralel yönünü sınırlar.',
        'Bu yüzey örneğinde datum A’ya paralel iki düzlem arasındaki toplam uzaklık t; bölgenin datumdan mesafesini belirlemez.',
        'required', 'Datum düzlemi oluşturularak yüzey taraması veya karşılaştırmalı yükseklik ölçümü. Parça datumuna göre bağlanır.',
        'Paralellik, iki yüzey arasındaki mesafe toleransı değildir. Eksen paralelliği için bölge ve özellik türü ayrıca seçilir.',
        'Kızak üst yüzeyinin oturma düzlemine yönü.'),
    Characteristic('perpendicularity', 'Diklik', 'Perpendicularity', 'Yön',
        'Bir yüzeyin datum düzlemine göre 90° yönünü sınırlar.',
        'Bu yüzey örneğinde datum A’ya dik iki paralel düzlem arasındaki toplam uzaklık t; konum ayrı belirlenir.',
        'required', 'Datum düzlemi üzerinde CMM taraması veya uygun diklik düzeni ve komparatör; ölçüm yüksekliği ve bağlama tanımlanır.',
        'Tolerans mm cinsinden bölge genişliğidir; ± derece değildir. Delik ekseni için silindirik bölge farklı bir belirtimdir.',
        'Omuz yüzeyinin taban düzlemine dikliği.'),
    Characteristic('angularity', 'Açısallık', 'Angularity', 'Yön',
        'Bir yüzeyin datuma göre teorik olarak tam tanımlanan açıdaki yönünü sınırlar.',
        'Bu örnekte datum A’ya teorik 45° açıda iki paralel düzlem arasındaki toplam uzaklık t. 45° yalnızca gösterim örneğidir.',
        'required', 'Datum referansı ve teorik açı kullanılarak CMM veya uygun açılı ölçüm düzeniyle yüzey değerlendirmesi.',
        'Çerçevedeki tolerans mm’dir; açısal ± toleransla aynı şey değildir. Gerçek teorik açı teknik resimde ayrıca belirtilmelidir.',
        '45° işlenmiş oturma yüzeyi.'),
    Characteristic('position', 'Konum', 'Position', 'Konum',
        'Bir boyut özelliğinin basic ölçülerle tanımlanan gerçek konumundan izin verilen sapmasını sınırlar. Bu örnek RFS delik eksenidir.',
        'Bu delik ekseni örneğinde true position çevresinde çapı t olan silindir; radyal pay t/2. Basic ölçüler ve datum sistemi birlikte okunur; eksen unrelated AME’den değerlendirilir.',
        'required', 'CMM ile datum sistemine göre unrelated AME ekseninin RFS değerlendirmesi. Basit 2B merkez kontrolünde çap cinsinden hata: 2 × √(dx² + dy²).',
        '2B merkez hesabı tek başına eksen eğimini ve bütün boyu doğrulamaz. İşaretsiz boyut özelliğinde RFS, datum boyut özelliğinde RMB varsayılır. MMC/LMC yüzey sınırı veya bonus hesabı yapılmaz.',
        'Bağlantı deliği ekseninin teorik konumu.', True),
    Characteristic('concentricity', 'Eş Merkezlilik (eski)', 'Concentricity', 'Eski işaretler',
        'ASME 2018’de kaldırılmış eski eş merkezlilik sembolüdür. Güncel çerçeve oluşturulmaz.',
        'Eski merkez/medyan nokta kontrolü, güncel position veya runout kontrolüyle doğrudan eşdeğer değildir. İşlev ve kontrol edilen özellik belirlenerek yeniden belirtilir.',
        'required', 'CMM ile karşılıklı yüzey noktalarından türetilmiş merkez/eksen değerlendirmesi; datum ekseni ayrı kurulur.',
        'Eksen/koaksiyellik için position; yüzeyin datum eksenine ilişkisi için uygun profile veya runout kontrolü düşünülebilir (10.6). Otomatik dönüşüm yapılmaz.',
        'İki mil kademesinin türetilmiş eksenleri.', True),
    Characteristic('symmetry', 'Simetri (eski)', 'Symmetry', 'Eski işaretler',
        'ASME 2018’de kaldırılmış eski simetri sembolüdür. Güncel çerçeve oluşturulmaz.',
        'Simetrik ilişkiler güncel position veya profile belirtimleriyle kontrol edilebilir. Bu kontrollerin gerektirdiği geometri eski symmetry ile aynı kabul edilmez (10.7).',
        'required', 'CMM ile karşılıklı yüzeylerden orta noktaların oluşturulması ve datum orta düzlemine göre değerlendirme.',
        'Boyut özelliğinin merkez düzlemi ve yüzey profili farklı gerekliliklerdir. İstenen işlev için position veya profile seçin; eski sembolü doğrudan değiştirmeyin.',
        'Mil üzerindeki kanalın orta düzlemi.'),
    Characteristic('circular_runout', 'Dairesel Salgı', 'Circular Run-out', 'Salgı',
        'Datum ekseni çevresinde dönüş sırasında her ölçüm kesitindeki yüzey değişimini sınırlar.',
        'Bu radyal örnekte her kesit için datum eksenine eş merkezli iki çember arasındaki radyal mesafe t. Kesitler ayrı değerlendirilir.',
        'required', 'Datum ekseninde tam bir tur döndürme ve aynı kesitte komparatörün en büyük - en küçük okuması; gerekli kesitlerde tekrarlama.',
        'Hem yüzey biçimi hem datum eksenine göre kaçıklık etkili olabilir. Dairesellik ile aynı kontrol değildir.',
        'Dönen milin tek kesitte radyal salgısı.'),
    Characteristic('total_runout', 'Toplam Salgı', 'Total Run-out', 'Salgı',
        'Datum ekseninde dönüş ve yüzey boyunca tarama sırasında bütün yüzey değişimini birlikte sınırlar.',
        'Bu radyal örnekte datum eksenine eş eksenli iki silindir arasındaki radyal mesafe t. Kesitler birbirinden bağımsız sıfırlanmaz.',
        'required', 'Datum ekseninde tam dönüşlerle birlikte yüzey boyunca komparatör taraması; bütün taramanın ortak maksimum - minimum farkı.',
        'Silindiriklikten farklı olarak datum ekseniyle ilişkilidir. Her kesitte ölçümü sıfırlamak toplam salgıyı gizleyebilir.',
        'Uzun dönen milin bütün çalışan yüzeyi.'),
)

REFERENCES = {
    'straightness': '8.4.1.1', 'flatness': '8.4.2', 'circularity': '8.4.3',
    'cylindricity': '8.4.4', 'line_profile': '11.2.1.2 / 11.3.1',
    'surface_profile': '11.2.1.1 / 11.3.1', 'parallelism': '9.3 / 9.3.2',
    'perpendicularity': '9.3 / 9.3.2', 'angularity': '9.3 / 9.3.2',
    'position': '10.2 / 10.3.2', 'circular_runout': '12.4.1.1',
    'total_runout': '12.4.2.1', 'concentricity': 'Önsöz / Ek D.2–D.4 / 10.6',
    'symmetry': 'Önsöz / Ek D.3–D.4 / 10.7',
}
CATALOG = tuple(replace(item, active=item.key not in ('concentricity', 'symmetry'),
                        reference=REFERENCES[item.key]) for item in CATALOG)
CHARACTERISTICS = {item.key: item for item in CATALOG}
ACTIVE = tuple(item for item in CATALOG if item.active)
GROUPS = ('Şekil', 'Profil', 'Yön', 'Konum', 'Salgı', 'Eski işaretler')

MEASUREMENT_INPUTS = {
    'straightness': 'Yüzey çizgisini kapsayan en dar iki paralel doğru arasındaki mesafeyi girin; tek nokta sapmasını girmeyin.',
    'flatness': 'Yüzeyi kapsayan en dar iki paralel düzlem arasındaki mesafeyi girin; datuma göre yükseklik veya tek nokta sapması değildir.',
    'circularity': 'Kesit için değerlendirilmiş eş merkezli çemberlerin Rmax - Rmin radyal mesafesini girin; çap farkı değildir. Gerekli bütün kesitler değerlendirilir.',
    'cylindricity': 'Bütün yüzeyi kapsayan eş eksenli silindirlerin değerlendirilmiş Rmax - Rmin radyal mesafesini girin; çap farkı veya tek kesit sonucu değildir.',
    'line_profile': 'Bu merkezlenmiş profil örneğinde teorik profile göre 2 x en büyük |normal sapma| değerini girin. Her noktanın sınırı ±t/2; maksimum - minimum farkı yeterli değildir.',
    'surface_profile': 'Bu merkezlenmiş profil örneğinde teorik yüzeye göre 2 x en büyük |normal sapma| değerini girin. Her noktanın sınırı ±t/2; maksimum - minimum farkı yeterli değildir.',
    'parallelism': 'Datuma paralel yönü sabit iki düzlemin yüzeyi kapsayan normal mesafesini girin; datumdan uzaklık değildir.',
    'perpendicularity': 'Datuma dik yönü sabit iki düzlemin yüzeyi kapsayan normal mesafesini girin; açı derecesi değildir.',
    'angularity': 'Teorik açıda yönü sabit iki düzlemin yüzeyi kapsayan normal mesafesini girin; açı derecesi değildir.',
    'position': 'Çap cinsinden değerlendirilmiş konum hatasını girin. Basit 2B kontrol: 2 x sqrt(dx² + dy²); radyal sapmayı doğrudan girmeyin. Bütün AME ekseni ayrıca değerlendirilir.',
    'circular_runout': 'Aynı kesitte tam turdaki maksimum - minimum komparatör farkını (TIR) girin; ikiyle çarpmayın. Gerekli bütün kesitler değerlendirilir.',
    'total_runout': 'Bütün yüzeyin tam dönüş ve boyuna taramasındaki ortak maksimum - minimum farkını (TIR) girin; kesitleri ayrı sıfırlamayın, ikiyle çarpmayın.',
}

GUIDE = """GEOMETRİK TOLERANSLAR · ASME Y14.5-2018

Birincil kaynak kullanıcının yüklediği ASME-Y14.5-2018-R2024-Dimensioning-and-Tolerancing.pdf belgesidir. Kapak ve ana metin ASME Y14.5-2018 olarak doğrulandı. R2024 dosya adıdır; yeniden onay bilgisi kapakta/metinde görülmedi. Belge hash'i ve bölüm eşleştirmeleri raporda kayıtlıdır. PDF GitHub'a yüklenmez.

12 güncel özellik vardır: dört şekil, üç yön, konum, iki profil ve iki salgı. Concentricity / Symmetry sembolleri 2018’de kaldırılmıştır (Önsöz, Ek D). Eski işaretler eğitim için ayrı gösterilir; geçerli çerçeve oluşturulmaz. Koaksiyellik ve simetrik ilişki position/profile/runout ile işlevine göre yeniden belirtilir (10.6–10.7); otomatik veya eşdeğer dönüşüm yapılmaz.

Rule #1 — 5.8.1: Düzenli boyut özelliğinin yüzeyi MMC’deki kusursuz şekil zarfını aşamaz. Boyut limitleri ile şekil bağımsız varsayılmaz. İstisnalar 5.8.2, türetilmiş medyan çizgi/düzlem ve özel belirtimlere bağlıdır. Bu ekrandaki şekil örnekleri normal durumdaki yüzey/çizgi kontrolüdür. İlgili boyut toleransı girilirse t < boyut toleransı kontrol edilir (8.4); bu, MMC zarfını ölçerek kontrol etmek değildir.

Rule #2 — 5.9.1: Boyut özelliğindeki geometrik tolerans için değiştirici yoksa RFS; datum boyut özelliği referansında değiştirici yoksa RMB varsayılır. RFS/RMB aynı kavram değildir. MMC/LMC ile MMB/LMB birbirinin yerine kullanılamaz. Bu rehber M/L değiştiricisi, bonus veya datum mobility üretmez. Dairesellik, silindiriklik, yüzeye uygulanan yön/profil ve salgı toleranslarına MMC/LMC eklenmez.

Datum sistemi — Bölüm 7: Datum, datum unsurunun true geometric counterpart'ından oluşturulan teorik referanstır. A | B | C sırası önceliği gösterir. Ortogonal düzlem-düzlem-düzlem örneğinde 3-2-1 bağlama altı serbestliği kısıtlar; her datum geometrisi için otomatik 3-2-1 varsayılmaz. Şekil toleransları datum kullanmaz. Yön ve bu RFS konum örneği referans ister. Profil datumla veya datumsuz kullanılabilir. Datumsuz koaksiyellik gibi özel konum uygulamaları 10.6.2.3’te ayrıca açıklanır; bu çerçeve örneği onları üretmez.

Basic ölçüler — 5.1.1.2 ve 10.2.1.1: Teorik olarak tam ölçülerin dikdörtgen çerçevesi, gerçek konumu/profili belirler. Gösterim boyutu bir basic konum ölçüsü veya boyut toleransı değildir. Konum için eksen, RFS'de unrelated AME üzerinden değerlendirilir (10.3.2); MMC/LMC'de surface method varsayımı vardır (5.9.2). Türetilmiş medyan çizgiyle AME ekseni karıştırılmaz.

Toplam bölge: t=0,3 mm, ±0,3 mm değildir. Konum Ø0,3 mm için radyal pay 0,15 mm’dir. Silindiriklikte t iki eş eksenli silindir arasındaki radyal mesafedir. Profilde normal yönde toplam genişlik t; aksi belirtilmezse uniform ve true profile çevresinde eşit dağılır (11.3). Yön toleransı mm cinsinden bölgedir; ± derece değildir.

Ölçüm girişi: Konumda 2B radyal sapma 0,03 mm ise çap cinsinden hata 0,06 mm’dir; Ø0,05 sınırını aşar. Merkezlenmiş profil t=0,05 mm ise her normal sapma -0,025 ile +0,025 mm arasında kalmalıdır. +0,01 ve +0,04 mm sapmaların aralığı 0,03 mm olsa da profil uygun değildir: eşdeğer merkezlenmiş toplam hata 2 x 0,04 = 0,08 mm’dir. Datumlu profilde hizalama datum sistemini korumalıdır; datumsuz profilde izin verilen ilişkilendirme sonrası sapmalar kullanılır. Dairesellik/silindiriklik radyal bölge genişliğidir; salgı komparatörün maksimum - minimum farkıdır, tekrar ikiyle çarpılmaz. Alan, seçilen özellik için önceden değerlendirilmiş hata içindir; ham nokta/sapma hesaplayıcısı değildir.

Çerçeve yazımı: Teknik çerçevede mm değerleri ondalık noktayla, 1 mm altı başında sıfırla yazılır (4.3.1, 4.3.3): 0.05. Türkçe giriş ve açıklamalarda ondalık virgül kullanılabilir. Şemanın 45° açısallık örneği gerçek 45° yönünde çizilir; profil sınırları teorik profile normal yönde eşit uzaklıktadır. Şema piksel boyutları fiziksel ölçüm değildir.

Değeri tasarımcı belirler. Genel f/m/c/v boyut sınıflarından ASME geometrik değer türetilmez. İsteğe bağlı hata, ilgili özellik için doğru datum/bölgeyle değerlendirilmiş toplam geometrik hatadır; tek çap sapması veya nokta ölçümü değildir. Yalnızca hata <= t aritmetiği gösterilir. Tam resim/model uygunluğu, zarf/virtual condition, ölçüm belirsizliği ve kalite kabulü değerlendirilmez. Tür değişince eski ölçüm temizlenir; yeniden açılışta geri yüklenmez.

Şemalar öğreticidir; bölgeler büyütülür. 3B bölgeler kesit/izdüşümle gösterilir. Kompozit/ortak bölge, izdüşümlü bölge, free state, tangent plane, unequally disposed/dynamic profile ve malzeme/boundary değiştiricileri burada oluşturulmaz. Tam GD&T çerçeve editörü veya CMM simülatörü değildir. Çerçeve CAD'e yazılmaz.

GitHub yardımcı kaynağı: juanvanyo/FreeCAD-GDT’deki adlar ve çerçeve yapısı karşılaştırıldı. Bu eski kaynak 14 işaret içerir; 2018’e uymayan iki işaret uygulamada devre dışıdır. FreeCAD çalıştırılmadı ve kodu kopyalanmadı. Standart kuralları GitHub'dan değil yüklenen ASME belgesinden kontrol edildi; ISO kuralları bu sekmenin ASME kurallarıyla birleştirilmez.
"""
