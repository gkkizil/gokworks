# Bilinen sınırlar ve canlı kabul gereksinimi

## Gerçek CAD doğrulaması

19 Kasım 2026'da gerçek SolidWorks 2025 SP5 (33.5.0, Türkçe) üzerinde önceki
akışın sekiz kabul senaryosundan yedisi geçti. Firma şablonları ve SolidWorks
2026 canlı kabul bekliyor. Yeni delik bilgisi, kesit, detay ve açınım akışları
da canlı kabul bekliyor. Koşullar [canlı kabul kaydında](LIVE_ACCEPTANCE.md).

## Gerçek SolidWorks 2025 SP5'te kaydedilen davranışlar

- Varsayılan `Teknik Resim.DRWDOT` sayfa biçimi içermez (`GetTemplateName` = `*.drt`);
  bu yer tutucu `SetupSheet6`'ya verilirse çağrı False döner. Şablonda biçim yoksa
  kurulumun `<kağıt> - iso.slddrt` dosyası uygulanır ve rapora yazılır. SolidWorks'ün
  sayfa biçimi klasörü ayarı kaldırılmış bir sürümün klasörünü gösterebilir
  (görülen: `SOLIDWORKS 2024\lang\turkish\sheetformat`); bu durumda şablonun kurulum
  kökü ve çalışan revizyonun `SOLIDWORKS <yıl>` klasörü aranır.
- `IExportPdfData.SetSheets(swExportData_ExportAllSheets, …)` her argümanla False döner;
  bütün pafta adları `swExportData_ExportSpecifiedSheets` ile verilir.
- 2015 sonrası SLDDRW OLE bileşik belge değildir; kayıt doğrulaması dosyayı
  SolidWorks'te yeniden açarak yapılır.
- Görünüş oluşurken belge seçeneği delik merkez işaretlerini zaten ekler;
  `AutoInsertCenterMarks2` tekrar çağrılırsa işaretler ikilenir, `GetCenterMarkCount2`
  0 döner. İşaretler görünüş anotasyonları (`swCenterMarkSym`) sayılarak okunur.
- 'Yüklemede montajı yeniden oluştur: her zaman' ayarında tam yeniden oluşturulup
  kaydedilmiş montaj da `swFileLoadWarning_NeedsRegen` ve `NeedsRebuild2 = 1` ile açılır.
  Yalnız modülün salt okunur açtığı belge bellekte yeniden oluşturulur; kullanıcının açık
  belgesi yeniden oluşturulmaz, kirli veya bekleyen kaynak yine reddedilir.
- BOM `GetComponentsCount2` / `GetComponents2` BOM konfigürasyonunda bastırılmış bileşeni
  de sayar; adet bastırılmamış bileşenlerle doğrulanır. Kayıt sonrası BOM tablosu model
  görünüşünde değil pafta girdisinde listelenir.
- Açınım paftaları ölçülendirilir: toplam boy / en ve her büküm çizgisinin taban kenardan
  konumu (referans ölçü). `AutoDimension` açınımda 1 döndürür, tek büküm ölçer ve eni iki kez
  yazar; bu yüzden kenarlar `GetVisibleEntities2` + `ModelToViewTransform` ile, büküm çizgileri
  pafta konumundan `EXTSKETCHSEGMENT` olarak seçilir. Dikdörtgen olmayan dış hatta
  `AutoDimension` yedek olarak kullanılır ve uyarı verilir.
- Tek başına açılan bir SLDDRW, dış referans aramasıyla başka klasördeki aynı adlı modele
  bağlanabilir (fixture adları çakışınca görüldü). Aynı adlı farklı modelleri aynı arama
  yolunda tutmayın.

## Henüz tamamlanmamış özellikler

- Serbest biçimli, açılı veya ofset kesitler, yardımcı görünüş ve patlatılmış
  montaj seçimi. Kesit ve detay kuralları standart yönler ve doğrulanabilen
  parça geometrisiyle sınırlıdır.
- PCD ve genel delik düzeni tanıma, birçok yüzeye bölünmüş veya açılı deliklerin
  otomatik ölçülendirilmesi ve tüm geometriye imalat ölçüsü oluşturma.
  Hole Wizard model verisi bulunamayan deliklerin çapı ölçülebilir.
- Sac açınımı için her gövdenin kayıtlı açınım konfigürasyonu ve standart bir
  görünüme dik sabit yüzü gerekir. Açınım görünüşü kayıtlı konfigürasyondaki
  geometriyi gösterir. Native büküm çizgileri ve büküm notları
  gerçek SolidWorks'te ayrıca kontrol edilmelidir.
