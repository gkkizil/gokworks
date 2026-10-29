# GOKWORKS proje denetimi — 23 Ekim 2026

Durum: **KOŞULLU OLARAK YAYINA HAZIR** — yerel hesap/GUI regresyonu geçti;
bu revizyon Windows EXE ve gerçek SolidWorks kabul testleri tamamlanmadan
CAD entegrasyonları doğrulanmış genel yayın olarak sunulmamalı.
İncelenen başlangıç: `main`, `4f11b5889ee697ab07ad28bcb881ff27607d3da8`.
Çalışmaya temiz çalışma dizininde başlandı. Yedek depoya ve `release` dalına
dokunulmadı. Arayüz teknolojisi ve modül adları korundu; özellik kaldırılmadı.

## Kapsam ve yöntem

Mevcut uygulama PySide6/Qt Widgets kullanıyor. `gui_qt/app.py` içindeki 14 kalıcı
sayfa, ortak `ValueForm`/tablo modelleri, tema, `SettingsStore`, `JobManager`,
`solidworks/connection.py`, PDF alt süreci ve Windows paketleme zinciri incelendi.
CAD çağrıları iş parçacığı/STA veya PDF için ayrı süreçte; saf hesaplar Qt/COM
başlatmadan kullanılabiliyor. Profil kesimi mevcut 2D nesting'den ayrı 1D motordur.

`docs/audit/inventory.json` bütün izlenen ve yeni Python dosyalarının yollarını,
satır sayılarını, SHA256 imzalarını, sınıf/fonksiyon sayılarını, yerel erken import
bağlantılarını ve incelenmesi gereken dosya/süreç çağrılarını içerir. AST/compile
denetimi ve Ruff hata taraması uygulanmıştır. Bu envanter, her yardımcı betiğin
her çalışma yolunun canlı olarak çalıştırıldığı anlamına gelmez.
Envanter **300 Python dosyası / 45.507 satır** içerir; test/örnek/tarihsel
yardımcılar dışındaki **139 uygulama/altyapı dosyası** ayrıca gözden geçirildi.

`requirements.txt`, `requirements-dev.txt`, `pytest.ini`, Windows requirements,
`.github/workflows/windows-exe.yml`, PyInstaller veri kaynakları, tema/ikonlar ve
mevcut üçüncü taraf bildirimleri incelendi. `pyproject.toml` bulunmaması mevcut
pip/requirements düzeninde hata sayılmadı; paketleme mimarisi değiştirilmedi.

## Bulgular ve düzeltmeler

Öncelik dağılımı: **0 kritik, 2 yüksek, 5 orta, 2 düşük**. Sekiz bulgu giderildi;
genel tip denetimi borcu açık. Windows/SolidWorks doğrulaması ayrıca bekliyor.

