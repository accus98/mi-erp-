
import unittest
import os
from core.db import Database
from core.env import Environment
from core.models.ir_translation import IrTranslation
from core.tools.po_loader import POLoader
from addons.base.models.res_lang import ResLang

class TestPOLoader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = Database.connect()
        cls.cr = cls.conn.cursor()
        
        # Init Schema
        IrTranslation._auto_init(cls.cr)
        ResLang._auto_init(cls.cr)
        
        # Init Lang
        env = Environment(cls.cr, uid=1)
        if not env['res.lang'].search([('code', '=', 'es_ES')]):
            env['res.lang'].create({'name': 'Spanish', 'code': 'es_ES', 'iso_code': 'es'})
        
        cls.conn.commit()

    @classmethod
    def tearDownClass(cls):
        cr = cls.conn.cursor()
        cr.execute("DELETE FROM ir_translation")
        cls.conn.commit()
        cls.conn.close()

    def test_load_po_file(self):
        # Create temp PO file
        po_content = """
msgid "Hello World"
msgstr "Hola Mundo"

msgid "Welcome to the system."
msgstr "Bienvenido al sistema."
"""
        filename = "test_es.po"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(po_content)
            
        try:
            env = Environment(self.cr, uid=1)
            POLoader.load_po(env, filename, 'es_ES')
            
            # Check translations
            t1 = env['ir.translation'].search([
                ('type', '=', 'code'),
                ('src', '=', 'Hello World'),
                ('lang', '=', 'es_ES')
            ], limit=1)
            self.assertTrue(t1)
            self.assertEqual(t1[0].value, 'Hola Mundo')
            
            t2 = env['ir.translation'].search([
                ('type', '=', 'code'),
                ('src', '=', 'Welcome to the system.'),
                ('lang', '=', 'es_ES')
            ], limit=1)
            self.assertTrue(t2)
            self.assertEqual(t2[0].value, 'Bienvenido al sistema.')
            
            # Check module default
            self.assertEqual(t1[0].module, 'base')

        finally:
            if os.path.exists(filename):
                os.remove(filename)

if __name__ == '__main__':
    unittest.main()
