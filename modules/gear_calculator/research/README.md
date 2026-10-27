# Araştırma ve seçim kaydı · 27 Ekim 2026

Bu çalışma bağımlılık ve somut kaynak incelemesidir. Aşağıdaki projelerin
testleri GOKWORKS test sonuçları gibi gösterilmez; bu projeler kurulup CAD/FEM
testleri çalıştırılmadı. Motor kaynakları GOKWORKS'e kopyalanmadı.

## Mevcut GOKWORKS mimarisi

Başlangıç `49ba2a3c115bbc019d00618a7b14801a69ec5a1f` ana dalıdır.
Python/PySide6 6.10.3 / Qt Widgets; web frontend/backend veya HTTP routing yoktur.
`gui_qt/app.py` sayfaları bir kez oluşturur; `QStackedWidget` ile `navigate(mode)`
görünür sayfayı değiştirir. `gui_qt/workspace.py` çalışma alanlarını gruplar.
`BasePage`, iki tema ve `JobManager` ortak arayüz/arka plan sözleşmesidir.
Hesap modülleri `modules/<özellik>/` altında saf motor + `ui.py` + testler + README
olarak düzenlenmiştir. `AGENTS.md` bulunmadı.

Mevcut ezdxf DXF, Shapely/GEOS geometri, NumPy ve yerel Qt OpenGL/CPU
görüntüleyici kullanılabilir. SOLIDWORKS COM yalnız onu gerektiren modüllerde
Windows'ta devreye girer. Bu dişli modülü hesap/CAD için COM kullanmaz.
Bağımlılıklar pip/pinlenmiş requirements dosyaları, testler pytest/pytest-qt/
pytest-timeout, dağıtım Windows Python 3.13 x64 / PyInstaller tek dosyadır.

## İncelenen projeler

