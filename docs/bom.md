# BOM - Ürün ağacı

[Örnek Excel ve arayüz görselleri](reports/bom/README.md) sentetik montaj
verileriyle hazırlanmıştır; kullanıcının gerçek CAD dosyalarını içermez.

Aktif montajın aktif konfigürasyonu `GetRootComponent3(True)` ile alınır.
`GetChildren` her bileşen örneği için ayrı dolaşılır; alt montajın referans
konfigürasyonuna ait çocuklar kullanılır. Başka konfigürasyona geçilmez ve
parça tanımları değiştirilmez. Lightweight bileşenler tarama öncesi çözülür.
Tekrarlanan alt montaj dosyası üzerinden dolaşım tekilleştirilmez; her
fiziksel kullanım adetlere katılır. Aynı dosya + referans konfigürasyonu
toplu parça listesinde birleştirilir. Özgün Türkçe yollar korunur.

Excel **Parça listesi** sayfası ad sırasındadır. **Ürün ağacı** sayfası önce
üst montajı, sonra ada göre sıralanmış çocuklarını içerir. Pozisyon, üst
pozisyon ve seviye alanları ilişkiyi korur; montaj satırları vurgulanır,
çocukları girintili ve Excel satır grupları içindedir. Aynı parçanın her
örneği ağaçta ayrı, toplam listesinde adet olarak gösterilir.

Tarama fiziksel adet sayar. CAD özel BOM Quantity alanı, Hide/Promote alt
bileşen görünümü, parça numarası kaynağı, fiyat, malzeme ve kullanıcıya özel
özellik sütunları bu sürümde uygulanmaz. Tüm alt montaj parçalarını kendi
üst montajı altında gösterme amacıyla gerçek hiyerarşi korunur.

`GetExcludeFromBOM2(swThisConfiguration, null)` aktif konfigürasyondaki
BOM dışı durumunu okur. Metodu sunmayan eski dispatch arayüzlerinde belgeli
`ExcludeFromBOM` özelliği kullanılır. Okunamayan sonuç atlanmaz; tarama hata
verir. BOM dışı bir montaj atlandığında bütün alt dalı da atlanır. Bu sayılar
atlanmış dal köklerini ifade eder, bastırılmış dalların içindeki bilinmeyen
parça sayılarını değil. Gizli parçalar alınır.

Excel isim/yol hücreleri formül olarak yorumlanmaz; adetler sayısaldır.
Çıktı aynı klasörde geçici dosyaya yazılır ve başarıdan sonra hedefe taşınır.
Yazma hatası veya iptal mevcut dosyayı değiştirmez. Excel uygulamasının
kurulu olması gerekmez. Büyük önizlemeler Tk döngüsünde yaklaşık 6 ms'lik
gruplar halinde hazırlanır; tarama ve Excel yazımı ayrı iş parçacığındadır.

## İncelenen GitHub kaynakları

Kaynaklar okunarak karşılaştırıldı; makrolar/kütüphaneler çalıştırılmadı ve
VBA/C# kodu projeye kopyalanmadı. Bağımsız Python uygulaması ve regresyonlar
yazıldı.

- [CodeStack: bileşen ağacı dolaşımı](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/document/assembly/components/traversing-tree/Macro.vba):
  aktif konfigürasyonun kökünden `GetChildren` ile girintili dolaşım.
- [CodeStack: BOM oluşturma](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/document/assembly/compose-flat-bom/Macro.vba):
  bastırılmış/BOM dışı filtreleme, dosya + konfigürasyon anahtarı, adet artırma.
- [CodeStack: adet yazma](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/document/assembly/components/write-quantities/Macro.vba):
  dallar üzerinden dolaşım, BOM dışı seçeneği, Hide/Promote ve özel miktar
  farkları. Bu uygulama CAD özel özelliklerine adet yazmaz.
- [xCAD: montaj bileşenleri](https://github.com/xarial/xcad/blob/f9feb293f74576a6a5dbb3ffcca99502e0a257ed/src/SolidWorks/Documents/SwAssembly.cs)
  ve [alt bileşenler](https://github.com/xarial/xcad/blob/f9feb293f74576a6a5dbb3ffcca99502e0a257ed/src/SolidWorks/Documents/SwComponent.cs):
  aktif/referans konfigürasyonundan kök ve `GetChildren` tabanlı erişim.
- Önceden checksum ile doğrulanmış [2026 API belge aynası](https://github.com/pedropaulovc/offline-solidworks-api-docs/releases/tag/v3.12.1):
  `GetChildren` yalnız doğrudan çocukları verir ve dönüş sırası sabit değildir;
  bastırılmış/gizli/lightweight bileşenleri içerir. `GetExcludeFromBOM2`
  belirtilen konfigürasyon için bool dizisi döndürür. Kaynak ayrıntıları
  [API kayıt dosyasında](reports/k-radius/api-contract.json) bulunur.

## Windows / SolidWorks 2025 kabulü

1. Alt montaj içeren bir test montajını ve doğru ana konfigürasyonu açın.
2. ÖRNEK-M001'i iki kez kullanın; her örnekte aynı parçadan iki tane olsun.
   Toplu listede bu parçanın adedi 4, ağaçta iki ayrı ÖRNEK-M001 dalı olmalı.
3. Bir iç içe alt montaj ve aynı adlı farklı klasördeki parça ekleyin.
   Ağaç ilişkileri ve ayrı dosya satırlarını kontrol edin.
4. Bastırılmış bir dal, gizli bir parça ve BOM dışı bir dal ile iki dahil
   etme seçeneğini karşılaştırın. Farklı referans konfigürasyonlarını sınayın.
5. Excel'e aktarın; ad sırası, toplam adet, alt montajın altındaki satırlar,
   girintiler, grup düğmeleri ve Türkçe yolları kontrol edin.
6. Önizleme araması açıkken Excel'in bütün sonuçları içerdiğini doğrulayın.
   Açık/kilitli Excel dosyasına yazma hatasının mevcut dosyayı koruduğunu
   kontrol edin. CAD konfigürasyonu ve parça parametreleri değişmemeli.

Bulut regresyonları COM davranışını test nesneleriyle, Tk arayüzünü gerçek
sanal ekranla ve `.xlsx` içeriğini gerçek openpyxl okuyucusuyla kontrol eder.
Gerçek SolidWorks 2025 montajı bulutta çalıştırılmamıştır.
