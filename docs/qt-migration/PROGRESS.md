# Qt migrasyonu — çalışma kaydı

Çalışma dalı: `codex/pyside6-migration`, depo: `gkkizil/gokworks`.
Başlangıç: `5f01e53`. `main` korunur; yedek depoya erişilmez veya gönderim yapılmaz.

## Aşama 1 — analiz

Tam Python dosya/sınıf/fonksiyon ve test envanteri `inventory.json` içinde.
Dokuz modül: PDF, DXF/DWG, BOM, isimlendirme, manuel K/R + hesap yardımı,
ISO seçimi + manuel tolerans + montaj hedefi, GD&T, cıvata ve ağırlık.
İşlem motorları Qt'den bağımsız kalacak. Eski çizimlerin geometrisi yeni
Qt Graphics Scene arka ucunda korunacak; Tk nesnesi oluşturulmayacak.
Ayarların bilinmeyen anahtarları dahil eski JSON kaydı korunacak.
Uzun işler QThread/QObject üzerinden çalışacak, COM nesneleri GUI'ye taşınmayacak.

Başlangıç ekranları ve profil Linux/Xvfb ile alındı. Mevcut testlerin başlangıç
sonuçları ayrıca kaydediliyor; başarısızlıklar migrasyon sonucu gibi gösterilmeyecek.

## Aşamalar 2–6 — tamamlandı

Dokuz Qt sayfası, cache’li navigasyon, modeller, arka plan işleri, ayar geçişi,
vektör şemalar ve iptal/kapatma akışları uygulandı. 38 motor/geometri dosyası
byte olarak aynı kaldı. Büyük isimlendirme planları da worker’a taşındı.

## Aşama 7 — doğrulama

Linux: 520 test geçti, 878 alt senaryo geçti. Önceki Tk testlerinden 210 yöntem
arşivde aynen korunur; 110 Qt senaryosu bunların davranış karşılıklarını kapsar.
Windows ilk denemesi başarısız oldu; ilk kayıtta aşama ayrıntısı yoktu. Gelişmiş test günlükleri
ve native EXE/DPI kontrolleriyle yeniden derleniyor. Canlı SolidWorks testi yok.

## Aşama 8 — temizlik ve belge

Ana runtime’dan Tk/CustomTkinter çıkarıldı, eski kullanılmayan mixin’ler kaldırıldı.
Lisanslar, envanter, test eşleştirmesi ve migrasyon raporu eklendi. Windows sonucu
ve son ölçüm kanıtları derleme tamamlandığında rapora işlenecek.

## Nihai sonuç

520 Linux testi, 519 Windows testi + 878 alt senaryo geçti. Windows’ta yalnız
Unix hard-link yoluna ait 1 test atlandı. K/R geçiş/kapanış yarışı düzeltildi.
50.000 satırın kapsamlı Qt denetimi ile üretim performansı ayrı sınandı.
Native Windows EXE üretildi; dokuz ekran, iki tema, dört boyut ve üç ölçek geçti.
Son rapor: docs/QT_MIGRATION_REPORT.md. Canlı SolidWorks testi ve fiziksel
çoklu monitör kabulü bu ortamda yapılamadı. Ana dal ve yedek depo korunur.