| Kimlik | Öncelik | Dosya / sorun | Uygulanan çözüm ve doğrulama |
| --- | --- | --- | --- |
| A01 | Yüksek | `requirements.txt`: Pillow 12.1.0 için güvenlik bildirimleri | Pillow 13.0.0 sabitlendi. Eski taramada 72 bildirim kaydı / 54 farklı bildirim kimliği vardı; bunlar uygulamada 72 istismar doğrulandığı anlamına gelmez. Güncel doğrudan ve kurulu geçişli paketler, ayrıca pywin32/PyInstaller sürümleri için tarama sıfır bilinen bildirimle tamamlandı. Güncel Pillow ile hesap/GUI/Excel/PDF testleri yürütüldü. |
| A02 | Yüksek | `modules/profile_cutting/models.py`, `ui.py`, `optimizer.py`: yeni taramada değişen/silinen kaynak, eski kesim planıyla kullanılabiliyordu | Kök kaynak/konfigürasyon ve satır revizyonu eşleştirmesi eklendi. Değişen/eski satır hesap ve üretim raporunu engeller; plan silinir, kullanıcı değerleri korunur. Yeni alanlar varsayılanlıdır; eski v1 JSON açılır. Başka montaj ve konfigürasyonlar etkilenmez. |
| A03 | Orta | `modules/k_factor/rules.py`: büyük sonlu girdiler BA/BD için `inf`/`nan`; çok küçük açı sıfıra bölme üretebiliyordu | Türetilen uzunluklarda sonluluk ve radyana dönüşümde alt taşma kontrolü. Yanlış sonuç yerine anlaşılır `ValueError`; normal bağımsız büküm örnekleri korunur. |
| A04 | Orta | `shared/settings.py`: sabit `settings.tmp` eşzamanlı yazmada çakışabilir ve kullanıcıya ait aynı adlı dosyayı ezebilirdi | Benzersiz aynı klasör geçicisi, serileştirmeden sonra yazma, flush/fsync, atomik replace ve her durumda temizlik. Boşta kalan/başarısız geçici dosyalar, yarış ve önceki kayıt koruması test edildi. Sonlu olmayan JSON reddedilir; Qt kayıt hatasını gösterebilir. |
| A05 | Orta | `modules/nesting/dxf_export.py`: kesim sırası CSV'sinde formül gibi başlayan parça kodu | CSV metin alanları apostrofla korunur. Beş formül/boşluk örneği test edildi. CAD parça kodu ve DXF geometrisi değiştirilmez. |
| A06 | Orta | `modules/profile_cutting/storage.py`: bozuk kaydedilmiş taramanın metin/bool/adet/property alanları Qt'ye ulaşabiliyordu | Yükleme sınırında tür/listeler/adet kontrolleri; NaN/Infinity JSON ve aşırı iç içe kayıtlar açık hata verir. Geçerli ve eski v1 kayıtları korunur; hatalı proje mevcut UI verisini değiştirmez. |
| A07 | Orta | `modules/profile_cutting/optimizer.py`: her parçada bütün açık stokları Python döngüsüyle aramak | Aynı best-fit sırası ve eşitlikte stok indeksi korunarak sıralı boşluk listesinde ikili arama. Decimal hesaplar ve bağımsız plan doğrulayıcısı korunur. 100 küçük rastgele örnek bağımsız subset-DP ile karşılaştırılır. |
| A08 | Düşük | `modules/weight/examples/capture.py`: eski Tk yöntemleri nedeniyle yeniden görüntü alma betiği çalışmıyordu | Mevcut Qt sayfası, native widget görüntüsü ve geçici tercihler kullanılır. Beş malzeme/katalog örneği çalıştırıldı. Uygulama ekranı yeniden tasarlanmadı. |
| A09 | Düşük, açık | Qt/COM ve yardımcı kodlarda Pyright tip bildirimleri | Genel tarama temiz değildir. Dinamik COM dönüşleri, Qt'nin kısa enum adları, `QObject.thread`/`QWidget.layout` ile aynı adlı Python alanları, varsayılanlardan çıkarılan dar tipler ve Linux'ta bulunmayan Windows modülleri başlıca kaynaklardır. Bu bildirimlerin tamamı çalışma hatası sayılmadı ve gizlenmedi. Ayrı kademeli tip iyileştirmesi gerekir. |

Nesting PDF'sindeki `writer` için ilk Ruff uyarısı çalışma hatası değildi:
yerel kapanış fonksiyonlarının kullandığı nesne döngüler bittikten sonra
`del` ile bırakılıyordu. Serbest bırakma `writer = None` ile açık hale getirildi;
PDF testleriyle kontrol edildi. Bu değişiklik CSV hatası olarak sayılmadı.

Kullanılmayan import ve aynı gövdeli fonksiyon adayları ayrıca kaydedildi.
Önemli bölümü tarihsel test kopyaları, test fixture importları ve uyumluluk
yeniden dışa aktarımlarıdır. Sadece benzer/boşta göründüğü için dosya silinmedi.
Erken yerel import grafiğinde döngü bulunmadı; çalışma zamanı import testleri de
modül motorlarının Qt/COM olmadan yüklenmesini kontrol ediyor.

## Modül ve senaryo matrisi

Bu tablo otomatik ve kontrollü test kapsamını gösterir; her düğmenin bütün
olası gerçek CAD dosyalarında çalıştığı iddiası değildir. Ayrıntılı test kimlikleri
son JUnit raporundadır. `Mock`, gerçek SolidWorks testi anlamına gelmez.

