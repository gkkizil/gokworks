# K faktörü / yarıçap

Ekranda **Manuel K / R**, **Hesap yardımı** ve **Montaj sonuçları** sekmeleri vardır.

Manuel montaj ataması doğrudan Sac-Levha parametrelerini değiştirir; bu
belgedeki eski hesap/alt büküm eşitleme yolu manuel arayüzde kullanılmaz.
Güncel akış ve sınırlar [manuel atama kılavuzundadır](manual-k-radius.md).
Bu belge malzeme/takım hesabını anlatır. Kalınlık eşleştirerek doğrudan kullanıcı
K/R değerlerini yazmak için [manuel atama kılavuzuna](manual-k-radius.md) bakın.

Bu ekran, SolidWorks'teki aktif montajın aktif konfigürasyonunu alt montajlar
dahil dolaşır. Her dosya + referans konfigürasyonu bir kez işlenir; tekrar eden
parçanın montaj adedi sonuçta gösterilir. Bastırılmış bileşenler işlenmez.

## Kullanım

1. Ana montajı SolidWorks'te aktif yapın. **K faktörü / yarıçap** ekranını açın.
2. Malzeme ailesini seçin: genel düşük karbonlu çelik, paslanmaz veya yumuşak
   alüminyum. Seçim tüm işlenecek saclar için bir hesap varsayımıdır; CAD'deki
   malzeme ataması değişmez. Farklı malzemeli sacları aynı varsayımla işlemeyin.
3. Üst bıçak uç yarıçapını, üst bıçak açısını, alt kalıp V açıklığını ve kalıp
   açısını seçin. Listelerdeki ölçülerin yerine özel değer yazabilirsiniz.
4. **Otomatik (8 × t)** V, katalogdaki uygun açıklığı her parçanın kendi
   kalınlığına göre seçer. Elinizdeki kalıbı kullanacaksanız gerçek V'yi girin.
5. **Montajı tara** ile değişiklik yapmadan K/R önerilerini inceleyin. Sonuç
   satırına çift tıklayarak mevcut ve önerilen değerleri, BA hesabını ve uygunluk
   notlarını görün. Sac olmayan parçalar atlanır; desteklenmeyen parçalar açık
   hata alır. **Uygulamaya hazır**, yalnız tarama sonucudur; K/R yazılmaz.
6. **Montaja K/R uygula**, K ve iç R'yi sac metal unsuruna yazar. Varsayılan
   davranış bellekte değiştirmektir; parçalar otomatik kaydedilmez. Sonuç
   **Uygulandı** olduğunda değerler geri okunarak doğrulanmış olur.
7. **Parça dosyalarını kaydet** işaretlenirse SolidWorks `Save3` kullanılır.
   Önceden kaydedilmemiş değişikliği olan parçanın otomatik kaydı reddedilir.
   İlk gerçek uygulamayı montaj/parça kopyalarıyla kontrol edin.
8. Sonuçları CSV olarak kaydedebilirsiniz. **Durdur**, geçerli parçanın
   doğrulama/geri alma işlemi tamamlandıktan sonra sonraki parçaları durdurur.

## Gömülü takım ölçüleri

### Canlı abkant takım kesiti

**Hesap yardımı** içinde üst bıçak, alt kalıp ve büküm numunesi ayrı kesitlerle
gösterilir. Üst bıçakta **Düz bıçak / Kaz boynu**, alt kalıpta **Tek V kalıp /
Çift V kalıp** seçilebilir. Seçilen aile kesitteki gövde biçimini değiştirir.
Üreticiye ait bir takım kataloğu veya gövde ölçüsü varsayılmaz.

Çizimdeki `Rp` üst bıçak uç yarıçapıdır; `İç R` ise sacın hesaplanan veya
ölçülen iç yarıçapıdır. Bu iki değer ayrı gösterilir. `V`, `αp` (üst bıçak
açısı), `αv` (kalıp açısı), `t` (numune kalınlığı) ve `β` (düz sactan dönülen
büküm açısı) girişlerle birlikte güncellenir. Otomatik V, numunenin kalınlığına
göre seçilen gerçek açıklığı gösterir. Çift V görünümünde girilen değerler
soldaki mavi işaretli aktif ağza aittir; ikinci ağız ölçülendirilmez.

