# GOKWORKS — Claude ve Codex çalışma kuralları

Her iki ajan da bütün modüllerde çalışabilir. Kalıcı modül veya uzmanlık
sahipliği yoktur; görev kapsamını kullanıcının o anki talimatı belirler.

## Her görevin başında

- Güncel kaynak kodunu esas al; sohbet geçmişindeki mimari varsayımlarını doğrula.
- `git status --short --branch`, `git worktree list`, son commitler ve ilgili
  dosyaların geçmişini incele. Değiştirmeden önce dosyanın güncel hâlini oku.
- Komitlenmemiş kullanıcı/ajan değişikliklerini koru. Diğer ajanın devam eden
  işini bilmiyorsan tahmin etme; olası dosya çakışmalarını bildir.

## Ayrı çalışma alanları

Ana çalışma klasörü `gokworks`, Codex alanı `gokworks-codex` (`agent/codex`),
Claude alanı `gokworks-claude` (`agent/claude`) olacak şekilde kardeş klasörler
kullanılır. Aynı fiziksel klasörde iki ajan eş zamanlı kod değiştirmez.

İlk kurulum, ana depo klasöründen:

```sh
git fetch origin main
git worktree add -b agent/codex ../gokworks-codex origin/main
git worktree add -b agent/claude ../gokworks-claude origin/main
```

Bu kurulum 4 Kasım 2026'da bu çalışma ortamında uygulandı. Var olan branch
ve worktree'leri yeniden oluşturmaya çalışma; önce durumlarını kontrol et.
Worktree'ler aynı Git geçmişi, nesne deposu ve referanslarını paylaşır;
çalışma dosyaları ve index ayrıdır. Ana klasördeki değişiklikler yeni alanlara
otomatik taşınmaz. Python sanal ortamları ve yerel araçlar her alan için
ayrıca seçilmelidir.

## Değişiklik ve entegrasyon

- Yalnız kendi çalışma alanında düzenleme yap. Başka alanın komitlenmemiş
  dosyalarını kendi işine otomatik dahil etme.
- Küçük, görevle ilgili değişiklikler yap; gereksiz toplu refactoring, arayüz
  yeniden tasarımı veya önceki özellikleri geri alma işlemi yapma.
- Giriş noktası, modül kaydı, ortak CAD servisleri, SolidWorks bağlantıları,
  veri modelleri, bağımlılıklar ve ana pencere değişikliklerinde çağıranları
  kontrol et. Fonksiyon imzaları ve veri sözleşmelerini mümkün olduğunca koru.
- Diğer ajanın commitlerini incelemek serbesttir. Kullanıcı talimatı olmadan
  rebase veya elle `main` entegrasyonu yapma.
- Kullanıcı 4 Kasım 2026'da `agent/codex` ve `agent/claude` için PR açılmasını
  ve testler başarılıysa otomatik birleştirilmesini açıkça istedi. Bu yetkiyi
  `.github/workflows/agent-integration.yml` uygular: sabit head/main birleşimi
  Windows'ta test edilir; dal veya main ilerlerse yeni doğrulama gerekir.
  Başarısız testler, çakışmalar, taslak/kapalı PR'lar ve depo korumaları aşılmaz.
  CI'ın geçici checkout'undaki test birleşimi canlı worktree'leri değiştirmez.
- Diğer ajanın dalını veya main'i kendi dalına yalnız gerçek bir çakışma
  (otomasyonun "çakışma var" sonucu ya da aynı dosyada bilinen örtüşen değişiklik)
  olduğunda birleştir. Gereksiz birleştirmeler dalın head'ini değiştirip
  devam eden doğrulamayı geçersiz kılar ve iki dalın kuyruğunu uzatır.
- Kısa aralıklarla çok sayıda push yapma; ilgili commitleri biriktirip tek seferde
  gönder. Otomasyon son commit'i 5 dakikadan yeni dalı beklemeye alır.
- Başka ajanın branch'ini sıfırlama; çakışmayı tek tarafın kodunu seçerek çözme.
  Force push ve yıkıcı Git işlemleri için açık kullanıcı onayı gerekir.
- Ortak dosyada çalışma gerekiyorsa kendi branch'inde kal ve entegrasyon
  riskini raporla. Sahiplik görev bitince kalıcı olarak devam etmez.

## Doğrulama ve teslim

- Sözdizimini, ilgili testleri, bağımlı modüllerdeki regresyonları ve Git diff'ini
  kontrol et. Beklenmeyen dosya değişikliklerini bildir.
- Qt testlerinde gerekirse `packaging/run_windows_tests.py` ile sınırlı
  büyüklükte ayrı test süreçleri kullan. Çöken veya başarısız grupları gizleme.
- Kontrollü Python/COM sınır testleri ve C# derlemesi canlı SolidWorks testi
  değildir. Windows/SolidWorks/ODA gerektiren, çalıştırılamayan alanları belirt.
- Teslimde düzeltmeleri, değişen dosyaları ve amaçlarını, branch/commit'i,
  komitlenmemiş durumu, diğer ajanla çakışma/API risklerini, entegrasyon
  gereksinimini ve test sonuçlarını bildir. Test edilmemiş başarı iddiasında bulunma.

Öncelik: kullanıcı verisi ve mevcut kodun korunması, ajan çakışmalarının
önlenmesi, mimari uyumluluk, doğruluk ve kontrollü entegrasyon.
