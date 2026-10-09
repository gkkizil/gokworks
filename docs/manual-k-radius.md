# Kalınlığa göre manuel K / R atama

**K FAKTÖR - RADIUS → Manuel K / R** sekmesinde üç değer girilir:

| Alan | Örnek |
| --- | --- |
| Hedef sac kalınlığı | 2 mm |
| K faktörü | 0,274 |
| İç büküm yarıçapı R | 2 mm |

Nokta ve virgül ondalık ayırıcı olarak kabul edilir. Hedef kalınlık listeden
seçilebilir veya özel değer olarak yazılabilir. K ve R kullanıcı tarafından
doldurulur; başlangıçta bu alanlara üretim değeri atanmaz.

1. Ana montajı SolidWorks'te aktif yapın; **Manuel K / R** sekmesini açın.
2. Kalınlık, K ve R değerlerini girin.
3. **Montajı tara** ile yazma yapmadan eşleşmeleri ve önerilen değerleri görün.
4. **Montaja K/R uygula** ile eşleşen sac parçalarının sac metal parametrelerini
   güncelleyin. `2 mm → K=0.274, R=2 mm` örneğinde 1, 1.99, 2.01 ve 3 mm
   saclar atlanır; bu parçalar için K/R yazımı veya dosya kaydı yapılmaz.
5. Varsayılan değişiklik SolidWorks belleğindedir. Dosyalara da kaydetmek
   isterseniz **Parça dosyalarını kaydet** seçeneğini işaretleyin.

Aktif montajın aktif konfigürasyonu, alt montajlar dahil dolaşılır. Aynı
dosya/referans konfigürasyonu bir kez işlenir, montaj adedi raporda gösterilir.
Sac kalınlığı SolidWorks sac metal unsurundan okunur; mm hesabına çevrilir.
Birimi dönüştürürken oluşan kayan nokta hataları için sabit `0.000001 mm`
tolerans kullanılır; kalınlıklar iki ondalığa yuvarlanarak eşleştirilmez.

Girdiğiniz **K ve R aynen kullanılır**. Manuel sekme malzeme tablosu, V kalıp
tahmini, bıçak ölçüsü veya BA kalibrasyonu istemez. Malzeme/takım sekmesindeki
ayarlar ve manuel değerler ayrı saklanır; iki sekme arasında geçişte korunur.
K `0–1` aralığında; kalınlık ve R pozitif ve sonlu olmalıdır. Boş/geçersiz
alanlarla tarama ve uygulama başlatılmaz.

SolidWorks'e `KFactor=0.274`, büküm payı türü `K factor (2)` ve
`BendRadius=0.002 metre` yazılır. Mevcut sac kalınlığı değiştirilmez. Önceki
K/R sürümündeki geri okuma, rebuild, konfigürasyonların korunması, hata
halinde geri alma ve önceki montaja dönüş kontrolleri kullanılır. Çok gövdeli,
gauge/malzeme tablosuna bağlı veya özel büküm override'ı olan parçalar için
aynı destek sınırları geçerlidir; [ayrıntılar](k-factor-radius.md).

CSV raporunda başarılı, farklı kalınlık nedeniyle atlanan ve hatalı parçalar
ayrı görünür. Küçük pencerede form kaydırılabilir; tarama, uygulama ve sonuç
listesi erişilebilir kalır.

[Açık GUI](screenshots/gui-manual-k-radius-light.png) ·
[Koyu GUI](screenshots/gui-manual-k-radius-dark.png)

Linux testlerinde gerçek Tk arayüzü çalıştırıldı; SolidWorks COM sınırı test
nesneleriyle temsil edilir. Gerçek Windows/SolidWorks montajında uygulama
bu bulut ortamında çalıştırılamaz.
