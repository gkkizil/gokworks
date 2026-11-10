# Kaynak incelemesi — 10 Kasım 2026

Bu modülün Python kodu ve demo geometri/verileri GOKWORKS için yazılmıştır.
Aşağıdaki depolardan kaynak kodu, takım kataloğu veya çizim kopyalanmamıştır.
Araştırma dosyaları çalışma alanındaki `work/press-brake` altında saklanmıştır;
uygulama bu sayfalara bağlanarak çalışmaz.

| Kaynak | İncelenen konu / uygulanan sınır |
| --- | --- |
| [AyenseWorks](https://ayense.com/moduller/abkant-bukum), [Reels](https://www.instagram.com/reel/Ddb74z6MAT0/) | İçe alma → sıra → takım → 3B → föy akışı. Kullanıcının ek isteği üzerine herkese açık gömme sayfasındaki 43,14 saniyelik videoya erişildi; kareleri ve özellikle 21. saniyedeki üst/alt takım kartları, arama, favoriler ve sütun seçimi incelendi. GOKWORKS'te özgün kodla bu seçim akışı uygulandı. Video/üretici kart varlıkları dağıtıma alınmadı. |
| [Cincinnati katalog PDF](https://wwwassets.e-ci.com/PDF/Products/encompass-software-catalog.pdf) | Gerçek takım/istasyon geometrisi, adım planı ve çarpışma kapsamı; tezgâh modeli olmadan tezgâh güvenliği iddiası yok. |
| [Metec](https://www.metecmt.com/tools/bending-simulator) | Üst/alt takım çalışma referansı ve kanal seçimi; üretici varlıkları alınmadı. |
| [3D Bending Simulator](https://github.com/DenisPapushaJava/3d-bending-simulator) | `37e30d51ef842ea9ba2b2518ecb88a7736cf9872`; MIT kod lisansı gözlendi. Geometrik hareket, yerel temas, kesit/segment belgeleri okundu. Katalog verilerinin hakları kod lisansından ayrı ele alındı. |
| [starter-tools-v1.json](https://github.com/DenisPapushaJava/3d-bending-simulator/blob/37e30d51ef842ea9ba2b2518ecb88a7736cf9872/src/project/data/starter-tools-v1.json) | Yalnız şema incelendi: kesit kenarları, çalışma referansları, mm/radyan. Hiçbir katalog satırı veya üretici kesiti dağıtıma alınmadı. |
| [BendSeq](https://github.com/KanadeK/bendseq) | `774f6b81c9356ae2a67d5a02064956cfaa7c9b23`; MIT. 2B sıra ve tutuş ayrımı incelendi. Otomatik sıra arama bu sürümde yok. |
| [Open-MRP DFM](https://github.com/open-mrp/dfm) | `c3369de50fca51281abf97b2dba7f5c766dfb43e`; Apache-2.0. Flanş grafiği/dönüşümleri incelendi; bağımsız Python uygulaması yazıldı. |
| [WILA BIU-021](https://www.wilatooling.com/products/press-brake-tooling/new-standard-tooling/new-standard-premium/biu-021/), [OZU-313](https://www.wilatooling.com/products/press-brake-tooling/new-standard-tooling/new-standard-premium/ozu-313/), [Rolleri](https://www.rolleritools.com/tools-6437/press-brakes/tools) | Kart alanları, aile/bağlantı ayrımı için referans; dağıtım izni doğrulanmayan çizim/katalog gömülmedi. |
| [ISO 6909:2026](https://www.iso.org/standard/83403.html), [DIN 6935](https://www.dinmedia.de/en/standard/din-6935/144419944) | Kamuya açık başlık/kapsam bilgisi incelendi. Norm tam metni doğrulanmadı; standarda uygunluk veya makine güvenliği sertifikası iddia edilmez. |

SolidWorks 2025 yayımlanmış API belgeleri ayrıca kontrol edildi:
`IOneBendFeatureData.BendAngle`, `.BendRadius`, `.BendDirection`,
`.FlatPatternSketchSegments2`; `swBendDirection_UP/DOWN` kurulu swconst'tan;
`ISketch.ModelToSketchTransform`, `IMathTransform.Inverse()` **metot**;
`ICurveParamData.StartPoint/EndPoint`; `ICurve.GetTessPts` toleransları metre;
`ISurface.PlaneParams` normal + kök noktası; `IFace2.GetUVBounds`.
Yeni tip sac için Flat-Pattern bastırma/geri alma yolu seçildi;
`SetBendState`'in yeni base-flange parçalardaki kısıtı nedeniyle kullanılmadı.
Canlı COM yerine yayımlanmış çağrı biçimlerini uygulayan kontrollü doubles ile
birim, kimlik, aktif konfigürasyon ve geri alma testleri yapılır; bu canlı SW testi değildir.

Video erişimi için `cloud-desktop` becerisi de incelendi. Çalışan ortam
`ccarenv_b64_Y2NhcmVudl9kNDFkYmNmZDZmYWM4MTkxOWQ3ZDg2MDlkZTMyYTUwNQ`;
desktop yeteneği enabled/unknown olarak raporlandı, ancak `cua_repl.js` /
tarayıcı kontrol aracı sunulmadı. Bunun yerine kamusal Instagram embed kaynağı
ve yerel video kareleri kullanıldı; masaüstünde video oynatıldığı iddia edilmez.
