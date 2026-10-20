# Nesting ve sac maliyeti · teknik teslim kaydı

20 Ekim 2026 · kaynak: güncel çalışma dizini · PySide6/Qt Widgets,
Python 3.13; mevcut DXF altyapısı ezdxf 1.4.3, raporlar openpyxl 3.1.5,
PDF/çizimler mevcut QtGui. Yeni çalışma bağımlılığı **Shapely 2.1.2**.

## İncelenen kaynaklar ve seçim

| Depo / okunan dosya | Lisans / mimari | Entegrasyon kararı |
|---|---|---|
| [SVGnest](https://github.com/Jack000/SVGnest), `svgnest.js`, `util/geometryutil.js`, `LICENSE` | MIT; JavaScript, web worker, NFP önbelleği, genetik sıra/rotasyon, delik seçeneği | NFP ve çoklu arama yaklaşımı referans; uygulama için özgün Python yazıldı. MIT bildirimi korunur. JavaScript motoru gömülmedi. |
| [libnest2d](https://github.com/tamasmeszaros/libnest2d), `README.md`, `include/libnest2d/nester.hpp`, `LICENSE.txt` | LGPL-3.0; C++11 policy/backend, Boost/Clipper/NLopt. README delik/içbükey destek sınırlarını açıkça belirtiyor. | Python 3.13/Windows için özel native toolchain ve ABI paketleme yükü nedeniyle bu sürümde bağlanmadı. |
| [deepnest-next/deepnest](https://github.com/deepnest-next/deepnest), `README.md`, `LICENSE`, `LICENSES.md`, `package.json` | Ana lisans MIT; `LICENSES.md` `/main/deepnest.js` için **GPLv3**, başka dosyalarda Boost/MIT listeliyor. Electron/Node/native motor. | Ana MIT ibaresi bütün dosyalara genişletilmedi; GPL bileşenler veya diğer kodlar kopyalanmadı. |
| [pynest2d](https://github.com/Ultimaker/pynest2d), README, LICENSE, System Requirements | LGPL-3.0; SIP/CMake/Conan, Windows VS2022/nmake | Hazır Python 3.13 entegrasyonu varsayılmadı; yeni C++ build zinciri kurulmadı. |
| [ezdxf](https://github.com/mozman/ezdxf) README/LICENSE; kurulu 1.4.3 API | MIT; mevcut Windows/Linux Python bağımlılığı | İçe/dışa aktarma, blok dönüşümleri, özgün ARC/CIRCLE ve diğer DXF nesnelerini koruma için kullanıldı. |
| [Shapely](https://github.com/shapely/shapely), README/LICENSE; kurulu 2.1.2 | BSD-3-Clause + dinamik GEOS LGPL-2.1 | Poligon doğrulama, kısıtlı üçgenleme, NFP birleşimleri/farkları, gerçek mesafe/kesişim ve STRtree. CPython 3.13 Windows x64 wheel varlığı PyPI'dan doğrulandı. |
| [pyclipper](https://github.com/fonttools/pyclipper), README/LICENSE | MIT sarmalayıcı, Clipper 6.4.2 native; tamsayı ölçekleme ve Minkowski/offset | Ek native bağımlılık/tamsayı nicemleme eklenmedi; GEOS geometrisiyle aynı katmanda kalındı. |

Bu sürüm SVGnest/libnest2d çalıştırıyormuş gibi davranmaz: ekrandaki ve proje
dosyasındaki motor adı **GOKWORKS NFP 1.0**'dır. Kontur tabanlı Minkowski
ve çoklu sıra/rotasyon araması uygulanır; genetik algoritma veya global optimum
iddiası yoktur. Dışbükey toplamlar açısal kenar birleştirmesiyle, içbükeyler
doğrulanmış dışbükey alt parçaların birleşimiyle oluşturulur. Lisans incelemesi
dağıtım koşullarını listeler; ticari ürüne koşulsuz hukuki uygunluk garantisi değildir.

## Teslim edilen kod

- `nesting/`: veri modelleri, DXF okuyucu, geometri/NFP motoru, bağımsız
  doğrulama, ağırlık/maliyet, taşınabilir JSON, DXF/Excel/PDF, ortak çizim.
- `gui_qt/pages/nesting.py`, `nesting_widgets.py`: mevcut tasarım sistemi,
  iş yöneticisi, tablolar, koyu/açık tema ve dar/geniş pencere düzeni.
- `gui_qt/app.py`, `icons.py`: kalıcı yeni sayfa ve yerel vektör simgesi.
- `requirements.txt`, `packaging/build_windows.py`, `gui_qt/package_check.py`:
  Windows bağımlılık toplama ve gerçek dosyalarla paket açılış kontrolü.
- `solidworks/runtime.py`: isteğe bağlı Shapely/GEOS değiştirme yolu;
  mevcut Qt yolu ve normal varsayılan çalışma korunur.
- `packaging/licenses/nesting/`, `docs/THIRD_PARTY_NOTICES.md`: lisanslar.
- `tests/test_nesting.py`, `test_nesting_gui.py`, single-file lisans kontrolü.

## Doğrulama kapsamı

Zorunlu 13 kabul senaryosu gerçek geometri/dosya testlerindedir: dikdörtgen,
dairesel delik, yaylı kontur, açık/bozuk geometri reddi, 10 farklı parça,
50 aynı parça, ikinci levha, çakışma/kenar mesafesi, ağırlık/alan denkliği,
farklı malzeme/kalınlık grupları, Excel/PDF/DXF ve kaydet/yeniden aç.
Ek olarak içbükey L parçasının girintisine sınır dikdörtgenleri çakışan
bir parçanın aynı levhada yerleşmesi, daha büyük levhayla levha adedini
azaltma, hadde/rotasyon, birimler, bütün desteklenen DXF nesneleri,
blok dönüşümleri, stok yetersizliği, kuruş dengesi, iptal, eski sonucun
engellenmesi, değiştirilmiş saklı DXF'in reddi ve kaynak taşınması test edilir.

Qt testleri gerçek worker ve dosya işlemleriyle içe alma, yerleşim,
kaydet/aç ve raporları çalıştırır; işlem sırasında olay döngüsü ve
başka sayfaya geçişi kontrol eder. Küçük pencere listesi ve geniş pencereye
dönüş, her iki tema, geçersiz form ve önceki modüllerin gezinti/Temizle
kontrolleri kapsanır. Gerçek Windows EXE veya kesim tezgâhı bu Linux
ortamında çalıştırılmadı; SolidWorks API bu modül için gerekli değildir.

Kullanım, formüller, dosya formatı ve açık sınırlamalar:
[nesting/README.md](../nesting/README.md).

Gerçek DXF girişleri, taşınabilir proje, levha DXF'i, çizimli raporlar ve
ekran görüntüleri: [uçtan uca örnek](nesting-example/README.md).

Doğrulama kaydı (Linux/offscreen): 59 yeni modül/lisans/Qt kontrolü geçti;
175 mevcut DXF, BOM, ağırlık, cıvata, ISO ve tolerans yığılması testi ile
250 alt senaryo geçti. Gezinti/çözünürlük/Temizle dahil 43 Qt kontrolü geçti.
Boş proje/şablon kaydı ve gerçek uç birleştirme hata payı da denetlendi. Kaynak paket açılış
kontrolü 11 modül, 2 tema, 4 çözünürlük ve NFP/DXF/Excel/PDF için geçti.
Geometri ilerleme bildirimleri 80 ms'de bir birleştirilir; fitInView sırasında
scrollbar değişimiyle yeniden boyutlandırma döngüsü engellenir.
