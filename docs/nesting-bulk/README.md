# Toplu DXF ve sıralı plaka düzeltmesi

Seçilen dosyalar okumadan önce tek listeye alınır. Her dosya için **Sırada,
Okunuyor, Hazır, Okunamadı, Durduruldu** durumu gösterilir. `DXFStructureError`
gibi `ValueError/OSError` dışında kalan bir dosya hatası kalan kuyruğu kesmez.
Başarılı dosyalar anında parçaya dönüşür; iptal ve sonraki bir hatada kaybolmaz.
Arama yeni yüklemede temizlenir. Sonuç mesajını geç gelen ilerleme mesajı örtemez.

Hatalı/durdurulmuş dosyaya çift tıklayın: önceki malzeme/kalınlık/adet,
birim, katman ve tolerans ayarlarıyla yeniden deneyebilirsiniz. Birimsiz DXF
için mm/cm/inch açıkça seçilir. Başarılı parçalar yerinde kalır, tekrar denenen
dosya ikinci bir kuyruk satırı oluşturmaz. **Yükleme ayrıntıları** bütün dosyaları
ve hataları gösterir. Hatalı dosya düzeltilmeden veya kullanıcı tarafından
listeden kaldırılmadan eksik bir üretim yerleşimi başlatılmaz. Yükleme kayıtları
JSON projeye eklenir; eski proje biçimi okunmaya devam eder.

NFP 1.1, her fiziksel plakada bütün kalan uygun parçaları dener. Sıradaki büyük
parça sığmıyorsa daha küçük parçalarla boşlukları kullanır. Hiçbiri sığmadığında
sonraki stok plakasını açar; 1 → 2 → 3 sırası korunur. Dışbükey ayrıştırmalar
parça/dönüş başına önbelleğe alınır. Malzeme/kalınlık eşleşmesi, kenar/kerf
payları, stok ve bağımsız kontur doğrulaması korunur. Eksik kalınlık/stok açıkça
belirtilip **Sac ve ayarlar** sekmesi açılır; farklı kalınlıklar karıştırılmaz.

Ekranda **1. plaka, 2. plaka, 3. plaka** belge sekmeleri bulunur.
Plakadaki parça sayısı ve verim ayrıca gösterilir. Excel/PDF'de de aynı
fiziksel plaka numaraları kullanılır. Boş çizim alanındaki yazı zoom ile büyümez.

## Kanıt

`docs/report-tools/capture_nesting_bulk.py` on gerçek DXF oluşturur; birini
bozuk grup koduyla okutur, aynı dosyayı düzelterek yeniden yükler ve gerçek
motorla üç plakaya yerleştirir. Yerleşim veya hata verisi elle doldurulmaz.

- [Toplu seçim: 10 dosya, 9 hazır + 1 sorunlu](bulk-import-dark.png).
- [Üç plaka: 4 + 4 + 2 parça](three-plates-dark.png).
- [Sayısal kayıt](checks.json).

İlgili testler gerçek DXF ayrıştırma hatası sonrası devam, çoklu dosya seçimi,
anında satır görünürlüğü, okuma sırasında kısmi sonuç, iptal, birim seçip yeniden
okuma, sorunlu kaynaklarla kaydet/aç, küçük parçayla ilk plakayı doldurma,
9 parçanın 4+4+1 dağılımı ve plakalar arasında gezinmeyi kapsar.
Linux/offscreen doğrulaması: **66 modül/akış testi + 6 tema/çözünürlük kontrolü
geçti**, başarısız test yok. Geçerli kaynaklar kullanılarak oluşturulan örnek
yerleşim bağımsız kontur doğrulamasını da geçti. Kullanıcının ekran görüntüsündeki
asıl DXF dosyaları bu ortamda bulunmadığından onların özel geometri sorunu
tekrar üretildiği iddia edilmez; gerçek bozuk DXF ile kuyruğun kesilmesi doğrulandı.
Bu düzeltme için EXE otomatik üretilmedi; önceki EXE bu kaynak değişikliklerini içermez.

Güncel üç adımlı arayüz, kaydırılabilir plaka sekmeleri ve yeniden yapılan
kontroller: [Nesting kullanım incelemesi](../nesting-usability/README.md).
