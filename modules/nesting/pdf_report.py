"""Print-only document layout; application palettes never define PDF colors."""

from html import escape
import re


def _text(value):
    # Qt's rich-text tables do not break long identifiers at arbitrary letters.
    # Give hashes/codes safe wrapping points without changing the saved project.
    value = re.sub(r'\S{25,}', lambda m: '\u200b'.join(
        m[0][i:i+16] for i in range(0, len(m[0]), 16)), str(value))
    return escape(value).replace('\n', '<br>')


def _number(value, places=5):
    return f'{value:.{places}f}'.rstrip('0').rstrip('.')


def _table(headers, widths, rows):
    head = ''.join(f'<th width="{width}%">{_text(title)}</th>' for title, width in zip(headers, widths))
    body = ''.join('<tr>'+''.join(f'<td>{_text(cell)}</td>' for cell in row)+'</tr>' for row in rows)
    return f'<table width="100%" cellspacing="0" cellpadding="4"><thead><tr>{head}</tr></thead>{body}</table>'


def _metrics(rows):
    cells = []
    for index in range(0, len(rows), 2):
        pair = rows[index:index+2]
        cells.append('<tr>'+''.join(f'<td width="32%">{_text(key)}</td><td width="18%"><b>{_text(value)}</b></td>'
                                   for key, value in pair)+('</tr>' if len(pair) == 2 else '<td colspan="2"></td></tr>'))
    return '<table width="100%" cellspacing="0" cellpadding="5">'+''.join(cells)+'</table>'


