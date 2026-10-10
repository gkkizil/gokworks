# GUI tasarımı ve doğrulama

Kullanıcının paylaştığı sade CRM ekranı örneği temel alındı: açık zemin, ince gri sınırlar, ikonlu yan menü, beyaz çalışma alanı ve belirgin başlıklar. Aynı düzenin koyu tema paleti de hazırlandı. PDF ve DXF/DWG aktarım ekranları vardır; DXF veya DWG tek başına seçilir. **K FAKTÖR - RADIUS** ekranında geniş Malzeme / Takım, Manuel K / R ve Montaj sonuçları sekmeleri vardır. **ISO GEÇMELERİ** bağımsız delik/mil hesap ekranıdır. **GEOMETRİK TOL.**, ASME 2018 rehberidir: 12 güncel özellik ve iki eski eğitim kartı.

## Kullanım

Yan menüden **Açık / Koyu** seçilir. Seçim beş ekranı, tabloyu, ikonları ve açık ayrıntı penceresini değiştirir; ayarlara kaydedilir. Tema değişikliği çalışan aktarımı durdurmaz, dosya listelerini/sonuçları sıfırlamaz.

Koyu tema siyah zemin kullanır: ana arka plan `#000000`, yan menü `#080808`, panel `#0B0B0B`, giriş/şema `#050505`. İkincil düğmeler ve hover nötr siyah tonlarındadır; yeşil vurgular korunur. Sekiz mevcut GUI testiyle kontrast, tema tercihi, sekmeler, ölçekler, rehber ve işlem sırasındaki tema geçişi sınandı. [Siyah tema kontrolü ve güncel ekranlar](reports/black-theme/README.md). Önceki 270 testlik rapor, önceki paletin denetim kaydıdır.

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

**301 test geçti; 103'ü gerçek Tk GUI testidir.** Yeni K/R ekranı için hesaplama, önizleme/uygulama işçisi, canlı formül güncellemesi, tercihler ve iki tema/ölçek/boyut matrisi eklendi. GUI testleri tarama/aktarım iş parçacığı akışları, CSV, tercih/sekme durumu, boş liste, Türkçe arama, canlı sonuçlarla filtre güncellemesi, filtrelenmiş satırlardan sonra tekrar tarama, ayrıntı/pano, tema tercihi ve yeniden yükleme, işlem sırasında tema değiştirme/kapanış ve küçük pencereyi kapsar. Son eklenen testler tek biçim üretimini, eski birleşik ayarın dönüşümünü, hızlı menü geçişlerini, tercih kaydı tekrarını ve büyük listelerin olay sırasını kontrol eder. Windows'un tüm monitör/DPI kombinasyonları burada çalıştırılmadı.

Yeni liste filtrelerinde görünmeyen satırlar Tk tablosundan silinmez, ayrılır. Yeniden taramada bu satırlar da temizlenir; eski `file_n` kimlikleri yeni listeyle çakışmaz. Aktarımın mevcut testleri korunmuştur. [Son test çıktısı](test-results/latest-tests.log); önceki sürümün [tam program raporu](program-verification.md) tarihsel kayıttır.

Çalışan uygulamadan 1240×860 boyutunda alınan gerçek ekran görüntüleri:

| Ekran | Açık | Koyu |
| --- | --- | --- |
| DXF/DWG | [Görüntü](reports/kr-workspace-fix/screenshots/dxf-dwg-light.png) | [Görüntü](reports/kr-workspace-fix/screenshots/dxf-dwg-dark.png) |
| PDF | [Görüntü](reports/kr-workspace-fix/screenshots/pdf-light.png) | [Görüntü](reports/kr-workspace-fix/screenshots/pdf-dark.png) |
| K/R Manuel | [Görüntü](reports/kr-workspace-fix/screenshots/k-factor-manual-light.png) | [Görüntü](reports/kr-workspace-fix/screenshots/k-factor-manual-dark.png) |
| K/R Takım | [Görüntü](reports/kr-workspace-fix/screenshots/k-factor-light.png) | [Görüntü](reports/kr-workspace-fix/screenshots/k-factor-dark.png) |
| ISO | [Görüntü](reports/kr-workspace-fix/screenshots/iso-fits-light.png) | [Görüntü](reports/kr-workspace-fix/screenshots/iso-fits-dark.png) |
| ISO Mil esaslı | [Görüntü](reports/kr-workspace-fix/screenshots/iso-fits-shaft-basis-light.png) | [Görüntü](reports/kr-workspace-fix/screenshots/iso-fits-shaft-basis-dark.png) |
| GD&T | [Görüntü](reports/kr-workspace-fix/screenshots/geometric-tolerances-light.png) | [Görüntü](reports/kr-workspace-fix/screenshots/geometric-tolerances-dark.png) |

