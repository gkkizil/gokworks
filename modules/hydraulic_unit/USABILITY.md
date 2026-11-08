# Hidrolik ekranı — anlaşılabilirlik iyileştirmesi

8 Kasım 2026; taban `9684677`, çalışma dalı `agent/codex`.
Claude'un mevcut ekranı korunarak akış, açıklamalar ve hata düzeltme davranışı
iyileştirildi. Hesap çekirdeği, proje şeması ve rapor motoru değişmedi.

## Kullanıcı akışı

1. **Silindirleri tanımlama — iyileştirildi.** İlk görünümde ad, çaplar,
   strok ve başlangıç konumu bulunur. Verim/burkulma sütunları isteğe bağlı
   açılır. Seçili silindirin bağımsız hesabı ayrı bir açılır bölümde ve çevrimi
   değiştirmediği açıklanır. Hücrelerin çift tıklamayla düzenlendiği yazılıdır.
2. **Çevrimi kurma — iyileştirildi.** Seçili hareket için hız/süre menüsü
   karşı alanı temizler; doğru giriş hücresini açar. Bekleme ve boşta
   türlerinde kullanılmayan alanlar düzenlenmez ve hesabı engellemez.
   Geçersiz yarım değer varken ekleme/silme/sıralama komutları girdiyi silmez.
3. **Ayar ve sonuçları yorumlama — iyileştirildi.** Yedi sekmenin kısa adları,
   adım açıklamaları ve ileri/geri düğmeleri vardır. Temel ve gelişmiş ayarlar
   ayrılır. Otomatik seçilen değerlerin boş bırakılacağı görünür. Pompa kontrol
   türüne uymayan alanlar ve kapalı akümülatör girdileri pasiftir.
4. **Uyarıyı çözme — iyileştirildi.** Kritik/uyarı metnine işlem önerisi
   eklenir; ilgili sekmeye/alandan devam edilebilir. Uyarıya tıklamak geçerli
   girdiyi kırmızı hataya dönüştürmez. Hatalı gizli gelişmiş alan otomatik açılır.
   Sayısal sonuçtan farklı olarak kullanıcıya üretim onayı verilmez.
5. **Rapor öncesi kontrol — korundu ve netleştirildi.** Girdi değiştiği anda
   eski sonuçla kayıt/rapor kapatılır; 300 ms debounce sonunda tekrar açılır.
   Akümülatör sonuçları İngilizce SI alanları yerine Türkçe litre ve gösterge
   bar olarak sunulur. Senaryo sonucu gerçek performansla karıştırılmaz.

## Görsel ve erişim kontrolleri

Bu görevde yeni Qt ekran görüntüleri alınıp dosyadan açılarak incelendi:

- Önce: `/tmp/hydraulic-ux-before-start.png`, `...-accumulator.png`.
- Sonra: `/tmp/hydraulic-ux-delivery-start.png`, `...-cycle.png`,
  `...-accumulator.png`, `...-light.png`, `...-small.png`.
- 1366×900 koyu/açık tema ve 1024×700 dar pencere incelendi. Dar alanda
  iki ayar grubu alt alta dizilir; sayısal alanlar en az 100 px genişliktedir.
  Geniş mühendislik tablolarında yatay kaydırma korunur; küçük pencerede son
  sekmelere önceki/sonraki düğmeleriyle de erişilir.
- Uyarılar renk dışında başlık ve açıklama taşır; metinler dar panelde
  satıra sarılır. Adım, giriş yöntemi ve hata yönlendirmesi Qt testleriyle
  kontrol edilir. Ekran görüntüleri tam erişilebilirlik/ekran okuyucu onayı değildir.

## Doğrulama

```sh
QT_QPA_PLATFORM=offscreen python -m pytest tests/hydraulic_unit modules/hydraulic_unit/tests tests/test_lazy_pages_gui.py tests/test_page_transition.py -q
QT_QPA_PLATFORM=offscreen python main.py --self-check /tmp/hydraulic-ux-startup.json
```

Son birleşik test koşusunda **109 test geçti**. Mevcut 20 modülün, iki temanın ve çözünürlük matrisinin Linux offscreen
açılış kontrolü geçti. Ruff E9/F63/F7/F82/F401 ve Git whitespace kontrolü
kullanılır. Canlı Windows/SolidWorks testi yapılmadı; Windows CI ayrı doğrulamadır.

Değişen kod: `ui.py` (görünüm/davranış), `guidance.py` (kullanıcı metinleri),
`tests/test_ui.py` (akış ve regresyon testleri). Diğer modüllere dokunulmadı.
