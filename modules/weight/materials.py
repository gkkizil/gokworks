"""Fixed nominal weight densities in kg/m³, grouped by material or steel grade."""

MATERIAL_GROUPS = {
    'Genel': ('Demir / Çelik', 'Paslanmaz', 'Alüminyum', 'Bakır', 'Pirinç C23000',
              'Fosfor bronz C51000', 'Çinko', 'Kurşun', 'Titanyum'),
    'Sac / Yapı': ('S235JR', 'S275JR', 'S355JR', 'S355J2', 'DC01 (DKP)',
                  'DC02 (DKP)', 'DC03 (DKP)', 'DC04 (DKP)', 'DX51D+Z', 'DX52D+Z',
                  'S355MC', 'P265GH'),
    'Makine / Takım': ('C45', 'C45E (CK45)', '42CrMo4', '16MnCr5', '34CrNiMo6'),
    'Kalıp Çelikleri': ('1.2311', '1.2312', '1.2344', '1.2379'),
    'Paslanmaz': ('304', '304L', '316', '316L', '430'),
    'Alüminyum alaşımları': ('1050A', '5005', '5754', '6061', '6063', '6082', '7075'),
    'Saf metaller': ('Nikel', 'Magnezyum', 'Kalay', 'Krom', 'Kobalt', 'Molibden', 'Tungsten', 'Gümüş'),
    'Plastikler': ('Delrin (POM-H)', 'Kestamit (PA6G)', 'PA6', 'PA66', 'PE-HD', 'PP', 'PTFE', 'PVC'),
}

# Selecting this entry enables the density field; every other density is fixed.
CUSTOM_MATERIAL = 'Özel malzeme'
CUSTOM_DENSITY_RANGE = (100.0, 25000.0)  # kg/m³: below cork/foam, above osmium (22.590)

MATERIALS = {
    'Demir / Çelik': 7850,
    'Paslanmaz': 8000,
    'Alüminyum': 2700,
    'Bakır': 8960,
    'Pirinç C23000': 8750,
    'Fosfor bronz C51000': 8860,
    'Çinko': 7140,
    'Kurşun': 11340,
    'Titanyum': 4506,
    **{name: 7850 for name in (*MATERIAL_GROUPS['Sac / Yapı'], *MATERIAL_GROUPS['Makine / Takım'])},
    '1.2311': 7850,
    '1.2312': 7850,
    '1.2344': 7800,
    '1.2379': 7700,
    '304': 7916,
    '316': 8000,
    '316L': 8000,
    '304L': 8000,
    '430': 7750,
    '1050A': 2710,
    '5005': 2700,
    '5754': 2700,
    '6061': 2700,
    '6063': 2700,
    '6082': 2700,
    '7075': 2810,
    'PA66': 1150,
    'Nikel': 8908,
    'Magnezyum': 1738,
    'Kalay': 7365,
    'Krom': 7190,
    'Kobalt': 8900,
    'Molibden': 10280,
    'Tungsten': 19250,
    'Gümüş': 10490,
    'PE-HD': 950,
    'Delrin (POM-H)': 1420,
    'Kestamit (PA6G)': 1150,
    'PA6': 1150,
    'PP': 916,
    'PTFE': 2070,
    'PVC': 1380,
}

MATERIAL_ALIASES = {'Pirinç': 'Pirinç C23000', 'Bronz': 'Fosfor bronz C51000'}

MATERIAL_TYPES = {
    '1.2311': 'Plastik kalıp çeliği',
    '1.2312': 'Plastik kalıp çeliği',
    '1.2344': 'Sıcak iş takım çeliği',
    '1.2379': 'Soğuk iş takım çeliği',
}

