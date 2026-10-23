"""Capture reproducible native screens without changing user preferences."""

import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from gui_qt.app import MainWindow, create_application
from modules.weight.rules import MATERIAL_GROUPS


def main():
    screens = (
        ('Koyu', 'weight-steel-dark', dict(kind='Kutu profil', material='S235JR',
            b='100', h='100', t='5', length='2000', count='3')),
        ('Açık', 'weight-delrin-light', dict(kind='Mil', material='Delrin (POM-H)',
            d='50', length='1000', count='2')),
        ('Koyu', 'weight-2379-dark', dict(kind='Sac levha', material='1.2379',
            b='200', t='40', length='300', count='1')),
        ('Koyu', 'weight-2344-dark', dict(kind='Sac levha', material='1.2344',
            b='200', t='40', length='300', count='1')),
        ('Koyu', 'weight-catalogue-dark', dict(kind='IPE', material='S235JR',
            method='Katalog alanından', area_cm2='10', unit='mm', length='1000', count='1')),
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).parent)
    parser.add_argument('screens', nargs='*', help='Capture only these screen names.')
    arguments = parser.parse_args()
    selected = arguments.screens
    unknown = set(selected) - {name for _, name, _ in screens}
    if unknown:
        parser.error('Unknown screens: ' + ', '.join(sorted(unknown)))
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    application = create_application([])
    with TemporaryDirectory() as folder:
        window = MainWindow(settings_path=Path(folder)/'settings.json')
        try:
            window.navigate('weight')
            window.resize(1240, 860); window.show()
            page = window.pages['weight']
            for theme, name, values in screens:
                if selected and name not in selected:
                    continue
                window.set_theme('dark' if theme == 'Koyu' else 'light')
                group = next(key for key, items in MATERIAL_GROUPS.items() if values['material'] in items)
                page.form.set_value('material_group', group)
                for key, value in values.items():
                    if key == 'material':
                        choices = page.form.fields['material']
                        choices.setCurrentIndex(choices.findData(value))
                    else:
                        page.form.set_value(key, value)
                page.update_timer.stop()
                page.update_result()
                application.processEvents()
                assert page.result is not None
                assert page.result.material == values['material']
                if not window.grab().save(str(arguments.output_dir/(name+'.png'))):
                    raise OSError('Ekran görüntüsü kaydedilemedi: '+name)
                print(name, page.result.total_mass_kg, 'kg')
        finally:
            window.close(); window.deleteLater(); application.processEvents()


if __name__ == '__main__':
    main()
