# SolidWorks sac unsurunu bulma — 13 Ekim 2026

K/R işçisi ana sac parametrelerini `TemplateSheetMetal` unsurunda değiştirir;
gövde kalınlığını ve miras alınan değerleri `SheetMetal` unsurundan kontrol eder.
İnceleme sırasında bu ayrımı koruyan örnekler ve API belgeleri karşılaştırıldı.

## İncelenen kaynaklar

- [PowerSM — ana klasörün K değerini değiştirme](https://github.com/AmenJlili/power-sm/blob/6c835fb712c18df8969500ec247a0768d3af0d37/PowerSM/PowerSM/PowerGeometry_Form.cs#L1058):
  `GetSheetMetalFolder → GetFeature → GetDefinition → GetCustomBendAllowance`.
- [PowerSM — klasördeki sac unsurlarını bulma](https://github.com/AmenJlili/power-sm/blob/6c835fb712c18df8969500ec247a0768d3af0d37/PowerSM/PowerSM/PowerGeometry_Form.cs#L470):
  `GetSheetMetals()` listesini ayrıca kullanır.
- [CodeStack — türüne göre unsur ve alt unsur dolaşımı](https://github.com/xarial/codestack/blob/0cde3849a184cdbbface61238ef431a6ebb9d530/solidworks-api/document/sheet-metal/export-all-flat-patterns/Macro.vba#L475):
  adı yerine `GetTypeName2` ile türü kontrol eder, alt unsurları da dolaşır.
- [SolidWorks API belge aynası](https://github.com/pedropaulovc/offline-solidworks-api-docs/releases/tag/v3.12.1):
  `ISheetMetalFolder.GetSheetMetals` sac unsuru dizisi döndürür;
  Instant3D `ICE` sarmalayıcısının gerçek türü `GetTypeName` ile okunur.
  `UseMaterialSheetMetalParameters`, yalnız gauge tablosu kullanılmıyorsa geçerlidir.

Kaynaklar okundu; örnek projeler SolidWorks üzerinde çalıştırılmadı.
Dosya özetleri ve sabit commitler [sources.json](sources.json) içindedir.

## Bulunan ve düzeltilen durumlar

1. Gövde sacı yalnız unsur ağacında aranıyordu. Artık klasörün
   `GetSheetMetals()` listesi de aynı taramaya katılır; yinelenen unsurlar
   bir kez işlenir. Listeye ait saclar geri okuma ve geri alma kontrollerine de dahildir.
2. Keşif API'leri boş döndüğünde ağaçtaki modern ana sac unsuru reddediliyordu.
   Artık ağaçta tek bir `TemplateSheetMetal` varsa aynı ana unsur kullanılır.
3. `GetTemplateSheetMetal` üyesi yoksa klasör yoluna geçilemiyordu. Yalnız
   eksik üye/unknown-name hataları alternatif aramaya izin verir; gerçek COM
   çalışma hataları hâlâ işlemi durdurur.
4. Geçmiş/gövde gibi klasörlerin bastırılma durumu ve unsur tanımı, sac
   bulunmadan önce okumayı engelleyebiliyordu. Klasörün kendisinden K/R
   istenmez; içindeki sac ve büküm unsurları kontrol edilir.
5. `ICE` tipindeki Instant3D sarmalayıcılar gerçek unsur türüyle değerlendirilir.
6. Malzeme özelliği gauge tablosu kontrolünden önce okunuyordu. API'nin
   geçerlilik koşuluna uygun olarak önce gauge durumu kontrol edilir.

Günlükte **Ana sac unsuru**, **Gövde sac unsuru** ve keşif yolu gösterilir.
Birden fazla ana aday, yanlış tür, okunamayan sac parametresi veya etkin
özel büküm ayarı başarıya çevrilmez. Tek gövdeli parça kapsamı sürer.

## Kontrol

Eski kod dört yeni senaryoda hata verdi: eksik keşif üyesi, API'nin boş
dönmesi, sacın yalnız klasör listesinde bulunması ve geçmiş klasörünün
bastırılma API'sinin sonuç vermemesi. [Önceki davranış kaydı](before.log).

Son kodda **31 hedefli kontrol geçti**: ana/gövde seçim yolları, eşleşmeyen
kalınlık, özel ayarlar, değişikliğin başka konfigürasyona yayılması, geri
okuma/geri alma ve gerçek Tk arayüzünden tarama–uygulama–CSV akışı.
[Son kontrol çıktısı](checks.log).

Bu ortamda gerçek Windows/SolidWorks oturumu ve kullanıcının montajı
çalıştırılmadı; bu sonuçlar gerçek modelde atamanın doğrulandığı anlamına
gelmez. EXE oluşturulmadı.
