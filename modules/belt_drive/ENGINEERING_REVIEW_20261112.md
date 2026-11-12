# Kayış–kasnak seçim algoritması: mühendislik incelemesi

**İnceleme tarihi:** 12 Kasım 2026. Amaç, geometrik ön boyutlandırmayı
yük taşıma hesabından ayırmak ve gerçek seçim hatalarını düzeltmektir.

## Standart ve kaynak kontrolü

| Kaynak | Kontrol edilen durum | Hesaba etkisi |
| --- | --- | --- |
| [ISO 4183:2026](https://www.iso.org/standard/88705.html) | Yayımlanmış 4. baskı; 1995 baskısının yerini almış | Klasik/dar V kasnağında datum esaslı kanal ve kasnak boyutları. Dış çap, datum çapının yerine geçirilemez. |
| [ISO 4184:2025](https://www.iso.org/standard/88704.html) | Yayımlanmış 3. baskı | V kayışında datum uzunluğu. R40 sayısından boy üretmek, standart ürün/uzunluk toleransı veya stok uygunluğu kanıtı değildir. |
| [ISO 5295:2023](https://www.iso.org/standard/86235.html) | Senkron kayışta güç ve eksen mesafesi hesabı | Hesabın bazı katsayıları kayış yapısı ve adıma bağlı üretici verisidir; yalnız hatve/diş sayısı güç kapasitesini belirlemez. |
| [ISO 13050:2022](https://www.iso.org/standard/82453.html) | Metrik kavisli G/H/R/S profil sistemleri | Aynı adım tek başına diş profili uyumluluğu sağlamaz. Ticari HTD/GT adı otomatik standart uygunluğu değildir. |
| [ISO 17396:2024](https://www.iso.org/standard/88593.html) | Metrik T ve AT profilleri | T5, AT5 ve kavisli 5M birbirinin yerine seçilmez. |
| [ISO 5292:1995](https://www.iso.org/standard/11293.html) | **8 Nisan 2022'de geri çekilmiş** | Güncel, zorunlu bir güç hesabı standardı gibi gösterilemez. Üretici yöntemi ve geçerlilik sınırları ayrıca gereklidir. |

ISO'nun resmî kapsam, baskı ve durum sayfaları incelendi. Ücretli tam
standartların bütün tabloları/toleransları okunmuş veya uygulanmış sayılmadı;
bu çalışma standart uygunluk belgesi değildir.

[Gates Heavy Duty V-Belt Drive Design Manual](https://www.gates.com/content/dam/documents-library/catalogs/heavy-duty-vbelt-drive-design-manual-en.pdf)
resmî kaynaktan alınıp yerel olarak incelendi. Dosyanın kapağındaki baskı
**14995-A, Eylül 2010**; PDF değişiklik tarihi yeni bir teknik baskı kabul
edilmedi. SHA256:
`d4dd682a006fccfbdceaaed73257141756bc7df9b0e7a7bcf20335e8e0fbca08`.
Kılavuz güncel ürün stok kataloğu olarak eklenmedi.

İncelenen akış: tasarım gücü → kesit → kasnak sınırları ve devir → gerçek
kayış boyu/C → düzeltilmiş kayış kapasitesi → gerekli adet → kurulum/germe.
Gates B6 örneğinin yalnız aritmetiği bağımsız regresyona aktarıldı:
`10 hp × 1,2 / ((7,01 + 0,08) × 1,1)` için gereken adet **2**.
Bu test sentetik geometri üzerinde işlem sırasını sınar; 3VX ürününü mevcut
A profil modeli olarak tanıtmaz ve 3VX imalatı/ürün seçimi onayı vermez.

Eski Optibelt PDF adresi ana sayfaya yönlendi; aramada bulunan Storyblok
dosyası ise 1 sayfalık **Document replacement / Document being revised**
bildirimiydi. Bu dosyadan güç veya servis katsayısı çıkarılmadı.

## Doğrulanan ve düzeltilen seçim hataları

1. **Ticari seri uyumlulukla karıştırılıyordu.** Aynı üretici, profil ve açık
   `compatibility_id` altında farklı kayış/kasnak serileri hiç aranmıyordu.
   Seri adları ayrıldı; profil/uyumluluk/üretici sınırları korunuyor.
   Açık seri filtresi verilirse önceki gibi tüm ürünlere uygulanır.
   Güç tablosu her zaman **kayışın serisinden** alınır. Tekrarlanan ürün
   kodları farklı serilerde farklı aday kimliği taşır; eski tek-seri aday
   kimlikleri korunur.
2. **C hedefi uygunsuzsa tolerans aralığı da eleniyordu.** Örneğin iki 630 mm
   referans çapı, `C=600±100 mm` içinde 630 mm'nin üstünde yerleşebilir.
   3350 mm tercihli boy için bağımsız `C=(L−πD)/2` sonucu yaklaşık
   **685,398 mm**'dir. Motor artık izin verilen fiziksel bölgeyi tarar;
   hedefin ayarlandığını bildirir ve sapmayı asıl hedeften hesaplar.
3. **Teorik triger boyu gerçek diş seçiminin önüne çıkabiliyordu.** Tercihli
   boy politikasında tam diş/tercihli boy bulunan adaylar, yalnız teorik boy
   üreten yedek sonuçlardan önce gelir. Teorik sonuçlar silinmez; tam kayış
   dişi seçilmediği açıkça yazılır. R40 sonucu stok ürünü sayılmaz.
4. **Kapasitesi bilinmeyen aday, yeterli hesaplanmış adayın önüne çıkabiliyordu.**
   Beyan edilen yöntemde yeterli kapasitesi hesaplanan aday önce sıralanır.
   Yetersiz aday elenir; bilinmeyen kapasite sıfır veya yeterli kabul edilmez.
   `PROVISIONAL` sonuçlar üretici doğrulaması olarak yükseltilmez.
5. **Çalışma sınırları seçime aktarılamıyordu.** İsteğe bağlı minimum küçük
   sarılma açısı, maksimum kayış hızı ve minimum geometrik kavrama dişi
   alanları hem katalog hem genel boyutlandırmaya eklendi. Arayüz, proje
   yükleme/kaydetme ve eski isteklerin okunmasıyla birlikte sınandı. Proje
   sınırı ekranın aralığına/hassasiyetine sığmazsa eski sonuç gösterilmez;
   değişen değer açıklanır ve yeniden hesaplama istenir.

Sarılma sınırı, iki kasnağın ortak teğet geometrisinden C sınırına çevrilir:

`βküçük = π − 2 asin(|D₂−D₁|/(2C))`

`Cmin = |D₂−D₁| / (2 cos(βmin/2))`

Geometrik kavrama tahmini `z × β/(2π)` kullanılır. Eşit olmayan çaplarda
180° küçük sarılma sonlu C'de sağlanamaz. Herhangi bir 120°, 6 diş veya
30 m/s değeri evrensel standart sınırı diye gizlice uygulanmaz; ürünün
kapasite/diş kavrama katsayıları bu geometrik filtreden ayrıca gerekir.

## Korunan hesap sözleşmeleri ve açık sınırlar

- `Ptasarım = P × servis faktörü`; eksik faktör otomatik 1 yapılmaz.
- Aynı referans çizgisinde tam teğet-yay boyu ve monoton ters C çözümü
  korunur. V kayışında Li/La, Ld yerine geçmez. Senkronda `Lp=Np` kullanılır.
- Motor devri, küçük kasnak daha hızlı dönen **sürülen** kasnaksa güç
  tablosuna doğrudan verilmez; küçük kasnağın kendi devri kullanılır.
- Güç tablosu, ek güç ve tanımlı düzeltmeler üretici/yöntem kaynağına bağlıdır;
  eksik veya aralık dışı veri ekstrapolasyonla doldurulmaz.
- `Ft=P/v` toplam çevresel kuvvet farkıdır; ön germe veya yatak yükü değildir.
- Genel mod halen **geometrik ön boyutlandırma** yapar. Sadece güç/devirden
  bilinmeyen bir ürünün kesiti, kayış adedi, genişliği veya ömrü uydurulmaz.
  Ekrandaki güç ve tasarım gücü bu sınırla birlikte gösterilir.
- Gerçek motor minimum kasnağı, mil deliği/kama, dış zarf, hizalama, germe,
  sıcaklık ve ömür koşulları ilgili motor/ürün belgesiyle tamamlanmalıdır.

## Doğrulama

Başlangıç: mevcut **254 modül testi** geçti. Ek regresyonlar ticari seri
uyumu, yanlış profil/üreticiyi dışlama, doğru güç tablosu, eski aday kimliği,
C toleransı, kesikli boy önceliği, sarılma/hız/kavrama sınırları, yayınlanmış
aritmetik ve arayüz/proje aktarımını kapsar. Kesin yerel ve Windows sayıları
bu değişikliğin PR doğrulama kaydında tutulur.

Değişiklik sonrası **275 modül testi** geçti. Ayrı, deterministik 150
geometri/çalışma sınırı denemesinde bütün tercihli boylar bağımsız yay-teğet
formülü ve ters çözümle karşılaştırıldı: **59 uygun, 91 elenen, 0 uyuşmazlık**.
Modül ile kompakt pencere/metin kontrolleri ayrıca 33 sınırlı süreçte
**294/294**, son eklenen hassasiyet kontrolleriyle seçim ve arayüz grubu
**62/62** geçti. Bu kümeler örtüşür; sayıları toplanmaz. Yerel hata/atlama/
tekrar yoktur. Son Windows doğrulaması PR'da tutulur.

İlk tam Windows koşusunda kayıştan ayrı bir video testi taze süreçte Qt
uygulaması olmadan yazı çizerken yerel Qt çöküşü üretti. Aynı hata tek
testle Linux'ta da tekrarlandı. Teste açık `qapp` bağımlılığı eklendi;
abkant üretim kodu, test kapsamı ve kapı kuralları değiştirilmedi. Bu ilk
koşu başarılı sayılmadı; son commit yeniden doğrulanır.
