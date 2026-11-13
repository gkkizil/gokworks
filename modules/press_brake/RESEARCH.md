# Kaynak incelemesi — 10 Kasım 2026

Bu modülün Python kodu ve demo geometri/verileri GOKWORKS için yazılmıştır.
İlk sürümde aşağıdaki depolardan kaynak kodu, takım kataloğu veya çizim
kopyalanmamıştı. Sonraki kaynak aktarımı ve kod atfı aşağıda belirtilmiştir.
Araştırma dosyaları çalışma alanındaki `work/press-brake` altında saklanmıştır;
uygulama bu sayfalara bağlanarak çalışmaz.

10 Kasım düzeltmesi: kullanıcı isteğiyle `sources.py`, sabit `37e30d51` sürümündeki
yedi gerçek takımın açık kaynaktan kişisel kütüphaneye indirilmesini destekler.
DXF varlıkları dağıtım paketine alınmaz. Kaynak `docs/licensing.md`, üretici
profillerinin MIT kod lisansından ayrı kaldığını açıkça belirtiyor. Çalışma ucu /
omuz geometrisi tanıma matematiği `src/core/ToolGeometry.cpp` referansıyla
uyarlanmıştır; MIT metni `packaging/licenses/press-brake` altında dağıtılır.
WILA ve Rolleri'nin dört ürününün açık teknik ölçüleri kaynak URL'leriyle bilgi
kartına alınmıştır. WILA indirmeleri oturum/e-posta ister; Rolleri otomatik
doğrudan erişiminde 403 döndürdü. Eksik CAD için geometri üretilmemiştir.

SolidWorks düzeltmesinde yayımlanmış `IFeature.GetOwnerFeature`,
`IFace2.GetFeature`, `ISurface.CylinderParams`, `IEdge.GetTwoAdjacentFaces2`
ve gerçek açınım yüzleri kullanılır. Aynı yarıçap ve açı tek başına eşleştirme
kanıtı değildir. Eş eksenlilik veya unsur sahipliği; kenar yan yüzlerinde de
komşu düzlemlerin doğrulanmış kalınlık ayrımı gerekir. Canlı SolidWorks testi
bu Linux ortamında yapılamaz; kontrollü API sözleşmeleri ayrı test edilir.

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

13 Kasım · açınım kenarı okuma: 12 Kasım'daki daire okuyucusunun zorunlu
`ICurve.Evaluate2` ve sabit dizi boyutu bağımlılığı kaldırıldı. Düz kenarlar
`ICurve.IsLine` ve gerçek uçlardan, daireler `CircleParams` merkez/eksen/R,
gerçek uçlar ve `abs(UMaxValue-UMinValue)` yay açıklığından okunur. `Sense`
üzerinden parametre işareti tahmin edilmez. Uçların verdiği iki yön belirsizse
(özellikle yarım daire), gerçek kırpılmış `IEdge.GetClosestPointOn` izdüşümleri
doğrulanır; bu API'nin beşinci değeri kullanılmayan alandır. Alternatif
`IEdge.Evaluate2` çağrısında kenarın ham U aralığı ve son double içindeki
paketlenmiş başarı kodu kullanılır; `ICurve.Evaluate2` ile aynı sözleşme değildir.
Yön doğrulanamazsa yay uydurulmaz. Delikler, büyük yaylar, ters kenarlar, eğik
çember düzlemleri, 0,02 mm kiriş toleransı ve 100.000 nokta sınırı korunur.
Diğer eğriler gerçek `GetTessPts` sonucunu kullanır; boşsa kısa parça filtresi
sıfırlanarak bir kez denenir. Eksik eğri düz kirişle değiştirilmez.

`Radyus4 / açınım kenarı 2` ve boş eğri değerlendirmesi kontrollü aktif-parça
örneğinde önce eski hatayı verdi, ardından aynı örnek yeni okuyucuyla geçti.
Bu, kullanıcının SLDPRT dosyasında canlı SolidWorks doğrulaması değildir.
Kontrollü testler delikleri, gerçek yay tarafını ve başarı/hata/iptalde
konfigürasyon, unsur ve seçim durumlarının geri yüklenmesini de kapsar.

Aynı incelemede ortak CAD oturumunun ve DXF dışa aktarıcının önceki belgeye
`ActivateDoc3` ile dönerken `swDocNeedsRebuildWarning=2` değerini ölümcül hata
saydığı yeniden üretildi. Resmî `swActivateDocError_e` bit maskesine göre belge
bu uyarıda etkinleştirilmiştir; yalnız 0 veya 2 kabul edilir. 1, birleşik 3 ve
bilinmeyen bitler reddedilir. Dönen belge ve gerçek `ActiveDoc` kimlikleri ayrıca
önceki belgeyle eşleştirilir. Bu uyarı tek başına önceki montajda zorla yeniden
oluşturma veya ek kayıt başlatmaz.
Gerçek geri yükleme hatası aktarımı engeller ve ilk hata arayüz günlüğünde ve
Ayrıntı metninde korunur. Kullanıcı ekranının ilk yerel hata nedeni ayrıca
alınamadığı için bu kontrol örneği canlı hatanın kesin teşhisi sayılmaz.

Yerel regresyon doğrulaması: abkant, DXF/DWG, ortak CAD dönüştürücü ve profil
kesim paketlerinde 932 test düğümü; **924 geçti, 8 atlandı**, ayrıca 44 unittest
alt kontrolü geçti. 44 ayrı süreçte hata/çökme/yeniden deneme olmadı. Atlananlar
Windows COM/yerel pencere veya lisanslı canlı SolidWorks ve açık test kopyası
ister. Bu sonuçlar üretim ortamında canlı parçanın alındığı anlamına gelmez.

- [GetTessPts · toleranslar ve dizi biçimi](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.interop.sldworks~SolidWorks.interop.sldworks.ICurve~GetTessPts.html)
- [CircleParams · merkez/eksen/yarıçap ve metre birimi](https://help.solidworks.com/2021/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ICurve~CircleParams.html)
- [UMaxValue · kenar parametre aralığı](https://help.solidworks.com/2026/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ICurveParamData~UMaxValue.html)
- [Sense · kenar ve eğri yönü](https://help.solidworks.com/2023/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ICurveParamData~Sense.html)
- [ICurve.Evaluate2 · eğri noktası ve türevleri](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.icurve~evaluate2.html)
- [IEdge.GetClosestPointOn · kırpılmış kenara izdüşüm](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.iedge~getclosestpointon.html)
- [IEdge.Evaluate2 · kenar parametresi ve paketlenmiş durum](https://help.solidworks.com/2016/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IEdge~Evaluate2.html)
- [swActivateDocError_e · uyarı ve hata bitleri](https://help.solidworks.com/2026/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swActivateDocError_e.html)

Video erişimi için `cloud-desktop` becerisi de incelendi. Çalışan ortam
`ccarenv_b64_Y2NhcmVudl9kNDFkYmNmZDZmYWM4MTkxOWQ3ZDg2MDlkZTMyYTUwNQ`;
desktop yeteneği enabled/unknown olarak raporlandı, ancak `cua_repl.js` /
tarayıcı kontrol aracı sunulmadı. Bunun yerine kamusal Instagram embed kaynağı
ve yerel video kareleri kullanıldı; masaüstünde video oynatıldığı iddia edilmez.