| Modül | Normal / hatalı kullanım ve çıktı | Hacim, tekrar, iptal / hata sınırı | Gerçek ortamda kalan |
| --- | --- | --- | --- |
| PDF aktarımı | Klasör seçimi, tüm sayfalar, bozuk PDF başlık/EOF, eksik kaynak, hedef çakışması; COM mock | Süreç protokolü, yarım mesaj/native çıkış, iptal, belge sahipliği ve COM bırakma; GUI temizleme | Windows'ta art arda gerçek SLDDRW PDF aktarımı ve kapanma günlükleri |
| DXF / DWG | Sac açınımı seçenekleri, çıktı adı, API hata/uyarıları; mock | İptal, konfigürasyon/aktif belge geri dönüşü, geçici çıktı | Gerçek sac geometrisi, büküm çizgileri ve sürüme göre COM davranışı |
| 3D Dönüştürücü | Çoklu kaynak/dosya/klasör, sekiz format, STEP/IGES/STL/Parasolid yapı doğrulayıcıları | Yinelenen kaynak, ad çakışması, değişen kaynak/konfigürasyon, iptal ve salt okunur oturum; mock | Native model bütünlüğü ve gerçek SW sürümüyle her format |
| BOM | Montaj ağacı/adet/ağırlık ve Excel; eksik bilgi uyarısı | Tekrarlanan parçalar, alt montajlar, iptal/COM temizliği; mock | Gerçek model/konfigürasyon/property ve kütle doğruluğu |
| İsimlendirme / Pack and Go | Plan, güvenli adlar, kaynak/hedef çakışması, API imzası ve yerel .NET köprüsü; mock | Kısmi hata, iptal, kaynak koruma, bağlantı/başvuru kontrolleri | Kurulu SW interop ile gerçek paket ve teknik resim referansları |
| K faktörü / yarıçap | BA/BD, ölçülmüş BA'dan K, kalınlığa göre manuel K/R, takım şeması | Geçersiz/taşan girdi, uyumsuz kalınlık ve COM geri alma; mock | Gerçek SheetMetal yazma, tüm bükümler, rebuild sonrası geri okuma |
| ISO geçme toleransları | ISO 286 tablo aralıkları, alt/üst limitler, manuel/ISO ortak kesit | Sınıf sınırları, eşleşme, sıfır/boşluk/sıkılık, tema ve görünüm ölçeği | Tam standardın desteklenmeyen sınıfları otomatik tahmin edilmez |
| Geometrik toleranslar | Katalog, datum, toplam hata kontrolü, sayısal sınırlar | Geçersiz/uyumsuz seçimler ve diyagramlar | Tam 2D/3D GPS çözümü/ölçüm cihazı doğrulaması kapsam dışı |
| Tolerans yığılması | İşaretli/asimetrik WC, RSS, seed'li Monte Carlo, ISO girdisi, JSON/PDF/Excel | Eksik tolerans, süreksiz zincir, tekrar ölçü, kaynak revizyonu, iptal; okuma/yazma mock | Gerçek SLDDRW ölçü/tolerans okuma, ek anotasyon ve farklı kaydetme |
| Cıvata hesabı | Çekme/kesme/birleşik yük, dişli/dişsiz kesit, yük birimleri | Sıfır, negatif, geçersiz sayı, emniyet sınırları, adet ve grafik | Statik eşit yük paylaşımı yaklaşımı; tam bağlantı/yorulma analizi değildir |
| Hızlı tork | M3–M36, normal/ince diş, kalite/çap sınırı, K ve ön yük | Hatalı/boş/aşırı giriş, sıfır ön yük, kopyalama ve yaklaşık K açıklamaları | Gerçek yüzey sürtünmesi/üretici tork şartnamesi |
| Ağırlık | 19 kesit, katalog alanı, sabit malzeme yoğunluğu, mm/cm/m | Geçersiz geometri, adet, taşma, tekrarlı birim değişimi | Radyüs/üretim toleransı ve gerçek malzeme yoğunluğu ölçülmez |
| Nesting / sac maliyeti | Gerçek DXF konturu/delik, açık kontur reddi, çoklu plaka, stok ve maliyet | 50 kopya, farklı şekiller, otomatik delik içi yerleşim, çakışma/kenar/kerf doğrulaması, iptal; bozuk JSON/DXF | Çok büyük gerçek müşteri DXF kümesiyle tezgâh/CAM doğrulaması ve kesim sırası |
| Profil kesim / Weldments | Çok gövde, montajda 5 örnek, konfigürasyon, property mapping, adet/uzunluk, stok+kerf | Boş/eksik LENGTH, 45° ve eğri profiller, tekrar/değişen tarama, 10.000 profil, iptal; mock | Gerçek Cut List/BodyFolder/konfigürasyon/ham stok doğrulaması |

