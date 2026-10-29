# GUI tasarımı ve doğrulama

> Eski Tk arayüzü için verilen görsel/rapor komutları tarihîdir. Bu betikler ve
> üretilmiş görseller güncel daldan kaldırılmıştır; yeniden incelemek için
> [temizlik öncesi sürümü](https://github.com/gkkizil/gokworks/tree/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9) kullanın.

Kullanıcının paylaştığı sade CRM ekranı örneği temel alındı: açık zemin, ince gri sınırlar, ikonlu yan menü, beyaz çalışma alanı ve belirgin başlıklar. Aynı düzenin koyu tema paleti de hazırlandı. PDF ve DXF/DWG aktarım ekranları vardır; DXF veya DWG tek başına seçilir. **K FAKTÖR - RADIUS** ekranında geniş Malzeme / Takım, Manuel K / R ve Montaj sonuçları sekmeleri vardır. **ISO GEÇMELERİ** bağımsız delik/mil hesap ekranıdır. **Geometrik tolerans**, ASME 2018 rehberidir: 12 güncel özellik ve iki eski eğitim kartı.

## Son görsel düzenleme

Yan menü dışa aktarım ve mühendislik olarak ayrıldı; GD&T için ayrı hedef ikonu kullanıldı. İç içe ayar çerçeveleri kaldırıldı, sonuç sekmelerinin tıklama alanı büyütüldü, boş listelere ikonlu yönlendirme ve manuel K/R formuna özet bandı eklendi. ISO geçme sınıfı ve minimum/maksimum değerler artık kesitin üstündedir. Açık temada nötr yeşil-gri, koyu temada siyah zemin korunur.

Ekran ölçeği değiştiğinde gizli ISO manuel formu, filtrelenmiş seçenekler ve K/R panelleri yeniden görünmüyor. CustomTkinter kaydırma çerçevelerinde gerçek geometri sahibi de temizlenir; seçim, sayfa önbelleği ve hesap sonuçları korunur. Bu davranış tek bir yeni regresyon testinde sınanır. K/R sonuç yerleşimi testi ilgili sekmeyi açıkça seçer. Python 3.13/Tk 8.6 toplu testlerinde eski pencere yazı tiplerinin bir sonraki aktarım işçisinde temizlenmesini önlemek için testler arasında ana iş parçacığında çöp toplama yapılır.

[Gerçek ekran galerisi](ui-preview/README.md). Bulutta düzgün yazı görüntülemesi için Python 3.13 / Tk 8.6 kullanıldı; Windows Segoe UI değişmedi. [Aynı ortamda önce/sonra akıcılık ölçümü](test-results/ui-polish-responsiveness.json): sıcak menü geçişi medyanı 4,26 → 3,96 ms; 500 sentetik sonucun çizimi 84,00 → 83,50 ms. Bu küçük fark hızlanma garantisi değildir; görsel değişiklikler önceki toplu çizim davranışını korur. SolidWorks işlem süresi ölçülmedi.

## Uygulama logosu

15 Ekim 2026'da paylaşılan GÖK logo paketinin açık ve koyu tema PNG'leri,
yan menüde ve açılış ekranında en-boy oranı korunarak gösterilir. Tema seçimi
logoyu da otomatik değiştirir. Ana pencere, dosya ayrıntıları, ISO kaynakları
ve GD&T rehberi paketteki `GOK_app_windows.ico` simgesini kullanır. Windows
`.ico` dosyası yedi boyut içerir; CustomTkinter'ın gecikmeli varsayılan
simgesini de devre dışı bırakır. Varlık yolları çalışma dizininden bağımsız
çözülür. İki PNG ve ICO, Windows EXE içine gömülür.

Windows paket kontrolü, açılış ekranıyla tüm sayfaları hazırlar ve her iki
tema logosunu derlenmiş paketten yükleyip gösterir. Önceki logoya ait
[Arşiv: hedefli test çıktısı](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/test-results/logo-gui-tests.log) ve 332 testlik tam
tarama, eski sürümlerin kayıtlarıdır.

## K/R tarama ve atama ayrımı

Tarama sonuçları **Uygulamaya hazır**, gerçek yazma sonuçları **Uygulandı**
gösterilir. Sayaç, filtre, satır ayrıntısı, günlük ve CSV aynı ayrımı kullanır.
Tarama, K/R'yi değiştirmediğini açıkça belirtir; gerçek uygulama istenen
değerlerin SolidWorks'ten geri okunarak doğrulandığını gösterir.

Tarama sürerken verilen **Tarama bitince K/R uygula** isteği saklanır.
Kontrol başarılıysa ve uygun parça varsa yeni uygulama işlemi başlar;
durdurma, hata veya uygun parça bulunamaması bekleyen isteği iptal eder.
Uygulama isteğine yalnız önizleme sonucu gelmesi açık hata olarak gösterilir.
`128` bilgisi, zaten yüklü parçanın yeniden kullanılmasıyla ele alınır;
mevcut belge uygulamanın yeni açtığı belge gibi kapatılmaz.
[API karşılaştırması ve yerel kontrol](local-solidworks-check.md).

Astra ile K/R dosyaları ve bağlı arayüz/COM akışı ayrıca incelendi. Süpürme
flanşının özel yarıçapını belirleyen `UseDefaultRadius` kontrolü eklendi;
tanım, kaynağı ve DLL hash'i [API kaydında](reports/k-radius/api-contract.json)
ayrı tutulur. Adetlerin karşılaştırma anahtarları özgün dosya yolu olarak
kullanılmıyor; `İ` gibi karakterler ve referans konfigürasyonu COM çağrılarında
korunuyor. İki durum mevcut regresyon testlerine eklenerek sınandı.

11 Ekim tam çalıştırma: **335 test, 0 başarısız, 0 atlanan**, 189,489 saniye;
133 gerçek Tk GUI testi dahildir. Yüklü belgeyi yeniden kullanma, 128/karma
uyarı maskesinde belgeyi kapatmama, taramada sıfır yazma, gerçek atama ve
bekleyen isteğin durdurma/hata ile iptali kontrol edildi. Uygulama isteğine
yalnız önizleme sonucu gelen bildirilen durum da yeniden üretildi; arayüz
bunu uygulanmış saymıyor. [Arşiv: Tam çıktı](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/test-results/latest-tests.log).
SolidWorks COM sınırı test nesneleriyle temsil edildi; gerçek SolidWorks
2025 kabulü yerelde yapılmalıdır.

## Kullanım

Yan menüden **Açık / Koyu** seçilir. Seçim beş ekranı, tabloyu, ikonları ve açık ayrıntı penceresini değiştirir; ayarlara kaydedilir. Tema değişikliği çalışan aktarımı durdurmaz, dosya listelerini/sonuçları sıfırlamaz.

Koyu tema siyah zemin kullanır: ana arka plan `#000000`, yan menü `#080808`, panel `#0B0B0B`, giriş/şema `#101010`. İkincil düğmeler ve hover nötr siyah tonlarındadır; yeşil vurgular korunur. Sekiz mevcut GUI testiyle kontrast, tema tercihi, sekmeler, ölçekler, rehber ve işlem sırasındaki tema geçişi sınandı. [Siyah tema kontrolü ve güncel ekranlar](reports/black-theme/README.md). Önceki 270 testlik rapor, önceki paletin denetim kaydıdır.

Sonuç alanına Türkçe dosya adı/açıklama araması, durum filtresi ve görünen/toplam dosya sayısı eklendi. Filtreler yalnızca görünümü etkiler. Yeni tarama/aktarım filtreleri sıfırlar; PDF ve DXF/DWG geçişleri filtreleri bağımsız korur. İş parçacığından gelen sonuç, aktif filtreye göre kendi satırını günceller; tüm tablo her sonuçta yeniden çizilmez.

Dosyaya çift tıklama veya seçili dosyada Enter, tam kaynak/çıktı yollarını ve aktarım açıklamasını açar. Ayrıntıların panoya kopyalanması desteklenir. Pano sahipliği ana uygulamada tutulur; ayrıntı penceresini kapatmak kopyalanan bilgiyi kaybettirmez. Pencere kapanırken CustomTkinter zamanlayıcıları iptal edilir. İlk incelemedeki kapanış sonrası Tcl `invalid command name` hatası bu şekilde giderildi.

## Dosyalar ve bağımlılıklar

| Dosya | Görevi |
| --- | --- |
| `shared/theme.py` | Ortak açık/koyu renk çiftleri ve platform yazı tipleri. |
| `shared/icons.py` | Pillow ile çizilen özgün ikonlar; tema ve ölçek için iki görüntülü CTkImage nesneleri. |
| `gui/layout.py` | Yan menü, başlık, ayarlar, sayaçlar, sonuç tablosu ve tablo teması. |
| `iso_fits/window.py`, `diagram.py`, `rules.py`, `tables.json` | ISO delik/mil hesabı, kesit/bölge grafiği, çap aralıkları ve sayısal veri. |
| `geometric_tolerances/` | ASME 12 güncel/2 eski özellik kataloğu, açık tolerans/hata kontrolü, vektör sembol/şema ve rehber ekranı. |
| `modules/pdf/window.py` | Ekran durumu, iş parçacığı olayları, filtreleme, tema tercihi, ayrıntılar ve rapor akışı. |

`Pillow==12.1.0` kuruldu ve `requirements.txt` içine eklendi. Mevcut `customtkinter==6.0.0` kullanılıyor. İkonlar uygulama tarafından çiziliyor; çevrimiçi ikon servisine veya ayrı ikon yazı tipine bağımlılık yok. Bulut kurulum scripti ve başlangıç talimatları yeni bağımlılıkla güncellendi.

## Doğrulama

**335 test geçti; 133'ü gerçek Tk GUI testidir.** Yeni K/R ekranı için hesaplama, önizleme/uygulama işçisi, canlı formül güncellemesi, tercihler ve iki tema/ölçek/boyut matrisi eklendi. GUI testleri tarama/aktarım iş parçacığı akışları, CSV, tercih/sekme durumu, boş liste, Türkçe arama, canlı sonuçlarla filtre güncellemesi, filtrelenmiş satırlardan sonra tekrar tarama, ayrıntı/pano, tema tercihi ve yeniden yükleme, işlem sırasında tema değiştirme/kapanış ve küçük pencereyi kapsar. Son eklenen testler tek biçim üretimini, eski birleşik ayarın dönüşümünü, hızlı menü geçişlerini, tercih kaydı tekrarını, büyük listelerin olay sırasını ve çizim/ön yükleme önbelleğini kontrol eder. Windows'un tüm monitör/DPI kombinasyonları burada çalıştırılmadı.

Yeni liste filtrelerinde görünmeyen satırlar Tk tablosundan silinmez, ayrılır. Yeniden taramada bu satırlar da temizlenir; eski `file_n` kimlikleri yeni listeyle çakışmaz. Aktarımın mevcut testleri korunmuştur. [Arşiv: Son test çıktısı](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/test-results/latest-tests.log); önceki sürümün [tam program raporu](program-verification.md) tarihsel kayıttır.

Çalışan uygulamadan 1240×860 boyutunda alınan gerçek ekran görüntüleri:

| Ekran | Açık | Koyu |
| --- | --- | --- |
| DXF/DWG | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/dxf-dwg-light.png) | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/dxf-dwg-dark.png) |
| PDF | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/pdf-light.png) | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/pdf-dark.png) |
| K/R Manuel | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/k-factor-manual-light.png) | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/k-factor-manual-dark.png) |
| K/R Takım | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/k-factor-light.png) | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/k-factor-dark.png) |
| ISO | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/iso-fits-light.png) | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/iso-fits-dark.png) |
| ISO Mil esaslı | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/iso-fits-shaft-basis-light.png) | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/iso-fits-shaft-basis-dark.png) |
| GD&T | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/geometric-tolerances-light.png) | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/geometric-tolerances-dark.png) |

