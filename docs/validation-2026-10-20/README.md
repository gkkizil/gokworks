# GOKWORKS · Genel uygulama testi

20 Ekim 2026. Test edilen uygulama kaynak sürümü:
`9de4b17c7472a29747dc854fb2c97db3187d5569`.
Bu çalışma uygulama kodunu değiştirmez; yeniden çalıştırılabilir bir kararlılık
kontrolü ve test kanıtları ekler. Yedek depoya erişilmedi.

## Sonuç

Tam paket tekrar koşusunda **897 test başarılı, 7 test atlandı; 878 alt
senaryo başarılı**. Süre: 449,11 saniye. Başarısız test veya hata yok.
[Tam çıktı](full-repeat.log) · [JUnit XML](full-repeat.xml) ·
[Makine tarafından okunabilir özet](summary.json).
Saklanan konsol çıktılarında yalnızca satır sonu boşlukları temizlendi.

Ek olarak 138 Qt arayüz testi ayrı süreçte geçti; bunlar tam paketle örtüşür,
897 sayısına eklenmez. Üç DPI açılış kontrolü, gezinme/boyutlandırma ve 20 PDF
hata kurtarma döngüsü de geçti. Aşağıdaki **tema gecikmesi ve ilk koşudaki
aralıklı takılma bulguları açık kalıyor**. Başarılı tekrar koşusu bunların
giderildiği anlamına gelmez.

Atlananlar: gerçek Windows PowerShell/interop derlemesi (1), canlı Pack and Go
(1), Windows süreç tutamaçları (2), gerçek pywin32 API (1), canlı teknik resim
okuma (1) ve açık seçime bağlı analizli teknik resim kopyası (1). İlgili
dosya/satır ve nedenler tam çıktıda bulunur. 137 uyarı, ezdxf/pyparsing
bağımlılığının eski ayrıştırıcı API kullanımından gelir; test hatası değildir.

## Ortam ve kapsam

Linux, Python 3.13.5, PySide6 / Qt 6.10.3, `offscreen` platformu.
Gerçek hesap motorları, Qt widget'ları, dosya sistemi ve alt süreçler çalıştırıldı.
CAD sınırındaki sahte nesneler gerçek SolidWorks entegrasyonu sayılmadı.

| Alan | Uygulanan kontrol |
| --- | --- |
| 12 ekran | Açılış, önbellekteki aynı sayfaya gezinme, açık/koyu tema, minimum pencere, başlık ve işlem alanları |
| Hesaplar | Cıvata yük/güvenlik, hızlı tork, ISO ve manuel geçmeler, geometrik tolerans, ağırlık ve K/R hesap yardımı |
| Tolerans yığılması | Simetrik/asimetrik ve işaretli zincirler, Worst-Case/RSS/Monte Carlo, birimler, eksik veri, revizyon ve proje kaydı |
| Nesting | Gerçek DXF okuma, çoklu dosya, gerçek konturlar, plaka sıralaması, malzeme/kalınlık grupları, doğrulama ve maliyet |
| Çıktılar | Yerel DXF, Excel ve PDF üretimi; nesting PDF metninin koyu/açık temada okunması, sayfalama ve bağlantı bulunmaması |
| Veri güvenliği | İptal, yarım çıktı temizliği, kaynakların korunması, kayıt hataları ve atomik proje/rapor kaydı |
| PDF aktarımı | Ayrı süreç/IPC, Türkçe kayıtlar, alt sürecin beklenmedik çıkışı, iptal, tamamlanan dosyaların korunması; CAD nesneleri sahte |
| COM hizmetleri | K/R, Pack and Go, BOM ve teknik resim okuma/yazma sözleşmeleri ile hata/geri alma yolları; CAD nesneleri sahte |
| Ortak arayüz | Temizle, filtre, kopyala, seçim, çalışan işi durdurma, kapanırken bekleme ve ayarları yeniden açma |

`tests/legacy_tk` arşivdir; güncel PySide6 regresyon paketine dahil değildir.

## Kaynak uygulama açılış kontrolleri

Üç ayrı süreçte %100, %125 ve %150 Qt ölçeklemesi denendi. Her süreçte 12 ekran,
iki tema ve 1024×700, 1366×768, 1920×1080, 2560×1440 pencere boyutları geçti.
Bu, gerçek Windows monitör/DPI testi değildir.

- [100%](selfcheck-1.json), [125%](selfcheck-1.25.json), [150%](selfcheck-1.5.json)
- Örnek tork: 51,96 N·m / 25,98 kN; ağırlık: 157 kg.
- Örnek tolerans zinciri: nominal 0,20 / minimum 0,02 / maksimum 0,38 mm.
- Gerçek yerel nesting örneği, DXF/Excel/PDF, çizimler ve 50.000 satırlık tablo kontrol edildi.
- PDF hizmetinin gerçek alt süreci boş kaynakla başlatıldı; SolidWorks açılmadı.

## Kararlılık ve süre ölçümleri

[Tekrar çalıştırma aracı](../report-tools/validate_application_stability.py),
geçici ayar dosyaları ve depodaki nesting örneğini kullanır. Kullanıcı CAD
dosyalarına veya mevcut ayarlarına yazmaz.

[Aşamalara ayrılmış ölçüm](stability-phased.json): 360 gezinme, 360 yeniden
boyutlandırma, 10 tema değişimi; 820×560, 1024×700, 1440×900; açık ve dar menü.
Widget sayısı 1931 → 1931. Ağırlık/tork/K-R girdileri, tolerans zinciri ve nesting
sonucu korundu. Uygulama kapatılıp yeniden açıldığında ayarlar doğrulandı.
Sabit widget sayısı, tüm olası bellek sızıntılarının dışlandığı anlamına gelmez.

