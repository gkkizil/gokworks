# GOKWORKS — Qt migrasyon raporu

Depo: `gkkizil/gokworks` · Dal: `codex/pyside6-migration` · Başlangıç: `5f01e53`.
Ana dal birleştirilmedi. Yedek depoya bu çalışma kapsamında erişilmedi.

## Mimari ve korunan işlevler

Ana uygulama Python/PySide6 6.10.3 + Qt Widgets kullanır. `main.py` ve
`python -m gui_qt` aynı uygulamayı açar. `pdf.window` eski başlatma yolu için
Qt ana pencereye yönlendiren ince bir uyumluluk modülüdür. Tk widget taklidi yoktur.

`gui_qt/app.py`: QMainWindow, önceden oluşturulmuş dokuz sayfa, QStackedWidget,
yan menü, açık/koyu QPalette/QSS, logo, değişmeyen Windows ICO/AppUserModelID,
durum/ilerleme, bağlantı kontrolü ve güvenli asenkron kapatma.

`gui_qt/models.py`: sanallaştırılmış QAbstractTableModel/QAbstractItemModel,
Türkçe ve sayısal sıralama, önbellekli arama, hiyerarşik filtre. Satır başına
widget oluşturulmaz. BOM açılımı 100 düğümlük event-loop gruplarıyla yapılır.

`gui_qt/workers.py`: QObject/QThread, sinyal/slot, 64 olay veya 16 ms gruplama,
threading.Event iptali. Bir CAD/dosya işi çalışırken gezinme ve bağımsız hesaplar
kullanılabilir. COM nesneleri GUI’ye taşınmaz; mevcut motorlar COM’u kendi worker
thread’lerinde başlatır/sonlandırır. QThread.terminate veya zorla kapatma yoktur.

`gui_qt/settings.py`: mevcut JSON anahtarlarını ve bilinmeyen tercihleri korur;
atomik mevcut yazıcı, gecikmeli kayıt, bozuk dosyanın silinmeden kopyalanması.
QSettings yalnız Qt pencere geometrisi ve geçiş sürümü içindir.

`gui_qt/diagrams.py`: mevcut geometri üreticilerinden QGraphicsScene üzerinde
vektörel teknik şemalar oluşturur. Resize sırasında sahne ölçeklenir;
hesap motoru veya CAD sorgusu yeniden çalıştırılmaz. Canvas protokolü yalnız
geometri arayüzüdür; Tk/Tcl nesnesi veya bitmap ekran kopyası kullanılmaz.

| Modül | Qt karşılığı ve korunan davranış |
|---|---|
| PDF | Klasör/alt klasör tarama, toplu aktarım, üzerine yazma seçimi, durdurma, dosya sonuçları/günlük/CSV, mevcut atomik çıktı koruması. |
| DXF/DWG | Tek çıktı formatı, büküm çizgileri, kalınlık klasörleri, miktar/kalınlık ayrıntıları, aynı dosya güvenliği. |
| BOM | Doğal sıralanan parça listesi, alt montaj ağacı, konfigürasyon, adet, canlı ağırlık, bilinmeyen ağırlık uyarısı, arama, yol kopyalama, tam Excel çıktısı. |
| İsimlendirme | Kaynak klasör ve montaj seçimi, klasörde montaj bulma, aktif montaj, tam hedef klasör, ön/son ek, numara, bul/değiştir, hiyerarşik önizleme, elle düzeltme, çakışma kontrolü, native Pack and Go, referans doğrulama ve JSON raporu. |
| K/R | Kalınlık/K/R satırları, birebir kullanıcı değerleri, bağımsız hesap yardımı/BA kalibrasyonu, montaj önizleme, sıraya alınan atamanın montaj kapsamına bağlanması, iptal, varsayılan kapalı kayıt. |
| ISO | ISO 286 seçimi, esasa göre/aranabilir hazır geçmeler, manuel sınırlar ve montaj hedefi, en yakın sınıf/çift karşılaştırması, üç örnek boyut, iki şema, CSV/kopyalama/rehber. |
| GD&T | 12 güncel ve 2 eski sembol, aranabilir katalog, datum, boyut/şekil ilişkisi, çerçeve/bölge, ölçülen hata karşılaştırması, kopyalama/CSV/rehber. |
| Cıvata | M3–M39, kalite 4.6–12.9, kaba/ince adım ve standart etiketi, çekme/kesme/birleşik yük, kg/N/kN fiziksel dönüşümü, emniyet/adet/kesit/düzlem, yük ve ölçü şeması, kapsamlı sonuç raporu. |
| Ağırlık | 19 kesit, malzeme grupları ve kalıp çeliği açıklamaları, değiştirilemeyen yoğunluk, mm/cm/m dönüşümü, ölçüler/katalog alanı, adet, parça/toplam ağırlık, kesit şeması ve rapor. |

