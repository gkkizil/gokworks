# Genel arayüz iyileştirmeleri

Ortak Qt arayüzündeki tema, başlık, boşluk, gezinme ve sonuç geri bildirimleri
güncellendi. Hesaplama motorları ve CAD üretim kodu bu değişikliğin kapsamı dışındadır.
Uygulamanın önceki nötr gri renk paleti korunur.

- Araç aramasında `Ctrl+K` odağı açar, `Enter` ilk eşleşmeyi açar,
  `↓` ilk eşleşmeye odaklanır ve `Esc` aramayı temizler.
- Sonuç bulunamadığında aramayı temizleme seçeneği görünür. Seçilen modül,
  dar pencerelerde menünün görünür bölümüne kaydırılır.
- Uzun çalışma alanı ve durum metinleri düğmelere yer bırakacak şekilde
  kısaltılır; tam metin araç ipucunda korunur.
- Sonuç tabloları boş kaynak, devam eden işlem ve eşleşmeyen filtre durumlarını
  ayırır. Filtre temizleme verileri silmez. 3D Dönüştürücü'nün özel sonuç modeli
  ve sayacı da aynı davranışı kullanır.
- Sonuç ayrıntısı için `Enter` yalnızca sonuç tablosu odaktayken çalışır.

Görüntüler çalışan PySide6 uygulamasından, Linux üzerinde Qt `offscreen`
platformuyla alınmıştır:

- [Koyu tema](dark.png)
- [Açık tema](light.png)
- [820 × 560 pencere](compact.png)
- [Araç bulunamadı](search-empty.png)
- [Filtreye uyan sonuç yok](filtered-results.png)
- [Dişli ekranı · gri tema](gear-gray.png)

İlgili testler: `tests/test_fusion_workbench.py` ve
`tests/test_compact_workspaces_gui.py` için 29 test; `tests/test_shell_feedback.py`
için 5 test başarılı. `git diff --check` ve değişen Python dosyalarının derleme
kontrolü başarılıdır. Bu çalışma için Windows EXE derlemesi veya canlı
SOLIDWORKS testi yapılmadı.

Görüntüleri yeniden almak için:

```bash
QT_QPA_PLATFORM=offscreen python docs/report-tools/capture_general_ui.py docs/screenshots/general-ui
```
