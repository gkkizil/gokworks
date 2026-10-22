# Depo düzeni

Güncel kaynak geliştirmesi `main` dalında yapılır. Paylaşım için `release`
dalı kullanılır; `main` güncellemeleri yalnız açık yayın isteğiyle bu dala
aktarılır. [Yayın düzeni](releases.md). Yedek depo bu düzenlemenin parçası
değildir. Klasör taşıma dosya geçmişini korur; hesaplama ve CAD algoritmaları
yeniden yazılmaz.

```text
gokworks/
├── main.py          # Uygulama, PDF işçisi ve öz denetim girişleri
├── modules/         # Her özellik: kod + ui.py + tests + örnekler
├── gui_qt/          # Ortak Qt kabuğu, tema, bileşenler ve iş yönetimi
├── shared/          # JSON ayarları ve paylaşılan Python yardımcıları
├── solidworks/      # Ortak COM bağlantısı, tanılama ve süreç yönetimi
├── assets/          # Gömülü logo ve uygulama ikonu
├── tests/           # Ortak altyapı, uygulama ve paketleme testleri
├── docs/            # Kullanım, doğrulama raporları ve ekran görüntüleri
├── packaging/       # Windows EXE üretimi ve lisans bildirimleri
├── sources/         # Kaynak/telif envanteri
└── .github/         # GitHub Actions
```

[Modül dizini ve tüm ekran girişleri](../modules/README.md).

## Bir modül üzerinde çalışma

Her modülün `README.md` dosyası ilgili motorları ve sınırlarını açıklar.
Arayüz `modules/<modül>/ui.py`, testler `modules/<modül>/tests/` altındadır.
Yalnız nesting/tolerans yığılması gibi kapsamlı ekranlar ek `ui_widgets.py`
ve `ui_dialogs.py` dosyalarına ayrılır. PDF ve DXF/DWG ekranlarının ortak
düzeni `gui_qt/export.py` içindedir; modüller kendi `ui.py` girişine sahiptir.
Ortak hesap ekranı `gui_qt/calculations.py` içindedir.

`modules/profile_cutting/` 1D stok planı ve Weldments taramasını içerir.
`solidworks.py` COM adaptörü, `scanner.py` tarama servisi, `optimizer.py` saf
hesap motorudur; mevcut sac nesting paketini değiştirmez.

```bash
python main.py
python -m pytest
python -m pytest modules/nesting/tests
python -m pytest modules/tolerance_stack/tests
QT_QPA_PLATFORM=offscreen python main.py --self-check /tmp/gokworks-check.json
```

`pytest.ini` hem `tests/` hem `modules/` altını toplar. `tests/support/`, tüm
CAD sınır testlerinin ortak sahte nesnelerini içerir. `tests/legacy_tk/` ve
eski bağımsız K/R denemesi güncel regresyon grubundan ayrı tutulur.

## Eski yolların karşılıkları

| Önceki konum | Güncel konum |
| --- | --- |
| `pdf/`, `bolt/`, `nesting/` vb. | `modules/pdf/`, `modules/bolt/`, `modules/nesting/` vb. |
| `gui_qt/pages/nesting.py` | `modules/nesting/ui.py` |
| `gui_qt/pages/kr.py` | `modules/k_factor/ui.py` |
| `gui_qt/pages/stack_dialogs.py` | `modules/tolerance_stack/ui_dialogs.py` |
| `gui_qt/tooling_diagram.py` | `modules/k_factor/tooling_diagram.py` |
| `gui_qt/torque_diagram.py` | `modules/bolt_torque/diagram.py` |
| `tests/test_nesting*.py` | `modules/nesting/tests/test_nesting*.py` |
| `tests/test_bom.py` | `modules/bom/tests/test_bom.py` |
| `pdf/settings.py` | `shared/settings.py` |
| `gui/assets/` | `assets/` |
| `gui/theme.py` vb. | `shared/theme.py` vb. |

İçe aktarma örneği: `from modules.bolt_torque.rules import calculate`.
Eski kök modül adları için ikinci kod kopyası veya import alias'ı tutulmaz.
Geçmiş JSON günlükleri ve kaynak envanterleri üretildikleri sürümün yollarını
içerebilir; tarihî kanıtlar değiştirilmez.

## Paketleme

Windows üzerinde mevcut `python packaging/build_windows.py` komutu korunur.
Paket; `assets/`, `modules/iso_fits/tables.json` ve
`modules/naming/interop/PackAndGoHost.cs` dosyalarını çalışma zamanındaki
gerçek konumlarına gömer. GitHub Actions test yolları ve bağlama kontrolünün
çıktı konumu yeni düzene göre güncellenmiştir. Ayrı bir bağımlılık eklenmez.

## Doğrulama

Linux / Qt offscreen ortamında **911 test ve 878 alt senaryo geçti**;
Windows veya canlı SolidWorks gerektiren **7 test atlandı**. 12 ekranlı
uygulama öz denetimi iki tema ve dört çözünürlükte geçti. Modül konumları,
bağımsız hesap importları, PDF işçisi başlangıç yolu ve hem onefile hem onedir
paket kaynak hedefleri ayrıca kontrol edildi. Windows EXE üretimi bu Linux
kontrolünde çalıştırılmadı.

62 motor/çizim dosyasının AST karşılaştırması, importlar dışında aynı kodu
koruduğunu doğruladı. PDF süreç dosyasındaki ek değişiklik, `main.py` dosyasına
giden üst klasör sayısıdır. Hesaplama ve CAD algoritmaları değiştirilmedi.

[Test özeti](repository-organization/checks.json) ·
[Uygulama öz denetimi](repository-organization/selfcheck.json) ·
[Motor karşılaştırması](repository-organization/engine-audit.json).
