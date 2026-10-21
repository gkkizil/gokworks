# Hızlı Cıvata Tork Hesabı

**Mühendislik Hesapları → Hızlı tork hesabı** menüsünde açılır. Ekran başlığı
**Hızlı Cıvata Tork Hesabı**dır. SolidWorks bağlantısı gerekmez. Mevcut cıvata
dayanım hesabından ayrı, yalnız bir cıvatanın yaklaşık sıkma torkunu hesaplar.

## Kullanım

1. M3–M36 yaygın metrik serisinden çapı seçin: M3, M4, M5, M6, M8, M10, M12,
   M14, M16, M18, M20, M22, M24, M27, M30, M33 veya M36.
2. **Normal diş / İnce diş** ve uygun adımı seçin. Normal adım **Standart**
   olarak gösterilir; ince listesinde ISO 262 seçkisine ait adımlar ayrıca
   işaretlenir. Sunulan her ince kombinasyonun bir stok cıvata ürünü olduğu
   varsayılmaz. Mevcut `bolt.rules` diş tabloları değiştirilmeden kullanılır.
3. **4.8 / 5.8 / 8.8 / 10.9 / 12.9** kalite sınıfını seçin.
4. **Kuru** seçimi K=0,20; **Hafif yağlı** K=0,15 getirir. Bunlar yaklaşık
   başlangıç varsayımlarıdır; kaplama, yağ ve yüzeye göre gerçek K değişir.
   K elle değiştirilebilir; manuel değer ayrıca belirtilir. **Varsayılan K’yı
   kullan** düğmesi koşula ait değeri geri getirir. Koşulun değiştirilmesi K'yı
   yeni koşulun varsayımına döndürür; ardından tekrar elle düzenlenebilir.
5. Hedef ön yük oranı varsayılan **%70**; giriş aralığı **%0–100**dür.
6. Sonuç **Tahmini Sıkma Torku**, N·m; hedef ön yük kN olarak gösterilir.
   **Sonucu kopyala** girdileri, birimleri, dayanım temelini ve varsayımları
   da kopyalar. Girişler kısa otomatik güncelleme aralığında değiştirilmişse
   kopyalama güncel girdilerle yeniden hesaplar; eski sonucu kopyalamaz.

Kritik bağlantılarda üretici şartnamesi esas alınır. Bu ekran sıkma yöntemini,
FEA, yorulma, diş sıyırması veya kapsamlı bağlantı davranışını çözmez.

## Hesap ve birimler

```text
As = π/4 × (d_mm − 0,938194 × P_mm)²              [mm²]
F  = As × akma referansı × (ön yük yüzdesi / 100) [N]
T  = K × F × (d_mm / 1000)                      [N·m]
F_kN = F_N / 1000                               [kN]
```

As, ISO metrik temel diş profilinin çekme gerilme alanı yaklaşımıdır;
ara sonuçlar yuvarlanmaz. Standart tablolarda yuvarlanmış As ile hesaplandığında
küçük farklar beklenir. Örneğin M16 için 156,668 mm² yaklaşık 157 mm² olarak
tabloya yazılır. Ekrandaki alan hesaplanan değerdir.

K, boyutsuz **tork katsayısıdır**; diş sürtünme katsayısı veya sac büküm K
faktörü değildir. Mevcut K/R aracı ve `bolt.rules.PROOF_STRESS` değiştirilmez.

### Canlı bağlantı kesiti

Sonuç kartında cıvata, somun ve farklı tarama yönleriyle iki sıkılan parçanın
boyuna kesiti bulunur. Seçilen nominal `d`, `P`, kalite sınıfı, tahmini `T` ve
hedef ön yük `F` çizimde güncellenir. Çap gövde oranını, adım diş çizgilerinin
aralığını değiştirir. Karşılıklı eksenel oklar cıvatadaki hedef çekme ön yükünü
gösterir; dış servis yükünü göstermez. %0 ön yükte kesit ve sıfır değerleri
korunur, yük/tork okları gösterilmez. Geçersiz girişte eski sonuç kaldırılır.

Çizim şematik ve ölçeksizdir; baş, somun, parça, delik ve sıkma boyu ölçüleri
temsili olup sayısal olarak verilmez. Bağlantı kapasitesi hesaplanmaz. Çizim
mevcut sonucu kullanır; hesap motorunu, pano raporunu veya diğer modülleri
değiştirmez. Açık/koyu tema ve pencere boyutuyla birlikte ölçeklenir.

## ISO 898-1 dayanım temeli

Hesapta çekme dayanımı `Rm` veya deney yükü gerilmesi `Sp` yerine aşağıdaki
akma/uzama sınırı referansları kullanılır. Temel: **ISO 898-1:2013** mekanik
özellik tanımları. Değer ve nominal/minimum ayrımı arayüzde ve pano sonucunda
gösterilir; kalite sınıfı sayıları gelişigüzel çarpılarak bütün tablo üretilmez.