Mühendislikte korunmuş sınırlar: bilinmeyen tolerans uydurulmaz; çap/radyüsün
1D ilişkisi kullanıcı tarafından doğrulanır; RSS bağımsızlık ve sigma varsayımı
açıktır; Cp/Cpk simülasyondur. Açılı/kavisli profiller doğrulanmış ham boy
olmadan üretim için hazır sayılmaz. K ve yoğunluk varsayımları kesindir diye
sunulmaz. Nesting optimum veya CAM takım yolu garantisi vermez.

## Sayısal doğrulama

`tests/test_audit_engineering_oracles.py` bağımsız literal örnekler içerir:

- A=50±0,10, B=20±0,05, C=29,80±0,03 için A−B−C: nominal **0,20**, WC **0,02–0,38 mm**.
- Kesilmemiş normal RSS üç-sigma yarı bandı **√0,0134 ≈ 0,115758 mm**; WC ile eşitlenmez.
- Ø50 H7: **0/+0,025 mm**; h6: **−0,016/0 mm**; tabloda tam sayı nm saklanır.
- M10×1,5, 8.8, %70, K=0,20: yaklaşık **25,984 kN**, **51,968 N·m**. Alan formülüyle fark için ±0,02 N·m test toleransı; yağlı/kuru oranı 0,75.
- 100×1000×2 mm çelik levha: **1,57 kg**; cm/m girişleri ve nesting kütle hesabı aynı sonucu verir.
- t=R=2 mm, K=0,4, 90°: BA **4,39822971502571 mm**, BD **3,60177028497429 mm**, mutlak tolerans 10⁻¹² mm.

Teknik dayanaklar modül README'leri ve mevcut kaynak/lisans bildirimlerindedir:
ISO 286 tablo verileri; ISO 898-1 dayanım tanımları; metrik çekme alanı yaklaşımı;
BA=θ(R+Kt), BD=2(R+t)tan(θ/2)−BA; hacim×yoğunluk; işaretli aralık aritmetiği ve
bağımsız dağılım momentleri. Bu denetimde yeni lisanssız algoritma kopyalanmadı.

## Performans ve GUI

- 10.000 adet, her biri ayrı stok gerektiren 3500 mm profil: üç tekrar medyanı
  **2,895 → 0,168 saniye**, yaklaşık **17,2 kat**. 5000 adet: **0,779 → 0,072 saniye**.
  Aynı donanım/örnek, tam stok sayısı korunur; bu bütün yerleşim örnekleri için hız garantisi değildir.
- 14 sayfa / iki tema / dört çözünürlük kaynak self-check geçti. Ek minimum
  820×560 ve 1440×900 testleri arayüz testlerinde bulunur.
- Ayrı ölçümde importlar dahil açılış **813 ms**, 140 geçişte medyan **5,56 ms**,
  en uzun geçiş **40,47 ms**; timer en büyük aralığı **40,34 ms**.
- Tepe RSS **185.548 KiB (~181 MiB)**. Sayfa geçişi öncesi/sonrası widget sayısı
  **2352/2351**: bu örnekte sayfa başına sürekli widget birikimi görülmedi;
  ölçüm uzun süreli native heap/COM sızıntısı olmadığını kanıtlamaz.
- 50.000 satır: yükleme **38,91 ms**, filtre **114,70 ms** (kaynak self-check).
  Üretim CAD dosyalarının açılış/aktarım süresi bu Linux ortamında ölçülmedi.

## Güvenlik, dosya ve dağıtım

Atomik proje/rapor yazımı, mevcut hedefi izin olmadan değiştirmeme, yalnızca
işlemin kendi geçici dosyasını temizleme, iptalde önceki dosyayı koruma ve CSV/Excel
metin güvenliği incelendi. `shell=True`, uygulama girdisiyle `eval` ve pickle
yükleme bulunmadı. Qt `dialog.exec()` dinamik Python kod çalıştırması değildir.
Süreçler argüman listeleriyle başlatılıyor. Normal mühendislik akışlarında
zorunlu ağ çağrısı yok; bağımlılık güvenlik taraması yalnız paket adlarını/sürümlerini
PyPI'ye sorar. CAD içerikleri denetim için dış servise yüklenmedi.

Tanılama logları dosya içeriği/yerel değişken dökmez; hata arayüzleri ve kullanıcının
istediği raporlar kaynak yollarını içerebilir. Rapor paylaşırken bunlar kullanıcıya
ait ticari/kişisel bilgi olabilir. Bilinen açık taraması gelecekte güvenlik
açığı bulunmayacağı garantisi değildir; Qt içine gömülü tüm üçüncü taraf C/C++
bileşenlerinin ayrıca exploit analizi yapılmadı.

