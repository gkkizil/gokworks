# Kaynak araştırması — 4 Kasım 2026

Bu belge uygulanmış hesaplarla araştırma hedeflerini ayırır. İnceleme
kodlamadan önce salt okunur olarak yapıldı. Kaynak uygulama kodu veya
üretici tabloları modüle kopyalanmadı. Bütün formüller kullanıcıdaki görev
sözleşmesinden ve bağımsız analitik geometriden uygulandı.

## Ticari yazılımlar: doğrulama eksikliği

Bu ortamın ağ politikası GitHub kaynaklarına izin veriyor; aşağıdaki
üretici/yardım alan adlarına erişim vermiyor. Bu nedenle ürünlerin güncel
arayüzleri, lisanslı hesap yöntemleri, tabloları ve CAD yetenekleri burada
**bağımsız doğrulanamadı**. Aşağıdaki satırlar ürün özelliklerinin tespit
edilmiş karşılaştırması değildir; sonraki incelemenin açık işleridir.

| Araştırılması istenen ürün | Resmî kaynak alanı | Bu teslimde durum / sonraki kanıt ihtiyacı |
| --- | --- | --- |
| Gates Design Flex Pro | [gates.com](https://www.gates.com/) | NOT_VERIFIED; ürün sürümü, rating/germe yöntemi ve katalog revizyonu gerekli |
| Optibelt CAP | [optibelt.com](https://www.optibelt.com/) | NOT_VERIFIED; kesit/adet seçimi ve düzeltme tabloları gerekli |
| MITCalc V-Belts | [mitcalc.com](https://www.mitcalc.com/) | NOT_VERIFIED; kullanılan standart/üretici tablosu ve geçerlilik sınırları gerekli |
| SOLIDWORKS Belt/Chain Assembly Feature | [help.solidworks.com](https://help.solidworks.com/) | NOT_VERIFIED; seçilen sürümün feature/mate/API davranışı gerekli |
| Inventor V-Belt Component Generator | [help.autodesk.com](https://help.autodesk.com/) | NOT_VERIFIED; datum tanımları, yük/germe ve servis faktörü yöntemi gerekli |
| Inventor Synchronous Belt Generator | [help.autodesk.com](https://help.autodesk.com/) | NOT_VERIFIED; profil/standart uzunluk/kapasite yöntemi gerekli |
| SKF güç aktarım araçları | [skf.com](https://www.skf.com/) | NOT_VERIFIED; ürün serisi, katalog ve germe verileri gerekli |

Giriş iş akışı, profil seçimi, standart ürün, uzunluk/C ters hesabı, güç
kapasitesi, germe, mil/yatak yükleri, servis faktörü, adet, güvenlik, CAD,
simülasyon ve raporlama başlıklarının **üreticiye özgü karşılaştırması açık
iştir**. Güncel ekran görüntüsü veya ürün çalıştırma testi yapılmadı.
Aşama 1'in bağımsız nominal hesapları bu eksik üretici verilerine dayanmaz.
Aşama 3 kapasite veya Aşama 4 imalat profili için bu araştırma yeterli değildir.

## Açık kaynaklar: erişilen içerik ve lisans gözlemleri

Depoların o gün görünen HEAD'i sabitlendi. Aşağıdaki tarih **incelenen
commit'in author tarihidir**; sürüm desteği veya bakım garantisi değildir.
Tam SHA, incelenen dosya URL'leri, dosya boyutu ve SHA-256 değerleri
[research/sources.json](research/sources.json) içindedir. “Lisans tespit
edilmedi” yalnız kök dizin/lisans dosyası incelemesi sonucudur; sınırsız
kullanım izni anlamına gelmez.

| Kaynak | İncelenen HEAD / tarih | Lisans gözlemi | Gerçek içerik ve GOKWORKS uygunluğu |
| --- | --- | --- | --- |
| [WolftheGrey/belt-calc](https://github.com/WolftheGrey/belt-calc) | `4f14fc4` / 20.05.2026 | MIT, LICENSE okundu | Tek HTML/JS uygulaması. README'de sürüklenen kasnaklar, uzunluk kilidi, gergi ve çok kademe; `index.html` içinde yaklaşık açık kayış uzunluğu, sarılma açısı, en yakın boyut ve aşağı yuvarlanan kavrama dişi hesabı incelendi. Burada tam uzunluk ve kesirli kavrama kullanıldı. PySide bileşeni veya güç tablosu adaptörü değildir. |
| [Temukamakh/partforge](https://github.com/Temukamakh/partforge) | `cd995b3` / 21.09.2026 | Kök lisans tespit edilmedi | README, `belt_profiles.py`, `core.py`, `exporters.py` okundu. build123d tabanlı parametrik parça ve STEP/STL/DXF akışı. Diş verilerinin açık kaynak kökenli oluşu üretici doğrulaması değildir. Kod/veri taşınmadı. |
| [looooo/FCGear](https://github.com/looooo/FCGear) | `83ec154` / 15.09.2026 | Kök GPLv3; timinggear başlığında GPLv3-or-later | README, LICENSE ve `freecad/gears/timinggear.py` incelendi. FreeCAD/numpy/pygears kullanan parametrik profil üretimi; bağımsız GOKWORKS motoruna doğrudan uygun bağımlılık değildir. Copyleft kodu kopyalanmadı. |
| [paulius-zubavicius/pulleys-profile-generator](https://github.com/paulius-zubavicius/pulleys-profile-generator) | `0c11aa0` / 02.06.2018 | Kök lisans tespit edilmedi | `readme.md`, `pom.xml` incelendi. Java CLI/JAR; çeşitli senkron profil için DXF R14 polygon, baskıya yönelik diş genişliği ayarı; README nihai parça olmadığını belirtir. Üretici onaylı imalat konturu sayılmadı. JAR çalıştırılmadı. |
| [LukevLuijn/timing_belt_calculator](https://github.com/LukevLuijn/timing_belt_calculator) | `10324f5` / 14.11.2021 | Kök lisans tespit edilmedi | Ana README ve `belt_calc/README.md` okundu. Eğitim/tasarım hesap açıklamaları; doğrulanmış üretici güç kataloğu olarak kullanılmadı. |
| [CadQuery/cadquery](https://github.com/CadQuery/cadquery) | `8178185` / 24.10.2026 | Apache-2.0, LICENSE okundu | README ve lisans incelendi; Python/OCCT B-Rep ve CAD aktarma için uygun olası üst katman. Mevcut OCP yeterli olduğundan yeni bağımlılık eklenmedi. Bu görevde CAD uygulaması çalıştırılmadı. |
| [gumyr/build123d](https://github.com/gumyr/build123d) | `1901d71` / tarih alınamadı | Apache-2.0, LICENSE okundu | README/lisans; Python OCCT B-Rep yaklaşımı, README'de Python 3.11–3.14 desteği. dev HEAD incelendi; sabit sürüm kararlılığı test edilmedi. Yeni bağımlılık yok. |
| [xarial/xcad](https://github.com/xarial/xcad) | `f9feb29` / tarih alınamadı | MIT, LICENSE.md okundu | README/lisans; .NET CAD soyutlama ve uygulama çatısı, kayış hesap motoru değildir. Mevcut C# STA protokolüne doğrudan bağımlılık eklenmedi. |
| [xarial/codestack](https://github.com/xarial/codestack) | `0cde384` / 07.05.2026 | MIT, LICENSE.md okundu | README/lisans ve kök içerik; SolidWorks API/makro referans deposu. Kasnak parametrik feature çağrıları canlı denenmedi. |

Build123d ve xCAD için commit tarihini almak üzere okunan commit yanıtı
araştırma boyut sınırını aştı; tarih uydurulmadı. Kapsam, tabloda belirtilen
dosyalarla sınırlıdır; bu depoların tüm kodlarına veya tüm lisans zincirine
denetim yapıldığı iddia edilmez. Lisansı açık projelerin üçüncü taraf
bağımlılık/veri lisansları da ileride yeniden kullanım öncesi incelenmelidir.

## Hesapların kaynak ve standart kapsamı

Bu motor standart sertifikalı ürün seçimi yapmaz. Uygulanan oran, güç/tork,
hız, teğet ve yay bağıntıları görev tanımındaki ideal modelin bağımsız
uygulamasıdır. Sayısal doğrulama farklı açı formülü, bağımsız yüksek
hassasiyetli sabit referans, vektör/teğet ve moment dengeleriyle yapıldı.
Kütüphane veya üretici programının çıktısı tek başına doğruluk kanıtı sayılmadı.

V kayışı datum sistemi için ISO 4183/4184; senkron kasnak/kayış ailesi için
ISO 5294/5296 ve ISO 13050 ileride kontrol edilecek standart hedefleridir.
Tam metinleri ve geçerli baskıları bu ortamda doğrulanmadı; **bunlara uygun
kasnak profili veya güç kapasitesi uygulandığı iddia edilmez**. Özellikle
üretici GT serileri standart adım/profil varsayımıyla değiştirilmemelidir.

Üretici adaptörü için gerekli asgari kanıt: üretici ve ürün serisi, revizyon,
belge/sayfa, referans çap/uzunluk tanımı, geçerli hız/çap aralığı, nominal
güç tablosu, düzeltme katsayıları, germe yöntemi, veri kullanım izni ve
bağımsız katalog örnekleriyle test. Bunlar olmadan kapasite/ömür onayı kapalıdır.
