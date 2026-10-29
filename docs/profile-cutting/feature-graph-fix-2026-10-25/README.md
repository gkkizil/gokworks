# Weldments okuma düzeltmesi · 25 Ekim 2026

Kullanıcının hata ayrıntısı: `FeatureManager ağacında yinelenen/döngüsel unsur bulundu.`
Arayüzde kaynak ve `Default<As Machined>` konfigürasyonu okunuyor, fakat sonuç
`0 profil · 1 taranamayan` olarak dönüyordu.

## Düzeltilen iki neden

1. **FeatureManager grafiğinin tekil bir ağaç kabul edilmesi.** Önceki tarama,
   aynı kalıcı kimliği kardeş zincirde tekrar görünce bütün parçayı reddediyordu.
   SolidWorks aynı unsuru üst listede ve alt unsur bağlantılarında gösterebilir;
   bazı klasör kimlikleri de farklı adlı unsurlar için aynı olabilir.
   Tarayıcı artık `GetNextFeature` ve `GetNextSubFeature` yollarını ayrı ziyaret
   durumlarıyla takip eder. Kimlikte ad, tür ve mevcut kalıcı referans birlikte
   kullanılır. Aynı Cut List yalnız bir kez okunur; tekrar eden bir bağlantı
   sonsuz döngü oluşturmadan sonlandırılır. Python özyinelemesi kaldırıldı;
   iptal kontrolü ve 20.000 ziyaret durumu güvenlik sınırı vardır.
2. **`NeedsRebuild2` dönüşünün Boolean sanılması.** Gerçek
   `IModelDocExtension.get_NeedsRebuild2` imzası `200008`: dönüş tipi `Int32`.
   `swModelRebuildStatus_FullyRebuilt = 0`, diğer iki bekleyen rebuild durumu
   `1` ve `2`'dir. Eski `is False` karşılaştırması gerçek `0` dönüşünü güncel
   kabul etmiyordu. Yeni kontrol kurulu SolidWorks'ün enum değerlerini kullanır.
   Bilinmeyen/okunamayan durum hâlâ otomatik aktarımı engeller; parçanın ve
   montajın güncellik denetiminde aynı yorumlama uygulanır.

Hata mesajı artık tarama ekranında asıl nedeni içerir. Boş Cut List başarı
olarak bildirilmez; **Tarama ayrıntıları** Python sözlüğü yerine kaynak,
konfigürasyon ve okunabilir açıklama gösterir.

Geometri, ölçü, property veya dosya kaydetme algoritmaları değiştirilmedi.
Mevcut gövde kimliği denetimi, montaj örnek adetleri, konfigürasyonun geri
getirilmesi, gönye/özel geometri incelemesi ve güncellik korumaları durur.
Cut List güncelleme seçimi kapalıysa kaynak güncellenmez; açık olduğunda
alt unsurlar güncellemeden sonra okunur. Otomatik güncelleme tercihi değiştirilmez.

## Kanıt ve testler

- İlk yeni graf testleri eski kodda **6 başarısız / 4 başarılı**:
  [kayıt](before-graph.txt). Üst/alt kardeş tekrarları, ortak kalıcı kimlik,
  farklı türlerde aynı ad ve derin ağaç sorunu yeniden oluşturuldu.
- Sayısal rebuild durumu için eski kodda iki ek test başarısız:
  [kayıt](before-rebuild.txt).
- Düzeltme sonrası profil paketinin tamamı: **101 başarılı / 1 atlanan**.
  [Arşiv: JUnit](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/profile-cutting/feature-graph-fix-2026-10-25/tests.xml), [çıktı](tests.txt), [statik kontrol](static.txt).
- Yeni regresyonlar; 1.200 derinlikli grafik, iptal, sınırsız grafik sınırı,
  güncellemeden sonra oluşan Cut List, ham `IDispatch` sarmalayıcılarının
  tekrar oluşturulması, beş montaj örneğinin doğru çarpılması, hata mesajı,
  `0/1/2` ve bilinmeyen rebuild durumlarını kapsar.
- API dönüşü, yerel referans SOLIDWORKS 2023 interop metadata dosyasında
  doğrulandı; çalışırken kullanılan sabitler bu dosyadan değil, kullanıcının
  kurulu SolidWorks `swconst` tür kitaplığından okunur.
- [API sözleşmesi](../api-contract.json) `get_NeedsRebuild2` ile güncellendi.
- CodeStack'in [Cut List tarama örneği](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/document/cut-lists/rename-cut-list-items/Macro.vba)
  tekrar ayıklama yaklaşımı için incelendi. Bu düzeltmede dış kaynak kodu
  kopyalanmadı ve yeni uygulama bağımlılığı eklenmedi.

Bu yerel testler COM mock'ları kullanır. Kullanıcının gerçek SLDPRT dosyası
bu ortamda açılmadı; gerçek SolidWorks testi başarılı olarak raporlanmaz.
Sonraki Windows derlemesinin native regresyon ve EXE açılış sonuçları
`packaging/latest-windows.json` / GitHub Actions kaydında ayrıca bulunur.
