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
        'Yüzey üzerindeki bir çizginin düz bir çizgiden sapmasını sınırlar.',
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
        'ASME Kural 1, boyut sınırlarıyla şekli de sınırlar. Normal durumda ayrı yüzey dairesellik toleransı boyut toleransından küçük olmalıdır. Loblu kesit iki noktalı mikrometrede gözden kaçabilir.',
        'Rulman yuvasının bir kesiti.'),
    Characteristic('cylindricity', 'Silindiriklik', 'Cylindricity', 'Şekil',
        'Silindirik yüzeyin tamamının ideal silindir biçimine uygunluğunu kontrol eder.',
        'İki eş eksenli silindir arasındaki radyal mesafe t. Belirtilen yüzeyin tamamı bölge içinde kalır.',
        'none', 'Silindiriklik cihazı veya yeterli kesit ve boyuna tarama yapan CMM. Tek kesit yalnızca dairesellik hakkında bilgi verir.',
        'Dairesellik, koniklik ve boyuna şekil hatalarını birlikte sınırlar; bu hataların basit toplamı değildir. Datum yoktur. Normal durumda t ilgili boyut toleransından küçük olmalıdır (8.4.4).',
        'Hidrolik pistonun çalışan silindirik yüzeyi.'),
    Characteristic('line_profile', 'Çizgi Profili', 'Profile of a Line', 'Profil',
        'Tanımlanan kesitteki çizginin teorik profile göre sapmasını sınırlar.',
        'Bu örnekte teorik profil çevresinde simetrik, toplam genişliği t olan iki sınır çizgisi. Tek taraflı veya kaydırılmış bölgeler ayrıca belirtilir.',
        'optional', 'CMM, optik profil ölçümü veya uygun kesit taraması; teorik profil ve kesit yönü bilinmelidir.',
        'Datum verilirse profilin referansa göre yönü/konumu da sınırlandırılır. Teorik profil tanımı olmadan çerçeve tek başına yeterli değildir.',
        'Kam profilinin tanımlanan kesiti.'),
    Characteristic('surface_profile', 'Yüzey Profili', 'Profile of a Surface', 'Profil',
        'Üç boyutlu yüzeyin teorik yüzeye göre sapmasını sınırlar.',
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
        'Bir deliğin veya milin, teorik ölçülerle tanımlanan konumundan sapmasını sınırlar. Bu örnek, boyuttan bağımsız (RFS) delik ekseni kontrolüdür.',
        'Bu örnekte tolerans bölgesi, teorik eksen çevresinde çapı t olan silindirdir; radyal pay t/2’dir. Teorik ölçüler ve referans sistemi birlikte değerlendirilir. Eksen, datumlarla kısıtlanmadan oluşturulan ideal eşleşme zarfından (unrelated AME) elde edilir.',
        'required', 'CMM ile datum sistemine göre unrelated AME ekseninin RFS değerlendirmesi. Basit 2B merkez kontrolünde çap cinsinden hata: 2 × √(dx² + dy²).',
        '2B merkez hesabı tek başına eksen eğimini ve bütün boyu doğrulamaz. İşaretsiz boyut özelliğinde RFS, datum boyut özelliğinde RMB varsayılır. MMC/LMC yüzey sınırı veya bonus hesabı yapılmaz.',
        'Bağlantı deliği ekseninin teorik konumu.', True),
    Characteristic('concentricity', 'Eş Merkezlilik (eski)', 'Concentricity', 'Eski işaretler',
        'ASME 2018’de kaldırılmış eski eş merkezlilik sembolüdür. Güncel çerçeve oluşturulmaz.',
        'Eski merkez/medyan nokta kontrolü, güncel konum veya salgı kontrolüyle doğrudan eşdeğer değildir. İşlev ve kontrol edilen özellik belirlenerek yeniden belirtilir.',
        'required', 'CMM ile karşılıklı yüzey noktalarından türetilmiş merkez/eksen değerlendirmesi; datum ekseni ayrı kurulur.',
        'Eksenlerin ortaklığı için konum; yüzeyin referans eksenine ilişkisi için profil veya salgı kontrolü düşünülebilir (10.6). Otomatik dönüşüm yapılmaz.',
        'İki mil kademesinin türetilmiş eksenleri.', True),
    Characteristic('symmetry', 'Simetri (eski)', 'Symmetry', 'Eski işaretler',
        'ASME 2018’de kaldırılmış eski simetri sembolüdür. Güncel çerçeve oluşturulmaz.',
        'Simetrik ilişkiler güncel konum veya profil toleranslarıyle kontrol edilebilir. Bu kontrollerin gerektirdiği geometri eski simetri kontrolü ile aynı kabul edilmez (10.7).',
        'required', 'CMM ile karşılıklı yüzeylerden orta noktaların oluşturulması ve datum orta düzlemine göre değerlendirme.',
        'Boyut özelliğinin merkez düzlemi ve yüzey profili farklı gerekliliklerdir. İstenen işlev için konum veya profil toleransı seçin; eski sembolü doğrudan değiştirmeyin.',
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

GUIDE = """ASME Y14.5-2018 · Geometrik tolerans rehberi

Bu ekran 12 güncel özelliği açıklar: dört şekil, üç yön, bir konum, iki profil ve iki salgı toleransı. Eş merkezlilik ve simetri sembolleri ASME 2018’de kaldırılmıştır (Ek D). Eski çizimleri okumak için gösterilir; bu sembollerle güncel tolerans çerçevesi oluşturulmaz. İşlevine göre konum, profil veya salgı toleransı seçilmelidir (10.6–10.7).

Referans (datum), ölçümde esas alınan teorik düzlem, eksen veya noktadır. Parçadaki ilgili referans yüzeyiyle aynı şey değildir. A | B | C sırası referansların önceliğini gösterir. Şekil toleransları referans kullanmaz. Bu ekrandaki yön ve konum örnekleri referans gerektirir; profil kontrolünde referans isteğe bağlıdır (Bölüm 7).

Teorik olarak tam ölçüler (basic dimensions), tolerans çerçevesiyle birlikte konumu veya profili tanımlar. Teknik resimde dikdörtgen çerçeve içinde gösterilir. Bu uygulamadaki “Gösterim boyutu” yalnız şemanın örnek boyutudur; konum ölçüsünün veya boyut toleransının yerine geçmez (5.1.1.2, 10.2.1.1).

ASME Kural 1 (Rule #1) — 5.8.1: Düzenli boyut özelliğinde, boyut sınırları şekli de sınırlar. Maksimum malzeme durumundaki (MMC) kusursuz şekil zarfı aşılmamalıdır. İstisnalar 5.8.2’de açıklanır. Bu ekran normal yüzey şekli örneklerinde geometrik toleransın ilgili boyut toleransından küçük olmasını kontrol eder (8.4); MMC zarfını ölçmez.

ASME Kural 2 (Rule #2) — 5.9.1: Boyut özelliğinde ek değiştirici yoksa geometrik tolerans boyuttan bağımsızdır (RFS). Referans boyut özelliğinde ise malzeme sınırından bağımsızlık (RMB) varsayılır. RFS ve RMB aynı kavram değildir. MMC/LMC belirtilmişse malzeme durumuna bağlı yüzey sınırları ayrıca değerlendirilir (5.9.2). Bu ekranda MMC/LMC, bonus tolerans veya referansın hareket payı hesaplanmaz. Dairesellik ve silindiriklik gibi yüzey şekli kontrollerine malzeme durumu değiştiricisi eklenmez.

Toplam toleransın anlamı: t=0,3 mm, ±0,3 mm demek değildir. Konum için Ø0,3 mm tolerans bölgesinin radyal payı 0,15 mm’dir. Silindiriklikte t, iki eş eksenli silindir arasındaki radyal mesafedir. Merkezlenmiş profilde toplam bölge genişliği t’dir; her normal sapma ±t/2 içinde kalmalıdır. Yön toleransı da mm cinsindendir; açıya verilen ± derece toleransı değildir.

Ölçülen hata: Bu alana seçilen özellik için değerlendirilmiş toplam geometrik hatayı girin. Tek çap ölçüsü veya tek noktanın sapması çoğu özellik için yeterli değildir. Konum örneğinde 2B radyal sapma 0,03 mm ise çap cinsinden hata 0,06 mm’dir. Bu, bütün eksenin eğimini ve boyunu doğrulamaz. CMM, koordinat ölçüm cihazıdır; eksen kontrolünde datumlarla kısıtlanmadan oluşturulan ideal eşleşme zarfı (unrelated AME) ayrıca değerlendirilir.

Merkezlenmiş profil örneği: t=0,05 mm için her normal sapma -0,025 ile +0,025 mm arasında olmalıdır. +0,01 ve +0,04 mm sapmalar arasındaki fark 0,03 mm olsa da yüzey uygun değildir; bu örnekte toplam hata 2 × 0,04 = 0,08 mm’dir. Dairesellik ve silindiriklikte radyal bölge genişliği kullanılır. Salgıda komparatörün en büyük ve en küçük okumalarının farkı kullanılır; sonuç ikiyle çarpılmaz.

Teknik çerçevede mm değerleri ondalık noktayla ve 1 mm altındaki değerler başında sıfırla yazılır: 0.05 (4.3.1, 4.3.3). Giriş alanları ve Türkçe açıklamalar ondalık virgülü destekler. Toleransı tasarımcı belirler; genel f/m/c/v boyut sınıflarından geometrik tolerans üretilmez.

Şemalar açıklama amaçlıdır; piksel boyutları fiziksel ölçü değildir. Sonuç yalnız girilen hata ile toleransı karşılaştırır. Tam teknik resim veya model uygunluğu, ölçüm belirsizliği ve kalite kabulü değerlendirilmez. Tür değiştiğinde eski ölçüm temizlenir. Çerçeve CAD'e yazılmaz.

Bu rehber ASME Y14.5-2018 kapsamındadır; ISO geometrik tolerans kurallarıyla birleştirilmez. Kaynak belgeler ve bölüm karşılaştırmaları docs/geometric-tolerances.md içinde kayıtlıdır.
"""
