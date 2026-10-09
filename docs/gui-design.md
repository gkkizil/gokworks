# GUI tasarımı ve doğrulama

Kullanıcının paylaştığı sade CRM ekranı örneği temel alındı: açık zemin, ince gri sınırlar, ikonlu yan menü, beyaz çalışma alanı ve belirgin başlıklar. Aynı düzenin koyu tema paleti de hazırlandı. PDF ve DXF/DWG aktarım seçenekleri korunuyor; **K FAKTÖR - RADIUS** etkin; Malzeme / Takım ve Manuel K / R alt sekmeleri vardır. **ISO GEÇMELERİ** bağımsız delik/mil hesap ekranıdır. **GEOMETRİK TOL.**, ASME 2018 rehberidir: 12 güncel özellik ve iki eski eğitim kartı.

## Kullanım

Yan menüden **Açık / Koyu** seçilir. Seçim beş ekranı, tabloyu, ikonları ve açık ayrıntı penceresini değiştirir; ayarlara kaydedilir. Tema değişikliği çalışan aktarımı durdurmaz, dosya listelerini/sonuçları sıfırlamaz.

Sonuç alanına Türkçe dosya adı/açıklama araması, durum filtresi ve görünen/toplam dosya sayısı eklendi. Filtreler yalnızca görünümü etkiler. Yeni tarama/aktarım filtreleri sıfırlar; PDF ve DXF/DWG geçişleri filtreleri bağımsız korur. İş parçacığından gelen sonuç, aktif filtreye göre kendi satırını günceller; tüm tablo her sonuçta yeniden çizilmez.

Dosyaya çift tıklama veya seçili dosyada Enter, tam kaynak/çıktı yollarını ve aktarım açıklamasını açar. Ayrıntıların panoya kopyalanması desteklenir. Pano sahipliği ana uygulamada tutulur; ayrıntı penceresini kapatmak kopyalanan bilgiyi kaybettirmez. Pencere kapanırken CustomTkinter zamanlayıcıları iptal edilir. İlk incelemedeki kapanış sonrası Tcl `invalid command name` hatası bu şekilde giderildi.

## Dosyalar ve bağımlılıklar

| Dosya | Görevi |
| --- | --- |
| `gui/theme.py` | Ortak açık/koyu renk çiftleri ve platform yazı tipleri. |
| `gui/icons.py` | Pillow ile çizilen özgün ikonlar; tema ve ölçek için iki görüntülü CTkImage nesneleri. |
| `gui/layout.py` | Yan menü, başlık, ayarlar, sayaçlar, sonuç tablosu ve tablo teması. |
| `iso_fits/window.py`, `diagram.py`, `rules.py`, `tables.json` | ISO delik/mil hesabı, kesit/bölge grafiği, çap aralıkları ve sayısal veri. |
| `geometric_tolerances/` | ASME 12 güncel/2 eski özellik kataloğu, açık tolerans/hata kontrolü, vektör sembol/şema ve rehber ekranı. |
| `pdf/window.py` | Ekran durumu, iş parçacığı olayları, filtreleme, tema tercihi, ayrıntılar ve rapor akışı. |

`Pillow==12.1.0` kuruldu ve `requirements.txt` içine eklendi. Mevcut `customtkinter==6.0.0` kullanılıyor. İkonlar uygulama tarafından çiziliyor; çevrimiçi ikon servisine veya ayrı ikon yazı tipine bağımlılık yok. Bulut kurulum scripti ve başlangıç talimatları yeni bağımlılıkla güncellendi.

## Doğrulama

**270 test geçti; 84'ü gerçek Tk GUI testidir.** Yeni K/R ekranı için hesaplama, gerçek önizleme/uygulama işçisi, canlı formül güncellemesi, tercihler ve iki tema/ölçek/boyut matrisi eklendi. GUI testleri tarama/aktarım iş parçacığı akışları, CSV, tercih/sekme durumu, boş liste, Türkçe arama, canlı sonuçlarla filtre güncellemesi, filtrelenmiş satırlardan sonra tekrar tarama, ayrıntı/pano, tema tercihi ve yeniden yükleme, işlem sırasında tema değiştirme/kapanış ve küçük pencereyi kapsar. %125 widget ölçeklemesinde tablo yazısının büyümesi, iki tema ve iki ekranın çalışması da sınandı. Windows'un tüm monitör/DPI kombinasyonları burada çalıştırılmadı.

Yeni liste filtrelerinde görünmeyen satırlar Tk tablosundan silinmez, ayrılır. Yeniden taramada bu satırlar da temizlenir; eski `file_n` kimlikleri yeni listeyle çakışmaz. Aktarımın mevcut testleri korunmuştur. [Tam program raporu](program-verification.md) ve [son test çıktısı](reports/gdt-dimension-audit/test-run.log).

Çalışan uygulamadan 1240×860 boyutunda alınan gerçek ekran görüntüleri:

| Ekran | Açık | Koyu |
| --- | --- | --- |
| DXF/DWG | [Görüntü](reports/final-audit/screenshots/dxf-dwg-light.png) | [Görüntü](reports/final-audit/screenshots/dxf-dwg-dark.png) |
| PDF | [Görüntü](reports/final-audit/screenshots/pdf-light.png) | [Görüntü](reports/final-audit/screenshots/pdf-dark.png) |
| K FAKTÖR - RADIUS / Manuel | [Görüntü](reports/final-audit/screenshots/manual-k-radius-light.png) | [Görüntü](reports/final-audit/screenshots/manual-k-radius-dark.png) |
| ISO GEÇMELERİ | [Görüntü](reports/fit-compatibility/screenshots/iso-light.png) | [Görüntü](reports/fit-compatibility/screenshots/iso-dark.png) |
| ISO / Manuel kontrol | [Görüntü](reports/fit-compatibility/screenshots/iso-manual-light.png) | [Görüntü](reports/fit-compatibility/screenshots/iso-manual-dark.png) |
| GEOMETRİK TOL. | [Görüntü](reports/geometric-tolerances/screenshots/gdt-light.png) | [Görüntü](reports/geometric-tolerances/screenshots/gdt-dark.png) |
| K FAKTÖR - RADIUS / Takım | [Görüntü](reports/final-audit/screenshots/k-radius-light.png) | [Görüntü](reports/final-audit/screenshots/k-radius-dark.png) |

