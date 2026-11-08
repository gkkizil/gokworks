"""Hidrolik ekranı için kullanıcı dili ve işlem önerileri; hesap içermez."""

STEPS = (
    ('Silindirleri tanımlayın', 'Piston ve mil çapını, toplam stroku girin. Başlangıç konumu, milin çevrim başında ne kadar dışarıda olduğunu belirtir.'),
    ('Hareket sırasını kurun', 'Her satır bir işlemdir. Silindiri ve yönü seçin; hareket için hız veya süre kullanın. Bekleme fazında yalnız süre girilir.'),
    ('Pompayı ve motoru kontrol edin', 'Pompa debisi çevrimin ihtiyacını karşılamalıdır. Motor ve emniyet valfi alanını boş bırakırsanız öneri otomatik hesaplanır.'),
    ('Hattı ve yağı tanımlayın', 'Hat türünü ve boyunu girin. İç çapı boş bırakırsanız hesap seçer. Örnek yağ yerine gerçek ürün verilerini kullanabilirsiniz.'),
    ('Tankı ve soğutucuyu kontrol edin', 'Tankın ölçülerini ve hedef yağ sıcaklığını girin. Isı yükü yüksekse sağdaki özette gereken soğutucu gücünü görebilirsiniz.'),
    ('Gerekiyorsa akümülatörü ekleyin', 'Bu bölüm isteğe bağlıdır. Akümülatör kullanmıyorsanız kapalı bırakıp rapora geçin.'),
    ('Sonuçları inceleyip rapor alın', 'Önce kritik uyarıları çözün. PDF paylaşılabilir rapordur; Excel tabloları, JSON ise hesap verilerini içerir.'),
)
ADVANCED = {
    'pump': {'volumetric_efficiency','mechanical_efficiency','leakage_flow','idle_pressure'},
    'project': {'relief_factor','overload'},
    'pipe': {'min_velocity','max_velocity','zeta','hose_laminar'},
    'oil': {'nu40','nu100','density'},
    'thermal': {'residence_time','fill_fraction','heat_transfer'},
    'accumulator': {'exponent','atmospheric_pressure'},
}
SECTION_HELP = {
    'pump': 'Önce pompa tipini, devir başına hacmi ve devri seçin. Verimler ve kaçak bilgileri gelişmiş ayarlardadır.',
    'project': 'Otomatik seçim için elle girilen ayarları boş bırakın. Öneriler sağdaki özette görünür.',
    'pipe': 'Bu hesap bir hattı inceler. Borunun iç çapını kullanın; dış çap veya diş ölçüsü değildir.',
    'oil': 'Hazır yağ eğrileri örnektir. Yağ sınıfı değişince “Örnek yağ verilerini kullan” düğmesiyle eğriyi de güncelleyin.',
    'thermal': 'Denge sıcaklığı soğutucusuz, basitleştirilmiş tahmindir; sistemin gerçekten o sıcaklıkta çalışacağını göstermez.',
    'accumulator': 'Yağın basınç altında depolandığı hacmi hesaplar; pompa boyutunu otomatik küçültmez.',
}
ACTIONS = {
    'HOT_OIL': 'Tank ve ısı sekmesine gidin; gereken soğutucu gücünü ve pompa kayıplarını inceleyin.',
    'COOLER': 'Hedef sıcaklık için en az özetteki kapasitede soğutucu değerlendirin.',
    'VELOCITY': 'Hat ve yağ sekmesinde önerilen hızları uygulayın veya iç çapı kontrol edin.',
    'CAPACITY': 'Pompa debisi/basıncını artırmayı veya çevrimde hız/kuvvet ihtiyacını azaltmayı değerlendirin.',
    'BUCKLING': 'Silindir ayarlarında mil çapını, bağlantıyı ve gerçek burkulma boyunu kontrol edin.',
    'TANK_VOLUME': 'Tank ölçülerini veya kullanılabilir doluluk oranını kontrol edin.',
    'RELIEF_LIMIT': 'Emniyet valfi ayarını pompanın izin verilen basıncıyla uyumlu hâle getirin.',
    'MOTOR_SMALL': 'Elle seçilen motoru büyütün veya alanı boş bırakıp otomatik öneriyi kullanın.',
    'CYCLE_NOT_CLOSED': 'Çevrim sonunda her silindiri başlangıç konumuna döndürecek hareket ekleyin.',
    'OIL_EXTRAPOLATION': 'Yağın bu sıcaklıktaki üretici viskozite verisini doğrulayın.',
    'FRICTION_MODEL': 'Hat kaybı tahminini uygun akış modeli veya üretici verisiyle doğrulayın.',
}
