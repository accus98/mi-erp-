from core.orm import Model
from core.fields import Char, Integer, Many2one

class IrUiView(Model):
    _name = 'ir.ui.view'
    _description = 'UI Views'

    name = Char(string='View Name', required=True)
    model = Char(string='Model', required=True)
    type = Char(string='View Type', required=True) # form, tree, search
    arch = Char(string='Architecture', required=True) # XML
    priority = Integer(string='Priority') 
    inherit_id = Many2one('ir.ui.view', string='Inherited View')
    mode = Char(string='View Inheritance Mode', default='primary') # primary, extension

    def apply_inheritance(self, source_arch, inheritance_arch):
        """
        Apply Odoo-style XML patch.
        source_arch, inheritance_arch: XML strings.
        Returns: string (Combined XML).
        """
        import xml.etree.ElementTree as ET
        
        source_root = ET.fromstring(source_arch)
        inherit_root = ET.fromstring(inheritance_arch)
        
        # We need a parent map to handle 'replace' (remove from parent) and insertion
        parent_map = {c: p for p in source_root.iter() for c in p}
        
        for spec in inherit_root:
            # Spec is like <field name="target" position="after">...</field>
            # Or <xpath expr="...">...</xpath>
            
            node = None
            
            # 1. Locate Node
            if spec.tag == 'xpath':
                expr = spec.attrib.get('expr')
                # ElementTree limited xpath support:
                # - tag
                # - *
                # - .//tag
                # - tag[@attrib='value'] (Only 3.8+?) -> Our env includes Python 3.11 likely.
                # Assuming simple Odoo xpath: //field[@name='foo']
                # ET supports ".//field[@name='foo']"
                
                # Convert // to .// for ET relative search from root
                if expr.startswith('//'):
                    expr = "." + expr
                
                node = source_root.find(expr)
            elif spec.tag == 'field':
                name = spec.attrib.get('name')
                # Find field by name recursively
                # xpath: .//field[@name='name']
                node = source_root.find(f".//field[@name='{name}']")
            else:
                # Top level tag matching? 
                pass
            
            if node is None:
                # Fail silent or warn?
                print(f"View Inheritance Warning: Node not found for spec {spec.tag} {spec.attrib}")
                continue
            
            # 2. Apply Operation
            position = spec.attrib.get('position', 'inside')
            
            if position == 'inside':
                # Append children of spec to node
                for child in spec:
                    node.append(child)
            
            elif position == 'replace':
                if node == source_root:
                    # Replacing root?
                    print("Cannot replace root node via simple inheritance currently.")
                    continue
                
                parent = parent_map[node]
                # Find index
                # ElementTree 'replace' usually means remove and insert new content
                # Spec children become replacements
                
                # Get index
                idx = list(parent).index(node)
                parent.remove(node)
                
                # Insert spec children
                for i, child in enumerate(spec):
                    parent.insert(idx + i, child)
                    # Update parent map for new children?
                    # For simple pass we might skip updating parent_map if we don't recurse often.
                    
            elif position in ('after', 'before'):
                if node == source_root: continue
                parent = parent_map[node]
                idx = list(parent).index(node)
                
                if position == 'after':
                    idx += 1
                
                for i, child in enumerate(spec):
                    parent.insert(idx + i, child)
        
        return ET.tostring(source_root, encoding='unicode')

