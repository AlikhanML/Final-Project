import unittest
from services.hospital_allowlist import approved_hospital
from services.dispatch import select_hospital
import test_hospital

class AllowlistTests(unittest.TestCase):
    def record(self,name,**tags):
        return {'name':name,'tags':{'amenity':'hospital',**tags}}
    def test_three_approved_names(self):
        for n in (1,2,3):
            for name in (f'Городская больница №{n}',f'№{n} көпбейінді қалалық аурухана',f'City Hospital No. {n}'):
                self.assertEqual(approved_hospital(self.record(name))['approved_number'],n)
    def test_other_number_or_type_rejected(self):
        for name in ('Городская больница №13','Городская больница №4','Детская городская больница №1','Областная больница №1','Hospital','Городская больница №1 и №2'):
            self.assertIsNone(approved_hospital(self.record(name)))
        self.assertIsNone(approved_hospital(self.record('Городская больница №1',amenity='pharmacy')))
    def test_conflicting_address_rejected(self):
        self.assertIsNone(approved_hospital(self.record('Городская больница №1',**{'addr:housenumber':'6'})))
        self.assertIsNone(approved_hospital(self.record('Городская больница №2',**{'addr:street':'Республика'})))
        self.assertIsNotNone(approved_hospital(self.record('Городская больница №3',**{'addr:street':'проспект Республики','addr:housenumber':'50/2'})))
    def test_nearer_unapproved_hospital_is_not_selected(self):
        fixture=test_hospital.HospitalTests();fixture.setUp();w=fixture.w
        w['source']['hospitals'][1]['name']='Городская больница №4'
        self.assertEqual(select_hospital(w,(51.15,71.43))['id'],'a')
        w['source']['hospitals'][0]['name']='Частная больница'
        with self.assertRaises(ValueError):select_hospital(w,(51.15,71.43))
