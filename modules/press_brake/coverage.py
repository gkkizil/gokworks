"""Press brake coverage: what “no collision” is and is not based on."""
from gui_qt.coverage import PARTIAL, SUPPORTED, UNSUPPORTED

PASS_MEANING = ('“Çarpışma yok”: sac, atanmış takım katıları ve varsa tutucular yalnız kontrol edilen '
                'pozlarda kesişmiyor. Pozlar arasındaki hareket sürekli kanıtlanmaz; aşağıda kısmi / '
                'desteklenmiyor olarak işaretli konular kontrole dahil değildir.')

COVERAGE = (
    ('Sac – takım çarpışması', PARTIAL, 'örneklenmiş pozlarda katı kesişimi; pozlar arası hareket sürekli kanıtlanmaz'),
    ('Takım segmentleri ve V kanalı', SUPPORTED, 'segment boşlukları ve seçilen kanal kontrol katısına girer'),
    ('Takım tutucuları', PARTIAL, 'yalnız takım verisinde tutucu katısı varsa'),
    ('Tezgâh gövdesi (üst kiriş, alt ray)', UNSUPPORTED, 'sahnede yalnız görseldir, çarpışmaya girmez'),
    ('Arka dayama', UNSUPPORTED, 'konum ve çarpışma kontrol edilmez'),
    ('Yeniden tutuş / parça çevirme', UNSUPPORTED, 'adımlar arası konumlandırma kontrol edilmez, kartta yalnız işaretlenir'),
    ('Parça çıkarma rotası', UNSUPPORTED, 'kontrol edilmez'),
    ('Büküm kuvveti (tonaj)', UNSUPPORTED, 'hesaplanmaz'),
    ('Geri yaylanma', UNSUPPORTED, 'hedef açı nominal geometridir, yaylanma payı hesaplanmaz'),
    ('CNC strok / eksen değerleri', UNSUPPORTED, 'hesaplanmaz; üretim uygunluğu onayı değildir'),
)
