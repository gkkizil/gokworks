# Ortak uygulama testleri

Modüle özgü hesap, CAD ve arayüz testleri `modules/<modül>/tests/` altındadır.
Bu klasör yalnız ortak altyapıyı ve uygulama bütününü sınayan grupları içerir:

- `test_qt_workflows.py`: birden çok ekranı kapsayan Qt iş akışları ve entegrasyonlar.
- `test_compact_*.py`: tüm uygulamanın ortak başlık, araç çubuğu ve dar pencere sözleşmeleri.
- `test_repository_structure.py`: modül yerleşimi, bağımsız importlar ve EXE kaynak yolları.
- `test_settings_and_connection.py`: paylaşılan JSON ayarları ve SolidWorks bağlantısı.
- `test_process_watch.py`, `test_qt_diagnostics.py`: tanılama ve süreç yaşam döngüsü.
- `test_single_file_distribution.py`: tek EXE dağıtımı ve lisanslar.
- `test_workspace_layout.py`: ortak pencere geometrisi.
- `support/`: tüm modüllerin kullandığı test nesneleri ve PDF hata enjektörü.
- `legacy_tk/`: güncel test grubuna dahil edilmeyen, değiştirilmeden korunan tarihsel testler.

Depo kökünde `python -m pytest` hem burayı hem `modules/` altını toplar.
Yalnız bir modül: `python -m pytest modules/nesting/tests`.
Linux'ta ekran olmadan çalıştırırken `QT_QPA_PLATFORM=offscreen` kullanın.
Canlı SolidWorks kabul testleri uygun Windows oturumu ve ilgili test ortam
değişkenleri olmadan atlanır; başarılı kabul edilmiş sayılmaz.
