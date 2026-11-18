# Otomatik Teknik Resim: gerçek SolidWorks'te uçtan uca düzeltme (yerel oturum devri)

Bu dosya, kullanıcının **Windows + lisanslı SolidWorks** kurulu bilgisayarında
açılacak Claude Code oturumu içindir. Bulut oturumu SolidWorks'e erişemediği için
modül şimdiye kadar yalnız COM taklitleriyle (fake) test edildi. Gerçek
SolidWorks'te hâlâ hata veriyor. Amaç, modülü gerçek SolidWorks'te baştan sona
çalıştırıp her hatayı yerinde görerek düzeltmektir.

## Kurallar (kullanıcının sabit kuralları)

- Kullanıcıyla **Türkçe** konuş.
- Depo: `gkkizil/gokworks`. Çalışma dalı **`agent/claude`**, başka dala push yok.
  Push öncesi testleri koş ve **kullanıcıya sor**. Force push ve reset izinsiz yapılmaz.
- `agent/claude`, 3 Windows doğrulama parçası geçince otomasyonla
  (`.github/workflows/agent-integration.yml`) main'e birleşir.
- main'i dala yalnız gerçek çakışma varsa birleştir. Codex'in değişikliklerini geri alma.
- Kullanıcı istemedikçe EXE derleme.
- **Kullanıcının SolidWorks kaynak dosyalarını (SLDPRT/SLDASM) asla kaydetme ve
  değiştirme.** Denemeleri kopyalar üzerinde yap.
