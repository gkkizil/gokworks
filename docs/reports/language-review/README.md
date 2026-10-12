# Türkçe metin ve yazı tipi kontrolü

12 Ekim 2026. PDF, DXF/DWG, BOM, K/yarıçap, ISO geçmeleri ve geometrik
toleranslar ekranlarının başlıkları, düğmeleri, yardım metinleri ve hata
mesajları gözden geçirildi. Geometrik tolerans ve ISO rehberleri sadeleştirildi;
standart kapsamı ve matematiksel ayrımlar korundu.

Düzeltilen örnekler: K FAKTÖR - RADIUS → K faktörü / yarıçap;
sacdan → sactan; 180° hem → tam katlama; kaynak klasör → kaynak klasörü.
Şekil ve eski işaretler başlıklarında i/ı büyük harf dönüşümü Türkçe kurala
uyar: ŞEKİL ve ESKİ İŞARETLER. BOM sayacı, dosya/konfigürasyon satırlarını
ifade ettiği için “farklı parça” yerine “kalem” olarak adlandırıldı.

“ÜRÜN AACI” görünümü kaynak yazısından değil, ilk bulut Tk 9 derlemesinin
Ğ/İ harflerini çizmemesinden kaynaklanıyordu. Önceki ortamda bu harflerin
ölçülen genişliği 0 piksel olduğundan harfler kayboluyordu. GUI çalıştırması
sistem Python 3.13 / Tk 8.6 ortamına taşındı. Normal ve kalın arayüz/günlük
yazı tiplerinde ÇçĞğİıÖöŞşÜü harflerinin tamamı görünür genişliğe sahip.
Uygulama, desteklenmeyen kurulumda harfleri sessizce kaybetmek yerine
başlangıçta açıklayıcı bir hata verir. Windows Segoe UI seçimi korunur.

**377 test geçti; 0 başarısız, 0 hata, 0 atlanan.** Gerçek Tk testleri iki
tema, küçük/büyük pencere ve ölçek durumlarını kapsar. Standart karşılaştırma
kontrolleri kaldırılmadı; yeni metinlere göre güncellendi. Bağımlılık kontrolü,
kaynak derleme ve git diff --check temizdir. Tam kayıt ve yazı tipi ölçümleri
[validation.json](validation.json) içindedir. Gerçek SolidWorks 2025 bu
ortamda çalıştırılmadı.

[Güncel ekran galerisi](../../ui-preview/README.md) ·
[BOM örneği ve görselleri](../bom/README.md)
