# GUI tasarımı ve doğrulama

Kullanıcının paylaştığı sade CRM ekranı örneği temel alındı: açık zemin, ince gri sınırlar, ikonlu yan menü, beyaz çalışma alanı ve belirgin başlıklar. Aynı düzenin koyu tema paleti de hazırlandı. PDF ve DXF/DWG aktarım seçenekleri korunuyor; **K FAKTÖR - RADIUS** etkin; Malzeme / Takım ve Manuel K / R alt sekmeleri vardır.

## Kullanım

Yan menüden **Açık / Koyu** seçilir. Seçim üç ekranı, tabloyu, ikonları ve açık ayrıntı penceresini değiştirir; ayarlara kaydedilir. Tema değişikliği çalışan aktarımı durdurmaz, dosya listelerini/sonuçları sıfırlamaz.

Sonuç alanına Türkçe dosya adı/açıklama araması, durum filtresi ve görünen/toplam dosya sayısı eklendi. Filtreler yalnızca görünümü etkiler. Yeni tarama/aktarım filtreleri sıfırlar; PDF ve DXF/DWG geçişleri filtreleri bağımsız korur. İş parçacığından gelen sonuç, aktif filtreye göre kendi satırını günceller; tüm tablo her sonuçta yeniden çizilmez.

Dosyaya çift tıklama veya seçili dosyada Enter, tam kaynak/çıktı yollarını ve aktarım açıklamasını açar. Ayrıntıların panoya kopyalanması desteklenir. Pano sahipliği ana uygulamada tutulur; ayrıntı penceresini kapatmak kopyalanan bilgiyi kaybettirmez. Pencere kapanırken CustomTkinter zamanlayıcıları iptal edilir. İlk incelemedeki kapanış sonrası Tcl `invalid command name` hatası bu şekilde giderildi.

## Dosyalar ve bağımlılıklar

| Dosya | Görevi |
| --- | --- |
| `gui/theme.py` | Ortak açık/koyu renk çiftleri ve platform yazı tipleri. |
| `gui/icons.py` | Pillow ile çizilen özgün ikonlar; tema ve ölçek için iki görüntülü CTkImage nesneleri. |
| `gui/layout.py` | Yan menü, başlık, ayarlar, sayaçlar, sonuç tablosu ve tablo teması. |
| `pdf/window.py` | Ekran durumu, iş parçacığı olayları, filtreleme, tema tercihi, ayrıntılar ve rapor akışı. |

`Pillow==12.1.0` kuruldu ve `requirements.txt` içine eklendi. Mevcut `customtkinter==6.0.0` kullanılıyor. İkonlar uygulama tarafından çiziliyor; çevrimiçi ikon servisine veya ayrı ikon yazı tipine bağımlılık yok. Bulut kurulum scripti ve başlangıç talimatları yeni bağımlılıkla güncellendi.

## Doğrulama

**189 test geçti; 44'ü gerçek Tk GUI testidir.** Yeni K/R ekranı için hesaplama, gerçek önizleme/uygulama işçisi, canlı formül güncellemesi, tercihler ve iki tema/ölçek/boyut matrisi eklendi. GUI testleri tarama/aktarım iş parçacığı akışları, CSV, tercih/sekme durumu, boş liste, Türkçe arama, canlı sonuçlarla filtre güncellemesi, filtrelenmiş satırlardan sonra tekrar tarama, ayrıntı/pano, tema tercihi ve yeniden yükleme, işlem sırasında tema değiştirme/kapanış ve küçük pencereyi kapsar. %125 widget ölçeklemesinde tablo yazısının büyümesi, iki tema ve iki ekranın çalışması da sınandı. Windows'un tüm monitör/DPI kombinasyonları burada çalıştırılmadı.

Yeni liste filtrelerinde görünmeyen satırlar Tk tablosundan silinmez, ayrılır. Yeniden taramada bu satırlar da temizlenir; eski `file_n` kimlikleri yeni listeyle çakışmaz. Aktarımın mevcut testleri korunmuştur. [Tam program raporu](program-verification.md) ve [son test çıktısı](test-results/latest-tests.log).

Çalışan uygulamadan 1240×860 boyutunda alınan gerçek ekran görüntüleri:

| Ekran | Açık | Koyu |
| --- | --- | --- |
| DXF/DWG | [Görüntü](screenshots/gui-current-dxf-dwg-light.png) | [Görüntü](screenshots/gui-current-dxf-dwg-dark.png) |
| PDF | [Görüntü](screenshots/gui-current-pdf-light.png) | [Görüntü](screenshots/gui-current-pdf-dark.png) |
| K FAKTÖR - RADIUS / Manuel | [Görüntü](screenshots/gui-manual-k-radius-light.png) | [Görüntü](screenshots/gui-manual-k-radius-dark.png) |

## Kod satırı sayısı

| Kapsam | Python dosyası | Toplam satır | Boş olmayan satır |
| --- | ---: | ---: | ---: |
| Uygulama | 17 | 2.788 | 2.539 |
| Testler | 7 | 2.753 | 2.434 |
| Toplam | 24 | 5.541 | 4.973 |

Fiziksel satırlar sayıldı; yorumlar ve boş satırlar toplam satıra dahildir. Uygulama kapsamı `main.py`, `pdf/`, `dxf_dwg/`, `solidworks/`, `k_factor/`, `gui/` altındaki Python dosyalarıdır. Test kapsamı `tests/` altındaki Python dosyalarıdır. `.venv`, üçüncü taraf kütüphaneler, `backups/`, belgeler ve DXF örnekleri sayılmadı. Bu değerler GUI çalışması tamamlandığı andaki sayımdır.

Son yeniden denetimde 12 ek GUI kabul testi eklendi. İlk yerleşim zamanlaması açıkça başlatıldı. Sonuçlar ve kapsam sınırları [Word raporunda](reports/GOKWORKS_GUI_Test_Raporu_2026-10-09.docx); test bazlı kanıtlar [rapor dizininde](reports/README.md). Satır sayıları bu yeniden denetim sonrası güncellenmiştir; rapor üretim araçları uygulama/test sayımına dahil değildir.

K/R güncel ekranında Montajı tara, Hesapla ve dosya kayıt seçimi kaydırılan formun dışındadır. Seçilen malzeme tüm saclara varsayılır; parametreler değiştikçe numune hesabı yenilenir. [Yeni Word raporu](reports/k-radius/GOKWORKS_K_RADIUS_GUI_Raporu_2026-10-09.docx); eski rapor K/R öncesi denetimin kaydıdır.

Son manuel eklemede 15 test çalıştırıldı. Form alanları küçük pencerede kaydırılarak erişilebilir; tarama/uygulama ve sonuç listesi görünür kalır. [189 testlik kanıt](reports/manual-k-radius/README.md). Önceki Word raporları kendi sürümlerinin tarihsel kayıtlarıdır.
