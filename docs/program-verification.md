# Tüm programın yeniden doğrulanması

**240 test başarılı, 0 başarısız, 0 atlanan.** [Güncel montaj uyumu kontrolü ve Word raporu](reports/fit-compatibility/README.md); önceki denetimler tarihsel kayıt olarak korunur. Testler Linux/Python 3.12.14 ortamında gerçek Tk arayüzü, gerçek ezdxf okuyucusu ve SolidWorks COM davranışını temsil eden nesnelerle çalıştırıldı. `git diff --check` temiz. [Son test çalışmasının tam çıktısı](reports/fit-compatibility/test-run.log) kaydedildi.

## Kapsam

| Alan | Test sayısı | Kontrol edilen davranışlar |
| --- | ---: | --- |
| DXF/DWG | 69 | Geometri/büküm seçenekleri, parça arayüzü, kalınlık, dosya adı, alt montajların toplam adedi, bastırma, konfigürasyon ve Unicode yol ayrımı, SpeedPak/yüklenmemiş bileşenler, dosya koruma, durdurma ve COM temizliği. Yanlış belge, uzun dosya adı ve bozuk ASCII/ikili DXF de sınandı. |
| PDF | 34 | Tüm sayfalar, tek sayfa, teknik resim arayüzü, açık/kapalı belgeler, aktivasyon ve önceki belgeye dönüş, BYREF bağlama, kesilmiş çıktı, üzerine yazma, yarışan hedef ve hata sonrası devam. |
| Gerçek Tk arayüzü | 68 | PDF ve DXF/DWG iş parçacıklarının çıktı/CSV sonuçları, Türkçe yollar, sekmelerin durumunu koruma, tercihlerin yeniden yüklenmesi, hata sonrası düğmelerin açılması, işlem sırasında kapanış, boş liste yönlendirmesi, kalınlık/adet gösterimi ve küçük pencerede liste görünürlüğü. Gerçek uygulama giriş noktası Tk ana döngüsünden geçirilip kapatıldı. |
| K/R hesaplama ve uygulama | 39 | ANSI sınıfları, sınırlar, elle BA/BD örnekleri, bağımsız ölçümden K, takım/açı uygunluğu, montaj, geri okuma, konfigürasyon yayılımında geri alma, başarısız geri alma, kayıt ve COM kapanışı. |
| ISO delik/mil hesabı | 22 | Çap sınırları, 198 eşleşme, limitler, yarım mikrometre, işaret/sınıflama, geçersiz giriş ve bağımsız tablo örnekleri. 9 ISO ve 10 manuel ISO GUI testi üstteki GUI sayısına dahildir. Manuel tek/bilateral toleranslar, ölçülen noktalar, eşleşme farkları ve geçersiz limitler de sınandı. |
| Ayarlar | 4 | JSON ve Türkçe karakterler, bozuk/okunamayan dosyadan güvenli dönüş, başarısız kayıt sırasında eski ayarların korunması. |
| SolidWorks bağlantısı | 3 | Çalışan oturuma bağlanma, oturum bulunamaması ve pywin32 eksikliği. |
| Giriş noktası | 1 | `main.py` uygulama giriş fonksiyonunu çağırıyor. |

K/R sekmesi **K FAKTÖR - RADIUS** adıyla etkin. Genel ANSI tablosu, yaklaşık havada büküm R hesabı ve bağımsız BA ölçümüyle kalibrasyon var. Üretim doğruluğu iddiası için gerçek numune gerekir. [Algoritma ve kaynak kıyaslaması](k-factor-radius.md). `backups/` uygulamanın çalıştırdığı kod değildir.

## Bulunan ve düzeltilen sorunlar

Yeni 25 PDF testi ilk çalıştırmada **9 başarısızlık ve 2 hata** verdi. COM özellik okuma, geç bağlama, teknik resim arayüzü, aktif belge ve çıktı bütünlüğü testleri sorunları görünür kıldı. Düzeltmelerden sonra bu testler geçti; ek hata durumlarıyla PDF kapsamı 29 teste çıktı.