[Manuel ISO H6 referansı](reports/kr-workspace-fix/screenshots/iso-fits-manual-h6-dark.png), [tam H8 eşleşmesi](reports/kr-workspace-fix/screenshots/iso-fits-manual-h8-dark.png) ve [tablo kontrolü](reports/kr-workspace-fix/screenshots/iso-fits-manual-comparison-dark.png).

## Kod satırı sayısı

| Kapsam | Python dosyası | Toplam satır | Boş olmayan satır |
| --- | ---: | ---: | ---: |
| Uygulama | 28 | 4.940 | 4.499 |
| Testler | 15 | 4.717 | 4.201 |
| Toplam | 43 | 9.657 | 8.700 |

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

## Tam yükseklikte çalışma alanları — 10.10.2026

PDF/DXF ayarları soldaki bağımsız kaydırılan formda, tablo/günlük sağdaki tam yükseklikte sonuç alanındadır. Form kaydırılırken tablo yüksekliği değişmez. K/R ekranı aşağıdaki yeni sekmeli düzene geçti. ISO ve GD&T kendi hesap/şema düzenlerini korur. Dar sonuç panelinde arama ve filtreler iki satıra geçer; başlık ve ipuçları alan genişliğine uyar.

CustomTkinter ölçeklemesinin eski grid konumlarını yeniden yüklediği sekme geçişi giderildi. ISO filtre değişiminde liste kaydırması başa alınır; kısa mil esaslı listede önceki uzun listenin boş alanı görünmez. Tümü görünümünde delik ve mil esaslı örnekler dönüşümlü gösterilir. [Son 19 gerçek ekran ve Word/test kanıtları](reports/kr-workspace-fix/README.md). Önceki raporlar tarihsel tasarımı gösterir.

## Güncel K/R alanı ve menü geçişleri

K/R için form ve tablo aynı anda dar sütunlara sıkıştırılmaz. 48 px sekme seçimi kaydırma dışında kalır; malzeme/takım ve manuel alanlar tüm genişliği kullanır. Girişler 42 px yüksekliğindedir. Montaj sonuçları sekmesi tam genişlikte dosya/günlük alanını açar. Montajı tara, Hesapla ve kayıt seçeneği üç görünümde de sabittir. İki tema, 1000×690 minimum pencere ve %125/%150 ölçekler test edilir.

Yan menü vurgusu kısa renk geçişi kullanır; sayfa içeriği hemen açılır. Tercih yazımı 250 ms ertelenir; hızlı geçişte ayrılan sayfaların değerleri birleştirilir, işlem başlatılırken/kapanırken kaydedilir. Büyük dosya listeleri kısa gruplarla eklenir, işçi olayları sınırlı sürelerle tüketilir; Durdur ve diğer Tk olaylarına sıra verilir.

Güncel gerçek ekranlar: [takım](screenshots/gui-current-kr-tools-dark.png), [manuel koyu](screenshots/gui-current-kr-manual-dark.png), [manuel açık](screenshots/gui-current-kr-manual-light.png), [küçük pencere](screenshots/gui-current-kr-manual-small.png), [montaj sonuçları](screenshots/gui-current-kr-results-dark.png), [tek biçim DXF/DWG](screenshots/gui-current-dxf-dwg-dark.png). Bu görüntüler çalışan Tk arayüzünden alındı; SolidWorks çıktısını kanıtlamaz. Önceki Word raporları kendi sürümlerinin kayıtlarıdır.