- Genel görünüşleri keyfi sayıda sayfaya bölen optimizasyon; şu an bağlı
  izdüşüm grubu birlikte kalır, izometri / açınım / BOM ayrılabilir.
- Büyük BOM tablolarını otomatik bölme ve sonraki sayfaya taşıma.
- Lider–lider kesişimleri, GD&T çerçeveleri, kaynak sembolleri ve şablonun
  çizgi ağının tamamı. Okunabilen liderlerin metin ve tabloları kesmesi denetlenir.
- Named profil kütüphanesi, kesintiden sonra kalıcı kuyruk devamı,
  BOM CSV/XLSX ve tek paket ZIP dışa aktarımı.
- Üzerine yazma modu. Mevcut dosyayı atlama / yeni ad üretme vardır.
- Çok sayfalı resmin DXF paketi. Tek sayfalı DXF seçilebilir; çok sayfa
  SLDDRW ve PDF içinde korunur ve DXF için WARNING üretilir.

## Muhafazakâr davranışlar

Dirty veya rebuild bekleyen kaynak otomatik kaydedilmez / onarılmaz.
Kullanıcı modelini SolidWorks’te hazırlamalıdır. Yeni SolidWorks oturumu
izinsiz başlatılmaz. Virtual / eksik / çözümlenmemiş bileşenler gizlenmez;
BOM tamlığı doğrulanamıyorsa işlem engellenir.

Bağlantı analiz / oluşturma başlatılınca worker içinde kontrol edilir;
sayfa açılışında arka planda ayrı bir COM oturumu oluşturulmaz. İptal
kontrolü native çağrılar arasında yapılır. SolidWorks’ün o anda blokladığı
bir COM çağrısı zorla sonlandırılamaz.

Standart yön puanında kutu alanı ve ölçülmüş yüzeyler kullanılır; gerçek
gizli kenar yoğunluğu hesaplanmış gibi gösterilmez. Şablon üzerindeki
ön tanımlı ek görünüşler sessizce göz ardı edilmez; kayıt sonrası fazladan
görünüş saptanırsa dosya başarılı sayılmaz.

Firmanın DRWDOT / SLDDRT / BOM şablonu, PDM kuralları ve ağ klasörü
davranışı canlı kabul edilmelidir. Başarılı şablon seçimi ISO 128, 129,
5456, 7200, 1101 veya 2768 uygunluğunu tek başına garanti etmez.

Açınım mevcut konfigürasyona bağlı model görünüşüyle oluşturulur. Kaynakta
geçici konfigürasyon açabilen `CreateFlatPatternViewFromModelView3` bu
akımdan çıkarıldı. Konfigürasyon listesi beklenmedik biçimde değişirse
kuyruk durur ve paket yayımlanmaz.

Gövde kimliği, Cut List üyeliği, bastırılmamış FlatPattern ve görünüşün
tek gövde kapsamı birlikte kontrol edilir. Sadece görünüş adının veya
SM-FLAT-PATTERN metninin bulunması destek kanıtı sayılmaz. Yeniden
adlandırılmış Türkçe konfigürasyonlar da özellik durumuyla değerlendirilir.
Kalınlık / malzeme kesin okunamıyorsa ortak model değeri gövdeye atanmaz.
Paftaya yazılmış bir değer işlem sırasında değişirse paket yayımlanmaz.
Gövde kimliği, kalınlığı ve malzemesi ek pafta başlığındadır. Firma anteti
ortak model / drawing property bağlantılarını kullanabilir; farklı malzemeli
gövdelerde ortak antet malzemesi ayrıca kontrol edilmeli veya şablon
uyarlanmalıdır. Bu durum çalışma raporunda WARNING olarak belirtilir.

Sac envanteri bir kaynakta en fazla 256 sac gövdesi ve 128 konfigürasyon
tarar. Cut List otomatik güncellenmez; kaynak hazır olmalıdır. Tanım erişimi
geçici rollback gerektirirse mutlaka kapatılır, eski gövde pointer’ları tekrar
kullanılmaz. Bu davranışın kaynak dirty / rebuild bayrakları üzerindeki
etkisi firma modelleriyle gerçek SolidWorks’te ayrıca kabul edilmelidir.

Girintili BOM, terfi / gizleme ve özel adet birimi kurallarında satır
miktarları basit örnek toplamı gibi onaylanmaz. Balonların tablo bağlantısı
ve numaraları denetlenir; bütün lider yerleşimi ayrıca incelenmelidir.

PASS bir imalat serbest bırakma kararı değildir. Üretim ölçüleri,
datumlar, toleranslar ve büküm bilgileri mühendislik kontrolü gerektirir.
