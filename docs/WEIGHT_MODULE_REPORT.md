# Ağırlık Hesabı Modülü — Geliştirme Raporu

Tarih: 3 Kasım 2026 · Kapsam: `modules/weight` · Referans: [ESN Metal ağırlık hesaplama](https://www.esnmetal.com/agirlik-hesaplama/)

Bu raporda yalnızca çalışan ve otomatik testle doğrulanan özellikler “tamamlandı”
olarak yazılmıştır. Doğrulanamayanlar 7. bölümde ayrıca belirtilmiştir.

## 1. Mevcut modülde tespit edilen eksikler

| Eksik / hata | Etkisi |
| --- | --- |
| HEA, HEB, IPE, UPN… adları yalnızca etiketti; kullanıcı bütün ölçüleri elle giriyor, kök yarıçapı ve flanş eğimi yoktu | Standart profil ağırlığı katalogdan farklı çıkıyordu |
| Standart profil kütüphanesi ve kaynak bilgisi yoktu | Doğrulanabilir kg/m verilemiyordu |
| Kutu profil ve köşebentte köşe yarıçapı yoktu (dünkü ilk ekleme hafızadan bir köşebent r₁ tablosu kullanıyordu) | Kutu profilde ~%3,5 fazla ağırlık; köşebent tablosunun küçük boyları doğrulanmamıştı |
| `1.000` girişi sessizce **1** olarak okunuyordu | Binlik ayırıcı kullanan bir kullanıcı 1000 kat hatalı sonuç alırdı |
| Özel malzeme / yoğunluk girişi yoktu | Listede olmayan malzeme hesaplanamıyordu |
| Hesaplama listesi, birim fiyat, fire, KDV, Excel/PDF raporu yoktu | Satınalma ve üretim için toplu hesap yapılamıyordu |
| Kesit şeması ölçeksiz ve dekoratifti | Çizim hesaplanan geometriyi göstermiyordu |
| SOLIDWORKS model kütlesi okunamıyordu | Delikli/pahlı gerçek parça kütlesi bu modülden alınamıyordu |
| Kesit türleri arasında ölçü alanları ortaktı | Sac için girilen 1000 mm “b”, kutu profile geçince kenar olarak kalıyordu |

## 2. Geliştirilen ve eklenen özellikler (tamamlandı, testli)

- **Hesap motoru GUI’den ayrıldı:** `sections.py` (kesit kayıt sistemi), `catalog.py`
  (standart profiller), `rules.py` (yöntem seçimi, birimler, doğrulama), `worklist.py`
  (liste ve maliyet), `export.py` (CSV/XLSX/PDF), `cad.py` (SOLIDWORKS kütlesi).
- **Doğrulanmış standart profil kütüphanesi:** 175 kesit (`data/sections.json`), üretici
  veri sayfalarından programla çıkarıldı; her satır iki kontrolden geçti (bölüm 4).
- **Kutu profil köşe biçimi:** EN 10219-2 hesap yarıçapları (varsayılan), elle yarıçap, keskin köşe.
- **Köşebent, U, I profilde kök yarıçapı** ve **bükme sac U profil** (iç büküm yarıçapı).
- **Malzeme kütüphanesi:** 39 → 58 kayıt (304L, 430, 1050A, 5005, 5754, 6061, 6063, 6082,
  7075, PA66, PE-HD, 8 saf metal) + kullanıcı tanımlı **Özel malzeme** (ad + yoğunluk).
- **Birimler ve hassasiyet:** mm/cm/m giriş, kg/g/t sonuç, 0–4 ondalık; ara hesapta yuvarlama yok.
- **Sayı girişi:** virgül veya nokta ondalık, `1.234,5` binlikli yazım; belirsiz `1.000` reddedilir.
- **Kesit çizimi:** gerçek oran, köşe/kök yarıçapları, ölçü çizgileri ve okları, otomatik
  ölçek ve ortalama, fare tekerleğiyle yakınlaştırma, sürükleyerek kaydırma, “Sığdır”.
- **Sonuç alanı:** parça ve toplam ağırlık, kg/m, kesit alanı (mm²/cm²), hacim (cm³/m³),
  yoğunluk, adet, yöntem, standart ve kaynak; standart profilde katalog ile geometrik alan farkı.
- **Hesaplama listesi:** ekle, satırda ad/boy/adet/fiyat düzenle, çoğalt, sil, temizle;
  fire % ve KDV % kullanıcıya açık; “yalnız malzeme bedeli” notu; liste kalıcı.
- **Dışa aktarma:** Excel (sayı hücreleri ve sayı biçimi), PDF (seçili hesap, açık renkli
  kesit çizimi, liste, toplamlar; satır bölmeden sayfalama), CSV (`;`, ondalık virgül).
- **Aktif CAD modelinden hesap:** SOLIDWORKS parça/montaj hacmi, malzeme, yoğunluk, kütle;
  formül hesabıyla yüzde farkı; bağlantı yok / malzeme yok / teknik resim açık için Türkçe hata.

## 3. Desteklenen kesit türleri

| Kategori | Türler |
| --- | --- |
| Dolu malzeme | Mil, kare dolu çubuk, lama / dikdörtgen çubuk, altıköşe çubuk (anahtar ağzı), sac levha |
| İçi boş kesit | Boru, kare kutu profil, dikdörtgen kutu profil |
| Açık profil | Eşit kollu köşebent, farklı kollu köşebent, U profil (hadde), bükme U profil (sac), T profil, I profil |
| Standart profil | IPE (+ IPE A, IPE O), HEA, HEB, HEM, HP, HD, UPE, UPN (NPU), eşit ve farklı kollu köşebent (EN 10056-1) |

Yeni bir aile, `sections.py` içinde alanları ve alan fonksiyonuyla tek bir kayıt eklenerek tanımlanır.

## 4. Mühendislik hesap yöntemleri

`A` mm², `L` mm, `ρ` kg/m³: kg/m = A·ρ/10⁶; parça kg = kg/m · L/1000; toplam = parça · adet.

| Kesit | Alan |
| --- | --- |
| Mil | πD²/4 |
| Boru | π(D² − d²)/4, d = D − 2t (sayısal kararlılık için πt(D − t)) |
| Kare / lama / sac | a² · a·b |
| Altıköşe | √3·s²/2 |
| Kutu, keskin | BH − (B−2t)(H−2t) |
| Kutu, yarıçaplı | 2t(B+H−2t) − (4−π)(rₒ² − rᵢ²) |
| Köşebent (EN 10056-1) | t(a+b−t) + (1−π/4)(r₁² − 2r₂²), r₂ = r₁/2 |
| U, paralel başlık | 2b·tf + (h−2tf)·tw + (4−π)/2·r² |
| Bükme U (sac) | t·[(A − 2(r+t)) + 2(B − (r+t))] + 2·π/4·((r+t)² − r²) |
| T | b·tf + (h−tf)·tw |
| I / H (EN 10365) | 2b·tf + (h−2tf)·tw + (4−π)·r² |

**Yöntemler birbirine karıştırılmaz:** *Ölçülerden* (geometrik), *Katalog alanından*
(kullanıcının girdiği cm²), *Standart katalog* (üretici kg/m, çelik 7850 kg/m³; başka
yoğunlukta A×ρ ve bunu söyleyen not), *CAD modeli* (SOLIDWORKS hacmi).

**Standart profil verisinin doğrulanması** (`data/extract_catalogue.py`):

| Aile | Kaynak (üretici veri sayfası) |
| --- | --- |
| IPE, IPE A/O, HEA/HEB/HEM | Stahlwerk Thüringen, EN 10365:2017 (eksik boylar British Steel, 2026-07) |
| HP, HD, UPE | Stahlwerk Thüringen, EN 10365:2017 |
| UPN | Stahlwerk Thüringen (EN 10365:2017) + Kocaer Çelik (DIN 1026-1) |
| Köşebent 120–200, 200×100, 200×150 | British Steel, EN 10056-1 |

Her satır: (1) ölçülerden EN formülüyle hesaplanan alan tablo alanıyla eşleşmeli
(±max(6 mm², %0,4)), (2) alan × 7850 tablodaki kg/m ile eşleşmeli, (3) iki üretici
aynı kesiti veriyorsa ölçüler aynı olmalı. **19 satır reddedildi** (ör. British Steel
IPE 330: tabloda r = 20 mm ve buna göre alan verilmiş, oysa kg/m sütunu r = 18 mm
değerine karşılık geliyor). Üreticiler arasında farklı **8 kesitte** EN 10365 değeri
kullanılır, diğer üreticinin değeri sonuçta not olarak gösterilir.

**Kutu profil yarıçapı:** rₒ = 2t / 2,5t / 3t (t ≤ 6 / ≤ 10 / > 10), rᵢ = rₒ − t. Bu değerler
EN 10219-2 dış köşe tolerans bantlarının (1,6–2,4t; 2,0–3,0t; Tata Steel Hybox veri
sayfası) ortasıdır.

## 5. Test sonuçları ve doğrulama değerleri

Komut: `python -m pytest modules/weight` — **108 test geçti.** Arayüz testleriyle birlikte
(`tests/test_qt_workflows.py`): **274 test geçti.** Bütün proje test paketinin sonucu
commit mesajında verilmiştir.

| Kabul testi | Beklenen | GOKWORKS |
| --- | --- | --- |
| 1 · Dolu mil Ø220 × 200 mm, 7850 | ≈ 59,681 kg | 59,6808 kg |
| 2 · Sac 1000 × 2000 × 2 mm | 31,4 kg | 31,400 kg |
| 3 · Kare 20 × 20 × 1000 mm | 3,14 kg | 3,140 kg |
| 4 · Boru Ø60 × 3 × 1000 mm | ≈ 4,217 kg | 4,2171 kg |

| Katalog karşılaştırması | kg/m |
| --- | --- |
| IPE 200 | 22,4 |
| HEA 200 | 42,3 |
| HEB 300 | 117,0 |
| HEM 200 | 103,0 |
| UPN 200 | 25,3 |
| UPE 200 | 22,8 |
| L 150×150×12 | 27,3 |
| L 200×100×10 | 23,0 |

Diğer testler: her kesit türü için bağımsız el formülü (14 tür), yarıçap terimleri, EN 10219
kutu profil yarıçapları (4 boy), mm/cm/m ve kg/g/t dönüşümleri, adet ve yoğunluk
doğrusallığı, sabit/özel yoğunluk kuralları, 31 geçersiz giriş durumu (sıfır, negatif,
NaN, sonsuz, duvar, sığmayan yarıçap, bilinmeyen tür/profil), taşma, çok küçük değer,
ondalık virgül/nokta/binlik ve belirsiz `1.000`, eski kesit adları, liste toplamları
(fire, KDV, fiyatsız satır), satır düzenleme doğrulaması, CSV/XLSX/PDF içerikleri,
SOLIDWORKS okuması (sahte COM nesneleriyle 7 durum), arayüzde her kesit türünün
hesap ve çizimi, özel malzeme, liste düzenleme ve üç formatta dışa aktarma.

## 6. Değiştirilen ve eklenen kaynak dosyaları

| Dosya | Durum |
| --- | --- |
| `modules/weight/sections.py` | Yeni — kesit kayıt sistemi, alan ve doğrulama |
| `modules/weight/catalog.py` | Yeni — standart profil kütüphanesi |
| `modules/weight/data/sections.json` | Yeni — 175 doğrulanmış kesit, kaynak meta verisi |
| `modules/weight/data/extract_catalogue.py` | Yeni — veri çıkarma ve doğrulama betiği |
| `modules/weight/worklist.py` | Yeni — hesaplama listesi ve maliyet |
| `modules/weight/export.py` | Yeni — CSV / XLSX / PDF |
| `modules/weight/cad.py` | Yeni — SOLIDWORKS model kütlesi |
| `modules/weight/rules.py` | Yeniden yazıldı — yöntemler, birimler, sayı ayrıştırma; eski API korundu |
| `modules/weight/materials.py`, `materials.md` | Genişletildi; tablo koddan üretilir |
| `modules/weight/diagram.py` | Yeniden yazıldı — gerçek oranlı, ölçülü çizim |
| `modules/weight/ui.py` | Yeniden yazıldı — kategori/tür/profil, liste, maliyet, dışa aktarma, CAD |
| `modules/weight/tests/test_weight.py`, `test_worklist_export_cad.py` | Yeni/yeniden yazıldı |
| `tests/test_qt_workflows.py` | Ağırlık arayüz testleri güncellendi ve genişletildi |
| `modules/weight/README.md` | Güncellendi |

Diğer modüllere dokunulmadı. Nesting modülünün kullandığı `MATERIALS` /
`MATERIAL_SOURCES` ve eski kesit adları (ayar dosyaları için) korunur.

## 7. Bilinen sınırlamalar ve tamamlanamayanlar

- **IPN, HL, IPE 80/600/750 ve 120 mm altı köşebentler** kütüphanede yok. Erişilebilir
  doğrulanmış kaynak bulunamadı ya da bulunan tablo kendi içinde tutarsızdı. Bunlar Açık
  profil türleriyle ölçü girilerek (yaklaşık) hesaplanır.
- **Sıcak bitirilmiş kutu profil (EN 10210-2)** için otomatik yarıçap yok; kaynakla teyit
  edilemedi. Elle yarıçap seçeneği kullanılmalıdır.
- **SOLIDWORKS model kütlesi canlı oturumda denenmedi.** Okuma mantığı sahte nesnelerle
  test edildi; gerçek API davranışı ilk kullanımda doğrulanmalıdır.
- **ESN Metal’in hesap formülü görülemedi** (hesap sunucuda yapılıyor). Karşılaştırma
  kategori, alan ve işlev düzeyindedir; sonuç değerleri birebir karşılaştırılmadı.
- Hesaplama listesi bu bilgisayarın ayar dosyasında saklanır; kullanıcılar arasında paylaşılmaz.
- Malzeme yoğunlukları nominaldir; alaşım, ısıl işlem ve ürün biçimine göre farklılık
  gösterebilir. Kaplama (galvaniz vb.), üretim toleransı ve kesim firesi hesaba dahil değildir.
