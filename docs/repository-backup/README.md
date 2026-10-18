# Proje yedekleme noktası

GitHub yedek deposu: [gkkizil/gokworks-yedek](https://github.com/gkkizil/gokworks-yedek).
Kaynak depo ve ana geliştirme dalı: [gkkizil/gokworks — main](https://github.com/gkkizil/gokworks/tree/main).

[18 Ekim 2026 sürüm kaydı](checkpoint-2026-10-18.json), yedekleme öncesindeki
main commitini ve bu sürümün Windows paket bağlantısı/SHA256 bilgisini içerir.
Bu kaydı ekleyen commit de Git yedeğine dahil edilmelidir.

Git yedeği, kaynak depodaki tüm dalların ve etiketlerin eriştiği commit
geçmişini içermelidir. `.bundle` dosyası tam Git geçmişini tek dosyada taşır;
`git bundle verify DOSYA.bundle` ile kontrol edilir ve
`git clone DOSYA.bundle gokworks` ile geri açılabilir.

Ayrı GitHub yedek deposuna kaynak dalları ve etiketleri aktarılmalıdır.
Kaynak ile yedekteki `refs/heads/*` ve `refs/tags/*` commit/etiket kimlikleri
karşılaştırılarak aktarım doğrulanır. Yedek depoda GitHub Actions kapatılabilir. İlk aktarımın son commitinde
`[skip ci]` kullanılarak kopyalanan push iş akışlarının yeni paket
derlemeleri başlatması önlenir. Bu işaret depo genelinde Actions ayarını
kapatmaz; sonraki yedek güncellemeleri de aynı şekilde yapılmalıdır.

Git yedeği GitHub Actions artefaktlarının, iş kayıtlarının, issue'ların,
PR yorumlarının veya depo ayarlarının yedeği değildir. Windows paketinin
bağlantısı süreli olabilir; EXE dosyası ayrıca saklanmalıdır.
