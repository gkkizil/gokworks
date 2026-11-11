# Uygulama genelinde zorlayıcı test ve düzeltmeler

Başlangıç sürümü: `94d98200c77784353f6cf09b9ed11172ae868a0f`.
Testler Linux/Qt offscreen ortamında, gerçek dosyalar ve kontrollü CAD API
sınırlarıyla yürütüldü. Windows doğrulamasının kesin sürüm ve sonuçları PR'dadır.
Canlı SolidWorks, ODA kurulumu veya tezgâh kabulü yapıldığı iddia edilmez.

## Tekrarlanan ve düzeltilen hatalar

| Alan | Tetikleyici ve önceki sonuç | Düzeltme |
| --- | --- | --- |
| Nesting kenarı | 100×100 sac, 60 mm kenar payı: ters sınırlar GEOS tarafından çevrilerek sahte bir orta boşluk oluşturuyordu | İmkânsız kullanılabilir alan açıkça reddedilir |
| Nesting ölçüleri | Sonlu koordinatlardan sonsuz alan/çevre/sac alanı veya toplam kontur payı oluşabiliyordu | Türetilmiş büyüklükler de doğrulanır |
| Akıllı bölme | Çok büyük fakat sonlu bir dairenin çevresinin karesi taşarak sınıflandırmayı çökertiyordu | Boyutsuz dairesellik hesabı taşmayan sırayla yapılır |
| Tolerans yığını | Dar kesilmiş normal bantta büyük sigma, sıfır veya bandın fiziksel sınırını aşan varyans üretiyordu | Merkezlenmiş moment hesabı ve bant içinde kalan örnekleme kullanılır |
| Hidrolik | Küçük mil alanı, iki büyük alanın çıkarılmasında sıfıra yuvarlanıyordu | Mil alanı doğrudan, halka alanı çarpanlarına ayrılarak hesaplanır |
| K faktörü | Geçerli ileri BA hesabından K=0/1'e dönüşte yuvarlama, ölçümü aralık dışında gösterebiliyordu | Önce BA'nın fiziksel sınırları doğrulanır; sonra ters işlem yuvarlaması düzeltilir |
| Abkant hedefi | Pozitif orta yüz yarıçapı, negatif gerçek iç yarıçapı gizleyebiliyordu | Hedef açının gerçek iç yarıçapı doğrulanır |
| Abkant segmenti | Adım üzerindeki segment seçimleri NaN/sonsuz veya negatif boy kabul edebiliyordu | Segment tipi, sonluluk ve pozitif boy doğrulanır |
| Windows adları | `CON .part`, `CONIN$`, `COM¹`, `LPT²` gibi adlar bazı çıktı/yeniden adlandırma yollarından geçebiliyordu | Windows aygıt adı kuralları CAD, DXF ve yeniden adlandırmada uygulanır |
| DXF kontrolü | LWPOLYLINE yüksekliğindeki NaN, XY noktaları geçerliyken denetimden kaçabiliyordu | Yükseklik de sonluluk kontrolüne alınır |
| Profil kayıtları | Boş veya yinelenmiş tarama kimlikleri belirsiz kayıtlar oluşturabiliyordu | Kaydetme/yükleme sınırında kimlikler doğrulanır; eski arayüzün yenileme zorunluluğu korunur |
| Mil projesi | Yeni dosyaya doğrudan yazarken disk hatası yarım proje bırakabiliyordu | Tam, fsync edilmiş geçici dosya özel oluşturmayla yayımlanır; yarışan hedef korunur |
| Arayüz olayları | Hızlı işçinin binlerce sonucunu işlerken GUI olay kuyruğu uzun süre kullanıcı girdisine dönemiyordu | Sıralı olaylar küçük GUI dilimlerinde teslim edilir; iş kilidi son teslimden önce açılmaz |

PDF aktarım motoru ve süreç protokolü değiştirilmedi. PDF sunumunda gizli
tekrarlanan sayaç hesabı kaldırıldı; renk stili yalnız gerçekten değiştiğinde
yenilenir. Tarama/aktarım argümanları korunur.

## Ek zorlayıcı ölçümler

- Tek açık pencerede 22 modül ×15 döngü =330 gezinme; iki tema ve
  820×560/1366×768/1920×1080 boyutları. Yakalanmamış istisna görülmedi;
  widget sayısı ilk döngüde 6.271, son döngüde 6.279 idi. RSS yaklaşık
  267→287 MB; bu sınırlı koşu kalıcı bellek sızıntısı olmadığını kanıtlamaz.
- 3.000 sonuç ve ilerleme olayı: önce 33,39 saniye toplam/32,10 saniye
  en uzun GUI kalp atımı aralığı; sonra 4,90/0,31 saniye. Sonuçların tamamı
  ve 1.000 başarılı/1.000 atlanan/1.000 hatalı sayaçları korundu.
- 120 rastgele nesting projesinde 240 durum; gerçek kontur, boşluk, stok,
  adet/kimlik, kaynak korunması ve iptal bağımsız olarak denetlendi.
  Bazı durumlar bilinçli yetersiz stok veya iptal içerir; tümünün tamamlanmış
  üretim yerleşimi olduğu iddia edilmez.
- 600 rastgele BA/açı/yarıçap fiziksel sınır kontrolü; bağımsız sayısal
  moment ve alan orakılları; disk-dolu ve yarışan kayıt benzetimleri.

Başlangıç tam testi ayrı, değişmez bir checkout'ta çalıştırıldı. Oturum
kesilmesinden önce tamamlanan hedefler korunup kalan hedefler ayrı koşuda
devam ettirildi. Kesilen veya henüz çalışmamış vakalar başarılı sayılmaz.
Yeni hatalar için eklenen regresyonlar ve ilgili mevcut modül testleri ayrıca
çalıştırılır; Windows'un tam raporu son sürümü yeniden doğrular.
