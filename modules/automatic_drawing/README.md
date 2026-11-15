# Otomatik Teknik Resim

GOKWORKS → Üretim → Otomatik Teknik Resim.

Bu modül kayıtlı SLDPRT / SLDASM kaynaklarından SolidWorks API üzerinden
modele bağlı SLDDRW oluşturmak için geliştirilmiştir. Python, mevcut PySide6,
pywin32 bağlantısı ve sıralı JobManager kullanılır. Yeni CAD motoru veya
ayrı bir MCP / yapay zekâ servisi gerekmez.

**Doğrulama durumu:** Linux üzerindeki algoritma, dosya güvenliği, ham COM
çağrı sözleşmeleri ve Qt testleri gerçek SolidWorks kabul testi değildir.
Bu geliştirme ortamında lisanslı SolidWorks bulunmadığından gerçek CAD
üretimi henüz doğrulanmamıştır. Opt-in Windows testi aşağıdadır.

## Kullanım

1. SolidWorks’te kaynağı yeniden oluşturup kaydedin. Uygulama bu modülde
   kaynak parça / montaj dosyalarını otomatik kaydetmez.
2. Dosya veya klasör ekleyin ya da Aktif dosyayı al komutunu kullanın.
   Dosya / konfigürasyon seçimleri ile montaj hiyerarşisi aynı ağaçtadır.
3. Analiz et ile belge bilgilerini, özellikleri, dış ölçüleri ve önerilen
   parça sınıfını inceleyin. Konfigürasyon hücresi düzenlenebilir.
4. Firma DRWDOT şablonunu, gerekirse SLDDRT antetini ve çıktı klasörünü
   seçin. Boş DRWDOT alanında SolidWorks varsayılanı kullanılır.
   Varsayılan pafta A3 yatay, izdüşüm ISO birinci açı ve sonuç birimi mm’dir.
5. Ana görünüşü otomatik veya manuel seçin. Önce modelde resme işaretli
   ölçüler kullanılır. Geometrik referans ölçüleri ayrıca seçilebilir;
   bunlara tasarım toleransı veya datum bilgisi uydurulmaz.
6. Resimleri oluştur komutu kaynakları tek worker üzerinde sırayla işler.
   Mevcut dosya atlanır veya benzersiz ad üretilir; üzerine yazılmaz.
7. Sonuçlar sekmesinden PASS / WARNING / FAIL ve dosya bazlı bulguları
   inceleyin. Önizleme, SolidWorks’ten dışa aktarılan gerçek PDF’i gösterir.
   Her başarılı pakette SLDDRW ve JSON raporu; seçilmişse PDF / DXF vardır.

PASS yalnız temel yapısal denetimlerin geçtiğini belirtir; imalat serbest
bırakma onayı değildir. Belirsiz veya eksik imalat bilgileri raporlanır.

## Mevcut kapsam

- Altı standart yönden yüzey alanı / eksen / parça sınıfı destekli ana
  görünüş seçimi; native bağlı üst / yan izdüşümler ve izometri.
- A4–A0, özel boyut, otomatik / manuel ölçek, gerçek görünüş sınırlarından
  yeniden sığdırma; gerekirse izometriyi ayrı paftaya alma.
- Native model ölçüleri, isteğe bağlı AutoDimension, merkez işaretleri,
  ölçü metni yerleşimi ve kayıt sonrası yeniden denetim.
- Üç BOM tipi; gerçek bileşen kimlikleri, örnek adetleri ve görünen adet
  sütunu karşılaştırması. BOM’a bağlı balonlar seçilebilir.
- Tek gövdeli sac için mevcut, doğru üst konfigürasyona bağlı açınım
  konfigürasyonu varsa ek pafta. Çok gövdeli sac açınımı henüz desteklenmez.
- Kaynak ve açık belgeleri koruma; iptal, başarısız dosyayı ayırma,
  benzersiz dosya / konfigürasyon kuyruğu ve aşama raporu.

Kesit / detay oluşturma, tam delik / diş / PCD tanıma, çok gövdeli sac
eşleştirmesi ve tüm geometriye üretim ölçüsü oluşturma tamamlanmış değildir.
Bkz. [bilinen sınırlar](../../docs/automatic-drawing/KNOWN_LIMITATIONS.md).

## Testler

~~~powershell
python -m pytest modules/automatic_drawing/tests -q
~~~

Gerçek Windows / SolidWorks kabul testi ayrıca etkinleştirilir:

~~~powershell
$env:GOKWORKS_DRAWING_LIVE_SOURCE = 'C:\fixtures\Plate.SLDPRT'
$env:GOKWORKS_DRAWING_LIVE_TEMPLATE = 'C:\templates\Company-A3.drwdot'
python -m pytest modules/automatic_drawing/tests/test_live_solidworks.py -v
~~~

Fixture kayıtlı ve tam yeniden oluşturulmuş olmalı; SolidWorks açık,
kurulu ve lisanslı olmalıdır. Test geçici çıktı klasöründe çalışır ve
kaynak dosyanın baytlarının değişmediğini de kontrol eder.

[Mimari](../../docs/automatic-drawing/ARCHITECTURE.md) ·
[API kaynakları](../../docs/automatic-drawing/SOLIDWORKS_API_REFERENCES.md) ·
[Kurallar](../../docs/automatic-drawing/DRAWING_RULES.md) ·
[Araştırma](../../docs/automatic-drawing/RESEARCH.md) ·
[Test raporu](../../docs/automatic-drawing/TEST_REPORT.md).
