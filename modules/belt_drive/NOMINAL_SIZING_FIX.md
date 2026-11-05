# Genel boyutlandırma ve C boşken sonuç üretme düzeltmesi

5 Kasım 2026. Kullanıcının ekranında V kayışı seçili, yüklenen Tosyalı
kataloğunda yalnız triger-senkron kasnakları ve sıfır kayış ürünü vardı.
`search_drives` gerçek SKU eşleştirmesi yaptığı için sıfır sonuç doğruydu;
fakat uygulamada katalogdan bağımsız boyutlandırma yolu eksikti. Bu nedenle
C aralığı seçilmese de kullanıcı hesap sonucu alamıyordu.

## Değişiklik

- Varsayılan **Genel boyutlandırma** katalog/üretici gerektirmeden çalışır.
  **Katalogdan ürün seçimi** mevcut katı SKU kurallarıyla ayrı tutulur.
- V'de profil/kesit görünür girdidir. R40 tercihli nominal çap çiftleri
  ideal hedef devre göre aranır. Güç, tork ve etkin kuvvet hesabında kullanılır;
  üretici tablosu yokken güçten gerekli kesit veya adet uydurulmaz.
- C verilirse kullanılır; aralık verilirse fiziksel olarak uygun kısmının
  ortası seçilir. C tamamen boşsa `D₁+D₂` başlangıç mesafesidir ve bu varsayım
  ekranda açıkça yazılır. Arama çap kapsamı varsayılan 50–1000 mm'dir;
  bir güvenlik/ürün limiti değildir ve kullanıcı tarafından değiştirilebilir.
- V kayışında tam teğet uzunluğu **datum çizgisinde** hesaplanır. Yakın
  R40 boyundan C, mevcut bisection ile yeniden bulunur. C koşuluna uyan
  tercihli boy yoksa teorik gerekli L korunur; fiziksel ilişki bozulmaz.
- Triger-senkron tasarımda bölüm çapı `z×p/π`, boy `N×p` ve mümkünse tam
  N kullanılır. Tam N, katalogda böyle bir ürün bulunduğu anlamına gelmez.
- Genel hesap sonuçları “doğrulanmamış katalog adaylarını gizle” filtresine
  takılmaz. İlk aday seçilir; gerçek teğet yolu, boy ve C görünür.
- Sonuç manuel tasarıma aktarılır, karşılaştırılır ve katalogsuz v3 proje
  olarak kaydedilip yeniden hesaplanarak açılır. Eski v1/v2 değişmedi.
- Sayı gösteriminde `digits=0` iken 1450'nin 145 görünmesine yol açan
  sondaki sıfırları silme hatası da düzeltildi.

## Hesap ve standart ayrımı

Mevcut saf `calculation.py`/`belt_length.py` yeniden yazılmadı. Kullanılan:

```text
i = D₂/D₁ veya z₂/z₁;  n₂ = n₁/i
δ = (D₂−D₁)/2; α = asin(δ/C)
L = 2sqrt(C²−δ²) + π(D₁+D₂)/2 + 2δ·α
C > (D₁+D₂)/2  (ayrık referans çemberleri)
```

R40 mantissaları ISO 3 tercihli sayı yaklaşımıdır. Nominal çap ve Ld
önerisi gerçek üretici stok listesi veya ISO 4184 ürün uygunluğu değildir.
ISO 4183/4184 referans ölçüleri, groove/ürün toleransları ve gerçek güç
kapasitesi bu nominal geometriden otomatik onaylanmaz. V profili minimum
datum çapı ön elemesinde önceki kullanıcı el kitabının basılı s.76,
Çizelge 4 referans değerleri kullanılır; bunlar üretici rating onayı değildir.
İç/dış kayış uzunluğu Li/La ile datum Ld karıştırılmaz.

Tercihli boy seçerken monoton L(C) bağıntısında hedefin hemen alt/üst boyu
sorgulanır; uygun C'de hedefe en yakın seçenek alınır. Böylece boyu sadece
yuvarlayıp eski C'yi koruyan bir sonuç üretilmez. Sabit C ±0 durumunda
tercihli boy sığmazsa tam teorik boy gösterilir.