[Arşiv: Manuel ISO H6 referansı](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/iso-fits-manual-h6-dark.png), [Arşiv: tam H8 eşleşmesi](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/iso-fits-manual-h8-dark.png) ve [Arşiv: tablo kontrolü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/ui-preview/screenshots/iso-fits-manual-comparison-dark.png).

## Kod satırı sayısı

| Kapsam | Python dosyası | Toplam satır | Boş olmayan satır |
| --- | ---: | ---: | ---: |
| Uygulama | 29 | 5.336 | 4.874 |
| Testler ve ortak yardımcıları | 23 | 5.483 | 4.888 |
| Toplam | 52 | 10.819 | 9.762 |

Fiziksel satırlar sayıldı; yorumlar ve boş satırlar toplam satıra dahildir. Uygulama kapsamı `main.py`, `pdf/`, `dxf_dwg/`, `solidworks/`, `k_factor/`, `gui/`, `iso_fits/`, `geometric_tolerances/` altındaki Python dosyalarıdır. Test kapsamı, `tests/support/` dahil `tests/` altındaki bütün Python dosyalarıdır. `.venv`, üçüncü taraf kütüphaneler, `backups/`, belgeler, ISO veri JSON'u ve DXF örnekleri sayılmadı. Bu değerler 11 Ekim K/R atama düzeltmesi sonrası sayımdır.

