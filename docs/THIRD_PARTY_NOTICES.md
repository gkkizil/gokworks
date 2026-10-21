# GOKWORKS Qt sürümü — üçüncü taraf lisansları

## Nesting ve sac maliyeti · 20 Ekim 2026

Yeni çalışma bağımlılığı **Shapely 2.1.2 (BSD-3-Clause)** ve tekerlekteki
dinamik **GEOS (LGPL-2.1)** kitaplıklarıdır. Kurulu dağıtımın özgün lisansları
`packaging/licenses/nesting/` altında korunur; EXE lisans arşivine eklenir.
GEOS değiştirilmedi. Kaynakları: https://github.com/libgeos/geos ve
https://github.com/shapely/shapely/tree/2.1.2 . Tam GEOS sürümü kurulu
Shapely'nin `geos_version_string` değeriyle görülebilir; derlemenin wheel
envanteri dağıtımla saklanır. Python 3.13 Windows x64 wheel'i doğrulandı;
gerçek Windows EXE kontrolü sonraki istenen derlemede yapılır.

GOKWORKS NFP motoru bu proje için yazılmıştır. SVGnest'in NFP, önbellek,
rotasyon, sıralama araması ve `useHoles` / iç NFP yaklaşımı incelendi; özgün Python uygulaması
Shapely/GEOS üzerinde çalışır. SVGnest MIT bildirimi referans kaydı olarak
korunur. SVGnest/Deepnest JavaScript kodu, libnest2d/pynest2d C++ kodu veya
GPL kapsamlı Deepnest bileşenleri uygulamaya kopyalanmadı/bağlanmadı.
Pyclipper çalışma bağımlılığı değildir. [İncelenen dosyalar ve seçim](nesting.md).
[Delik içi yerleşim için sabit commit ve lisans kanıtları](nesting-hole-placement/README.md).

LGPL kitaplıklarıyla ticari dağıtım, lisans koşullarının karşılanmasına bağlıdır.
Qt değiştirme mekanizmasına ek olarak `GOKWORKS_GEOMETRY_DIR`, uyumlu
`shapely/` ve wheel'in `shapely.libs/` klasörlerini içeren bir dizinden
Shapely/GEOS yüklemeye izin verir. Windows DLL arama dizinleri açılışta
ayarlanır. Bu seçeneği kullanmak normal kullanıcı için gerekli değildir.
Alıcıların kitaplığı değiştirme/hata ayıklama hakları kısıtlanmamalıdır.
Uyumlu değiştirilmiş GEOS'un kaynakları/derleme bilgileri ilgili dağıtım
yükümlülükleriyle birlikte sağlanmalıdır. Üretim son kullanıcısı ek klasör
taşımaz; varsayılan tek EXE dağıtımı korunur.

## Tolerans yığılması modülü · 19 Ekim 2026

CodeStack (©2025 Xarial Pty Limited), EasyStackup (©2026 github.com/robertdosa)
ve tolerancing (©2026 saurabh-krishnan) referansları MIT lisansları doğrulanarak
incelendi/uyarlandı. Tam bildirimler `packaging/licenses/tolerance-stack/`
altında korunur ve Windows lisans klasörüne birlikte dağıtılır. Bu projeler
çalışma bağımlılığı olarak kurulmaz. [Kullanım kapsamı ve sürümler](tolerance-stack.md).

TolStack deposunda standart lisans dosyası doğrulanamadı; README'deki genel
izin ifadesi MIT olarak yorumlanmadı. 3D yaklaşımı incelendi, kod kopyalanmadı.
SolidWorks interop DLL'leri yalnız API meta verisini kontrol etmek için dış
geliştirme ortamında okundu; GOKWORKS içine eklenmedi veya dağıtılmadı.

## Mevcut Qt sürümü bildirimleri

Bu inceleme 18 Ekim 2026 tarihli geliştirme dalına aittir. Yeni arayüz kodu
proje için yazılmıştır; üçüncü taraf hazır arayüz veya ücretli ikon kopyalanmadı.
GÖK görselleri kullanıcı tarafından sağlanan mevcut marka varlıklarıdır.

