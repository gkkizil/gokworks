# Proje yedekleme noktası

[18 Ekim 2026 sürüm kaydı](checkpoint-2026-10-18.json), yedekleme öncesindeki
main commitini ve bu sürümün Windows paket bağlantısı/SHA256 bilgisini içerir.
Bu kaydı ekleyen commit de Git yedeğine dahil edilmelidir.

Git yedeği, kaynak depodaki tüm dalların ve etiketlerin eriştiği commit
geçmişini içermelidir. `.bundle` dosyası tam Git geçmişini tek dosyada taşır;
`git bundle verify DOSYA.bundle` ile kontrol edilir ve
`git clone DOSYA.bundle gokworks` ile geri açılabilir.

Ayrı GitHub yedek deposuna kaynak dalları ve etiketleri aktarılmalıdır.
Kaynak ile yedekteki `refs/heads/*` ve `refs/tags/*` commit/etiket kimlikleri
karşılaştırılarak aktarım doğrulanır. Yedek depoda GitHub Actions kapalı
olmalıdır; böylece kopyalanan iş akışları yeni paket derlemeleri başlatmaz.

Git yedeği GitHub Actions artefaktlarının, iş kayıtlarının, issue'ların,
PR yorumlarının veya depo ayarlarının yedeği değildir. Windows paketinin
bağlantısı süreli olabilir; EXE dosyası ayrıca saklanmalıdır.