Kesitler şematik ve ölçeksizdir. Takım gövde ölçüleri temsilidir; görünüm,
takımların bir arada temasını, çarpışmayı veya kapasiteyi hesaplamaz.
Geniş pencerede girişler ve çizim yan yanadır. Dar pencerede aynı kontroller
ve çizim tek sütunda, tek kaydırma alanında korunur. BA ölçüm yöntemi
seçildiğinde doğrudan BA ve alternatif A/B/açınım girişleri açılır; yöntem
değişince önceden girilen ölçümler silinmez.

Hesap sonucu ve üretim notları çizimin altında yer alır. Seçimler kaydedilir.
Bu alan bağımsız hesap yardımıdır: manuel K/R satırlarını veya SolidWorks
parçalarını değiştirmez. [Örnek ekranlar](kr-tooling/README.md).

| Özellik | Genel ölçü seçenekleri |
| --- | --- |
| Üst bıçak uç R, mm | 0.5, 0.8, 1, 1.5, 2, 3, 4, 5, 6 |
| Alt kalıp V, mm | 6, 8, 10, 12, 16, 20, 24, 32, 40, 50, 63, 80, 100 |
| Bıçak/kalıp açısı | 30°, 60°, 85°, 88°, 90° |

Bunlar markalı takım model numaraları veya onaylı üretici kapasite kataloğu
değildir; yaygın nominal ölçü seçimleridir. Özel ölçü girilebilir. Program
takım dayanımını, tonajı, minimum flanş boyunu, çarpışmayı veya geri esnemeyi
hesaplamaz. Bu sürüm yalnız **havada büküm** içindir; dip büküm, ezme/coining,
tam katlama ve özel büyük yarıçaplı takımlar bu modelle değerlendirilmez.

Genel uygunluk sınırı `6 ≤ V/t ≤ 12`; otomatik seçim hedefi `8t`'dir. Katalogda
bu sınır içinde seçenek bulunmuyorsa değer uydurulmaz. Bıçak R ve iç R,
`V/2`'den küçük olmalıdır. Hedef iç açı (`180° − büküm açısı`), seçilen bıçak
ve kalıp açısından küçükse işlem reddedilir. Geri esneme için gereken ek
büküm payı bu basit açı kontrolünün kapsamında değildir.

## K ve R algoritması

Programın K tanımı **ANSI: nötr eksenin iç yüzeyden uzaklığı / sac kalınlığı**.
DIN tablosundaki sayılar doğrudan kullanılamaz; o tanımda `K_ANSI = K_DIN / 2`.

Genel havada büküm başlangıç tablosu:

| İç R / t | Yumuşak sınıf | Orta sınıf | Sert sınıf |
| --- | ---: | ---: | ---: |
| 0–1, 1 dahil | 0.33 | 0.38 | 0.40 |
| 1 üzeri–3, 3 dahil | 0.40 | 0.43 | 0.45 |
| 3 üzeri | 0.50 | 0.50 | 0.50 |

Yumuşak alüminyum → yumuşak sınıf; genel düşük karbonlu çelik → orta sınıf;
genel paslanmaz → sert sınıf. Bunlar başlangıç sınıflandırmalarıdır, alaşım,
temper, hadde yönü veya çekme dayanımı sertifikası değildir. Tablo değerleri
arası doğrusal bir eğri uydurulmaz; kaynakta verilen aralıklar kullanılır.

Ölçülmüş iç R yoksa yaklaşık havada büküm modeli:

`R ≈ max(üst bıçak uç R, c × V)`