Qt’nin üçüncü taraf font bileşeni için bildirim: Portions of this software are
copyright © The FreeType Project (https://freetype.org). All rights reserved.
FreeType için dağıtıma eklenen FTL koşulları esas alınır; metin lisans klasöründedir.

| Bileşen | Sürüm | Lisans / kullanım |
|---|---|---|
| PySide6, Shiboken6 | 6.10.3 | LGPL-3.0-only veya GPL seçenekleri / ticari Qt lisansı. Bu paket LGPL yolunu kullanır. |
| Qt Core, Gui, Widgets | 6.10.3 | LGPL v3 seçeneği. QML, Quick, WebEngine, Charts kullanılmaz. |
| Python | 3.13 | PSF lisansı; paketleyicinin Python çalışma zamanı dahildir. |
| pywin32 | 312 | BSD tarzı izinli lisans; kaynak başına ek bildirimler olabilir. |
| Pillow | 12.1.0 | MIT-CMU; mevcut bağımlılık korunur. |
| ezdxf | 1.4.3 | MIT; geçişli bağımlılık bildirimleri de dağıtılır. |
| openpyxl | 3.1.5 | MIT; et-xmlfile izinli lisansı. |
| PyInstaller | 6.16.0 | GPL v2+ ve bootloader istisnası; oluşturulan uygulamayı GPL yapmaz. |
| pytest / pytest-qt / pytest-timeout | 9.0.2 / 4.5.0 / 2.4.0 | MIT; yalnız geliştirme/test ortamında, uygulama çalışma yolunda bulunmaz. |

## LGPL ile ticari dağıtım

LGPL, koşulları karşılandığında kapalı kaynak ve ticari uygulamayla kullanılabilir.
Bu cümle koşulsuz bir “telif sorunu yok” garantisi değildir.

- Varsayılan dağıtım `--onefile --noupx` biçimindedir. Qt/PySide paylaşımlı
  kütüphaneleri açılışta geçici klasöre açılır; uygulamaya statik bağlanmaz.
- Uyumlu değiştirilmiş Qt/PySide/Shiboken paketleri `GOKWORKS_LIBRARY_DIR`
  klasöründen yüklenebilir. Runtime hook bu yolu Qt yüklenmeden önce uygular.
  Bu değiştirme mekanizması gerçek paket açılış kontrolünde doğrulanır.
  Geliştirici açık klasörlü dağıtımı `packaging/build_windows.py --onedir`
  ile de yeniden oluşturabilir. Kullanım ayrıntıları `packaging/README.md` içindedir.
- Alıcıların LGPL kütüphanelerini uyumlu değiştirilmiş sürümlerle değiştirmesine
  ve bunun için hata ayıklama/tersine mühendisliğe izin verilmelidir. Sonradan
  hazırlanacak EULA bu hakkı engellememelidir. Bu depoda engelleyici EULA yoktur.
- Lisans metinleri, telif bildirimleri, kaynak sürümleri ve kaynak edinme bilgisi
  EXE içindeki `licenses` kaynaklarında birlikte dağıtılır. Uygulamadaki
  **Lisanslar** ekranından okunur veya **Lisansları kaydet** ile tam arşiv alınır.
- Qt veya PySide kaynakları değiştirilmedi. Değiştirilirse ilgili kaynak ve
  değişiklikler LGPL koşullarıyla sağlanmalı; kurulum bilgisi yükümlülüğü ürünün
  dağıtım biçimine göre ayrıca karşılanmalıdır.
- Yeni Qt modülleri eklenirse lisansı yeniden incelenmeli; yalnız GPL sunulan
  modüller bu izin değerlendirmesine otomatik dahil değildir.
- GÖK markasının, CAD dosyalarının ve mühendislik standart metinlerinin hakları
  ilgili sahiplerindedir. Uygulama ISO/ASME standartlarının tam metnini dağıtmaz.

## Sürüme bağlı kaynaklar

- [PySide/Shiboken 6.10.3 kaynak ağacı](https://github.com/pyside/pyside-setup/tree/6.10.3)
- [Qt Base 6.10.3 kaynak ağacı](https://github.com/qt/qtbase/tree/6.10.3)
- [Qt 6.10.3 açık kaynak indirmeleri](https://download.qt.io/archive/qt/6.10/6.10.3/single/)
- [Qt for Python lisans açıklaması](https://doc.qt.io/qtforpython-6/licenses.html)
- [Qt LGPL yükümlülükleri](https://www.qt.io/licensing/open-source-lgpl-obligations)
- [pywin32 b312 lisansı](https://github.com/mhammond/pywin32/blob/b312/win32/License.txt)
- [PyInstaller lisansı ve istisnası](https://pyinstaller.org/en/v6.16.0/license.html)

`packaging/licenses` kanonik LGPL/GPL metinlerini, kullanılan dağıtımlardan
alınan izinli lisansları ve Qt üçüncü taraf bildirimlerini içerir. Derleme betiği
ayrıca kurulu bağımlılıkların lisans dosyalarını ve paket/sürüm/lisans envanterini
toplar. Ticari dağıtım öncesinde gerçek DLL envanteri, lisans bildirimlerinin
yeterliliği ve nihai EULA dağıtıcı tarafından kontrol edilmelidir.