Önceki sadeleştirmede GUI pencere kurulumu, kapanış denetimi, olay bekleme ve sınır kontrolleri; SolidWorks belge taklitleri ve COM bağlantı kurulumu `tests/support/` altında ortaklaştırıldı. Test dosyaları artık başka test dosyalarının kurulumlarına bağımlı değildir. O aşamadaki 327 test kimliği korundu; 302 test gövdesi aynı kaldı, diğerlerinde ortak yardımcılar kullanıldı. Yardımcı dosyalar da sayıldığında test kodu 5.299'dan 5.210 satıra indi (89 fiziksel, 96 boş olmayan satır azalma). Ortak temel sınıflarda test yöntemi bulunmadığı için kalıtım testleri çoğaltmaz.

Son yeniden denetimde 12 ek GUI kabul testi eklendi. İlk yerleşim zamanlaması açıkça başlatıldı. Sonuçlar ve kapsam sınırları [Arşiv: Word raporunda](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/GOKWORKS_GUI_Test_Raporu_2026-10-09.docx); test bazlı kanıtlar [rapor dizininde](reports/README.md). Satır sayıları bu yeniden denetim sonrası güncellenmiştir; rapor üretim araçları uygulama/test sayımına dahil değildir.

K/R güncel ekranında Montajı tara, Hesapla ve dosya kayıt seçimi kaydırılan formun dışındadır. Seçilen malzeme tüm saclara varsayılır; parametreler değiştikçe numune hesabı yenilenir. [Arşiv: Yeni Word raporu](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/k-radius/GOKWORKS_K_RADIUS_GUI_Raporu_2026-10-09.docx); eski rapor K/R öncesi denetimin kaydıdır.