Genel çelik ve yumuşak alüminyum için `c=0.16`, genel paslanmaz için `c=0.20`.
Bu katsayılar yaklaşık mühendislik başlangıçlarıdır; bu oturumda üretici
kalibrasyon verisiyle teyit edilmemiştir. Bıçak baskınsa sonuçta ayrıca
belirtilir. Üretimde ölçülmüş iç R girildiğinde tahminin yerine o değer geçer.

## Elle bend allowance kontrolü

Açı `θ`, **düz sactan dönülen büküm açısıdır**; parça iç açısı değildir.
Örneğin iç açı 60° ise formüle 120° girilir. `θ_rad = θ_deg × π / 180`.

```text
BA = θ_rad × (R + K × t)
K  = (BA / θ_rad − R) / t
BD = 2 × (R + t) × tan(θ_rad / 2) − BA
```

Tek bükümlü numunede, A ve B dış yüzeylerin sanal kesişimine ölçülen dış
boylarsa ve L deneyden bilinen açınım boyuysa:

```text
BA_ölçüm = L − A − B + 2 × (R + t) × tan(θ_rad / 2)
```

Elle örnek: `t=2 mm`, `R=2 mm`, `θ=90°`, `K=0.4`.

```text
θ_rad = 90 × 3.141592653589793 / 180 = 1.570796326794897
BA = 1.570796326794897 × (2 + 0.4 × 2) = 4.39822971502571 mm
BD = 2 × (2 + 2) × tan(45°) − BA     = 3.60177028497429 mm
```

Numunede A=50 mm, B=40 mm ve L=86.3982297150257 mm ölçülmüşse:

```text
BA = 86.3982297150257 − 50 − 40 + 8 = 4.3982297150257 mm
K  = (4.3982297150257 / 1.570796326794897 − 2) / 2 ≈ 0.4
```

Ekrandaki **K kaynağı → BA ölçümü** ile bağımsız numunenin BA değeri ve gerçek
iç R girilir. BA doğrudan bilinmiyorsa BA alanı boş bırakılıp A, B, L girilir.
Ölçümden çıkan K ile tablo K arasındaki fark gösterilir. Kalibrasyon yalnız
numuneyle aynı kalınlığa uygulanır; aynı malzeme, takım, açı ve işlem koşulları
ayrıca korunmalıdır. Sayısal örnek sentetiktir; fiziksel üretim ölçümü değildir.

**Tablodan BA üretip aynı BA'dan K'yi geri hesaplamak, K'nin üretimde doğru
olduğunu kanıtlamaz.** Bu yalnız formül tutarlılığıdır. Deneysel teyit için BA,
R ve kalınlık ayrı bir gerçek numuneden gelmelidir.

## SolidWorks'e yazma ve hata yönetimi

- Tek gövdeli, tek aktif `SheetMetal` unsurlu parçalar desteklenir. Kalınlık
  SolidWorks'ten metre olarak okunur; hesap mm'de, iç R yazımı metre olarak
  yapılır. Kalınlık ve CAD malzemesi değiştirilmez.
- `GetCustomBendAllowance`, `Type=2` (`swBendAllowanceKFactor`), `KFactor`,
  `SetCustomBendAllowance` kullanılır. R, ana unsura ait tek yarıçap ölçüsü
  bulunursa `SetSystemValue3(..., swSetValue_InThisConfiguration, ...)` ile,
  ölçü bulunmazsa `BendRadius` tanımıyla yazılır. Alt unsura ait ölçüler ve
  çap ölçüleri R hedefi olarak seçilmez. `AccessSelections`,
  `ModifyDefinition`, yeniden oluşturma ve geri okuma kontrol edilir.