_STEEL_NOTE = 'Nominal çelik ağırlığı 7.850 kg/m³ ile hesaplanır; mekanik özellik hesabı yapılmaz.'
MATERIAL_NOTES = {
    'Demir / Çelik': 'Genel çelik için nominal ağırlık değeri; belirli bir kaliteyi temsil etmez.',
    'Paslanmaz': 'Genel nominal değer olarak 316 yoğunluğu kullanılır; biliniyorsa malzemenin kalitesini seçin.',
    'Alüminyum': 'Genel alüminyum için nominal değer; alaşım sınıfını ayrıca dikkate alın.',
    'Bakır': 'Genel bakır için nominal ağırlık değeri.',
    'Pirinç C23000': 'C23000 kırmızı pirinç için nominal değer; diğer pirinç alaşımları farklı olabilir.',
    'Fosfor bronz C51000': 'C51000 fosfor bronzu için nominal değer; diğer bronz alaşımları farklı olabilir.',
    'Çinko': 'Elementel çinkonun nominal yoğunluğu kullanılır.',
    'Kurşun': 'Elementel kurşunun nominal yoğunluğu kullanılır.',
    'Titanyum': 'Elementel titanyumun nominal yoğunluğu kullanılır.',
    **{name: _STEEL_NOTE for name in (*MATERIAL_GROUPS['Sac / Yapı'], *MATERIAL_GROUPS['Makine / Takım'])},
    '1.2311': 'Plastik kalıp çeliği. Nominal yoğunluk 7.850 kg/m³.',
    '1.2312': 'Plastik kalıp çeliği. Nominal yoğunluk 7.850 kg/m³.',
    '1.2344': 'Sıcak iş takım çeliği (X40CrMoV5-1 / H13). Nominal yoğunluk 7.800 kg/m³.',
    '1.2379': 'Soğuk iş takım çeliği (D2). Nominal yoğunluk 7.700 kg/m³.',
    **{name: 'Paslanmaz çelik kalitesi için nominal ağırlık değeri; ürün sertifikası yerine geçmez.'
       for name in MATERIAL_GROUPS['Paslanmaz']},
    'Delrin (POM-H)': 'POM homopolimer için genel malzeme kartı değeri.',
    'Kestamit (PA6G)': 'Döküm PA6G için nominal yaklaşım; genel PA6 yoğunluğu kullanılır.',
    'PA6': 'Genel PA6 malzeme kartı değeri; nem ve ürün sınıfı gerçek yoğunluğu etkileyebilir.',
    'PP': 'Genel polipropilen malzeme kartı değeri.',
    'PTFE': 'Genel PTFE malzeme kartı değeri.',
    'PVC': 'Genel PVC malzeme kartı değeri.',
}
_ALLOY = 'Alaşım veri sayfasındaki nominal yoğunluk; temper ve ürün biçimi yoğunluğu pratikte değiştirmez.'
MATERIAL_NOTES.update({
    '304L': 'EN 1.4307 (304L), çubuk ve profil veri sayfası değeri.',
    '430': 'EN 1.4016 (430) ferritik paslanmaz, sac ve plaka veri sayfası değeri.',
    '1050A': 'EN AW-1050A ticari saf alüminyum. ' + _ALLOY,
    '5005': 'EN AW-5005. ' + _ALLOY,
    '5754': 'EN AW-5754 (AlMg3). ' + _ALLOY,
    '6061': 'EN AW-6061. ' + _ALLOY,
    '6063': 'EN AW-6063 (profil alaşımı). ' + _ALLOY,
    '6082': 'EN AW-6082 (AlSi1MgMn / AlMgSi1). ' + _ALLOY,
    '7075': 'EN AW-7075 (yüksek dayanımlı, çinko alaşımlı). ' + _ALLOY,
    **{name: 'Saf elementin oda sıcaklığı yoğunluğu; ticari alaşımlar ve sinter ürünler farklıdır.'
       for name in ('Nikel', 'Magnezyum', 'Kalay', 'Krom', 'Kobalt', 'Molibden', 'Tungsten', 'Gümüş')},
    'PA66': 'Dolgusuz PA66 yarı mamul; cam elyaf takviyeli kaliteler daha ağırdır.',
    'PE-HD': 'Yüksek yoğunluklu polietilen yarı mamul.',
    '304': 'AISI 304 paslanmaz; MMPDS referanslı malzeme kartının nominal yoğunluğu kullanılır.',
    'S235JR': 'Piyasada St37 adıyla anılan grupta; sertifikadaki EN kaliteyi esas alın. ' + _STEEL_NOTE,
    'S355JR': 'Piyasada St52 adıyla anılan grupta; sertifikadaki EN kaliteyi esas alın. ' + _STEEL_NOTE,
    **{name: 'Soğuk haddelenmiş düşük karbonlu sac. ' + _STEEL_NOTE
       for name in ('DC01 (DKP)', 'DC02 (DKP)', 'DC03 (DKP)', 'DC04 (DKP)')},
    'DX51D+Z': 'Galvanizli sac; hesap çelik taban içindir. Çinko kaplaması dahil değildir.',
    'DX52D+Z': 'Galvanizli sac; hesap çelik taban içindir. Çinko kaplaması dahil değildir.',
    'S355MC': 'Soğuk şekillendirmeye uygun sıcak haddelenmiş sac. ' + _STEEL_NOTE,
    'P265GH': 'Basınçlı kap sacı için nominal ağırlık hesabı. ' + _STEEL_NOTE,
    'C45': 'C45 karbon çeliği. ' + _STEEL_NOTE,
    'C45E (CK45)': 'C45E karbon çeliği; kaliteyi ürün sertifikasından seçin. ' + _STEEL_NOTE,
    '42CrMo4': 'Islah çeliği; SAE 4140 ile benzer grupta anılır, birebir eşdeğerlik varsayılmaz. ' + _STEEL_NOTE,
})

_FREECAD = ('https://github.com/FreeCAD/FreeCAD/blob/384314776045a67fcdf09d49aa29306243578d4f/'
            'src/Mod/Material/Resources/Materials/Standard/')
