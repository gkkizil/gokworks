# Canlı abkant takım kesiti

GOKWORKS → **K faktörü / yarıçap → Hesap yardımı**.

1. **Düz bıçak / tek V** — üst bıçak uç R=4 mm, üst açı=67°, alt açı=60°,
   t=2 mm ve otomatik V=16 mm. [Koyu tema](straight-single-v-dark.png).
2. **Kaz boynu / çift V** — R=1,5 mm, V=24 mm, takım açıları=60°, t=3 mm,
   β=110° ve ölçülmüş sac iç R=4,5 mm. [Koyu tema](gooseneck-double-v-dark.png)
   · [Açık tema](gooseneck-double-v-light.png).
3. **Dar pencere** — aynı kontroller, çizim ve sonuçlar tek sütunda;
   [1024 × 700](compact-dark.png).

Ekranlar gerçek PySide6 arayüzünden `docs/report-tools/capture_kr_tooling.py`
ile alınır. Girişler ve hesaplanan değerler [captures.json](captures.json)
içindedir. Şekiller şematik, gövde boyutları temsilidir. Rp ile sac iç R'si
ayrı gösterilir; ikinci V ağzına ölçü atanmaz.

Kontrol kapsamı: canlı sayısal girişler ve otomatik V, farklı takım profilleri,
BA kalibrasyonu, geçersiz girdide eski çizimin kaldırılması, tercihlerin tekrar
açılışta korunması, iki tema ve geniş/dar/geniş pencere geçişi. Manuel K/R
satırları hesap yardımından etkilenmez. SolidWorks bağlantısı kullanılmaz.

Bu değişiklik tek başına EXE derlemesini başlatmaz. Sonraki kullanıcı talebinde
üretilen EXE'nin paket kontrolü de bu takım profillerini ve ölçülerini doğrular.