- Malzeme veya gauge tablosuna bağlı saclar otomatik değiştirilmez;
  ilgili bağın SolidWorks'te düzenlenmesi gerektiği raporlanır.
  **Tüm bükümlere uygula** açıksa desteklenen özel K/R ayarları ana sac
  değerlerine bağlanır; kapalıysa bu parçalar yazmadan durdurulur.
  Kalınlığı farklı bir alt sacın override'ı kaldırılmaz. Eski sac mimarisinde gauge API hata
  veriyorsa uygunluk doğrulanmış sayılmaz.
  Süpürme flanşının yarıçap mirası `UseDefaultRadius` ile kontrol edilir;
  diğer bükümlerdeki `UseDefaultBendRadius` ile aynı alan değildir.
  Her değiştirilen bükümün varsayılan ayarları geri okumayla doğrulanır.
  Tabloya bağlı özel bükümler ve tanınmayan özel unsur türleri yazmadan
  durdurulur. Büküm boşaltma, açı, uzunluk ve malzeme ayarları değiştirilmez.
- **Katıyı Saca Dönüştür** unsurları `GetTypeName2 = SolidToSheetMetal`
  ile tanınır. Varsayılan sac parametrelerine bağlı, tek gövdeli dönüşümlerde
  ana `SheetMetal` güncellenir; dönüşümün kendi `SheetThickness`, `BendRadius`,
  büküm payı türü, K değeri ve unsur hata durumu da geri okunur. Dönüşüm
  değerleri hedefle eşleşmeden **Uygulandı** sonucu verilmez.
  `OverrideDefaultSheetMetalParameters` veya
  `OverrideDefaultBendAllowanceParameters` açıksa yazmadan önce ilgili unsur
  ve ayar adı bildirilir. Özel ayarlar kendiliğinden kaldırılmaz.
  `OverrideBendRadius`, yalnız unsur oluşturulurken kullanılan gauge ayarıdır;
  mevcut dönüşümün parametre mirasını denetlemek için kullanılmaz.
  **Gövdeyi koru** nedeniyle birden fazla katı gövde kalan parçalar mevcut
  tek gövde sınırına tabidir.
- İşlem öncesi parçanın bütün konfigürasyonlarındaki sac parametreleri,
  desteklenen bükümlerin varsayılan ayarları ve etkin özel K/R değerleri alınır.
  Başka konfigürasyona yayılan değişiklik, yanlış geri okuma veya rebuild
  hatasında eski K/R ve özel büküm ayarları geri yazılır ve tekrar kontrol edilir. Geri alma da
  başarısızsa açık **GERİ ALMA HATASI** gösterilir; otomatik kayıt yapılmaz.
  Değerler geri alınsa bile SolidWorks'ün değiştirilmiş belge işareti kalabilir.
  Dönüşüm unsurları da bu karşılaştırmaya dahildir. Yeniden oluşturma sonrası
  dönüşüm tanımı okunamasa bile ana sacın önceki değerleri geri yüklenmeye
  çalışılır; ardından ana sac ve dönüşüm birlikte tekrar denetlenir.