Son manuel eklemede 15 test çalıştırıldı. Form alanları küçük pencerede kaydırılarak erişilebilir; tarama/uygulama ve sonuç listesi görünür kalır. [189 testlik kanıt](reports/manual-k-radius/README.md). Önceki Word raporları kendi sürümlerinin tarihsel kayıtlarıdır.

ISO öncesi denetim: 112 yerleşim kombinasyonu, 144 gerçek menü seçimi ve %150 ölçek dahil 49 GUI testi geçti. Yeşil vurgu korundu. Desteklenen ekranlarda ilk pencere mevcut ölçülere göre seçilir. [ISO öncesi Word raporu, ekranlar ve kanıtlar](reports/final-audit/README.md).

ISO eklemesinde 8 hesap ve 9 GUI testi eklendi. İki tema, 5 boyut/ölçek, 31 delik/mil/birim menü seçeneği, 14 eşleşme, iki grafik, üç örnek ölçü, CSV/pano, hatalı giriş ve yeniden açılış sınandı. Bu ilk sürümde tolerans bölgeleri gerçek sapma ölçeğini, montaj kesiti sabit büyütmeyle şematik gösterimi kullanıyordu; güncel kesit aşağıda açıklanır. [Güncel ISO raporu ve kaynak sınırları](reports/iso-fits/README.md).

