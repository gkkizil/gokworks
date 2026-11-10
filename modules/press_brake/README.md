# Abkant Simülasyonu

GOKWORKS normal girişinde (`python main.py`) **Üretim → Abkant Simülasyonu**.
Mevcut OCP katı çekirdeği, yerel 3B görüntüleyici, Qt işçi yöneticisi ve atomik
PDF yazıcısı kullanılır. Yeni bir Python bağımlılığı yoktur.

## İlk çalıştırma

1. Üstten `DEMO · U / 2 mm`, `DEMO · L / 120°` veya delikli kutuyu seçip
   **Demoyu aç** düğmesine basın. SolidWorks gerekmez.
2. Solda bükümü seçin; ↑/↓ ile sırayı değiştirin. Sağdaki kesit resimli **üst bıçak**
   veya **alt kalıp** düğmesine tıklayın. Videodaki gibi ayrı görsel kütüphane
   açılır: gerçek kesit kartları, kod/üretici/aile araması, favoriler, sütun seçimi,
   büyük kesit ve ölçüler. Kartı seçip **Seçili bıçağı/kalıbı kullan** ile o adıma atayın.
   Çok V'li gövdenin kanalını ve segmentlerini aynı seçimde belirleyebilirsiniz.
   Ana panelde tutuş/yön ve V kanalı ayrıca değiştirilebilir. Segmentler `başlangıç:boy; …` biçiminde
   mm girilir; örneğin `-40:30; 5:35` gerçek bir 15 mm boşluk bırakır.
3. **Hareketi kontrol et**: yaklaşma, büküm ve geri çekilmenin ara katıları
   arka planda incelenir. Oynatma kare/s seçimi kontrol çözünürlüğünü değiştirmez.
4. **Oynat**, ileri/geri adım, konum sürgüsü, **Açınım**, **Bitmiş form** ve
   3B fareyle döndürme/yakınlaştırma kullanılabilir. Çarpışma konumu kırmızı
   işaretlenir; oynatma ilk çarpışan karede durur.
5. **Büküm Föyü PDF** her adımın gerçek 3B katı görüntüsünü, açılarını,
   takımlarını, V kanalını, segmentlerini, ilk çarpışmasını ve kontrol kapsamını
   yazar. Plan değişince önceki sonuç ve PDF komutu geçersiz olur.

Özgün demolar: 2 mm, iç R 2 mm; L parçasında 120° iç açı = 60° dönüş.
U'da iki sıra farklı ara şekiller ve aynı nominal son şekli verir. Kutuda
flanş delikleri, taban deliği ve 1,5 mm köşe rahatlatmaları geometrinin parçasıdır.
`DEMO-WIDE` bıçağı bilinen çarpışma üretir. `DEMO-NARROW` ve demo adımlarındaki
etkin boya uygun segmentler ilgili çarpışmayı kaldırır. Takım/tutucular GOKWORKS
tarafından sıfırdan çizilmiş eğitim geometrisidir; üretici eşdeğeri değildir.

## Ekran düzeni

- **Sol · Büküm sırası:** her adım bir karttır: sıra numarası, büküm, iç açı/R/boy, kontrol
  sonucu (✓ kontrol edilen hareketlerde çarpışma yok · ✕ çarpışma var · ? kontrol edilemedi ·
  ○ kontrol bekliyor) ve *Takım değişimi*, *Yeniden tutuş*, *Çevir 180°* etiketleri. Sonuç renkle
  birlikte simge ve yazıyla da verilir. ↑ Yukarı / ↓ Aşağı sırayı değiştirir.
- **Orta · 3B sahne:** sol üstte geçerli adım · hareket fazı · dönüş açısı, sağ altta renk
  açıklaması. Üst/alt takım, büküm ekseni ve çarpışma noktası sahnede adıyla etiketlidir.
  Görünüm küpü (sağ üst) tıklanabilir.
- **Sağ · Seçili adım:** iç açı, dönüş, iç R ve etkin boy; ardından takımlar (kesit resimli
  kartlar ve V kanalı) ve konumlandırma. Segment yerleşimi, takım verisi ve kontrol
  ayrıntıları/kapsamı açılır bölümlerdedir.
- **Alt:** önceki/oynat/sonraki, konum sürgüsü, oynatma hızı, Açınım, Bitmiş form, Sığdır ve
  tek satırlık sonuç. Takım kütüphanesinde bütün kesitler aynı ölçekte çizilir; ölçek çubuğu,
  DEMO/DXF etiketi, favori yıldızı ve seçili kart işareti kartın üzerindedir.

## SolidWorks

**Aktif SolidWorks Parçasını Al**, açık SLDPRT'nin gerçekten aktif konfigürasyonunu
okur; kaynak kaydedilmez. İlk adaptör tek sabit kalınlıklı gövde, düz sabit yüz,
`OneBend` tanımları ve ölçülebilir paralel açınım teğetlerini destekler. Kararlı
kimlik persistent-reference özetinden üretilir; unsur adını değiştirmek kimliği
değiştirmez. API metre/radyan sınırında mm/derece dönüşümü yapılır.

