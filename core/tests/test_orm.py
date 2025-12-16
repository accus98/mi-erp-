
from core.tests.common import TransactionCase
from core.orm import Model
from core.fields import Char, Integer, Many2one
from core.registry import Registry

# Define Test Implementation Models (Transient for test duration in memory usually, 
# but here they register to Registry global. 
# Since we rollback, data is not saved, but classes stay in Registry.
# Usually Odoo loads modules. Here we define inline.)

class Partner(Model):
    _name = 'res.partner.test'
    _description = 'Test Partner'

    name = Char(string="Name", required=True)
    age = Integer(string="Age")
    parent_id = Many2one('res.partner.test', string="Parent Company")

# Manually trigger auto_init if not loaded by module loader?
# tests run in context where models might not be in DB. 
# We need to ensure table exists.

class TestORM(TransactionCase):
    
    @classmethod
    def setUpClass(cls):
        # We need to make sure the table exists for our test model
        # Connect purely to create table, then commit?
        # Or just rely on auto_init inside the test run?
        # Let's do it in a separate transaction or connection if possible, 
        # or just once.
        pass

    def setUp(self):
        super().setUp()
        # Initialize the test model table
        Partner._auto_init(self.cursor)
        self.Partner = self.env['res.partner.test']

    def test_create_and_read(self):
        """ Test unitario real con aserciones """
        partner = self.Partner.create({'name': 'Odoo Corp', 'age': 20})
        
        # Verificar que el ID existe
        self.assertTrue(partner.id)
        
        # Testear lectura
        self.assertEqual(partner.name, 'Odoo Corp')
        self.assertEqual(partner.age, 20)

    def test_update(self):
        partner = self.Partner.create({'name': 'Old Name'})
        partner.write({'name': 'New Name'})
        self.assertEqual(partner.name, 'New Name')
        
    def test_search(self):
        self.Partner.create({'name': 'A', 'age': 10})
        self.Partner.create({'name': 'B', 'age': 20})
        
        # Search all
        all_recs = self.Partner.search([])
        # Note: table might be dirty from other runs if not cleaned, 
        # but TransactionCase methods rollback. 
        # However, _auto_init might commit? Database.create_table does execute.
        # SQLite DDL inside transaction? Yes supported.
        
        # Filter
        res = self.Partner.search([('age', '>', 15)])
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].name, 'B')

    def test_unlink(self):
        p = self.Partner.create({'name': 'To Delete'})
        p_id = p.id
        p.unlink()
        
        exists = self.Partner.search([('id', '=', p_id)])
        self.assertFalse(exists)

    def test_vectorization_prefetch(self):
        # Clear table first to ensure clean state if DDL persisted
        self.cursor.execute(f'DELETE FROM "{self.Partner._table}"')
        
        p1 = self.Partner.create({'name': 'P1', 'age': 1})
        p2 = self.Partner.create({'name': 'P2', 'age': 2})
        p3 = self.Partner.create({'name': 'P3', 'age': 3})
        
        # Search returns records with prefetch set shared
        partners = self.Partner.search([], order='id')
        self.assertEqual(len(partners), 3)
        
        # Check prefetch propagation
        # (Internal check: partners._prefetch_ids should contain all 3)
        self.assertTrue(len(partners._prefetch_ids) >= 3)

        self.assertEqual(partners[0].name, 'P1')
        self.assertEqual(partners[1].name, 'P2')

    def test_singleton_error(self):
        self.cursor.execute(f'DELETE FROM "{self.Partner._table}"')
        self.Partner.create({'name': 'A'})
        self.Partner.create({'name': 'B'})
        partners = self.Partner.search([])
        
        with self.assertRaises(ValueError):
            name = partners.name # Should fail
            
    def test_mapped_filtered(self):
        self.cursor.execute(f'DELETE FROM "{self.Partner._table}"')
        self.Partner.create({'name': 'A', 'age': 10})
        self.Partner.create({'name': 'B', 'age': 20})
        partners = self.Partner.search([], order='age')
        
        names = partners.mapped('name')
        self.assertEqual(names, ['A', 'B'])
        
        adults = partners.filtered(lambda r: r.age >= 18)
        self.assertEqual(len(adults), 1)
        self.assertEqual(adults.name, 'B')

