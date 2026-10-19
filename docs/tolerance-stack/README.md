# Tolerans yığılması · geliştirme kanıtları

[Kullanım, mimari, matematik ve CAD güvenliği](../tolerance-stack.md) ·
[Örnek JSON / PDF / Excel](../../tolerance_stack/examples)

**Güncel arayüz:** [Sadeleştirilmiş kullanım akışı ve ekran görüntüleri](usability/README.md).
Alt kısımdaki eski ekranlar önceki arayüzün geliştirme kayıtlarıdır.

Bu klasör gerçek Qt ekranlarını ve çalıştırılmış kontrol sonuçlarını içerir.
Ekranlardaki analiz **manuel A−B−C örneğidir**; gerçek SolidWorks çalıştırıldığı
iddia edilmez.

- [Zincir · koyu tema](screenshots/chain-dark.png)
- [Sonuçlar · koyu tema](screenshots/results-dark.png)
- [Monte Carlo](screenshots/monte-carlo-dark.png)
- [Sonuçlar · açık tema](screenshots/results-light.png)
- [Teknik resim çıktı seçenekleri](screenshots/drawing-output-dark.png)
- [Küçük pencere](screenshots/chain-compact.png)

[validation.json](validation.json): 615 tam regresyon + 878 alt senaryo geçti;
2 gerçek SolidWorks testi atlandı. Son opsiyonel ham COM bağlantısı için ayrıca
69 hedefli test + 5 alt senaryo geçti. Koşular örtüşür; sayılar toplanmaz.
Qt açılışı %125/%150 ölçeklerde on ekran, iki tema, dört boyut ve gerçek
PDF/XLSX çıktısıyla yeniden kontrol edildi. Windows EXE bu adımda üretilmedi.

[example-validation.json](example-validation.json) örneğin tam MC sonuçlarını,
[api-contracts.json](api-contracts.json) interop meta verisiyle kontrol edilmiş
API imzalarını, [sources.json](sources.json) referans commit/lisans kayıtlarını,
[changes.json](changes.json) eklenen/değiştirilen dosyaları içerir.

Yeniden görsel üretimi:

```bash
DISPLAY=:99 python docs/report-tools/capture_tolerance_stack.py docs/tolerance-stack
```
