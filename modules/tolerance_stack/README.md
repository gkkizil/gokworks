# Tolerans yığılması

Manuel veya SolidWorks teknik resim ölçülerinden fonksiyonel 1D ölçü zinciri.

- [ui.py](ui.py), [ui_widgets.py](ui_widgets.py), [ui_dialogs.py](ui_dialogs.py): Qt çalışma alanı.
- [models.py](models.py), [chain.py](chain.py): veri modeli ve zincir doğrulaması.
- [calculator.py](calculator.py), [monte_carlo.py](monte_carlo.py): Worst-Case, RSS ve simülasyon.
- [solidworks_reader.py](solidworks_reader.py), [com.py](com.py): teknik resim ölçülerini okuma.
- [drawing_writer.py](drawing_writer.py): ayrı analiz anotasyonları.
- [storage.py](storage.py), [report.py](report.py): proje kaydı ve raporlar.
- [extensions.py](extensions.py): ilerideki doğrulanmış geometrik analizler için genişletme noktası.
- [tests/](tests), [examples/](examples): regresyonlar ve örnek analiz/PDF/Excel.
- [Kullanım, matematik ve gerçek SolidWorks kabul adımları](../../docs/tolerance-stack.md).

Test: `python -m pytest modules/tolerance_stack/tests`.
