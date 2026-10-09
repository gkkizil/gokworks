# Son program ve GUI kontrolü — 9 Ekim 2026

**199 test geçti; 0 başarısız, 0 atlanan. 49 gerçek Tk GUI testi.** [Word raporu](GOKWORKS_Son_Kontrol_2026-10-09.docx), [test bazlı sonuçlar](gui-verification-results.json), [tam günlük](test-run.log), [kapsam](coverage.json).

Uygulamanın 17 Python dosyası incelendi. PDF, DXF/DWG, otomatik K/R, manuel K/R, bağlantı, ayarlar, ikonlar ve ortak GUI akışları kapsamda. Eski `backups/` dosyaları çalıştırılan uygulamanın parçası değildir. Tam program için aynı davranışları içeren tek bir dış proje yok; her modül ilgili API ve hesap örnekleriyle karşılaştırıldı.

## GitHub kaynak karşılaştırması

| GOKWORKS dosyaları | Sabit GitHub referansı | İncelenen davranış / sonuç |
| --- | --- | --- |
| `dxf_dwg/exporter.py` | [CodeStack DXF/DWG](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/document/sheet-metal/export-dxf-dwg/Macro.vba), [montaj sayımı](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/document/assembly/components/write-quantities/Macro.vba) | `ExportToDWG2` argümanları ve 1/4 seçenek bitleri uyumlu. Alt montaj örnekleri, referans konfigürasyonları ve bastırma kontrol edildi. |
| `dxf_dwg/exporter.py`, `k_factor/apply.py` | [xCAD parça arayüzü](https://github.com/xarial/xcad/blob/f9feb293f74576a6a5dbb3ffcca99502e0a257ed/src/SolidWorks/Documents/SwPart.cs), [ExportDxf kalınlık okuyucusu](https://github.com/ajisaacs/ExportDxf/blob/14fa1e69064f743f48edb279edd99681ff0ba783/ExportDXF/Utilities/SolidWorksHelper.cs) | `IPartDoc`, `GetBodies2`, `SheetMetal.GetDefinition().Thickness` ve metre/mm dönüşümü kontrol edildi. |
| `pdf/exporter.py` | [CodeStack PDF](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/import-export/export-sheets-pdf/Macro.vba), [xCAD kayıt işlemi](https://github.com/xarial/xcad/blob/f9feb293f74576a6a5dbb3ffcca99502e0a257ed/src/SolidWorks/Documents/SwSaveOperation.cs) | Sayfa seçimi, 2D PDF ve `SaveAs` çağrısı uyumlu. GOKWORKS tüm sayfaları tek dosyada toplar; referans makro ayrı PDF'ler üretir. Belge kimliği ve geçici dosya güvenliği yerel regresyon testleriyle düzeltildi. |
| `solidworks/connection.py`, PDF/DXF/K/R COM sınırı | [pywin32 b312](https://github.com/mhammond/pywin32/blob/2a277cb5552756c2b4d42b524dc36d25e0bb6354/com/win32com/HTML/variant.html) | Çalışan oturum, işçi başına COM başlatma/kapatma, `DumbDispatch`, açık BYREF `VARIANT` ve varsayılan COM üyesini yanlış çağırmama kontrol edildi. Windows COM testleri burada çalıştırılmadı. |
| `k_factor/rules.py` | [FreeCAD SheetMetal hesap kodu](https://github.com/shaise/FreeCAD_SheetMetal/blob/a1cf212d8b86b3849e5cc12070226d5d4bded2a3/tools/calc-unfold.py), [ANSI tablosu](https://github.com/shaise/FreeCAD_SheetMetal/blob/a1cf212d8b86b3849e5cc12070226d5d4bded2a3/tools/README.md) | 9 tablo hücresi eşleşti. Dış hesap kodunun yalnızca giriş atamaları değiştirilerek BA formülü 108 kombinasyonda gerçekten çalıştırıldı; sonuçlar 1e-12 toleransla eşleşti. Havada büküm R tahmini ve malzeme sınıfı seçimi genel başlangıç önerileridir; bu çalışma üretim kalibrasyonu değildir. |
| `k_factor/apply.py` | [SolidDNA 2023 API tanımları](https://github.com/angelsix/solidworks-api/tree/85a773aedc87b49afda3a65c8bb650f5ba771092/References/2023) | K tipi=2, R/kalınlık özellikleri ve büküm payı API sözleşmesi [önceki metadata incelemesiyle](../k-radius/api-contract.json) yeniden karşılaştırıldı. Bu tanımların SolidWorks'te çalıştırıldığı iddia edilmiyor. Manuel atama, geri okuma ve konfigürasyon koruması yerel testlerde geçti. |
| `main.py`, `pdf/window.py`, `gui/layout.py`, `gui/theme.py`, `gui/icons.py`, `k_factor/window.py` | [CustomTkinter 6.0 örneği](https://github.com/TomSchimansky/CustomTkinter/blob/35f954293b0a39c90b2ad99f812ae0b1773cf3a1/examples/complex_example.py), [menü testi](https://github.com/TomSchimansky/CustomTkinter/blob/35f954293b0a39c90b2ad99f812ae0b1773cf3a1/test/manual_integration_tests/test_optionmenu_combobox.py) | Grid/sidebar, genişleyen alanlar, tema, ölçekleme, Tk değişkenleri ve görüntü nesneleri kontrol edildi. Dış örnek gerçekten açıldı; iki tema ve %100/%125/%150 seçimiyle callback hatası vermeden kapandı. GOKWORKS'e özgü işçi/kuyruk, filtre ve iptal davranışları kendi GUI testleriyle sınandı. |
| `pdf/settings.py`, modüllerin `__init__.py` dosyaları | GOKWORKS yerel ayar/başlatma testleri | Ayarların JSON olarak korunması, başarısız kayıt, bozuk dosya ve giriş noktası kontrol edildi. Dış örnek, bizim ayar dosyamızı veya işçi protokolümüzü doğrulamıyor. |

[Çalıştırılan hesap ve dış GUI örneğinin sayısal kanıtı](reference-comparison.json). CAD makroları ve dış projelerin Windows entegrasyon testleri bu ortamda çalıştırılmadı. Önceki kaynakların çalışma kanıtı ve sınırları [DXF/DWG incelemesinde](../../dxf-dwg-verification.md) kayıtlıdır.

## Bu kontrolde düzeltilenler

- PDF kaynak belgesi, aktivasyonun döndürdüğü belge ve gerçek aktif belge artık tam yolla doğrulanıyor. Farklı bir çizimden PDF üretilmiyor.
- Uzun PDF adlarında kısa, benzersiz geçici ad kullanılıyor; geçerli hedef adı geçici dosya nedeniyle sınırı aşmıyor.
- PDF hedefi bir klasörse işlem hata bildiriyor.
- PDF COM kapanış hatası günlüğe ve bitiş özetine yazılıyor; işçi istisnayla çıkmıyor.
- Dosyalar/Günlük seçimi yerleşimi yeniden hesaplatıyor.
- İlk pencere boyutu ekranın mevcut ölçülerine ve pencere ölçeğine göre seçiliyor; desteklenen küçük ekranlarda 860 px yüksekliğe zorlanmıyor.

5 yeni PDF testi ve 5 yeni GUI testi eklendi. [PDF düzeltme öncesi hata günlüğü](pdf-before-fix.log) korunur. GUI testinde ayrıca CustomTkinter'ın ölçek değişimindeki 1000 ms boyut kilidi beklendi ve istenen boyutun gerçekten gerçekleştiği doğrulandı; böylece yanlış çözünürlükte geçen bir test raporlanmıyor.

## GUI matrisi

- PDF, DXF/DWG, Malzeme/Takım ve Manuel K/R ekranları; açık ve koyu tema; Dosyalar ve Günlük sekmeleri.
- %100 widget ölçeğinde `1000×690`, `1240×860`, `1366×768`, `1600×900`, `1920×1080`; %125'te `1400×900`; %150'de `1920×1080`. **112 alt senaryo geçti.** Bunlar gerçek Tk pencere/viewport ölçüleridir; monitör sürücüsü testi değildir.
- **144 menü seçimi** gerçek Tk menü komutlarıyla yürütüldü. Biçim seçicinin DXF/DWG/DXF+DWG seçenekleri ayrıca sınandı.
- Otomatik ve manuel K/R alanlarının tamamı küçük pencerede kaydırılarak görünür alana getirildi. Tarama ve uygulama düğmeleri sabit erişilebilir kaldı.
- Üç ek açılış senaryosu: 1366×768/%100, 1920×1080/%125 ve 1920×1080/%150. Ekran ölçüleri testte temsil edildi; gerçek Tk widget ve pencere ölçeklemesi kullanıldı. Gerçek Windows DPI/çoklu monitör çalıştırması değildir.
- Yeşil ana düğmeler korunuyor. Normal metin, yardımcı metin ve ana düğme metni iki temada en az 4.5:1 kontrast sağlıyor.

Asgari çalışma alanı **1000×690 mantıksal piksel**. %125/%150 DPI bunu fiziksel ekranda büyütür; daha küçük ekranlar bu sürümde desteklenmiş sayılmaz. %150 ölçekte 1920×1080 açılışı sınandı.

## Güncel görüntüler

Çalışan uygulamadan doğrudan alınan `1240×860` görüntüler. Tablo boş; gerçek CAD sonucu gösterildiği iddia edilmiyor.

| Ekran | Açık | Koyu |
| --- | --- | --- |
| PDF | [Görüntü](screenshots/pdf-light.png) | [Görüntü](screenshots/pdf-dark.png) |
| DXF/DWG | [Görüntü](screenshots/dxf-dwg-light.png) | [Görüntü](screenshots/dxf-dwg-dark.png) |
| Malzeme/Takım | [Görüntü](screenshots/k-radius-light.png) | [Görüntü](screenshots/k-radius-dark.png) |
| Manuel K/R | [Görüntü](screenshots/manual-k-radius-light.png) | [Görüntü](screenshots/manual-k-radius-dark.png) |

Görüntülerin hashleri [screenshots.json](screenshots.json) dosyasında. Bulut Linux fontları ve çizim yöntemi Windows'tan farklıdır.

## Kapsam ve gerçek SolidWorks sınırı

Uygulamanın çalıştırılabilir satır kapsamı **%96,04**, satır/dal birleşik kapsamı **%94,55**. Kapsam, CAD doğruluğu veya hatasızlık garantisi değildir. SolidWorks COM sınırı test nesneleriyle temsil edildi. Gerçek `.SLDPRT` açınım ölçüleri ve büküm geometrisi, PDF içeriği ve SolidWorks sürümüne özgü davranışlar Windows'ta henüz çalıştırılmadı. DWG'de tam ayrıştırma yerine başlık/boyut kontrolü var.

Akşam kontrolü için aktif montajda bir 2 mm ve bir farklı kalınlıkta sac seçin. Manuel sekmede `2 / 0,274 / 2` girip önce tarayın, sonra uygulayın. 2 mm sacın SheetMetal tanımındaki K/R değerlerini, farklı kalınlıktaki sacın korunmasını ve montajın geri etkinleşmesini kontrol edin. Ardından aynı parçanın DXF/DWG açınım ölçülerini ve dosya adındaki toplam adedi kontrol edin. Kayıt seçeneği varsayılan kapalıdır; değişiklikler bu durumda SolidWorks belleğindedir.

## Tekrarlama

```bash
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user \
COVERAGE_FILE=/tmp/gokworks-final-audit.coverage \
.venv/bin/python -m coverage run --branch \
  --source=pdf,dxf_dwg,solidworks,main,k_factor,gui \
  docs/report-tools/run_verification.py --output-dir docs/reports/final-audit
```

Windows'ta `.venv\Scripts\python.exe -m unittest discover -s tests -v` kullanılabilir. Yerel testler SolidWorks'ü değiştirmez.