## Değiştirilen dosyalar

[Tam değişiklik listesi](qt-migration/changed-files.txt) Git başlangıç commit’ine
göre tutulur. Yeni uygulama `gui_qt/` içindedir: ana pencere, ayarlar, worker,
tema/ikonlar, modeller, ortak bileşenler, vektör sahnesi ve dokuz sayfa.
`main.py`, `pdf/window.py`, `gui/package_check.py` başlatma/kontrol yolları Qt’ye
yönlendirildi. Kullanılmayan eski yedi `window.py` mixin’i ve beş Tk GUI yardımcısı
kaldırıldı; asılları `5f01e53` geçmişinde korunur.

`requirements.txt` / `requirements-dev.txt`, `pytest.ini`, Windows build ve sonuç
yayınlama betikleri/iş akışı güncellendi. İş mantığı testleri yerinde korunurken
eski GUI testlerinin asılları arşive taşındı; `tests/test_qt_workflows.py` eklendi.
README, migrasyon/test/performans kanıtları ve lisans bildirimleri güncellendi.

## Test ve ölçümler

Başlangıç envanteri: 140 izlenen Python dosyası, 620 test yöntemi.
Başlangıç sürümünün gerçek çalıştırması: **620 test, 9 failure + 6 error**.
Bu hatalar Qt migrasyonu sonucu gibi gösterilmez; kayıtlar analiz kanıtında tutulur.

410 mevcut hesap/CAD/ayar testinin yöntem gövdeleri korunmuştur. Manuel K/R’nin
alt büküm bayraklarını değiştirmesini bekleyen eski bir beklenti, mevcut üretim
sözleşmesine göre düzeltilmiştir: yalnız ana SheetMetal parametreleri değiştirilir.
Eski testin aslı başlangıç commit’inde korunur.

210 Tk GUI testi **verbatim** `tests/legacy_tk` altında saklanır; çalıştırmak için
başlangıç commit’i ve eski bağımlılıklar gerekir. Bunlar Qt suite sonucu olarak
sayılmaz. `gui-test-mapping.json` her eski testin karşılık grubunu gösterir.
Qt testleri gerçek widget/model/event-loop kullanır; yalnız CAD sınırı sahte
nesnelerle kontrol edilir. Eski widget iç yapısına bağlı iddialar yerine kullanıcı
davranışı sınanır. Ana suite komutu `python -m pytest -q`.

Son Linux kontrolü: **518 test geçti** (410 mevcut motor/ayar testi + 108 Qt
senaryosu); **878 alt senaryo geçti**, failure/error/skip yok. Süre 92,36 s.
131 uyarı ezdxf/pyparsing’in mevcut API kullanımlarına aittir; hata olarak gizlenmedi.
[Makine tarafından okunabilir sonuç](qt-migration/validation.json),
[komut sonucu](qt-migration/final-test-summary.txt),
[38 dosyanın SHA256 karşılaştırması](qt-migration/engine-integrity.json),
[Qt ekranları](qt-migration/screenshots).

| Linux/Xvfb ölçümü | Önceki Tk sürümü | Qt sürümü |
|---|---:|---:|
| Aynı profilli tekrar: 18 menü tıklaması + 46 resize | 1,850 s | 0,668 s |
| Menü geçişi ortanca / en uzun | aynı ölçüm ayrı tutulmadı | 19,81 / 30,82 ms |
| Resize ortanca / en uzun | aynı ölçüm ayrı tutulmadı | 11,40 / 24,62 ms |
| 50.000 satır yükleme / filtreleme | aynı ölçüm yok | 46,68 / 111,86 ms |
| Qt açılışı (tüm sayfalar dahil) | aynı ölçüm yok | 1.209 ms |

