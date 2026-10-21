"""Shared Turkish labels and locale-independent uppercase conversion."""

BOM_TREE_TAB = 'Ürün ağacı'
BOM_TITLE = f'BOM - {BOM_TREE_TAB}'
KR_TITLE = 'K faktörü ve yarıçap'
KR_NAV_TITLE = 'K faktörü / yarıçap'


def turkish_upper(text):
    return str(text).translate(str.maketrans({'i': 'İ', 'ı': 'I'})).upper()
