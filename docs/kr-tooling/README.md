# Canlı abkant takım kesiti

GOKWORKS → **K faktörü / yarıçap → Hesap yardımı**.

1. **Düz bıçak / tek V** — üst bıçak uç R=4 mm, üst açı=67°, alt açı=60°,
   t=2 mm ve otomatik V=16 mm. [Arşiv: Koyu tema](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/kr-tooling/straight-single-v-dark.png).
2. **Kaz boynu / çift V** — R=1,5 mm, V=24 mm, takım açıları=60°, t=3 mm,
   β=110° ve ölçülmüş sac iç R=4,5 mm. [Arşiv: Koyu tema](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/kr-tooling/gooseneck-double-v-dark.png)
   · [Arşiv: Açık tema](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/kr-tooling/gooseneck-double-v-light.png).
3. **Dar pencere** — aynı kontroller, çizim ve sonuçlar tek sütunda;
   [Arşiv: 1024 × 700](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/kr-tooling/compact-dark.png).

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