ISO sol panelinde **ISO seçimi / Manuel kontrol** menüsü bulunur. Manuel girişte dört sapma alanı, canlı geçme sonucu, tam/en yakın ISO sınıfı ve farklar; mm/µm, örnek doldurma, CSV ve pano desteklenir. 14 ek test (8 hesap, 6 GUI) geçti. %100/%125/%150, iki tema, alanlara ve karşılaştırmaya kaydırarak erişim sınandı. [Güncel manuel rapor ve resimler](reports/manual-iso/README.md).

Manuel kontrolde Montaj hedefi menüsü ve MONTAJ UYUMU / EN YAKIN GEÇME kartı eklendi. Yeni kart farklı referans/gerçek geçme türünü, sınırda teması ve büyük limit farklarını açıklar. 6 hesap + 4 GUI testi daha geçti; CSV/pano ve hedef tercihi desteklenir. [Arşiv: Güncel kart görüntüsü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/fit-compatibility/screenshots/iso-compatibility-dark.png) ve [240 testlik güncel rapor](reports/fit-compatibility/README.md).

GD&T eklemesinde 10 hesap/içerik ve 11 GUI testi geçti. 12 güncel türün iki temada çizimi, iki kaldırılmış kartın çıktı engeli ve Rule #1 boyut ilişkisi, datum menüleri, arama, CSV/pano, hatalı giriş, ölçüm temizliği, rehber ve %100/%125/%150 alan erişimi kontrol edildi. [261 testlik son rapor](reports/geometric-tolerances/README.md).

GD&T ölçü denetiminde 9 regresyon testi eklendi: gerçek 45° ve normal ok, tam çap oku, normal yönde eşit profil sınırları, teknik çerçevede ASME ondalık noktası ve uzun sayıların iki tema/üç ölçekte hücreye sığması. Özelliğe göre ölçüm açıklamaları ve profil ±t/2 payı eklendi. [270 testlik güncel rapor](reports/gdt-dimension-audit/README.md).

## Tam yükseklikte çalışma alanları — 10.10.2026

PDF/DXF ayarları soldaki bağımsız kaydırılan formda, tablo/günlük sağdaki tam yükseklikte sonuç alanındadır. Form kaydırılırken tablo yüksekliği değişmez. K/R ekranı aşağıdaki yeni sekmeli düzene geçti. ISO ve GD&T kendi hesap/şema düzenlerini korur. Dar sonuç panelinde arama ve filtreler iki satıra geçer; başlık ve ipuçları alan genişliğine uyar.

CustomTkinter ölçeklemesinin eski grid konumlarını yeniden yüklediği sekme geçişi giderildi. ISO filtre değişiminde liste kaydırması başa alınır; kısa mil esaslı listede önceki uzun listenin boş alanı görünmez. Tümü görünümünde delik ve mil esaslı örnekler dönüşümlü gösterilir. [Son 19 gerçek ekran ve Word/test kanıtları](ui-preview/README.md). Önceki raporlar tarihsel tasarımı gösterir.

## Güncel K/R alanı ve menü geçişleri

K/R için form ve tablo aynı anda dar sütunlara sıkıştırılmaz. 48 px sekme seçimi kaydırma dışında kalır; malzeme/takım ve manuel alanlar tüm genişliği kullanır. Girişler 42 px yüksekliğindedir. Montaj sonuçları sekmesi tam genişlikte dosya/günlük alanını açar. Montajı tara, Hesapla ve kayıt seçeneği üç görünümde de sabittir. İki tema, 1000×690 minimum pencere ve %125/%150 ölçekler test edilir.

Yan menü vurgusu kısa renk geçişi kullanır; sayfa içeriği hemen açılır. Tercih yazımı 250 ms ertelenir; hızlı geçişte ayrılan sayfaların değerleri birleştirilir, işlem başlatılırken/kapanırken kaydedilir. Büyük dosya listeleri kısa gruplarla eklenir, işçi olayları sınırlı sürelerle tüketilir; Durdur ve diğer Tk olaylarına sıra verilir.

