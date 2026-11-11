# DXF/DWG alma ve nesting içe aktarım zorlaması

11 Kasım 2026. SolidWorks DXF/DWG çıktı denetimi ile nesting DXF/DWG
okuyucusu birlikte incelendi. PDF aktarım motoruna dokunulmadı.

## Düzeltilen sorunlar

- DWG onarımı, sıfır handle taşıyan bir delik/CIRCLE kaydını silip parçayı
  deliksiz kabul edebiliyordu. ENTITIES/BLOCKS kesim kayıtları artık silinemez;
  dosya bütünüyle reddedilir. Kurtarma denetiminde kesim değiştiren onarımlar
  da kabul edilmez. Bilinen DICTIONARYVAR muhasebe düzeltmesi korunur.
- Gerçek LibreDWG 0.13.3 çıktısında görülen sıfır handle'lı ENDBLK kaydı
  silinmeden, çakışmayan bir kimlikle düzeltilir. OBJECTS yer tutucuları
  kesim geometrisinden ayrı değerlendirilir; kaynak dosya değiştirilmez.
- Daire değerlendirmesi, nokta sınırına ulaşmadan milyonlarca öğelik numpy
  dizisi ayırabiliyordu. Segment sayısı ayırmadan önce kontrol edilir.
  Elips/spline/polyline değerlendirmesi de 20.000 noktada durur; eğri içinde
  iptal kontrol edilir. NaN/sonsuz parametreler adaptif değerlendirmeden önce
  reddedilir. Toplam kontur nokta sınırı ayrıca korunur.
- Bloklar akış halinde açılır. 1.000 MINSERT tekrarı, 200.000 nesne ve mevcut
  20 iç içe blok sınırı aşılınca işlem açıklamalı hata ile durur.
- DXF katman adları büyük/küçük harfe duyarsızdır. Kapalı/dondurulmuş/dışlanan
  yardımcı katmanlar ve bloktan miras alınan katmanlar bu kurala uyar.
  Aynı kesimin farklı harf biçimiyle mükerrer çıktı denetimini aşması engellenir.
- SolidWorks çıktı denetimine eski POLYLINE, ELLIPSE ve SPLINE için sonlu
  koordinat/parametre kontrolleri eklendi. Sonlu, geçerli çizimler değiştirilmez.
- Başlatılamayan ODA işlemi kullanılabilir LibreDWG yedeğini engellemez.
  İptal ve zaman aşımı yedek işlem başlatmaz; çalışan süreç öldürülüp beklenir.
  Geçersiz DWG başlığı dönüştürücü başlamadan reddedilir.
- DWG dönüşümünden çıkan DXF'in 100 MB sınırı kurtarma dalından önce de
  kontrol edilir; onarımın ham kayıt taraması dosya boyutu sınırını aşamaz.
- Açık uç tanısı bütün uç çiftlerini karşılaştırıyordu. Aynı Öklid uzaklığı
  tanımı korunarak STRtree en yakın komşu sorgusu kullanılır. Kaynak SHA256
  değeri de her parça için yeniden hesaplanmak yerine dosya başına hesaplanır.

## Kabul ölçümleri

- 240 deterministik gerçek DXF dosyası: R12/R2000/R2018, metin/ikili,
  mm/cm/inç, negatif X ölçeği, farklı X/Y ölçeği, döndürme, blok ve delik.
  Bağımsız afin geometri/alan oraklı ve kaynak SHA256 kontrolü geçti.
- Kullanıcının özel çerçeveli DXF'i: **14 parça türü / 56 adet**;
  kaynak dosya baytları değişmedi. Kullanıcı dosyası depoya eklenmedi.
- Ayrı klasörde kaynak sürümünden derlenen gerçek GNU LibreDWG 0.13.3 ile
  **12 DXF → R2000 DWG → GOKWORKS** örneği geçti: mm/cm/inç, blok,
  aynalama, farklı ölçek ve dairesel delik. Alan, şekil, delik ve kaynak
  parmak izi karşılaştırıldı. Basit çerçeveli DWG de **2 tür / 7 adet** verdi.
- Harici LibreDWG DXF→DWG yazıcısının ikili DXF girişi ve kullanıcının bütün
  açıklama/veri tablolarını taşıyan çiziminde üretim kusurları görüldü:
  çıktı oluşmaması veya adet yazılarının kaybolması/bozuk kimlikler.
  Bu denemeler başarılı sayılmadı; eksik çerçeveli çizim sonuç üretmedi.
  GOKWORKS ikili DXF'i doğrudan okuma denemeleri yukarıdaki 240 vakaya dahildir.
- Aynı makinede 2.000 açık uç, üç tekrar medyanı: eski tanı **0,8108 s**,
  yeni tanı **0,0369 s**. Bulunan boşluk iki uygulamada da 1 mm.
  Bu ölçüm bütün aktarımlara ilişkin genel hız garantisi değildir.
- 5.000 bağımsız çizgi / 10.000 açık uç testi, tüm dosyayı reddederek
  gerçek 1 mm boşluğu bildirir. Bozuk geometri kısmi parça üretmez.

İlk geniş tek-süreç Qt denemesi başarısız test ardından kapatma onay
penceresinde takıldı; yığın izi alınıp süreç sonlandırıldı. Bu deneme
başarılı sayılmadı. Temiz denemeler deponun sınırlı süreç çalıştırıcısıyla
tekrarlandı: DXF/DWG, nesting ve CAD dönüştürücü birlikte **1.068 geçti,
8 atlandı, 0 hata, 0 tekrar** (54 süreç). Son eklenen açık-uç vakaları dahil
odak regresyonları ayrıca **106/106** geçti. Kesin Windows sonuçları PR ve
CI raporundadır.

Canlı SolidWorks ve kurulu ODA bu Linux ortamında denenmedi. SolidWorks
COM sınırları kontrollü testlerle, gerçek DWG okuma ise yukarıdaki GNU
dönüştürücüyle sınandı. Windows doğrulaması canlı CAD testi anlamına gelmez.

## Lazer markalama değerlendirmesi

Eklenebilir. Önerilen yapı, kesimden ayrı bir `LASER_MARK` işlem katmanıdır.
Parça kodu/adı veya kullanıcının seçtiği kaynak DXF markalama çizgileri,
parçayla aynı dönüş/öteleme ile taşınmalıdır. Yazı/çizgi gerçek malzeme içinde
kalmalı, deliklere veya kesim sınırına taşmamalıdır. Markalama, yerleşim
çarpışması, net alan, kerf veya kesim delme hesabına katılmamalıdır.

Arayüzde ayrı renk/önizleme ve açık bir işlem seçimi gerekir. DXF çıktısı
ayrı markalama katmanı taşıyabilir; vektör yazı ve kesimden önce markalama
sırası CAM entegrasyonunda ayrıca ele alınmalıdır. Güç/hız/G-code için
tezgâh ve kontrolcü bilgisi gerekir. Bu çalışma markalama olanağını inceledi;
henüz markalama özelliği eklenmedi.
