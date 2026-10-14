# İsimlendirme aracı

SolidWorks dosyalarını yeni adlarla **ayrı bir Pack and Go paketine** aktarır. Montaj, parça, alt montaj, türetilmiş parça ve bulunan teknik resim dosyalarının yolları aynı eşleştirmeyle güncellenir. Kaynak dosyalarda yerinde yeniden adlandırma yapılmaz; mevcut proje ve ona dışarıdan bağlı dosyalar kendi adlarıyla kullanılmaya devam eder. Yeni proje, çıktı klasöründeki montaj/teknik resim üzerinden açılır.

## Kullanım

1. SolidWorks’te ana montajı, parçayı veya teknik resmi açıp değişikliklerini kaydedin.
2. **Aktarım ve montaj → İsimlendirme aracı → Dosyaları oku** seçin.
3. Çıktı için mevcut bir üst klasör ve henüz oluşturulmamış bir **Yeni paket klasörü** adı girin.
4. Ön/son ek, bul–değiştir veya numaralı isimlendirme seçin. Numaralı modda başlangıç ve basamak sayısı ayarlanır. Dosya uzantıları korunur.
5. Eski–yeni adları kontrol edin. Tek bir dosya için satırı seçip **Seçili adı düzenle** kullanın. Aynı klasördeki aynı adlı model/teknik resim çifti, modelin yeni adını paylaşır; bağlantılar ayrıca dosya yolu üzerinden eşlenir.
6. **Paketi oluştur** seçin. Başarıda bütün dosya referansları kontrol edilmiş olur. Paketin içinde `GOKWORKS-isimlendirme.json` eski/yeni yolları ve yeni kök dosyayı gösterir.

Teknik resimler, bastırılmış bileşenler ve Toolbox dosyaları dahil edilir. Teknik resim sayısı önizlemede görünür. SolidWorks Pack and Go'nun bulmadığı, başka klasörlerdeki resimlerin bu pakete otomatik eklendiği iddia edilmez; kaynak proje korunduğu için bu dosyaların mevcut modele olan bağlantıları yerinde kalır. Simülasyon sonuçları bu araçta paketlenmez.

Küçük ekranda ayarlar ayrı kaydırılır; önizleme tablosu ve paket düğmesi yerini korur. Açık/koyu tema, %125 ölçek, sayfa önbelleği ve kuralların kaydedilmesi desteklenir. Katı isim çakışmalarında tablo silinmez: dosyalar elle düzeltilebilir, aktarım adlar benzersiz olana kadar kapalıdır.

## Referans koruma

- Windows ad kuralları, dosya yolu uzunluğu, uzantılar ve büyük/küçük harften bağımsız ad çakışmaları doğrulanır.
- Kaydedilmemiş değişiklik, eksik kaynak, paket dışında kalan referans veya sanal/bilinmeyen Pack and Go belgesi aktarımı engeller. Sanal parçaların adları bu API ile değiştirilemediğinden önce dış dosyaya kaydedilmesi gerekir.
- Önizlemeden sonra aktif belge, kaynak boyutu/tarihi veya referans listesi değişirse yeniden okuma gerekir.
- `SetDocumentSaveToNames` dizisi, Pack and Go'nun **kendi belge sırasıyla** verilir. Önizlemedeki numaralandırma sırası bu API sırasını değiştirmez. Adlar geri okunup planla karşılaştırılır. `SetSaveToName` için `Override=False` kullanılır; `True` özel dosya eşleştirmesini geçersiz kılabilir.
- Kaydetme her dosya için başarı kodu dönmelidir. Dosyaların varlığı/boyutu ve `GetDocumentDependencies2` ile diskte kayıtlı referansları denetlenir. Montaj ve resim referanslarının beklenen yeni dosyalara tam olarak eşleşmesi gerekir. Arama klasörleri veya kullanıcı konfigürasyonları değiştirilmez.
- Çıktı en baştan **nihai klasörüne** yazılır. Bir geçici klasörü sonradan taşımak, dosyalara yazılmış mutlak referansları bozabileceğinden böyle bir taşıma yapılmaz.
- Hata/iptalde sadece bu işlem için planlanan yeni çıktı dosyaları temizlenir; mevcut paket ve kaynakların üzerine yazılmaz. İşletim sistemi silmeyi engellerse yarım dosyalar kalabilir; hata verilen paket başarılı çıktı olarak kullanılmamalıdır. Pack and Go'nun tek COM çağrısı çalışırken iptal, çağrı tamamlandıktan sonra uygulanır.

Bu kontrol kayıtlı **dosya yolu referanslarını** doğrular. Canlı SolidWorks ortamında mate çözümü, rebuild sonucu ve teknik resim görünüşleri bu bulutta doğrulanmadı. Pack and Go, modelin iç unsur/konfigürasyon bilgilerini taşır; araç bu adları veya geometriyi ayrı ayrı düzenlemez.

## İncelenen kaynaklar ve kontroller

[AngelSix / SolidDna PackAndGo](https://github.com/angelsix/solidworks-api/blob/85a773aedc87b49afda3a65c8bb650f5ba771092/SolidDna/AngelSix.SolidDna/SolidWorks/Models/Model.cs#L271): Pack and Go oluşturma, teknik resimleri dahil etme ve her dosyanın durum kodunu kontrol etme akışı referans alındı. Bizde tek ön ek yerine dosya başına ad eşleştirmesi ve çıktı referans doğrulaması kullanılır.

[xCAD kaydetme işlemi](https://github.com/xarial/xcad/blob/f9feb293f74576a6a5dbb3ffcca99502e0a257ed/src/SolidWorks/Documents/SwSaveOperation.cs): Save As hata ve referans gereksinimleri incelendi. Araç, dosyaları tek tek Save As veya dosya sistemi yeniden adlandırmasıyla taşımaz.

[API imza kaydı](examples/api-contract.json), [çevrimdışı SolidWorks dokümantasyon aynasından](https://github.com/pedropaulovc/offline-solidworks-api-docs/tree/b586c9f0c993ae7791e1b8aea79dab2a341a0147) doğrulandı. Kaynak kodu bu projelerden kopyalanmadı; GOKWORKS için bağımsız Python/Tk uygulaması yazıldı.

**20 ilgili kontrol geçti:** referans grafiği, türetilmiş parça ve resim yolları, ad kuralları, model/resim eşleştirmesi, çıktı çakışmaları, kaynak değişimi, kayıt/iptal/hata temizliği, pywin32 dizi ve byref dönüşleri, COM yaşam döngüsü, gerçek Tk tarama/önizleme/elle düzeltme/kaydetme, tema/DPI/küçük ekran, ön yükleme ve hızlı menü geçişleri. İlk kontrollerde bulunan Linux mutlak yol ayrımı ve küçük ekrandaki yerleşim sorunları giderildi; ilgili kontroller tekrar geçti. Tüm test paketi çalıştırılmadı. [Kontrol kaydı](examples/checks.json).

[Açık tema](examples/naming-light.png) · [Koyu tema](examples/naming-dark.png). Ekranlar örnek dosya bilgileriyle çalışan Tk uygulamasından alındı. Testlerde SolidWorks sınırı test nesneleriyle temsil edildi; gerçek `.sldasm/.sldprt/.slddrw` dosyaları üzerinde native Windows kabul testi henüz yapılmadı.
