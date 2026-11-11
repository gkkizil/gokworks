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
  ○ kontrol bekliyor) ve *Takım değişimi*, *Yeniden tutuş* etiketleri. Sonuç renkle
  birlikte simge ve yazıyla da verilir. Kartı sürükleyip bırakmak veya ↑ Yukarı / ↓ Aşağı
  sırayı değiştirir. Kart içindeki **⇄ Yön** büküm yönünü, **↻ 180°** parçanın çevrilmesini
  açıp kapatır (sağ paneldeki alanlarla aynı plan verisi). Oynatırken numara rozeti konumu
  gösterir: dolu vurgu = oynatılan adım, gri = oynatıldı, halka = sırada.
- **Orta · 3B sahne:** sac mavi, üst takım açık gri, alt takım orta gri; üst kiriş ve alt ray
  koyu gri ve **yalnız görseldir** (çarpışma kontrolüne girmez). Sol üstte geçerli adım ·
  hareket fazı · dönüş açısı, sağ altta renk açıklaması. Üst/alt takım, büküm ekseni ve çarpışma noktası sahnede adıyla etiketlidir.
  Görünüm küpü (sağ üst) tıklanabilir.
- **Sağ · Açınım planı:** düz açınımda büküm çizgileri sıra numarasıyla ve adım başına
  ayrı renkle çizilir; bir çizgiye tıklamak o adımı seçer.
- **Sağ · Seçili adım:** iç açı, dönüş, iç R ve etkin boy; **Hedef iç açı** (− değer +, CAD
  düğmesi CAD açısına döndürür) sahneyi, çarpışma kontrolünü ve PDF'i bu açıya göre
  yapar. CAD'den ölçülen büküm bölgesi (açınım boyu, nötr eksen) korunur, yani aynı
  açınım farklı açıya bükülür; geri yaylanma hesabı değildir. Ardından takımlar (kesit resimli
  kartlar ve V kanalı) ve konumlandırma. Segment yerleşimi, takım verisi ve kontrol
  ayrıntıları/kapsamı açılır bölümlerdedir.
- **Alt:** önceki/oynat/sonraki, konum sürgüsü, oynatma hızı, Açınım, Bitmiş form, Sığdır ve
  tek satırlık sonuç. Üst çubuktaki **Video MP4**, kontrol edilmiş hareketi sahnedeki bakış
  açısıyla 1280×720 video olarak kaydeder; kare hızı seçili oynatma hızıdır. Kodlama Qt
  Multimedia ile yapılır (varsa H.264, yoksa MPEG-4); ek program gerekmez. Takım kütüphanesinde bütün kesitler aynı ölçekte çizilir; ölçek çubuğu,
  DEMO/DXF etiketi, favori yıldızı ve seçili kart işareti kartın üzerindedir.

## SolidWorks

**Aktif SolidWorks Parçasını Al**, açık SLDPRT'nin gerçekten aktif konfigürasyonunu
okur; kaynak kaydedilmez. İlk adaptör tek sabit kalınlıklı gövde, düz sabit yüz,
`OneBend`/`SketchBend`/`ToroidalBend` tanımları ve ölçülebilir paralel açınım teğetlerini
destekler. Açık profilli Base-Flange bükümleri ağaçta yalnız Flat-Pattern altında `UiBend`
olarak bulunur (bükülü durumda bastırılmış); bunlar açınım geçici açıldığında okunur.
Bükülü parçadaki her kısmi silindir yüzü eksenine göre gruplanır; her grup açı ve iç/dış
R ile bir bükümle, her büküm de bir grupla eşleşmelidir. Fazla/eksik büküm hatadır,
yalnız yarıçaptan tahmin yapılmaz. Büküm bulunamazsa hata, okunan sac unsurlarını tür ve
bastırma durumuyla listeler. Kararlı
kimlik persistent-reference özetinden üretilir; unsur adını değiştirmek kimliği
değiştirmez. API metre/radyan sınırında mm/derece dönüşümü yapılır.

Flat-Pattern'in `MergeFace` ayarı açıksa okuma sırasında geçici kapatılır;
büküm bandı genişliği gerçek ayrılmış açınım yüzlerinden ölçülür. Unsur sahipliği
yeniden oluşturmada değişmişse merkez çizgisiyle kesişen ve ölçülen R/açı/kalınlık
sınırlarını sağlayan tek bir düz yüz eşleştirilir. Birden fazla aday reddedilir;
K faktöründen varsayılan genişlik üretilmez. Büküm unsurları yeniden oluşturma
sonrası kalıcı referanslarıyla yeniden bulunur.

Geçici `MergeFace` ayarı, Flat-Pattern bastırma durumu, diğer unsur durumları, aktif konfigürasyon
ve seçim listesi başarı, hata ve iptalde geri yüklenip doğrulanır. COM yalnız
işçinin STA oturumunda yaşar. Eksik açı/R, merkez çizgisinden gerçek büküm
bölgesinin ölçülememesi, belirsiz sabit
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

### Genel standart takımlar (piyasa ölçüsü)

Abkant takım **kesitleri için DIN/ISO standardı yoktur**. DIN EN 12622 makine güvenliğini,
DIN ISO 16367 başka pres kalıbı parçalarını kapsar. Piyasada ortak olan ölçüler parametre
olarak kullanılır ve GOKWORKS bunlardan kendi sade kesitini çizer (üretici çizimi değildir):