## Kod satırı sayısı

| Kapsam | Python dosyası | Toplam satır | Boş olmayan satır |
| --- | ---: | ---: | ---: |
| Uygulama | 27 | 4.627 | 4.212 |
| Testler | 11 | 4.050 | 3.620 |
| Toplam | 38 | 8.677 | 7.832 |

Fiziksel satırlar sayıldı; yorumlar ve boş satırlar toplam satıra dahildir. Uygulama kapsamı `main.py`, `pdf/`, `dxf_dwg/`, `solidworks/`, `k_factor/`, `gui/`, `iso_fits/`, `geometric_tolerances/` altındaki Python dosyalarıdır. Test kapsamı `tests/` altındaki Python dosyalarıdır. `.venv`, üçüncü taraf kütüphaneler, `backups/`, belgeler, ISO veri JSON'u ve DXF örnekleri sayılmadı. Bu değerler GUI çalışması tamamlandığı andaki sayımdır.

Son yeniden denetimde 12 ek GUI kabul testi eklendi. İlk yerleşim zamanlaması açıkça başlatıldı. Sonuçlar ve kapsam sınırları [Word raporunda](reports/GOKWORKS_GUI_Test_Raporu_2026-10-09.docx); test bazlı kanıtlar [rapor dizininde](reports/README.md). Satır sayıları bu yeniden denetim sonrası güncellenmiştir; rapor üretim araçları uygulama/test sayımına dahil değildir.

K/R güncel ekranında Montajı tara, Hesapla ve dosya kayıt seçimi kaydırılan formun dışındadır. Seçilen malzeme tüm saclara varsayılır; parametreler değiştikçe numune hesabı yenilenir. [Yeni Word raporu](reports/k-radius/GOKWORKS_K_RADIUS_GUI_Raporu_2026-10-09.docx); eski rapor K/R öncesi denetimin kaydıdır.

Son manuel eklemede 15 test çalıştırıldı. Form alanları küçük pencerede kaydırılarak erişilebilir; tarama/uygulama ve sonuç listesi görünür kalır. [189 testlik kanıt](reports/manual-k-radius/README.md). Önceki Word raporları kendi sürümlerinin tarihsel kayıtlarıdır.

ISO öncesi denetim: 112 yerleşim kombinasyonu, 144 gerçek menü seçimi ve %150 ölçek dahil 49 GUI testi geçti. Yeşil vurgu korundu. Desteklenen ekranlarda ilk pencere mevcut ölçülere göre seçilir. [ISO öncesi Word raporu, ekranlar ve kanıtlar](reports/final-audit/README.md).

ISO eklemesinde 8 hesap ve 9 GUI testi eklendi. İki tema, 5 boyut/ölçek, 31 delik/mil/birim menü seçeneği, 14 eşleşme, iki grafik, üç örnek ölçü, CSV/pano, hatalı giriş ve yeniden açılış sınandı. Tolerans bölgeleri gerçek sapma ölçeğini, montaj kesiti sabit büyütmeyle şematik gösterimi kullanır. [Güncel ISO raporu ve kaynak sınırları](reports/iso-fits/README.md).

ISO sol panelinde **ISO seçimi / Manuel kontrol** menüsü bulunur. Manuel girişte dört sapma alanı, canlı geçme sonucu, tam/en yakın ISO sınıfı ve farklar; mm/µm, örnek doldurma, CSV ve pano desteklenir. 14 ek test (8 hesap, 6 GUI) geçti. %100/%125/%150, iki tema, alanlara ve karşılaştırmaya kaydırarak erişim sınandı. [Güncel manuel rapor ve resimler](reports/manual-iso/README.md).

Manuel kontrolde Montaj hedefi menüsü ve MONTAJ UYUMU / EN YAKIN GEÇME kartı eklendi. Yeni kart farklı referans/gerçek geçme türünü, sınırda teması ve büyük limit farklarını açıklar. 6 hesap + 4 GUI testi daha geçti; CSV/pano ve hedef tercihi desteklenir. [Güncel kart görüntüsü](reports/fit-compatibility/screenshots/iso-compatibility-dark.png) ve [240 testlik güncel rapor](reports/fit-compatibility/README.md).

GD&T eklemesinde 10 hesap/içerik ve 11 GUI testi geçti. 12 güncel türün iki temada çizimi, iki kaldırılmış kartın çıktı engeli ve Rule #1 boyut ilişkisi, datum menüleri, arama, CSV/pano, hatalı giriş, ölçüm temizliği, rehber ve %100/%125/%150 alan erişimi kontrol edildi. [261 testlik son rapor](reports/geometric-tolerances/README.md).

GD&T ölçü denetiminde 9 regresyon testi eklendi: gerçek 45° ve normal ok, tam çap oku, normal yönde eşit profil sınırları, teknik çerçevede ASME ondalık noktası ve uzun sayıların iki tema/üç ölçekte hücreye sığması. Özelliğe göre ölçüm açıklamaları ve profil ±t/2 payı eklendi. [270 testlik güncel rapor](reports/gdt-dimension-audit/README.md).