Karşılaştırma aynı Linux/Xvfb/Python 3.13 ortamında, aynı 64 adımlı
navigasyon/resize dizisiyle yapıldı. Grafik sunucusuna verilen işlemler ölçülür;
insanın algıladığı ekran gecikmesi veya fiziksel monitör FPS’i değildir. Profil
koşulları yükü etkiler; Windows sonucu ayrıca raporlanır. Qt ölçümleri
[qt-linux-smoke.json](qt-migration/qt-linux-smoke.json) ve profillerde bulunur.

20 ardışık worker yaşam döngüsünde çalışan QThread kalmadığı, tekrarlanan
navigasyonda sayfa nesnelerinin aynı kaldığı, 50.000 satır eklenmesinin yeni
widget oluşturmadığı test edildi. Bu kontroller uzun süreli işletim sistemi
bellek sızıntısı analizinin yerine geçmez.

## Windows paketleme

PyInstaller 6.16.0, Python 3.13 x64, `--onedir --windowed --noupx`.
Qt platform DLL/eklentileri PyInstaller’ın PySide6 hook’larıyla toplanır.
Tk/_tkinter/CustomTkinter ve emekli bağımsız K/R aracı açıkça hariç tutulur.
Logo ve ICO dosyaları paket içinde korunur. Lisans dosyaları beraber dağıtılır.

GitHub Actions: regresyonlar, EXE üretimi, EXE’yi gerçekten açarak dokuz ekran,
iki tema, dört çözünürlük ve üç DPI ölçeği kontrolü; XLSX/DXF bağımlılık kontrolü,
SHA256 ve artifact. Sonuç yayıncısı yalnız derlemenin **kaynak dalına** yazar.
Geliştirme derlemesi `main` veya yedek depoyu değiştiremez.

Windows derleme sonucu: **hazırlanıyor; başarılı olduğuna dair henüz iddia yok**.

## Sınırlar ve gerçek SolidWorks kontrolleri

Linux ortamında SolidWorks 2025 SP5/Windows COM sunucusu yoktur. Gerçek CAD
aktarımı, K/R yazma ve Pack and Go’nun canlı SolidWorks doğrulaması yapılmadı.
Geçen test nesneleri canlı SolidWorks testi yerine sunulmaz. Windows açılış testi
de CAD bağlantısını otomatik olarak doğrulamaz.

Windows/SolidWorks’te şu kabul kontrolleri yapılmalıdır:

1. Kaydedilmemiş açık belge ve etkin konfigürasyon korunarak PDF/DXF/DWG aktarımı.
2. Eski/TemplateSheetMetal/katıdan dönüştürülmüş parçaların gerçek kalınlığıyla
   eşleşme; K/R yazımı, geri okuma, eşleşmeyen ve sac olmayan parçaların atlanması.
3. Çok konfigürasyonlu montaj ve başarısız yazımda geri alma/kayıt engeli.
4. Pack and Go’da teknik resim, alt montaj, ortak parça, Toolbox ve bastırılmış
   bileşen bağlantılarının yeni hedefte açılarak doğrulanması; kaynakların değişmemesi.
5. BOM ağırlıklarının SolidWorks kütle özellikleriyle, özellikle montaj kesileri ve
   konfigürasyon farklarıyla karşılaştırılması.
6. Farklı DPI’lı fiziksel monitörler arasında pencere taşıma. CI ölçek testi gerçek
   çoklu monitör kullanıcı kabulünün yerine geçmez.

Kod imzası yoktur. Ticari dağıtım için LGPL/EULA ve diğer bildirimler
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) kapsamında gözden geçirilmelidir.
Eski bağımsız `k_factor/standalone` denemesi tarihsel kaynaktır; yeni uygulamanın
çalışma veya paketleme yolunda bulunmaz. Eski rapor araçları önceki commit’e ait
kanıtları üretir; güncel Qt denetimi ayrı araçla yapılır.

## Bulut geliştirme ortamı

Kurulum/başlangıç talimatları cloud-environment-onboarding:setup ile Qt’ye
güncellendi ve taslak olarak kaydedildi. Python 3.13 venv yenilemesi, pinned
bağımlılıklar, başsız gerçek Qt açılış kontrolü ve test komutu çalıştırıldı.
Ağ/secret/depo üyeliği değiştirilmedi. Bu taslak kaydı ortamı yayımlamaz;
gelecek görevler için kullanıcı ortam ayarlarından kaydedip yayımlamalıdır.
Çalışan Xvfb süreci snapshot ile taşınmaz; başlangıç talimatı bunu açıklar.