Geçici Flat-Pattern bastırma durumu, diğer unsur durumları, aktif konfigürasyon
ve seçim listesi başarı, hata ve iptalde geri yüklenip doğrulanır. COM yalnız
işçinin STA oturumunda yaşar. Eksik açı/R, yalnız merkez çizgisi, belirsiz sabit
yüz, eşleşmeyen silindirik büküm, çok gövde, eğrisel veya döngülü topoloji
gerekçesiyle reddedilir; varsayılan büküm üretilmez. Genel STEP tanıma yoktur.
Geçici açınım SolidWorks'ün bellek içi yeniden oluşturma/dirty göstergesini
etkileyebilir; adaptör dosyayı kaydetmez, kullanıcının dosyasını yeniden açıp
değişikliklerini atmaz. Canlı Windows/SolidWorks kabul testi ayrıca gereklidir.

## DXF takım kütüphanesi

**DXF takım ekle…** gerçek 1:1 mm LINE/ARC/CIRCLE ve yaylı polilineleri okur.
Çok kesitte seçim yapılır. DXF birimsizse yalnız bilerek **Birimsiz DXF = mm**
seçin. Açık/dallanan/kesişen kesit, farklı birim, düzlem dışı geometri veya
desteklenmeyen spline/ellipse gerekçeli hata verir. Yazı, ölçülendirme, tarama,
kapalı/gizli/plot dışı yardımcı katmanlar kesite katılmaz. Diğer yardımcı
çizgileri HELPER/AUX/CONSTRUCTION katmanına alıp gizleyin.

Kesit çiziminin X,Y koordinatları istasyondaki Y,Z kesitidir. Takım boyu istasyon
X eksenindedir. Uç, V ve montaj referansları kesitin kendi koordinatlarında girilir.
Çok V, tek gövdede birden fazla `Kod;V;açı;y;z;omuzR` satırıdır. Kanal seçimi
tüm gövdeyi çalışma referansına taşır; rapora da aynı kanal yazılır.

Takım kartında üretici/kod, aile, çalışma yüksekliği, montaj referansı, segmentler,
uç açı/R veya V verileri ve üretici hat yükünün **özgün birimi** tutulur.
Boş hat yükü bilinmiyor kalır; proses iç R'si ile uç R/hedef iç R karıştırılmaz.
Üst ve alt bağlantılar ayrı doğrulanır. Yalnız WILA/Amada/Promecam gibi aile
etiketi yeterli değildir: gerçek takım, tutucu, varsa adaptör arayüz kodları
eşleşmelidir. Tutucu/adapter DXF'si aynı montaj datumunda ve kendi boyuna
yerleşimiyle verilir. Eksik geometri veya bağlantı başarılı kontrol sayılmaz.
Kullanıcı kataloğu işletim sisteminin GOKWORKS uygulama veri klasöründe atomik
`press-brake-tools-v1.json` dosyasıdır; başka projenin kataloğu gömülü değildir.

## Hesap kapsamı

- Flanş ağacı ve ölçülen büküm bölgeleri birlikte taşınır. Dikdörtgen büküm
  bölgeleri analitik dairesel katıdır; deliği/rahatlatması büküm bandını kesen
  bölgeler en fazla 2° kirişli kapalı B-Rep ile korunur. Sabit sac kalınlığı ve
  CAD'den gelen açınım boyuyla nominal hava bükümü yapılır.
- Sac–sac, sac–üst bıçak, sac–alt kalıp, sac–mevcut tutucu ve farklı takım
  bileşenlerinin istemsiz katı çakışmaları incelenir. AABB yalnız aday filtresidir;
  çarpışma OCCT katı ortak hacmiyle doğrulanır. 0,001 mm³ altı ortak hacim sayısal
  eşik içindedir. Uç/omuz temas istisnası yalnız çalışma noktası çevresindeki
  0,3 mm yarıçaplı yerel hacimde ve ilgili fazda geçerlidir. Aktif flanş muaf değildir.
- En fazla 6° aralıklarla tarama, yakın kutularda en fazla 2°'ye sıklaştırılır;
  doğrusal yaklaşma/geri çekilme en fazla 2 mm, yakınlıkta 0,5 mm örneklenir.
  Bu ayrık arama **sürekli süpürme/temassızlık kanıtı değildir**; kalan ara hareket
  belirsizliği kontrol notunda ve PDF'de yer alır. Görüntülenen kareler aynı katılardır.
- Çarpışma / kontrol edilen hareketlerde çarpışma yok / kontrol edilemedi
  ayrıdır. Eksik tutucu, kesit veya bağlantı sonuncusuna yol açar. Tezgâh gövdesi,
  arka dayama, adımlar arası yeniden tutuş/çevirme ve çıkarma rotası kapsam dışıdır.
  Bu hareketler adım verisinde kayıtlıdır; fiziksel kontrol edilmiş gibi sunulmaz.
- Proses kuvveti, yaylanma, CNC strok ve üretim uygunluğu hesaplanmaz. Nominal
  katı kontrolü gerçek tezgâh ve operatör kurulum doğrulamasının yerini almaz.

## Kaynak dosyaları ve doğrulama

`models.py`: değişmez veri sözleşmeleri; `kinematics.py`: ağaç dönüşümleri;
`geometry.py`: gerçek katılar/yerleşim; `tooling.py`: analitik DXF ve katalog;
`motion.py`, `collision.py`, `service.py`: örnekleme/çarpışma/işçi;
`solidworks.py`: STA CAD adaptörü; `demo.py`: özgün veriler;
`ui.py`, `dialogs.py`, `tool_picker.py`, `viewer.py`: Qt ve görsel takım kütüphanesi; `report.py`: PDF.

```sh
QT_QPA_PLATFORM=offscreen python -m pytest modules/press_brake/tests -q
python main.py --self-check package-check.json
```

Araştırma ve lisans sınırları: [RESEARCH.md](RESEARCH.md).
