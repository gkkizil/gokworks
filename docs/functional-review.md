# Uygulamanın işleyiş incelemesi — 13 Ekim 2026

Bu inceleme hesap, belge seçimi, tarama, çıktı üretimi ve durdurma akışlarını
kapsar. Kaynak kodu altı modülde incelendi; yalnız değişen akışlara yönelik
testler çalıştırıldı. Windows/SolidWorks bu ortamda bulunmuyor.

## Düzeltilen davranışlar

| Akış | Bulgu | Değişiklik |
| --- | --- | --- |
| Kontrol sürerken sıraya alınan K/R uygulaması | Uygulama çalışanı etkin montajı yeniden okuyordu; başka montaja geçilmişse kontrol edilmemiş hedefe yazabiliyordu. | Önizlemenin montaj yolu, ana konfigürasyonu ve dosya/konfigürasyon adetleri korunuyor. Uygulama öncesinde karşılaştırılıyor; değişiklik varsa parça yazımı ve kaydı başlamıyor. |
| DXF/DWG ve çoklu konfigürasyon | Etkin parça konfigürasyonu aktarılıyor, montajda kullanılan diğer konfigürasyonlar sonuçta belirtilmiyordu. | Aktarılmayan konfigürasyonlar özgün adları ve adetleriyle sonuç/CSV açıklamasına ekleniyor; bitiş özeti uyarı gösteriyor. |
| BOM durdurma | Excel satırları biçimlendirilirken iptal kontrolü yoktu. Daha başlamadan iptal edilmiş tarama da SolidWorks bağlantısına girişiyordu. | Excel biçimlendirmesinde her satırda iptal kontrol ediliyor. Önceden iptal edilmiş tarama COM bağlantısını başlatmıyor. |

## Modüllerin mevcut işleyişi

| Modül | Kaynak ve işlem | Sonuç ve sınırlar |
| --- | --- | --- |
| PDF | Kaynak klasördeki `.SLDDRW` dosyaları taranır. Her teknik resmin bütün sayfaları seçilir; alt klasör düzeni korunur. | Her resim tek PDF olur. Başlık ve dosya sonu kontrol edilen geçici dosya hedefe taşınır. Bu kontrol çizim ölçülerini veya PDF içeriğinin tamamını doğrulamaz. |
| DXF/DWG | Etkin ana montajın alt montajları dahil fiziksel adetler sayılır. Kaynak klasördeki parçaların yalnız etkin konfigürasyonu aktarılır. | Ad: parça adı, sac kalınlığı ve adet. Tek gövdeli sac gerekir. DXF ayrıştırılır; DWG için başlık/boyut kontrolü vardır. Diğer konfigürasyonlar otomatik dolaşılmaz; aynı kalınlık/adette ad çakışabileceğinden ayrı çıktı klasörleri gerekir. |
| K/R | Her dosya ve referans konfigürasyon bir kez işlenir. Manuel mod hedef kalınlığı eşleştirir; otomatik mod malzeme ve takıma göre hesaplar. | Önizleme yazmaz. Uygulama değerleri geri okuyarak kontrol eder; varsayılan işlem bellektedir, kayıt ayrıca seçilir. Hata geri alma işlemi parça bazındadır. Durdur, daha önce tamamlanan parçaları geri almaz. |
| BOM | Etkin montaj örnekleri hiyerarşik dolaşılır. Tekrarlanan alt montajların her kullanımındaki parçalar sayılır; dosya/konfigürasyon birlikte gruplanır. | Excel'de sıralı parça listesi ve ayrı ürün ağacı vardır. Bastırılmış dallar atlanır; BOM dışı parçalar seçeneğe bağlıdır. Arama yalnız ekrandaki listeyi filtreler, Excel tüm tarama sonucunu içerir. |
| ISO geçmeler | Nominal çap ve sınıflar veya manuel alt/üst sapmalar kullanılır. Sapmalar tam sayı nanometre olarak hesaplanır. | Boşluk/sıkılık sınırları, sınıf karşılaştırması ve CSV/pano sonucu verir. Doğrulanan tablo aralığı 1–400 mm'dir. SolidWorks modelini değiştirmez. |
| Geometrik toleranslar | Seçilen özellik, tolerans, datum ve isteğe bağlı ölçülmüş toplam hata değerlendirilir. | Girilen toplam hata toleransla karşılaştırılır. Rehber ve rapor üretir; CAD modeline tolerans yazmaz veya CMM ölçüm analizi yapmaz. |

PDF/DXF mevcut çıktıları varsayılan olarak atlar; üzerine yazma seçiliyse yeni
dosya doğrulandıktan sonra hedef değiştirilir. BOM Excel dosyası da geçici
dosyadan yayımlanır. SolidWorks'ün devam eden COM çağrısı zorla kesilmez;
Excel'in ZIP dosyasına yazma çağrısı sırasında iptal gelirse yazma dönüşünde
kontrol edilir ve hedef dosya değiştirilmez.

## Doğrulama

17 hedefli test geçti: 5 yeni test ve 12 ilgili akış kontrolü.
İki kontrol gerçek Tk arayüzünü çalıştırdı. Montaj/konfigürasyon değişimi,
parça yolu/adet değişimi, aynı içerikte farklı ağaç sırası, sıraya alınan
uygulama ve iptal, Excel'in mevcut dosyayı koruması ve DXF adet/çıktı
davranışı sınandı. COM çağrılarında test nesneleri kullanıldı; gerçek CAD
dosyalarının geometrisi veya Windows/SolidWorks davranışı burada doğrulanmadı.

PDF, ISO ve geometrik toleranslarda bu kaynak incelemesinde ek hata
saptanmadı; değişiklik yapılmadığı için testleri yeniden çalıştırılmadı.