- `gokworks-solid` deposu ayrı bir projedir (SolidWorks eklentisi); ona dokunma.
- Commit sonuna şu satırları ekle:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  ```
  Commit mesajlarına model kimliği yazma.
- Raporlarda gerçek SolidWorks sonucu, COM taklidi testleri ve arayüz testleri
  ayrı ayrı yazılır. Mock sonuç CAD doğrulaması diye sunulmaz.

## Modül haritası (`modules/automatic_drawing/`)

| Dosya | Görev |
|---|---|
| `pipeline.py` | Kuyruk ve aşamalar. `generate()` tek COM oturumu açar; `generate_one()` aşamaları sırayla çalıştırır. |
| `solidworks.py` | `Session`: SolidWorks'e bağlanma (`GetActiveObject`), kaynak açma, konfigürasyon ve model analizi. |
| `native.py` | `NativeDrawing`: resim oluşturma (`create`/`setup` pafta, `create_views`, ölçü, merkez işareti, `validate`, `save`, `verify_saved`). |
| `sheetmetal.py` | Sac gövdeleri ve açınım konfigürasyonları. |
| `manufacturing.py` | BOM tablosu ve adetler. |
| `layout.py`, `rules.py` | Ölçek, pafta ve görünüş yerleşimi. Saf Python, COM'suz. |
| `outputs.py` | Dosya adları, atomik yayın, rapor. |
| `live_acceptance.py` | **Gerçek SolidWorks kabul betiği** (8 senaryo). Fixture listesi: `docs/automatic-drawing/LIVE_ACCEPTANCE.md`. |
| `tests/test_live_solidworks.py` | Ortam değişkenleriyle açılan canlı testler. |

API imza referansı: `docs/automatic-drawing/SOLIDWORKS_API_REFERENCES.md`. Bilinen
sınırlar: `docs/automatic-drawing/KNOWN_LIMITATIONS.md`.

## Kullanıcının gerçek SolidWorks'te gördüğü hatalar (sırayla)

1. `Pafta / şablon ayarı SolidWorks tarafından reddedildi` (`SetupSheet6` False döndü).
   Düzeltme denendi: tam sayılı ölçek, `Default` özellik görünümü, son çare olarak
   sayfa biçimsiz kurulum. **Kökü çözülmedi:** her denemede
   `Pafta ayarı ilk denemede reddedildi; "no_format" ayarıyla kuruldu. Şablonun sayfa
   biçimi (antet) uygulanamadı: *.drt` uyarısı çıkıyor. `GetTemplateName`, `*.drt`
   adında yer tutucu döndürüyor (`native.py` `setup()`, satır ~96). Antet hiç
   uygulanmıyor.
2. `Görünüş oluşturulamadı: main`. Türkçe SolidWorks standart görünüş adlarını
   `*Ön`, `*Üst`, `*İzometrik` diye verir. Düzeltme: İngilizce ad, sonra Türkçe ad,
   sonra `GetModelViewNames` listesi denenir. **Gerçekte doğrulanmadı.**
3. `GetCenterMarkCount2: (-2147352561, 'Parametre seçime bağlı değil.')`. Bu
   çağrının out parametresi var. Düzeltme yapıldı; **gerçekte doğrulanmadı.**
4. Uyarı: `Aktarılabilir model ölçüsü bulunamadı`. Test bloğunda modele işaretli
   ölçü yoktu; beklenebilir, ama `InsertModelAnnotations` çağrısı gözden geçirilmeli.

Kullanıcının test dosyası:
`GOKWORKS-verification-block.SLDPRT`
(gokworks-solid deposunun `artifacts/` klasöründe; kopyalayıp kullan).

## Yapılacaklar (sırayla)

1. **Ortam:** `python -m pip install -r requirements.txt` (pywin32 dahil).
   SolidWorks'ü aç. Çalıştığını şöyle doğrula:
   `python -c "import win32com.client as w; print(w.GetActiveObject('SldWorks.Application').RevisionNumber())"`.
2. **Önce küçük bir deneme betiği:** Modülü kullanmadan, `win32com` ile adım adım
   ilerle. Her adımda dönen değeri ve `GetLastError` / hata kodunu yazdır:
   - `NewDocument(DRWDOT, paper, w, h)`
   - `GetTemplateName` / `GetProperties2`
   - `SetupSheet6`
   - `CreateDrawViewFromModelView3`
   - `CreateUnfoldedViewAt3`
   - `InsertModelAnnotations3`
   - merkez işaretleri
   - `SaveAs3`

   Kullanılacak DRWDOT: SolidWorks'ün varsayılan resim şablonu
   (`GetUserPreferenceStringValue(swDefaultTemplateDrawing)`). Sayfa biçimi
   klasörü: `swFileLocationsSheetFormat`. Hangi çağrının neden reddedildiğini
   gerçek verilerle belirle.
3. **Antet kökü:** Şablonda sayfa biçimi yoksa (`*.drt`), kullanıcının SolidWorks
   sayfa biçimi klasöründen kağıda uygun standart `.slddrt` dosyasını
   (ör. `a3 - iso.slddrt`) bulup `SetupSheet6` ile ver. Seçilen dosya rapora yazılsın.
4. **Modülü uygulamadan çalıştır** (`python main.py` → Üretim → Otomatik Teknik
   Resim) ve şu komutu koş:
   `python -m modules.automatic_drawing.live_acceptance --report kabul.json`.
   Ortam değişkenleri: `docs/automatic-drawing/LIVE_ACCEPTANCE.md`. Önce en az 1
   (kademeli mil veya blok) ve 2 (delikli plaka) numaralı senaryolar geçsin, sonra
   sac ve montaj.
5. Bulunan her hata için:
   - kök nedeni gerçek dönüş değeriyle göster;
   - hedefli düzeltme yap;
   - COM taklidi testini (`modules/automatic_drawing/tests/`) gerçekte görülen
     davranışa göre güncelle veya yeni test ekle;
   - kaynak dosyanın değişmediğini SHA256 ile doğrula.
6. Bitince şunlar ayrı ayrı raporlanır:
   - gerçek SolidWorks'te geçen ve kalan senaryolar (SolidWorks sürümü/revizyonu ile);
   - üretilen SLDDRW/PDF yolları;
   - taklit COM testi sonuçları;
   - arayüz testleri;
   - değişen dosyalar.

## Mevcut testler

```bat
python -m pytest modules/automatic_drawing -q
python -m pytest tests/test_unsaved_projects.py tests/test_tool_coverage_display.py -q
```

Tam paket uzun sürer (~30 dk). Push öncesi en azından `modules/automatic_drawing`
ve `tests/` klasörünü koş.