def report_html(project, result, totals):
    """A concise production report; full provenance remains in JSON and Excel."""
    text = ['''<html><head><style>
        body, p, h1, h2, h3, table, th, td { color: #17212b; }
        body { background-color: #ffffff; font-family: Arial; font-size: 10.5pt; }
        h1 { font-size: 19pt; margin-bottom: 8px; }
        h2 { font-size: 13pt; margin-top: 18px; margin-bottom: 8px; page-break-after: avoid; }
        h3 { font-size: 11pt; margin-bottom: 6px; page-break-after: avoid; }
        p { margin-top: 5px; margin-bottom: 7px; }
        table { border-collapse: collapse; font-size: 10.5pt; }
        th { background-color: #e8edf2; font-weight: bold; text-align: left; }
        td, th { border: 1px solid #bac3cd; vertical-align: top; }
        .page { page-break-before: always; }
        .total { font-size: 14pt; font-weight: bold; }
        </style></head><body><h1>GOKWORKS · Nesting ve sac maliyeti</h1>''',
        f'<p><b>Proje:</b> {_text(project.name)}<br><b>Rapor zamanı (UTC):</b> {_text(result.timestamp)}<br>'
        f'<b>Motor:</b> {_text(result.engine)} {_text(result.engine_version)}</p>',
        '<p>Bağımsız geometri kontrolü geçti. En iyi bulunan sonuçtur; optimum garantisi yoktur.</p>',
        '<p><b>Delik içi yerleşim:</b> Otomatik. '
        'Delik içindeki küçük parçalar çevrelerindeki delik kesilmeden önce kesilmelidir. '
        'DXF yanındaki KESIM-SIRASI.csv sırasını CAM içinde uygulayın.</p>',
        '<h2>Üretim özeti</h2>']
    text.append(_metrics([
        ('Parça adedi', totals['part_count']), ('Kullanılan levha', totals['sheet_count']),
        ('Brüt ağırlık kg', _number(totals['gross_weight'])), ('Net ağırlık kg', _number(totals['net_weight'])),
        ('Fire ağırlığı kg', _number(totals['waste_weight'])), ('Fire %', f"{100-totals['efficiency']:.2f}"),
        ('Alan verimi %', f"{totals['efficiency']:.2f}"), ('Kontur / piercing adedi', totals['piercing_count']),
        ('Kesim uzunluğu m', _number(totals['cut_length_m'])), ('Hesap birimi', 'mm; kg; TL')]))
    text.append('<h2>Maliyet özeti</h2>')
    text.append(_metrics([(title, f'{totals[key]:.2f}') for title, key in [
        ('Malzeme maliyeti TL', 'material_cost'), ('Net malzeme karşılığı TL', 'net_material_value'),
        ('Fire malzeme karşılığı TL', 'waste_material_value'), ('Kesim TL', 'cut_cost'),
        ('Piercing TL', 'piercing_cost'), ('Hazırlık TL', 'setup'), ('Sabit gider TL', 'fixed'),
        ('Kâr TL', 'profit'), ('KDV TL', 'vat')]]))
    text.append(f'<p class="total">Genel toplam TL: {totals["total"]:.2f}</p>')

    text.append('<h2 class="page">Parça özeti</h2>')
    for p in totals['part_summary']:
        text.append(f'<h3>{_text(p["code"])}</h3>')
        if p['description']:
            text.append(f'<p>{_text(p["description"])}</p>')
        text.append(_metrics([
            ('Malzeme / kalınlık', f"{p['material']} / {p['thickness']:g} mm"), ('Adet', p['quantity']),
            ('Tek parça kg', f"{p['weight']:.5f}"), ('Toplam kg', f"{p['total_weight']:.5f}"),
            ('Net alan mm² / adet', f"{p['area']:.3f}"), ('Dağıtılmış malzeme TL', f"{p['allocation']:.2f}")]))
        text.append(f'<p><b>Levhalar:</b> {_text(p["sheets"])}</p>')

    text.append('<h2>Yerleşim ayarları ve hesap notları</h2>')
    text.append(_metrics([
        ('Kenar payı mm', _number(project.options.margin)), ('Bitmiş parça aralığı mm', _number(project.options.gap)),
        ('Kerf mm', _number(project.options.kerf)),
        ('Hadde yönü', '0°/180° ile sınırlı' if project.options.grain_locked else 'Parça bazlı / serbest')]))
    text.append('<p><b>Kerf:</b> Nominal kontur; CAM kesim yolu telafisi uygulanmadı. '
                'Mesafe max(aralık, kerf) + eğri hata payları. Aynalama kapalıdır; uygun delik içleri otomatik kullanılır.</p>'
                '<p><b>Maliyet dağıtımı:</b> Her levhanın satın alma bedeli, yerleşen parçaların net alanı '
                'oranında dağıtılır; toplam kuruşu kuruşuna korunur.</p>'
                '<p><b>Kalıntılar:</b> Delikler dahil bütün boş alan fire/kalan alanıdır. '
                'Yeniden kullanım veya hurda kredisi düşülmedi.</p>'
                '<p><b>Süre tahmini:</b> Hesaplanmaz. Kesim ve piercing bedelleri girilen birim fiyatlardan gelir.</p>')

    text.append('<h2>Malzeme yoğunlukları</h2>')
    used_materials = {project.part(p.part_id).material for p in result.placements}
    text.append(_table(['Malzeme', 'Yoğunluk kg/m³'], [65, 35],
                       [(m.name, _number(m.density)) for m in project.materials if m.id in used_materials]))
    text.append('<p>Yoğunluklar yaklaşık başlangıç değerleridir. Kaynak kayıtları proje dosyasında '
                've Excel raporunun Malzemeler sayfasında korunur.</p>')
    text.append('<h2 class="page">Yerleşen örnekler</h2>')
    text.append('<p>Malzeme ve kalınlık parça özetindedir. Plaka numaraları çizim sayfalarıyla aynıdır. '
                'Maliyet, levha malzeme bedelinin örneğe ayrılan payıdır.</p>')
    text.append(_table(['Parça / örnek', 'Plaka', 'Net kg', 'Net alan mm²', 'Malzeme TL'],
                       [35, 10, 18, 20, 17],
                       [(f"{p['code']} #{p['instance']}", p['plate'], f"{p['weight']:.5f}",
                         f"{p['area']:.3f}", f"{p['allocation']:.2f}") for p in totals['parts']]))
    text.append('</body></html>')
    return ''.join(text)