| Proje / sabit kaynak | Lisans ve ticari kullanım | İncelenen somut dosyalar / sonuç |
| --- | --- | --- |
| [py_gearworks](https://github.com/GarryBGoode/py_gearworks/tree/e7583713b8b7dfc3747acce6c82696b0ac0a3ba9) | Apache-2.0; bildirim/lisans ve değişiklik koşullarıyla ticari kullanım mümkündür | `src/py_gearworks/gearteeth.py`: parametrik evolvent ve dip bağlantısı; `wrapper.py`: `build_part`, `mesh_to`; `conv_build123d.py`: NURBS/B-Rep ve OCP 8 API geçişi; `tests/test_03_gear.py`: Shapely ile doğru/yanlış faz kesişim testleri. |
| [python-gearbox](https://github.com/efirvida/python-gearbox/tree/c005e4d50b4fcee649866f5e2437265335077132) | MIT; telif ve izin bildirimi korunarak ticari kullanım | `pyproject.toml`, `standards/iso6336/bending.py`: sonuç veri sınıfları ve ayrı ISO faktörleri; `standards/agma2101` ve `export` ağacı. Gelecek mukavemet katmanı için incelendi, ISO uyumu devralınmadı. |
| [FreeCAD Gears](https://github.com/looooo/freecad.gears/tree/83ec154b1925347622b61812f75d2ed51e956b9f) | GPL-3.0 (ilgili dosyada v3 veya sonrası); ticari kullanım yasak değildir, dağıtılan türev/bağlı eser için copyleft koşulları değerlendirilmelidir | `pygears/involute_tooth.py`: taban/dip dairesi ayrımı, alttan kesilme seçimi ve normal/alın düzlemi; `tests/test_pygears_involute.py`: yarıçap, simetri, kapalılık ve trokoid kontrolleri. Kaynak veya FreeCAD motoru alınmadı. |
| [GEARpie](https://github.com/cfernandesFEUP/GEARpie/tree/cb30c9111e010890d7c4989cab4478f5a3b02bc2) | MIT; bu yalnız ana kaynakların lisansıdır; gmsh/FEM bağımlılıklarının ayrıca lisansı vardır | `CLASSES/CALC_GEOMETRY.py`: MAAG geometri, temas yolları / kavrama oranı; `INVOLUTE_GEOMETRY.py`: Litvin evolvent ve gerçek kesici trokoidi; README: temas, yağ filmi, kayıplar, DIN/VDI ve FEM kapsamı. Bu sonuçlar GOKWORKS'e uygulanmış gibi gösterilmez. |

`py_gearworks` ilk aday olarak değerlendirildi: PyPI 0.0.24, Python≥3.10,
build123d≥0.11, NumPy 2 ve SciPy gerektiriyor. Araştırma sırasında build123d
0.13.0; ek olarak svgpathtools, ocpsvg, ocp_gordon, SymPy, scikit-learn,
IPython, malzeme ve diğer bağımlılıkları taşıyor. Düz/helisel/konik/iç ve
planet yaklaşımları gelecekte tekrar değerlendirilebilir. Parametrik model
ve build123d üzerinden STEP/düzlem export sunar; doğrudan API'yi değişmez
GOKWORKS hesap sözleşmesine bağlayan adaptör olmadan entegre edilmedi.

### Eski PyPI / güncel python-gearbox ayrımı

Araştırmada PyPI `python-gearbox` paketi hâlâ **0.1.2.a.dev**:
Python 2.7 egg ve eski zip dağıtımıdır. Zip'te eski yazımla
`gearbox/transmition/gears.py` içinde `Gear` ve `Transmition` sınıfları vardır.
NumPy≥1.8, SciPy≥0.10, Jinja2≥2.7 bağımlılıkları da güncel API'den farklıdır.
İncelenen güncel kaynak Python≥3.11, `src/gearbox`
paket düzeni, NumPy≥2.2.6, SciPy≥1.15.3 ve Jinja2 ile yeni ISO/AGMA
modülleridir. Eski PyPI kurulumu güncel README/API'yi vermez.
Bu nedenle sürümü belirsiz `pip install python-gearbox` yeni modüle eklenmedi.

### Bakım, test, performans ve çalışma ortamı

- Son push gözlemleri: py_gearworks 24 Eylül 2026; python-gearbox 23 Ekim 2026;
  FreeCAD Gears 15 Eylül 2026; GEARpie 10 Ocak 2025. Bu tarihler kalite garantisi
  veya doğrulanmış mühendislik sertifikası değildir.
- İlk üç projede otomatik test ağaçları incelendi. GEARpie kaynak ağacında bir
  `tests/` dizini saptanmadı; görseller otomatik doğrulama sayılmadı.
- Performansları ortak bir benchmark ile ölçülmedi. Eğri örnekleme, native
  katı üretimi ve FEM iş yükleri farklıdır; hız sıralaması uydurulmadı.
- py_gearworks / python-gearbox Python süreçlerinde çalışabilir; FreeCAD geometrisi
  FreeCAD runtime ister. GEARpie bilimsel Python/gmsh iş akışıdır.
- Bu kütüphaneler doğrudan tarayıcı paketi değildir. Sunucu veya WebAssembly
  adaptasyonu olmadan React içine konulabilecekleri varsayılmadı. GOKWORKS Qt
  masaüstüdür; yeni web backend'i veya servis/API anahtarı eklenmedi.

## Seçilen CAD motoru ve dağıtım

`cadquery-ocp-novtk==8.0.1.1.0`, aynı sürümde `cadquery-ocp-proxy`; native OCCT
8.0.1. CPython 3.12 Linux ve 3.13 Windows x64 wheel dosyaları indirildi ve
içerikleri incelendi. Windows wheel yaklaşık 47.750.971 bayttır.
[Wheel üretim kaynağı](https://github.com/CadQuery/ocp-build-system/tree/eace4e42cfa2c162ac39bc36864534fe5f5787a6).
Saf hesap ve eğri tanımı GOKWORKS için yazıldı; üst düzey dişli kütüphanesi,
build123d, VTK, FreeCAD veya mukavemet motoru çalışma bağımlılığı yapılmadı.

[OCP](https://github.com/CadQuery/OCP) bağlayıcısı Apache-2.0,
[OCCT V8_0_1](https://github.com/Open-Cascade-SAS/OCCT/tree/V8_0_1) ise LGPL-2.1
ve ek OCCT istisnasıdır. Bu ayrım kullanıcı lisans ekranında da korunur.
Dağıtılan dinamik kitaplığı değiştirme/hata ayıklama hakları kısıtlanmamalıdır;
`GOKWORKS_CAD_DIR` uyumlu harici OCP/proxy/DLL seçimini sağlar. Değiştirilmiş
LGPL bileşenleri dağıtılırsa ilgili kaynak ve değişiklikler de sağlanmalıdır.

Windows wheel'de OCCT'ye ek FreeImage, FreeType, OpenEXR/Imath, JPEG, LCMS2,
Lerc, XZ/liblzma, PNG, WebP, OpenJPEG/OpenJPH, LibRaw, TIFF, zlib, zstd,
libdeflate ve Microsoft çalışma zamanı DLL'leri vardır. Apache wheel etiketi
bunların hepsini Apache yapmaz. FreeImage için FIPL, LibRaw için LGPL-2.1,
zstd için BSD seçeneği kullanılır; GPL seçeneği otomatik benimsenmez.
Tam bildirimler `packaging/licenses/gears/native/` altında; FreeType için
mevcut `QtBase-FreeType-FTL.TXT` ve ilgili bildirimler de paketlenir.
[Bildirim kaynakları / metin SHA256 envanteri](native-notices.json).
Bu envanter metin provenansıdır; tüm yerel kodeklerin birebir derleme sürümü
tespiti olarak sunulmaz. Yeniden dağıtımda gerçek wheel/DLL sürümleri korunmalıdır.

## Görsel referans

[Gear Generator](https://geargenerator.com/) sayfasının parametre/animasyon,
görünürlük, dişli seçimi ve export iş akışı incelendi. Özel kaynak kodu veya
arayüz varlıkları kopyalanmadı; yerel GOKWORKS teması, seçim ve paneller kullanıldı.
Bu tarayıcı okuması WebGL2 etkileşimli render testi değildi.

## Kabul sınırı

Standart sıfır kaydırmalı dış düz çift için kapsam tanımlıdır. Gerçek azdırma
trokoidi ve alttan kesilmiş dişin imalat geometrisi yoktur. Kavraşma taraması
belirtilen örnek sayısında sayısal girişim kontrolüdür; elastik temas/FEM veya
ISO 6336 onayı değildir. Referans hesap, DXF geri okuma ve gerçek OCCT STEP
geri okuma testleri bu projenin `tests/` dizinindedir.
