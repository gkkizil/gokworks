# Sac Açınımı — arayüz

Menü: **Üretim → Sac Açınımı**. Akış: şekil → ölçü → önizleme → açınım → çıktı.

Bu klasör yalnız arayüzdür. Geometri, doğrulama, açınım, kütle/maliyet,
DXF/PDF/STEP/ZIP, proje dosyası ve nesting dönüşümü `core.unfolding`
servisinindir (sözleşme: [docs/unfolding/contract_v1.md](../../docs/unfolding/contract_v1.md)).
`service.py` yalnız dönüştürür: form → `UnfoldRequest`, sonuç → ekran verisi;
dışa aktarma ve proje her zaman ekrandaki sonucun kendisiyle (`expected_revision`,
`expected_input_hash`) yapılır. Şekil kategorisi, atölye adları, küçük resim ve
şema üzerindeki ölçü yerleri dışında sabit katalog tutulmaz; alanlar, sınırlar
ve varsayılanlar `get_schema` sonucudur.

## Ekran

- **Sol:** şekil galerisi (arama: kare yuvarlak, redüksiyon, kurtağzı…; kategori),
  varyant, son kullanılanlar. Motorda olmayan aileler "Planlanan" olarak görünür, seçilemez.
- **Orta:** ölçülü şema — her ölçü çizim üzerinde düzenlenir ve formla eşzamanlıdır;
  ölçüler, birim (mm/inch, fiziksel parça değişmez), ölçü yüzeyi (iç/orta/dış şemasıyla),
  malzeme, birleşim (alın/bindirme + pay), dikiş başlangıç açısı, çevresel bölme, fiyat.
  "1,2" ve "1.2" kabul edilir; belirsiz binlik ayırıcı reddedilir. Enter hesaplar, Esc geri alır.
  Servisin alan hataları ilgili alanın altına yazılır.
- **Sağ:** durum + özet şeridi (açınım ölçüsü, alan, kesim boyu, kütle, parça);
  3D önizleme ağı ile servisin ön/üst tel görünüşleri; açınım (gerçek çizgi/yay,
  kesim/delik/büküm/yardımcı/dikiş/ölçü katmanları, sığdır, 1:1, servis
  geometrisinden ölçüm, seçili parçaya odak).
- **Alt:** parçalar (alan, çevreleyen, kesim boyu, kütle, maliyet), uyarılar,
  proje parçaları (adet, çoğalt, kaldır, aç/kaydet, projeyi ZIP'e aktar) ve
  çıktı düğmeleri. Düğmeler servisin `capabilities` bilgisine göre açılır; STEP
  orta yüzey B-Rep'tir, kalınlıklı katı değildir.
- **Nesting'e gönder:** `to_nesting_parts` ile kesim konturu, delikler, kalınlık,
  adet ve özgün DXF yayları Nesting projesine eklenir; malzeme Nesting'deki bir
  malzeme kimliğiyle eşleştirilir.

Hesaplar ve dosya üretimi `JobManager` ile arka planda çalışır. Durumlar: eksik/hatalı
girdi, hesaplanıyor, geçerli, uyarılı, hata, iptal, "Ölçüler değişti — yeniden
hesaplanmalı". Geç gelen sonuç `request_id`/`revision` ile reddedilir; eski sonuçla
çıktı, projeye ekleme ve nesting aktarımı yapılmaz.

Bu sürümde yok: açılma/kapanma animasyonu (çekirdek yüzey eşleme sözleşmesi
gerekiyor), çizimden ölçü alma (AI/OCR adaptörü yok), 3D'de tıklayarak parça seçimi.

Testler: `tests/test_unfold_gui.py` (gerçek servis).
