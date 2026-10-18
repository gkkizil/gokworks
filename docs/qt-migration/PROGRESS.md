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

## Aşamalar 2–8

Uygulama sürüyor. Bu dosya tamamlanma raporu değildir.