Güncel gerçek ekranlar: [Arşiv: takım](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/gui-current-kr-tools-dark.png), [Arşiv: manuel koyu](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/gui-current-kr-manual-dark.png), [Arşiv: manuel açık](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/gui-current-kr-manual-light.png), [Arşiv: küçük pencere](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/gui-current-kr-manual-small.png), [Arşiv: montaj sonuçları](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/gui-current-kr-results-dark.png), [Arşiv: tek biçim DXF/DWG](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/gui-current-dxf-dwg-dark.png). Bu görüntüler çalışan Tk arayüzünden alındı; SolidWorks çıktısını kanıtlamaz. Önceki Word raporları kendi sürümlerinin kayıtlarıdır.

Menü akıcılığı için ISO/GD&T listeleri yalnız arama, filtre veya seçim değiştiğinde düzenlenir. Sayı ve örnek ölçü değişince sabit menü düğmeleri yeniden çizilmez. Grafik önbelleği veri, görünüm, tema, ölçek ve gerçek tuval boyutunu izler; hatalı girişte eski geçerli grafiği korumaz. Kullanılmamış sayfalar, son girişten en az 600 ms sonra ve işçi çalışmıyorken, 700 ms aralıklarla Tk iş parçacığında hazırlanır. Aktif sayfa ve tercihler korunur. Gizli sayfaların CTk 6 DPI değişiminde tekrar görünmesi engellendi.

Linux/Xorg üzerinde aynı 8ece3f4 sürümüyle karşılaştırılan ölçümde değişken güncellemesi ve `update_idletasks()` süresinin medyanı (her satır 30 örnek):

| İşlem | Önce (ms) | Sonra (ms) |
| --- | ---: | ---: |
| ISO örnek ölçü seçimi | 6,67 | 0,74 |
| ISO mil sınıfı seçimi | 6,44 | 0,98 |
| GD&T tolerans girişi | 4,78 | 0,49 |

Hazır sayfalar arasında 50 geçişin medyanı yaklaşık 3 ms'dir. Bunlar Tk güncelleme süreleridir; Windows cihazının kare hızı veya monitör gecikmesi ölçülmedi. Ön yükleme sırasında aktif sonuçlar, manuel ölçüler, hata sonrası geri dönüş ve DPI değişiminde gizli sayfalar ayrıca test edilir.

PDF, DXF/DWG ve K/R sonuç listeleri arama metnini bellekte tutar; her tuşta satırları Tk'dan yeniden okumaz. Filtrelenmiş satırlar tek `Treeview.set_children` çağrısıyla tarama sırasına yerleştirilir. Durum veya açıklama değişince arama metni yenilenir; gizli satırlar silinmez. Yeniden tarama önbelleği temizler, sekmeler kendi listelerini korur. Canlı sonuçlarla geri gelen satırın konumu sıralı indekslerden bulunur.

Aynı Linux/Xorg ortamında 66a8e45 ile karşılaştırma: 10.000 örnek dosyalık listede Türkçe `imalat-000` araması ve ardından aramayı temizleme, değişken güncellemesi + `update_idletasks()` medyanı (3 tekrar):

| İşlem | Önce (ms) | Sonra (ms) |
| --- | ---: | ---: |
| Arama | 32,50 | 2,27 |
| Aramayı temizleyip tüm satırları gösterme | 389,49 | 4,39 |

Bu ölçüm gerçek Tk listesi ve örnek dosya adlarıyla yapıldı; CAD aktarım süresi değildir. 10.000 satırda toplu filtreleme, seçim/veri korunması, sırasız canlı sonuçlar, yeni tarama ve üç modülün ayrı listeleri regresyon testleriyle kontrol edilir.

