# Tolerans yığılması · geliştirme kanıtları

[Kullanım, mimari, matematik ve CAD güvenliği](../tolerance-stack.md) ·
[Örnek JSON / PDF / Excel](../../modules/tolerance_stack/examples)

**Güncel arayüz:** [Sadeleştirilmiş kullanım akışı ve ekran görüntüleri](usability/README.md).
Alt kısımdaki eski ekranlar önceki arayüzün geliştirme kayıtlarıdır.

Bu klasör gerçek Qt ekranlarını ve çalıştırılmış kontrol sonuçlarını içerir.
Ekranlardaki analiz **manuel A−B−C örneğidir**; gerçek SolidWorks çalıştırıldığı
iddia edilmez.

- [Arşiv: Zincir · koyu tema](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/tolerance-stack/screenshots/chain-dark.png)
- [Arşiv: Sonuçlar · koyu tema](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/tolerance-stack/screenshots/results-dark.png)
- [Arşiv: Monte Carlo](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/tolerance-stack/screenshots/monte-carlo-dark.png)
- [Arşiv: Sonuçlar · açık tema](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/tolerance-stack/screenshots/results-light.png)
- [Arşiv: Teknik resim çıktı seçenekleri](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/tolerance-stack/screenshots/drawing-output-dark.png)
- [Arşiv: Küçük pencere](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/tolerance-stack/screenshots/chain-compact.png)

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