- Avrupa tipi (Promecam) bağlantı, 13 mm dil; 835 mm bölünmüş set (10+15+20+40+50+100+200+400).
- Üst bıçak: 88° ve 86° R 0,8; 30° keskin R 0,6; 88° kaz boynu; çalışma yüksekliği 95 mm.
- Alt kalıp: 88° tek V, V6…V50 serisi ve V16 30°; omuz R ≈ 0,08 × V.
- V seçimi: V ≈ 8 × t (yumuşak çelik, 6–12 × t aralığı); hava bükümünde iç R ≈ 0,16 × V.

SolidWorks'ten alınan parça bu takımlarla başlar: 88° bıçak ve 8 × t kuralına en yakın V.
Adımda segment girilmemişse istasyon büküm boyundan, setin en az parçasıyla kurulur
(ör. 80 mm → 50+20+10). Genel ara tutucu (13 mm dil yuvası, pahlı gövde, ön sıkma plakası
ve cıvatası) ile kalıp rayı (dil yuvası, yan cıvatalar, taban flanşı) GOKWORKS'ün yaklaşık
profilidir ve istasyonla aynı boyda kurulur. Tutucu ile tuttuğu takım tek rijit montaj sayılır;
kesitleri birbirine giriyorsa adım "Kontrol edilemedi" olur. Sac–tutucu teması her zaman
kontrol edilir. Bu takımlarla
kontrol çalışır ve her adımın notunda "Genel standart ölçülü takım: üretici kesiti değil"
yazar; gerçek tedarikçi kesiti DXF ile eklendiğinde o kullanılmalıdır.

### Kaynak takım kataloğu

Soldaki **Takım kataloğu indir** düğmesi, açık kaynak referans deposundaki yedi
gerçek profili kişisel kütüphaneye indirir: ST3408S, ST3412S, ST1405S, ST1701S,
2067-1, TOP.205.85.R08 ve 1063. Çizgiler ve dairesel yaylar 1:1 mm korunur;
uç / V çalışma referansları kesitte doğrulanır. Dört taraflı 2067-1 tek gövdedir;
V16/V22/V35/V50 seçimi gövdeyi çalışma yönüne çevirir. Kaynaktaki segment
boyları/adetleri örnek settir; fiziksel stok olarak doğrulanmış sayılmaz.
Var olan ve düzenlenmiş kayıtlar korunur, tekrar indirme kopya oluşturmaz.
İndirme/okuma hatasında eski kütüphane değişmez. Katalog eklemek mevcut çözülmüş
planı yeniden hesaplatmaz; atamayı değiştirmek eski kontrolü geçersiz kılar.

WILA BIU-021 / OZU-313 ve Rolleri 04600 / 07500 teknik bilgi kartları da vardır.
Bunlar üreticinin açık ürün verileridir; kesitleri eksikken **DXF bekleniyor**
olarak görünür ve gerçek kesit gibi çizilmez. **Üretici / kaynak sayfası** ilgili
ürünü açar. WILA CAD indirmesi üretici oturumu veya e-posta bağlantısı ister.
DXF'yi aldıktan sonra **Takım kütüphanesi** bölümünden (DXF takım ekle…) ekleyebilirsiniz. Üretici
çizimleri EXE'ye gömülmez; çevrimiçi indirilen profiller kişisel katalogda kalır.

### Aktarım ve hesaplama düzeltmeleri

Kenar flanşlarında OneBend alt unsurunun yalnız iç yüzü listelemesi, dış yüzün
yanlışlıkla eksik büküm sayılmasına yol açıyordu. Dış yüz eşleştirmesi artık
ölçülen eksen, iç/dış R, açı veya sahip unsur bağı üzerinden doğrulanır.
Yuvarlatılmış sac konturu yan yüzleri, iki komşu sac düzlemi ve gerçek kalınlık
ile bükümden ayrılır. Merkez çizgisi tek başınaysa genişlik yalnız unsurla
eşleşen gerçek açınım yüzünden ölçülür. Hatalarda uzun COM referansları yerine
unsur adı ve kısa yüz kimliği gösterilir. Tanınmayan gerçek bükümler atlanmaz.

Katı kesişimi aynı çift için iki kez başlatılmaz. Sabit geometri, yerleşim ve
sonuçlar işlem içinde tekrar kullanılır; sacın kendiyle çarpışması istasyon
dönüşümünden bağımsız parça koordinatlarında kontrol edilir. Adaptif tarama
istasyon kutularını ve aynı çözünürlüğü korur. Geometri/önbellekler işçiye aittir;
SolidWorks COM nesneleri veya canlı UI nesneleri önbelleğe taşınmaz.

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
`standard.py`: genel piyasa standardı takımlar;
`ui.py`, `dialogs.py`, `tool_picker.py`, `viewer.py`, `cards.py`, `flat_plan.py`: Qt ve görsel takım
kütüphanesi; `report.py`: PDF; `video.py`: MP4.

```sh
QT_QPA_PLATFORM=offscreen python -m pytest modules/press_brake/tests -q
python main.py --self-check package-check.json
```

Araştırma ve lisans sınırları: [RESEARCH.md](RESEARCH.md).