İşçi olayları tüketilirken tüm sonuçlar ve günlük kayıtları korunur; aynı turdaki sayaç, ilerleme, durum yazısı ve tablo kaydırması bir kez uygulanır. Her tur en fazla 100 olay veya 6 ms tüketimle sınırlıdır; ardından çizim ve diğer Tk olaylarına sıra verilir. Son özet önceki sayaçlarla ezilmez. Günlükte yukarı kaydıran okuyucunun konumu korunur; aşağıya dönünce yeni kayıt takibi devam eder.

9bfcac4 ile aynı Linux/Xorg ortamında, 2.000 satırlık tabloda 500 örnek dosya sonucu ve üç tekrar için:

| Ölçüm | Önce | Sonra |
| --- | ---: | ---: |
| Olay tüketimi + Tk çizimi medyanı | 305,83 ms | 47,47 ms |
| Bir olay turunun en uzun süresi | 8,19 ms | 2,23 ms |
| Günlüğe ekleme çağrısı | 501 | 21 |
| İlerleme çubuğu çizimi | 500 | 20 |

Sayaç ölçümleri zaman ölçümünden ayrı çalıştırıldı. Poll beklemeleri ve SolidWorks süresi bu ölçüme dahil değildir; Windows kare hızı ölçülmedi. Hazır sayfalar arasında geçiş medyanı 3,08 ms'dir. [Ham ölçümler](test-results/gui-responsiveness.json) ve [Arşiv: tekrar çalıştırma aracı](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/report-tools/benchmark_gui_events.py): `python docs/report-tools/benchmark_gui_events.py . sonuc.json`. Dört yeni gerçek GUI testi toplu çizimde veri/sıra korunmasını, PDF/DXF/K-R son özetlerini, olay turunun sınırını ve günlük kaydırmasını sınar.

ISO montaj kesitinde delik ve mil tam çap oklarıyla (D/d), tek taraflı boşluk veya çakışma g oku ile gösterilir. Çapsal ve radyal değerler ayrı yazılır; seçilen örneğin durumu ile tolerans çiftinin genel türü ayrılır. Sıfır fark temas olarak gösterilir. Kesit ölçeksizdir; küçük boşluklar çizgi kalınlığında kaybolmaz. Kırmızı alanlar deformasyon öncesi boyutsal çakışmayı gösterir. Kesit 310 px, tolerans bölgeleri 220 px çizim alanı kullanır; sağ çalışma alanı kaydırılabilir. Altı gerçek GUI testi çap/radyal oklarını, ara geçme uçlarını, yarım mikrometreyi, sıfır temasını ve iki tema/üç ölçek görünümünü doğrular.

Yeni gerçek ekranlar: [Arşiv: boşluklu koyu](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/iso-section-clearance-dark.png), [Arşiv: boşluklu açık](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/iso-section-clearance-light.png), [Arşiv: ara geçmenin sıkı örneği](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/iso-section-transition-dark.png), [Arşiv: sıkı geçme](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/iso-section-interference-dark.png), [Arşiv: temas](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/iso-section-contact-dark.png), [Arşiv: 1000×690 pencere](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/iso-section-small-dark.png). [Kesiti okuma ve hesap açıklaması](iso-fits.md).

Tolerans yeniden denetiminde 9.108 ISO çiftinin ve 225 manuel aralığın işaretleri bağımsız kesir hesabıyla kontrol edildi. Sayısal sınıflandırmada ters işaret bulunmadı. Nominalden ortak sapma büyüdüğünde 0,02 mm boşluğu 0,016 piksele düşüren çizim düzeltildi: boşluk/sıkılık alanı yalnız D−d ilişkisinden türetilir ve sıfır olmayan alan çizgi kalınlığında kaybolmaz. Kesit ölçeksizdir; sayısal değerler değişmez. İşaretli D−d kesitte, Cmin/Cmax tolerans kartında, seçili örneğin değerleri de CSV/panoda görünür. Girilen limitlerin sonucu, en yakın ISO referansının türünden önce açıkça yazılır. Pozitif 0,02 mm, negatif 0,02 mm, temas, ara geçme örnekleri ve veri çıkışları beş gerçek GUI testiyle sınandı. [Arşiv: 0,02 mm boşluk görüntüsü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/iso-positive-twenty-microns-dark.png).