_STEEL_SOURCE = ('https://github.com/robbievanleeuwen/section-properties/blob/'
                 '1e12d48b3ccb9ee1b7df8e2ac357c633cc004bdf/docs/user_guide/overview.rst')
_ELEMENT_SOURCE = ('https://github.com/Bowserinator/Periodic-Table-JSON/blob/'
                   '9090b1c472a1e68f7295e77280f374f8d125cefc/PeriodicTableJSON.json')
_AISI_SOURCE = ('https://github.com/mvernacc/material-properties-interchange/blob/'
                '561d181d8b2c83c53c17b177c21505c55809fc11/materials/materials_data/')
_STEEL_316_SOURCE = ('https://github.com/scroberts/Engineering-Materials-Database/blob/'
                     'bf225bb98d95df288a02ee3ab0ac9fb691a5c4ad/materials/metals/stainless-316.json')
_TOOL_STEEL_SOURCE = ('https://github.com/scroberts/Engineering-Materials-Database/blob/'
                     'bf225bb98d95df288a02ee3ab0ac9fb691a5c4ad/materials/metals/')
_AALCO = 'https://www.aalco.co.uk/datasheets/'
_PFM_SOURCE = ('https://github.com/RF555/PFM-Calculator/blob/'
               '1be015cb20aad00cec018a13705312073dafac5f/src/calculator/data/materials.json')
MATERIAL_SOURCES = {
    'Demir / Çelik': _STEEL_SOURCE,
    'Paslanmaz': _STEEL_316_SOURCE,
    'Alüminyum': _FREECAD + 'Metal/Aluminum/Aluminum-Generic.FCMat',
    'Bakır': _FREECAD + 'Metal/Copper/Copper-Generic.FCMat',
    'Pirinç C23000': _FREECAD + 'Metal/Copper/Copper-230.FCMat',
    'Fosfor bronz C51000': _FREECAD + 'Metal/Copper/Copper-510.FCMat',
    'Çinko': _ELEMENT_SOURCE,
    'Kurşun': _ELEMENT_SOURCE,
    'Titanyum': _ELEMENT_SOURCE,
    **{name: _STEEL_SOURCE for name in (*MATERIAL_GROUPS['Sac / Yapı'], *MATERIAL_GROUPS['Makine / Takım'])},
    '1.2311': _PFM_SOURCE,
    '1.2312': _PFM_SOURCE,
    '1.2344': _TOOL_STEEL_SOURCE + 'steel-h13.json',
    '1.2379': _PFM_SOURCE,
    '304': _AISI_SOURCE + 'AISI_304.yaml',
    '316': _STEEL_316_SOURCE,
    '316L': _AISI_SOURCE + 'AISI_316L.yaml',
    'Delrin (POM-H)': _FREECAD + 'Thermoplast/POM-Homopolymer-Generic.FCMat',
    'Kestamit (PA6G)': _FREECAD + 'Thermoplast/PA6-Generic.FCMat',
    'PA6': _FREECAD + 'Thermoplast/PA6-Generic.FCMat',
    'PP': _FREECAD + 'Thermoplast/PP-Generic.FCMat',
    'PTFE': _FREECAD + 'Thermoplast/PTFE-Generic.FCMat',
    'PVC': _FREECAD + 'Thermoplast/PVC-Generic.FCMat',
    '304L': _AALCO + 'Stainless-Steel-14307-304L-Bar-and-Section_35.ashx',
    '430': _AALCO + 'Stainless-Steel-14016-430-Sheet-and-Plate_95.ashx',
    '1050A': _AALCO + 'Aluminium-Alloy-1050A-H14-Sheet_57.ashx',
    '5005': _AALCO + 'Aluminium-Alloy-5005-H34-Sheet_137.ashx',
    '5754': _FREECAD + 'Metal/Aluminum/AlMg3F24.FCMat',
    '6061': _FREECAD + 'Metal/Aluminum/Aluminum-6061-T6.FCMat',
    '6063': _AALCO + 'Aluminium-Alloy-6063-T6-Extrusions_158.ashx',
    '6082': _FREECAD + 'Metal/Aluminum/AlMgSi1F31.FCMat',
    '7075': _FREECAD + 'Metal/Aluminum/Aluminum-7075-T6.FCMat',
    **{name: _ELEMENT_SOURCE for name in ('Nikel', 'Magnezyum', 'Kalay', 'Krom', 'Kobalt', 'Molibden',
                                          'Tungsten', 'Gümüş')},
    'PA66': 'https://www.ensingerplastics.com/en/shapes/pa66-tecamid-66-natural',
    'PE-HD': 'https://www.ensingerplastics.com/en-us/shapes/polyethylene-tecafine-hdpe-natural',
}

DENSITY_NOTE = ('Yoğunluk seçilen malzemeye göre sabittir ve kullanıcı tarafından değiştirilemez. '
                'Değerler nominal ağırlık hesabı içindir.')