## Bağımsız doğrulama

- 3 kW, 1450→400 rpm, C yok, A profili, %1 tolerans: **2116 çap çifti**
  tarandı ve **5 geometrik aday** bulundu. İlk örnek: 118/425 mm,
  402.588235294 rpm, teorik gerekli Ld=1982.631287259 mm; tercihli Ld=2000 mm
  için C=552.047203183 mm. Bunlar nominal ölçülerdir, ürün kodu değildir.
- D₁=100, D₂=200, C=400 mm, sabit C ±0: Ld=1277.497074475 mm korunur.
- Aynı referans için ±20 mm ayarda 1250 mm tercihli boy seçilebilir;
  C ters çözülür ve ayrı acos teğet formülüyle kontrol edilir.
- Ekrandaki 1–11 mm aralık, fiziksel olarak mümkün olmadığı için açıklayıcı
  hata verir. C tamamen boşken ise boy ve merkez mesafesi hesaplanır.
- **239 belt_drive testi geçti**: eski matematik/katalog/UI testleri ve
  yeni 26 bağımsız nominal test + 5 GUI testi. Hata/atlanmış yok.
- Dişli, DFM, parametrik mil, sayfa açılışları, paket verileri ve Claude'un
  ağırlık güncellemesini kapsayan **283 ek regresyon kontrolü geçti**;
  hata/atlanmış yok.
- Uygulama açılış denetimi geçti; **18 sayfa**. Python 3.13.5/Linux,
  Qt offscreen. Bu canlı Windows/SolidWorks veya üretici kapasite testi değildir.
- Katalogsuz GUI, 3 kW/1450→400/C boş girdileriyle gerçek widget'larda
  çalıştırıldı; 5 aday, boy/C ve analitik 2D yol ekran görüntüsüyle doğrulandı.

## Kapsam ve çakışma

Yalnız `modules/belt_drive/` değişti. Claude'un mevcut ekranları, katalog
seçimi, kaynak/karantina gösterimi ve eski kayıtları korundu. Bu sırada
main'e gelen ağırlık modülü güncellemesi (PR #23) de tabana alındı; o kodlar
değiştirilmedi. Menü, tema, iş yöneticisi, paketleme ve diğer motorlarda
refactoring yapılmadı. Güçten kesit/adet/ömür onayı, CAD ve canlı SolidWorks
bu düzeltmenin kapsamı değildir.

## Claude arayüz düzeltmeleriyle entegrasyon

PR #24, `c715c80` ile main'e alındıktan sonra Claude'un `bb8c4dd` commit'i
aynı `ui.py` alanlarında çakıştı. `42012509453` numaralı Windows işi,
üçüncü adım olan geçici head/main birleştirmesinde durdu; pytest başlamadığı
için eksik XML/artifact mesajları oluştu. Node sürüm uyarısı bu hatanın
nedeni değildi. Yeşil `merge` işi, başarısız doğrulamayı atlamadı.

Çözüm Codex çalışma alanında iki geçmişi birleştirir. Claude'un alan
hassasiyeti/orijin koordinatları, boş ağırlık reddi, ayrı uyarı sayısı,
dosya/proje katalog seçimi, gizli görünümde animasyonu durdurma, güncel
arama olmadan katalog kaydetmeme ve bekleyen manuel değişikliği kaydetme
düzeltmeleri korunur. Katalogsuz genel hesap, isteğe bağlı C, nominal aday
aktarımı ve v3 projeler de korunur. Ekrana sığmayan tasarımın uyarısı
aktarım/açılış başarı mesajıyla örtülmez.

Birleşik sürümde 250 mevcut kayış testi ve bu iki değişikliğin birlikte
çalışmasını doğrulayan 3 ek GUI testi geçer. 18 sayfalık uygulama açılış
denetimi de geçer. Bunlar Linux/Qt offscreen kontrolleridir; GitHub Windows
doğrulaması ayrıca gereklidir. Claude'un dalı veya çalışma dosyaları
değiştirilmez; CI kuralları gevşetilmez.
