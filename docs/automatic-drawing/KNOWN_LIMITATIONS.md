# Bilinen sınırlar ve canlı kabul gereksinimi

## Gerçek CAD doğrulaması

Bu geliştirme Linux ortamında yapıldı; Windows / pywin32 / lisanslı çalışan
SolidWorks yoktu. Gerçek SLDPRT / SLDASM’den gerçek SLDDRW / PDF üretimi
ve yeniden açılması bu ortamda çalıştırılmadı. Ham IDispatch fakes,
orchestration fakes veya dosya başlığı testleri gerçek entegrasyon testi
olarak değerlendirilmemelidir. SolidWorks 2026 öncelikli canlı kabul
yapılmadan bu özellik üretim için doğrulanmış sayılmaz.

## Henüz tamamlanmamış özellikler

- Otomatik kesit, detay, yardımcı görünüş ve patlatılmış montaj seçimi.
  Mevcut veriye göre kesit / detay gereksinimi önerilir.
- Tam delik / diş / havşa / PCD tanıma ve tüm geometriler için eksiksiz
  imalat ölçülendirmesi. Hole Wizard model ölçüleri native import edilir;
  yeni diş veya tolerans açıklaması tahmin edilmez.
- Çok gövdeli sac için yeni açınım konfigürasyonlarını otomatik hazırlama.
  Gövde bazlı paftalar yalnız mevcut ve doğrulanmış bir konfigürasyonla
  üretilir; eksik veya birden fazla adayda o gövde atlanır ve WARNING verilir.
- Kaynakta hiç açınım konfigürasyonu yokken yeni konfigürasyon oluşturma.
  Mevcut konfigürasyonla sınırlı çalışma kaynak değişikliği riskini azaltır.
- Genel görünüşleri keyfi sayıda sayfaya bölen optimizasyon; şu an bağlı
  izdüşüm grubu birlikte kalır, izometri / açınım / BOM ayrılabilir.
- Büyük BOM tablolarını otomatik bölme ve sonraki sayfaya taşıma.
- Tam lider çizgisi, GD&T frame, genel not ve kaynak sembolü çakışma
  denetimi. Ölçü metin sınırları ve görünüş / tablo alanları denetlenir.
- Named profil kütüphanesi, kesintiden sonra kalıcı kuyruk devamı,
  BOM CSV/XLSX ve tek paket ZIP dışa aktarımı.
- Üzerine yazma modu. Mevcut dosyayı atlama / yeni ad üretme vardır.
- Çok sayfalı resmin DXF paketi. Tek sayfalı DXF seçilebilir; çok sayfa
  SLDDRW ve PDF içinde korunur ve DXF için WARNING üretilir.

## Muhafazakâr davranışlar

Dirty veya rebuild bekleyen kaynak otomatik kaydedilmez / onarılmaz.
Kullanıcı modelini SolidWorks’te hazırlamalıdır. Yeni SolidWorks oturumu
izinsiz başlatılmaz. Virtual / eksik / çözümlenmemiş bileşenler gizlenmez;
BOM tamlığı doğrulanamıyorsa işlem engellenir.

Bağlantı analiz / oluşturma başlatılınca worker içinde kontrol edilir;
sayfa açılışında arka planda ayrı bir COM oturumu oluşturulmaz. İptal
kontrolü native çağrılar arasında yapılır. SolidWorks’ün o anda blokladığı
bir COM çağrısı zorla sonlandırılamaz.

Standart yön puanında kutu alanı ve ölçülmüş yüzeyler kullanılır; gerçek
gizli kenar yoğunluğu hesaplanmış gibi gösterilmez. Şablon üzerindeki
ön tanımlı ek görünüşler sessizce göz ardı edilmez; kayıt sonrası fazladan
görünüş saptanırsa dosya başarılı sayılmaz.

Firmanın DRWDOT / SLDDRT / BOM şablonu, PDM kuralları ve ağ klasörü
davranışı canlı kabul edilmelidir. Başarılı şablon seçimi ISO 128, 129,
5456, 7200, 1101 veya 2768 uygunluğunu tek başına garanti etmez.

Bir native açınım çağrısı beklenmedik kaynak konfigürasyonu oluşturursa
dosya kaydedilmez, kuyruk durur ve kontrol mesajı verilir. Kullanıcıya ait
olabilecek konfigürasyonlar otomatik silinmez.

Gövde kimliği, Cut List üyeliği, bastırılmamış FlatPattern ve görünüşün
tek gövde kapsamı birlikte kontrol edilir. Sadece görünüş adının veya
SM-FLAT-PATTERN metninin bulunması destek kanıtı sayılmaz. Yeniden
adlandırılmış Türkçe konfigürasyonlar da özellik durumuyla değerlendirilir.
Kalınlık / malzeme kesin okunamıyorsa ortak model değeri gövdeye atanmaz.
Paftaya yazılmış bir değer işlem sırasında değişirse paket yayımlanmaz.
Gövde kimliği, kalınlığı ve malzemesi ek pafta başlığındadır. Firma anteti
ortak model / drawing property bağlantılarını kullanabilir; farklı malzemeli
gövdelerde ortak antet malzemesi ayrıca kontrol edilmeli veya şablon
uyarlanmalıdır. Bu durum çalışma raporunda WARNING olarak belirtilir.

Sac envanteri bir kaynakta en fazla 256 sac gövdesi ve 128 konfigürasyon
tarar. Cut List otomatik güncellenmez; kaynak hazır olmalıdır. Tanım erişimi
geçici rollback gerektirirse mutlaka kapatılır, eski gövde pointer’ları tekrar
kullanılmaz. Bu davranışın kaynak dirty / rebuild bayrakları üzerindeki
etkisi firma modelleriyle gerçek SolidWorks’te ayrıca kabul edilmelidir.

Girintili BOM, terfi / gizleme ve özel adet birimi kurallarında satır
miktarları basit örnek toplamı gibi onaylanmaz. Balonların tablo bağlantısı
ve numaraları denetlenir; bütün lider yerleşimi ayrıca incelenmelidir.

PASS bir imalat serbest bırakma kararı değildir. Üretim ölçüleri,
datumlar, toleranslar ve büküm bilgileri mühendislik kontrolü gerektirir.