- PDF tarafındaki özellik okuyucu, çağrılabilir COM nesnesinin varsayılan üyesini yanlışlıkla çağırabiliyordu. `_oleobj_` taşıyan nesneler artık çağrılmadan okunuyor.
- BYREF çıkış parametreleri için uygulama ve iç içe `ModelDocExtension.SaveAs` çağrısı gerektiğinde `DumbDispatch` ile geç bağlanıyor.
- `IModelDoc2` üzerinden sayfa adlarına erişilemiyorsa `IDrawingDoc` arayüzüne geçiliyor. Düz PDF üretimi için `ExportAs3D=False` açıkça ayarlanıyor.
- Açık fakat aktif olmayan çizim aktarım öncesinde etkinleştiriliyor. Uygulamanın açtığı çizim kapatılıyor; önceki belgeye tam yoluyla geri dönülüyor. Aktivasyon hatasında aktarım yapılmıyor.
- Yalnızca `%PDF-` başlığı olan veya dosya sonu kesilmiş çıktı başarılı sayılabiliyordu. Başlıkla birlikte `%%EOF` kontrolü eklendi. Bu temel bütünlük kontrolü PDF içeriğinin doğru çizim olduğunu kanıtlamaz.
- Hedef klasör oluşturma hatası dosya bazındaki hata işleyicisinin dışındaydı. Hata artık ilgili çizimin sonucu olarak raporlanıyor; başka çizimler işlenebiliyor. Aynı hedefin işlem sırasında oluşması ayrıca ele alınıyor.
- PDF COM temizliği hata verse bile arayüze bitiş olayı gönderiliyor.
- `1000×690` pencerede PDF tablosu 73, DXF/DWG tablosu 64 piksele kadar daralıyordu. Ayarlar yüksekliği artık gerçek görünür alan ve sekme çerçevelerinden hesaplanıyor; sonuç tablosuna alan ayrılıyor. Tasarım ve sekmeler korunuyor.

## GitHub kaynaklarıyla kıyaslama