PyInstaller onefile/onedir kaynak eşlemeleri, ikon/ISO JSON/.NET kaynak dosyası,
Qt runtime hook'u ve platform eklentisi kontrolleri mevcut testlerle doğrulandı.
Bu ortam **Linux**: bu revizyonla Windows EXE derlemesi, DLL yükleme, SmartScreen,
Defender veya gerçek Windows masaüstü testi çalıştırılmadı. Linux'ta bir betiğin
adının `run_windows_tests.py` olması sonucu Windows testi yapmaz. Önceki bir
EXE'nin başarılı olması bu revizyon için kanıt olarak kullanılmadı.

## Test komutları ve kanıtlar

Ortam: Python 3.13.5, PySide6/Qt 6.10.3, `QT_QPA_PLATFORM=offscreen`.
Pillow 13.0.0 proje içi `.cache/runtime-updated` dizinine kurularak
`PYTHONPATH` ile kullanıldı; mevcut paylaşılan Python ortamı değiştirilmedi.
Paketlenmiş dağıtımda `requirements.txt` aynı sürümü kurar.

```bash
python packaging/audit_project.py --output docs/audit/inventory.json
python -m ruff check . --exclude .cache --select F821,F822,F823,E9 --output-format json
python -m pip_audit --no-deps --disable-pip -r requirements.txt --format json
python -m pyright --pythonpath <qt-python> main.py gui_qt shared solidworks modules --outputjson
QT_QPA_PLATFORM=offscreen python packaging/run_windows_tests.py
QT_QPA_PLATFORM=offscreen python main.py --self-check docs/audit/source-selfcheck.json
QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=1.25 python main.py --self-check docs/audit/source-dpi-125.json
QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=1.5 python main.py --self-check docs/audit/source-dpi-150.json
QT_QPA_PLATFORM=offscreen python docs/report-tools/measure_audit_ui.py docs/audit/ui-performance.json
QT_QPA_PLATFORM=offscreen python modules/weight/examples/capture.py --output-dir docs/audit/weight-screens
```

Tam kurulumda komutların başındaki `python`, Qt ve requirements yüklenmiş
yorumlayıcıdır. Bu oturumda `/workspace/.cloud-setup/qt-venv/bin/python`
kullanıldı. Ruff/Pyright/pip-audit ürün bağımlılığı değildir; denetim araçları
proje içi `.cache/audit-tools` altına kuruldu.

Son tam regresyon **1161 test: 1152 başarılı, 0 başarısız, 0 hata, 9 atlanan**.
37 ayrı süreçte tamamlandı. **878 alt kontrol** ayrıca geçti; 1152 sayısına
tekrar eklenip bağımsız test gibi sunulmadı. 31 yeni regresyon senaryosu eklendi.
Ön çalıştırma ve hedefli testler ayrı dosyalardadır; toplamlar bunlarla şişirilmedi.
Atlanan gerçek SW/Windows testleri geçmedi. Tam nedenler `docs/audit/test-summary.json` içindedir.

| Denetim | Sonuç / kanıt |
| --- | --- |
| Tam regresyon | [Arşiv: final-regression.xml](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/audit/final-regression.xml), [çalıştırma kaydı](docs/audit/final-regression-run.txt) |
| Hedefli düzeltme testleri | 93 başarılı / 2 atlanan; 5 alt kontrol; [Arşiv: focused-tests.xml](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/audit/focused-tests.xml) |
| Delik yerleşimi + bağımsız mühendislik örnekleri | 27 başarılı; [Arşiv: geometry-oracles.xml](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/audit/geometry-oracles.xml) |
| AST/compile / erken yerel import döngüsü | 0 syntax hatası, 0 döngü; [inventory.json](docs/audit/inventory.json) |
| Ruff F821/F822/F823/E9, bütün ağaç | 0 bulgu; [static-all-critical.json](docs/audit/static-all-critical.json) |
| Geniş Ruff F/E9, uygulama+test+paketleme | 81 F401, 7 F811 inceleme adayı kaldı; test fixture/uyumluluk dışa aktarımları dahil. Gizlenmedi; [static-final.json](docs/audit/static-final.json) |
| Pyright | 218 dosyada 1262 hata / 29 uyarı; **başarılı sayılmadı**. Dinamik Qt/COM/tip borcu; [types-final.json](docs/audit/types-final.json) |
| Bilinen bağımlılık açıkları | Güncel doğrudan ve geçişli paketler + pywin32/PyInstaller: 0; [dependencies-transitive.json](docs/audit/dependencies-transitive.json) |
| Kaynak GUI self-check | 14 sayfa, 2 tema, 4 çözünürlük; [source-selfcheck.json](docs/audit/source-selfcheck.json) |
| Qt DPI benzetimi | 1,25 ve 1,5 geçti; [125](docs/audit/source-dpi-125.json), [150](docs/audit/source-dpi-150.json). Gerçek Windows DPI testi değildir. |
| Windows wheel çözümlemesi | Python 3.13 / win_amd64 için 14 runtime paketi çözüldü; [windows-dependency-resolution.json](docs/audit/windows-dependency-resolution.json). DLL çalıştırılmadı. |
| Yardımcı görüntü betiği | Beş örnek çalıştı; [weight-capture-run.txt](docs/audit/weight-capture-run.txt) |

