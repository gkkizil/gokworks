# Sac açınımı — arayüz istekleri (Claude → Codex)

Arayüz `modules/sheet_unfolding/` altında, `core.unfolding.UnfoldService` ile
çalışıyor (sözleşme v1). Bağlantı `modules/sheet_unfolding/service.py` içinde.
Aşağıdakiler ekranın şu an yerel bir sunum tablosuyla çözdüğü veya hiç
gösteremediği konulardır; çekirdekte bir alan olarak gelirse arayüz onu kullanır.

> Motor 1.1.0 ile karşılandı: 1 (kategori/varyant etiketi; kaynak modellerde
> `ShapeSummary.category/variant_labels`) ve 2 (eski planlanan ailelerin hepsi
> artık çalışıyor). Arayüz yalnız kategori küçük resmi ve arama eş anlamlılarını
> ekliyor. Açık kalan yeni istek:
>
> 8. **Kaynak modeller için kroki:** 191 kaynak modelin `ShapeSchema.sketch` /
>    `dimension_id` konumları yok; arayüz kroki alanını gizleyip sembolleri form
>    etiketinde gösteriyor. Kaynak `thumbPng` bilgisi için lisanslı/bağımsız bir
>    küçük resim veya basit giriş krokisi gelirse ölçü üzerinde düzenleme açılır.
> 9. **Örnek varsayılanı:** bazı kaynak varsayılanları doğrulamadan geçip hesapta
>    hata veriyor (ör. `pipe-to-oblique-cone-vertical-trunk`); arayüz "Çalışan
>    örneği yükle" düğmesi sunuyor. Şemada `example_available` / örnek isteği
>    alanı olursa JSON dosya yolu yerine o kullanılır.

1. **Şekil sunumu:** `ShapeSummary` içinde kategori, atölye arama adları
   (kurtağzı, pantolon…), küçük önizleme çizgileri ve varyant başlıkları
   (ör. `{"variant_id": "frustum", "label": "Kesik koni"}`). Şu an arayüzdeki
   `PRESENTATION` tablosunda.
2. **Planlanan aileler:** `list_shapes(include_planned=True)` veya ayrı bir
   `planned` listesi. Arayüz şimdilik branşman, pantolon, eğik koni, bombe ve
   helezonu kendi listesinden "Planlanan" olarak (seçilemez) gösteriyor.
3. **Giriş şeması çizimi:** `ShapeSchema.sketch` (giriş ölçülerini gösteren
   basit ön görünüş) ve her `dimension_id` için `start/end` konumu:
   `{"dimension_id": "diameter", "start": [-150, -30], "end": [150, -30]}`.
   Şu an arayüzde şekil başına elle yerleştirilmiş şablon var.
4. **Malzeme listesi:** `materials() -> [{name, density_kg_m3}]`; arayüz şimdilik
   uygulamanın ağırlık modülündeki yoğunluk tablosunu kullanıyor.
5. **Açılma animasyonu:** `mappings` her parçada var; animasyon için parça
   başına sıralı yüzey eşlemesi (`fold_steps` / ara konumlar) gerekiyor.
6. **3D seçimi:** mesh üçgenlerinde `part_id` (veya parça başına ayrı mesh
   olduğunun garanti edilmesi) ile 3D'de tıklayarak parça seçimi.
7. **İptal ayrıntısı:** `UnfoldCancelled` mesajı Türkçe; arayüz bunu "İptal edildi"
   olarak gösteriyor, ek alan gerekmiyor.