- Önceki parça konfigürasyonu ve işlem sonunda ana montaj geri etkinleştirilir.
  Bellekte değiştirilmiş yeni açılan parça kaybolmaması için açık bırakılır.
  Yüklü montaj parçaları önce `GetOpenDocument`, ardından
  `GetOpenDocumentByName` ile aranır. `OpenDoc6` uyarı maskesinde 128
  (`AlreadyOpen`) varsa belge mevcut oturuma aittir; yeni açılmış kabul edilip
  kapatılmaz. Diğer uyarı bitleri ayrıca görünür kalır. Belge arama sırası
  [xCAD kaynak koduyla](https://github.com/xarial/xcad/blob/f9feb293f74576a6a5dbb3ffcca99502e0a257ed/src/SolidWorks/Documents/SwDocumentCollection.cs#L340),
  128 değeri [interop metadata kaydıyla](reports/k-radius/api-contract.json)
  karşılaştırıldı; bu karşılaştırma gerçek SolidWorks 2025 çalıştırması değildir.
  Montaj adetleri karşılaştırma anahtarlarıyla sayılır; COM'a dosya yolu ve
  referans konfigürasyonu SolidWorks'ün verdiği özgün haliyle gönderilir.
  Özellikle `İ` harfi küçük harfe çevrilip fiziksel dosya yolu değiştirilmez.
- `Save3` hatası dosya bazında raporlanır. SolidWorks'ün yerel kaydı, eski
  DXF/PDF çıktılarındaki atomik dosya yayımlama garantisiyle eşdeğer değildir.

## Kaynak ve kanıt

- [FreeCAD SheetMetal genel ANSI tablosu](https://github.com/shaise/FreeCAD_SheetMetal/blob/a1cf212d8b86b3849e5cc12070226d5d4bded2a3/tools/README.md)
  sayısal aralıklar için incelendi; bu kaynak da genel bir tablo verir.
- [FreeCAD elle açınım hesabı](https://github.com/shaise/FreeCAD_SheetMetal/blob/a1cf212d8b86b3849e5cc12070226d5d4bded2a3/tools/calc-unfold.py)
  gerçekten çalıştırıldı. `t=2`, `R=1.64`, `K=0.38`, `90°` için her iki uygulama
  da `BA=3.7699111843077517 mm` verdi. [Karşılaştırma kaydı](reports/k-radius/reference-comparison.json).
- [FreeCAD ANSI/DIN dönüşümü](https://github.com/shaise/FreeCAD_SheetMetal/blob/a1cf212d8b86b3849e5cc12070226d5d4bded2a3/SheetMetalNewUnfolder.py)
  tanım farklılığını doğrulamak için incelendi.
- [SolidDNA'nın yayımladığı SolidWorks 2023 interop dosyaları](https://github.com/angelsix/solidworks-api/tree/85a773aedc87b49afda3a65c8bb650f5ba771092/References/2023)
  çalıştırılmadan metadata olarak okundu. Kullanılan arayüz üyeleri, BYREF
  parametreler, gauge hata kodu `0` ve K tipi `2` doğrulandı.
  [API sözleşmesi ve SHA-256 kayıtları](reports/k-radius/api-contract.json).
- Dönüşümün unsur türü ve override davranışı, 2026 API yardımının
  [GitHub'daki bağımsız belge kopyası v3.12.1](https://github.com/pedropaulovc/offline-solidworks-api-docs/releases/tag/v3.12.1)
  üzerinden incelendi. `IConvertSolidFeatureData` üye imzaları ayrıca xCAD
  deposundaki interop dosyasıyla karşılaştırıldı. Kaynak sürümü, dosya özeti
  ve tespitler aynı API sözleşmesi kaydındadır. Bu belge sürümü karşılaştırması,
  SolidWorks 2025 üzerinde gerçek model çalıştırması değildir.

SolidWorks yardım sitesi bu bulut ortamındaki ağ erişiminde 403 verdi;
resmi siteden doğrudan yardım sayfaları okunmuş gibi gösterilmez. Dönüşüm
belgeleri yukarıda belirtilen bağımsız kopyadan okunmuştur. Interop metadata kıyaslaması
gerçek COM çalıştırması değildir. Gerçek SolidWorks geometrisi, hedef sürüm
ve üretim numunesi Windows/atölye ortamında ayrıca kontrol edilmelidir.

[Son test sonuçları](reports/k-radius/README.md) ·
[Arşiv: Açık GUI](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/gui-k-radius-light.png) ·
[Arşiv: Koyu GUI](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/gui-k-radius-dark.png)

## COM okuma/yazma denetimi — 10.10.2026

Sıfır argümanlı üyeler dönen COM nesnesini tekrar çağırmadan okunur. Büküm payı tipi 2 için yalnız K, tip 3 için BA, tip 4 için BD, tip 1/5 için tablo alanı kullanılır. Etkin olmayan alanlar okunmaz/yazılmaz; geri okuma ve geri alma etkin türe göre yapılır. Hata mesajı API üyesini ve işlem aşamasını içerir. [Tekrarlanan HRESULT, testler ve ekranlar](reports/kr-workspace-fix/README.md). Interop kaynak kıyaslaması gerçek SolidWorks 2025 çalıştırmasının yerini tutmaz; [yerel kontrol](local-solidworks-check.md) gereklidir.
