# Araştırma ve lisans kararları

9 Kasım 2026 tarihinde GitHub API, kaynak dosyalar ve README'ler doğrudan
incelendi. Aşağıdaki sürümler araştırma anını gösterir; GOKWORKS bağımlılık
sürümleri değiştirilmedi. Bu modülün algoritmaları özgün Python kodudur;
aşağıdaki projelerden kod kopyalanmadı veya yeni motor bağlanmadı.

| Kaynak | İncelenen sürüm / lisans | Bulgular ve karar |
| --- | --- | --- |
| [OpenNest](https://github.com/ajisaacs/OpenNest) | `f62f73533e521bc652b77ba8dfe0399f8397174a`, MIT | `OpenNest.Core/Splitting/DrawingSplitter.cs` ve `AutoSplitCalculator.cs` okundu. `SplitByCount` X/Y sınır kutusu aralıklarını bölüyor; `FitToPlate` kenar/özellik payını kullanılabilir levha ölçüsünden düşerek gereken X/Y kesimlerini üretiyor. DrawingSplitter kırpma bölgelerinde dış/iç konturları ayırıyor, çevrelere göre delikleri yeniden ilişkilendiriyor ve bağlantısız parçaları ayrı çıkarıyor. Radyal sabit-n gereksinimi bunun doğrudan portu değildir; burada bağlantısız dilim reddedilir. |
| [Shapely](https://github.com/shapely/shapely) | `9ab6978eb2153a7781729fb303e0e35b119c1c2c`, BSD-3-Clause; GEOS LGPL-2.1 | Mevcut 2.1.2 Polygon/MultiPolygon, intersection/difference/union_all, buffer, validation ve dönüşüm API'leri kullanıldı. `split` yerine her radyal sektörle kesişim seçildi: delik topolojisi GEOS'ta kalır ve tam n doğrulaması yapılır. Prepared geometriler bu küçük/rutin başına değişen adaylarda ayrı cache yükü getireceği için eklenmedi. |
| [Clipper2](https://github.com/PolyClipping/Clipper2) | `b496b454df168a2280354857c1cd90bd6fa7b4dd`, Boost-1.0 | README'de boolean intersection/union/difference/XOR, poligon offset ve C++17/native DLL yapısı incelendi. Aynı işi mevcut GEOS katmanı yaptığı için ikinci kernel, tamsayı ölçekleme ve native paketleme eklenmedi. |
| [ezdxf](https://github.com/mozman/ezdxf) | `8a593d329ab44b8495e65314dc1b0f9234851f1c`, MIT | Mevcut 1.4.3 entity flattening, native CIRCLE ve kapalı polyline API'leri uygulamada doğrulandı. Tüm kaynak türleri mevcut Nesting okuyucusundan geçer. Kesilmiş eğrilerin analitik yeniden kurulması yerine toleranslı poligon çıktısı ve yeniden okuma testi kullanılır; tam kalan CIRCLE korunur. |
| [SheetNest](https://github.com/YJack0000/sheetnest) | `0b3517f0b1d5ebd0e8c874f1591fc35e3278dc52`, MIT veya Apache-2.0 seçeneği | README'de Rust/Clipper2 tabanlı NFP + GA, geometri/order/rotasyon adayları ve zaman bütçesi incelendi. Ayrı Rust/native motor yerine mevcut GOKWORKS NFP kullanıldı. Dış segmentasyon taraması deterministik açı/yerel aramadır; GA, Beam Search ve Simulated Annealing bu sürümde eklenmedi. |

Lisanslar depo LICENSE/README ve GitHub metadata üzerinden kontrol edildi.
Yeni kaynak kodu alınmadığı için bu projelerden bir dağıtım bileşeni eklenmedi;
mevcut Shapely/GEOS/ezdxf/PySide6 bildirimleri ve paketleme korunur. Bu kayıt
koşulsuz hukuki uygunluk veya üretim onayı anlamına gelmez.
