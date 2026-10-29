# Depo birleştirme ve tekilleştirme kaydı · 28 Ekim 2026

Kullanıcı talimatı: önce son EXE teslim edilir; ardından tüm dallar main üzerinde toplanır ve gereksiz kopyalar kaldırılır.
EXE: [Windows derlemesi](https://github.com/gkkizil/gokworks/actions/runs/40630877925); uygulama kaynağı `714ebbe2fa051f3d2174db0dc5bc6a85966594ea`.
İndirme oturum açmadan HTTP 206 ve Windows MZ başlığıyla doğrulandı. Temizlik uygulama kodunu veya bu EXE dosyasını değiştirmez.

## Dallar

Altı özellik dalının son dosya ağacı, ilgili squash birleştirmesinin dosya ağacıyla birebir aynıdır. Main daha sonraki düzeltmeleri de içerir. Eski kod tekrar birleştirilmez; tamamlanmış dal başları kaydedilerek kaldırılır.

| Kaldırılan dal | Son commit | Main birleştirmesi / PR |
| --- | --- | --- |
| `codex/gear-families` | `c2ae50d5049a6db7a31d415db22dc9f4e5ee0b8d` | `714ebbe2fa051f3d2174db0dc5bc6a85966594ea` / [#15](https://github.com/gkkizil/gokworks/pull/15) |
| `codex/gear-math-audit` | `7404565f66b5c670cebf1df3842c5d959d2a954a` | `51d3b2b60a117a423179ad52103cd53fdb017095` / [#14](https://github.com/gkkizil/gokworks/pull/14) |
| `codex/gear-mvp` | `22a6e9c0c45191097157aa173710e4e1ffa186c2` | `27a4ed83689dca1a180077039df59e0cbb1c2f67` / [#13](https://github.com/gkkizil/gokworks/pull/13) |
| `codex/shaft-bore-cosmetic` | `6194d9d6e9a6fa6b5feb66846cf812b7e30e5d41` | `2232129c52881b0fdc705b3a1429a2b4242dd32a` / [#12](https://github.com/gkkizil/gokworks/pull/12) |
| `codex/shaft-standard-screenshots` | `5ff9bdcf5e04ded3b3469515ac5d078984780d00` | `8fbd8649c6ae2f45f96a703aee8e9fae56b8291b` / [#11](https://github.com/gkkizil/gokworks/pull/11) |
| `codex/parametric-shaft` | `4c141c959119606340664892885a28e66b11cb0f` | `cb3d2c7c15b118ccac8fa45d94deb5fa937def51` / [#10](https://github.com/gkkizil/gokworks/pull/10) |
| `release` | `c306c76604fd2cdc8d58127bedb41c48bbb9791b` | Main geçmişinin atası; benzersiz commit yok. |

GitHub Release etiketleri, önceki EXE dosyaları ve birleştirilmiş PR kayıtları korunur. Tek kalıcı kaynak/paylaşım dalı `main`dir.

## Birebir kopyalar

29 dosya kopyası kaldırıldı; toplam 2,018,505 bayt (1.92 MiB). Her kaldırmadan önce kalan kopyayla bayt eşitliği kontrol edildi. Kaynak betiklerinde adı/yolu kullanılan kopyalar ve benzersiz raporlar korunur.

Markdown/JSON/metin referansları kalan kopyaya yönlendirildi. SHA256 sütunu her iki kopyanın ortak içerik özetidir.

| Kaldırılan kopya | Kalan dosya | Bayt | SHA256 |
| --- | --- | ---: | --- |
| `docs/profile-cutting/selfcheck.png` | [Arşiv: docs/audit/source-selfcheck.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/audit/source-selfcheck.png) | 167080 | `eca5bc81c979be1c141fd86b50c80ffab7e3a13be25b7a21749a29a758506c07` |
| `docs/product-design-compact/after/application-settings.png` | [Arşiv: docs/fusion-workspace/before/application-settings.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/application-settings.png) | 19416 | `95e72fffd9a53d47ec48b620a59d1435e54d3a3fc6f9d87fcd4e26c7b24ea2ac` |
| `docs/product-design-compact/after/stack-measurement-picker.png` | [Arşiv: docs/fusion-workspace/before/stack-measurement-picker.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/before/stack-measurement-picker.png) | 37080 | `370e96d695d0a11023cbd0ae7e67277ab5699560064fb0de38b2fca81841e922` |
| `docs/verification-2026-10-24/baseline-full-run.txt` | [docs/fusion-workspace/final-regression-summary.txt](fusion-workspace/final-regression-summary.txt) | 3409 | `a22e9097df153393528ce347eb6b0392ba6361a9fae9f0f048356a48377aca8d` |
| `docs/verification-2026-10-24/source-dpi-1.25.png` | [Arşiv: docs/fusion-workspace/source-dpi-1.25.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/source-dpi-1.25.png) | 230368 | `8d180839ab087afae0b1ec720f2ca5e6ef0f200a292fca3136206f7470128c65` |
| `docs/verification-2026-10-24/source-dpi-1.5.png` | [Arşiv: docs/fusion-workspace/source-dpi-1.5.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/source-dpi-1.5.png) | 279936 | `42162821fe10cc71391511421cf5be713ebde7524a74ba2931f8ca6e71ed17c9` |
| `docs/fusion-workspace/source-selfcheck.json` | [docs/fusion-workspace/source-dpi-1.json](fusion-workspace/source-dpi-1.json) | 2113 | `4f1e1f86177ea9763442f7315d0e5f51932ab73e389bd1e78280842f313a493b` |
| `docs/verification-2026-10-24/source-dpi-1.png` | [Arşiv: docs/fusion-workspace/source-dpi-1.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/fusion-workspace/source-dpi-1.png) | 158838 | `069e132fae5737183a3b35bd3c2739bb6c2bdefe3160e46bc271aa6f483619c6` |
| `docs/nesting-hole-placement/after-dark.png` | [Arşiv: docs/nesting-hole-placement/after.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/nesting-hole-placement/after.png) | 116940 | `bcf78407b65e59f52cef18f54ab379eb5078863989134edb2ceb1e10b8dd60ea` |
| `docs/nesting-workspace/00-before.png` | [Arşiv: docs/nesting-usability/01-parts-dark.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/nesting-usability/01-parts-dark.png) | 141409 | `b1eddded577f456dd6afb2f9a69918bfa09e4f350b0adf6205d682f7b045c8c8` |
| `docs/reports/assets/audit-dxf-dwg-dark.png` | [Arşiv: docs/screenshots/gui-dxf-dwg-dark.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/gui-dxf-dwg-dark.png) | 30611 | `ed8497456c9b0be0725e3e60a413b4c57e05b0018dc4ae231754b929f3134ba2` |
| `docs/screenshots/gui-dxf-dwg-light.png` | [Arşiv: docs/screenshots/gui-dxf-dwg.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/gui-dxf-dwg.png) | 30621 | `4e34b315da05c9af1a49ccf3c5fe5513e6b6354d6beae59ab745c20cae16f134` |
| `docs/reports/assets/audit-dxf-dwg-light.png` | [Arşiv: docs/screenshots/gui-dxf-dwg.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/gui-dxf-dwg.png) | 30621 | `4e34b315da05c9af1a49ccf3c5fe5513e6b6354d6beae59ab745c20cae16f134` |
| `docs/reports/assets/audit-pdf-dark.png` | [Arşiv: docs/screenshots/gui-pdf-dark.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/gui-pdf-dark.png) | 28620 | `3c54f6ef04e1c4edf7f20e2562a4ebb246e17055d9a62f842938084406513df0` |
| `docs/reports/kr-workspace-fix/screenshots/geometric-tolerances-light.png` | [Arşiv: docs/reports/black-theme/screenshots/geometric-tolerances-light.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/black-theme/screenshots/geometric-tolerances-light.png) | 30783 | `a6e10d551b1438edc437806933741a9fe5e9c3fdce422b1794f2debe72076ef1` |
| `docs/reports/kr-workspace-fix/screenshots/geometric-tolerances-dark.png` | [Arşiv: docs/reports/black-theme/screenshots/geometric_tolerances-black.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/black-theme/screenshots/geometric_tolerances-black.png) | 30488 | `afb30419894b63a2b39e8d0c55496c948c31ba1885e0f2372f341194f7dc6ed5` |
| `docs/reports/final-audit/screenshots/manual-k-radius-dark.png` | [Arşiv: docs/screenshots/gui-manual-k-radius-dark.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/gui-manual-k-radius-dark.png) | 31194 | `f4501b3d6a49abc660c3ae2f5585500d1c9d8e8920f9b4d9896350888f6a480c` |
| `docs/reports/final-audit/screenshots/manual-k-radius-light.png` | [Arşiv: docs/screenshots/gui-manual-k-radius-light.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/gui-manual-k-radius-light.png) | 31278 | `d7655285c9aa67e7adae830c9b318c3c9416badf8c50c452e797f9f353824942` |
| `docs/reports/final-audit/screenshots/pdf-light.png` | [Arşiv: docs/screenshots/gui-current-pdf-light.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/gui-current-pdf-light.png) | 29460 | `6ee896127585f725f8f45a98a1cf787a1db0b9f36f180313a440cc4b03ceb9ce` |
| `docs/reports/fit-compatibility/screenshots/iso-dark.png` | [Arşiv: docs/reports/manual-iso/screenshots/iso-dark.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/manual-iso/screenshots/iso-dark.png) | 32011 | `f698407b0a61b4b8038da9eae11bb1b4892c8b7fb59534a7336c2a3845359919` |
| `docs/reports/fit-compatibility/screenshots/iso-interference-dark.png` | [Arşiv: docs/reports/manual-iso/screenshots/iso-interference-dark.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/manual-iso/screenshots/iso-interference-dark.png) | 32151 | `50818eab9f299fc382007634c6ade75ebcbacee599e47d36a0cf6bb43bf715e0` |
| `docs/reports/fit-compatibility/screenshots/iso-light.png` | [Arşiv: docs/reports/manual-iso/screenshots/iso-light.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/manual-iso/screenshots/iso-light.png) | 32221 | `15e753d5baf13a85039664293c970064630006fad5e322efb7b67b201f695f8e` |
| `docs/reports/fit-compatibility/screenshots/iso-transition-dark.png` | [Arşiv: docs/reports/manual-iso/screenshots/iso-transition-dark.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/manual-iso/screenshots/iso-transition-dark.png) | 32417 | `b746a2f2ad7eeaff0c276fedf613be67bf1eba081ea521350736436a581ea123` |
| `docs/reports/fit-compatibility/screenshots/iso-zones-dark.png` | [Arşiv: docs/reports/manual-iso/screenshots/iso-zones-dark.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/manual-iso/screenshots/iso-zones-dark.png) | 31227 | `a9aebd1f912754eec37e900614e1453038aabb56686fa1f95660c1e257dd0ee5` |
| `docs/reports/fluency-2026-10-17/before/01-pdf.png` | [Arşiv: docs/reports/fluency-2026-10-17/after/01-pdf.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/fluency-2026-10-17/after/01-pdf.png) | 95878 | `b3aca3e2be4b3e0926aa1293d0305de16a98e354a477d85919582ee3d6278ad6` |
| `docs/reports/fluency-2026-10-17/before/02-iso.png` | [Arşiv: docs/reports/fluency-2026-10-17/after/02-iso.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/fluency-2026-10-17/after/02-iso.png) | 115295 | `089be69951ddef943190053e8b08a59a72d35697d6937369dc4cbd14cb687b45` |
| `docs/reports/fluency-2026-10-17/before/03-compact.png` | [Arşiv: docs/reports/fluency-2026-10-17/after/03-compact.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/fluency-2026-10-17/after/03-compact.png) | 83666 | `f23a67eb099599326f68bce0d57c272a719d96ba6db7153cff05c05b2cbfd42a` |
| `docs/reports/fluency-2026-10-17/before/04-expanded.png` | [Arşiv: docs/reports/fluency-2026-10-17/after/04-expanded.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/fluency-2026-10-17/after/04-expanded.png) | 104645 | `c56f2683230c53dae18d23c31523285c895ca881c207d2936e928b507cb29c0e` |
| `docs/screenshots/gui-pdf-light.png` | [Arşiv: docs/screenshots/gui-pdf.png](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/gui-pdf.png) | 28729 | `e55ba63e826b979c5f362e3fd879b6593f9fdddd51f4d2f398fa261f123a3a81` |

## Doğrulama

- Uygulama modülleri, CAD/COM köprüleri, varlıklar, bağımlılıklar, testler ve lisanslar değiştirilmedi.
- Tekilleştirmeden kaynaklanan yeni kırık yerel Markdown bağlantısı yok.
- Güncel EXE indirme bloğu ve derleme isteği korunur; bu temizlik yeni EXE isteği üretmez.
- Kaynak/paylaşım belgeleri ve Windows EXE push filtresi yalnız main düzenine uyarlandı.
- Temizlik sonrası depo yapısı, tek dosyalı dağıtım ve derleme isteği denetimlerinin 27 testi geçti; atlanan test yok.
- EXE'nin Windows JUnit kaydında 2.700 kontrol, 0 hata/başarısızlık ve 46 ortam atlaması var; üç DPI paket açılış kontrolü geçti.
- EXE SHA256: `7857de3c48a2bc3acd010421a87ab361f403ae9a6027bca17abc4e3a6d8effc8`.
