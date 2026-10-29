# Geliştirme ve doğrulama kayıtları

[Güncel kullanım kılavuzu](../README.md), uygulamayı ilk kez kullanacak kişiler
için hazırlanmıştır. Bu sayfa önceki geliştirme, arayüz geçişi ve test
kayıtlarına erişim sağlar. Geçmiş raporlardaki ekranlar, dosya yolları ve test
sayıları raporun ait olduğu sürümü anlatır.

Eski ekran görüntüleri, ham günlükler ve üretilmiş rapor kopyaları güncel
daldan temizlenmiştir. **Arşiv** bağlantıları dosyanın Git geçmişindeki
sabit sürümüne gider; yeni ekran/test çıktıları CI artifact'larında tutulur.

| Konu | Kayıt |
| --- | --- |
| İlk arayüz, K/R, ISO ve GD&T geliştirmeleri | [Rapor arşivi](reports/README.md) |
| K/R ve çalışma alanı düzenlemeleri | [Çalışma alanı düzeltme raporu](reports/kr-workspace-fix/README.md) |
| 14 Ekim kod incelemesi | [İnceleme ve doğrulama kapsamı](astra-review.md) |
| Qt arayüzüne geçiş | [Migrasyon raporu](QT_MIGRATION_REPORT.md) |
| Mevcut ayrıntıların Qt ekranlarına aktarılması | [Korunan açıklamalar ve grafikler](qt-migration/restored-details) |
| 20 Ekim genel uygulama testi | [Doğrulama raporu](validation-2026-10-20/README.md) |
| Aktarım ve Montaj ekranlarının iki sütunlu düzeni | [Arayüz kontrolü ve ekranlar](transfer-columns/README.md) |
| Modüllerin ayrı klasörlerde toplanması | [Depo düzeni ve doğrulama](repository-structure.md) |

Son klasör düzenlemesinin Linux/Qt kontrolünde 911 test ve 878 alt senaryo
geçti; Windows veya gerçek SolidWorks gerektiren 7 test atlandı.
[Sonuç özeti](repository-organization/checks.json),
[uygulama açılış kontrolü](repository-organization/selfcheck.json) ve
[motor kaynak karşılaştırması](repository-organization/engine-audit.json)
ayrı dosyalarda saklanır.

Otomatik testlerde CAD sınırının test nesneleriyle sınanması, gerçek bir
SolidWorks dosyasında üretim işlemi yapıldığı anlamına gelmez.
Windows/SolidWorks kabul adımları [yerel kontrol kılavuzunda](local-solidworks-check.md)
ve ilgili modül belgelerinde bulunur. Windows EXE derlemesinin kendi kontrol
sonuçları [paket kaydında](../packaging/latest-windows.json) belirtilir.
