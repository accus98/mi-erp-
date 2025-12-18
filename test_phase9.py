
import unittest
import tempfile
import shutil
import os
import ast
from pydantic import ValidationError
from core.module_graph import ModuleGraph
from core.api.schema import SchemaFactory
from core.fields import Char, Integer
from core.orm import Model
from core.registry import Registry

class TestPhase9(unittest.TestCase):
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def make_module(self, name, depends=[]):
        p = os.path.join(self.test_dir, name)
        os.makedirs(p)
        manifest = {'name': name, 'depends': depends}
        with open(os.path.join(p, '__manifest__.py'), 'w') as f:
            f.write(str(manifest))
            
    def test_module_topo_sort(self):
        # A depends on B
        # B depends on C
        # D depends on nothing
        # Order should be C, B, A, D (or D mixed in)
        self.make_module('mod_a', ['mod_b'])
        self.make_module('mod_b', ['mod_c'])
        self.make_module('mod_c', [])
        self.make_module('mod_d', [])
        
        graph = ModuleGraph(self.test_dir)
        graph.scan()
        sorted_mods = graph.topological_sort()
        
        print(f"Sorted Modules: {sorted_mods}")
        
        # Verify positions
        idx_a = sorted_mods.index('mod_a')
        idx_b = sorted_mods.index('mod_b')
        idx_c = sorted_mods.index('mod_c')
        
        # B must be before A
        self.assertLess(idx_b, idx_a, "B should load before A")
        # C must be before B
        self.assertLess(idx_c, idx_b, "C should load before B")
        
    def test_schema_factory(self):
        # Create Dummy Model
        class TestSchemaModel(Model):
            _name = 'test.schema.model'
            name = Char(required=True)
            age = Integer()
            
        # Mock Env
        class EnvMock:
            registry = Registry
            def __getitem__(self, key):
                return TestSchemaModel
                
        env = EnvMock()
        
        # Create Schema
        CreateSchema = SchemaFactory.get_create_schema(env, 'test.schema.model')
        
        # Test Validation
        with self.assertRaises(ValidationError):
            CreateSchema(age=10) # Missing name
            
        obj = CreateSchema(name="Test", age=20)
        self.assertEqual(obj.name, "Test")
        
        # Write Schema
        WriteSchema = SchemaFactory.get_write_schema(env, 'test.schema.model')
        obj2 = WriteSchema(age=25) # Partial update allowed
        self.assertEqual(obj2.age, 25)

if __name__ == '__main__':
    unittest.main()
