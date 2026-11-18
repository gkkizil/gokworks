"""Automatic drawing coverage, kept in step with docs/automatic-drawing/KNOWN_LIMITATIONS.md."""
from gui_qt.coverage import PARTIAL, SUPPORTED, UNSUPPORTED

PASS_MEANING = ('“Başarılı”: istenen standart görünüşler, paftalar ve seçilen çıktılar üretildi, '
                'SolidWorks’te yeniden açılıp denetlendi. Aşağıda kısmi / desteklenmiyor olarak '
                'işaretli konular bu denetime dahil değildir; resim imalat için ayrıca kontrol edilmelidir.')

COVERAGE = (
    ('Standart görünüşler', SUPPORTED, 'ana, üst, yan izdüşüm ve izometrik; ölçek ve pafta seçimi'),
    ('Kesit görünüşü', UNSUPPORTED, 'otomatik oluşturulmaz; gerekiyorsa analizde öneri olarak yazılır'),
    ('Detay / yardımcı görünüş', UNSUPPORTED, 'otomatik oluşturulmaz'),
    ('Delik ölçüleri', PARTIAL, 'Hole Wizard model ölçüleri içe aktarılır; delik tablosu ve konum ölçüsü tamamlanmaz'),
    ('Diş / havşa açıklaması', UNSUPPORTED, 'diş, havşa ve tolerans açıklaması tahmin edilmez'),
    ('PCD (bölüm dairesi)', UNSUPPORTED, 'flanş delik dairesi otomatik ölçülmez'),
    ('Ölçülendirme', PARTIAL, 'model ölçüleri ve isteğe bağlı geometri ölçüleri; tam imalat ölçülendirmesi değildir'),
    ('BOM tablosu', SUPPORTED, 'native BOM, adet ve görünen sütun denetimi'),
    ('Büyük BOM’u paftalara bölme', UNSUPPORTED, 'tablo sonraki paftaya taşınmaz; pafta güvenli alanına sığmazsa iş HATA ile durur, resim yayımlanmaz'),
    ('Tek gövdeli sac açınımı', PARTIAL, 'yalnız modelde hazır, bastırılmamış açınım ile'),
    ('Çok gövdeli sac açınımı', PARTIAL, 'yalnız gövde için hazır ve doğrulanmış açınım konfigürasyonu varsa; yoksa o gövde UYARI ile atlanır'),
    ('Çok paftalı DXF', UNSUPPORTED, 'çok pafta SLDDRW / PDF’te korunur, DXF için uyarı verilir'),
    ('Gerçek SolidWorks kabulü', UNSUPPORTED, 'kabul senaryoları yazıldı, bu sürümde çalıştırılmadı (LIVE_ACCEPTANCE.md)'),
)
