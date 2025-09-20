from core_10x.code_samples.directories import ANIMALS, FISH


def test_flatten():
    f1 = ANIMALS.flatten()
    assert f1 == {
        ('Microorganisms',): 'Microorganisms',
        ('Microorganisms', 'Single Cell'): 'Single Cell',
        ('Microorganisms', 'Multi Cell'): 'Multi Cell',
        ('Mollusks',): 'Mollusks',
        ('Fishes',): 'Fishes',
        ('Fishes', 'Salt Water'): 'Salt Water',
        ('Fishes', 'Salt Water', 'Beluga'): 'Beluga',
        ('Fishes', 'Fresh Water'): 'Fresh Water',
        ('Amphibia',): 'Amphibia',
        ('Reptiles',): 'Reptiles',
        ('Birds',): 'Birds',
        ('Mammals',): 'Mammals',
        ('Mammals', 'Cats'): 'Cats',
        ('Mammals', 'Dogs'): 'Dogs',
        ('Mammals', 'Bears'): 'Bears',
        ('Mammals', 'Whales'): 'Whales',
        ('Mammals', 'Whales', 'Bluewhale'): 'Bluewhale',
        ('Mammals', 'Whales', 'Orca'): 'Orca',
        ('Mammals', 'Whales', 'Spermwhale'): 'Spermwhale',
        ('Mammals', 'Whales', 'Beluga'): 'Beluga',
    }

    f2 = ANIMALS.flatten(with_root=True)
    assert f2 == {('Animals',): 'Animals', **{('Animals', *k): v for k, v in f1.items()}}


def test_choices():
    c1 = FISH.choices()
    assert c1 == {
        'Pike Family': 'PkF',
        'Pike Family/Northern Pike': 'NPK',
        'Pike Family/Muskie': 'MSK',
        'Pike Family/Pickerel': 'PKL',
        'Perch Family': 'PeF',
        'Perch Family/Common Perch': 'PCH',
        'Perch Family/Yellow Perch': 'YPH',
        'Perch Family/Walleye': 'WLY',
        'Perch Family/Sagger': 'SGR',
        'Carp Family': 'CrF',
        'Carp Family/Common Carp': 'CRP',
        'Carp Family/Wild Carp': 'WCP',
        'Carp Family/Ide': 'IDE',
        'Carp Family/Bream': 'BRM',
        'Carp Family/Roach': 'RCH',
    }

    c2 = FISH.choices(with_root=True)
    assert c2 == {'Fresh Water Fish': 'FWF', **{f'Fresh Water Fish/{k}': v for k, v in c1.items()}}
