# Şekillendirme doğrulaması — 6 Kasım 2026

Ortam: Python 3.13.5, PySide6/Qt 6.10.3, Linux/offscreen. Yeni bağımlılık yok.
Kaynak dal: `agent/codex-forming-compensation`; başlangıç main `6f75e4e`.
Makine tarafından okunabilen kanıt: [forming_validation.json](forming_validation.json).

## Test sonuçları

| Çalıştırma | Sonuç |
|---|---|
| Sac Açınımı çekirdeği + gerçek GUI + mevcut K/R testleri | 1152 test ve 160 alt test geçti; 1 canlı ODA testi atlandı |
| Son giriş/çıktı değişiklikleri sonrası kaynak modelleri, doğrulama ve yeni mekanik entegrasyon | 853 geçti, 1 canlı ODA testi atlandı |
| Son önbellek kimliği düzeltmesi, mesh yakınsaması ve eksik referans noktası kontrolleri dahil yeni testler | 89 geçti, 1 canlı ODA testi atlandı |
| Son arayüz etiketleri ve mevcut Sac Açınımı GUI regresyonu | 40 geçti |
| Ana uygulama self-check | 19 modül; iki tema ve dört çözünürlük; passed |
| Sözdizimi / kritik statik kontrol / git diff --check | Geçti |

Bu üç test sayısı aynı testleri kısmen içerir; toplanıp benzersiz test sayısı
olarak sunulmaz. Geniş testten sonra bulunan giriş kontrolleri ve nominal
cache kimliği düzeltmesi ayrıca belirtilen son testlerle doğrulanmıştır.

Geniş komut:

```sh
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=.:tests:/workspace/gokworks/.cache/runtime-updated \
/workspace/.cloud-setup/qt-venv/bin/python packaging/run_windows_tests.py \
    tests/unfolding modules/sheet_unfolding/tests modules/k_factor/tests
```

Çalıştırıcı adındaki Windows, testlerin Windows'ta çalıştırıldığı anlamına
gelmez; burada Qt/native testler Linux'ta ayrı süreçlere bölünmüştür.
Yerel ayrıntı dosyaları `windows-tests.xml`, `windows-tests.log` ve
`.cache/forming-evidence/` içindedir. Yeni statik kontroller E9, F63, F7,
F82, F401 sınıflarını kapsar.

## Bağımsız referanslar ve kabul edilen çıktı

- 90° BA/BD/OSSB, farklı R/t ve K için bağımsız formüller.
- DC01 1 mm, S235 2 mm, AISI 304 3 mm senaryoları: açık **sentetik** E,
  akma ve pekleşme girdileri; üretici sertifikası varsayılmadı.
- Kesit momenti bağımsız 20000 dilimli gerilme integraliyle karşılaştırıldı.
- R/t ve dayanım değişince fazla büküm değişiyor; sabit derece eklenmiyor.
- BA/BD ve kupon yöntemleri, iç/dış/teğet ölçü ayrımı, açı türü,
  bilineer hücre aralığı ve proses/takım/hadde bağlamı doğrulandı.
- Dairesel, oval ve yatık oval segmentlerde gerçek parça adedi ve hedef 3D
  geometri korundu. Oval düz kenarlarda genel ölçek uygulanmadığı sınandı.
- Konik ve genel loft'ta doğrulanmamış K dönüşümü reddedildi; nominal
  sonuç korunurken telafili çıktı başarı sayılmadı.
- Eğri fanın mesh optimizasyonu enerjiyi azalttı; kalan geometrik deformasyon
  sıfırlanmış gibi gösterilmedi. Silindir mesh hata yakınsaması bağımsız
  yay/kord formülüyle 8/16/32 bölmede kontrol edildi.
- Eksik referans noktası `NOT_EVALUATED`; tüm ölçülerin eşleştiği söylenmedi.
- Nominal cache kopyasının yeni istek kimliği ve nominal JSON çıktısı sınandı.
- DXF nominal/telafili/karşılaştırma dosyaları ezdxf ile geri açıldı;
  1:1 mm, kapalı kontur, alan/boyut ve işaretli büküm katmanları denetlendi.
- PDF QtPdf ile geri açıldı; Türkçe içerik, hesap boyları, kaynak ve uyarılar
  denetlendi; sayfa render edildi ve yerleşim görsel olarak incelendi.
- Yeni GUI gerçek motor ve mevcut iş yöneticisiyle test edildi; hatalı
  mekanik girdide güncelmiş gibi çıktı alınması engellendi. Proje/profile
  aç/kaydet ve önceki JSON dosyaları kontrol edildi.
- DWG sınır testleri: dönüştürücü eksikliği, bozuk geri okuma ve değişmiş
  ölçüler başarı sayılmadı. Bu testler gerçek DWG üretimi kanıtı değildir.

## Açık sınırlar ve yapılmayan kabul testleri

Canlı Windows/SolidWorks/ODA ve Windows EXE kabulü yapılmadı. Kurulu ODA
bulunmadığı için canlı DXF→DWG→DXF testi **atlandı**. Sahte DWG veya
telafili STEP oluşturulmadı; STEP mevcut nominal hedef yüzeyi korur.

Yayımlanmış veya kullanıcı üretiminden doğrulanmış fiziksel yaylanma veri seti
bu görevde sağlanmadı. Analitik sonuçlar yalnız sayısal tutarlılıkla sınandı.
Kalibrasyon testlerindeki ölçümler sentetiktir. Gerçek takım, malzeme ve
üretim doğruluğu onayı verilmedi.

Koni/genel loft için genel K telafisi, delikli yamada mesh optimizasyonu,
plastik incelme/hasar, takım/parça çarpışması, büküm sırası ve makine kapasitesi
tamamlanmış özellik değildir. İlgili sonuçlar `NOT_EVALUATED` taşır.

## Dosya kapsamı ve ajan uyumu

- Yeni hesap dosyaları: `core/unfolding/forming/` içindeki mechanics,
  profiles, deformation, integration, reference, reporting ve storage.
- Mevcut çekirdekte sözleşme/normalizasyon/cache, profil kaydı, daire/oval
  üretim parametresi, DXF/PDF/ZIP, proje kayıt ve CLI entegrasyonu.
- Yeni opsiyonel `core/unfolding/dwg.py`: bağımsız ODA ve geri okuma doğrulaması.
- Arayüzde `modules/sheet_unfolding/forming.py`, servis DTO'ları, panel,
  sonuç sekmesi, nominal katmanı ve çıktı seçimi. Mevcut galeri testi yeni
  yerel kategoriyi kapsayacak şekilde güncellendi.
- Mevcut K/R, dişli, DFM, nesting ve SolidWorks davranışları değiştirilmedi.
  Başka ajanın worktree'si veya commit edilmemiş değişiklikleri ezilmedi.
- Claude ile olası entegrasyon noktaları: `models.py`, `service.py`,
  `modules/sheet_unfolding/ui.py`, adaptör ve çizim katmanları.
  Güncel [CLAUDE_HANDOFF.md](CLAUDE_HANDOFF.md) sözleşmesini koruyun.
- `requirements.txt`, `AGENTS.md`, yayın ayarları ve CI dosyaları değiştirilmedi.

Yeni hesapların matematiksel/teknik ayrıntıları ve kaynak sınırları
[FORMING.md](FORMING.md) içindedir.