| Sınıf | Çap | Hesap referansı (N/mm²) | Temel |
| --- | --- | ---: | --- |
| 4.8 | Sunulan çaplar | 320 | Nominal Rp0,2 |
| 5.8 | Sunulan çaplar | 400 | Nominal Rp0,2 |
| 8.8 | d ≤ 16 mm | 640 | Minimum ReL |
| 8.8 | d > 16 mm | 660 | Minimum ReL |
| 10.9 | Sunulan çaplar | 940 | Minimum Rp0,2 |
| 12.9 | Sunulan çaplar | 1100 | Minimum Rp0,2 |

4.8/5.8 sınıflarında nominal Rp0,2 değerleri seçilmiştir. Tam boy deneyin
kalıcı uzama sınırı `Rpf` için verilen 340/420 değerleri farklı bir özellik
olduğundan Rp0,2 yerine kullanılmaz. Dolayısıyla bu sınıflarda %70, seçilen
nominal akma referansının %70'idir; bütün sınıflar için minimum ölçülmüş akmanın
%70'i olduğu iddia edilmez. Bu tercih ekranda **nominal Rp0,2** olarak görünür.
10.9/12.9'da nominal 900/1080 yerine minimum 940/1100 kullanılır.

İnce dişte geometri seçilen adıma göre değişir; 8.8'de M16 sınırı adım
değişince ortadan kalkmaz. ISO 898-1'in normatif kapsamı ve ürün şartları
ayrıca kontrol edilmelidir: örneğin M8 altı ince seçenekler burada geometrik
tahmin olarak sunulur. Sonuç bir ürünün ISO uygunluk belgesi değildir.

Standart referansları: [ISO 898-1](https://www.iso.org/obp/ui/#iso:std:iso:898:-1:ed-5:v1:en),
[ISO 261](https://www.iso.org/obp/ui/#iso:std:iso:261:ed-2:v1:en),
[ISO 724](https://www.iso.org/obp/ui/#iso:std:iso:724:ed-2:v1:en).
Standartların tam metni uygulamaya kopyalanmamıştır. Bu geliştirme oturumunda
Bossard, Fastenal, Westfield ve Bolt Depot teknik sayfalarına erişim ağ geçidi
tarafından reddedildi; bu sitelerden doğrulanmış alıntı veya tablo aktarımı
yapıldığı iddia edilmez. İncelenen BAT verisinin 10.9/12.9 için nominal
900/1080 kullanması, yeni modülün minimum değer tablosu yerine aktarılmadı.
Yeni üçüncü taraf kodu veya bağımlılık eklenmedi.

## Doğrulama örneği

M10×1,5 / 8.8 / kuru / K=0,20 / %70:

```text
As = 57,9895969018452 mm²
Akma referansı = 640 N/mm²
F = 25.979,339412 N = 25,979339412 kN
T = 0,20 × 25.979,339412 × 0,010 = 51,958678824 N·m
```

Ekranda **51,96 N·m** ve **25,98 kN** görünür. Hafif yağlı K=0,15 ile ön yük
aynı kalır, tork **38,97 N·m** olur. M10×1,25 ince dişte As yaklaşık 61,195 mm²
olduğu için aynı kalite ve hedef yüzdeyle ön yük/tork artar.

## Kaynak, test ve paketleme

- `modules/bolt_torque/rules.py`: bağımsız hesap, doğrulama, dayanım ve sonuç modeli.
- `modules/bolt_torque/ui.py`: mevcut kartlar/formlar, tema, ayarlar ve tek tuşla pano.
- `modules/bolt_torque/diagram.py`: canlı cıvata–somun kesiti ve yük/tork gösterimi.
- `modules/bolt_torque/tests/test_bolt_torque.py`: referans sonuçlar, bütün sunulan çap/adım/kalite
  kombinasyonları, M16 sınırı, birimler, manuel K, yüzdeler ve geçersiz girdiler.
- `modules/bolt_torque/tests/test_bolt_torque_gui.py`: gerçek Qt girişleri, normal/ince adım,
  ayarların yeniden açılması, kopyalama, hata düzeltme, iki tema ve pencere boyutları.
- Mevcut EXE kontrolü 12 modülü ve yeni tork/ön yük/pano sonuçlarını da kapsar.
  Doğrudan Python importu PyInstaller tarafından izlenir; ek veri dosyası veya
  bağımlılık gerekmez. Kullanıcı talep etmedikçe EXE üretilmez.

```bash
python main.py
python -m pytest modules/bolt_torque/tests/test_bolt_torque.py modules/bolt_torque/tests/test_bolt_torque_gui.py modules/bolt/tests/test_bolt.py
```

Bağımsız kullanım:

```python
from bolt_torque import calculate
result = calculate(metric='M10', grade='8.8', condition='Kuru', preload_percent=70)
print(result.torque_nm, result.preload_kn)
```
