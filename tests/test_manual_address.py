import unittest
from services.manual_address import save_manual_address

class ManualAddressTests(unittest.TestCase):
    def test_save_preserves_route(self):
        route=object();state={'nav_B':(51,71),'nav_result':route}
        save_manual_address(state,{'point':[51,71],'address':'  Абай көшесі,  10 '})
        self.assertEqual(state['nav_address']['label'],'Абай көшесі, 10')
        self.assertEqual(state['nav_address']['status'],'manual')
        self.assertIs(state['nav_result'],route)
        self.assertEqual(state['nav_B'],(51,71))
    def test_old_point_rejected(self):
        state={'nav_B':(51,71)}
        save_manual_address(state,{'point':[52,71],'address':'Абай, 10'})
        self.assertNotIn('nav_address',state)
        self.assertIn('nav_error',state)
    def test_empty_and_too_long_rejected(self):
        for value in ('  ','x'*201,None):
            state={'nav_B':(51,71)}
            save_manual_address(state,{'point':[51,71],'address':value})
            self.assertNotIn('nav_address',state)
    def test_street_without_house_and_approximate_text_rejected(self):
        for value in ('Аңырақай көшесі','E 100','Аңырақай көшесінің маңы, 37','Рядом с Абай, 37'):
            with self.subTest(value=value):
                state={'nav_B':(51,71)}
                save_manual_address(state,{'point':[51,71],'address':value})
                self.assertNotIn('nav_address',state)
                self.assertIn('nav_error',state)

if __name__=='__main__':unittest.main()