- Gezinme: medyan 9,31 ms, en uzun 53,88 ms.
- Yeniden boyutlandırma: medyan 5,88 ms, en uzun 46,33 ms.
- **Açık performans bulgusu:** tema değişimi medyan 1122,83 ms,
  en uzun 1202,79 ms. Olay döngüsündeki en uzun aralık da yaklaşık 1203 ms.
  [Profil](theme-profile.txt), gecikmenin büyük bölümünün tüm uygulamaya
  yeniden stil uygulayan `QApplication.setStyleSheet` içinde olduğunu gösterir.
  Menü geçişi süresine tema değişimi dahil edilmedi.

Bu değerler kaynak uygulamada, Linux/offscreen ortamında ve eşzamanlı test
yükü altında ölçüldü; Windows akıcılığı için süre garantisi değildir.

## PDF hata kurtarma ve aralıklı takılma bulgusu

İlk geniş test koşusu, PDF alt sürecinin çökmesini taklit eden testte,
`ResultsPanel.append_log → QPlainTextEdit.appendPlainText` içinde ilerlemeyi
kesti. Yaklaşık beş dakika yeni test ilerlemesi olmadı. Test süreci, nerede
beklediğini kaydetmek için bizim tarafımızdan `SIGABRT` ile sonlandırıldı;
bu çıkış uygulamanın kendiliğinden çökmesi olarak raporlanmaz.
[Tamamlanmayan ilk koşunun izi](initial-incomplete.log).

Bu durum başarı sayılmadı. Aynı test tek başına geçti ve arayüz regresyon
paketinde yeniden çalıştırıldı: [tek test](pdf-isolated.log) ve
[138 arayüz testi](qt-suite.log) hatasız tamamlandı.
Tam paketin 897 testlik tekrar koşusu da aynı PDF hata testini geçerek tamamlandı.
İlk koşudaki sinyal tabanlı zaman aşımı C++
çağrısını durduramadığı için tekrar koşusunda thread tabanlı süre sınırı ve
faulthandler kullanıldı. Bu, ürün düzeltmesi değildir; testin sınırsız
beklemesini önleyen çalıştırma seçeneğidir.

Ayrıca [PDF hata kurtarma aracı](../report-tools/validate_pdf_fault_recovery.py)
ile tek uygulama oturumunda, diğer ekranlara geçiş yapılırken **20 gerçek alt
süreç** art arda kod 23 ile sonlandırıldı. Her döngüde GUI zamanlayıcısı
çalışmaya devam etti, sonuçlar GUI thread'inde işlendi, ilk tamamlanan sahte PDF
korundu, yarım çıktı temizlendi ve kaynak dosyalar aynı kaldı. Temizle ve
yeniden başlatma da her döngüde geçti. [Sonuç](pdf-fault-recovery.json).
CAD yerine hata enjekte eden test yardımcısı kullanıldı.

**İlk toplu koşudaki takılmanın nedeni kesinleştirilmedi ve giderildiği iddia
edilmiyor.** Gerçek Windows/SolidWorks PDF aktarımında ayrıca izlenmelidir.

Bağımlılık uyumluluğu kontrolünde kurulu 22 paketin tamamı uyumluydu.
Güncel uygulama paketlerinin Python derleme kontrolü de hatasız tamamlandı.

## Gerçek Windows / SolidWorks kabul kontrolleri

Burada şu işlemler doğrulanmadı:

1. Gerçek SolidWorks oturumuna bağlanma, sürüm/konfigürasyon farklılıkları.
2. Gerçek montajda K/R yazma, geri okuma, kaydetme ve geri alma.
3. Pack and Go ile gerçek bağımlılıkları okuma ve yeniden adlandırılan paketi açma.
4. Gerçek SLDDRW ölçülerini/toleranslarını okuma ve ayrı analizli kopyaya anotasyon.
5. Gerçek teknik resimlerin toplu PDF/DXF/DWG aktarımı ve uzun süreli COM kararlılığı.
6. Son Windows EXE'sinin açılışı, tek dosya dağıtımı, SmartScreen ve gerçek ekran ölçeklemesi.

Canlı testler için örnek, gözden çıkarılabilir CAD kopyalarıyla Windows üzerinde
`modules/naming/tests/test_naming_native_live.py` ve `modules/tolerance_stack/tests/test_tolerance_stack_live.py`
çalıştırılabilir. Gerekli ortam değişkenleri bu dosyaların başında açıklanır.
Kopyaya yazma testi ayrıca açık seçime bağlıdır; kaynak üzerine yazılmaz.
Bu test çalışması için yeni EXE üretilmedi.

## Yeniden çalıştırma

Geliştirme bağımlılıkları kurulmuş Python ortamında:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -vv -ra --timeout=60 --timeout-method=thread -o faulthandler_timeout=30 --junitxml=full-repeat.xml
QT_QPA_PLATFORM=offscreen python main.py --self-check selfcheck.json
QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=1.25 python main.py --self-check selfcheck-1.25.json
QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=1.5 python main.py --self-check selfcheck-1.5.json
QT_QPA_PLATFORM=offscreen python docs/report-tools/validate_application_stability.py stability.json
QT_QPA_PLATFORM=offscreen python docs/report-tools/validate_pdf_fault_recovery.py pdf-fault-recovery.json
```

Windows'ta `QT_QPA_PLATFORM=offscreen` olmadan normal Qt platformu ile çalıştırın.
