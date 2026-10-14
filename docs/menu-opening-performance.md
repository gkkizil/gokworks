# Menü geçişleri — 14 Ekim 2026

Yeni sayfalar, bütün kontrolleri hazırlandıktan sonra görünür oluyor. Kurulum sırasında mevcut ekran açık kalıyor; arka planda hazırlanan sayfalar hiç görünür yapılmıyor. Böylece CustomTkinter'ın kurulum sırasında çalıştırdığı yerleşim işlemleri, yarım sayfayı tekrar tekrar pencereye yerleştirmiyor.

Aynı olay kuyruğunda biriken menü tıklamaları son seçime birleştiriliyor. Hazır sayfalar ve girilmiş değerler korunuyor. İşlem başladığında veya pencere kapandığında bekleyen geçiş uygulanmıyor. Sayfa oluşturulamazsa mevcut ekranın verileri ve yerleşimi geri yükleniyor. Kapanış sırasında yeni yerleşim zamanlayıcıları oluşturulması da engellendi.

## Ölçüm

Başlangıç: `7ffd15d`. Python 3.13.5, Tk 8.6.16, CustomTkinter 6.0.0 ve Linux/Xvfb üzerinde üç tur, aynı bağımlılıklar ve ekran kullanıldı. SolidWorks çalıştırılmadı. Font yüklenemediği için her iki ölçümde de CTk'nin `circle_shapes` çizimi kullanıldı. Windows süreleri farklı olabilir.

| İşlem | Önce | Sonra |
| --- | ---: | ---: |
| İlk sayfa çizimi, medyan | 121,33 ms | 108,35 ms |
| Gizli sayfa hazırlama, medyan | 105,49 ms | 72,92 ms |
| Hazır sayfalar arası geçiş, medyan | 4,55 ms | 4,24 ms |
| Altı tıklamalık kuyruk, medyan | 825,82 ms | 120,55 ms |
| Bu kuyrukta oluşturulan yeni sayfa | 6 | 1 |

Çizim ölçümleri `update_idletasks()` içerir; gecikmeli yerleşim çağrılarının ve menü renk animasyonunun tamamlanmasını içermez. Kuyruk ölçümünde altı düğme, olay döngüsüne dönmeden art arda çağrılır. Bu sonuç, kullanıcının aralıklı altı tıklamasının süresi değildir; bekleyen tıklamaların gereksiz sayfa kurulumlarına dönüşmesini ölçer.

İlk açılış kazanımı sayfaya göre değişiyor: K/R 181 → 146 ms, BOM 113 → 94 ms; geometrik toleranslar 104 → 110 ms. Sayfa kurulumu hâlâ Tk ana iş parçacığında; tüm ilk açılışlar tek çizim karesine sığmıyor. [Ham sonuçlar](test-results/menu-opening.json) bütün sayfaları içerir.

## Kontrol

19 ilgili GUI kontrolü geçti: biriken tıklamalar, mevcut sayfaya geri dönüş, doğrudan geçiş, işlem/kapanış sırasında bekleyen geçiş, sayfa oluşturma hatasından dönüş, gizli hazırlama, veri ve ayarların korunması, menü vurgusu, diyagramlar, tema, DPI ve çalışma alanı boyutları. İlk çalışmadaki test sınıfı adı ve CTk yerine doğrudan Tk olay bağlama düzeltildi; ilgili üç kontrol tekrar geçti. Tüm test paketi çalıştırılmadı.

Ölçümü çalıştırmak için, Tk bağımlılıkları ve sanal ekran hazırken:

```bash
DISPLAY=:99 python docs/report-tools/benchmark_menu_opening.py /tmp/menu-opening.json
```
