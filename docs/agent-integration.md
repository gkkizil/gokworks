# Ajan dallarından otomatik PR ve birleştirme

Kullanıcının 4 Kasım 2026 tarihli talimatıyla `agent/codex` ve `agent/claude`
otomatik entegrasyona alınır. Ajan kendi worktree'sinde test edip kendi dalına
normal push yapar. GitHub'da **Compare & pull request** düğmesine basmak gerekmez.

`Agent integration` workflow'u iki dalı da tarar, açık PR'ı kullanır veya PR açar.
Push olayı yanında yaklaşık beş dakikalık zamanlanmış tarama vardır; böylece
workflow dosyası henüz kendi dalında bulunmayan Claude/Codex değişiklikleri de
`main` üzerindeki kurulum tamamlandıktan sonra keşfedilir. GitHub zamanlanmış
işleri yoğunlukta geciktirebilir.

Her PR'ın kesin head SHA'sı ile tarama anındaki main SHA'sı, geçici Windows
checkout'unda birleştirilir. Bütün pytest paketi mevcut sınırlı süreç çalıştırıcısı
ile çalışır; C# test referansları ve uygulama açılış kontrolü de hazırlanır.
Gerçek SolidWorks gerektiren kabul testleri ayrıca uygun ortam ister.

Başarılı sonuç yalnız aynı head/main çifti için kullanılabilir. Diğer ajanın
PR'ı main'i ilerletirse yeni birleşim yeniden test edilir. Başarısız test,
çakışma, taslak PR veya aynı commit'te kullanıcı tarafından kapatılmış PR otomatik
birleştirilmez. Koruma kuralları ve gerekli onaylar GitHub tarafından uygulanır;
workflow bunları kaldırmaz. Kaynak dallar silinmez veya sıfırlanmaz. Merge commit
kullanılarak uzun ömürlü ajan dallarının geçmiş bağlantısı korunur.

Başarısız aynı head/main çifti her taramada yeniden test edilmez. Yeni commit
göndermek veya Actions → Agent integration → Run workflow → `retry_failed`
seçeneğiyle yeniden denemek gerekir. Test kanıtları workflow artifacts alanında
saklanır. Tüm entegrasyon işleri tek concurrency grubu kullanır. Bir PR
birleşince güncel main üzerinden yeni tarama ayrıca tetiklenir; diğer ajan
dalı zamanlanmış taramayı beklemeden yeni main ile doğrulanır.
Yeni Codex push'u, aynı dalın artık eski commit'ine ait çalışan entegrasyon
işini iptal ederek son commit'in doğrulamasına yer açar. Güncel commit'in işi,
zamanlanmış/manual işler ve başka dalların işleri bu yolla iptal edilmez.

Windows hataları ayrıca test adı ve hata metniyle Actions anotasyonlarına
yazılır. Yerel süreç çökmeleri de korunur. `[agent-diagnostics]` işaretli bir
commit yalnız eski raporların teşhisini tetikler; doğrulama veya merge yapamaz.
`Agent failure diagnostics` workflow'u önceki çalışmanın artifact'lerini okuyup
aynı raporlayıcıyla incelemek için kullanılır.

## GitHub kurulumu

- Workflow ve `.github/scripts/agent-integration.cjs` main'e ilk kez alınmalıdır.
  Kurulum commit'i ajan dalındayken o dalın push'u da ilk PR'ı açıp test edebilir.
- Settings → Actions → General → Workflow permissions bölümünde **Allow GitHub
  Actions to create and approve pull requests** açık olmalıdır. Workflow PR
  onaylamaz; GitHub PR oluşturma iznini de bu seçenekle yönetir.
- Repo merge commit'e izin vermelidir. Mevcut branch protection/ruleset kuralları
  korunur. Ek insan onayı gerektiren bir kural varsa PR o onayı bekler.
- Ayrı PAT/secret gerekmez: PR oluşturma, commit status ve son birleştirme işleri
  kendi sınırlı `GITHUB_TOKEN` izinlerini kullanır. Test job'unda kod yazma izni
  yoktur; checkout kimlik bilgileri diskte tutulmaz.
- GitHub kendi token'ıyla açılan PR'lar için başka PR workflow'larını otomatik
  tetiklemez. Bu nedenle tam Windows doğrulaması doğrudan bu workflow içindedir.
  Ayrıca zorunlu başka kontroller varsa onların tamamlanması da gerekir.

Yerel otomasyon mantığı testi:

```sh
node .github/scripts/tests/agent-integration.test.cjs
```

Bu testler GitHub API sınırını kontrollü yanıtlarla sınar; canlı GitHub/Windows
çalıştırması yerine geçmez. Uygulamanın üretim kodu bu otomasyondan etkilenmez.
