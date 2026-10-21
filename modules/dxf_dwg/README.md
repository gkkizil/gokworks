# DXF / DWG — Sac kalınlığına göre klasörleme

**DXF / DWG → Sac kalınlığına göre klasörle** seçeneği
açıkken uygulama, sacın SolidWorks'ten okunan gerçek kalınlığına göre çıktı
klasörleri oluşturur. Başlangıçta açıktır; tercih kaydedilir.

```text
Çıktı/
  1,5 mm/
    BRAKET - 1.5 mm - 12 adet.dxf
  2 mm/
    KAPAK - 2 mm - 3 adet.dxf
    Alt montaj/
      DESTEK - 2 mm - 6 adet.dxf
```

Klasör adında Türkçe ondalık virgül, mevcut dosya adlarında ondalık nokta
kullanılır. DXF ve DWG aynı kurala uyar; seçtiğiniz biçim kaydedilir.
Kaynak alt klasörler kalınlık klasörünün içinde korunur: farklı kaynak
klasörlerindeki aynı adlı parçalar birbirinin üzerine yazılmaz.

Seçenek kapalıysa önceki çıktı düzeni kullanılır: kaynak alt klasör yapısı,
seçtiğiniz çıktı klasörünün altında korunur. PDF aktarımı bu seçenekten etkilenmez.

Mevcut dosyaları atlama ve güvenli üzerine yazma kuralları seçilen hedef
klasörde uygulanır. Sonuç listesi, dosya ayrıntıları ve CSV raporu gerçek
çıktı yolunu gösterir. Kalınlık okunamazsa, geçersizse veya parçada birden
fazla farklı kalınlık varsa tahmini bir klasöre aktarım yapılmaz; hata bildirilir.

[Genel kullanım ve SolidWorks kontrol adımları](../../README.md#sac-metal-açınımı) ·
[Aktarım yöntemi ve kaynak karşılaştırması](../../docs/dxf-dwg-verification.md).

Bu eklemede **12 ilgili kontrol geçti**: 8 aktarım/yol kontrolü ve 4 gerçek
Tk arayüz kontrolü. Karışık kalınlıklar, aynı adlı kaynak alt klasörleri,
DXF/DWG çıktıları, geçersiz kalınlık, mevcut dosyaları atlama, güvenli üzerine
yazma, CSV yolu, tercih kaydı, sayfa önbelleği ve PDF ayrımı doğrulandı.
Aktarım kontrolleri SolidWorks COM davranışını temsil eden test nesneleriyle
yapıldı; gerçek Windows/SolidWorks aktarımı bu bulut ortamında çalıştırılmadı.
EXE oluşturulmadı.

[Klasörleme seçeneğinin güncel ekran görüntüsü](examples/thickness-folders-dark.png).
Görüntü, kullanıcı tercihlerini değiştirmeden
`python modules/dxf_dwg/examples/capture.py` ile gerçek Tk ekranından yeniden alınabilir.
