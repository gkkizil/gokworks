# Abkant: merkez çizgisi bulunan aktif parçanın okunması

SolidWorks Flat-Pattern içindeki `MergeFace` açıkken büküm bandı komşu düz
yüzlere birleşebilir. `FlatPatternSketchSegments2` yalnız merkez çizgisi
döndürdüğünde okuyucu gerçek bant genişliğini bulamıyor ve parçayı reddediyordu.

Okuyucu artık geçici açınımda bu ayarı kapatıp genişliği gerçek ayrılmış
yüzlerden ölçer. Unsur sahipliği yeniden oluşturmada değişirse merkez çizgisiyle
kesişen, R/açı/kalınlık sınırlarına uyan tek yüz kabul edilir; belirsiz eşleşme
reddedilir. Büküm unsurları yeniden oluşturma sonrası kalıcı referanslarıyla
yeniden bulunur. K faktöründen genişlik tahmin edilmez.

Başarı, hata ve iptalde `MergeFace`, bastırma durumları, aktif konfigürasyon
ve seçim listesi geri yüklenip doğrulanır. Başarısız `ModifyDefinition`
sonrası seçim erişimi serbest bırakılır. Geri yükleme hatası gizlenmez.
Kaynak parça kaydedilmez; geçici yeniden oluşturma SolidWorks'ün bellek içi
dirty göstergesini etkileyebilir.

Yayımlanmış API dayanakları:

- [IFlatPatternFeatureData.MergeFace](https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFlatPatternFeatureData~MergeFace.html)
- [IOneBendFeatureData.FlatPatternSketchSegments2](https://help.solidworks.com/2019/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IOneBendFeatureData~FlatPatternSketchSegments2.html)
- [Feature seçim erişimi ve ModifyDefinition](https://help.solidworks.com/2025/english/api/sldworksapiprogguide/Miscellaneous/Accessing_Selections_that_Define_Features.htm)
- [Birleştirilmiş yüzler ve teğet çizgileri](https://support.hawkridgesys.com/hc/en-us/articles/115002472911-How-to-Show-Tangent-Bend-Lines-in-a-SOLIDWORKS-Sheet-Metal-Flat-Pattern)

Yerel doğrulama (Python 3.13, Qt offscreen):

- Abkant modülü: 126 geçti; bunun 31'i SolidWorks sözleşme testi.
- Sac envanteri, ortak CAD API ve bağlantı/ayar regresyonları: 66 geçti,
  1 atlandı; ayrıca 5 alt test geçti.
- Uygulama `--self-check`: geçti.
- Değişen Python dosyalarında Ruff F, compileall ve `git diff --check`: geçti.

Bu sonuçlar kontrollü Python/COM sınır testleridir. Linux ortamında canlı
SolidWorks veya ekrandaki SLDPRT dosyasıyla doğrulama yapılmamıştır.
