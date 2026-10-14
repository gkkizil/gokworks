# Astra proje incelemesi — 14 Ekim 2026

İnceleme modeli: **GPT-6 Astra**. Kapsam: PDF, DXF/DWG, K/R, BOM, isimlendirme,
cıvata, ISO geçmeler, geometrik toleranslar, SolidWorks bağlantısı, ortak GUI,
ayarlar, işçi yaşam döngüsü, giriş noktası ve Windows paketleme iş akışı.

## Doğrulanan ve düzeltilen sorunlar

| Alan | Tetikleyen durum ve eski sonuç | Düzeltme |
| --- | --- | --- |
| K/R kayıt sırası | Aynı açık parçanın iki konfigürasyonuna kayıtlı atama. İlk kayıt sonrası eski konfigürasyona dönüş belgeyi yeniden değişmiş gösteriyor; ikinci atama önceden kaydedilmemiş değişiklik gerekçesiyle duruyordu. | Kullanıcının başlangıç konfigürasyonuna son kayıttan önce dönülür. Gerçek önceden kaydedilmemiş değişiklikler yine korunur. |
| PDF ve DXF/DWG belge sahipliği | `OpenDoc6`, zaten açık belgeyi `AlreadyOpen (128)` uyarısıyla döndürdüğünde aktarım sonunda kullanıcı belgesi kapatılıyordu. | Uyarı biti denetlenir; mevcut belge açık tutulur. Açma sırasında etkin belge değişmişse önceki belgeye dönülür. Başarı ve açma hatası yolları kontrol edildi. |
| İsimlendirme önizlemesi | Ön eki değiştirip 150 ms içinde başka menüye geçince tablo yeni adları gösteriyor, sayfa önbelleğindeki plan eski adları taşıyordu. Elle düzenleme eski adla açılıyordu. | Bekleyen önizleme sayfa durumu saklanmadan tamamlanır; doğrudan güncellemede eski zamanlayıcı iptal edilir. Tablo, plan ve düzenleme penceresi aynı adı kullanır. |

K/R, cıvata, ISO ve geometrik tolerans hesaplarında desteklenen kapsam içinde
başka doğrulanmış formül hatası bulunmadı. BOM ağırlık/toplam mantığı, Pack and Go
dosya referansı doğrulamaları, kaynak/çıktı koruması ve iptal/temizlik yolları da
incelendi. Bu ifade gerçek SolidWorks geometrisi için kabul testi anlamına gelmez.

## Depo ve paket temizliği

- Çalışan kod tarafından kullanılmayan 6 eski kaynak yedeği (`backups/`) ve
  5 IDE dosyası (`.idea/`) kaldırıldı. Önceki sürümler Git geçmişinde durur.
- Yerel IDE klasörleri, yedekler ve `.env.*` dosyaları için yok sayma kuralları eklendi.
- Paketleme, tüm `gui/assets/` klasörü yerine gerekli JPG ve ICO dosyalarını alır.
  Kaynak açıklama dosyası EXE'ye eklenmez.
- Kullanım belgeleri, örnek Excel dosyaları, ekran görüntüleri ve test kaynakları
  depoda tutulur; uygulama EXE'sine zaten eklenmezler.

## Kontroller ve sınırlar

Üç hata önce odaklı senaryolarla yeniden üretildi. Düzeltmelerden sonra **19 ilgili
kontrol geçti**: 7 K/R kayıt/konfigürasyon/geri alma, 8 PDF/DXF belge yaşam döngüsü,
4 gerçek Tk isimlendirme/menü/tema/ölçek kontrolü. Tam test paketi çalıştırılmadı.

İnceleme başlamadan önce kullanıcı isteğiyle hazırlanan
[Windows EXE paketi](https://github.com/gkkizil/gokworks/actions/runs/38527091279/artifacts/11876681375)
sekiz ekranın gerçek Windows açılış kontrolünden geçti. Uygulama kaynağı `9fa08d6`,
derleme dalı commit'i `1fe90e8` idi. **Bu paket yukarıdaki inceleme düzeltmelerinden
önce oluşturuldu.** Bu düzeltmeler için ikinci EXE derlemesi başlatılmadı.

SolidWorks COM sınırı yerel kontrollerde test nesneleriyle temsil edildi. Gerçek
Windows/SolidWorks'te K/R yazma ve geri alma, model/montaj rebuild sonuçları,
mate çözümü, teknik resim görünüşleri ve canlı kütle değerlerinin doğrulanması
halen yerel kabul kontrolü gerektirir.