| Kaynak | Kıyaslanan bölüm | Kanıtın sınırı |
| --- | --- | --- |
| [CodeStack PDF sayfa makrosu](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/import-export/export-sheets-pdf/Macro.vba) | `DrawingDoc.GetSheetNames`, `GetExportFileData(1)`, `SetSheets(3, names)`, `ExportAs3D=False`, `ViewPdfAfterSaving=False`, `Extension.SaveAs` argümanları. GOKWORKS tüm sayfaları tek PDF'e seçiyor. | Yayımlanmış API örneği; bu PDF makrosu burada SolidWorks'te çalıştırılmadı. |
| [xCAD.NET PDF kayıt işlemi](https://github.com/xarial/xcad/blob/f9feb293f74576a6a5dbb3ffcca99502e0a257ed/src/SolidWorks/Documents/SwSaveOperation.cs#L360) | PDF veri nesnesi, belirtilen/tüm sayfaların seçimi, görüntüleyici açmama ve hata kodlu kayıt çağrısı. | Kaynak tutarlılığını destekliyor; upstream testlerin başarılı çalıştırılması burada doğrulanmadı. |
| [pywin32 b312 kaynak ve VARIANT belgeleri](https://github.com/mhammond/pywin32/blob/2a277cb5552756c2b4d42b524dc36d25e0bb6354/com/win32com/HTML/variant.html#L138) | `CDispatch.__call__` varsayılan COM üyesi; açık BYREF parametreleri için `DumbDispatch`. | pywin32 davranışının birincil kaynağı; Windows COM testleri burada çalıştırılmadı. |
| CodeStack DXF/DWG ve montaj adedi, ExportDxf kalınlık okuyucusu | Sac açınımı seçenekleri, `ExportToDWG2`, örnek bazında montaj dolaşımı ve metre/mm dönüşümü yeniden incelendi. | Sabit commitler ve geçmiş kullanıcı çalışma bildirimi [DXF/DWG raporunda](dxf-dwg-verification.md) kayıtlı. Başka bir projenin çalışması GOKWORKS'ün gerçek CAD çıktısını doğrulamaz. |

SolidWorks gerektiren dış projeler burada çalıştırılmadı. `ezdxf==1.4.3` ise gerçekten çalıştırıldı; dört ASCII/ikili DXF örneği oluşturuldu, okundu ve denetlendi. API kıyaslamaları, hata üreten yerel testlerin yerine kullanılmadı.

## Son DXF/DWG incelemesi ve GUI düzenlemesi

Önceki 105 testten sonra 15 yeni DXF/DWG testi ve bir GUI testi eklendi. İlk dokuz DXF/DWG regresyon testi, düzeltmelerden önce alt senaryolar dahil **10 başarısızlık ve 1 hata** üretti. Daha sonra eklenen Unicode eşleştirme testi de düzeltme öncesinde başarısız oldu. Son çalışmada tüm 121 test geçti.

- SolidWorks'ün açtığı model, aktivasyonun döndürdüğü belge ve gerçek `ActiveDoc` yolu artık kaynak parçayla karşılaştırılıyor. Farklı belgeyle açınım oluşturulmuyor.
- Hedefin dosya yerine klasör olması hata döndürüyor; diğer biçim var diye sessizce atlanmıyor.
- Geçici ad yalnızca kısa önek, UUID ve uzantıdan oluşuyor. Uzun ama geçerli parça adı, UUID eklenerek dosya adı sınırının aşılmasına yol açmıyor.
- Ana montajın aktif konfigürasyonu SpeedPak ise eksik adet üretebilecek işlem durduruluyor. [xCAD.NET montaj doğrulaması](https://github.com/xarial/xcad/blob/f9feb293f74576a6a5dbb3ffcca99502e0a257ed/src/SolidWorks/Documents/SwAssembly.cs#L203) da konfigürasyonun `IsSpeedPak()` değerini kontrol ediyor.
- COM temizliği hata verdiğinde iş parçacığı istisnayla çıkmak yerine hata özeti ve bitiş olayı gönderiyor; GUI kilitli kalmıyor.
- `casefold()` farklı `Straße` ve `Strasse` dosyalarını/konfigürasyonlarını birleştirerek yanlış adet üretebiliyordu. Eşleştirme artık harfleri genişletmeyen `lower()` normalizasyonunu kullanıyor; bu iki ad ayrı sayılıyor.
- DXF'nin başlık veya geometri bölümü taşıması tek başına yeterli sayılmıyor. [ezdxf v1.4.3](https://github.com/mozman/ezdxf/tree/df5ef277fcc674d77580143212ec63dd981cc2b3) bağımlılığı eklendi. Dosya sonu kontrolü, gerçek okuyucu ve `audit()` ile eksik bölüm, bozuk grup kodu/sayısal değer, onarım gereksinimi, boş model alanı ve kesilmiş ikili dosya reddediliyor. Eski çıktı, bu doğrulama başarısızsa korunuyor. R12 ve R2018 ASCII/ikili örnekleri kabul ediliyor; [örneklerin üretimi ve kapsamı](../tests/fixtures/dxf/README.md) kayıtlı.

Bu DXF incelemesinde GUI'nin önceki koyu yan menüsü ve bağımsız PDF/DXF-DWG ekranları korunmuştu. Sonraki GUI çalışmasında düzen, kullanıcı örneğine göre açık/koyu tema, ikonlar, birleşik ayar paneli ve sonuç inceleme araçlarıyla yenilendi; [GUI raporu](gui-design.md) son tasarımı kaydeder. Biçim seçici ve sonuç sekmeleri yeşil vurguya uyarlandı; düğme yazıları, ipuçlarının okunabilirliği ve tablonun görünümü düzenlendi. Boş liste, klasör seçme/tarama adımlarını gösteriyor. Liste dolunca yönlendirme gizleniyor, sıfırlanınca dönüyor ve her ekran kendi durumunu koruyor. DXF/DWG satırlarında okunabilen kalınlık/adet, açıklamanın başında gösteriliyor. CSV ve günlükte ham aktarım sonucu korunuyor. GUI düzenlemesi için mevcut CustomTkinter yeterli oldu.

## İkinci inceleme ve gerçek GUI görüntüleri

Önceki 102 testten sonra, test nesnelerinin kapsamadığı yollar ayrıca incelendi. Üç yeni DXF/DWG testi eklendi; ilk çalıştırmada bir başarısızlık ve bir hata yeniden üretildi:

- Hedefin üst klasörü yerine dosya varsa `mkdir` hatası yanlışlıkla yarışan çıktı sayılıp **Atlandı** raporlanıyordu. `FileExistsError` artık yalnızca dosyayı yayımlama adımında atlama olarak ele alınıyor; klasör hatası **Hata** döndürüyor.
- Aynı unsur hem ana hem alt unsur listesinde görünürse daha önce görüldüğü için ana listedeki sonraki unsurlara geçilmiyordu. Ziyaret anahtarına ana/alt liste bağlamı eklendi. [CodeStack unsur dolaşımı](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/document/features-manager/find-features/Macro.vba) da `GetNextFeature` ve `GetNextSubFeature` zincirlerini ayrı ilerletiyor.
- Önceki tek parça test nesnesi birden fazla gerçek modeli temsil etmiyordu. Yeni testte iki ayrı model aynı aktarımda kendi dosya yolları, farklı kalınlıkları ve **2 / 5 adet** değerleriyle hem DXF hem DWG olarak oluşturuluyor; değerlerin karışmadığı kontrol ediliyor. Aktarım fonksiyonu bu testte taklit edilmiyor; yalnızca COM sınırı temsil ediliyor.

Görsel kontrolde Linux'ta bulunmayan Segoe UI'ın küçük sabit yazı tipine dönüştüğü görüldü. Linux için Helvetica/Courier kullanıldı; Windows'taki Segoe UI/Consolas seçimleri korundu. Ayarlar alanı, yeterli yükseklik varsa içeriğine göre büyüyor. Küçük pencere ve geniş pencerede tarama düğmesinin görünürlüğü sınanıyor. Son tasarımda arama, durum filtresi, ayrıntı penceresi, kalıcı açık/koyu tema ve %125 ölçekleme de sınandı; ayrıntılar [GUI raporunda](gui-design.md).

Son uygulamadan **1240×860** boyutunda doğrudan alınan ekran görüntüleri: [DXF/DWG açık](screenshots/gui-dxf-dwg-light.png), [DXF/DWG koyu](screenshots/gui-dxf-dwg-dark.png), [PDF açık](screenshots/gui-pdf-light.png) ve [PDF koyu](screenshots/gui-pdf-dark.png). Görseller tasarım çizimi değildir; çalışan Tk penceresinden alınmıştır. Buluttaki yazı tipleri Windows'takilerden farklıdır.

## Tekrarlama ve kapsam ölçümü

Windows:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Bulut ortamı:

```bash
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user .venv/bin/python -m unittest discover -s tests -v
```

K/R öncesi tarihsel GUI denetiminde ek test aracı `coverage==7.16.2` ile ölçülen sonuç: **1457 çalıştırılabilir satırın 1416'sı (%97,2)**; satır/dal birleşik kapsamı **%96**. Çalıştırılmamış istisna yolları ve Windows'a özgü davranışlar bulunduğundan %100 doğrulama iddia edilmiyor. Coverage yalnızca test ortamına kuruldu, uygulamanın bağımlılıklarına eklenmedi.

```bash
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user \
COVERAGE_FILE=/tmp/gokworks-gui-reaudit.coverage \
.venv/bin/python -m coverage run --branch \
  --source=pdf,dxf_dwg,solidworks,main,k_factor,gui \
  -m unittest discover -s tests -v
COVERAGE_FILE=/tmp/gokworks-gui-reaudit.coverage .venv/bin/python -m coverage report -m
```

Sanal ekranda CustomTkinter'ın kullanıcı font dizinine yazamaması nedeniyle font şekilleri yerine alternatif çizim yöntemi kullanıldığı uyarısı var; testler ve arayüz çalıştı. Bu durum SolidWorks aktarımıyla ilgili değildir.

## Gerçek SolidWorks kontrolünün sınırı

Linux ortamında SolidWorks/pywin32 COM çalıştırılamıyor. COM testlerindeki PDF/DXF/DWG çıktıları sentetiktir. Dört ek DXF örneği gerçek DXF biçiminde ezdxf ile yazılmıştır; SolidWorks açınımından üretilmemiştir. Windows dosya yayımlama kolu test nesneleriyle sınandı; gerçek Windows dosya sistemi çalıştırması değildir. DWG için yalnızca dosya boyutu/başlığı doğrulanır; tam DWG ayrıştırması ve açınım geometrisi doğrulanmış değildir.

Gerçek `.SLDDRW` için PDF sayfa sayısı ve çizim içeriği; gerçek `.SLDPRT` için açınım ölçüleri, kontur/büküm çizgileri, yön, kalınlık ve dosya adındaki montaj adedi Windows/SolidWorks'te kontrol edilmelidir. [Kullanım kılavuzu](../README.md#akşam-yapılacak-solidworks-kontrolü) bu kontrolleri açıklar.

## GUI baştan sona yeniden kontrolü

Önceki 128 test yeniden geçti. Gerçek düğme komutları ve Tk klavye/fare olaylarıyla 12 ek kabul testi çalıştırıldı. İlk boyutlandırma açıkça zamanlanarak ilk Configure olayına bağımlılık giderildi. Son tam çalıştırmada 140 test başarılı, 0 başarısız, 0 atlanan; GUI kapsamı 34 testtir. 12 boyut/tema/ekran alt senaryosu da geçti. [Word raporu](reports/GOKWORKS_GUI_Test_Raporu_2026-10-09.docx), [kanıt dosyaları](reports/README.md).

## K/R sürümü sonrası son kontrol

174 test başarılı; 39 gerçek GUI testi. K/R kapsamında 34 yeni test (29 hesaplama/COM, 5 GUI) var. Kaydırma çubuğunun varsayılan 200 px minimumu yeni ayar alanını daraltmayı engelliyordu; 24 px olarak ayarlandı. Tarama/hesaplama/kayıt seçimi kaydırma alanı dışına alındı. İki tema, küçük/büyük pencere ve %125 ölçek sınandı. [Güncel kanıtlar](reports/k-radius/README.md) ve [Word raporu](reports/k-radius/GOKWORKS_K_RADIUS_GUI_Raporu_2026-10-09.docx).

## Kalınlığa göre manuel K/R

15 yeni test eklendi; son tam çalışmada 189 test geçti, 44 GUI testi. Kullanıcı girdiği K ve R doğrudan yazılır, hedef kalınlıkla eşleşmeyen saclar atlanır. K/R sekmesinde iki bağımsız alt sekme var. İçerik/sekmeler değişince yerleşim tekrar ölçülerek küçük pencerede tabloya alan ayrılır. [Son kanıtlar](reports/manual-k-radius/README.md) ve [kullanım](manual-k-radius.md).

## Son kaynak ve GUI denetimi

199 test geçti. Beş PDF regresyon testi ve beş GUI testi eklendi. Yanlış kaynak/aktif çizim, uzun geçici ad, hedef klasörü ve COM kapanış hatası düzeltildi. Sonuç sekmesi değişimi yeniden ölçülüyor; ilk pencere desteklenen ekran ölçüsüne göre açılıyor. 112 yerleşim senaryosu, 144 menü seçimi ve 108 dış BA hesap karşılaştırması geçti. [Kaynaklar, görüntüler ve kapsam sınırları](reports/final-audit/README.md).

## ISO geçmeleri eklemesi

216 test geçti; 58 gerçek GUI testi. ISO GEÇMELERİ için 8 hesap ve 9 arayüz testi eklendi. 1–400 mm, 11 delik / 18 mil sınıfı; tam sayı nm sapmaları ve Decimal hesap. 3217 kaynak kontrolünde bilinen F8 ≤3 mm kaynak hatasından iki fark kaydedildi; 0 beklenmeyen fark. Resmî ISO metnine ağ erişimi engellendi; uygulama ISO sertifikası iddia etmez. [Hesap, kaynaklar ve kapsam](iso-fits.md), [güncel kanıtlar](reports/iso-fits/README.md).

## Manuel ISO tolerans kontrolü

230 test geçti; 64 gerçek Tk GUI testi. Kullanıcının üst/alt sapmalarıyla geçme hesaplanır; tam ISO sınıfı ve en yakın mevcut sınıf/farkları ayrı verilir. Yağlı/kayar kullanım açıklamaları öneridir; boyut limitleri yağlama veya montaj kuvvetini kanıtlamaz. 8 hesap + 6 GUI testi eklendi; bütün önceki testler tekrar geçti. [Yeni kanıt ve Word raporu](reports/manual-iso/README.md).

## Montaj uyumu kontrolü

240 test geçti; 68 GUI testi. 6 hesap ve 4 arayüz testi daha eklendi. Montaj hedefleri tüm ölçü limitlerine göre değerlendirilir; referans çift/yaygın geçme, gerçek geçme türünün yerine kullanılmaz. Mil ±0,1, delik +0/−0,05 örneğinde −0,15…+0,10 mm ara geçme; tüm parçalarda serbest veya tüm parçalarda sıkı geçme garantisi yok. [Yeni kaynak hashleri, ekran ve Word raporu](reports/fit-compatibility/README.md).
