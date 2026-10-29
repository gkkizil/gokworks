# Tolerans yığılması · sadeleştirilen çalışma akışı

1. **Ölçüleri al:** Aktif resmi oku, Dosya seç ve oku veya Manuel ölçü.
2. **Zinciri kur:** Bir ölçü seç, + Topla / − Çıkar kullan. Formül seçimi gösterir.
3. **Kontrol edip hesapla:** Gerçek çizimde ortak doğrultu/referansı ve işaretleri
   kontrol et, kutuyu işaretle, Hesapla ve sonuçları göster düğmesine bas.

Doğrusal CAD ölçülerinde ayrı ayrı serbest metin açıklaması istenmez. Kullanıcının
açık doğrultu onayı projede ve raporlarda saklanır; şema CAD geometrisini
doğrulamış gibi sunulmaz. Eksik tolerans, farklı doğrultu/referans, özel katsayı
ve çap/radyüs ilişkisi kontrolleri korunur. Eksik bilgi varken hesap kapalıdır.
Uyarı kartı ilgili satırı belirtir; düzeltme düğmesi doğru ölçüyü veya ayarı açar.

- [Arşiv: Zincir · koyu tema](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/tolerance-stack/usability/chain-dark.png)
- [Arşiv: Zincir · açık tema](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/tolerance-stack/usability/chain-light.png)
- [Arşiv: Eksik tolerans ve düzeltme düğmesi](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/tolerance-stack/usability/missing-tolerance.png)
- [Arşiv: Küçük pencerede uyarı ve temel işlemler](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/tolerance-stack/usability/missing-tolerance-compact.png)
- [Arşiv: Sonuç kartları ve katkı grafiği](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/tolerance-stack/usability/results-dark.png)

Ekranlar gerçek PySide6 arayüzünden, manuel A−B−C örneğiyle alınmıştır.
**Gerçek SolidWorks bağlantısı bu Linux ortamında test edilmedi.**
[validation.json](validation.json) yalnız bu görsel koşunun sonuçlarını içerir.

Doğrulanan kontroller: simetrik/asimetrik ve işaretli limit/RSS/Monte Carlo
hesapları, CAD COM taklitleri, açık doğrultu onayı, tolerans tamamlama, farklı
eksen/özel dönüşüm engelleri, kaydet/yükle uyumluluğu, PDF/Excel ve kontrollü
anotasyon çıktısı. Eski JSON dosyaları yeni isteğe bağlı onay alanı olmadan
açılabilir; eski hesap sonucu güncel kabul edilmez.

[checks.json](checks.json): **116 farklı kontrol geçti**, hata veya atlanan kontrol
yok. İlk koşu 113 kontrol, ardından arayüz için 29 ve son yerleşim değişiklikleri
için 12 kontrol çalıştırıldı. Koşular örtüştüğü için bu sayılar toplanmaz.

Yeniden görsel üretimi:

```bash
QT_QPA_PLATFORM=offscreen python docs/report-tools/capture_stack_usability.py docs/tolerance-stack/usability
```

Matematik, COM, kayıt/rapor, arayüz ve anotasyon kontrolleri:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest modules/tolerance_stack/tests/test_tolerance_stack_math.py modules/tolerance_stack/tests/test_tolerance_stack_com.py modules/tolerance_stack/tests/test_tolerance_stack_storage_report.py modules/tolerance_stack/tests/test_tolerance_stack_gui.py modules/tolerance_stack/tests/test_tolerance_stack_drawing_writer.py
```

[Ayrıntılı kullanım ve mühendislik sınırları](../../tolerance-stack.md)
