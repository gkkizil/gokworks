# Otomatik Teknik Resim — Mimari

15 Kasım 2026. Tek modül, tek kaynak ağacı ve tek SolidWorks yürütme yolu.

## Uygulamaya entegrasyon

gui_qt/app.py içindeki gecikmeli PAGE_TYPES kataloğu AutoDrawingPage’i
yükler; gui_qt/workspace.py Üretim grubunda gösterir. Paketleme hook’u
aynı katalogdan modülü keşfeder. Ortak JobManager yalnız tek CAD işine
izin verir. Yeni global thread, ayrı CAD oturumu veya ayrı uygulama yoktur.

UI yalnız Source, Options, ModelInfo, Node, DrawingResult ve temel Python
değerlerini taşır. COM nesneleri UI’ya veya EventSink zamanlayıcısına
gönderilmez. SolidWorks bağlantısı uzun bir işin worker thread’inde açılır;
mevcut CAD oturumu kullanılır ve COM initialization / cleanup dengelenir.

## Bileşenler

| Dosya | Sorumluluk |
|---|---|
| models.py | Birimler, veri sözleşmeleri, seçenek denetimi, gerçek aşama listesi |
| solidworks.py | Mevcut raw COM bağlantısı, STA sahipliği, kaynak analizi ve hiyerarşi |
| rules.py | Kanıta dayalı sınıf / yön puanı, benzersiz işler ve BOM örnek adetleri |
| layout.py | Pafta / ölçek seçimi, bağlı izdüşüm yerleşimi, ölçü metni alanları |
| native.py | Gerçek Drawing / View / Dimension nesneleri, kayıt ve tekrar açma |
| manufacturing.py | Native BOM / balonlar ve koşullu açınım paftası |
| sheetmetal.py | Gövde–Cut List–FlatPattern kanıtı, mevcut konfigürasyon ve üretim özelliklerini yeniden denetleme |
| validation.py | Gerçek model bağlantısı, konfigürasyon, pafta / ölçü denetimleri |
| outputs.py | Aynı klasörde geçici paket, üzerine yazmayan yayın, rapor |
| pipeline.py | Sıralı kuyruk, hata izolasyonu, iptal ve aşama raporu |
| ui.py | Tek dosya ağacı, ayarlar, gerçek PDF önizlemesi ve sonuçlar |

Bağlantı, enum okuma ve salt okunur kaynak belgesi yaşam döngüsü mevcut
cad_converter / profile_cutting servislerinden; raw IDispatch yardımcıları
ve mevcut ölçü okuma yordamı tolerance_stack modülünden yeniden kullanılır.
Bu ortak modüllerin davranışı değiştirilmemiştir.

## Belge sahipliği ve kaynak durumu

Kaynak yalnız okunur açılır. Zaten açık belgeler sahiplenilip kapatılmaz.
Önceki konfigürasyon ve seçim listesi hata / iptalde de geri yüklenir.
Kaynak Save3, SaveAll veya SaveAs çağrısı yoktur. Dirty / rebuild bekleyen
kaynak üretimden önce kullanıcıya döndürülür.

Çok gövdeli sac analizi yalnız SheetBody düz kayıtlarını taşır; native
gövde / unsur pointer’ları cache veya UI’ya girmez. GetPersistReference3
bağlantı hataları kayıp kimlik gibi yutulmaz. Gövde kimliği başlığı
AttachAnnotation ile paftaya bağlanır; görünüş ölçeklenince başlık değişmez.
Başlık, tek gövde kapsamı ve üretim özellikleri SLDDRW yeniden açılınca
tekrar denetlenir. Analiz / rapor şeması yeni gövde kanıtları için v2’dir.

IModelDoc2 ve IDrawingDoc dual arayüzleri ayrı işlenir. BOM tablosunun
ITableAnnotation arayüz kimliği çalışan SolidWorks tür kitaplığından alınır.
MakePy veya tahmini enum kimlikleri gerekmez.

Yalnız reddedilen okuma çağrıları, STA mesaj pompasıyla en çok üç kez
denenir. Oluşturma / kayıt çağrısı tekrarlanmaz. Restore veya kopan bağlantı
hatası bütün kuyruğu durdurur; olağan tek dosya hatasında sıradakine geçilir.

## Veri geçerliliği ve performans

Aynı fiziksel dosya ve konfigürasyon için tek resim oluşturulur; örnek
hiyerarşisi BOM adetleri için korunur. Dosya yolu canonical karşılaştırılır,
konfigürasyon adı ayrı kimliktir.

Analiz cache’i yalnız bir oturum boyunca yaşar. Anahtar dosya kimliği,
boyut / değişiklik zamanı, konfigürasyon, GetUpdateStamp, SolidWorks
revision ve analiz şemasıdır. Dirty veya bellek damgası okunamayan kaynak
cache’lenmez. Her dosyanın boyut / mtime / inode bilgisi üretim sonunda
tekrar denetlenir. Normal görünüş üretiminde bellek damgası da karşılaştırılır.
Açınım işlemi konfigürasyon değiştirebildiği için onun damgası aynı kuralın
kanıtı sayılmaz; ayrı konfigürasyon / dosya denetimleri ve WARNING uygulanır.

Yüzeyler / unsurlar analiz başına bir kez taranır; güvenli üst sınır ve
iptal kontrolü vardır. Son yerleşimde yalnız o görünüşün anotasyonları
yeniden okunur. Her ölçüden sonra kayıt yapılmaz.

## Çıktı işlemi

1. Hedef klasör / ad / çakışma politikası doğrulanır.
2. Nihai klasörde özel, geçici adlarla SLDDRW / PDF / rapor hazırlanır.
3. Native geometri ve bağlantılar incelenir; native dosya kapatılıp tekrar
   salt okunur açılır. Bütün kayıtlı sayfa / görünüşler sayılır.
4. Kaynak konfigürasyonu geri alındıktan ve kaynak dosya yeniden
   denetlendikten sonra paket yayımlanır.
5. Mevcut dosya üzerine yazmayan link / Windows rename uygulanır.
   JSON raporu en son yayımlanır. Kısmi yayın hatasında yalnız işlem
   tarafından oluşturulmuş, hâlâ aynı kimlikteki dosyalar geri alınır.

Geçici ve nihai dosyanın ana klasörü aynıdır; model bağlarının göreli
tabanını değiştiren başka klasöre taşıma yapılmaz. PDM ve firmaya özgü
referans davranışı yine canlı kabul testi gerektirir.

## Teslim sınırı

Yerel testler gerçek SolidWorks kurulumu içermez. API sözleşmesi testi,
gerçek CAD belgesi üretiminin veya SolidWorks 2026 uyumluluğunun kabul
kanıtı değildir. Ayrıntılar TEST_REPORT ve KNOWN_LIMITATIONS içindedir.
