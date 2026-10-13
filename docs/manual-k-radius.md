# Kalınlığa göre manuel K / R atama

**K faktörü / yarıçap → Manuel K / R** sekmesinde üç değer girilir:

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
   Uygun parçalar **Uygulamaya hazır** gösterilir; “Önizleme; K/R uygulanmadı”
   açıklaması mevcut ve hedef değerleri ayırır.
4. **Montaja K/R uygula** ile eşleşen sac parçalarının sac metal parametrelerini
   güncelleyin. `2 mm → K=0.274, R=2 mm` örneğinde 1, 1.99, 2.01 ve 3 mm
   saclar atlanır; bu parçalar için K/R yazımı veya dosya kaydı yapılmaz.
5. Varsayılan değişiklik SolidWorks belleğindedir. Dosyalara da kaydetmek
   isterseniz **Parça dosyalarını kaydet** seçeneğini işaretleyin.

Gerçek uygulama sonucu **Uygulandı** gösterilir. Başarı, istenen K ve R'nin
yazılması, yeniden oluşturma ve değerlerin SolidWorks'ten geri okunmasıyla
doğrulanır. Bellekte uygulama ile dosyaya kaydetme ayrı işlemlerdir.
`128` açma bilgisi, parçanın zaten yüklü olduğunu belirtir; hata anlamına
gelmez. [Güncelleme ve yerel kontrol adımları](local-solidworks-check.md).

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

## SolidWorks 2025 hata incelemesi

Dönen COM nesnesi çağrılabilir olsa da varsayılan üyesi çağrılmaz. Büküm payının yalnız etkin türünün alanı okunur; K atamasında tür 2, K ve R yazılır. Başka türden dönüşte geri alma o türün aktif alanını geri yükler. Kalınlık filtresi eşleşmeyen saclar için K/R API erişiminden önce uygulanır. Hatalar aşama ve üye adını gösterir. Aynı `Üye bulunamadı` HRESULT davranışı test nesnesiyle yeniden üretildi; gerçek SolidWorks 2025 bu bulutta çalıştırılmadı.

[Yeni yerleşim ve kanıtlar](reports/kr-workspace-fix/README.md) · [Yerel kabul kontrolü](local-solidworks-check.md).

## 13 Ekim 2026 çağrı ve hata görünürlüğü düzeltmesi

`GetUseGaugeTable`, `GetOverrideDefaultParameter2` ve `Save3` çağrıları,
kendi COM nesnelerinde `DumbDispatch` üzerinden yapılıyor. Yalnız ana
SolidWorks nesnesini dönüştürmek yeterli değildi: alt nesneler yeniden tür
bilgisiyle oluşturulabiliyor; çıkış değerleri tuple olarak dönüyor veya
açık VARIANT çıkışlarıyla çakışıyordu. Bu durum başarılı bir sac kontrolünü
hatalı gösterebiliyor, kayıt hatasının okunmasını da etkileyebiliyordu.
[pywin32 b312 çağrı sarmalayıcısı](https://github.com/mhammond/pywin32/blob/2a277cb5552756c2b4d42b524dc36d25e0bb6354/com/win32com/client/dynamic.py#L361)
incelendi; regresyonlar test nesneleriyle doğrulandı.

Kaydedilmemiş değişiklik kontrolü artık belge etkinleştirilmeden ve
konfigürasyon değiştirilmeden önce alınır. Programın kendi geçişinin
oluşturduğu kayıt işareti atamayı engellemez; önceden bulunan kullanıcı
düzenlemeleri için kayıt koruması sürer.

Geçersiz girişle uygulama istendiğinde form görünür hale gelir ve neden
başlatılmadığı durum satırında yazılır. Parça bazında hata oluştuğunda
**Günlük** açılır. **Günlüğü kopyala**, girilen manuel değerleri, dosya adını
ve tam hata metnini birlikte kopyalar. **Hesapla ve kontrol et** sonuç
ekranından girişlere ve hesap özetine geri döner.

Bu düzeltmelerin kullanıcının montajındaki hatayı giderdiği henüz gerçek
SolidWorks oturumunda doğrulanmadı. Devam eden hatanın tam metni günlükten
alınabilir. Güncel ekranlar ve hedefli kontrol kayıtları [burada](ui-preview/README.md).
