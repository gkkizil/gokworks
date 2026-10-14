# BOM parça ağırlıkları

BOM taraması, montajda kullanılan her parça örneğinin SolidWorks ağırlığını kg olarak okur. Parça listesinde **Birim (kg)** ve **Toplam (kg)**, ürün ağacında **Ağırlık (kg)** görünür. Excel'in parça listesine **Birim ağırlık (kg)**, **Toplam ağırlık (kg)** ve **Ağırlık durumu** sütunları; ürün ağacına **Ağırlık (kg)** ve **Ağırlık durumu** eklendi. Ağırlıklar hesaplamalarda kullanılabilen Excel sayılarıdır; gösterim altı ondalık basamak kullanır, değerler önceden yuvarlanmaz.

## Okuma ve toplam

- Ana montajın `Extension.CreateMassProperty2()` hesabı, `SelectedItems` ile tek bir parça örneğine sınırlandırılır. Seçim geri okunarak doğrulanır. COM bileşenleri pywin32'ye `VT_ARRAY | VT_DISPATCH` ile verilir.
- `UseSystemUnits=True` kg sağlar. `IncludeHiddenBodiesOrComponents=True` gizli parçaların/gövdelerin hesaba katılmasını sağlar. `Recalculate()` başarılı olmadan ağırlık kabul edilmez. SolidWorks'teki malzeme/yoğunluk ve ağırlık ayarları esas alınır.
- Parçanın açık belge konfigürasyonu üzerinden hesap yapılmaz. Kullanıcının seçimi, aktif belge/konfigürasyonu, özellikleri ve dosyaları değiştirilmez; dosya açma/kaydetme gerekmez.
- Hesaplayıcı yeniden kullanılır; dosya+konfigürasyona göre ağırlık önbelleği oluşturulmaz. Montaj kesileri gibi nedenlerle aynı parçanın örnekleri farklı ağırlıklara sahip olabilir. Bu durumda birim sütunu **Değişken**, toplam sütunu gerçek örnek ağırlıklarının toplamıdır.
- Alt montaj ağırlıkları, BOM'a alınan alt parçaların toplamıdır. Bastırılmış parçalar hariçtir; BOM dışındaki parçalar mevcut dahil etme seçimine uyar. Bu değer, alt montajın bağımsız belgesindeki tüm bileşenlerin veya alt montaja uygulanmış ayrı bir toplam ağırlık override'ının karşılığı değildir. Excel'de açıklaması bulunur.
- Genel BOM toplamı yalnız parça örneklerinden hesaplanır; alt montaj satırları ikinci kez eklenmez.

Okunamayan, negatif veya sonlu olmayan değerler **Okunamadı** olarak gösterilir. Parça ve adetler kaybolmaz; Excel aktarımı kullanılabilir. Bir grubun herhangi bir örneği okunamazsa grup toplamı, bir parça bile okunamazsa genel BOM toplamı eksik olarak işaretlenir. Sıfır ağırlık, API geçerli olarak döndürdüğünde kabul edilir. Hata ayrıntısı Excel'in ağırlık durumu sütununda yer alır. Canlı ağırlık API'si erişilemiyorsa kayıtlı/eski ağırlık değerleri üzerinden tahmin yapılmaz.

## Kaynak ve kontrol

Üye imzaları ve davranışları [API kaynak kaydında](api-contract.json) bulunur. Resmi yardım sitesine bulut isteği HTTP 403 ile engellendi; bilgiler [çevrimdışı dokümantasyon aynasındaki](https://github.com/pedropaulovc/offline-solidworks-api-docs/tree/b586c9f0c993ae7791e1b8aea79dab2a341a0147) XML üye belgelerinden doğrulandı. [CodeStack örneği](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/document/assembly/components/get-cog/MacroMassPrp.vba) montaj bağlamındaki ağırlık hesaplarının araştırılmasında incelendi; uygulama bu eski `AddBodies` yolunu kullanmaz.

27 ilgili kontrol geçti: BOM sayımı ve hiyerarşisi, örnek/konfigürasyon ağırlıkları, COM dizi tipi, gizli ve BOM dışı bileşenler, değişken ağırlıklar, eksik bilgi, sayısal Excel hücreleri, çift sayım, tarama/Excel iptali, mevcut dosyanın korunması, gerçek Tk önizleme/ayrıntılar/aktarım, tema ve küçük pencere/ölçek. İlk GUI çalışmasında kapalı sanal ekran yeniden başlatıldı; yeni sütunlar nedeniyle ortaya çıkan Excel iptal gecikmesi hücre başına durdurma kontrolüyle giderildi. İlgili kontroller tekrar geçti. Tüm test paketi çalıştırılmadı.

SolidWorks sınırı test nesneleriyle doğrulandı; canlı Windows/SolidWorks oturumu bu ortamda çalıştırılmadı. Yerel kontrol için aynı parçanın iki farklı konfigürasyonunu ve tekrarlanan bir alt montajı tarayın; parça ağırlıklarını SolidWorks'ün **Kütlesel Özellikler** değerleriyle, Excel toplamlarını adetlerle karşılaştırın. Yoğunluk/malzeme tanımı doğru olmalıdır.

## Örnek çıktı

[Örnek Excel](ornek-agirlikli-bom.xlsx): **8 cıvata × 0,025 kg**, **2 levha × 2,25 kg** ve **1 destek kolu × 0,875 kg**; iki ÖRNEK-M001 alt montajı, genel toplam **5,575 kg**. Bu veriler gösterim için hazırlanmıştır; gerçek SolidWorks ölçümü değildir.

[Açık tema](bom-weights-light.png) · [Koyu tema](bom-weights-dark.png)