PyInstaller/Windows paketleme betikleri ve kaynak yolları mock testleriyle
kontrol edildi. Atlananlar: iki Windows süreç gözlemcisi, gerçek pywin32,
3D canlı aktarım, .NET Pack and Go derleme/canlı okuma, canlı Weldments,
teknik resim okuma ve opt-in analizli kopya kaydıdır.

Test matrisinin modül bazında sayıları (ortak testler 218):
PDF 51; DXF/DWG 78; 3D 107; BOM 23; isimlendirme 62; K/R 161;
ISO 31; GD&T 14; tolerans yığılması 118; cıvata 18; hızlı tork 77;
ağırlık 13; nesting 112; profil kesim 78. Bunlar atlananları da içerir;
ortak GUI testleri ayrıca birçok modülü kapsar.

Kod ankrajları: `shared/settings.py:19` (`save_settings`),
`modules/profile_cutting/models.py:212` (`reconcile`),
`modules/profile_cutting/optimizer.py:40` (`optimize`),
`modules/profile_cutting/storage.py:55` (`validate_scan`),
`modules/k_factor/rules.py:65` (`_finite`),
`modules/nesting/dxf_export.py:24` (`export_dxf`).

Kaynak çalıştırma (Windows, Python 3.13):

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe packaging/run_windows_tests.py
# Gerçek Windows EXE ve frozen smoke için:
.\.venv\Scripts\python.exe -m pip install -r packaging/windows-requirements.txt
.\.venv\Scripts\python.exe packaging/build_windows.py
```

Canlı CAD testleri ilgili modüllerin README/test dosyalarındaki açık test-kopyası
ortam değişkenleriyle çalıştırılmalıdır. Bu komutlar burada Windows'ta çalıştırılmış
olarak raporlanmıyor.

## Değiştirilen dosyalar ve devam koşulları

Ürün: `requirements.txt`, `shared/settings.py`, `gui_qt/settings.py`,
`modules/k_factor/rules.py`, `modules/nesting/dxf_export.py`, `report.py`,
`modules/profile_cutting/models.py`, `optimizer.py`, `storage.py`, `ui.py`.
Yardımcı: `modules/weight/examples/capture.py` ve ilgili README; profil README.
Testler: `tests/test_audit_settings.py`, `test_audit_engineering_oracles.py`,
`modules/k_factor/tests/test_numeric_limits.py`,
`modules/profile_cutting/tests/test_revision_safety.py`, `test_ui.py`,
`modules/nesting/tests/test_hole_nesting.py`.
Denetim: bu rapor, `packaging/audit_project.py`,
`docs/report-tools/measure_audit_ui.py`, `docs/audit/` kanıtları.

Sonraki zorunlu doğrulama: Windows kaynak/onefile testlerini aynı revizyonda
çalıştırmak; gerçek SLDDRW ile uzun PDF oturumu, gerçek Pack and Go referansları,
K/R geri okuma, tolerans okuma/anotasyon ve Weldments miktar/konfigürasyonlarını
kontrollü CAD kopyalarında doğrulamak. Uygulama kapatma/COM iptali canlı bir
API çağrısını zorla öldürmez; SolidWorks kilitlenirse güvenli çıkış gecikebilir.
Kademeli Qt/COM tip tanımları, geçişli bağımlılıkların kilitlenmesi, daha büyük
gerçek DXF iş yükü ve uzun süreli bellek profili sonraki geliştirmelerdir.
